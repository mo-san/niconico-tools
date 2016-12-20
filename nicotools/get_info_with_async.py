# coding: utf-8
import asyncio
import json
from typing import Dict, Union, Tuple, List, Optional
from urllib.parse import unquote

import aiohttp
from bs4 import BeautifulSoup

from nicotools import nicodown
from nicotools import utils
from nicotools.utils import URL, Canopy, KeyDmc, KeyGetFlv


class GetInfoAsync(utils.Canopy):
    def __init__(self, mail: str=None, password: str=None, limit: int=4,
                 session: aiohttp.ClientSession=None, return_session=False):
        super().__init__()
        self.__mail = mail
        self.__password = password
        self.session = session
        self.glossary = {}
        self.__parallel_limit = limit
        self.__return_session = return_session

    def get_data(self, video_ids: list) -> Tuple[Dict, Optional[aiohttp.ClientSession]]:
        self.session = self.loop.run_until_complete(self.get_session())

        self.loop.run_until_complete(self.retrieve_info(video_ids))
        if self.__return_session:
            return self.glossary, self.session
        else:
            self.session.close()
            return self.glossary, None

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session:
            return self.session
        else:
            cook = utils.LogIn(mail=self.__mail, password=self.__password).cookie
            self.logger.debug("cookie (GetInfo): {}".format(id(cook)))
            return aiohttp.ClientSession(cookies=cook)

    async def retrieve_info(self, video_ids: list) -> None:
        sem = asyncio.Semaphore(self.__parallel_limit)
        tasks = [self._worker(sem, _id) for _id in video_ids]
        await asyncio.gather(*tasks)

    async def _worker(self, semaphore: asyncio.Semaphore, video_id: str) -> None:
        url = URL.URL_Watch + video_id
        self.logger.debug("_worker: {}".format(locals()))
        async with semaphore:
            async with self.session.get(url) as response:  # type: aiohttp.ClientResponse
                self.logger.debug("_worker", video_id, response.status)
                # ステータスコードが400番台以上なら例外を出す
                response.raise_for_status()
                if response.status == 200:
                    info_data = await response.text()
                    self.glossary[video_id] = self.junction(info_data)

    def pick_info_from_watch_api(self, content: str) -> \
            Dict[str, Union[str, int, List[str], bool]]:
        watch_api = json.loads(content)
        flash_vars = watch_api["flashvars"]
        flvinfo = Canopy.extract_getflv(unquote(flash_vars["flvInfo"]))
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
            KeyDmc.FILE_NAME    : nicodown.t2filename(flash_vars["videoTitle"]),
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

    def pick_info_from_data_api(self, content: str) -> \
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
            KeyDmc.FILE_NAME    : nicodown.t2filename(_video["originalTitle"]),
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

    def junction(self, content: str) -> Dict[str, Union[str, int, List[str], bool]]:
        soup = BeautifulSoup(content, "html.parser")
        _not_login = soup.select("#Login_nico")
        if _not_login:
            exit("ログインしてないよ")
        _data_api = soup.select("#js-initial-watch-data")
        _watch_api = soup.select("#watchAPIDataContainer")
        if _data_api:
            return self.pick_info_from_data_api(_data_api[0]["data-api-data"])
        elif _watch_api:
            return self.pick_info_from_watch_api(_watch_api[0].text)
        else:
            self.logger.debug(content)
            raise AttributeError("Unknown HTML")
