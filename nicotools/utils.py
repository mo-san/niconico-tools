# coding: utf-8
import logging
import os
import pickle
import re
import requests
import sys
from argparse import ArgumentParser
from getpass import getpass
from os.path import join, expanduser
from pathlib import Path

ALL_ITEM = "*"
LOG_FILE_ND = "nicotools_download.log"
LOG_FILE_ML = "nicotools_mylist.log"
if os.getenv("PYTHON_TEST"):
    os_name = os.getenv("TRAVIS_OS_NAME", os.name)
    version = (os.getenv("TRAVIS_PYTHON_VERSION") or
               os.getenv("PYTHON_VERSION") or
               "_" .join(map(str, sys.version_info[0:3])))
    COOKIE_FILE_NAME = "nicotools_cokkie_{0}_{1}".format(os_name, version)
else:
    COOKIE_FILE_NAME = "nicotools_cookie.pickle"

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
    動画IDが適切なものか確認する。

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

    :param list[str] input_list:
    :rtype: list[str]
    """
    matcher = re.compile(
        """\s*(?:
        {0}|  # 「全て」を指定するときの記号
        (?:
            (?:(?:h?t?tp://)?www\.nicovideo\.jp/)?watch/  # 通常URL
           |(?:h?t?tp://)?nico\.ms/  # 短縮URL
        )?
            ((?:sm|nm|so)?[0-9]+)  # ID本体
        )\s?""".format(re.escape(ALL_ITEM)), re.I + re.X).match

    if "\t" in input_list[0]:
        for line in input_list[1:]:
            if "\t" not in line:
                return []
        input_list = [item.split("\t")[0] for item in input_list]
    else:
        if input_list == [ALL_ITEM]:
            return input_list
        for item in input_list:
            if not matcher(item):
                return []

    return [matcher(item).group(1) or item.strip()
            for item in input_list if matcher(item) or ALL_ITEM in item]


def make_dir(directory):
    """
    保存場所に指定されたフォルダーがない場合にはつくり、その絶対パスを返す。

    :param str | Path directory: フォルダー名
    :rtype: Path
    """
    if isinstance(directory, str):
        directory = Path(directory)
    if directory.suffix:
        return make_dir(directory.parent) / directory.name
    try:
        if not directory.is_dir():
            directory.mkdir(parents=True)
        return directory.resolve()
    except (OSError, FileNotFoundError, NotADirectoryError, PermissionError):
        raise NameError(Err.invalid_dirname.format(directory))


def check_arg(parameters):
    """

    :param dict[str, Object] parameters: パラメーターの名前と値の辞書
    :rtype: None
    """
    for _name, _value in parameters.items():
        if _value is None:
            raise ValueError(Err.not_specified.format(_name))


class URL:
    URL_LogIn  = "https://secure.nicovideo.jp/secure/login?site=niconico"
    URL_Watch  = "http://www.nicovideo.jp/watch/"
    URL_GetFlv = "http://ext.nicovideo.jp/api/getflv/"
    URL_Info   = "http://ext.nicovideo.jp/api/getthumbinfo/"
    URL_Pict   = "http://tn-skr1.smilevideo.jp/smile"
    URL_GetThreadKey = "http://flapi.nicovideo.jp/api/getthreadkey"
    URL_Message_New = "http://nmsg.nicovideo.jp/api.json/"

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

    ''' マイリスト編集コマンドのヘルプメッセージ '''
    ml_default_name = "とりあえずマイリスト"
    ml_default_id = 0
    ml_description = "マイリストを扱います。 add, delete, move, copy の引数には " \
                     "テキストファイルも指定できます。 その場合はファイル名の " \
                     "先頭に \"+\" をつけます。 例: +\"C:/ids.txt\""
    ml_help_group_b = "マイリスト自体を操作する"
    ml_help_group_a = "リスト中の項目を操作する"
    ml_help_add = "指定したIDの動画を マイリストに追加します。"
    ml_help_delete = "そのマイリストから 指定したIDの動画を削除します。" \
                     "動画IDの代わりに * を指定すると、 マイリストを空にします。"
    ml_help_move = "移動元から移動先へと 動画を移動します。"
    ml_help_copy = "コピー元からコピー先へと 動画をコピーします。 " \
                   "動画IDの代わりに * を指定すると、 マイリスト全体をコピーします。"
    ml_help_export = "登録された動画IDのみを改行で区切り、 出力します。" \
                     "名前の代わりに * を指定すると 全マイリストを一覧にします。"
    ml_help_show = "登録された動画の情報をタブ区切り形式で出力します。" \
                   "名前の代わりに * を指定すると マイリスト全体のメタデータを出力します。" \
                   "-ss のように2回指定すると表形式で表示します。"
    ml_help_outfile = "そのファイル名で テキストファイルに出力します。"
    ml_help_purge = "そのマイリスト自体を削除します。 取り消しはできません。"
    ml_help_create = "指定した名前で 新しくマイリストを作成します。"
    ml_help_src = "移動(コピー)元、 あるいは各種の操作対象の、マイリストの名前"
    ml_help_to = "移動(コピー)先のマイリストの名前"
    ml_help_id = "マイリストの指定に、 名前の代わりにそのIDを使います。"
    ml_help_everything = "show や export と同時に指定すると、" \
                         "全てのマイリストの情報をまとめて取得します。"
    ml_help_yes = "これを指定すると、マイリスト自体の削除や" \
                  "マイリスト内の全項目の削除の時に確認しません。"

    ''' 動画ダウンロードコマンドのヘルプメッセージ '''
    nd_description = "ニコニコ動画のデータを ダウンロードします。"
    nd_help_video_id = "ダウンロードしたい動画ID。 例: sm12345678 " \
                       "テキストファイルも指定できます。 その場合はファイル名の " \
                       "先頭に \"+\" をつけます。 例: +\"C:/ids.txt\""
    nd_help_password = "パスワード"
    nd_help_mail = "メールアドレス"
    nd_help_destination = "ダウンロードしたものを保存する フォルダーへのパス。"
    nd_help_outfile = "--getthumbinfo の結果をそのファイル名で テキストファイルに出力します。"
    nd_help_comment = "指定すると、 コメントをダウンロードします。"
    nd_help_video = "指定すると、 動画をダウンロードします。"
    nd_help_thumbnail = "指定すると、 サムネイルをダウンロードします。"
    nd_help_xml = "コメントをXML形式でダウンロードしたい場合に指定します。" \
                  "チャンネル動画の場合は無視されます。"
    nd_help_info = "getthumbinfo API から動画の情報のみを ダウンロードします。"
    nd_help_what = "コマンドの確認用。 引数の内容を書き出すだけです。"
    nd_help_loglevel = "ログ出力の詳細さ。 デフォルトは INFO です。"

    input_mail = "メールアドレスを入力してください。"
    input_pass = "パスワードを入力してください(画面には表示されません)。"

    ''' ログに書くメッセージ '''
    nd_start_download = "{0} 件の動画の情報を取りに行きます。"
    nd_download_done = "{0} に保存しました。"
    nd_download_video = "({0}/{1}) ID: {2} (タイトル:{3}) の動画をダウンロードします。"
    nd_download_pict = "({0}/{1}) ID: {2} (タイトル:{3}) のサムネイルをダウンロードします。"
    nd_download_comment = "({0}/{1}) ID: {2} (タイトル:{3}) のコメントをダウンロードします。"
    nd_start_dl_video = "{0} 件の動画をダウンロードします。"
    nd_start_dl_pict = "{0} 件のサムネイルをダウンロードします。"
    nd_start_dl_comment = "{0} 件のコメントをダウンロードします。"
    nd_file_name = "{0}_{1}.{2}"
    nd_video_url_is = "{0} の動画URL: {1}"
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

    ml_done_add = "[完了:追加] ({0}/{1}) 動画: {2}"
    ml_done_delete = "[完了:削除] ({0}/{1}) 動画: {2}"
    ml_done_copy = "[完了:コピー] ({0}/{1}) 動画ID: {2}"
    ml_done_move = "[完了:移動] ({0}/{1}) 動画ID: {2}"
    ml_done_purge = "[完了:マイリスト削除] 名前: {0}"
    ml_done_create = "[完了:マイリスト作成] ID: {0}, 名前: {1} (公開: {2}), 説明文: {3}"

    ml_will_add = "[作業内容:追加] 対象: {0}, 動画ID: {1}"
    ml_will_delete = "[作業内容:削除] {0} から, 動画ID: {1}"
    ml_will_copyormove = "[作業内容:{0}] {1} から {2} へ, 動画ID: {3}"
    ml_will_purge = "[作業内容:マイリスト削除] マイリスト「{0}」を完全に削除します。"


class Err:
    """ エラーメッセージ """

    waiting_for_permission = "アクセス制限が解除されるのを待っています…"
    name_replaced = "作成しようとした名前「{0}」は特殊文字を含むため、" \
                    "「{1}」に置き換わっています。"
    cant_create = "この名前のマイリストは作成できません。"
    deflist_to_create_or_purge = "とりあえずマイリストは操作の対象にできません。"
    not_installed = "{0} がインストールされていないため実行できません。"
    invalid_dirname = "このフォルダー名 {0} はシステム上使えません。他の名前を指定してください。"
    invalid_auth = "メールアドレスとパスワードを入力してください。"
    invalid_videoid = "[エラー] 指定できる動画IDの形式は以下の通りです。" \
                      "http://www.nicovideo.jp/watch/sm1234," \
                      " sm1234, nm1234, so1234, 123456, watch/123456"
    connection_404 = "404エラーです。 ID: {0} (タイトル: {1})"
    connection_timeout = "接続が時間切れになりました。 ID: {0} (タイトル: {1})"
    keyboard_interrupt = "操作を中断しました。"
    not_specified = "[エラー] {0} を指定してください。"
    videoid_contains_all = "通常の動画IDと * を混ぜないでください。"
    list_names_are_same = "[エラー] 発信元と受信先の名前が同じです。"
    cant_move_to_deflist = "[エラー] とりあえずマイリストには移動もコピーもできません。"
    cant_perform_all = "[エラー] このコマンドに * は指定できません。"
    only_perform_all = "[エラー] このコマンドには * のみ指定できます。"
    no_commands = "[エラー] コマンドを指定してください。"
    item_not_contained = "[エラー] 以下の項目は {0} に存在しません: {1}"
    name_ambiguous = "同名のマイリストが {0}件あります。名前の代わりに" \
                     "IDで(--id を使って)指定し直してください。"
    name_ambiguous_detail = "ID: {id}, 名前: {name}, {publicity}," \
                            " 作成日: {since}, 説明文: {description}"
    mylist_not_exist = "[エラー] {0} という名前のマイリストは存在しません。"
    mylist_id_not_exist = "[エラー] {0} というIDのマイリストは存在しません。"
    over_load = "[エラー] {0} にはこれ以上追加できません。"
    remaining = "以下の項目は処理されませんでした: {0}"
    already_exist = "[エラー]すでに存在しています。 ID: {0} (タイトル: {1})"
    known_error = "[エラー] 動画: {0}, コード: {}, 内容: {1}"
    unknown_error_itemid = "[エラー] ({0}/{1}) 動画: {2}, サーバーからの返事: {3}"
    unknown_error = "[エラー] ({0}/{1}) 動画: {2}, サーバーからの返事: {3}"
    failed_to_create = "[エラー] {0} の作成に失敗しました。 サーバーからの返事: {0}"
    failed_to_purge = "[エラー] {0} の削除に失敗しました。 サーバーからの返事: {1}"
    invalid_spec = "[エラー] {0} は不正です。マイリストの名前またはIDは" \
                   "文字列か整数で入力してください。"
    no_items = "[エラー] 動画が1件も登録されていません。"

    '''
    APIから返ってくるエラーメッセージ
    {'error': {'code': 'MAXERROR', 'description': 'このマイリストにはもう登録できません'},'status':'fail'}
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


class LogIn:
    def __init__(self, mail=None, password=None, logger=None, session=None):
        """
        :param str | None mail: メールアドレス
        :param str | None password: パスワード
        :param T <= logging.logger | None logger:
        :param requests.Session | None session: セッションオブジェクト
        """
        self.logger = self.get_logger(logger)
        self.is_login = False
        if not (session or mail or password):
            self.session = self.get_session()
        elif session and not (mail or password):
            self.session = session
        else:
            _auth = self.ask_credentials(mail=mail, password=password)
            self.session = self.get_session(_auth, force_login=True)
        self.token = self.get_token(self.session)

    def get_logger(self, logger):
        """

        :param T <= logging.logger logger:
        :rtype: T <= logging.logger
        """
        if not (logger and hasattr(logger, "handlers")):
            return NTLogger()
        else:
            return logger

    def get_session(self, auth=None, force_login=False):
        """
        クッキーを読み込み、必要ならばログインし、そのセッションを返す。

        :param dict[str, str] | None auth:
        :param bool force_login: ログインするかどうか。クッキーが無い or 異常な場合にTrueにする。
        :rtype: requests.Session
        """

        session = requests.session()
        if force_login:
            res = session.post(URL.URL_LogIn, params=auth)
            if self._we_are_logged_in(res.text):
                self.save_cookies(session.cookies)
                self.is_login = True
            else:
                return self.get_session(self.ask_credentials(), force_login=True)
        else:
            cook = self.load_cookies()
            if cook:
                session.cookies = cook
        return session

    def _we_are_logged_in(self, response):
        """

        :param str response:
        :rtype: bool
        """
        # 成功したとき
        if "<title>niconico</title>" in response:
            return True
        # 失敗したとき
        elif "ログイン - niconico</title>" in response:
            print(Err.invalid_auth)
            return False
        else:
            print("Couldn't determine whether we could log in."
                  " This is the returned HTML:\n{0}".format(response))
            return False

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
            session = self.get_session(self.ask_credentials(), force_login=True)
            return self.get_token(session)

    @classmethod
    def ask_credentials(cls, mail=None, password=None):
        """
        メールアドレスとパスワードをユーザーに求める。

        :param str mail: メールアドレス。
        :param str password: パスワード
        :rtype: dict[str, str]
        """
        un, pw = mail, password
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
            exit(Err.keyboard_interrupt)
        return {
            "mail_tel": un,
            "password": pw
        }

    @classmethod
    def save_cookies(cls, requests_cookiejar, file_name=COOKIE_FILE_NAME):
        """
        クッキーを保存する。保存場所は基本的にユーザーのホームディレクトリ。

        :param requests.cookies.RequestsCookieJar requests_cookiejar:
        :param str file_name:
        :rtype: None
        """
        with open(join(expanduser("~"), file_name), "wb") as fd:
            pickle.dump(requests_cookiejar, fd)

    @classmethod
    def load_cookies(cls, file_name=COOKIE_FILE_NAME):
        """
        クッキーを読み込む。

        :param str file_name:
        :rtype: requests.cookies.RequestsCookieJar | None
        """
        try:
            with open(join(expanduser("~"), file_name), "rb") as fd:
                return pickle.load(fd)
        except (FileNotFoundError, EOFError):
            return None


class NTLogger(logging.Logger):
    def __init__(self, file_name=LOG_FILE_ND, name=__name__, log_level=logging.INFO):
        """
        :param str | Path | None file_name:
        :param str name:
        :param str | int log_level:
        """
        if isinstance(log_level, (str, int)):
            log_level = logging.getLevelName(log_level)
        else:
            raise ValueError("Invalid Logging Level. You Entered: %s", log_level)

        self.enco = get_encoding()
        self.log_level = log_level
        formatter = logging.Formatter("[{asctime}|{levelname: ^7}]\t{message}", style="{")

        logging.Logger.__init__(self, name, log_level)
        self.logger = logging.getLogger(name=name)

        # 標準出力用ハンドラー
        log_stdout = logging.StreamHandler(sys.stdout)
        log_stdout.setLevel(log_level)
        log_stdout.setFormatter(formatter)
        self.addHandler(log_stdout)

        if file_name is not None:
            # ファイル書き込み用ハンドラー
            if isinstance(file_name, Path):
                log_file = logging.FileHandler(
                    filename=str(file_name), encoding="utf-8")
            else:
                log_file = logging.FileHandler(encoding="utf-8",
                    filename=join(expanduser("~"), file_name))
            log_file.setLevel(log_level)
            log_file.setFormatter(formatter)
            self.addHandler(log_file)

    def forwarding(self, level, msg, *args, **kwargs):
        _msg = msg.encode(self.enco, BACKSLASH).decode(self.enco)
        _args = tuple([item.encode(self.enco, BACKSLASH).decode(self.enco)
                       if isinstance(item, str) else item for item in args[0]])
        self._log(level, _msg, _args, **kwargs)

    def debug(self, msg, *args, **kwargs): self.forwarding(logging.DEBUG, msg, args, **kwargs)

    def info(self, msg, *args, **kwargs): self.forwarding(logging.INFO, msg, args, **kwargs)

    def warning(self, msg, *args, **kwargs): self.forwarding(logging.WARNING, msg, args, **kwargs)

    def error(self, msg, *args, **kwargs): self.forwarding(logging.ERROR, msg, args, **kwargs)

    def critical(self, msg, *args, **kwargs): self.forwarding(logging.CRITICAL, msg, args, **kwargs)


class Key:
    """
    データの集まりのキーとなる文字列たち。

    DATE ("first_retrieve"):
        例えば…        2014-07-26
        もともとは…    2014-07-26T19:27:07+09:00

    MOVIE_TYPE ("movie_type"):
        one of "mp4", "flv" and "swf"
    URL_PIC ("thumbnail_url"):
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
    FILE_NAME       = "file_name"
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


class KeyGetFlv:
    THREAD_ID       = "thread_id"
    LENGTH          = "l"
    VIDEO_URL       = "url"
    MSG_SERVER      = "ms"
    MSG_SUB  = "ms_sub"
    USER_ID         = "user_id"
    IS_PREMIUM      = "is_premium"
    NICKNAME        = "nickname"
    USER_KEY        = "userkey"

    OPT_THREAD_ID   = "optional_thread_id"
    NEEDS_KEY       = "needs_key"


class MKey:
    ID = "id"
    NAME = "name"
    IS_PUBLIC = "is_public"
    PUBLICITY = "publicity"
    SINCE = "since"
    DESCRIPTION = "description"
    ITEM_DATA = "item_data"


class InheritedParser(ArgumentParser):
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
