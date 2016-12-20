# coding: utf-8
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Union, Optional

from string import Template
from typing import List

import aiohttp
import functools
from bs4 import BeautifulSoup, Tag
from tqdm import tqdm

sys.path.insert(0, "../")
from nicotools import utils
from nicotools.get_info_with_async import GetInfoAsync
from nicotools.utils import KeyDmc


class GetDmcVideoAsync(utils.Canopy):
    def __init__(self, loop: asyncio.AbstractEventLoop=None,
                 mail: str=None, password: str=None,
                 logger: utils.NTLogger=None,
                 session: aiohttp.ClientSession=None,
                 return_session=False,
                 division: int=4,
                 limit: int=4,
                 chunk_size=1024*50,
                 multiline=True):
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

    def start(self, glossary: Union[list, dict], save_dir: str, xml=True) -> Optional[aiohttp.ClientSession]:
        self.save_dir = utils.make_dir(save_dir)
        self.__downloaded_size = [0] * self.__division

        if isinstance(glossary, list):
            glossary, self.session = GetInfoAsync(
                mail=self.__mail, password=self.__password,
                session=self.session, return_session=True).get_data(glossary)
        else:
            self.session = self.loop.run_until_complete(self.get_session())
        self.glossary = glossary

        self.loop.run_until_complete(self._broker(xml))
        if self.__return_session:
            return self.session
        else:
            self.session.close()
            return None

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
            # await asyncio.wait(*tasks, loop=self.loop)
            await asyncio.gather(*tasks)

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session:
            return self.session
        else:
            cook = utils.LogIn(mail=self.__mail, password=self.__password).cookie
            return aiohttp.ClientSession(cookies=cook)

    async def first_nego_xml(self, video_id: str) -> str:
        async with self.session.post(
                url=self.glossary[video_id][KeyDmc.API_URL],
                params={"_format": "xml"},
                data=self.make_param_xml(self.glossary[video_id])
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
        print("送信するパラメーター: {}".format(result))
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
        [self.logger.debug("Order: {}, {}".format(o, h)) for o, h in zip(division, headers)]

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


if __name__ == "__main__":
    _video_ids = ["sm30213280", "sm30219950", "sm30250675"]
    _save_dir = "D:/Downloads/videos/"
    GetDmcVideoAsync(mail=os.getenv("addr_p"), password=os.getenv("pass_p"),
                     logger=utils.NTLogger(log_level=10), multiline=False
                     ).start(_video_ids, _save_dir)
