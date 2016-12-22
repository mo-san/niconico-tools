# coding: UTF-8
import asyncio
import time
from pathlib import Path
from typing import List
from urllib.parse import parse_qs

import aiohttp
try:
    import progressbar
except ImportError:
    progressbar = None

from nicotools import utils
from nicotools.utils import Msg, Err, URL, KeyGTI, KeyGetFlv
from nicotools.nicodown import get_infos


class Comment(utils.Canopy):
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

    def start(self, database, save_dir, xml=False):
        """

        :param dict[str, dict[str, int | str]] | list[str] database:
        :param str | Path save_dir:
        :param bool xml:
        """
        utils.check_arg(locals())
        self.logger.debug("Directory to save in: {}".format(save_dir))
        self.logger.debug("Dictionary of Videos: {}".format(database))
        self.logger.debug("Download XML? : {}".format(xml))
        if isinstance(database, list):
            database = get_infos(database, self.logger)
        self.glossary = database
        self.save_dir = utils.make_dir(save_dir)
        self.logger.info(Msg.nd_start_dl_comment.format(len(self.glossary)))
        for index, video_id in enumerate(self.glossary.keys()):
            self.logger.info(
                Msg.nd_download_comment.format(
                    index + 1, len(database), video_id,
                    self.glossary[video_id][KeyGTI.TITLE]))
            self.download(video_id, xml)
            if len(self.glossary) > 1:
                time.sleep(1.5)
        return True

    def download(self, video_id, xml=False):
        """
        :param str video_id: 動画ID (e.g. sm1234)
        :param bool xml:
        :rtype: bool
        """
        utils.check_arg(locals())
        db = self.glossary[video_id]
        if video_id.startswith("so"):
            redirected = self.session.get(URL.URL_Watch + video_id).url.split("/")[-1]
            db[KeyGTI.V_OR_T_ID] = redirected
        self.logger.debug("Video ID and its Thread ID (of officials):"
                          " {}".format(video_id, db[KeyGTI.V_OR_T_ID]))

        response = self.get_from_getflv(db[KeyGTI.V_OR_T_ID], self.session)

        if response is None:
            time.sleep(4)
            print(Err.waiting_for_permission)
            time.sleep(4)
            return self.download(video_id, xml)

        thread_id = response[KeyGetFlv.THREAD_ID]
        msg_server = response[KeyGetFlv.MSG_SERVER]
        user_id = response[KeyGetFlv.USER_ID]
        user_key = response[KeyGetFlv.USER_KEY]

        opt_thread_id = response[KeyGetFlv.OPT_THREAD_ID]
        needs_key = response[KeyGetFlv.NEEDS_KEY]

        if xml and video_id.startswith(("sm", "nm")):
            req_param = self.make_param_xml(thread_id, user_id)
            self.logger.debug("Posting Parameters: {}".format(req_param))

            res_com = self.session.post(url=msg_server, data=req_param)
            comment_data = res_com.text.replace("><", ">\n<")
        else:
            if video_id.startswith(("sm", "nm")):
                req_param = self.make_param_json(
                    False, user_id, user_key, thread_id)
            else:
                thread_key, force_184 = self.get_thread_key(db[KeyGTI.V_OR_T_ID],
                                                            needs_key)
                req_param = self.make_param_json(
                    True, user_id, user_key, thread_id,
                    opt_thread_id, thread_key, force_184)

            self.logger.debug("Posting Parameters: {}".format(req_param))
            res_com = self.session.post(
                url=URL.URL_Message_New_JSON,
                json=req_param)
            comment_data = res_com.text.replace("}, ", "},\n")

        comment_data = comment_data.encode(res_com.encoding).decode("utf-8")
        return self._saver(video_id, comment_data, xml)

    def _saver(self, video_id, comment_data, xml):
        """

        :param str video_id:
        :param str comment_data:
        :param bool xml:
        :return:
        """
        utils.check_arg(locals())
        if xml and video_id.startswith(("sm", "nm")):
            extention = "xml"
        else:
            extention = "json"

        file_path = self.make_name(video_id, extention)
        self.logger.debug("File Path: {}".format(file_path))
        with file_path.open("w", encoding="utf-8") as f:
            f.write(comment_data + "\n")
        self.logger.info(Msg.nd_download_done.format(file_path))
        return True

    def get_thread_key(self, video_id, needs_key):
        """
        専用のAPIにアクセスして thread_key を取得する。

        :param str needs_key:
        :param str video_id:
        :rtype: tuple[str, str]
        """
        utils.check_arg(locals())
        if not needs_key == "1":
            self.logger.debug("Video ID (or Thread ID): {},"
                              " needs_key: {}".format(video_id, needs_key))
            return "", "0"
        response = self.session.get(URL.URL_GetThreadKey, params={"thread": video_id})
        self.logger.debug("Response from GetThreadKey API: {}".format(response.text))
        parameters = parse_qs(response.text)
        threadkey = parameters["threadkey"][0]  # type: str
        force_184 = parameters["force_184"][0]  # type: str
        return threadkey, force_184

    def make_param_xml(self, thread_id, user_id):
        """
        コメント取得用のxmlを構成する。

        fork="1" があると投稿者コメントを取得する。
        0-99999:9999,1000: 「0分～99999分までの範囲で
        一分間あたり9999件、直近の1000件を取得する」の意味。

        :param str thread_id:
        :param str user_id:
        :rtype: str
        """
        utils.check_arg(locals())
        self.logger.debug("Arguments: {}".format(locals()))
        return '<packet>' \
               '<thread thread="{0}" user_id="{1}" version="20090904" scores="1"/>' \
               '<thread thread="{0}" user_id="{1}" version="20090904" scores="1"' \
               ' fork="1" res_from="-1000"/>' \
               '<thread_leaves thread="{0}" user_id="{1}" scores="1">' \
               '0-99999:9999,1000</thread_leaves>' \
               '</packet>'.format(thread_id, user_id)

    def make_param_json(self, official_video, user_id, user_key, thread_id,
                        optional_thread_id=None, thread_key=None, force_184=None):
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
                    "content" : "0-99999:9999,1000",
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
                               "content"  : "0-99999:9999,1000",
                               "scores"   : 1,
                               "nicoru"   : 0,
                               "force_184": force_184,
                               "threadkey": thread_key
                           }
                       },
                       {"ping": {"content": "pf:3"}}]
        result += [{"ping": {"content": "rf:0"}}]
        return result
