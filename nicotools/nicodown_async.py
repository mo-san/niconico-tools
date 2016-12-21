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
from typing import Tuple, Dict, Union, Optional, List
from urllib.parse import unquote

import aiohttp
from bs4 import BeautifulSoup, Tag
from tqdm import tqdm

sys.path.insert(0, "../")
from nicotools import utils
from nicotools.utils import Msg, Err, URL, KeyGetFlv, KeyGTI, KeyDmc

IS_DEBUG = int(os.getenv("PYTHON_TEST", "0"))


class InfoAsync(utils.Canopy):
    def __init__(self,
                 mail: str=None, password: str=None,
                 logger: utils.NTLogger=None,
                 session: aiohttp.ClientSession=None,
                 return_session=False,
                 limit: int=4,
                 loop: asyncio.AbstractEventLoop=None,
                 ):
        super().__init__(loop=loop, logger=logger)
        self.__mail = mail
        self.__password = password
        self.session = session or self.loop.run_until_complete(self.get_session())
        self.glossary = {}
        self.__parallel_limit = limit
        self.__return_session = return_session

    def get_data(self, video_ids: list) -> Tuple[Dict, Optional[aiohttp.ClientSession]]:
        self.loop.run_until_complete(self._retrieve_info(video_ids))
        if self.__return_session:
            return self.glossary, self.session
        else:
            self.session.close()
            return self.glossary, None

    async def get_session(self) -> aiohttp.ClientSession:
        cook = utils.LogIn(mail=self.__mail, password=self.__password).cookie
        self.logger.debug("Object ID of cookie (InfoAsync): {}".format(id(cook)))
        return aiohttp.ClientSession(cookies=cook)

    async def _retrieve_info(self, video_ids: list) -> None:
        sem = asyncio.Semaphore(self.__parallel_limit)
        tasks = [self._worker(sem, _id) for _id in video_ids]
        await asyncio.gather(*tasks)

    async def _worker(self, semaphore: asyncio.Semaphore, video_id: str) -> None:
        url = URL.URL_Watch + video_id
        self.logger.debug("_worker: {}".format(locals()))
        async with semaphore:
            async with self.session.get(url) as response:  # type: aiohttp.ClientResponse
                self.logger.debug("Video ID: {}, Status Code: {}".format(video_id, response.status))
                # ステータスコードが400番台以上なら例外を出す
                response.raise_for_status()
                if response.status == 200:
                    info_data = await response.text()
                    self.glossary[video_id] = self._junction(info_data)

    def _pick_info_from_watch_api(self, content: str) -> \
            Dict[str, Union[str, int, List[str], bool]]:
        watch_api = json.loads(content)
        flash_vars = watch_api["flashvars"]
        flvinfo = utils.Canopy.extract_getflv(unquote(flash_vars["flvInfo"]))
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
            KeyDmc.FILE_SIZE    : None,
            KeyDmc.THUMBNAIL_URL: flash_vars["thumbImage"],  # type: str
            KeyDmc.ECO          : flash_vars.get("eco") or 0,  # type: int
            KeyDmc.MOVIE_TYPE   : flash_vars["movie_type"],  # type: str
            # KeyDmc.IS_DMC       : int(flash_vars["isDmc"]),  # type: int
            KeyDmc.DELETED      : int(flash_vars["deleted"]),  # type: int
            KeyDmc.IS_DELETED   : watch_api["videoDetail"]["isDeleted"],  # type: bool
            KeyDmc.IS_PUBLIC    : watch_api["videoDetail"]["is_public"],  # type: bool
            KeyDmc.IS_OFFICIAL  : watch_api["videoDetail"]["is_official"],  # type: bool
            KeyDmc.IS_PREMIUM   : watch_api["viewerInfo"]["isPremium"],  # type: bool
            KeyDmc.USER_ID      : int(flvinfo[KeyGetFlv.USER_ID]),  # type: int
            KeyDmc.USER_KEY     : flvinfo[KeyGetFlv.USER_KEY],  # type: str
            KeyDmc.MSG_SERVER   : flvinfo[KeyGetFlv.MSG_SERVER],  # type: str
            KeyDmc.THREAD_ID    : int(flvinfo[KeyGetFlv.THREAD_ID]),  # type: int
            KeyDmc.API_URL      : None,
            KeyDmc.RECIPE_ID    : None,
            KeyDmc.CONTENT_ID   : None,
            KeyDmc.VIDEO_SRC_IDS: None,
            KeyDmc.AUDIO_SRC_IDS: None,
            KeyDmc.HEARTBEAT    : None,
            KeyDmc.TOKEN        : None,
            KeyDmc.SIGNATURE    : None,
            KeyDmc.AUTH_TYPE    : None,
            KeyDmc.C_K_TIMEOUT  : None,
            KeyDmc.SVC_USER_ID  : None,
            KeyDmc.PLAYER_ID    : None,
            KeyDmc.PRIORITY     : None,
            KeyDmc.OPT_THREAD_ID: None,
            KeyDmc.NEEDS_KEY    : None,
        }
        if dmc_info:
            info.update({
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
                KeyDmc.OPT_THREAD_ID: dmc_info["thread"]["optional_thread_id"],  # type: Optional[int]
                KeyDmc.NEEDS_KEY    : dmc_info["thread"]["thread_key_required"],  # type: bool
            })
        return info

    def _pick_info_from_data_api(self, content: str) -> \
            Dict[str, Union[str, int, List[str], bool]]:
        j = json.loads(content)
        _video = j["video"]
        if "dmcInfo" in _video:
            dmc_info = _video["dmcInfo"]
            session_api = dmc_info["session_api"]
        else:
            dmc_info = None
            session_api = None

        info = {
            KeyDmc.VIDEO_ID     : _video["id"],  # type: str
            KeyDmc.VIDEO_URL_SM : _video["source"],  # type: str
            KeyDmc.TITLE        : _video["originalTitle"],  # type: str
            KeyDmc.FILE_NAME    : utils.t2filename(_video["originalTitle"]),
            KeyDmc.FILE_SIZE    : None,
            KeyDmc.THUMBNAIL_URL: _video["thumbnailURL"],  # type: str
            KeyDmc.ECO          : j["context"]["isEconomy"],  # type: int
            KeyDmc.MOVIE_TYPE   : _video["movieType"],  # type: str
            KeyDmc.DELETED      : dmc_info["video"]["deleted"],  # type: int
            KeyDmc.IS_DELETED   : _video["isDeleted"],  # type: bool
            KeyDmc.IS_PUBLIC    : _video["isPublic"],  # type: bool
            KeyDmc.IS_OFFICIAL  : _video["isOfficial"],  # type: bool
            KeyDmc.IS_PREMIUM   : j["viewer"]["isPremium"],  # type: bool
            KeyDmc.USER_ID      : j["viewer"]["id"],  # type: int
            KeyDmc.USER_KEY     : j["context"]["userkey"],  # type: str
            # KeyDmc.IS_DMC       : None,
            # この2つは dmcInfo にしかない。watchAPI版との整合性のために初期化しておく。
            KeyDmc.MSG_SERVER   : None,
            KeyDmc.THREAD_ID    : None,
            KeyDmc.API_URL      : None,
            KeyDmc.RECIPE_ID    : None,
            KeyDmc.CONTENT_ID   : None,
            KeyDmc.VIDEO_SRC_IDS: None,
            KeyDmc.AUDIO_SRC_IDS: None,
            KeyDmc.HEARTBEAT    : None,
            KeyDmc.TOKEN        : None,
            KeyDmc.SIGNATURE    : None,
            KeyDmc.AUTH_TYPE    : None,
            KeyDmc.C_K_TIMEOUT  : None,
            KeyDmc.SVC_USER_ID  : None,
            KeyDmc.PLAYER_ID    : None,
            KeyDmc.PRIORITY     : None,
            KeyDmc.OPT_THREAD_ID: None,
            KeyDmc.NEEDS_KEY    : None,
        }

        if dmc_info:
            info.update({
                KeyDmc.MSG_SERVER   : dmc_info["thread"]["server_url"],  # type: str
                KeyDmc.THREAD_ID    : dmc_info["thread"]["thread_id"],  # type: int
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
                KeyDmc.OPT_THREAD_ID: dmc_info["thread"]["optional_thread_id"],  # type: Optional[int]
                KeyDmc.NEEDS_KEY    : dmc_info["thread"]["thread_key_required"],  # type: bool
            })
        return info

    def _junction(self, content: str) -> Dict[str, Union[str, int, List[str], bool]]:
        soup = BeautifulSoup(content, "html.parser")
        _not_login = soup.select("#Login_nico")
        if _not_login:
            exit("ログインしてないよ")
        _data_api = soup.select("#js-initial-watch-data")
        _watch_api = soup.select("#watchAPIDataContainer")
        if _data_api:
            return self._pick_info_from_data_api(_data_api[0]["data-api-data"])
        elif _watch_api:
            return self._pick_info_from_watch_api(_watch_api[0].text)
        else:
            self.logger.debug(content)
            raise AttributeError("Unknown HTML")


class ThumbnailAsync(utils.Canopy):
    def __init__(self,
                 logger: utils.NTLogger=None,
                 limit: int=8,
                 session: aiohttp.ClientSession=None,
                 return_session: bool=False,
                 loop: asyncio.AbstractEventLoop=None,
                 ):
        super().__init__(loop=loop, logger=logger)
        self.undone = []
        self.__bucket = {}
        self.session = session or self.loop.run_until_complete(self.get_session())
        self.__return_session = return_session
        self.__parallel_limit = limit

    async def get_session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession()

    def start(self, glossary: Union[List, Dict],
              save_dir: Union[str, Path], is_large=True) -> bool:
        """

        :param dict[str, dict[str, int | str]] | list[str] glossary:
        :param str | Path save_dir:
        :param bool is_large: 大きいサムネイルを取りに行くかどうか
        :rtype: bool | aiohttp.ClientSession
        """
        utils.check_arg(locals())
        self.logger.debug("Directory to save in: {}".format(save_dir))
        self.logger.debug("Dictionary of Videos: {}".format(glossary))
        if isinstance(glossary, list):
            glossary = utils.validator(glossary)
            glossary = self.loop.run_until_complete(self.get_infos(glossary))
        del self.__bucket
        self.glossary = glossary
        self.save_dir = utils.make_dir(save_dir)
        self.logger.info(Msg.nd_start_dl_pict.format(len(self.glossary)))
        self.loop.run_until_complete(self.download(list(self.glossary)))
        while len(self.undone) > 0:
            self.logger.debug("いくつか残ってる。{}".format(self.undone))
            self.loop.run_until_complete(self.download(self.undone, False))
        self.logger.debug("全部終わった")
        if not self.__return_session:
            self.session.close()
        return True

    async def download(self, video_ids: list, islarge: bool=True) -> None:
        urls = self.make_urls(video_ids, islarge)
        sem = asyncio.Semaphore(self.__parallel_limit)

        futures = []
        for video_id, _url in zip(video_ids, urls):
            coro = self.worker(sem, video_id, _url)
            f = asyncio.ensure_future(coro)
            f.add_done_callback(functools.partial(self.saver, video_id))
            futures.append(f)
        await asyncio.wait(futures, loop=self.loop)

    async def worker(self, semaphore: asyncio.Semaphore, video_id: str, url: str) -> Optional[bytes]:
        async with semaphore:
            self.logger.debug(
                Msg.nd_download_pict_async.format(
                    video_id, self.glossary[video_id][KeyGTI.TITLE]))
            try:
                async with self.session.get(url, timeout=10) as response:
                    self.logger.debug("Video ID: {}, Status Code: {}".format(video_id, response.status))
                    if response.status == 200:
                        # ダウンロードに成功したら「未完了のリスト」から取り除く
                        if video_id in self.undone:
                            self.undone.remove(video_id)
                        return await response.content.read()
                    else:
                        self.undone.append(video_id)
                        return None
            except asyncio.TimeoutError:
                self.logger.warning("{} が時間切れ".format(video_id))
                self.undone.append(video_id)
                return None

    def saver(self, video_id: str, coroutine: asyncio.Task) -> None:
        image_data = coroutine.result()
        if image_data:
            file_path = self.make_name(video_id, "jpg")
            self.logger.debug("File Path: {}".format(file_path))

            with file_path.open('wb') as f:
                f.write(image_data)
            self.logger.info(Msg.nd_download_done.format(file_path))

    def make_urls(self, video_ids: List[str], is_large: bool=True) -> List[str]:
        if is_large:
            urls = ["{0}.L".format(self.glossary[_id][KeyGTI.THUMBNAIL_URL]) for _id in video_ids]
        else:
            urls = [self.glossary[_id][KeyGTI.THUMBNAIL_URL] for _id in video_ids]
        return urls

    async def get_infos(self, queue: List[str]) -> Dict[str, Dict]:
        """
        getthumbinfo APIから、細かな情報をもらってくる

        * file_name         str
        * thumbnail_url     str
        * title             str
        * video_id          str

        :param list[str] queue: 動画IDのリスト
        :rtype: dict[str, dict]
        """
        sem = asyncio.Semaphore(self.__parallel_limit)
        futures = []
        for video_id in queue:
            f = asyncio.ensure_future(self.get_infos_worker(sem, video_id))
            f.add_done_callback(functools.partial(self.get_infos_second, video_id))
            futures.append(f)
        await asyncio.wait(futures, loop=self.loop)
        return self.__bucket

    async def get_infos_worker(self, semaphore: asyncio.Semaphore, video_id: str) -> str:
        async with semaphore:
            async with self.session.get(URL.URL_Info + video_id) as resp:
                return await resp.text()

    def get_infos_second(self, video_id: str, coroutine: asyncio.Task) -> None:
        soup = BeautifulSoup(coroutine.result(), "html.parser")
        if soup.nicovideo_thumb_response["status"].lower() == "ok":
            self.__bucket[video_id] = {
                KeyGTI.FILE_NAME    : utils.t2filename(soup.select(KeyGTI.TITLE)[0].text),
                KeyGTI.THUMBNAIL_URL: soup.select(KeyGTI.THUMBNAIL_URL)[0].text,
                KeyGTI.TITLE        : html.unescape(soup.select(KeyGTI.TITLE)[0].text),
                KeyGTI.VIDEO_ID     : video_id
            }


class VideoAsyncSmile(utils.Canopy):
    def __init__(self,
                 mail: str=None, password: str=None,
                 logger: utils.NTLogger=None,
                 session: aiohttp.ClientSession=None,
                 return_session=False,
                 division: int=4,
                 limit: int=4,
                 chunk_size=1024*50,
                 multiline=True,
                 loop: asyncio.AbstractEventLoop=None,
                 ):
        super().__init__(loop=loop, logger=logger)
        self.__mail = mail
        self.__password = password
        self.__downloaded_size = None  # type: List[int]
        self.__multiline = multiline
        self.__division = division
        self.session = session
        self.__return_session = return_session
        self.__parallel_limit = limit
        self.__chunk_size = chunk_size

    def start(self,
              glossary: Union[list, dict],
              save_dir: Union[str, Path]) -> bool:
        self.save_dir = utils.make_dir(save_dir)
        self.__downloaded_size = [0] * self.__division

        if isinstance(glossary, list):
            glossary, self.session = InfoAsync(
                mail=self.__mail, password=self.__password,
                session=self.session, return_session=True).get_data(glossary)
        else:
            self.session = self.loop.run_until_complete(self.get_session())
        self.glossary = glossary

        sem = asyncio.Semaphore(self.__parallel_limit)
        self.loop.run_until_complete(self._push_file_size(sem))
        self.loop.run_until_complete(self._broker())
        if not self.__return_session:
            self.session.close()
        return True

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session:
            return self.session
        else:
            cook = utils.LogIn(mail=self.__mail, password=self.__password).cookie
            return aiohttp.ClientSession(cookies=cook)

    async def _push_file_size(self, semaphore: asyncio.Semaphore):
        video_ids = sorted(self.glossary)
        tasks = [self._get_file_size_worker(video_id) for video_id in video_ids]
        async with semaphore:
            result = await asyncio.gather(*tasks)
        for _id, size in zip(video_ids, result):
            self.glossary[_id][KeyDmc.FILE_SIZE] = size

    async def _get_file_size_worker(self, video_id: str) -> int:
        vid_url = self.glossary[video_id][KeyDmc.VIDEO_URL_SM]
        self.logger.debug("Video ID: {}, Video URL: {}".format(video_id, vid_url))
        async with self.session.head(vid_url) as resp:
            headers = resp.headers
            self.logger.debug(str(headers))
            return int(headers["content-length"])

    async def _broker(self):
        futures = []
        for video_id in self.glossary:
            coro = self._download(video_id)
            f = asyncio.ensure_future(coro)
            f.add_done_callback(functools.partial(self._combiner, video_id))
            futures.append(f)
        await asyncio.wait(futures, loop=self.loop)

    async def _download(self, video_id: str):
        division = self.__division
        file_path = self.make_name(video_id, self.glossary[video_id][KeyDmc.MOVIE_TYPE])

        video_url = self.glossary[video_id][KeyDmc.VIDEO_URL_SM]
        file_size = self.glossary[video_id][KeyDmc.FILE_SIZE]
        headers = [
            {"Range": "bytes={}-{}".format(
                int(file_size*order/division),
                int((file_size*(order+1))/division-1)
            )} for order in range(division)]
        [self.logger.debug(str(h)) for h in headers]

        if self.__multiline:
            progress_bars = [tqdm(total=int(file_size / division),
                                  leave=False, position=order,
                                  unit="B", unit_scale=True)
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
        file_path = Path("{}.{:03}".format(file_path, order))
        # => video.mp4.000 ～ video.mp4.003 (4分割の場合)
        with file_path.open("wb") as fd:
            async with self.session.get(url=video_url, headers=header) as video_data:
                self.logger.debug("Started! Header: {}, Video URL: {}".format(header, video_url))
                while True:
                    data = await video_data.content.read(self.__chunk_size)
                    if not data:
                        break
                    downloaded_size = fd.write(data)
                    self.__downloaded_size[order] += downloaded_size
                    if pbar:
                        pbar.update(downloaded_size)
        self.logger.debug("Order: {} Done!".format(order))
        return pbar

    async def _counter_whole(self, file_size: int, interval: int=1):
        with tqdm(total=file_size, unit="B") as bar:
            oldsize = 0
            while True:
                newsize = sum(self.__downloaded_size)
                if newsize >= file_size:
                    bar.update(file_size - oldsize)
                    break
                bar.update(newsize - oldsize)
                oldsize = newsize
                await asyncio.sleep(interval)

    def _combiner(self, video_id: str, coroutine: asyncio.Task):
        if coroutine.done() and not coroutine.cancelled():
            file_path = self.make_name(video_id, self.glossary[video_id][KeyDmc.MOVIE_TYPE])
            file_names = ["{}.{:03}".format(file_path, order) for order in range(self.__division)]
            self.logger.debug("File names: {}".format(file_names))
            with file_path.open("wb") as fd:
                for name in file_names:
                    with open(name, "rb") as file:
                        fd.write(file.read())
                    os.remove(name)


class VideoAsyncDmc(utils.Canopy):
    def __init__(self,
                 mail: str=None, password: str=None,
                 logger: utils.NTLogger=None,
                 session: aiohttp.ClientSession=None,
                 return_session=False,
                 division: int=4,
                 limit: int=4,
                 chunk_size=1024*50,
                 multiline=True,
                 loop: asyncio.AbstractEventLoop=None,
                 ):
        super().__init__(loop=loop, logger=logger)
        self.__mail = mail
        self.__password = password
        self.__downloaded_size = None  # type: List[int]
        self.__multiline = multiline
        self.__division = division
        self.session = session
        self.__return_session = return_session
        self.__parallel_limit = limit
        self.__chunk_size = chunk_size

    def start(self,
              glossary: Union[list, dict],
              save_dir: Union[str, Path],
              xml: bool=True) -> bool:
        self.save_dir = utils.make_dir(save_dir)
        self.__downloaded_size = [0] * self.__division

        if isinstance(glossary, list):
            glossary, self.session = InfoAsync(
                mail=self.__mail, password=self.__password,
                session=self.session, return_session=True).get_data(glossary)
        else:
            self.session = self.loop.run_until_complete(self.get_session())
        self.glossary = glossary

        self.loop.run_until_complete(self._broker(xml))
        if not self.__return_session:
            self.session.close()
        return True

    async def _broker(self, xml: bool=True) -> None:
        for video_id in self.glossary:
            if self.glossary[video_id][KeyDmc.API_URL] is None:
                self.logger.warning("{} はDMC動画ではありません。".format(video_id))
                continue
            if xml:
                res_xml = await self.first_nego_xml(video_id)
                video_url = self.extract_video_url_xml(res_xml)
                coro_heartbeat = asyncio.ensure_future(self.heartbeat(video_id, res_xml))
            else:
                res_json = await self.first_nego_json(video_id)
                video_url = self.extract_video_url_json(res_json)
                coro_heartbeat = asyncio.ensure_future(self.heartbeat(video_id, res_json))

            self.logger.debug("動画URL:".format(video_url))
            coro_download = asyncio.ensure_future(self._download(video_id, video_url))
            coro_download.add_done_callback(functools.partial(self._canceler, coro_heartbeat))
            coro_download.add_done_callback(functools.partial(self._combiner, video_id))
            tasks = [coro_download, coro_heartbeat]
            await asyncio.gather(*tasks)

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session:
            return self.session
        else:
            cook = utils.LogIn(mail=self.__mail, password=self.__password).cookie
            return aiohttp.ClientSession(cookies=cook)

    async def first_nego_xml(self, video_id: str) -> str:
        payload = self.make_param_xml(self.glossary[video_id])
        async with self.session.post(
                url=self.glossary[video_id][KeyDmc.API_URL],
                params={"_format": "xml"},
                data=payload,
        ) as response:  # type: aiohttp.ClientResponse
            return await response.text()

    async def first_nego_json(self, video_id: str) -> str:
        payload = self.make_param_json(self.glossary[video_id])
        async with self.session.post(
                url=self.glossary[video_id][KeyDmc.API_URL],
                params={"_format": "json"},
                data=payload,
        ) as response:  # type: aiohttp.ClientResponse
            return await response.text()

    def make_param_xml(self, info: Dict[str, str]) -> str:
        info.update({
            "video_src_ids_xml": "".join(map(
                lambda _: "<string>{}</string>".format(_), info[KeyDmc.VIDEO_SRC_IDS])),
            "audio_src_ids_xml": "".join(map(
                lambda _: "<string>{}</string>".format(_), info[KeyDmc.AUDIO_SRC_IDS]))
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

    def make_param_json(self, info: Dict[str, Union[str, list, int]]) -> str:
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
        self.logger.debug("送信するパラメーター: {}".format(result))
        return result

    def extract_video_url_xml(self, text: str) -> str:
        soup = BeautifulSoup(text, "html.parser")
        url_tag = soup.content_uri  # type: Tag
        return url_tag.text

    def extract_video_url_json(self, text: str) -> str:
        print(text)
        soup = json.loads(text)
        url_tag = soup["data"]["session"]["content_uri"]
        return url_tag

    def extract_session_id_xml(self, text: str) -> str:
        soup = BeautifulSoup(text, "html.parser")
        id_tag = soup.session.id  # type: Tag
        self.logger.debug("Session ID: {}".format(id_tag.text))
        return id_tag.text

    def extract_session_id_json(self, text: str) -> str:
        soup = json.loads(text)
        id_tag = soup["data"]["session"]["id"]
        self.logger.debug("Session ID: {}".format(id_tag))
        return id_tag.text

    def extract_session_tag(self, text: str) -> str:
        return re.sub(".+(<session>.+</session>).+", r"\1", text)
        # return xml_text[xml_text.find("<session>"): xml_text.find("</session>")+10]

    async def heartbeat(self, video_id: str, text: str) -> None:
        try:
            self.logger.debug("返ってきたXML: {}".format(text))
            api_url = self.glossary[video_id][KeyDmc.API_URL]
            # 1分ちょうどで送ると遅れるので、待ち時間を少し早める
            waiting = (self.glossary[video_id][KeyDmc.HEARTBEAT] / 1000) - 5
            companion = self.extract_session_tag(text)
            self.logger.debug("送信するXML: {}".format(companion))
            session_id = self.extract_session_id_xml(text)
            await asyncio.sleep(waiting)
            async with self.session.post(
                    url=api_url + "/" + session_id,
                    params={"_format": "xml", "_method": "PUT"},
                    data=companion
            ) as response:  # type: aiohttp.ClientResponse
                res_text = await response.text()
            await self.heartbeat(video_id, res_text)
        except asyncio.CancelledError:
            pass

    async def _get_file_size(self, video_id: str, video_url: str) -> int:
        self.logger.debug("Video ID: {}, Video URL: {}".format(video_id, video_url))
        async with self.session.head(video_url) as resp:
            headers = resp.headers
            self.logger.debug(str(headers))
            return int(headers["content-length"])

    async def _download(self, video_id: str, video_url: str):
        division = self.__division
        file_path = self.make_name(video_id, self.glossary[video_id][KeyDmc.MOVIE_TYPE])

        file_size = await self._get_file_size(video_id, video_url)
        headers = [
            {"Range": "bytes={}-{}".format(
                int(file_size*order/division),
                int((file_size*(order+1))/division-1)
            )} for order in range(division)]
        [self.logger.debug("Order: {}, {}".format(o, h)) for o, h in zip(range(division), headers)]

        if self.__multiline:
            progress_bars = [tqdm(total=int(file_size / division),
                                  leave=False, position=order,
                                  unit="B", unit_scale=True)
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
        file_path = Path("{}.{:03}".format(file_path, order))
        # => video.mp4.000 ～ video.mp4.003 (4分割の場合)
        self.logger.debug(file_path)
        with file_path.open("wb") as fd:
            async with self.session.get(url=video_url, headers=header) as video_data:
                self.logger.debug("Started! Header: {}, Video URL: {}".format(header, video_url))
                while True:
                    data = await video_data.content.read(self.__chunk_size)
                    if not data:
                        break
                    downloaded_size = fd.write(data)
                    self.__downloaded_size[order] += downloaded_size
                    if pbar:
                        pbar.update(downloaded_size)
        self.logger.debug("Order: {} Done!".format(order))
        return pbar

    def _canceler(self, task_to_cancel: asyncio.Task, _: asyncio.Task) -> bool:
        return task_to_cancel.cancel()

    async def _counter_whole(self, file_size: int, interval: int=1):
        with tqdm(total=file_size, unit="B") as bar:
            oldsize = 0
            while True:
                newsize = sum(self.__downloaded_size)
                if newsize >= file_size:
                    bar.update(file_size - oldsize)
                    break
                bar.update(newsize - oldsize)
                oldsize = newsize
                await asyncio.sleep(interval)

    def _combiner(self, video_id: str, coroutine: asyncio.Task):
        if coroutine.done() and not coroutine.cancelled():
            file_path = self.make_name(video_id, self.glossary[video_id][KeyDmc.MOVIE_TYPE])
            file_names = ["{}.{:03}".format(file_path, order) for order in range(self.__division)]
            self.logger.debug("File names: {}".format(file_names))
            with file_path.open("wb") as fd:
                for name in file_names:
                    with open(name, "rb") as file:
                        fd.write(file.read())
                    os.remove(name)


def main(args):
    """
    メイン。

    :param args: ArgumentParser.parse_args() によって解釈された引数
    :rtype: bool
    """
    mailadrs = args.mail[0] if args.mail else None
    password = args.password[0] if args.password else None
    res_t = False
    res_c = False
    res_v = False

    """ エラーの除外 """
    videoid = utils.validator(args.VIDEO_ID)
    if not videoid:
        sys.exit(Err.invalid_videoid)
    if not (args.getthumbinfo or args.thumbnail or args.comment or args.video):
        sys.exit(Err.not_specified.format("--thumbnail、 --comment、 --video のいずれか"))

    if args.getthumbinfo:
        file_name = args.out[0] if isinstance(args.out, list) else None
        return utils.print_info(videoid, file_name)

    """ 本筋 """
    log_level = "DEBUG" if IS_DEBUG else args.loglevel
    logger = utils.NTLogger(log_level=log_level, file_name=utils.LOG_FILE_ND)
    destination = utils.make_dir(args.dest[0])

    if args.thumbnail:
        res_t = ThumbnailAsync(logger=logger).start(videoid, destination)
        if not (args.comment or args.video):
            # サムネイルのダウンロードだけなら
            # ログインする必要がないのでここで終える。
            return res_t

    database, session = InfoAsync(
        mail=mailadrs, password=password,
        logger=logger, return_session=True).get_data(videoid)

    # if args.comment:
    #     res_c = (nicodown.Comment(logger=logger, session=session)
    #              .start(database, destination, args.xml))

    if args.video:
        if args.smile:
            res_v = (VideoAsyncSmile(logger=logger, session=session,
                                     division=args.limit, multiline=args.nomulti)
                     .start(database, destination))
        else:
            res_v = (VideoAsyncDmc(logger=logger, session=session,
                                   division=args.limit, multiline=args.nomulti)
                     .start(database, destination))

    return res_c | res_v | res_t
