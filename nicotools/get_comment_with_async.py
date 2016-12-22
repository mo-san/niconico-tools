# coding: UTF-8
import asyncio
import json
import re
from pathlib import Path
from typing import List
from urllib.parse import parse_qs

import aiohttp
import functools

from nicotools.nicodown_async import Info

try:
    import progressbar
except ImportError:
    progressbar = None

from nicotools import utils
from nicotools.utils import Msg, URL, KeyDmc


class Comment(utils.CanopyAsync):
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
        self.__downloaded_size = None  # type: List[int]
        self.session = session or self.loop.run_until_complete(self.get_session())
        self.__return_session = return_session
        self.__parallel_limit = limit

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session:
            return self.session
        else:
            cook = utils.LogIn(mail=self.__mail, password=self.__password).cookie
            return aiohttp.ClientSession(cookies=cook)

    def close(self):
        self.session.close()

    def start(self, glossary, save_dir, xml=False):
        """

        :param dict[str, dict[str, int | str]] | list[str] glossary:
        :param str | Path save_dir:
        :param bool xml:
        """
        utils.check_arg(locals())
        self.save_dir = utils.make_dir(save_dir)

        if isinstance(glossary, list):
            glossary, self.session = Info(
                mail=self.__mail, password=self.__password,
                session=self.session, return_session=True).get_data(glossary)
        self.glossary = glossary

        self.logger.info(Msg.nd_start_dl_comment.format(len(self.glossary)))

        futures = []
        for video_id in self.glossary:
            coro = self._download(self.glossary[video_id], xml)
            f = asyncio.ensure_future(coro)
            f.add_done_callback(functools.partial(self.saver, video_id, xml))
            futures.append(f)

        self.loop.run_until_complete(asyncio.wait(futures, loop=self.loop))
        return self

    async def _download(self, info: dict, is_xml: bool) -> str:
        utils.check_arg(locals())

        thread_id       = info[KeyDmc.THREAD_ID]
        msg_server      = info[KeyDmc.MSG_SERVER]
        user_id         = info[KeyDmc.USER_ID]
        user_key        = info[KeyDmc.USER_KEY]

        # 以下は公式動画で必要
        opt_thread_id   = info[KeyDmc.OPT_THREAD_ID]    # int なければ None
        needs_key       = info[KeyDmc.NEEDS_KEY]        # int なければ None
        thread_key      = None
        force_184       = None

        is_official = re.match("^(?:so|\d)", info[KeyDmc.VIDEO_ID]) is not None

        if is_official:
            thread_key, force_184 = await self.get_thread_key(thread_id, needs_key)

        if is_xml:
            req_param = self.make_param_xml(thread_id, user_id, thread_key, force_184)
            com_data = await self.retriever(data=req_param, url=msg_server)
        else:
            req_param = self.make_param_json(
                is_official, user_id, user_key, thread_id,
                opt_thread_id, thread_key, force_184)
            com_data = await self.retriever(data=json.dumps(req_param), url=URL.URL_Msg_JSON)

        return self.postprocesser(is_xml, com_data)

    async def retriever(self, data: str, url: str) -> str:
        self.logger.debug("Posting Parameters: {}".format(data))
        async with asyncio.Semaphore(self.__parallel_limit):
            async with self.session.post(url=url, data=data) as resp:  # type: aiohttp.ClientResponse
                return await resp.text()

    def postprocesser(self, is_xml: bool, result: str):
        if is_xml:
            return result.replace("><", ">\n<")
        else:
            return result.replace("}, ", "},\n")

    def saver(self, video_id: str, is_xml: bool, coroutine: asyncio.Task) -> bool:
        utils.check_arg(locals())
        comment_data = coroutine.result()
        if is_xml:
            extention = "xml"
        else:
            extention = "json"

        file_path = self.make_name(video_id, extention)
        self.logger.debug("File Path: {}".format(file_path))
        with file_path.open("w", encoding="utf-8") as f:
            f.write(comment_data + "\n")
        self.logger.info(Msg.nd_download_done.format(file_path))
        return True

    async def get_thread_key(self, thread_id, needs_key):
        """
        専用のAPIにアクセスして thread_key を取得する。

        :param str thread_id:
        :param str needs_key:
        :rtype: tuple[str, str]
        """
        utils.check_arg(locals())
        if not int(needs_key) == 1:
            self.logger.debug("needs_key is not 1. Video ID (or Thread ID): {},"
                              " needs_key: {}".format(thread_id, needs_key))
            return "", "0"
        async with self.session.get(URL.URL_GetThreadKey, params={"thread": thread_id}) as resp:
            response = await resp.text()
        self.logger.debug("Response from GetThreadKey API"
                          " (thread id is {}): {}".format(thread_id, response))
        parameters = parse_qs(response)
        threadkey = parameters["threadkey"][0]  # type: str
        force_184 = parameters["force_184"][0]  # type: str
        return threadkey, force_184

    def make_param_xml(self, thread_id, user_id, thread_key=None, force_184=None,
                       quantity=1000, density="0-99999:9999,1000"):
        """
        コメント取得用のxmlを構成する。

        fork="1" があると投稿者コメントを取得する。
        0-99999:9999,1000: 「0分～99999分までの範囲で
        一分間あたり9999件、直近の1000件を取得する」の意味。

        :param str thread_id:
        :param str user_id:
        :param str thread_key:
        :param str force_184:
        :param int | str quantity:取りに行くコメント数
        :param str density: 取りに行くコメントの密度。 0-99999:9999,1000 のような形式。
        :rtype: str
        """
        utils.check_arg({"thread_id": thread_id, "user_id": user_id})
        self.logger.debug("Arguments: {}".format(locals()))
        if thread_key:
            return (
                '<packet>'
                '<thread thread="{thread_id}" user_id="{user_id}" scores="1"'
                ' threadkey="{thread_key}" force_184="{force_184}"'
                ' version="20090904" res_from="-{quantity}"/>'
                '<thread thread="{thread_id}" user_id="{user_id}" scores="1"'
                ' threadkey="{thread_key}" force_184="{force_184}"'
                ' version="20090904" res_from="-{quantity}" fork="1"/>'
                '<thread_leaves thread="{thread_id}" user_id="{user_id}" scores="1">'
                '{density}</thread_leaves>'
                '</packet>').format(thread_id=thread_id, user_id=user_id,
                                    thread_key=thread_key, force_184=force_184,
                                    quantity=quantity, density=density)
        else:
            return (
                '<packet>'
                '<thread thread="{thread_id}" user_id="{user_id}" scores="1"'
                ' version="20090904" res_from="-{quantity}"/>'
                '<thread thread="{thread_id}" user_id="{user_id}" scores="1"'
                ' version="20090904" res_from="-{quantity}" fork="1"/>'
                '<thread_leaves thread="{thread_id}" user_id="{user_id}" scores="1">'
                '{density}</thread_leaves>'
                '</packet>').format(thread_id=thread_id, user_id=user_id,
                                    quantity=quantity, density=density)

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
        utils.check_arg({"official_video": official_video, "user_id": user_id,
                         "user_key": user_key, "thread_id": thread_id})
        self.logger.debug("Arguments of creating JSON: {}".format(locals()))
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
