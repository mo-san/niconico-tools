# coding: UTF-8
import asyncio
import inspect
import logging
import os
import re
import sys
from argparse import ArgumentParser
from getpass import getpass
from pathlib import Path
from urllib.parse import parse_qs
from http.cookiejar import LWPCookieJar

from appdirs import user_data_dir
import requests
from requests import cookies

ALL_ITEM = "*"
DEFAULT_NAME = "とりあえずマイリスト"
DEFAULT_ID = 0
LOG_FILE = "nicotools.log"
IS_DEBUG = int(os.getenv("PYTHON_TEST", 0))
if IS_DEBUG:
    __os_name = os.getenv("TRAVIS_OS_NAME", os.name)
    __version = (os.getenv("TRAVIS_PYTHON_VERSION") or
               os.getenv("PYTHON_VERSION") or
               "_" .join(map(str, sys.version_info[0:3])))
    COOKIE_FILE_NAME = "nicotools_cokkie_{0}_{1}.txt".format(__os_name, __version)
else:
    COOKIE_FILE_NAME = "nicotools_cookie.txt"

# 文字列をUTF-8以外にエンコードするとき、変換不可能な文字をどう扱うか
BACKSLASH = "backslashreplace"
CHARREF = "xmlcharrefreplace"
REPLACE = "replace"


def get_encoding():
    """
    コンソールの文字コードを返す。sys.stdout.encoding が None の時には UTF-8を返す。

    :rtype: str
    """
    return sys.stdout.encoding or "UTF-8"


def validator(input_list):
    """
    動画IDが適切なものか確認する。 重複があれば除外する。
    元のリスト内の順番は保持されない。

    受け入れるのは以下の形式:
        * "*"
        * http://www.nicovideo.jp/watch/sm123456
        * http://nico.ms/sm123456
        * sm1234
        * watch/sm123456
        * nm1234
        * watch/nm123456
        * so1234
        * watch/so123456
        * 123456
        * watch/123456

    :param list[str] | tuple[str] | set[str] input_list:
    :rtype: list[str]
    """
    matcher = re.compile(
        """\s*(?:
        {0}|  # 「全て」を指定するときの記号
        (?:
            (?:(?:h?t?tp://)?www\.nicovideo\.jp/)?watch/  # 通常URL
           |(?:h?t?tp://)?nico\.ms/  # 短縮URL
        )?
            ((?:sm|nm|so)?\d+)  # ID本体
        )\s?""".format(re.escape(ALL_ITEM)), re.I + re.X).match
    if isinstance(input_list, str):
        input_list = [input_list]

    if not isinstance(input_list, (list, tuple, set)):
        print(Err.invalid_argument.format(input_list))
        sys.exit()

    if "\t" in input_list[0]:
        for line in input_list[1:]:
            if "\t" not in line:
                return []
        input_list = [item.split("\t")[0] for item in input_list]
    else:
        if len(input_list) == 1 and input_list[0] == ALL_ITEM:
            return input_list
        for item in input_list:
            if not matcher(item):
                return []

    # ................................↓"*" が入っていたときの対策
    return [matcher(item).group(1) or item.strip()
            for item in set(input_list) if matcher(item) or ALL_ITEM in item]


def get_dir(directory):
    """
    保存場所に指定されたフォルダーがない場合にはつくり、その絶対パスを返す。

    :param str | Path directory: フォルダー名
    :rtype: Path
    """
    if directory is None:
        return Path().cwd()

    if isinstance(directory, str):
        directory = Path(directory)
    if directory.suffix:
        return get_dir(directory.parent) / directory.name
    try:
        if not directory.is_dir():
            directory.mkdir(parents=True)
        return directory.resolve()
    except (
            # [WinError 87] パラメーターが間違っています。
            # (con とか nul とか)(Python 3.5以下で起こる。)
            OSError,
            # [WinError 2] 指定されたファイルが見つかりません。(Python 3.5以下で起こる。)
            FileNotFoundError,
            # [WinError 267] ディレクトリ名が無効です。(con とか nul とか)
            NotADirectoryError,
            # [WinError 5] アクセスが拒否されました。(C:/ とか D:/ とか)
            # [Errno 13] Permission denied (同名のフォルダーがあってそこに書き込もうとした場合)
            PermissionError,
            # [WinError 183] 既に存在するファイルを作成することはできません。
            FileExistsError
    ):
        print(Err.invalid_dirname.format(directory), file=sys.stderr)
        sys.exit()


def t2filename(text):
    """
    ファイル名に使えない文字を全角文字に置き換える。

    :param str text: ファイル名
    :rtype: str
    """
    mydic = {
        r"\/": "／", "/": "／", "'": "’", "\"": "”",
        "<"  : "＜", ">": "＞", "|": "｜", ":": "：",
        "*"  : "＊", "?": "？", "~": "～", "\\": "＼"
    }
    for item in mydic.keys():
        text = text.replace(item, mydic[item])
    # 置き換えるペアが増えたらこっちを使うと楽かもしれない
    # pattern = re.compile("|".join(re.escape(key) for key in mydic.keys()))
    # return pattern.sub(lambda x: mydic[x.group()], text)
    return text


def sizeof_fmt(num):
    """
    数字を読みやすい単位で表す。

    :param int num: 計りたい整数
    :rtype: str
    """
    for unit in ['B', 'Kb', 'Mb']:
        if num < 1024.0 and isinstance(num, int):
            return "{:3}{:s}".format(num, unit)
        elif num < 1024.0:
            return "{:3.2f}{:s}".format(num, unit)
        num /= 1024.0
    return "{:.2f}Gb".format(num)


def extract_getflv(content):
    """

    :param str content: GetFLV の返事
    :rtype: dict[str, str] | None
    """
    parameters = parse_qs(content)
    if parameters.get("error") is not None:
        return None
    result = {
        KeyGetFlv.THREAD_ID    : int(parameters[KeyGetFlv.THREAD_ID][0]),
        KeyGetFlv.LENGTH       : int(parameters[KeyGetFlv.LENGTH][0]),
        KeyGetFlv.VIDEO_URL    : parameters[KeyGetFlv.VIDEO_URL][0],
        KeyGetFlv.MSG_SERVER   : parameters[KeyGetFlv.MSG_SERVER][0],
        KeyGetFlv.MSG_SUB      : parameters[KeyGetFlv.MSG_SUB][0],
        KeyGetFlv.USER_ID      : int(parameters[KeyGetFlv.USER_ID][0]),
        KeyGetFlv.IS_PREMIUM   : int(parameters[KeyGetFlv.IS_PREMIUM][0]),
        KeyGetFlv.NICKNAME     : parameters[KeyGetFlv.NICKNAME][0],
        KeyGetFlv.USER_KEY     : parameters[KeyGetFlv.USER_KEY][0],

        # 以下は公式動画にだけあるもの。通常の動画ではNone
        KeyGetFlv.OPT_THREAD_ID: None,
        KeyGetFlv.NEEDS_KEY    : None,
    }

    opt_thread_id   = parameters.get(KeyGetFlv.OPT_THREAD_ID, [None])[0]
    needs_key       = parameters.get(KeyGetFlv.NEEDS_KEY, [None])[0]
    if opt_thread_id is not None:
        result.update({
            KeyGetFlv.OPT_THREAD_ID : int(opt_thread_id),
            KeyGetFlv.NEEDS_KEY     : int(needs_key),
        })
    return result


class MylistAPIError(Exception):
    """ APIの操作の結果が好ましくない場合に発生させるエラー """
    def __init__(self, code=None, msg=None, ok=False):
        """
        :param str code: APIのエラーコード(の文字列)
        :param str msg: 伝えたい文言
        :param bool ok: 作業を続行してよいかどうか
        """
        self.code = code
        self.msg = msg
        self.ok = ok


def make_name(data: dict, save_dir: Path, extention: str=None):
    """
    ファイル名を返す。

    :param dict data: 動画アイテムひとつ分の情報
    :param Path save_dir: 保存場所
    :param str extention: 拡張子
    :rtype: Path
    """
    ext = data[KeyDmc.MOVIE_TYPE]
    if extention:
        ext = extention
    file_name =  Msg.nd_file_name.format(vid=data[KeyDmc.VIDEO_ID], ext=ext, name=data[KeyGTI.FILE_NAME])
    return Path(save_dir).resolve() / file_name


class Canopy:
    def __init__(self, loop: asyncio.AbstractEventLoop=None, logger=None):
        self.logger = self.get_logger(logger)  # type: NTLogger
        self.loop = loop or asyncio.get_event_loop()  # type: asyncio.AbstractEventLoop

    def get_logger(self, logger):
        """
        ロガーを返す。

        すでにあるならそれを使い、無い、またはハンドラーを持たなければ新しく作って返す。

        :param NTLogger logger:
        :rtype: NTLogger
        """
        if not (logger and hasattr(logger, "handlers")):
            return NTLogger()
        else:
            return logger


class LogIn:
    __singleton__ = None
    is_login = False
    cookie = {}

    @classmethod
    # more と kwargs は未使用の変数だが消してはいけない
    def __new__(cls, *more, **kwargs):
        """
        ログイン処理が一度だけなのを保障するためにシングルトンとして振る舞わせる。

        参考:
            デザインパターン（Design Pattern）#Singleton - Qiita
            http://qiita.com/nirperm/items/af1f83925ba43dbf22eb
        """

        if cls.__singleton__ is None:
            cls.__singleton__ = super().__new__(cls)
        return cls.__singleton__

    def __init__(self, mail=None, password=None, session=None):
        """
        :param str | None mail: メールアドレス
        :param str | None password: パスワード
        :param requests.Session | None session: セッションオブジェクト
        """
        if not (session or mail or password):
            self.session = self.get_session()
        elif session and not (mail or password):
            self.session = session
            self.token = self.get_token(self.session)
        else:
            self.session = self.get_session(self.ask_credentials(mail=mail, password=password))

    @staticmethod
    def cookie_filepath():
        return Path(user_data_dir("nicotools")) / COOKIE_FILE_NAME

    def get_session(self, auth=None):
        """
        クッキーを読み込み、必要ならばログインし、そのセッションを返す。

        :param dict[str, str] | None auth:
        :rtype: requests.Session
        """

        session = requests.session()
        cook = self.load_cookies()

        expired = True

        if cook:
            for cookie in cook:
                if cookie.name == "user_session":
                    expired = cookie.is_expired()
                    break

        if auth is not None or cook:

            session.cookies = cook

            if expired:
                session.post(URL.URL_LogIn, params=auth)

            self.token = self.get_token(session)

            if self.token:
                # if self._we_have_logged_in(res.text):
                session.cookies.save(ignore_discard=True)
                self.cookie = self.save_cookies(session.cookies)
                self.is_login = True
            else:
                return self.get_session(self.ask_credentials())
        else:
            return self.get_session(self.ask_credentials())
        return session

    def get_token(self, session):
        """
        マイリストの操作に必要な"NicoAPI.token"を取ってくる。

        :param requests.Session session:
        :rtype: str
        """
        htmltext = session.get(URL.URL_MyListTop).text
        try:
            fragment = htmltext.split("NicoAPI.token = \"")[1]
            return fragment[:fragment.find("\"")]
        except IndexError:
            return None

    @classmethod
    def ask_credentials(cls, mail=None, password=None):
        """
        メールアドレスとパスワードをユーザーに求める。

        :param str | None mail: メールアドレス。
        :param str | None password: パスワード
        :rtype: dict[str, str]
        """
        un = mail
        pw = password
        try:
            if un is None:
                r = re.compile("^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*$")
                while True:
                    print(Msg.input_mail)
                    un = input("-=>")
                    if not un: continue
                    if r.match(un): break
            if pw is None:
                while True:
                    print(Msg.input_pass)
                    pw = getpass("-=>")
                    if pw: break
        except (EOFError, KeyboardInterrupt):
            sys.exit(Err.keyboard_interrupt)
        return {
            "mail_tel": un,
            "password": pw
        }

    @classmethod
    def save_cookies(cls, requests_cookiejar, file_name=COOKIE_FILE_NAME):
        """
        クッキーを保存する。保存場所はユーザーのホームディレクトリ。

        :param cookies.RequestsCookieJar requests_cookiejar:
        :param str file_name:
        :rtype: dict
        """
        # Python 3.5以上専用の書き方。

        requests_cookiejar.save(ignore_discard=True)
        cook = {cookie.name: cookie.value for cookie in requests_cookiejar}

        return cook

    @classmethod
    def load_cookies(cls, file_name=COOKIE_FILE_NAME):
        """
        クッキーを読み込む。名前、値をタブで区切ったテキストファイルから。

        :param str file_name:
        :rtype: cookielib.LWPCookieJar
        """
        # Python 3.5以上専用の書き方。

        file_path = get_dir(cls.cookie_filepath())
        cookiejar = LWPCookieJar(str(file_path))

        if not file_path.exists():
            cookiejar.save()

        cookiejar.load()

        return cookiejar


class NTLogger(logging.Logger):
    def __init__(self, file_name=LOG_FILE, name=__name__, log_level=logging.INFO):
        """
        ログ出力のためのクラス。

        :param str | Path | None file_name:
        :param str name:
        :param str | int log_level:
        """
        if not isinstance(log_level, (str, int)):
            raise ValueError("Invalid Logging Level: {}".format(log_level))

        log_level = logging.getLevelName(log_level)
        self.log_level = log_level
        if (IS_DEBUG or
            isinstance(log_level, str) and log_level == "DEBUG" or
            isinstance(log_level, int) and log_level <= logging.DEBUG):
            self.is_debug = True
        else:
            self.is_debug = False

        logging.Logger.__init__(self, name, log_level)
        self.logger = logging.getLogger(name=name)

        # 標準出力用ハンドラー
        log_stdout = logging.StreamHandler(sys.stdout)
        log_stdout.setLevel(log_level)
        formatter = self.get_formatter("stdout")
        log_stdout.setFormatter(formatter)
        self.addHandler(log_stdout)

        if file_name is not None:
            # ファイル書き込み用ハンドラー
            if isinstance(file_name, Path):
                log_file = logging.FileHandler(
                    filename=str(file_name), encoding="utf-8")
            else:
                log_file = logging.FileHandler(encoding="utf-8",
                    filename=str(Path.home() / file_name))
            log_file.setLevel(log_level)
            formatter = self.get_formatter("file")
            log_file.setFormatter(formatter)
            self.addHandler(log_file)

    def get_formatter(self, mode):
        """
        書式を指定する。

        :param str mode: stdout, file
        :rtype: logging.Formatter
        """
        if mode == "stdout":
            fmt = logging.Formatter("[{levelname: ^7}]\t{message}", style="{")
        else:  # file
            if self.is_debug:
                fmt = logging.Formatter("[{asctime}|{levelname: ^7}|{message}", style="{")
            else:
                fmt = logging.Formatter("[{asctime}|{levelname: ^7}]\t{message}", style="{")
        return fmt

    def forwarding(self, level, msg, *args, **kwargs):
        _enco = get_encoding()
        if self.is_debug:
            # [YYYY-MM-DD hh:mm:ss,ms| level |line:n|<...> from <...> from <...>]\t{message}
            history = inspect.stack()
            funcs = "line:{}|{}".format(
                # ログを呼び出した場所の行数
                history[2][2],
                # ログを呼び出した関数の名前をつなげる
                " from ".join(["<{}>".format(item[3]) for item in history[2:5]])
            )
            if level <= logging.DEBUG:
                msg = funcs + "]\t" + str(msg)
            else:
                msg = funcs + "]\t\t" + str(msg)
        _msg = str(msg).encode(_enco, BACKSLASH).decode(_enco)
        _args = tuple([item.encode(_enco, BACKSLASH).decode(_enco)
                       if isinstance(item, str) else item for item in args[0]])
        self._log(level, _msg, _args, **kwargs)

    def debug(self, msg, *args, **kwargs): self.forwarding(logging.DEBUG, msg, args, **kwargs)

    def info(self, msg, *args, **kwargs): self.forwarding(logging.INFO, msg, args, **kwargs)

    def warning(self, msg, *args, **kwargs): self.forwarding(logging.WARNING, msg, args, **kwargs)

    def error(self, msg, *args, **kwargs): self.forwarding(logging.ERROR, msg, args, **kwargs)

    def critical(self, msg, *args, **kwargs): self.forwarding(logging.CRITICAL, msg, args, **kwargs)


class URL:
    URL_LogIn  = "https://secure.nicovideo.jp/secure/login?site=niconico"
    URL_Watch  = "http://www.nicovideo.jp/watch/"
    URL_GetFlv = "http://ext.nicovideo.jp/api/getflv/"
    URL_Info   = "http://ext.nicovideo.jp/api/getthumbinfo/"
    URL_Pict   = "http://tn-skr1.smilevideo.jp/smile"
    URL_GetThreadKey = "http://flapi.nicovideo.jp/api/getthreadkey"
    URL_WayBackKey = "http://flapi.nicovideo.jp/api/getwaybackkey"
    URL_Msg_JSON = "http://nmsg.nicovideo.jp/api.json/"
    URL_Msg_XML = "http://nmsg.nicovideo.jp/api/"

    # 一般のマイリストを扱うためのAPI
    URL_MyListTop  = "http://www.nicovideo.jp/my/mylist"
    URL_ListAll    = "http://www.nicovideo.jp/api/mylistgroup/list"
    URL_AddMyList  = "http://www.nicovideo.jp/api/mylistgroup/add"
    URL_PurgeList  = "http://www.nicovideo.jp/api/mylistgroup/delete"
    URL_ListOne    = "http://www.nicovideo.jp/api/mylist/list"
    URL_AddItem    = "http://www.nicovideo.jp/api/mylist/add"
    URL_DeleteItem = "http://www.nicovideo.jp/api/mylist/delete"
    URL_CopyItem   = "http://www.nicovideo.jp/api/mylist/copy"
    URL_MoveItem   = "http://www.nicovideo.jp/api/mylist/move"
    URL_UpdateItem = "http://www.nicovideo.jp/api/mylist/update"

    # とりあえずマイリストを扱うためのAPI
    URL_ListDef   = "http://www.nicovideo.jp/api/deflist/list"
    URL_AddDef    = "http://www.nicovideo.jp/api/deflist/add"
    URL_DeleteDef = "http://www.nicovideo.jp/api/deflist/delete"
    URL_CopyDef   = "http://www.nicovideo.jp/api/deflist/copy"
    URL_MoveDef   = "http://www.nicovideo.jp/api/deflist/move"
    URL_UpdateDef = "http://www.nicovideo.jp/api/deflist/update"


class Msg:
    """メッセージ集"""

    description = ("nicotools downlaod --help または nicotools mylist --help"
                   " で各コマンドのヘルプを表示します。")

    ''' マイリスト編集コマンドのヘルプメッセージ '''
    ml_description = ("マイリストを扱います。 add, delete, move, copy の引数には"
                      "テキストファイルも指定できます。 その場合はファイル名の"
                      "先頭に \"+\" をつけます。 例: +\"C:/ids.txt\"")
    ml_help_group_b = "マイリスト自体を操作する"
    ml_help_group_a = "リスト中の項目を操作する"
    ml_help_add = "指定したIDの動画を マイリストに追加します。"
    ml_help_delete = ("そのマイリストから 指定したIDの動画を削除します。"
                      "動画IDの代わりに * を指定すると、 マイリストを空にします。")
    ml_help_move = "移動元から移動先へと 動画を移動します。"
    ml_help_copy = ("コピー元からコピー先へと 動画をコピーします。 "
                    "動画IDの代わりに * を指定すると、 マイリスト全体をコピーします。")
    ml_help_export = ("登録された動画IDのみを改行で区切り、出力します。"
                      "名前の代わりに * を指定すると 全マイリストを一覧にします。")
    ml_help_show = ("登録された動画の情報をタブ区切り形式で出力します。"
                    "名前の代わりに * を指定すると マイリスト全体のメタデータを出力します。"
                    "-ss のように2回指定すると表形式で表示します。")
    ml_help_outfile = "そのファイル名で テキストファイルに出力します。"
    ml_help_purge = "そのマイリスト自体を削除します。 取り消しはできません。"
    ml_help_create = "指定した名前で 新しくマイリストを作成します。"
    ml_help_src = "移動(コピー)元、 あるいは各種の操作対象の、マイリストの名前"
    ml_help_to = "移動(コピー)先のマイリストの名前"
    ml_help_id = "マイリストの指定に、 名前の代わりにそのIDを使います。"
    ml_help_everything = ("show や export と同時に指定すると、"
                          "全てのマイリストの情報をまとめて取得します。")
    ml_help_yes = ("これを指定すると、マイリスト自体の削除や"
                   "マイリスト内の全項目の削除の時に確認しません。")

    ''' 動画ダウンロードコマンドのヘルプメッセージ '''
    nd_description = "動画のいろいろをダウンロードします。"
    nd_help_video_id = ("ダウンロードしたい動画ID。 例: sm12345678 "
                        "テキストファイルも指定できます。 その場合はファイル名の "
                        "先頭に \"+\" をつけます。 例: +\"C:/ids.txt\"")
    nd_help_password = "パスワード"
    nd_help_mail = "メールアドレス"
    nd_help_destination = "ダウンロードしたものを保存する フォルダーへのパス。"
    nd_help_comment = "指定すると、 コメントをダウンロードします。"
    nd_help_video = "指定すると、 動画をダウンロードします。"
    nd_help_thumbnail = "指定すると、 サムネイルをダウンロードします。"
    nd_help_xml = ("指定すると、コメントをXML形式でダウンロードします。"
                   "チャンネル動画の場合は無視されます。")

    nd_help_what = "コマンドの確認用。 引数の内容を書き出すだけです。"
    nd_help_loglevel = "ログ出力の詳細さ。 デフォルトは INFO です。"
    nd_help_nomulti = "指定すると、プログレスバーを複数行で表示しません。"
    nd_help_limit = ("サムネイルとコメントについては同時ダウンロードを、"
                     "動画については1つあたりの分割数をこの数に制限します。標準は 4 です。")
    nd_help_smile = "動画をsmileサーバー(いわゆる従来サーバー)からダウンロードします。"

    input_mail = "メールアドレスを入力してください。"
    input_pass = "パスワードを入力してください(画面には表示されません)。"

    ''' ログに書くメッセージ '''
    nd_start_download = "{count} 件の情報を取りに行きます。: {ids}"
    nd_download_done = "{path} に保存しました。"
    nd_download_video = "({0}/{1}) ID: {2} ({3}) の動画をダウンロードします。"
    nd_download_pict = "({0}/{1}) ID: {2} ({3}) のサムネイルをダウンロードします。"
    nd_download_comment = "({0}/{1}) ID: {2} ({3}) のコメントをダウンロードします。"
    nd_start_dl_video = "{count} 件の動画をダウンロードします。: {ids}"
    nd_start_dl_pict = "{count} 件のサムネイルをダウンロードします。: {ids}"
    nd_start_dl_comment = "{count} 件のコメントをダウンロードします。: {ids}"
    nd_file_name = "{vid}_{name}.{ext}"
    nd_deleted_or_private = "{0} は削除されているか、非公開です。"

    ml_exported = "{0} に出力しました。"
    ml_items_counts = "含まれる項目の数:"
    ml_fetching_mylist_id = "マイリスト: {0} の ID を問い合わせています..."
    ml_showing_mylist = "マイリスト「{0}」の詳細を読み込んでいます..."
    ml_loading_mylists = "マイリストページを読み込んでいます..."
    ml_mylist_found = "ID: {0}, NAME: {1}, DESC: {2}"

    ml_ask_delete_all = "{0} に登録されている以下の全ての項目を削除します。"
    ml_confirmation = "この操作は取り消せません。よろしいですか? (Y/N)"
    ml_answer_yes = "処理を開始します。"
    ml_answer_no = "操作を中止しました。"
    ml_answer_invalid = "Y または N を入力してください。"
    ml_deleted_or_private = "{0[video_id]} {0[title]} は削除されているか非公開です。"

    ml_done_add = "[完了:追加] ({now}/{all}) 動画: {video_id}"
    ml_done_delete = "[完了:削除] ({now}/{all}) 動画: {video_id}"
    ml_done_copy = "[完了:コピー] ({now}/{all}) 動画ID: {video_id}"
    ml_done_move = "[完了:移動] ({now}/{all}) 動画ID: {video_id}"
    ml_done_purge = "[完了:マイリスト削除] 名前: {name}"
    ml_done_create = ("[完了:マイリスト作成] ID: {_id}, 名前:"
                      " {name} (公開: {pub}), 説明文: {desc}")

    ml_will_add = "[作業内容:追加] 対象: {0}, 動画ID: {1}"
    ml_will_delete = "[作業内容:削除] {0} から, 動画ID: {1}"
    ml_will_copy = "[作業内容:コピー] {0} から {1} へ, 動画ID: {2}"
    ml_will_move = "[作業内容:移動] {0} から {1} へ, 動画ID: {2}"
    ml_will_purge = "[作業内容:マイリスト削除] マイリスト「{0}」を完全に削除します。"


class Err:
    """ エラーメッセージ """

    failed_operation = "以下の理由により操作は失敗しました: {desc}"
    waiting_for_permission = "アクセス制限が解除されるのを待っています…"
    name_replaced = ("作成しようとした名前「{0}」は特殊文字を含むため、"
                     "「{1}」に置き換わっています。")
    cant_create = "この名前のマイリストは作成できません。"
    deflist_to_create_or_purge = "とりあえずマイリストは操作の対象にできません。"
    invalid_argument = "引数の型が間違っています。"
    invalid_dirname = "このフォルダー名 {0} はシステム上使えません。他の名前を指定してください。"
    invalid_auth = "メールアドレスとパスワードを入力してください。"
    invalid_videoid = ("[エラー] 指定できる動画IDの形式は以下の通りです。"
                       "http://www.nicovideo.jp/watch/sm1234, "
                       "sm1234, nm1234, so1234,  123456, watch/123456")
    connection_404 = "404エラーです。 ID: {0} (タイトル: {1})"
    keyboard_interrupt = "操作を中断しました。"
    not_specified = "[エラー] {0} を指定してください。"
    videoids_contain_all = "通常の動画IDと * を混ぜないでください。"
    list_names_are_same = "[エラー] 発信元と受信先の名前が同じです。"
    cant_perform_all = "[エラー] このコマンドに * は指定できません。"
    only_perform_all = "[エラー] このコマンドには * のみ指定できます。"
    unexpected_commands = "このコマンドは使用できません。 {0}"
    no_commands = "[エラー] コマンドを指定してください。"
    item_not_contained = "[エラー] 以下の項目は {0} に存在しません: {1}"
    name_ambiguous = ("同名のマイリストが {0}件あります。名前の代わりに"
                      "IDで(--id を使って)指定し直してください。")
    name_ambiguous_detail = ("ID: {id}, 名前: {name}, {publicity},"
                             " 作成日: {since}, 説明文: {description}")
    mylist_not_exist = "[エラー] {0} という名前のマイリストは存在しません。"
    mylist_id_not_exist = "[エラー] {0} というIDのマイリストは存在しません。"
    over_load = "[エラー] {0} にはこれ以上追加できません。"
    remaining = "以下の項目は処理されませんでした: {0}"
    already_exist = "[エラー]すでに存在しています。 ID: {0} (タイトル: {1})"
    known_error = "[エラー] 動画: {0}, コード: {}, 内容: {1}"
    unknown_error_itemid = "[エラー] ({0}/{1}) 動画: {2}, サーバーからの返事: {3}"
    unknown_error = "[エラー] ({0}/{1}) 動画: {2}, サーバーからの返事: {3}"
    failed_to_create = "[エラー] {0} の作成に失敗しました。 サーバーからの返事: {1}"
    failed_to_purge = "[エラー] {0} の削除に失敗しました。 サーバーからの返事: {1}"
    invalid_spec = ("[エラー] {0} は不正です。マイリストの名前"
                    "またはIDは文字列か整数で入力してください。")
    no_items = "[エラー] 指定した動画はいずれもこのマイリストには登録されていません。"

    '''
    APIから返ってくるエラーメッセージ
    {'error': {'code': 'MAXERROR', 'description': 'このマイリストにはもう登録できません'},'status':'fail'}
    {'error': {'code': 'MAXERROR', 'description': 'もうマイリストを作成できません', 'status': 'fail'}
    {'error': {'code': 'EXIST', 'description': 'すでに登録されています'}, 'status': 'fail'}
    {'error': {'code': 'NONEXIST', 'description': 'アイテムが存在しません'}, 'status': 'fail'}

    {'error': {'code': 'COMMANDERROR', 'description': '未定義のコマンドです'}, 'status': 'fail'}
    {'error': {'code': 'PARAMERROR', 'description': 'パラメータエラー'}, 'status': 'fail'}
    {'error': {'code': 'INVALIDTOKEN', 'description': '不正なトークンです'}, 'status': 'fail'}
    {'error': {'code': 'NOAUTH', 'description': '認証できませんでした'}, 'status': 'fail'}

    '''
    # エラーだが対処可能
    MAXERROR = "MAXERROR"
    EXIST = "EXIST"
    NONEXIST = "NONEXIST"

    # コマンドが不正
    COMMANDERROR = "COMMANDERROR"
    PARAMERROR = "PARAMERROR"
    INVALIDTOKEN = "INVALIDTOKEN"
    EXPIRETOKEN = "EXPIRETOKEN"
    NOAUTH = "NOAUTH"
    SECRETUSER = "SECRETUSER"
    INVALIDUSER = "INVALIDUSER"
    INVALIDVIDEO = "INVALIDVIDEO"

    # サーバーが不調
    MAINTENANCE = "MAINTENANCE"
    INTERNAL = "INTERNAL"


class KeyGTI:
    """
    getthumbinfo から取ってきたデータのキーとなる文字列たち。

    DATE ("first_retrieve")について:
        もともとは       2014-07-26T19:27:07+09:00
        という文字列だが 2014-07-26
        として保存しておく。

    MOVIE_TYPE ("movie_type")について:
        "mp4", "flv", "swf" のいずれか。

    URL_PIC ("thumbnail_url")について:
        例えば… http://tn-skr1.smilevideo.jp/smile?i=24093152
    """
    CH_ID           = "ch_id"           # チャンネル動画のみ
    CH_NAME         = "ch_name"         # チャンネル動画のみ
    CH_ICON_URL     = "ch_icon_url"     # チャンネル動画のみ
    COMMENT_NUM     = "comment_num"
    FIRST_RETRIEVE  = "first_retrieve"  # 例えば: 2014-07-26 もともとは: 2014-07-26T19:27:07+09:00
    DELETED         = "deleted"
    DESCRIPTION     = "description"
    EMBEDDABLE      = "embeddable"      # int; 0 or 1
    FILE_NAME       = "file_name"       # 元データには無い
    FILE_SIZE       = "file_size"       # 元データには無い
    LAST_RES_BODY   = "last_res_body"
    LENGTH          = "length"          # str
    LENGTH_SECONDS  = "length_seconds"  # int
    NUM_RES         = "num_res"         # int
    MYLIST_COUNTER  = "mylist_counter"  # int
    MOVIE_TYPE      = "movie_type"      # いずれか: mp4, flv, swf
    NO_LIVE_PLAY    = "no_live_play"    # int; 0 or 1
    SIZE_HIGH       = "size_high"       # int
    SIZE_LOW        = "size_low"        # int
    TAGS            = "tags"
    TAGS_LIST       = "tags_list"       # list
    THUMBNAIL_URL   = "thumbnail_url"   # 例えば: http://tn-skr1.smilevideo.jp/smile?i=24093152
    TITLE           = "title"
    USER_ID         = "user_id"         # int
    USER_NAME       = "user_nickname"
    USER_ICON_URL   = "user_icon_url"
    V_OR_T_ID       = "v_or_t_id"       # 普通は video_id と同一。so動画の時にのみ thread_id の値を入れる。
    VIDEO_ID        = "video_id"
    VIEW_COUNTER    = "view_counter"    # int
    WATCH_URL       = "watch_url"


class KeyDmc:
    IS_DMC          = "DMC_video"       # bool
    FILE_NAME       = "file_name"
    FILE_SIZE       = "file_size"

    VIDEO_ID        = "video_id"
    VIDEO_URL_SM    = "video_url"       # Smile サーバーのほう
    TITLE           = "title"
    THUMBNAIL_URL   = "thumbnail_url"
    ECO             = "eco"             # bool
    MOVIE_TYPE      = "movie_type"
    IS_DELETED      = "is_deleted"      # bool
    IS_PUBLIC       = "is_public"       # bool
    IS_OFFICIAL     = "is_official"     # bool
    IS_PREMIUM      = "is_premium"      # bool
    USER_ID         = "user_id"         # int
    USER_KEY        = "user_key"
    MSG_SERVER      = "ms"
    THREAD_ID       = "thread_id"       # int
    THREAD_KEY      = "thread_key"

    API_URL         = "api_url"
    RECIPE_ID       = "recipe_id"
    CONTENT_ID      = "content_id"
    VIDEO_SRC_IDS   = "video_src_ids"   # list
    AUDIO_SRC_IDS   = "audio_src_ids"   # list
    HEARTBEAT       = "heartbeat"       # int
    TOKEN           = "token"
    SIGNATURE       = "signature"
    AUTH_TYPE       = "auth_type"
    C_K_TIMEOUT     = "content_key_timeout"     # int
    SVC_USER_ID     = "service_user_id"     # USER_ID とたぶん同じ
    PLAYER_ID       = "player_id"
    PRIORITY        = "priority"

    # ↓公式動画にだけある情報
    OPT_THREAD_ID   = "optional_thread_id"
    NEEDS_KEY       = "needs_key"


class KeyGetFlv:
    """ GetFLV を解釈するときのURLパラメーターのキー """
    THREAD_ID       = "thread_id"           # int
    LENGTH          = "l"                   # int
    VIDEO_URL       = "url"                 # str
    MSG_SERVER      = "ms"                  # str
    MSG_SUB         = "ms_sub"              # str
    USER_ID         = "user_id"             # int
    IS_PREMIUM      = "is_premium"          # int
    NICKNAME        = "nickname"            # str
    USER_KEY        = "userkey"             # str

    # ↓公式動画にだけある情報
    OPT_THREAD_ID   = "optional_thread_id"  # int
    NEEDS_KEY       = "needs_key"           # int


class MKey:
    """ マイリスト情報を読み取るときのJSONのキー """
    ID          = "id"
    NAME        = "name"
    IS_PUBLIC   = "is_public"
    PUBLICITY   = "publicity"
    SINCE       = "since"
    DESCRIPTION = "description"
    ITEM_DATA   = "item_data"


class DataKey:
    CHUNK_SIZE      = "CHUNK_SIZE"
    DIVISION        = "DIVISION"
    IS_MULTILINE    = "MULTILINE"
    IS_SMILE        = "SMILE"
    LOGGER          = "LOGGER"
    LOOP            = "LOOP"
    SAVE_DIR        = "SAVE_DIR"
    SESSION         = "SESSION"



class InheritedParser(ArgumentParser):
    """ 文字コードで問題を起こさないために ArgumentParser を上書きするクラス """
    def _read_args_from_files(self, arg_strings):
        # expand arguments referencing files
        new_arg_strings = []
        for arg_string in arg_strings:

            # for regular arguments, just add them back into the list
            if not arg_string or arg_string[0] not in self.fromfile_prefix_chars:
                new_arg_strings.append(arg_string)

            # replace arguments referencing files with the file content
            else:
                try:
                    # ↓文字コードを指定しないとCP932で開いてしまいエラーになる
                    # todo: CP932 でも受け付けるようにする
                    with open(arg_string[1:], encoding="utf-8") as args_file:
                        arg_strings = []
                        for arg_line in args_file.read().splitlines():
                            for arg in self.convert_arg_line_to_args(arg_line):
                                arg_strings.append(arg)
                        arg_strings = self._read_args_from_files(arg_strings)
                        new_arg_strings.extend(arg_strings)
                except OSError:
                    err = sys.exc_info()[1]
                    self.error(str(err))

        # return the modified argument list
        return new_arg_strings
