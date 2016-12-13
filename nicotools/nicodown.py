# coding: utf-8
import html
import os

import requests
import sys
import time
from pathlib import Path
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectTimeout
from requests.packages.urllib3.util.retry import Retry
from requests.packages.urllib3.exceptions import MaxRetryError
from urllib.parse import parse_qs
from xml.etree import ElementTree

try:
    import progressbar
except ImportError:
    progressbar = None

from . import utils
from .utils import Msg, Err, URL, Key
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

IS_DEBUG = int(os.getenv("PYTHON_TEST", "0"))


def print_info(queue, file_name=None):
    """
    GetThumbInfo にアクセスして返ってきたXMLをそのまま表示する。

    :param list queue:
    :param str | Path | None file_name:
    :return: bool
    """
    text = "\n\n".join([requests.get(URL.URL_Info + video_id).text for video_id in queue])
    if file_name:
        file_name = utils.make_dir(file_name)
        if file_name is None:
            return False
        with file_name.open(encoding="utf-8", mode="w") as fd:
            fd.write(text + "\n")
    else:
        print(text.encode(utils.get_encoding(), Msg.BACKSLASH).decode(utils.get_encoding()))
    return True


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
    * watch_url         str

    :param list[str] queue: 動画IDのリスト
    :param NTLogger | None logger: ログ出力
    :rtype: dict[str, dict[str, int | str | list]]
    """
    if logger: logger.info(Msg.nd_start_download.format(len(queue)))
    else: print(Msg.nd_start_download.format(len(queue)))

    # データベースとして使うための辞書。削除や非公開の動画はここに入る
    lexikon = {}
    for video_id in utils.validator(queue):
        xmldata = requests.get(URL.URL_Info + video_id).text
        root = ElementTree.fromstring(xmldata)
        # 「status="ok"」 なら動画は生存 / 存在しない動画には「status="fail"」が返る
        if not root.get("status").lower() == "ok":
            if logger: logger.warning(Msg.nd_deleted_or_private.format(video_id))
            else: print(Msg.nd_deleted_or_private.format(video_id))
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
            minute, second = finder(Key.LENGTH).text.split(":")

            pocket[Key.COMMENT_NUM]     = int(finder(Key.COMMENT_NUM).text)
            pocket[Key.DESCRIPTION]     = html.unescape(finder(Key.DESCRIPTION).text)
            pocket[Key.EMBEDDABLE]      = int(finder(Key.EMBEDDABLE).text)
            pocket[Key.FILE_NAME]       = t2filename(finder(Key.TITLE).text)
            pocket[Key.FIRST_RETRIEVE]  = finder(Key.FIRST_RETRIEVE).text[:10]
            pocket[Key.LAST_RES_BODY]   = finder(Key.LAST_RES_BODY).text
            pocket[Key.LENGTH]          = "{}:{}".format(minute, second)
            pocket[Key.LENGTH_SECONDS]  = int(minute) * 60 + int(second)
            pocket[Key.MYLIST_COUNTER]  = int(finder(Key.MYLIST_COUNTER).text)
            pocket[Key.MOVIE_TYPE]      = finder(Key.MOVIE_TYPE).text.lower()
            pocket[Key.NO_LIVE_PLAY]    = int(finder(Key.NO_LIVE_PLAY).text)
            pocket[Key.SIZE_HIGH]       = int(finder(Key.SIZE_HIGH).text)
            pocket[Key.SIZE_LOW]        = int(finder(Key.SIZE_LOW).text)
            pocket[Key.TAGS]            = html.unescape(", ".join(tag_list))  # type: str
            pocket[Key.TAGS_LIST]       = tag_list  # type: list
            pocket[Key.THUMBNAIL_URL]   = finder(Key.THUMBNAIL_URL).text
            pocket[Key.TITLE]           = html.unescape(finder(Key.TITLE).text)
            pocket[Key.VIDEO_ID]        = video_id
            pocket[Key.VIEW_COUNTER]    = int(finder(Key.VIEW_COUNTER).text)
            pocket[Key.WATCH_URL]       = finder(Key.WATCH_URL).text
            pocket[Key.V_OR_T_ID]       = finder(Key.WATCH_URL).text.split("/")[-1]
            if video_id.startswith(("sm", "nm")):
                pocket[Key.USER_ID]         = int(finder(Key.USER_ID).text)
                pocket[Key.USER_NAME]       = html.unescape(finder(Key.USER_NAME).text)
                pocket[Key.USER_ICON_URL]   = finder(Key.USER_ICON_URL).text
            else:  # so1234 または 123456 の形式
                pocket[Key.CH_ID]           = int(finder(Key.CH_ID).text)
                pocket[Key.CH_NAME]         = html.unescape(finder(Key.CH_NAME).text)
                pocket[Key.CH_ICON_URL]     = finder(Key.CH_ICON_URL).text
            lexikon[video_id]               = pocket
    return lexikon


def t2filename(text):
    """
    ファイル名に使えない文字を全角文字に置き換える。

    :param str text: ファイル名
    :rtype: str
    """
    mydic = {
        r"\/": "／", "/": "／", "'": "’", "\"": "”",
        "<": "＜", ">": "＞", "|": "｜", ":": "：",
        "*": "＊", "?": "？", "~": "～", "\\": "＼"
    }
    for item in mydic.keys():
        text = text.replace(item, mydic[item])
    # 置き換えるペアが増えたらこっちを使うと楽かもしれない
    # pattern = re.compile("|".join(re.escape(key) for key in mydic.keys()))
    # return pattern.sub(lambda x: mydic[x.group()], text)
    return text


class Canopy:
    def __init__(self):
        self.database = None
        self.save_dir = None  # type: Path

    def make_name(self, vid, ext):
        """
        ファイル名を返す。

        :param str vid:
        :param str ext:
        :rtype: Path
        """
        file_name =  Msg.nd_file_name.format(vid, self.database[vid][Key.FILE_NAME], ext)
        return Path(self.save_dir).resolve() / file_name


class GetVideos(utils.LogIn, Canopy):
    def __init__(self, mail=None, password=None, logger=None, session=None):
        """
        動画をダウンロードする。

        :param str | None mail:
        :param str | None password:
        :param T <= logging.logger logger:
        :param requests.Session session:
        """
        super().__init__(mail=mail, password=password, logger=logger, session=session)

        if progressbar is None:
            self.widgets = None
        else:
            self.widgets = [
                progressbar.Percentage(),
                ' ', progressbar.Bar(),
                ' ', progressbar.ETA(),
                ' ', progressbar.AdaptiveTransferSpeed(),
            ]

    def start(self, database, save_dir):
        """

        :param dict[str, dict[str, int | str]] database:
        :param str | Path save_dir:
        :rtype: bool
        """
        utils.check_arg(locals())
        self.save_dir = utils.make_dir(save_dir, self.logger)
        if self.save_dir is None:
            return False
        self.database = database
        self.logger.info(Msg.nd_start_dl_video.format(len(self.database)))

        for index, video_id in enumerate(self.database.keys()):
            self.logger.info(
                Msg.nd_download_video.format(
                    index + 1, len(database), video_id,
                    self.database[video_id][Key.TITLE]))
            self.download(video_id)
            if len(database) > 1:
                time.sleep(1)
        return True

    def download(self, video_id, chunk_size=1024 * 50):
        """
        :param str video_id: 動画ID (e.g. sm1234)
        :param int chunk_size:
        :rtype: bool
        """
        utils.check_arg(locals())
        db = self.database[video_id]
        if video_id.startswith("so"):
            redirected = self.session.get(URL.URL_Watch + video_id).url.split("/")[-1]
            db[Key.V_OR_T_ID] = redirected

        response = self.session.get(URL.URL_GetFlv + db[Key.V_OR_T_ID]
                                    + ("", "?as3=1")[video_id.startswith("nm")])

        parameters = parse_qs(response.text)
        vid_url = parameters["url"][0]
        is_premium = parameters["is_premium"][0]
        # self.logger.debug(Msg.nd_video_url_is.format(video_id, vid_url))

        file_path = self.make_name(video_id, db[Key.MOVIE_TYPE])

        if is_premium == "1":
            file_size = db[Key.SIZE_HIGH]
        else:
            file_size = db[Key.SIZE_LOW]

        # 動画視聴ページに行ってCookieをもらってくる
        self.session.get(URL.URL_Watch + video_id)
        # connect timeoutを10秒, read timeoutを30秒に設定
        video_data = self.session.get(url=vid_url, stream=True, timeout=(10.0, 30.0))

        if progressbar is None:
            with file_path.open("wb") as f:
                [f.write(chunk) for chunk in
                 video_data.iter_content(chunk_size=chunk_size) if chunk]
        else:
            pbar = progressbar.ProgressBar(widgets=self.widgets, max_value=file_size)
            pbar.start()
            with file_path.open("wb") as f:
                downloaded_size = 0
                for chunk in video_data.iter_content(chunk_size=chunk_size):
                    if chunk:
                        downloaded_size += f.write(chunk)
                        pbar.update(min(downloaded_size, file_size))
            pbar.finish()
        self.logger.info(Msg.nd_download_done.format(file_path))
        return True


class GetThumbnails(Canopy):
    def __init__(self, logger=None):
        """
        :param T <= logging.logger logger:
        """
        super().__init__()
        self.logger = logger
        if not logger or not hasattr(logger, "handlers"):
            self.logger = utils.NTLogger()

    def start(self, database, save_dir):
        """

        :param dict[str, dict[str, int | str]] database:
        :param str | Path save_dir:
        :rtype: bool
        """
        utils.check_arg(locals())
        self.database = database
        self.save_dir = utils.make_dir(save_dir, self.logger)
        if self.save_dir is None:
            return False
        self.logger.info(Msg.nd_start_dl_pict.format(len(self.database)))
        for index, video_id in enumerate(self.database.keys()):
            self.logger.info(
                Msg.nd_download_pict.format(
                    index + 1, len(database), video_id,
                    self.database[video_id][Key.TITLE]))
            self.download(video_id)
        return True

    def download(self, video_id):
        """
        :param str video_id: 動画ID (e.g. sm1234)
        :rtype: bool
        """
        utils.check_arg(locals())
        image_data = self._download(video_id)
        if not image_data:
            return False

        file_path = self.make_name(video_id, "jpg")

        with file_path.open('wb') as f:
            f.write(image_data.content)
        self.logger.info(Msg.nd_download_done.format(file_path))
        return True

    def _download(self, video_id, is_large=True, retry=1):
        """
        サムネイル画像をダウンロードしにいく。

        :param str video_id: 動画ID (e.g. sm1234)
        :param bool is_large: 大きいサイズのサムネイルを取りに行くかどうか
        :param int retry: 再試行回数
        :rtype: bool | requests.Response
        """
        utils.check_arg(locals())
        with requests.Session() as session:
            # retry設定
            retries = Retry(total=retry,
                            backoff_factor=1,
                            status_forcelist=[500, 502, 503, 504])
            session.mount("http://", HTTPAdapter(max_retries=retries))

            url = self.database[video_id][Key.THUMBNAIL_URL] + ("", ".L")[is_large]
            try:
                # connect timeoutを10秒, read timeoutを30秒に設定
                response = session.get(url=url, timeout=(5.0, 10.0))

                # 大きいサムネイルを求めて404が返ってきたら標準の大きさで試す
                if response.status_code == 404 and is_large:
                    return self._download(video_id, is_large=False)
                elif response.ok:
                    return response
                else:
                    return False
            except (ConnectTimeout, MaxRetryError):
                self.logger.error(Err.connection_timeout.format(
                    video_id, self.database[video_id][Key.TITLE]))
                return False


class GetComments(utils.LogIn, Canopy):
    def __init__(self, mail=None, password=None, logger=None, session=None):
        """
        :param str | None mail:
        :param str | None password:
        :param T <= logging.logger logger:
        :param requests.Session session:
        """
        super().__init__(mail=mail, password=password, logger=logger, session=session)

    def start(self, database, save_dir, xml_mode=False):
        """

        :param dict[str, dict[str, int | str]] database:
        :param str | Path save_dir:
        :param bool xml_mode:
        """
        utils.check_arg(locals())
        self.database = database
        self.save_dir = utils.make_dir(save_dir, self.logger)
        if self.save_dir is None:
            return False
        self.logger.info(Msg.nd_start_dl_comment.format(len(self.database)))
        for index, video_id in enumerate(self.database.keys()):
            self.logger.info(
                Msg.nd_download_comment.format(
                    index + 1, len(database), video_id,
                    self.database[video_id][Key.TITLE]))
            self.download(video_id, xml_mode)
            if len(self.database) > 1:
                time.sleep(1.5)
        return True

    def download(self, video_id, xml_mode=False):
        """
        :param str video_id: 動画ID (e.g. sm1234)
        :param bool xml_mode:
        :rtype: bool
        """
        utils.check_arg(locals())
        db = self.database[video_id]
        if video_id.startswith("so"):
            redirected = self.session.get(URL.URL_Watch + video_id).url.split("/")[-1]
            db[Key.V_OR_T_ID] = redirected

        response = self.session.get(URL.URL_GetFlv + db[Key.V_OR_T_ID]
                                    + ("", "?as3=1")[video_id.startswith("nm")])

        if "error=access_locked" in response.text:
            time.sleep(3)
            print("アクセス制限が解除されるのを待っています…")
            time.sleep(3)
            return self.download(video_id)

        parameters = parse_qs(response.text)
        thread_id = parameters["thread_id"][0]  # type: str
        msg_server = parameters["ms"][0]  # type:str
        user_id = parameters["user_id"][0]  # type: str
        user_key = parameters["userkey"][0]  # type: str

        opt_thread_id = parameters["optional_thread_id"][0] if parameters.get("optional_thread_id") else None
        needs_key = parameters["needs_key"][0] if parameters.get("needs_key") else None

        if xml_mode and video_id.startswith(("sm", "nm")):
            comment_data = (self.session.post(
                url=msg_server,
                data=self.make_param_xml(thread_id, user_id))
                            .text.replace("><", ">\n<"))
            extention = "xml"
        else:
            if video_id.startswith(("sm", "nm")):
                req_param = self.make_param_json(
                    False, user_id, user_key, thread_id)
            else:
                thread_key, force_184 = self.get_thread_key(db[Key.V_OR_T_ID], needs_key)
                req_param = self.make_param_json(
                    True, user_id, user_key, thread_id,
                    opt_thread_id, thread_key, force_184)

            res_com = self.session.post(URL.URL_Message_New, json=req_param)
            comment_data = res_com.text.encode(res_com.encoding).decode("utf-8").replace("}, ", "},\n")
            extention = "json"

        file_path = self.make_name(video_id, extention)

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
            print("video id: {}, needs_key: {}".format(video_id, needs_key))
            return "", "0"
        response = self.session.get(URL.URL_GetThreadKey, params={"thread": video_id})
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
    mailadrs = args.mail[0] if args.mail else None
    password = args.password[0] if args.password else None

    """ エラーの除外 """
    videoid = utils.validator(args.VIDEO_ID)
    if not videoid:
        sys.exit(Err.invalid_videoid)
    if not (args.getthumbinfo or args.thumbnail or args.comment or args.video):
        sys.exit(Err.not_specified.format("--thumbnail、 --comment、 --video のいずれか"))

    if args.getthumbinfo:
        file_name = args.out[0] if isinstance(args.out, list) else None
        return print_info(videoid, file_name)

    """ 本筋 """
    logger = utils.NTLogger(log_level=args.loglevel, file_name=Msg.LOG_FILE_ND)
    destination = args.dest[0] if isinstance(args.dest, list) else None  # type: str
    destination = utils.make_dir(destination, logger)
    database = get_infos(videoid, logger=logger)

    if args.thumbnail and not (args.comment or args.video):
        return GetThumbnails(logger=logger).start(database, destination)

    session = utils.LogIn(mail=mailadrs, password=password, logger=logger).session

    res_c = False
    if args.comment:
        res_c = GetComments(logger=logger, session=session).start(database, destination, args.xml)

    res_v = False
    if args.video:
        res_v = GetVideos(logger=logger, session=session).start(database, destination)

    return res_c | res_v
