# coding: UTF-8
import html
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree
try:
    from prettytable import PrettyTable
except ImportError:
    PrettyTable = False

from nicotools import utils
from nicotools.utils import Msg, Err, URL, KeyGTI, MKey, MylistNotFoundError, MylistAPIError

# TODO: purifyコマンド


class NicoMyList(utils.Canopy):
    WHY_DELETED = {
        "0": "公開",
        "1": "削除",
        "2": "運営による削除",
        "3": "権利者による削除",
        "8": "非公開",
    }

    def __init__(self, mail=None, password=None, logger=None):
        """
        使い方:

            MYLISTに動画を追加する:
                mylist MYLIST --add sm1 sm2 sm3
            IDを一行ごとに書いたファイルからMYLISTに動画を追加する:
                mylist MYLIST --add +C:/Users/Me/Desktop/ids.txt
            MYLISTをそのIDで指定する:
                mylist 12345678 --id --add sm1 sm2 sm3
            MYLISTから動画を削除する:
                mylist MYLIST --delete sm1 sm2 sm3
            MYLIST の中のもの全てを削除する:
                mylist MYLIST --delete *
            MYLIST の中のもの全てを削除する(確認なし):
                mylist MYLIST --delete * --yes
            MYLIST の中の動画を --to に移す:
                mylist MYLIST --to なんとかかんとか --move sm1 sm2 sm3
            MYLIST の中のもの全てを --to に移す:
                mylist MYLIST --to なんとかかんとか --move *
            MYLIST の中の動画を --to に写す:
                mylist MYLIST --to なんとかかんとか --copy sm1 sm2 sm3
            MYLIST の中のもの全てを --to に写す:
                mylist MYLIST --to なんとかかんとか --copy *

            特定のマイリストの中身を一覧にする:
                mylist MYLIST --export
            全てのマイリストの名前を一覧にする:
                mylist * --show
            全てのマイリストの中身を一覧にする(タブ区切り):
                mylist * --show --everything --out D:/Downloads/all.txt
            全てのマイリストの中身を一覧にする(表形式):
                mylist * --show --show --everything --out D:/Downloads/all.txt
            全てのマイリストの中身を一覧にする:
                mylist * --export --everything --out D:/Downloads/all.txt
            マイリスト全体のメタデータを一覧にする:
                mylist * --export --out D:/Downloads/all.txt
            指定したマイリストに登録されたIDをファイルに出力する:
                mylist MYLIST --export --out C:/Users/Me/Desktop/file.txt
            指定した名前で新しいマイリストを作る:
                mylist MYLIST --create
            指定した名前のマイリストを削除する:
                mylist MYLIST --purge
            指定した名前のマイリストを削除する(確認なし):
                mylist MYLIST --purge --yes

        他のコマンド:
            それぞれにはログインに必要な情報を与えられる:
                mylist MYLIST --add sm9 --mail <メールアドレス> --pass <パスワード>

            引数がどの様に解釈されるかを確認したいとき (確認するだけで、プログラムは実行しません):
                mylist --export --id 12345678 --out ../file.txt --what

            ログ出力の詳細さを変える:
                mylist --loglevel WARNING  # エラー以外表示しない

            引用符を含むマイリスト名の指定方法:
                * 「"マイ'リ'スト"」 を指定するには 「"\"マイ'リ'スト\""」
                * 「'マイ"リ"スト'」 を指定するには 「"'マイ\"リ\"スト'"」

        :param str | None mail: メールアドレス
        :param str | None password: パスワードの組
        :param NTLogger logger:
        :rtype: None
        """
        super().__init__(logger=logger)
        __login = utils.LogIn(mail=mail, password=password)
        self.session = __login.session
        self.token = __login.token
        self.mylists = self.get_mylists_info()

    @classmethod
    def _confirmation(cls, mode, list_name, contents_to_be_deleted=None):
        """
        マイリスト自体を削除したり、マイリスト中の全てを削除する場合にユーザーの確認を取る。

        :param str mode: "purge" or "delete"
        :param str list_name: マイリスト名
        :param list[str] | None contents_to_be_deleted:
        :rtype: bool
        """
        assert mode.lower() in ("purge", "delete")
        if mode == "purge":
            print(Msg.ml_will_purge % list_name)
        else:
            print(Msg.ml_ask_delete_all.format(list_name))
            print("{}".format(contents_to_be_deleted))

        print(Msg.ml_confirmation)
        while True:
            reaction = input()
            if reaction.upper() == "Y":
                print(Msg.ml_answer_yes)
                return True
            elif reaction.upper() == "N":
                return False
            else:
                print(Msg.ml_answer_invalid)
                continue

    def _should_continue(self, res, **kwargs):
        """
        次の項目に進んでよいかを判断する。

        致命的なエラーならば False を返し、差し支えないエラーならば True を返す。

        :param dict[str, dict|str] res: APIからの返事
        :param str video_id: 動画ID
        :param str list_name: マイリスト名
        :param int count_now: 現在の番号
        :param int count_whole: 全体の件数
        :rtype: bool
        """
        video_id = kwargs.get("video_id")  # type: str
        list_name = kwargs.get("list_name")  # type: str
        count_now = kwargs.get("count_now")  # type: int
        count_whole = kwargs.get("count_whole")  # type: int

        if res["status"].lower() == "ok":
            return True
        try:
            code = res["error"]["code"]
            description = res["error"]["description"]
        except KeyError:
            self.logger.error(Err.unknown_error_itemid,
                count_now, count_whole, video_id, res)
            raise
        else:
            if code == Err.INTERNAL or code == Err.MAINTENANCE:
                self.logger.error(Err.known_error, video_id, code, description)
                raise MylistAPIError(code=code, msg=description)
            elif code == Err.MAXERROR:
                msg = Err.over_load.format(list_name)
                self.logger.error(msg)
                raise MylistAPIError(code=Err.MAXERROR, msg=msg)
            elif code == Err.EXIST:
                title = self.get_title(video_id)
                msg = Err.already_exist.format(video_id, title)
                self.logger.error(msg)
                raise MylistAPIError(code=Err.EXIST, msg=msg, ok=True)
            elif code == Err.NONEXIST:
                msg = Err.item_not_contained % (list_name, video_id)
                self.logger.error(msg)
                raise MylistAPIError(code=Err.NONEXIST, msg=msg, ok=True)
            else:
                self.logger.error(Err.known_error, video_id, code, description)
                raise MylistAPIError(code=code, msg=description, ok=True)

    def get_mylists_info(self):
        """
        とりあえずマイリスト以外の全てのマイリストのメタ情報を得る。

        APIからの返事:
            {"mylistgroup": [
                {"id": ..., "name": ..., "description": ..., "public": ..., "create_time": ...},
                {"id": ..., "name": ..., "description": ..., "public": ..., "create_time": ...},
                {"id": ..., "name": ..., "description": ..., "public": ..., "create_time": ...},
            ]}

        返す辞書:
            {
            1: {"id": ..., "name": ..., "is_public": ..., "publicity": ...,
                "since": ..., "description": ...},
            2: {"id": ..., "name": ..., "is_public": ..., "publicity": ...,
                "since": ..., "description": ...},
            3: {"id": ..., "name": ..., "is_public": ..., "publicity": ...,
                "since": ..., "description": ...},
            }

        :rtype: dict[int, dict[str, int | str | bool]]
        """
        jsonliketext = self.session.get(URL.URL_ListAll).text
        self.logger.debug("Response All Mylists: %s", jsonliketext)
        jtext = json.loads(jsonliketext)

        candidate = {}

        for item in jtext["mylistgroup"]:
            name = html.unescape(item["name"].replace(r"\/", "/"))
            description = html.unescape(item["description"]
                                        .strip()
                                        .replace("\r", "").replace("\n", " ")
                                        .replace(r"\/", "/"))
            publicity = "公開" if item["public"] == "1" else "非公開"

            candidate[int(item["id"])] = {
                MKey.ID: int(item["id"]),
                MKey.NAME: name,
                MKey.IS_PUBLIC: item["public"] == "1",  # type: bool
                MKey.PUBLICITY: publicity,
                MKey.SINCE: self._get_jst_from_utime(item["create_time"]),  # type: str
                MKey.DESCRIPTION: description,
            }
        self.logger.debug("Mylists infos: %s", candidate)
        return candidate

    @classmethod
    def _get_jst_from_utime(cls, timestamp):
        """
        UNIXTIME を日本標準時に変換する。末尾の'+09:00'は取り除く。

        1471084020 -> '2016-08-13 19:27:00'

        :param int timestamp: UNIXTIMEの数字
        :rtype: str
        """
        return str(datetime.fromtimestamp(timestamp, timezone(timedelta(hours=+9))))[:-6]

    # @classmethod
    # def _get_utime(cls):
    #     """
    #     現在の UNIXTIME を返す。
    #
    #     '2016-08-13 19:27:00' -> 1471084020
    #
    #     :rtype: int
    #     """
    #     return datetime.now().timestamp()

    def get_list_id(self, search_for):
        """
        指定されたIDまたは名前を持つマイリストのIDを得る。

        :param int | str search_for: マイリスト名またはマイリストID
        :rtype: dict[str, int | str | dict]
        """
        def composer(_err=False, _id=None, _name=None, _msg=None, _dic=None):
            res = {"error": _err, "list_id": _id, "list_name": _name,
                   "err_msg": _msg, "err_dic": _dic}
            self.logger.debug("List IDs: %s", res)
            return res

        if search_for == utils.DEFAULT_NAME or search_for == utils.DEFAULT_ID:
            return composer(_id=utils.DEFAULT_ID, _name=utils.DEFAULT_NAME)

        elif isinstance(search_for, int):
            value = self.mylists.get(search_for)  # type: dict
            if value is None:
                # 存在しなかったとき
                return composer(_err=True,
                                _msg=Err.mylist_id_not_exist.format(search_for))
            else:
                return composer(_id=search_for, _name=value["name"])

        elif isinstance(search_for, str):
            value = {l_id: info for l_id, info in self.mylists.items()
                     if info["name"] == search_for}
            if len(value) == 1:
                return composer(_id=list(value)[0], _name=search_for)
            elif len(value) == 0:
                # 存在しなかったとき
                return composer(_err=True,
                                _msg=Err.mylist_not_exist.format(search_for))
            else:
                # 同じ名前のマイリストが複数あったとき
                return composer(_err=True, _dic=value,
                                _msg=Err.name_ambiguous.format(len(value)))
        else:
            return composer(_err=True, _msg=Err.invalid_spec.format(search_for))

    def _get_list_id(self, search_for):
        """
        指定されたIDまたは名前を持つマイリストのIDを得る。

        :param int | str search_for: マイリスト名またはマイリストID
        :rtype: (int, str)
        """
        utils.check_arg(locals())
        result = self.get_list_id(search_for)

        if result.get("error") is True:
            if result.get("err_dic"):
                # 同じ名前のマイリストが複数あったとき
                self.logger.error(result.get("err_msg"))
                for single in result.get("err_dic").values():
                    print(Err.name_ambiguous_detail.format(**single), file=sys.stderr)
                sys.exit()
            else:
                # 存在しなかったとき
                raise MylistNotFoundError(result.get("err_msg"))
        else:
            list_id = result["list_id"]
            list_name = result["list_name"]
            self.logger.debug("List_id: %s, List_name: %s", list_id, list_name)
            return list_id, list_name

    def get_item_ids(self, list_id, *videoids):
        """
        そのマイリストに含まれている item_id の一覧を返す。

        全て、あるいは指定した(中での生存している)動画の Item IDを返す。
        item_id は sm1234 などの動画IDとは異なるもので、
        マイリスト間の移動や複製に必要となる。

        :param int | str list_id: マイリストの名前またはID
        :param list[str] | tuple[str] videoids:
        :rtype: dict[str, str]
        """
        utils.check_arg(locals())
        list_id, _ = self._get_list_id(list_id)

        # *videoids が要素数1のタプル ("*") or
        # *videoids が要素数0のタプル(即ち未指定) -> 全体モード
        # 何かしら指定されているなら -> 個別モード
        if len(videoids) == 0 or (len(videoids) == 1 and utils.ALL_ITEM in videoids):
            whole = True
        else:
            whole = False
        self.logger.debug("Is in whole mode?: %s", whole)

        if list_id == utils.DEFAULT_ID:
            jtext = json.loads(self.session.get(URL.URL_ListDef).text)
        else:
            jtext = json.loads(self.session.get(URL.URL_ListOne,
                                                params={"group_id": list_id}).text)
        self.logger.debug("Response: %s", jtext)

        results = {}
        for item in jtext["mylistitem"]:
            data = item["item_data"]
            # 0以外のは削除されているか非公開
            if not whole:
                if not "0" == data["deleted"]:
                    self.logger.debug(Msg.ml_deleted_or_private, data)
                    continue

            if whole or data["video_id"] in videoids:
                results.update({data["video_id"]: item["item_id"]})
        return results

    def get_title(self, video_id):
        """
        getthumbinfo APIから、タイトルをもらってくる

        :param str video_id: 動画ID
        :rtype:str
        """
        utils.check_arg(locals())
        document = ElementTree.fromstring(self.session.get(URL.URL_Info + video_id).text)
        # 「status="ok"」 なら動画は生存 / 存在しない動画には「status="fail"」が返る
        if not document.get("status").lower() == "ok":
            self.logger.error(Msg.nd_deleted_or_private, video_id)
            return ""
        else:
            return html.unescape(document[0].find("title").text)

    def get_response(self, mode, **kwargs):
        """
        マイリストAPIにアクセスして結果を受け取る。

        * bool is_def:
            (add, copy, move, delete) 「とりあえずマイリスト」が対象であれば True
        * bool is_public:
            (add) 公開マイリストであれば True
        * int  list_id:
            (purge) マイリストのID
        * int  list_id_to:
            (add, copy, move) マイリストのID
        * int  list_id_from:
            (copy, move, delete) マイリストのID
        * str  video_id:
            (add, copy, move, delete) 動画ID
        * str  item_id:
            (add, copy, move, delete) 動画の item ID
        * str  mylist_name:
            (create) マイリストの名前
        * str  description:
            (add, create) 動画またはマイリストの説明文
        * int default_sort:
            (create) 並び順
        * int icon_id:
            (create) マイリストのアイコンを表す数字

        :param str mode: "add", "copy", "move", "delete", "purge", "create" のいずれか
        :rtype: dict
        """
        utils.check_arg(locals())
        assert mode.lower() in ("add", "delete", "copy", "move", "purge", "create")

        self.logger.debug("Query components: %s", kwargs)
        to_def = kwargs.get("to_def")  # type: bool
        from_def = kwargs.get("from_def")  # type: bool
        is_public = kwargs.get("is_public")  # type: bool
        list_id = kwargs.get("list_id")  # type: int
        list_id_to = kwargs.get("list_id_to")  # type: int
        list_id_from = kwargs.get("list_id_from")  # type: int
        video_id = kwargs.get("video_id")  # type: str
        item_id = kwargs.get("item_id")  # type: str
        mylist_name = kwargs.get("mylist_name")  # type: str
        description = kwargs.get("description", "")  # type: str
        default_sort = kwargs.get("default_sort", 0)  # type: int
        icon_id = kwargs.get("icon_id", 0)  # type: int

        if video_id and not isinstance(video_id, list):
            video_id = [video_id]
        if item_id and not isinstance(item_id, list):
            item_id = [item_id]

        if "move" == mode and to_def:
            # とりあえずマイリストには直接移動できないので、追加と削除を別でやる。
            self.get_response("add", to_def=True, video_id=video_id,
                              description=description)
            return self.get_response("delete", from_def=True, item_id=item_id)

        if "add" == mode or ("copy" == mode and to_def):
            payload = {
                "item_type"      : 0,
                "item_id"        : video_id,
                "description"    : description,
                "token"          : self.token
            }
            if to_def:
                url = URL.URL_AddDef
            else:
                payload.update({"group_id": str(list_id_to)})
                url = URL.URL_AddItem
        elif "delete" == mode:
            payload = {
                "id_list[0][]": item_id,
                "token"       : self.token
            }
            if from_def:
                url = URL.URL_DeleteDef
            else:
                payload.update({"group_id": str(list_id_from)})
                url = URL.URL_DeleteItem
        elif "copy" == mode:
            payload = {
                "target_group_id": str(list_id_to),
                "id_list[0][]"   : item_id,
                "token"          : self.token
            }
            if from_def:
                url = URL.URL_CopyDef
            else:
                payload.update({"group_id": str(list_id_from)})
                url = URL.URL_CopyItem
        elif "move" == mode:
            payload = {
                "target_group_id": str(list_id_to),
                "id_list[0][]"   : item_id,
                "token"          : self.token
            }
            if from_def:
                url = URL.URL_MoveDef
            else:
                payload.update({"group_id": str(list_id_from)})
                url = URL.URL_MoveItem
        elif "purge" == mode:
            payload = {
                "group_id"       : str(list_id),
                "token"          : self.token
            }
            url = URL.URL_PurgeList
        else:  # create
            payload = {
                "name"           : mylist_name,
                "description"    : description,
                "public"         : int(is_public),
                "default_sort"   : default_sort,
                "icon_id"        : icon_id,
                "token"          : self.token
            }
            url = URL.URL_AddMyList
        self.logger.debug("URL: %s", url)
        self.logger.debug("Query to post: %s", payload)
        res = self.session.get(url, params=payload).text
        self.logger.debug("Response: %s", res)
        return json.loads(res)

    def create_mylist(self, mylist_name, is_public=False, description=""):
        """
        mylist_name を名前に持つマイリストを作る。

        :param str mylist_name: マイリストの名前
        :param bool is_public: True なら公開マイリストになる
        :param str description: マイリストの説明文
        :rtype: bool
        """
        utils.check_arg(locals())
        if utils.ALL_ITEM == mylist_name:
            raise utils.MylistError(Err.cant_perform_all)
        if mylist_name == "" or mylist_name == utils.DEFAULT_NAME:
            raise utils.MylistError(Err.cant_create)
        res = self.get_response("create", is_public=is_public,
                                mylist_name=mylist_name, description=description)
        if res["status"] != "ok":
            self.logger.error(Err.failed_to_create, mylist_name, res)
            return False
        else:
            self.mylists = self.get_mylists_info()
            item = self.mylists[res[MKey.ID]]
            self.logger.info(Msg.ml_done_create,
                res[MKey.ID], item[MKey.NAME],
                item[MKey.PUBLICITY], item[MKey.DESCRIPTION])
            if mylist_name != item[MKey.NAME]:
                self.logger.info(Err.name_replaced, mylist_name, item[MKey.NAME])
            return True

    def purge_mylist(self, list_id, confident=False):
        """
        指定したマイリストを削除する。

        :param int | str list_id: マイリストの名前またはID
        :param bool confident:
        :rtype: bool
        """
        utils.check_arg(locals())
        if utils.ALL_ITEM == list_id:
            raise utils.MylistError(Err.cant_perform_all)
        list_id, list_name = self._get_list_id(list_id)

        if list_id == utils.DEFAULT_ID:
            raise utils.MylistError(Err.deflist_to_create_or_purge)
        if not confident and not self._confirmation("purge", list_name):
            print(Msg.ml_answer_no)
            return False

        res = self.get_response("purge", list_id=list_id)
        if res["status"] != "ok":
            self.logger.error(Err.failed_to_purge, list_name, res["status"])
            return False
        else:
            self.logger.info(Msg.ml_done_purge, list_name)
            del self.mylists[list_id]
            return True

    def add(self, list_id, *videoids):
        """
        そのマイリストに、 指定した動画を追加する。

        :param int | str list_id: マイリストの名前またはID
        :param str videoids: 追加する動画ID
        :rtype: bool
        """
        utils.check_arg(locals())
        if utils.ALL_ITEM == list_id or utils.ALL_ITEM in videoids:
            raise utils.MylistError(Err.cant_perform_all)
        list_id, list_name = self._get_list_id(list_id)

        to_def = (list_id == utils.DEFAULT_ID)
        self.logger.info(Msg.ml_will_add, list_name, list(videoids))

        _done = []
        for _counter, vd_id in enumerate(videoids):
            _counter += 1
            res = self.get_response("add", to_def=to_def, list_id_to=list_id, video_id=vd_id)

            try:
                self._should_continue(res, video_id=vd_id, list_name=list_name,
                                      count_now=_counter, count_whole=len(videoids))
                self.logger.info(Msg.ml_done_add, _counter, len(videoids), vd_id)
                _done.append(vd_id)
                time.sleep(0.5)
            except MylistAPIError as error:
                if error.ok:
                    return True
                else:
                    # エラーが起きた場合
                    self.logger.error(Err.remaining,
                        [i for i in videoids if i not in _done and i != utils.ALL_ITEM])
                    raise
        return True

    def copy(self, list_id_from, list_id_to, *videoids):
        """
        そのマイリストに、 指定した動画をコピーする。

        :param int | str list_id_from: 移動元のIDまたは名前
        :param int | str list_id_to: 移動先のIDまたは名前
        :param str videoids: 動画ID
        :rtype: bool
        """
        utils.check_arg(locals())
        if len(videoids) > 1 and utils.ALL_ITEM in videoids:
            raise utils.MylistError(Err.videoids_contain_all)
        list_id_from, list_name_from = self._get_list_id(list_id_from)
        list_id_to, list_name_to = self._get_list_id(list_id_to)
        if list_id_from == list_id_to:
            raise utils.MylistError(Err.list_names_are_same)

        to_def = (list_id_to == utils.DEFAULT_ID)
        from_def = (list_id_from == utils.DEFAULT_ID)

        item_ids = self.get_item_ids(list_id_from, *videoids)
        if len(item_ids) == 0:
            self.logger.error(Err.no_items)
            return False
        if utils.ALL_ITEM not in videoids:
            item_ids = {vd_id: item_ids[vd_id] for vd_id in videoids if vd_id in item_ids}

            # 指定したものが含まれているかの確認
            excluded = [vd_id for vd_id in videoids if vd_id not in item_ids]
            if len(excluded) > 0:
                self.logger.error(Err.item_not_contained, list_name_from, excluded)

        self.logger.info(Msg.ml_will_copy,
            list_name_from, list_name_to, sorted(item_ids.keys()))

        _done = []
        for _counter, vd_id in enumerate(item_ids):
            _counter += 1
            res = self.get_response("copy", item_id=item_ids[vd_id], video_id=vd_id,
                                    to_def=to_def, from_def=from_def,
                                    list_id_to=list_id_to, list_id_from=list_id_from)
            try:
                self._should_continue(res, video_id=vd_id, list_name=list_name_to,
                                      count_now=_counter, count_whole=len(item_ids))
                self.logger.info(Msg.ml_done_copy, _counter, len(item_ids), vd_id)
                _done.append(vd_id)
            except MylistAPIError as error:
                if error.ok:
                    return True
                else:
                    # エラーが起きた場合
                    self.logger.error(Err.remaining,
                        [i for i in videoids if i not in _done and i != utils.ALL_ITEM])
                    raise
        return True

    def move(self, list_id_from, list_id_to, *videoids):
        """
        そのマイリストに、 指定した動画を移動する。

        :param int | str list_id_from: 移動元のIDまたは名前
        :param int | str list_id_to: 移動先のIDまたは名前
        :param str videoids: 動画ID
        :rtype: bool
        """
        utils.check_arg(locals())
        if len(videoids) > 1 and utils.ALL_ITEM in videoids:
            raise utils.MylistError(Err.videoids_contain_all)
        list_id_from, list_name_from = self._get_list_id(list_id_from)
        list_id_to, list_name_to = self._get_list_id(list_id_to)

        to_def = (list_id_to == utils.DEFAULT_ID)
        from_def = (list_id_from == utils.DEFAULT_ID)

        item_ids = self.get_item_ids(list_id_from, *videoids)
        if len(item_ids) == 0:
            self.logger.error(Err.no_items)
            return False
        if utils.ALL_ITEM not in videoids:
            item_ids = {vd_id: item_ids[vd_id] for vd_id in videoids if vd_id in item_ids}

            # 指定したものが含まれているかの確認
            excluded = [vd_id for vd_id in videoids if vd_id not in item_ids]
            if len(excluded) > 0:
                self.logger.error(Err.item_not_contained, list_name_from, excluded)

        self.logger.info(Msg.ml_will_move,
            list_name_from, list_name_to, sorted(item_ids.keys()))

        _done = []
        for _counter, vd_id in enumerate(item_ids):
            _counter += 1
            if to_def:
                # とりあえずマイリストには直接移動できないので、追加と削除を別でやる。
                res = self.get_response("add", to_def=True,
                                        video_id=vd_id, item_id=item_ids[vd_id])
                try:
                    self._should_continue(res, video_id=vd_id, list_name=list_name_to,
                                          count_now=_counter, count_whole=len(item_ids))
                except MylistAPIError as error:
                    if error.ok:
                        return True
                    else:
                        # エラーが起きた場合
                        self.logger.error(Err.remaining,
                            [i for i in videoids if i not in _done and i != utils.ALL_ITEM])
                        raise
                res = self.get_response("delete", from_def=True,
                                        video_id=vd_id, item_id=item_ids[vd_id])
            else:
                res = self.get_response("move", item_id=item_ids[vd_id], from_def=from_def,
                                        list_id_to=list_id_to, list_id_from=list_id_from)

            try:
                self._should_continue(res, video_id=vd_id, list_name=list_name_to,
                                      count_now=_counter, count_whole=len(item_ids))
                self.logger.info(Msg.ml_done_move, _counter, len(item_ids), vd_id)
                _done.append(vd_id)
            except MylistAPIError as error:
                if error.ok:
                    return True
                else:
                    # エラーが起きた場合
                    self.logger.error(Err.remaining,
                        [i for i in videoids if i not in _done and i != utils.ALL_ITEM])
                    raise
        return True

    def delete(self, list_id, *videoids, confident=False):
        """
        そのマイリストから、指定した動画を削除する。

        :param int | str list_id: 移動元のIDまたは名前
        :param str videoids: 動画ID
        :param bool confident:
        :rtype: bool
        """
        utils.check_arg(locals())
        if len(videoids) > 1 and utils.ALL_ITEM in videoids:
            raise utils.MylistError(Err.videoids_contain_all)
        list_id, list_name = self._get_list_id(list_id)

        from_def = (list_id == utils.DEFAULT_ID)

        item_ids = self.get_item_ids(list_id, *videoids)
        if len(item_ids) == 0:
            self.logger.error(Err.no_items)
            return False

        if len(videoids) == 1 and utils.ALL_ITEM in videoids:
            # 全体モード
            if not confident and not self._confirmation(
                    "delete", list_name, sorted(item_ids.keys())):
                print(Msg.ml_answer_no)
                return False
            self.logger.info(Msg.ml_will_delete, list_name, sorted(item_ids.keys()))
        else:
            # 個別モード
            self.logger.info(Msg.ml_will_delete, list_name, list(videoids))
            item_ids = {vd_id: item_ids[vd_id] for vd_id in videoids if vd_id in item_ids}

            # 指定したIDが含まれているかの確認
            excluded = [vd_id for vd_id in videoids if vd_id not in item_ids]
            if len(excluded) > 0:
                self.logger.error(Err.item_not_contained, list_name, excluded)

        _done = []
        for _counter, vd_id in enumerate(item_ids):
            _counter += 1
            res = self.get_response("delete", from_def=from_def,
                                    list_id_from=list_id, item_id=item_ids[vd_id])

            try:
                self._should_continue(res, video_id=vd_id, list_name=list_name,
                                      count_now=_counter, count_whole=len(item_ids))
                self.logger.info(Msg.ml_done_delete, _counter, len(item_ids), vd_id)
                _done.append(vd_id)
            except MylistAPIError as error:
                if error.ok:
                    return True
                else:
                    # エラーが起きた場合
                    self.logger.error(Err.remaining,
                        [i for i in videoids if i not in _done and i != utils.ALL_ITEM])
                    raise
        return True

    def fetch_meta(self, with_header=True):
        """
        マイリストのメタ情報を表示する。

        :param bool with_header:
        :rtype: list[list[str]]
        """
        utils.check_arg(locals())
        self.logger.info(Msg.ml_loading_mylists)

        counts = len(json.loads(self.session.get(URL.URL_ListDef).text)["mylistitem"])
        if with_header:
            container = [["ID", "名前", "項目数", "状態", "作成日", "説明文"]]
        else:
            container = []
        # とりあえずマイリストのデータ
        container.append([utils.DEFAULT_ID, utils.DEFAULT_NAME, counts, "非公開", "--", ""])

        # その他のマイリストのデータ
        # 作成日順に並び替えてから情報を得る
        for item in sorted(self.mylists.values(), key=lambda this: this["since"]):
            response = self.session.get(URL.URL_ListOne, params={"group_id": item["id"]}).text
            counts = len(json.loads(response)["mylistitem"])

            container.append([
                item[MKey.ID], item[MKey.NAME], counts, item[MKey.PUBLICITY],
                item[MKey.SINCE], item[MKey.DESCRIPTION]
            ])
        return container

    def fetch_one(self, list_id, with_header=True):
        """
        単一のマイリストに登録された動画情報を文字列にする。

        deleted について:
            * 1 = 投稿者による削除
            * 2 = 運営による削除
            * 3 = 権利者による削除
            * 8 = 投稿者による非公開

        :param int | str list_id: マイリストの名前またはID。
        :param bool with_header:
        :rtype: list[list[str]]
        """
        utils.check_arg(locals())
        list_id, list_name = self._get_list_id(list_id)

        self.logger.info(Msg.ml_showing_mylist, list_name)
        if list_id == utils.DEFAULT_ID:
            jtext = json.loads(self.session.get(URL.URL_ListDef).text)
        else:
            jtext = json.loads(self.session.get(URL.URL_ListOne,
                                                params={"group_id": list_id}).text)
        self.logger.debug("Returned: %s", jtext)

        if with_header:
            container = [[
                "動画 ID", "タイトル",
                "投稿日", "再生数",
                "コメント数", "マイリスト数",
                "長さ", "状態",
                "メモ", "所屬",
                # "最近のコメント",
            ]]
        else:
            container = []

        for item in jtext["mylistitem"]:
            data = item[MKey.ITEM_DATA]
            desc = html.unescape(item[MKey.DESCRIPTION])
            duration = int(data[KeyGTI.LENGTH_SECONDS])
            container.append([
                data[KeyGTI.VIDEO_ID],
                html.unescape(data[KeyGTI.TITLE]).replace(r"\/", "/"),
                self._get_jst_from_utime(data[KeyGTI.FIRST_RETRIEVE]),
                data[KeyGTI.VIEW_COUNTER],
                data[KeyGTI.NUM_RES],
                data[KeyGTI.MYLIST_COUNTER],
                "{}:{}".format(duration // 60, duration % 60),
                self.WHY_DELETED.get(data[KeyGTI.DELETED], "不明"),
                desc.strip().replace("\r", "").replace("\n", " ").replace(r"\/", "/"),
                list_name,
                # data[KeyGTI.LAST_RES_BODY],
            ])
        self.logger.debug("Mylists info: %s", container)
        return container

    def fetch_all(self, with_info=True):
        """
        全てのマイリストに登録された動画情報を文字列にする。

        :param bool with_info:
        :rtype: list[list[str]]
        """
        utils.check_arg(locals())
        container = []
        if with_info:
            result_def = self.fetch_one(utils.DEFAULT_ID)
            container.extend(result_def)
            for l_id in self.mylists.keys():
                result = self.fetch_one(l_id, False)
                container.extend(result)
        else:
            result_def = self.fetch_one(utils.DEFAULT_ID, False)
            container.extend(result_def)
            for l_id in self.mylists.keys():
                result = self.fetch_one(l_id, False)
                container.extend([[item[0]] for item in result])
        return container

    def show(self, list_id, file_name=None, table=False, survey=False):
        """
        そのマイリストに登録された動画を一覧する。

        :param int | str list_id: マイリストの名前またはID。0で「とりあえずマイリスト」。
        :param str | Path | None file_name: ファイル名。ここにリストを書き出す。
        :param bool table: Trueで表形式で出力する。
        :param bool survey: Trueで全てのマイリストの情報をまとめて出力する。
        :rtype: str
        """
        utils.check_arg({"list_id": list_id, "table": table, "survey": survey})
        if file_name:
            file_name = utils.make_dir(file_name)
        if table:  # 表形式の場合
            if list_id == utils.ALL_ITEM:
                if survey:
                    cont = self._construct_table(self.fetch_all())
                else:
                    cont = self._construct_table(self.fetch_meta())
            else:
                cont = self._construct_table(self.fetch_one(list_id))
        else:  # タブ区切りテキストの場合
            if list_id == utils.ALL_ITEM:
                if survey:
                    cont = self._construct_tsv(self.fetch_all())
                else:
                    cont = self._construct_tsv(self.fetch_meta())
            else:
                cont = self._construct_tsv(self.fetch_one(list_id))
        return self._writer(cont, file_name)

    def export(self, list_id, file_name=None, survey=False):
        """
        そのマイリストに登録された動画のIDを一覧する。

        :param int | str list_id: マイリストの名前またはID。0で「とりあえずマイリスト」。
        :param str | Path | None file_name: ファイル名。ここにリストを書き出す。
        :param bool survey: Trueで全てのマイリストの情報をまとめて出力する。
        :rtype: str
        """
        utils.check_arg({"list_id": list_id, "survey": survey})
        if file_name:
            file_name = utils.make_dir(file_name)
        if list_id == utils.ALL_ITEM:
            if survey:
                cont = self._construct_id(self.fetch_all(False))
            else:
                cont = self._construct_id_name(self.fetch_meta(False))
        else:
            cont = self._construct_id(self.fetch_one(list_id, False))
        return self._writer(cont, file_name)

    @classmethod
    def _construct_id(cls, container):
        """
        IDだけを出力する。

        :param list[list[str]] container: 表示したい動画IDのリスト。
        :rtype: str
        """
        utils.check_arg(locals())
        if len(container) == 0:
            return ""
        else:
            return "\n".join(
                [str(item[0]) for item in container
                 if item is not None and len(item) > 0])

    @classmethod
    def _construct_id_name(cls, container):
        """
        動画IDやマイリストIDとその名前だけを出力する。

        :param list[list[str]] container: 表示したいIDの入ったリスト。
        :rtype: str
        """
        utils.check_arg(locals())
        if len(container) == 0:
            return ""
        else:
            return "\n".join(
                ["{}\t{}".format(item[0], item[1]) for item in container
                 if item is not None and len(item) > 0])

    @classmethod
    def _construct_tsv(cls, container):
        """
        TSV形式で出力する。

        :param list[list[str]] container: 表示したい内容を含むリスト。
        :rtype: str
        """
        utils.check_arg(locals())
        if len(container) == 0:
            return ""
        else:
            first = container.pop(0)
            rows = [[str(item) for item in row] for row in container]
            rows.insert(0, first)
            return "\n".join(["\t".join(row) for row in rows])

    @classmethod
    def _construct_table(cls, container):
        """
        Asciiテーブル形式でリストの中身を表示する。

        入力の形式は以下の通り:

        [
            ["header1", "header2", "header3"],
            ["row_1_1", "row_1_2", "row_1_3"],
            ["row_2_1", "row_2_2", "row_2_3"],
            ["row_3_1", "row_3_2", "row_3_3"]
        ]

        最後のprintで、ユニコード特有の文字はcp932のコマンドプロンプトでは表示できない。
        この対処として幾つかの方法で別の表現に置き換えることができるのだが、例えば「♥」は

        =================== ==================================================
        メソッド                 変換後
        ------------------- --------------------------------------------------
        backslashreplace    \u2665
        xmlcharrefreplace   &#9829;
        replace             ?
        =================== ==================================================

        と表示される。

        :param list[list[str]] container: 表示したい内容を含むリスト。
        :rtype: str
        """
        utils.check_arg(locals())
        if len(container) == 0:
            return ""
        elif not PrettyTable:
            raise ImportError(Err.not_installed, "PrettyTable")
        else:
            column_names = container.pop(0)
            table = PrettyTable(column_names)
            for column in column_names:
                table.align[column] = "l"
            for row in container:
                table.add_row(row)
            return table.get_string()

    def _writer(self, text, file_name=None):
        """
        ファイルまたは標準出力に書き出す。

        :param str text: 内容。
        :param str | Path | None file_name: ファイル名またはそのパス
        :rtype: str
        """
        utils.check_arg({"text": text})
        if file_name:
            file_name = utils.make_dir(file_name)
            _text = "{}\n".format(text)
            with file_name.open(mode="w", encoding="utf-8") as fd:
                fd.write(_text)
            self.logger.info(Msg.ml_exported, file_name)
        else:
            enco = utils.get_encoding()
            _text = text.encode(enco, utils.BACKSLASH).decode(enco) + "\n"
            print(_text)
        return _text


def linting(args, dest, source):
    """

    :param args:
    :param str | None dest:
    :param str | int source:
    """
    if (((args.add or args.create or args.purge) and utils.ALL_ITEM == source) or
                args.add and utils.ALL_ITEM in args.add):
        raise ZeroDivisionError(Err.cant_perform_all)
    if (args.create or args.purge) and utils.DEFAULT_NAME == source:
        raise ZeroDivisionError(Err.deflist_to_create_or_purge)
    if args.create and "" == source:
        raise ZeroDivisionError(Err.cant_create)
    if args.copy or args.move:
        if dest is None:
            raise ZeroDivisionError(Err.not_specified.format("--to"))
        if source == dest:
            raise ZeroDivisionError(Err.list_names_are_same)
    if (args.delete and (len(args.delete) > 1 and utils.ALL_ITEM in args.delete) or
            (args.copy and len(args.copy) > 1 and utils.ALL_ITEM in args.copy) or
            (args.move and len(args.move) > 1 and utils.ALL_ITEM in args.move)):
        raise ZeroDivisionError(Err.videoids_contain_all)
    if not (args.export or args.show or args.create or args.purge
            or args.add or args.copy or args.move or args.delete):
        raise ZeroDivisionError(Err.no_commands)


def linting_2(args):
    operand = []
    if args.add or args.copy or args.move or args.delete:
        if args.add:
            operand = utils.validator(args.add)
        elif args.copy:
            operand = utils.validator(args.copy)
        elif args.move:
            operand = utils.validator(args.move)
        else:
            operand = utils.validator(args.delete)
        if not operand: raise ZeroDivisionError(Err.invalid_videoid)
    return operand


def main(args):
    """
    メイン。

    :param args: ArgumentParser.parse_args() によって解釈された引数。
    :rtype: bool
    """
    is_debug = int(os.getenv("PYTHON_TEST", 0))
    log_level = "DEBUG" if is_debug else args.loglevel
    logger = utils.NTLogger(log_level=log_level, file_name=utils.LOG_FILE_ML)

    mailadrs = args.mail[0] if args.mail else None
    password = args.password[0] if args.password else None
    instnc = NicoMyList(mail=mailadrs, password=password, logger=logger)

    source = args.src[0]
    if args.id and source.isdecimal(): source = int(source)

    dest = args.to[0] if isinstance(args.to, list) else None
    file_name = args.out[0] if isinstance(args.out, list) else None

    #
    # エラーの除外
    #
    try:
        linting(args, dest, source)
        operand = linting_2(args)
    except ZeroDivisionError as error:
        sys.exit(error.args)

    #
    # 本筋
    #
    if args.export:
        res = instnc.export(source, file_name, survey=args.everything)
    elif args.show:
        if args.show >= 2 and PrettyTable:  # Tableモード
            res = instnc.show(source, file_name, survey=args.everything, table=True)
        else:  # TSVモード
            res = instnc.show(source, file_name, survey=args.everything)
    elif args.create:
        res = instnc.create_mylist(source)
    elif args.purge:
        res = instnc.purge_mylist(source, confident=args.yes)
    elif args.add:
        res = instnc.add(source, *operand)
    elif args.copy:
        res = instnc.copy(source, dest, *operand)
    elif args.move:
        res = instnc.move(source, dest, *operand)
    else:
        res = instnc.delete(source, *operand, confident=args.yes)

    return res
