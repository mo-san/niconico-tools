# coding: UTF-8
import html
import os
import socket
import sys
import time
from urllib.parse import parse_qs
from xml.etree import ElementTree

import requests
from requests.exceptions import Timeout
from requests.packages import urllib3
from tqdm import tqdm

from nicotools import utils
from nicotools.utils import Msg, Err, URL, KeyGTI, KeyGetFlv

"""
使い方:

    nicodown --thumbnail --dest ".\Downloads" sm1 sm2 sm3 sm4 sm5
    nicodown --comment --video --thumbnail --dest ".\Downloads" sm1 sm2 sm3 sm4 sm5
    nicodown -cvt -d ".\Downloads" +ids.txt
    nicodown -cvt --xml -dest ".\Downloads" sm1

他のコマンド:
    引数がどの様に解釈されるかを確認したいとき (確認するだけで、プログラムは実行しません):
        nicodown.py --getthumbinfo sm12345678 --out ../file.txt --what

    ログ出力の詳細さを変える:
        nicodown --loglevel WARNING  # エラー以外表示しない
"""


def get_infos(queue, logger=None):
    """
    getthumbinfo APIから、細かな情報をもらってくる

    * comment_num       int
    * description       str
    * embeddable        int     # 0 or 1
    * file_name         str
    * first_retrieve    str     # 例えば: 2014-07-26 (もともとは: 2014-07-26T19:27:07+09:00)
    * last_res_body     str
    * length            str
    * length_seconds    int
    * mylist_counter    int
    * movie_type        str     # いずれか: mp4, flv, swf
    * no_live_play      int     # 0 or 1
    * size_high         int
    * size_low          int
    * tags              str
    * tags_list         list
    * thumbnail_url     str
    * title             str
    * user_id           int
    * user_name         str
    * user_icon_url     str
    * video_id          str
    * view_counter      int
    * v_or_t_id         str
    * watch_url         str

    :param list[str] | str queue: 動画IDのリスト
    :param NTLogger | None logger: ログ出力
    :rtype: dict[str, dict[str, int | str | list]]
    """
    if isinstance(queue, str):
        queue = [queue]
    message = Msg.nd_start_download.format(len(queue), queue)
    if logger:
        logger.info(message)
    else:
        print(message)

    # データベースとして使うための辞書。削除や非公開の動画はここに入る
    lexikon = {}
    for video_id in utils.validator(queue):
        xmldata = requests.get(URL.URL_Info + video_id).text
        root = ElementTree.fromstring(xmldata)
        # 「status="ok"」 なら動画は生存 / 存在しない動画には「status="fail"」が返る
        if not root.get("status").lower() == "ok":
            if logger:
                logger.warning(Msg.nd_deleted_or_private, video_id)
            else:
                print(Msg.nd_deleted_or_private, video_id)
            continue
        else:
            # 各種情報を辞書に追加していく
            pocket = {}
            # document == "thumb" タグ
            document = root[0]  # type: ElementTree.Element
            finder = document.find

            # 日本語以外のタグが設定されている場合にそれらも巻き込む
            tag_list = [tagstr.text for tagstr in document.iter("tag")]
            # 「分:秒」形式を秒数に直すため分離する
            minute, second = finder(KeyGTI.LENGTH).text.split(":")

            pocket[KeyGTI.COMMENT_NUM]     = int(finder(KeyGTI.COMMENT_NUM).text)
            pocket[KeyGTI.DESCRIPTION]     = html.unescape(finder(KeyGTI.DESCRIPTION).text)
            pocket[KeyGTI.EMBEDDABLE]      = int(finder(KeyGTI.EMBEDDABLE).text)
            pocket[KeyGTI.FILE_NAME]       = utils.t2filename(finder(KeyGTI.TITLE).text)
            pocket[KeyGTI.FIRST_RETRIEVE]  = finder(KeyGTI.FIRST_RETRIEVE).text[:10]
            pocket[KeyGTI.LAST_RES_BODY]   = finder(KeyGTI.LAST_RES_BODY).text
            pocket[KeyGTI.LENGTH]          = "{}:{}".format(minute, second)
            pocket[KeyGTI.LENGTH_SECONDS]  = int(minute) * 60 + int(second)
            pocket[KeyGTI.MYLIST_COUNTER]  = int(finder(KeyGTI.MYLIST_COUNTER).text)
            pocket[KeyGTI.MOVIE_TYPE]      = finder(KeyGTI.MOVIE_TYPE).text.lower()
            pocket[KeyGTI.NO_LIVE_PLAY]    = int(finder(KeyGTI.NO_LIVE_PLAY).text)
            pocket[KeyGTI.SIZE_HIGH]       = int(finder(KeyGTI.SIZE_HIGH).text)
            pocket[KeyGTI.SIZE_LOW]        = int(finder(KeyGTI.SIZE_LOW).text)
            pocket[KeyGTI.TAGS]            = html.unescape(", ".join(tag_list))  # type: str
            pocket[KeyGTI.TAGS_LIST]       = tag_list  # type: list
            pocket[KeyGTI.THUMBNAIL_URL]   = finder(KeyGTI.THUMBNAIL_URL).text
            pocket[KeyGTI.TITLE]           = html.unescape(finder(KeyGTI.TITLE).text)
            pocket[KeyGTI.VIDEO_ID]        = video_id
            pocket[KeyGTI.VIEW_COUNTER]    = int(finder(KeyGTI.VIEW_COUNTER).text)
            pocket[KeyGTI.WATCH_URL]       = finder(KeyGTI.WATCH_URL).text
            pocket[KeyGTI.V_OR_T_ID]       = finder(KeyGTI.WATCH_URL).text.split("/")[-1]
            if video_id.startswith(("sm", "nm")):
                pocket[KeyGTI.USER_ID]         = int(finder(KeyGTI.USER_ID).text)
                pocket[KeyGTI.USER_NAME]       = html.unescape(finder(KeyGTI.USER_NAME).text)
                pocket[KeyGTI.USER_ICON_URL]   = finder(KeyGTI.USER_ICON_URL).text
            else:  # so1234 または 123456 の形式
                pocket[KeyGTI.CH_ID]           = int(finder(KeyGTI.CH_ID).text)
                pocket[KeyGTI.CH_NAME]         = html.unescape(finder(KeyGTI.CH_NAME).text)
                pocket[KeyGTI.CH_ICON_URL]     = finder(KeyGTI.CH_ICON_URL).text
            lexikon[video_id]                  = pocket
    return lexikon


class Video(utils.Canopy):
    def __init__(self, mail=None, password=None, logger=None, session=None):
        """
        動画をダウンロードする。

        :param str | None mail:
        :param str | None password:
        :param NTLogger logger:
        :param requests.Session session:
        """
        super().__init__(logger=logger)
        self.session = session or utils.LogIn(mail=mail, password=password).session

    def start(self, glossary, save_dir, chunk_size=1024*50):
        """

        :param dict[str, dict[str, int | str]] | list[str] glossary:
        :param str | Path save_dir:
        :param int chunk_size: 一度にサーバーに要求するファイルサイズ
        :rtype: bool
        """
        utils.check_arg(locals())
        self.logger.debug("Directory to save in: %s", save_dir)
        self.logger.debug("Dictionary of Videos: %s", glossary)
        self.save_dir = utils.make_dir(save_dir)
        if isinstance(glossary, list):
            glossary = get_infos(glossary, self.logger)
        self.glossary = glossary
        self.logger.info(Msg.nd_start_dl_video,
            len(self.glossary), list(self.glossary))

        for index, video_id in enumerate(self.glossary.keys()):
            self.logger.info(Msg.nd_download_video,
                index + 1, len(glossary), video_id,
                self.glossary[video_id][KeyGTI.TITLE])
            self._download(video_id, chunk_size)
            if len(glossary) > 1:
                time.sleep(1)
        return True

    def _download(self, video_id, chunk_size=1024 * 50):
        """
        :param str video_id: 動画ID (e.g. sm1234)
        :param int chunk_size: 一度にサーバーに要求するファイルサイズ
        :rtype: bool
        """
        utils.check_arg(locals())
        db = self.glossary[video_id]
        if video_id.startswith("so"):
            redirected = self.session.get(URL.URL_Watch + video_id).url.split("/")[-1]
            db[KeyGTI.V_OR_T_ID] = redirected
        self.logger.debug("Video ID: %s and its Thread ID (of officials):"
                          " %s", video_id, db[KeyGTI.V_OR_T_ID])

        response = utils.get_from_getflv(
            db[KeyGTI.V_OR_T_ID], self.session, self.logger)

        vid_url = response[KeyGetFlv.VIDEO_URL]
        is_premium = response[KeyGetFlv.IS_PREMIUM]

        # 動画視聴ページに行ってCookieをもらってくる
        self.session.head(URL.URL_Watch + video_id)
        # connect timeoutを10秒, read timeoutを30秒に設定
        # ↓この時点ではダウンロードは始まらず、ヘッダーだけが来ている
        video_data = self.session.get(url=vid_url, stream=True, timeout=(10.0, 30.0))
        db[KeyGTI.FILE_SIZE] = int(video_data.headers["content-length"])
        self.logger.debug("File Size: %s (Premium: %s)",
                          db[KeyGTI.FILE_SIZE], [False, True][int(is_premium)])

        return self._saver(video_id, video_data, chunk_size)

    def _saver(self, video_id, video_data, chunk_size):
        """

        :param str video_id:
        :param requests.Response video_data: 動画ファイルのURL
        :param int chunk_size: 一度にサーバーに要求するファイルサイズ
        :rtype: bool
        """
        file_path = self.make_name(video_id, self.glossary[video_id][KeyGTI.MOVIE_TYPE])
        self.logger.debug("File Path: %s", file_path)
        db = self.glossary[video_id]

        if tqdm is None:
            with file_path.open("wb") as f:
                for chunk in video_data.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
        else:
            with tqdm(total=db[KeyGTI.FILE_SIZE], leave=False,
                      unit="B", unit_scale=True, file=sys.stdout) as pbar:
                with file_path.open("wb") as f:
                    for chunk in video_data.iter_content(chunk_size=chunk_size):
                        if chunk:
                            pbar.update(f.write(chunk))
        self.logger.info(Msg.nd_download_done, file_path)
        return True


class Thumbnail(utils.Canopy):
    def __init__(self, logger=None):
        """
        :param NTLogger logger:
        """
        super().__init__(logger=logger)

    def start(self, glossary, save_dir, is_large=True):
        """

        :param dict[str, dict[str, int | str]] | list[str] glossary:
        :param str | Path save_dir:
        :param bool is_large: 大きいサムネイルを取りに行くかどうか
        :rtype: bool
        """
        utils.check_arg(locals())
        self.logger.debug("Directory to save in: %s", save_dir)
        self.logger.debug("Dictionary of Videos: %s", glossary)
        if isinstance(glossary, list):
            glossary = get_infos(glossary, self.logger)
        self.glossary = glossary
        self.save_dir = utils.make_dir(save_dir)

        self.logger.info(Msg.nd_start_dl_pict,
            len(self.glossary), list(self.glossary))

        for index, video_id in enumerate(self.glossary.keys()):
            self.logger.info(Msg.nd_download_pict,
                index + 1, len(glossary), video_id,
                self.glossary[video_id][KeyGTI.TITLE])
            self._download(video_id, is_large)
        return True

    def _download(self, video_id, is_large=True):
        """
        :param str video_id: 動画ID (e.g. sm1234)
        :param bool is_large: 大きいサムネイルを取りに行くかどうか
        :rtype: bool
        """
        utils.check_arg(locals())
        url = self.glossary[video_id][KeyGTI.THUMBNAIL_URL]
        if is_large:
            url += ".L"
        image_data = self._worker(video_id, url, is_large)
        if not image_data:
            return False
        return self._saver(video_id, image_data)

    def _worker(self, video_id, url, is_large=True):
        """
        サムネイル画像をダウンロードしにいく。

        :param str video_id: 動画ID (e.g. sm1234)
        :param str url: 画像のURL
        :param bool is_large: 大きいサムネイルを取りに行くかどうか
        :rtype: bool | requests.Response
        """
        utils.check_arg(locals())
        db = self.glossary[video_id]
        with requests.Session() as session:
            try:
                # connect timeoutを5秒, read timeoutを10秒に設定
                response = session.get(url=url, timeout=(5.0, 10.0))
                if response.ok:
                    return response
                # 大きいサムネイルを求めて404が返ってきたら標準の大きさで試す
                if response.status_code == 404:
                    if is_large and url.endswith(".L"):
                        return self._worker(video_id, url[:-2], is_large=False)
                    else:
                        self.logger.error(Err.connection_404,
                            video_id, db[KeyGTI.TITLE])
                        return False
            except (TypeError, ConnectionError,
                    socket.timeout, Timeout,
                    urllib3.exceptions.TimeoutError,
                    urllib3.exceptions.RequestError) as e:
                self.logger.debug("An exception occurred: %s", e)
                if is_large and url.endswith(".L"):
                    return self._worker(video_id, url[:-2], is_large=False)
                else:
                    self.logger.error(Err.connection_timeout.format(video_id)
                                      + " (タイトル: {})".format(db[KeyGTI.TITLE]))
                    return False

    def _saver(self, video_id, image_data, _=None):
        """

        :param str video_id: 動画ID (e.g. sm1234)
        :param requests.Response image_data: 画像のデータ
        :return:
        """
        file_path = self.make_name(video_id, "jpg")
        self.logger.debug("File Path: %s", file_path)

        with file_path.open('wb') as f:
            f.write(image_data.content)
        self.logger.info(Msg.nd_download_done, file_path)
        return True


class Comment(utils.Canopy):
    def __init__(self, mail=None, password=None, logger=None, session=None):
        """
        :param str | None mail:
        :param str | None password:
        :param NTLogger logger:
        :param requests.Session session:
        """
        super().__init__(logger=logger)
        self.session = session or utils.LogIn(mail=mail, password=password).session

    def start(self, glossary, save_dir, xml=False):
        """

        :param dict[str, dict[str, int | str]] | list[str] glossary:
        :param str | Path save_dir:
        :param bool xml:
        """
        utils.check_arg(locals())
        self.logger.debug("Directory to save in: %s", save_dir)
        self.logger.debug("Dictionary of Videos: %s", glossary)
        self.logger.debug("Download XML? : %s", xml)
        if isinstance(glossary, list):
            glossary = get_infos(glossary, self.logger)
        self.glossary = glossary
        self.save_dir = utils.make_dir(save_dir)
        self.logger.info(Msg.nd_start_dl_comment,
            len(self.glossary), list(self.glossary))
        for index, video_id in enumerate(self.glossary.keys()):
            self.logger.info(Msg.nd_download_comment,
                index + 1, len(glossary), video_id,
                self.glossary[video_id][KeyGTI.TITLE])
            self._download(video_id, xml)
            if len(self.glossary) > 1:
                time.sleep(1.5)
        return True

    def _download(self, video_id, xml=False):
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
        self.logger.debug("Video ID: %s and its Thread ID (of officials):"
                          " %s", video_id, db[KeyGTI.V_OR_T_ID])

        response = utils.get_from_getflv(
            db[KeyGTI.V_OR_T_ID], self.session, self.logger)

        if response is None:
            time.sleep(4)
            print(Err.waiting_for_permission)
            time.sleep(4)
            return self._download(video_id, xml)

        thread_id = response[KeyGetFlv.THREAD_ID]
        msg_server = response[KeyGetFlv.MSG_SERVER]
        user_id = response[KeyGetFlv.USER_ID]
        user_key = response[KeyGetFlv.USER_KEY]

        opt_thread_id = response[KeyGetFlv.OPT_THREAD_ID]
        needs_key = response[KeyGetFlv.NEEDS_KEY]

        if xml and video_id.startswith(("sm", "nm")):
            req_param = self.make_param_xml(thread_id, user_id)
            self.logger.debug("Posting Parameters: %s", req_param)

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

            self.logger.debug("Posting Parameters: %s", req_param)
            res_com = self.session.post(
                url=URL.URL_Msg_JSON,
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
        self.logger.debug("File Path: %s", file_path)
        with file_path.open("w", encoding="utf-8") as f:
            f.write(comment_data + "\n")
        self.logger.info(Msg.nd_download_done, file_path)
        return True

    def get_thread_key(self, thread_id, needs_key):
        """
        専用のAPIにアクセスして thread_key を取得する。

        :param str thread_id:
        :param str needs_key:
        :rtype: tuple[str, str]
        """
        utils.check_arg(locals())
        if not needs_key == "1":
            self.logger.debug("Video ID (or Thread ID): %s,"
                              " needs_key: %s", thread_id, needs_key)
            return "", "0"
        response = self.session.get(URL.URL_GetThreadKey, params={"thread": thread_id})
        self.logger.debug("Response from GetThreadKey API: %s", response.text)
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
        self.logger.debug("Arguments: %s", locals())
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
        :rtype: list[dict]
        """
        utils.check_arg({"official_video": official_video, "user_id": user_id,
                         "user_key": user_key, "thread_id": thread_id})
        self.logger.debug("Arguments of creating JSON: %s", locals())
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
    if hasattr(args, "dmc"):
        sys.exit(Err.unexpected_commands.format("--dmc"))
    if hasattr(args, "smile"):
        sys.exit(Err.unexpected_commands.format("--smile"))
    videoid = utils.validator(args.VIDEO_ID)
    if not videoid:
        sys.exit(Err.invalid_videoid)
    if not (args.getthumbinfo or args.thumbnail or args.comment or args.video):
        sys.exit(Err.not_specified.format("--thumbnail、 --comment、 --video のいずれか"))

    if args.getthumbinfo:
        file_name = args.out[0] if isinstance(args.out, list) else None
        return utils.print_info(videoid, file_name)

    #
    # 本筋
    #
    log_level = "DEBUG" if is_debug else args.loglevel
    logger = utils.NTLogger(log_level=log_level, file_name=utils.LOG_FILE_ND)
    destination = utils.make_dir(args.dest[0])
    database = get_infos(videoid, logger=logger)

    res_t = False
    if args.thumbnail:
        res_t = Thumbnail(logger=logger).start(database, destination)
        if not (args.comment or args.video):
            # サムネイルのダウンロードだけならここで終える。
            return res_t

    session = utils.LogIn(mail=mailadrs, password=password).session

    res_c = False
    if args.comment:
        res_c = Comment(logger=logger, session=session).start(database, destination, args.xml)

    res_v = False
    if args.video:
        res_v = Video(logger=logger, session=session).start(database, destination)

    return res_c | res_v | res_t
