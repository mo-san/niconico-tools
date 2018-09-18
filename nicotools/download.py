# coding: UTF-8
import asyncio
import functools
import html
import json
import os
import re
import sys
from pathlib import Path
from string import Template
from typing import Dict, Union, Optional, List
from urllib.parse import parse_qs, unquote

import aiohttp
from bs4 import BeautifulSoup, Tag
from tqdm import tqdm

from nicotools import utils
from nicotools.utils import Msg, Err, URL, KeyGetFlv, KeyGTI, KeyDmc, DataKey


class Info(utils.Canopy):
    def __init__(self,
                 mail: Optional[str]=None,
                 password: Optional[str]=None,
                 logger: Optional[utils.NTLogger]=None,
                 session: Optional[aiohttp.ClientSession]=None,
                 limit: int=4,
                 loop: Optional[asyncio.AbstractEventLoop]=None,
                 interval: Union[int, float]=5,
                 backoff: Union[int, float]=3,
                 retries: Union[int, float]=3,
                 ):
        """
        動画視聴ページから様々なデータを集める。

        :param Optional[str] mail: メールアドレス
        :param Optional[str] password: パスワード
        :param T <= logging.logger logger: ロガーのインスタンス
        :param aiohttp.ClientSession session:
        :param int limit: 同時にアクセスする最大数
        :param asyncio.AbstractEventLoop loop: イベントループ
        :param Union[int, float] interval: うまくいかなかった場合の待ち時間
        :param Union[int, float] backoff: 待ち時間の増大倍率
        :param Union[int,float] retries: 再試行回数
        """
        super().__init__(loop=loop, logger=logger)
        self.__mail = mail
        self.__password = password
        self.session = session or self.loop.run_until_complete(self.get_session())
        self.__parallel_limit = limit
        self.interval = interval
        self.backoff = backoff
        self.retries = retries

    async def get_session(self) -> aiohttp.ClientSession:
        """
        aiohttp のセッションを返す。

        :rtype: aiohttp.ClientSession
        """
        login = utils.LogIn(mail=self.__mail, password=self.__password)
        if login.is_login:
            cook = login.cookie
        else:
            login.get_session(utils.LogIn.ask_credentials())
            cook = login.cookie
        self.logger.debug(f"Object ID of cookie (Info): {id(cook)}")
        return aiohttp.ClientSession(cookies=cook)

    def close(self):
        async def _close():
            await self.session.close()

        self.loop.run_until_complete(_close())

    def get_data(self, video_ids: List) -> Dict:
        """
        動画やコメントのダウンロードに必要なデータを集めてくる。

        :param List video_ids:
        :rtype: Dict
        """
        video_ids = utils.validator(video_ids)
        infos = self.loop.run_until_complete(
            asyncio.gather(*[self._retrieve_info(_id) for _id in video_ids]))
        result = {_id: _info for _id, _info in zip(video_ids, infos)}
        sieved_result = self.sieve(result)

        self.close()
        return sieved_result

    def sieve(self, infos: Dict) -> Dict:
        """
        非公開や削除済み動画をふるいにかける。

        :param Dict infos:
        :rtype: Dict
        """
        good = {_id: info for _id, info in infos.items()
                  if isinstance(info, dict) and info[KeyDmc.IS_PUBLIC] and not info[KeyDmc.IS_DELETED]}
        bad = list(set(infos) - set(good))
        if len(bad) > 0:
            self.logger.info(Msg.nd_deleted_or_private.format(bad))
        return good

    async def _retrieve_info(self, video_id: str) -> Dict:
        interval = self.interval
        backoff = self.backoff
        attempt = max(0, self.retries) + 1
        url = URL.URL_Watch + video_id

        async with asyncio.Semaphore(self.__parallel_limit):
            while attempt > 0:
                attempt -= 1
                async with self.session.get(url) as response:  # type: aiohttp.ClientResponse
                    if response.status == 200:
                        info_data = await response.text()
                        return self._junction(info_data)
                    elif 400 <= response.status < 500:
                        break
                    elif 500 <= response.status < 600:
                        await asyncio.sleep(interval/2)
                        print(Err.waiting_for_permission)
                        await asyncio.sleep(interval/2)
                        interval *= backoff
                    else:
                        break

    def _junction(self, content: str) -> Dict[str, Union[str, int, List[str], bool]]:
        """
        動画視聴ページのHTMLから必要な情報を取り出す。

        HTML構造は複数あり、ものによって内容が異なる。適切な担当者へ振り向ける。

        :param str content:
        :rtype: Dict[str, Union[str, int, List[str], bool]]
        """
        soup = BeautifulSoup(content, "html.parser")
        if soup.select("#Login_nico"):
            print("Login Failed", file=sys.stderr)
            sys.exit()
        _data_api = soup.select("#js-initial-watch-data")
        _watch_api = soup.select("#watchAPIDataContainer")
        if _data_api:
            return self._read_from_data_api(_data_api[0]["data-api-data"])
        elif _watch_api:
            return self._read_from_watch_api(_watch_api[0].text)
        else:
            if self.logger.is_debug:
                file_name = "_#_niconico_#_.html"
                with open(file_name, "w", encoding="utf-8") as fd:
                    fd.write(content)
                print(f"Unknown HTML structure has been met."
                      f" It's exported for debugging at {Path.cwd()/file_name}.", file=sys.stderr)

    def _read_from_data_api(self, content: str) -> Dict:
        """
        data-api-data 属性を持つタグがあるHTMLから情報を取り出す。

        :param str content: HTMLの文字列
        :rtype: Dict[str, Union[str, int, List[str], bool]]
        """
        j = json.loads(content)
        _video = j["video"]
        dmc_info = None
        session_api = None
        if _video.get("dmcInfo", None):
            dmc_info = _video["dmcInfo"]
            session_api = dmc_info["session_api"]

        info = {
            KeyDmc.VIDEO_ID     : _video["id"],  # type: str
            KeyDmc.VIDEO_URL_SM : _video["smileInfo"]["url"],  # type: str
            KeyDmc.TITLE        : _video["title"],  # type: str
            KeyDmc.FILE_NAME    : utils.t2filename(_video["title"]),  # type: str
            KeyDmc.FILE_SIZE    : None,  # type: Optional[int]
            KeyDmc.THUMBNAIL_URL: _video["thumbnailURL"],  # type: str
            KeyDmc.ECO          : bool(j["context"]["isPeakTime"]),  # type: bool
            KeyDmc.MOVIE_TYPE   : _video["movieType"],  # type: str
            KeyDmc.IS_DELETED   : _video["isDeleted"],  # type: bool
            KeyDmc.IS_PUBLIC    : _video["isPublic"],  # type: bool
            KeyDmc.IS_OFFICIAL  : _video["isOfficial"],  # type: bool
            KeyDmc.IS_PREMIUM   : j["viewer"]["isPremium"],  # type: bool

            # この6つはコメントのダウンロードに必要
            KeyDmc.USER_ID      : j["viewer"]["id"],  # type: int
            KeyDmc.USER_KEY     : j["context"]["userkey"],  # type: str
            KeyDmc.OPT_THREAD_ID: None,  # type: Optional[int]
            KeyDmc.NEEDS_KEY    : None,  # type: Optional[int]
            # ただしこの2つは dmcInfo にしかない。
            # watchAPI版との整合性のために初期化しておく。
            KeyDmc.MSG_SERVER   : None,
            KeyDmc.THREAD_ID    : None,

            # DMCサーバーからの動画のダウンロードに必要
            KeyDmc.IS_DMC       : False,  # type: bool
            KeyDmc.API_URL      : None,  # type: Optional[str]
            KeyDmc.RECIPE_ID    : None,  # type: Optional[str]
            KeyDmc.CONTENT_ID   : None,  # type: Optional[str]
            KeyDmc.VIDEO_SRC_IDS: None,  # type: Optional[List[str]]
            KeyDmc.AUDIO_SRC_IDS: None,  # type: Optional[List[str]]
            KeyDmc.HEARTBEAT    : None,  # type: Optional[int]
            KeyDmc.TOKEN        : None,  # type: Optional[str]
            KeyDmc.SIGNATURE    : None,  # type: Optional[str]
            KeyDmc.AUTH_TYPE    : None,  # type: Optional[str]
            KeyDmc.C_K_TIMEOUT  : None,  # type: Optional[int]
            KeyDmc.SVC_USER_ID  : None,  # type: Optional
            KeyDmc.PLAYER_ID    : None,  # type: Optional[str]
            KeyDmc.PRIORITY     : None,  # type: Optional[int]
        }

        if dmc_info:
            info.update({
                KeyDmc.IS_DMC       : True,  # type: bool
                KeyDmc.MSG_SERVER   : dmc_info["thread"]["server_url"],  # type: str
                KeyDmc.THREAD_ID    : dmc_info["thread"]["thread_id"],  # type: int
                KeyDmc.API_URL      : session_api["urls"][0]["url"],  # type: str
                KeyDmc.RECIPE_ID    : session_api["recipe_id"],  # type: str
                KeyDmc.CONTENT_ID   : session_api["content_id"],  # type: str
                KeyDmc.VIDEO_SRC_IDS: session_api["videos"],  # type: List[str]
                KeyDmc.AUDIO_SRC_IDS: session_api["audios"],  # type: List[str]
                KeyDmc.HEARTBEAT    : session_api["heartbeat_lifetime"],  # type: int
                KeyDmc.TOKEN        : session_api["token"],  # type: str
                KeyDmc.SIGNATURE    : session_api["signature"],  # type: str
                KeyDmc.AUTH_TYPE    : session_api["auth_types"]["http"],  # type: str
                KeyDmc.C_K_TIMEOUT  : session_api["content_key_timeout"],  # type: int
                KeyDmc.SVC_USER_ID  : info[KeyDmc.USER_ID],
                KeyDmc.PLAYER_ID    : session_api["player_id"],  # type: str
                KeyDmc.PRIORITY     : session_api["priority"],  # type: int
                KeyDmc.OPT_THREAD_ID: dmc_info["thread"]["optional_thread_id"],  # type: int
                KeyDmc.NEEDS_KEY    : int(dmc_info["thread"]["thread_key_required"]),  # type: int
            })
        return info

    def _read_from_watch_api(self, content: str) -> Dict:
        """
        watchAPIDataContainer を含む HTML から情報を取り出す。

        :param str content: HTMLの文字列
        :rtype: Dict[str, Union[str, int, List[str], bool]]
        """
        watch_api = json.loads(content)
        flash_vars = watch_api["flashvars"]
        flvinfo = utils.extract_getflv(unquote(flash_vars["flvInfo"]))
        if "dmcInfo" in flash_vars:
            dmc_info = json.loads(unquote(flash_vars["dmcInfo"]))
            session_api = dmc_info["session_api"]
        else:
            dmc_info = None
            session_api = None

        info = {
            KeyDmc.VIDEO_ID     : flash_vars["videoId"],  # type: str
            KeyDmc.VIDEO_URL_SM : flvinfo[KeyGetFlv.VIDEO_URL],  # type: str
            KeyDmc.TITLE        : flash_vars["videoTitle"],  # type: str
            KeyDmc.FILE_NAME    : utils.t2filename(flash_vars["videoTitle"]),
            KeyDmc.FILE_SIZE    : None,  # type: Optional[int]
            KeyDmc.THUMBNAIL_URL: flash_vars["thumbImage"],  # type: str
            KeyDmc.ECO          : bool(flash_vars.get("eco", 0)),  # type: bool
            KeyDmc.MOVIE_TYPE   : flash_vars["movie_type"],  # type: str
            KeyDmc.IS_DELETED   : watch_api["videoDetail"]["isDeleted"],  # type: bool
            KeyDmc.IS_PUBLIC    : watch_api["videoDetail"]["is_public"],  # type: bool
            KeyDmc.IS_OFFICIAL  : watch_api["videoDetail"]["is_official"],  # type: bool
            KeyDmc.IS_PREMIUM   : watch_api["viewerInfo"]["isPremium"],  # type: bool

            # この6つはコメントのダウンロードに必要
            KeyDmc.USER_ID      : flvinfo[KeyGetFlv.USER_ID],  # type: int
            KeyDmc.USER_KEY     : flvinfo[KeyGetFlv.USER_KEY],  # type: str
            KeyDmc.MSG_SERVER   : flvinfo[KeyGetFlv.MSG_SERVER],  # type: str
            KeyDmc.THREAD_ID    : flvinfo[KeyGetFlv.THREAD_ID],  # type: int
            KeyDmc.OPT_THREAD_ID: flvinfo[KeyGetFlv.OPT_THREAD_ID],  # type: Optional[int]
            KeyDmc.NEEDS_KEY    : flvinfo[KeyGetFlv.NEEDS_KEY],  # type: Optional[int]

            # DMCサーバーからの動画のダウンロードに必要
            KeyDmc.IS_DMC       : False,  # type: bool
            KeyDmc.API_URL      : None,  # type: Optional[str]
            KeyDmc.RECIPE_ID    : None,  # type: Optional[str]
            KeyDmc.CONTENT_ID   : None,  # type: Optional[str]
            KeyDmc.VIDEO_SRC_IDS: None,  # type: Optional[List[str]]
            KeyDmc.AUDIO_SRC_IDS: None,  # type: Optional[List[str]]
            KeyDmc.HEARTBEAT    : None,  # type: Optional[int]
            KeyDmc.TOKEN        : None,  # type: Optional[str]
            KeyDmc.SIGNATURE    : None,  # type: Optional[str]
            KeyDmc.AUTH_TYPE    : None,  # type: Optional[str]
            KeyDmc.C_K_TIMEOUT  : None,  # type: Optional[int]
            KeyDmc.SVC_USER_ID  : None,  # type: Optional
            KeyDmc.PLAYER_ID    : None,  # type: Optional[str]
            KeyDmc.PRIORITY     : None,  # type: Optional[int]
        }
        if dmc_info:
            info.update({
                KeyDmc.IS_DMC       : True,  # type: bool
                KeyDmc.API_URL      : session_api["api_urls"][0],  # type: str
                KeyDmc.RECIPE_ID    : session_api["recipe_id"],  # type: str
                KeyDmc.CONTENT_ID   : session_api["content_id"],  # type: str
                KeyDmc.VIDEO_SRC_IDS: session_api["videos"],  # type: List[str]
                KeyDmc.AUDIO_SRC_IDS: session_api["audios"],  # type: List[str]
                KeyDmc.HEARTBEAT    : session_api["heartbeat_lifetime"],  # type: int
                KeyDmc.TOKEN        : session_api["token"],  # type: str
                KeyDmc.SIGNATURE    : session_api["signature"],  # type: str
                KeyDmc.AUTH_TYPE    : session_api["auth_types"]["http"],  # type: str
                KeyDmc.C_K_TIMEOUT  : session_api["content_key_timeout"],  # type: int
                KeyDmc.SVC_USER_ID  : info[KeyDmc.USER_ID],
                KeyDmc.PLAYER_ID    : session_api["player_id"],  # type: str
                KeyDmc.PRIORITY     : session_api["priority"],  # type: int
                # KeyDmc.OPT_THREAD_ID: dmc_info["thread"]["optional_thread_id"],  # type: int
                # KeyDmc.NEEDS_KEY    : dmc_info["thread"]["thread_key_required"],  # type: bool
            })
        return info


class Thumbnail(utils.Canopy):
    def __init__(self,
                 logger: Optional[utils.NTLogger]=None,
                 limit: int=8,
                 session: Optional[aiohttp.ClientSession]=None,
                 loop: Optional[asyncio.AbstractEventLoop]=None,
                 ):
        """
        サムネイル画像をダウンロードする。

        :param T<= logging.logger logger: ロガー
        :param int limit: 同時にアクセスする最大数
        :param aiohttp.ClientSession session:
        :param asyncio.AbstractEventLoop loop: イベントループ
        """
        super().__init__(loop=loop, logger=logger)
        self.undone = []
        self.done = []
        self.__bucket = {}
        self.session = session or self.loop.run_until_complete(self.get_session())
        self.__parallel_limit = limit
        self.glossary = {}
        self.save_dir = None  # type: Path

    async def get_session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession()

    def close(self):
        async def _close():
            await self.session.close()

        self.loop.run_until_complete(_close())

    def start(self, glossary: Union[List, Dict],
              save_dir: Union[str, Path], is_large: bool=True):
        """
        ダウンロードを開始する。

        :param dict[str, dict[str, int | str]] | list[str] glossary:
         動画の情報が入った辞書またはIDのリスト
        :param str | Path save_dir:
        :param bool is_large: 大きいサムネイルを取りに行くかどうか
        :rtype: list
        """
        if isinstance(glossary, list):
            glossary = utils.validator(glossary)
            glossary = self.loop.run_until_complete(self._get_infos(glossary))
        self.glossary = glossary

        self.save_dir = utils.get_dir(save_dir)

        if len(self.glossary) > 0:
            self.loop.run_until_complete(self._download(list(self.glossary), is_large))
            while len(self.undone) > 0:
                self.loop.run_until_complete(self._download(self.undone, False))
        self.close()
        return self.done

    async def _download(self, video_ids: list, islarge: bool=True) -> None:
        urls = self._make_urls(video_ids, islarge)

        futures = []
        for idx, video_id, _url in zip(range(len(video_ids)), video_ids, urls):
            coro = self._worker(idx, video_id, _url)
            f = asyncio.ensure_future(coro)
            f.add_done_callback(functools.partial(self._saver, video_id))
            futures.append(f)
        await asyncio.wait(futures, loop=self.loop)

    async def _worker(self, idx: int, video_id: str, url: str) -> Optional[bytes]:
        async with asyncio.Semaphore(self.__parallel_limit):

            self.logger.info(Msg.nd_download_pict.format(
                idx + 1, len(self.glossary), video_id, self.glossary[video_id][KeyGTI.TITLE]))

            try:
                async with self.session.get(url, timeout=10) as response:
                    if response.status == 200:
                        # ダウンロードに成功したら「未完了のリスト」から取り除く
                        if video_id in self.undone:
                            self.undone.remove(video_id)
                        return await response.content.read()
                    elif response.status == 404:
                        self.undone.append(video_id)
            except asyncio.TimeoutError:
                return None

    def _saver(self, video_id: str, coroutine: asyncio.Task) -> None:
        image_data = coroutine.result()
        if image_data:
            file_path = utils.make_name(self.glossary[video_id], self.save_dir, extention="jpg")
            self.logger.debug(f"File Path: {file_path}")

            with file_path.open('wb') as f:
                f.write(image_data)
            self.logger.info(Msg.nd_download_done.format(path=file_path))
            self.done.append(video_id)

    def _make_urls(self, video_ids: list, is_large: bool=True) -> list:
        """

        :param List[str] video_ids:
        :param bool is_large:
        :rtype: List[str]
        """
        if is_large:
            urls = [f"{self.glossary[_id][KeyGTI.THUMBNAIL_URL]}.L" for _id in video_ids]
        else:
            urls = [self.glossary[_id][KeyGTI.THUMBNAIL_URL] for _id in video_ids]
        return urls

    async def _get_infos(self, queue: List[str]) -> Dict[str, Dict]:
        """
        getthumbinfo APIから、細かな情報をもらってくる

        * file_name         str
        * thumbnail_url     str
        * title             str
        * video_id          str

        :param List[str] queue: 動画IDのリスト
        :rtype: Dict[str, Dict]
        """
        tasks = [self._get_infos_worker(video_id) for video_id in queue]
        await asyncio.wait(tasks, loop=self.loop)
        bad = list(set(queue) - set(self.__bucket))
        if len(bad) > 0:
            self.logger.info(Msg.nd_deleted_or_private.format(bad))
        result = self.__bucket
        del self.__bucket
        return result

    async def _get_infos_worker(self, video_id: str):
        async with asyncio.Semaphore(self.__parallel_limit):
            async with self.session.get(URL.URL_Info + video_id) as resp:
                result = await resp.text()

            soup = BeautifulSoup(result, "html.parser")
            if soup.nicovideo_thumb_response["status"].lower() == "ok":
                self.__bucket[video_id] = {
                    KeyGTI.FILE_NAME    : utils.t2filename(soup.select(KeyGTI.TITLE)[0].text),
                    KeyGTI.THUMBNAIL_URL: soup.select(KeyGTI.THUMBNAIL_URL)[0].text,
                    KeyGTI.TITLE        : html.unescape(soup.select(KeyGTI.TITLE)[0].text),
                    KeyGTI.VIDEO_ID     : video_id
                }


class Video(utils.Canopy):
    def __init__(self,
                 videoids: Union[List, Dict],
                 save_dir: Union[str, Path]=None,
                 mail: Optional[str]=None,
                 password: Optional[str]=None,
                 logger: Optional[utils.NTLogger]=None,
                 chunk_size: int=1024*50,
                 multiline: bool=True,
                 smile: bool=False,
                 division: int=4,
                 loop: Optional[asyncio.AbstractEventLoop]=None,
                 ):
        """
        動画をダウンロードする。

        :param mail: メールアドレス
        :param password: パスワード
        :param logger: ロガー
        :param division: いくつに分割するか
        :param chunk_size: サーバーに一度に要求するデータ量
        :param multiline: プログレスバーを複数行で表示するか
        :param loop: イベントループ
        """
        super().__init__(loop=loop, logger=logger)
        self.session = self.loop.run_until_complete(self.get_session(mail, password))
        self.commons = {
            DataKey.SESSION     : self.session,
            DataKey.LOGGER      : self.logger,
            DataKey.LOOP        : self.loop,
            DataKey.CHUNK_SIZE  : chunk_size,
            DataKey.IS_MULTILINE: multiline,
            DataKey.IS_SMILE    : smile,
            DataKey.DIVISION    : division,
            DataKey.SAVE_DIR    : utils.get_dir(save_dir)
        }  # type: Dict[str, Union[int, bool, Path, aiohttp.ClientSession, asyncio.AbstractEventLoop, utils.NTLogger]]

        self.glossary = videoids
        if isinstance(videoids, list):
            info = Info(mail=mail, password=password, session=self.commons[DataKey.SESSION])
            self.glossary = info.get_data(utils.validator(videoids))
            self.commons[DataKey.SESSION] = info.session


    async def get_session(self, mail: str, password: str) -> aiohttp.ClientSession:
        cook = utils.LogIn(mail=mail, password=password).cookie
        return aiohttp.ClientSession(cookies=cook)

    def start(self):
        if self.commons[DataKey.IS_SMILE]:
            VideoSmile(self.glossary, self.commons).callee()
        else:
            dmc_list = {key: val for key, val in self.glossary.items() if val[KeyDmc.IS_DMC] is True}
            sml_list = {key: val for key, val in self.glossary.items() if val[KeyDmc.IS_DMC] is False}
            VideoDmc(dmc_list, self.commons).callee()
            VideoSmile(sml_list, self.commons).callee()

        self.close()
        return True

    def close(self):
        async def _close():
            await self.session.close()

        self.loop.run_until_complete(_close())



class VideoSmile:
    def __init__(self,
                 glossary: Dict[str, Union[str, int, bool, List]],
                 common: Dict[str, Union[int, bool, Path, aiohttp.ClientSession,
                         asyncio.AbstractEventLoop, utils.NTLogger]]):
        """
        Smileサーバーから動画をダウンロードする。

        """
        self.glossary = glossary
        self.session = common[DataKey.SESSION]
        self.logger = common[DataKey.LOGGER]
        self.loop = common[DataKey.LOOP]
        self.save_dir = common[DataKey.SAVE_DIR]
        self.chunk_size = common[DataKey.CHUNK_SIZE]
        self.multiline = common[DataKey.IS_MULTILINE]
        self.smile = common[DataKey.IS_SMILE]
        self.division = common[DataKey.DIVISION]
        # (実際のダウンロード前のファイルサイズの確認で)同時にアクセスする最大数
        self.__parallel_limit = 4
        # 分割数と同じだけの要素を持つリストを作り、各要素にそれぞれが
        # 保存したファイルサイズを記録する。プログレスバーに利用する。
        self.__downloaded_size = [0] * common[DataKey.DIVISION]  # type: List[int]

    def callee(self):
        # まず各動画のファイルサイズを集める。
        self.loop.run_until_complete(self._push_file_size())
        self.loop.run_until_complete(self._broker())
        return True

    async def _push_file_size(self):
        video_ids = sorted(self.glossary)
        tasks = [self._get_file_size_worker(video_id) for video_id in video_ids]
        async with asyncio.Semaphore(self.__parallel_limit):
            result = await asyncio.gather(*tasks)
        for _id, size in zip(video_ids, result):
            self.glossary[_id][KeyDmc.FILE_SIZE] = size

    async def _get_file_size_worker(self, video_id: str) -> int:
        vid_url = self.glossary[video_id][KeyDmc.VIDEO_URL_SM]
        self.logger.debug(f"Video ID: {video_id}, Video URL: {vid_url}")
        async with self.session.head(vid_url) as resp:
            headers = resp.headers
            self.logger.debug(f"Headers: {str(headers)}")
            return int(headers["content-length"])

    async def _broker(self):
        futures = []
        for idx, video_id in enumerate(self.glossary):
            coro = self._download(idx, video_id)
            f = asyncio.ensure_future(coro)
            f.add_done_callback(self._combiner)
            futures.append(f)
        await asyncio.wait(futures, loop=self.loop)

    async def _download(self, idx: int, video_id: str):
        division = self.glossary[DataKey.DIVISION]
        file_path = utils.make_name(self.glossary, self.save_dir)

        self.logger.info(Msg.nd_download_video.format(
            idx + 1, len(self.glossary), video_id, self.glossary[video_id][KeyDmc.TITLE]))

        video_url = self.glossary[video_id][KeyDmc.VIDEO_URL_SM]
        file_size = self.glossary[video_id][KeyDmc.FILE_SIZE]
        headers = [{
            "Range": f"bytes={int(file_size*order/division)}-{int((file_size*(order+1))/division-1)}"
           } for order in range(division)]

        for i, h in enumerate(headers):
            self.logger.debug(f"Header {i}: {str(h)}")

        if self.glossary[DataKey.IS_MULTILINE]:
            progress_bars = [tqdm(total=int(file_size / division),
                                  leave=False, position=order,
                                  unit="B", unit_scale=True,
                                  file=sys.stdout)
                             for order in range(division)]  # type: List[tqdm]
            tasks = [self._download_worker(file_path, video_url, header, order, pbar)
                     for header, order, pbar
                     in zip(headers, range(division), progress_bars)]
            progress_bars = await asyncio.gather(*tasks)  # type: List[tqdm]
            # ネストの「内側」から順に消さないと棒が画面に残る。
            for pbar in reversed(progress_bars):
                pbar.close()
        else:
            tasks = [self._download_worker(file_path, video_url, header, order)
                     for header, order
                     in zip(headers, range(division))]
            await asyncio.gather(*tasks, self._counter_whole(file_size))

    async def _download_worker(self, file_path: Union[str, Path], video_url: str,
                               header: dict, order: int, pbar: tqdm=None) -> tqdm:
        file_path = Path(f"{file_path}.{order:03}")
        # => video.mp4.000 ～ video.mp4.003 (4分割の場合)
        with file_path.open("wb") as fd:
            async with self.session.get(url=video_url, headers=header) as video_data:
                self.logger.debug(f"Started! Header: {header}, Video URL: {video_url}")
                while True:
                    data = await video_data.content.read(self.glossary[DataKey.CHUNK_SIZE])
                    if not data:
                        break
                    downloaded_size = fd.write(data)
                    self.__downloaded_size[order] += downloaded_size
                    if pbar:
                        pbar.update(downloaded_size)
        self.logger.debug(f"Order {order}: done!")
        return pbar

    async def _counter_whole(self, file_size: int, interval: int=1):
        """
        ダウンロード済みのファイルサイズを総合して一つのプログレスバーに表示する。

        :param int file_size: 全体のファイルサイズ
        :param int interval: ダウンロード率を更新する間隔
        """
        with tqdm(total=file_size, unit="B") as pbar:
            oldsize = 0
            while True:
                newsize = sum(self.__downloaded_size)
                if newsize >= file_size:
                    pbar.update(file_size - oldsize)
                    break
                pbar.update(newsize - oldsize)
                oldsize = newsize
                await asyncio.sleep(interval)

    def _combiner(self, coroutine: asyncio.Task):
        """
        ダウンロードが終わった後に分割したそれぞれを一つにまとめる関数。

        :param asyncio.Task coroutine: 動画をダウンロードしたタスク
        """
        if coroutine.done() and not coroutine.cancelled():
            file_path = utils.make_name(self.glossary, self.save_dir)
            file_names = [f"{file_path}.{order:03}" for order in range(self.glossary[DataKey.DIVISION])]
            self.logger.debug(f"File names: {file_names}")
            with file_path.open("wb") as fd:
                for name in file_names:
                    with open(name, "rb") as file:
                        fd.write(file.read())
                    os.remove(name)
            self.logger.info(Msg.nd_download_done.format(path=file_path))


class VideoDmc:
    def __init__(self,
                 glossary: Dict[str, Union[str, int, bool, List]],
                 common: Dict[str, Union[int, bool, Path, aiohttp.ClientSession,
                                         asyncio.AbstractEventLoop, utils.NTLogger]]):
        """
        DMCサーバーから動画をダウンロードする。
        """
        self.glossary = glossary
        self.session = common[DataKey.SESSION]
        self.loop = common[DataKey.LOOP]
        self.logger = common[DataKey.LOGGER]
        self.session = common[DataKey.SESSION]
        self.logger = common[DataKey.LOGGER]
        self.loop = common[DataKey.LOOP]
        self.save_dir = common[DataKey.SAVE_DIR]
        self.chunk_size = common[DataKey.CHUNK_SIZE]
        self.multiline = common[DataKey.IS_MULTILINE]
        self.smile = common[DataKey.IS_SMILE]
        self.division = common[DataKey.DIVISION]
        self.glossary = glossary
        self.__downloaded_size = [0] * common[DataKey.DIVISION]  # type: List[int]

    def callee(self, xml: bool=True):
        self.loop.run_until_complete(self._broker(xml))
        return True

    async def _broker(self, xml: bool=True) -> None:
        for idx, video_id in enumerate(self.glossary):
            if xml:
                res_xml = await self._first_nego_xml(video_id)
                video_url = self._extract_video_url_xml(res_xml)
                coro_heartbeat = asyncio.ensure_future(self._heartbeat(video_id, res_xml))
            else:
                res_json = await self._first_nego_json(video_id)
                video_url = self._extract_video_url_json(res_json)
                coro_heartbeat = asyncio.ensure_future(self._heartbeat(video_id, res_json))

            self.logger.debug(f"動画URL: {video_url}")
            coro_download = asyncio.ensure_future(self._download(idx, video_id, video_url))
            coro_download.add_done_callback(functools.partial(self._canceler, coro_heartbeat))
            coro_download.add_done_callback(self._combiner)
            tasks = [coro_download, coro_heartbeat]
            await asyncio.gather(*tasks)

    async def _first_nego_xml(self, video_id: str) -> str:
        payload = self._make_param_xml(self.glossary)
        async with self.session.post(
                url=self.glossary[video_id][KeyDmc.API_URL],
                params={"_format": "xml"},
                data=payload,
        ) as response:  # type: aiohttp.ClientResponse
            return await response.text()

    async def _first_nego_json(self, video_id: str) -> str:  # pragma: no cover
        payload = self._make_param_json(self.glossary)
        async with self.session.post(
                url=self.glossary[video_id][KeyDmc.API_URL],
                params={"_format": "json"},
                data=payload,
        ) as response:  # type: aiohttp.ClientResponse
            return await response.text()

    def _make_param_xml(self, info: Dict[str, str]) -> str:
        info.update({
            "video_src_ids_xml": "".join(map(
                lambda _: f"<string>{_}</string>", info[KeyDmc.VIDEO_SRC_IDS])),
            "audio_src_ids_xml": "".join(map(
                lambda _: f"<string>{_}</string>", info[KeyDmc.AUDIO_SRC_IDS]))
        })
        xml = Template("""<session>
          <recipe_id>${recipe_id}</recipe_id>
          <content_id>${content_id}</content_id>
          <content_type>movie</content_type>
          <protocol>
            <name>http</name>
            <parameters>
              <http_parameters>
                <method>GET</method>
                <parameters>
                  <http_output_download_parameters>
                    <file_extension>${movie_type}</file_extension>
                  </http_output_download_parameters>
                </parameters>
              </http_parameters>
            </parameters>
          </protocol>
          <priority>${priority}</priority>
          <content_src_id_sets>
            <content_src_id_set>
              <content_src_ids>
                <src_id_to_mux>
                  <video_src_ids>
                    ${video_src_ids_xml}
                  </video_src_ids>
                  <audio_src_ids>
                    ${audio_src_ids_xml}
                  </audio_src_ids>
                </src_id_to_mux>
              </content_src_ids>
            </content_src_id_set>
          </content_src_id_sets>
          <keep_method>
            <heartbeat>
              <lifetime>${heartbeat}</lifetime>
            </heartbeat>
          </keep_method>
          <timing_constraint>unlimited</timing_constraint>
          <session_operation_auth>
            <session_operation_auth_by_signature>
              <token>${token}</token>
              <signature>${signature}</signature>
            </session_operation_auth_by_signature>
          </session_operation_auth>
          <content_auth>
            <auth_type>${auth_type}</auth_type>
            <service_id>nicovideo</service_id>
            <service_user_id>${service_user_id}</service_user_id>
            <max_content_count>10</max_content_count>
            <content_key_timeout>${content_key_timeout}</content_key_timeout>
          </content_auth>
          <client_info>
            <player_id>${player_id}</player_id>
          </client_info>
        </session>
        """)
        return xml.substitute(info)

    def _make_param_json(self, info: Dict[str, Union[str, list, int]]) -> str:  # pragma: no cover
        param = {
            "session": {
                "recipe_id": info[KeyDmc.RECIPE_ID],
                "content_id": info[KeyDmc.CONTENT_ID],
                "content_type": "movie",
                "content_src_id_sets": [
                    {
                        "content_src_ids": [
                            {
                                "src_id_to_mux": {
                                    "video_src_ids": info[KeyDmc.VIDEO_SRC_IDS],
                                    "audio_src_ids": info[KeyDmc.AUDIO_SRC_IDS]
                                }
                            }
                        ]
                    }
                ],
                "timing_constraint": "unlimited",
                "keep_method": {
                    "heartbeat": {
                        "lifetime": info[KeyDmc.HEARTBEAT]
                    }
                },
                "protocol": {
                    "name": "http",
                    "parameters": {
                        "http_parameters": {
                            "parameters": {
                                "http_output_download_parameters": []
                            }
                        }
                    }
                },
                "content_uri": "",
                "session_operation_auth": {
                    "session_operation_auth_by_signature": {
                        "token": info[KeyDmc.TOKEN],
                        "signature": info[KeyDmc.SIGNATURE]
                    }
                },
                "content_auth": {
                    "auth_type": info[KeyDmc.AUTH_TYPE],
                    "max_content_count": 10,
                    "content_key_timeout": info[KeyDmc.C_K_TIMEOUT],
                    "service_id": "nicovideo",
                    "service_user_id": info[KeyDmc.SVC_USER_ID]
                },
                "client_info": {
                    "player_id": info[KeyDmc.PLAYER_ID]
                },
                "priority": info[KeyDmc.PRIORITY]
            }
        }
        result = json.dumps(param)
        return result

    def _extract_video_url_xml(self, text: str) -> str:
        self.logger.debug(f"Returned XML data: {text}")
        soup = BeautifulSoup(text, "html.parser")
        url_tag = soup.content_uri  # type: Tag
        return url_tag.text

    def _extract_video_url_json(self, text: str) -> str:  # pragma: no cover
        self.logger.debug(f"Returned JSON data: {text}")
        soup = json.loads(text)
        url_tag = soup["data"]["session"]["content_uri"]
        return url_tag

    def _extract_session_id_xml(self, text: str) -> str:
        soup = BeautifulSoup(text, "html.parser")
        id_tag = soup.session.id  # type: Tag
        self.logger.debug(f"Session ID: {id_tag.text}")
        return id_tag.text

    def _extract_session_id_json(self, text: str) -> str:  # pragma: no cover
        soup = json.loads(text)
        id_tag = soup["data"]["session"]["id"]
        self.logger.debug(f"Session ID: {id_tag}")
        return id_tag.text

    def _extract_session_tag(self, text: str) -> str:
        return re.sub(".+(<session>.+</session>).+", r"\1", text)
        # return xml_text[xml_text.find("<session>"): xml_text.find("</session>")+10]

    async def _heartbeat(self, video_id: str, text: str) -> None:
        """
        動画を視聴中に定期的に特定のデータを送信し続ける必要がある。そのための関数。

        :param video_id:
        :param text:
        """
        try:
            self.logger.debug(f"Returned XML: {text}")
            api_url = self.glossary[video_id][KeyDmc.API_URL]  # type: str
            # 1分ちょうどで送ると遅れるので、待ち時間を少し早める
            waiting = (self.glossary[video_id][KeyDmc.HEARTBEAT] / 1000) - 5
            companion = self._extract_session_tag(text)  # type: str
            session_id = self._extract_session_id_xml(text)  # type: str
            await asyncio.sleep(waiting)
            async with self.session.post(
                    url=api_url + "/" + session_id,
                    params={"_format": "xml", "_method": "PUT"},
                    data=companion
            ) as response:  # type: aiohttp.ClientResponse
                res_text = await response.text()
            await self._heartbeat(video_id, res_text)
        except asyncio.CancelledError:
            pass

    async def _get_file_size(self, video_id: str, video_url: str) -> int:
        self.logger.debug(f"Video ID: {video_id}, Video URL: {video_url}")
        async with self.session.head(video_url) as resp:
            headers = resp.headers
            self.logger.debug(str(headers))
            return int(headers["content-length"])

    async def _download(self, idx: int, video_id: str, video_url: str):
        division = self.glossary[DataKey.DIVISION]
        file_path = utils.make_name(self.glossary, self.save_dir)

        self.logger.info(Msg.nd_download_video.format(
            idx + 1, len(self.glossary), video_id, self.glossary[video_id][KeyDmc.TITLE]))

        file_size = await self._get_file_size(video_id, video_url)
        headers = [{
            "Range": f"bytes={int(file_size*order/division)}-{int((file_size*(order+1))/division-1)}"
        } for order in range(division)]

        for o, h in zip(range(division), headers):
            self.logger.debug(f"Order {o}: {h}")

        if self.glossary[DataKey.IS_MULTILINE]:
            progress_bars = [tqdm(total=int(file_size / division),
                                  leave=False, position=order,
                                  unit="B", unit_scale=True,
                                  file=sys.stdout)
                             for order in range(division)]  # type: List[tqdm]
            tasks = [self._download_worker(file_path, video_url, header, order, pbar)
                     for header, order, pbar
                     in zip(headers, range(division), progress_bars)]
            progress_bars = await asyncio.gather(*tasks)  # type: List[tqdm]
            # ネストの「内側」から順に消さないと棒が画面に残る。
            for pbar in reversed(progress_bars):
                pbar.close()
        else:
            tasks = [self._download_worker(file_path, video_url, header, order)
                     for header, order
                     in zip(headers, range(division))]
            await asyncio.gather(*tasks, self._counter_whole(file_size))

    async def _download_worker(self, file_path: Union[str, Path], video_url: str,
                               header: dict, order: int, pbar: tqdm = None) -> tqdm:
        file_path = Path(f"{file_path}.{order:03}")
        # => video.mp4.000 ～ video.mp4.003 (4分割の場合)
        self.logger.debug(file_path)
        with file_path.open("wb") as fd:
            async with self.session.get(url=video_url, headers=header) as video_data:
                self.logger.debug(f"Started! Header: {header}, Video URL: {video_url}")
                while True:
                    data = await video_data.content.read(self.glossary[DataKey.CHUNK_SIZE])
                    if not data:
                        break
                    downloaded_size = fd.write(data)
                    self.__downloaded_size[order] += downloaded_size
                    if pbar:
                        pbar.update(downloaded_size)
        self.logger.debug(f"Order {order}: done!")
        return pbar

    def _canceler(self, task_to_cancel: asyncio.Task, _: asyncio.Task) -> bool:
        """
        動画のダウンロードが終わった後にHeartbeatを止めるための関数。

        :param asyncio.Task task_to_cancel:
        :param asyncio.Task _:
        :rtype: bool
        """
        return task_to_cancel.cancel()

    async def _counter_whole(self, file_size: int, interval: int=1):
        with tqdm(total=file_size, unit="B") as pbar:
            oldsize = 0
            while True:
                newsize = sum(self.__downloaded_size)
                if newsize >= file_size:
                    pbar.update(file_size - oldsize)
                    break
                pbar.update(newsize - oldsize)
                oldsize = newsize
                await asyncio.sleep(interval)

    def _combiner(self, coroutine: asyncio.Task):
        """
        ダウンロードが終わった後に分割したそれぞれを一つにまとめる関数。

        :param asyncio.Task coroutine:
        """
        if coroutine.done() and not coroutine.cancelled():
            file_path = utils.make_name(self.glossary, self.save_dir)
            file_names = [f"{file_path}.{order:03}" for order in range(self.glossary[DataKey.DIVISION])]
            with file_path.open("wb") as fd:
                for name in file_names:
                    with open(name, "rb") as file:
                        fd.write(file.read())
                    os.remove(name)
            self.logger.info(Msg.nd_download_done.format(path=file_path))


class Comment(utils.Canopy):
    def __init__(self,
                 mail: str=None, password: str=None,
                 logger: utils.NTLogger=None,
                 session: aiohttp.ClientSession=None,
                 limit: int=4,
                 wayback=False,
                 loop: asyncio.AbstractEventLoop=None,
                 ):
        """
        コメントをダウンロードする。

        :param mail: メールアドレス
        :param password: パスワード
        :param logger: ロガー
        :param session: セッション
        :param limit: 同時にアクセスする最大数
        :param wayback: 過去ログを取りに行くかどうか
        :param loop: イベントループ
        """
        super().__init__(loop=loop, logger=logger)
        self.__mail = mail
        self.__password = password
        self.__downloaded_size = None  # type: List[int]
        self.session = session or self.loop.run_until_complete(self.get_session())
        self.__parallel_limit = limit
        self.__wayback = wayback
        self.glossary = {}
        self.save_dir = None  # type: Path

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session:
            return self.session
        else:
            cook = utils.LogIn(mail=self.__mail, password=self.__password).cookie
            return aiohttp.ClientSession(cookies=cook)

    def close(self):
        async def _close():
            await self.session.close()

        self.loop.run_until_complete(_close())

    def start(self, glossary, save_dir, xml=False, density: str="0-99999:9999,1000"):
        """
        ダウンロードを開始する。

        0-99999:9999,1000: 「0分～99999分までの範囲で
        一分間あたり9999件、直近の1000件を取得する」の意味。

        :param dict[str, dict[str, int | str]] | list[str] glossary:
        :param str | Path save_dir:
        :param bool xml:
        :param str density: ダウンロードするコメントの密度。
        """
        self.save_dir = utils.get_dir(save_dir)

        if isinstance(glossary, list):
            glossary = utils.validator(glossary)
            info = Info(mail=self.__mail, password=self.__password, session=self.session)
            glossary = info.get_data(glossary)
            self.session = info.session
        self.glossary = glossary

        futures = []
        for idx, video_id in enumerate(self.glossary):
            coro = self._download(idx, self.glossary[video_id], xml, density)
            f = asyncio.ensure_future(coro)
            f.add_done_callback(functools.partial(self.saver, video_id, xml))
            futures.append(f)

        self.loop.run_until_complete(asyncio.wait(futures, loop=self.loop))
        self.close()
        return True

    async def _download(self, idx: int, info: dict, is_xml: bool, density: str) -> str:
        video_id        = info[KeyDmc.VIDEO_ID]
        thread_id       = info[KeyDmc.THREAD_ID]
        msg_server      = info[KeyDmc.MSG_SERVER]
        user_id         = info[KeyDmc.USER_ID]
        user_key        = info[KeyDmc.USER_KEY]
        is_official     = info[KeyDmc.IS_OFFICIAL]

        # 以下は公式動画で必要
        opt_thread_id   = info[KeyDmc.OPT_THREAD_ID]    # int なければ None
        needs_key       = info[KeyDmc.NEEDS_KEY]        # int なければ None
        thread_key      = None
        force_184       = None

        self.logger.info(Msg.nd_download_comment.format(
            idx + 1, len(self.glossary), video_id, info[KeyGTI.TITLE]))

        if is_official:
            thread_key, force_184 = await self.get_thread_key(thread_id, needs_key)

        # if self.__wayback:
        #     waybackkey = await self.get_wayback_key(thread_id)

        if is_xml:
            req_param = self.make_param_xml(
                thread_id, user_id, thread_key, force_184, density=density)
            com_data = await self.retriever(data=req_param, url=msg_server)
        else:
            req_param = self.make_param_json(
                is_official, user_id, user_key, thread_id,
                opt_thread_id, thread_key, force_184, density=density)
            com_data = await self.retriever(data=json.dumps(req_param), url=URL.URL_Msg_JSON)

        return self.postprocesser(is_xml, com_data)

    async def retriever(self, data: str, url: str) -> str:
        async with asyncio.Semaphore(self.__parallel_limit):
            async with self.session.post(url=url, data=data) as resp:  # type: aiohttp.ClientResponse
                return await resp.text()

    def postprocesser(self, is_xml: bool, result: str):
        """
        取ってきたコメントデータに後処理する。

        :param bool is_xml: 受け取ったデータがXML形式かどうか。
        :param str result: コメントの文字列
        :rtype: str
        """
        if is_xml:
            return result.replace("><", ">\n<")
        else:
            return result.replace("}, ", "},\n")

    def saver(self, video_id: str, is_xml: bool, coroutine: asyncio.Task) -> bool:
        comment_data = coroutine.result()
        if is_xml:
            extention = "xml"
        else:
            extention = "json"

        file_path = utils.make_name(self.glossary[video_id], self.save_dir, extention=extention)
        with file_path.open("w", encoding="utf-8") as f:
            f.write(comment_data + "\n")
        self.logger.info(Msg.nd_download_done.format(path=file_path))
        return True

    async def get_thread_key(self, thread_id, needs_key):
        """
        専用のAPIにアクセスして thread_key を取得する。

        :param str thread_id:
        :param str needs_key:
        :rtype: tuple[str, str]
        """
        if not int(needs_key) == 1:
            self.logger.debug(f"needs_key is not 1. Video ID (or Thread ID): {thread_id},"
                              f" needs_key: {needs_key}")
            return "", "0"
        async with self.session.get(URL.URL_GetThreadKey, params={"thread": thread_id}) as resp:
            response = await resp.text()
        self.logger.debug("Response from GetThreadKey API"
                          f" (thread id is {thread_id}): {response}")
        parameters = parse_qs(response)
        threadkey = parameters["threadkey"][0]  # type: str
        force_184 = parameters["force_184"][0]  # type: str
        return threadkey, force_184

    async def get_wayback_key(self, thread_id: int):
        async with asyncio.Semaphore(self.__parallel_limit):
            async with self.session.get(URL.URL_WayBackKey, params={"thread", thread_id}) as resp:
                response = await resp.text()
                self.logger.debug(f"Waybackkey response: {response}")
            return parse_qs(response)["waybackkey"][0]

    def make_param_xml(self, thread_id, user_id, thread_key=None, force_184=None,
                       waybackkey=None, quantity=1000, density="0-99999:9999,1000"):
        """
        コメント取得用のxmlを構成する。

        fork="1" があると投稿者コメントを取得する。
        0-99999:9999,1000: 「0分～99999分までの範囲で
        一分間あたり9999件、直近の1000件を取得する」の意味。

        :param str thread_id:
        :param str user_id:
        :param str thread_key:
        :param str force_184:
        :param str waybackkey:
        :param int | str quantity:取りに行くコメント数
        :param str density: 取りに行くコメントの密度。 0-99999:9999,1000 のような形式。
        :rtype: str
        """
        wbk = f'waybackkey="{waybackkey}"' if waybackkey else ""
        if thread_key:
            return (
                f'<packet>'
                f'<thread thread="{thread_id}" user_id="{user_id}" scores="1"'
                f' threadkey="{thread_key}" force_184="{force_184}"'
                f' {wbk} version="20090904" res_from="-{quantity}"/>'
                f'<thread thread="{thread_id}" user_id="{user_id}" scores="1"'
                f' threadkey="{thread_key}" force_184="{force_184}"'
                f' {wbk} version="20090904" res_from="-{quantity}" fork="1"/>'
                f'<thread_leaves thread="{thread_id}" user_id="{user_id}" scores="1">'
                f'{density}</thread_leaves>'
                f'</packet>')
        else:
            return (
                f'<packet>'
                f'<thread thread="{thread_id}" user_id="{user_id}" scores="1"'
                f' {wbk} version="20090904" res_from="-{quantity}"/>'
                f'<thread thread="{thread_id}" user_id="{user_id}" scores="1"'
                f' {wbk} version="20090904" res_from="-{quantity}" fork="1"/>'
                f'<thread_leaves thread="{thread_id}" user_id="{user_id}" scores="1">'
                f'{density}</thread_leaves>'
                f'</packet>')

    def make_param_json(self, official_video, user_id, user_key, thread_id,
                        optional_thread_id=None, thread_key=None, force_184=None,
                        density="0-99999:9999,1000"):
        """
        コメント取得用のjsonを構成する。

        fork="1" があると投稿者コメントを取得する。
        0-99999:9999,1000: 「0分～99999分までの範囲で
        一分間あたり9999件、直近の1000件を取得する」の意味。

        :param bool official_video: 公式動画なら True
        :param str user_id:
        :param str user_key:
        :param str thread_id:
        :param str | None optional_thread_id:
        :param str | None thread_key:
        :param str | None force_184:
        :param str density: 取りに行くコメントの密度。 0-99999:9999,1000 のような形式。
        :rtype: str
        """
        result = [
            {"ping": {"content": "rs:0"}},
            {"ping": {"content": "ps:0"}},
            {
                "thread": {
                    "thread"     : optional_thread_id or thread_id,
                    "version"    : "20090904",
                    "language"   : 0,
                    "user_id"    : user_id,
                    "with_global": 1,
                    "scores"     : 1,
                    "nicoru"     : 0,
                    "userkey"    : user_key
                }
            },
            {"ping": {"content": "pf:0"}},
            {"ping": {"content": "ps:1"}},
            {
                "thread_leaves": {
                    "thread"  : optional_thread_id or thread_id,
                    "language": 0,
                    "user_id" : user_id,
                    # "content" : "0-4:100,250",  # 公式仕様のデフォルト値
                    "content" : density,
                    "scores"  : 1,
                    "nicoru"  : 0,
                    "userkey" : user_key
                }
            },
            {"ping": {"content": "pf:1"}}
        ]

        if official_video:
            result += [{"ping": {"content": "ps:2"}},
                       {
                           "thread": {
                               "thread"     : thread_id,
                               "version"    : "20090904",
                               "language"   : 0,
                               "user_id"    : user_id,
                               "force_184"  : force_184,
                               "with_global": 1,
                               "scores"     : 1,
                               "nicoru"     : 0,
                               "threadkey"  : thread_key
                           }
                       },
                       {"ping": {"content": "pf:2"}},
                       {"ping": {"content": "ps:3"}},
                       {
                           "thread_leaves": {
                               "thread"   : thread_id,
                               "language" : 0,
                               "user_id"  : user_id,
                               # "content"  : "0-4:100,250",  # 公式仕様のデフォルト値
                               "content"  : density,
                               "scores"   : 1,
                               "nicoru"   : 0,
                               "force_184": force_184,
                               "threadkey": thread_key
                           }
                       },
                       {"ping": {"content": "pf:3"}}]
        result += [{"ping": {"content": "rf:0"}}]
        return result


def main(args):
    """
    メイン。

    :param args: ArgumentParser.parse_args() によって解釈された引数
    :rtype: bool
    """
    is_debug = int(os.getenv("PYTHON_TEST", 0))
    mailadrs = args.mail[0] if args.mail else None
    password = args.password[0] if args.password else None

    #
    # エラーの除外
    #
    videoid = utils.validator(args.VIDEO_ID)
    if not videoid:
        sys.exit(Err.invalid_videoid)
    if not (args.thumbnail or args.comment or args.video):
        sys.exit(Err.not_specified.format("--thumbnail or --comment or --video"))

    #
    # 本筋
    #
    log_level = "DEBUG" if is_debug else args.loglevel
    logger = utils.NTLogger(log_level=log_level)
    destination = utils.get_dir(args.dest[0])

    database = Info(mail=mailadrs, password=password, logger=logger).get_data(videoid)

    if len(database) == 0:
        return True

    if args.thumbnail:
        Thumbnail(logger=logger).start(videoid, destination)

    if args.comment:
        Comment(logger=logger).start(database, destination, args.xml)

    if args.video:
        Video(videoids=database, save_dir=destination,
              logger=logger, division=args.limit, multiline=args.nomulti, smile=args.smile).start()

    return True
