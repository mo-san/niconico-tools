# coding: UTF-8
import html
import json
from argparse import ArgumentParser
from datetime import datetime, timezone, timedelta
from os.path import abspath
from sys import exit, argv, stderr, stdout
from time import sleep
from xml.etree import ElementTree
try:
    from prettytable import PrettyTable
except ImportError:
    PrettyTable = None

from utility_func import Msg, Err, URL, Key, MKey, MyLogger, LogIn, get_encoding, validator


class NicoMyList(LogIn):
    WHY_DELETED = {
        "0": "公開",
        "1": "削除",
        "2": "運営による削除",
        "3": "権利者による削除",
        "8": "非公開",
    }

    def __init__(self, auth, session=None, logger=None):
        """
        使い方:

            MYLISTに動画を追加する:
                nicoml MYLIST --add sm1 sm2 sm3
            IDを一行ごとに書いたファイルからMYLISTに動画を追加する:
                nicoml MYLIST --add +C:/Users/Me/Desktop/ids.txt
            MYLISTをそのIDで指定する:
                nicoml 12345678 --id --add sm1 sm2 sm3
            MYLISTから動画を削除する:
                nicoml MYLIST --delete sm1 sm2 sm3
            MYLIST の中のもの全てを削除する:
                nicoml MYLIST --delete *
            MYLIST の中の動画を --to に移す:
                nicoml MYLIST --to なんとかかんとか --move sm1 sm2 sm3
            MYLIST の中のもの全てを --to に移す:
                nicoml MYLIST --to なんとかかんとか --move *
            MYLIST の中の動画を --to に写す:
                nicoml MYLIST --to なんとかかんとか --copy sm1 sm2 sm3
            MYLIST の中のもの全てを --to に写す:
                nicoml MYLIST --to なんとかかんとか --copy *

            特定のマイリストの中身を一覧にする:
                nicoml MYLIST --export
            全てのマイリストの名前を一覧にする:
                nicoml * --show
            指定した名前で新しいマイリストを作る:
                nicoml MYLIST --create
            指定した名前のマイリストを削除する:
                nicoml MYLIST --purge
            指定したマイリストに登録されたIDを標準出力に出力する:
                nicoml MYLIST --export
            指定したマイリストに登録されたIDをタブ区切りで標準出力に出力する:
                nicomlrt MYLIST --export -expo
            指定したマイリストに登録されたIDを表形式で標準出力に出力する
            (PrettyTableがインストールされていれば):
                nicomlrt MYLIST --export -expo
            指定したマイリストに登録されたIDをファイルに出力する:
                nicoml MYLIST --export --out C:/Users/Me/Desktop/file.txt

        他のコマンド:
            それぞれにはログインに必要な情報を与えられる:
                nicoml MYLIST --add sm9 --user <メールアドレス> --pass <パスワード>

            引数がどの様に解釈されるかを確認したいとき (確認するだけで、プログラムは実行しません):
                nicoml.py --export --id 12345678 --out ../file.txt --what

            ログ出力の詳細さを変える:
                nicoml --loglevel WARNING  # エラー以外表示しない

            引用符を含むマイリスト名の指定方法:
                * 「"マイ'リ'スト"」 を指定するには 「"\"マイ'リ'スト\""」
                * 「'マイ"リ"スト'」 を指定するには 「"'マイ\"リ\"スト'"」

        :param tuple[typing.Optional[str], typing.Optional[str]] auth: メールアドレスとパスワードの組
        :param T <= logging.Logger logger:
        :rtype: None
        """
        super().__init__(auth, session, logger)
        if not hasattr(logger, "handlers"):
            self.logger = self.AltLogger()
        self.mylists = self.get_mylist_ids()

    class AltLogger:
        """ logger がなかった場合の保険 """
        def emitter(self, text, err=False, en=get_encoding()):
            print(text.encode(en, Msg.BACKSLASH).decode(en),
                  file=[stdout, stderr][err])

        def debug(self, text)   : self.emitter(text)

        def info(self, text)    : self.emitter(text)

        def error(self, text)   : self.emitter(text, True)

        def warning(self, text) : self.emitter(text, True)

        def critical(self, text): self.emitter(text, True)

    def get_mylist_ids(self):
        """
        全てのマイリストのメタ情報を得る。

        :rtype: dict
        """
        jsonliketext = self.session.get(URL.URL_ListAll).text
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
                MKey.SINCE: self.get_jst_from_utime(item["create_time"]),  # type: str
                MKey.DESCRIPTION: description,
            }
        self.mylists = candidate
        return candidate

    def get_id(self, search_for):
        """
        指定されたIDまたは名前を持つマイリストのIDを得る。

        :param int | str search_for:
        :rtype: (int, str)
        """
        if self.mylists is None: self.get_mylist_ids()  # 保険のため

        if search_for == Msg.ml_default_name:
            return Msg.ml_default_id, Msg.ml_default_name

        if isinstance(search_for, int):
            value = self.mylists.get(search_for, None)
            if value is None:
                exit(Err.mylist_id_not_exist.format(search_for))
            return search_for, value["name"]

        elif isinstance(search_for, str):
            value = [(l_id, info) for l_id, info in self.mylists.items()
                     if info["name"] == search_for]
            if len(value) == 0:
                exit(Err.mylist_not_exist.format(search_for))
            if len(value) == 1:
                return value[0][0], search_for
            else:
                # 同じ名前のマイリストが複数あったとき
                self.logger.error(Err.name_ambiguous.format(len(value)))
                for single in value:
                    self.logger.error(Err.name_ambiguous_detail.format(single[1]))
                exit()
        else:
            exit(Err.invalid_spec.format(search_for))

    def get_item_ids(self, list_id, *videoids):
        """
        そのマイリストに含まれている item_id の一覧を返す。

        全て、あるいは指定した(中での生存している)動画の Item IDを返す。
        item_id は sm1234 などの動画IDとは異なるもので、 マイリスト間の移動や複製に必要となる。

        :param int | str list_id: マイリストの名前またはID
        :param list[str] | tuple[str] videoids:
        :rtype: dict[str, str]
        """
        list_id, list_name = self.get_id(list_id)
        # *videoids が要素数1のタプル ("*") or
        # *videoids が要素数0のタプル(即ち未指定) -> 全体モード
        # 何かしら指定されているなら -> 個別モード
        whole = True if len(videoids) == 0 or (len(videoids) == 1 and Msg.ALL_ITEM in videoids) else False

        # self.logger.debug("動画IDに対応するItemIDを探しています...")
        if list_id == Msg.ml_default_id:
            jtext = json.loads(self.session.get(URL.URL_ListDef).text)
        else:
            jtext = json.loads(self.session.get(URL.URL_ListOne,
                                                params={"group_id": list_id}).text)

        results = {}
        for item in jtext["mylistitem"]:
            data = item["item_data"]
            # 0以外のは削除されているか非公開
            if not whole:
                if not "0" == data["deleted"]:
                    self.logger.debug(Msg.ml_deleted_or_private.format(data))
                    continue

            if whole or data["video_id"] in videoids:
                results.update({data["video_id"]: item["item_id"]})

        if len(results) == 0: exit(Err.no_items)
        return results

    def get_jst_from_utime(self, timestamp):
        """
        UNIXTIMEを日本標準時に変換する。末尾の'+09:00'は取り除く。

        1471084020 -> '2016-08-13 19:27:00'

        :param int timestamp: UNIXTIMEの数字。
        :rtype: str
        """
        return str(datetime.fromtimestamp(timestamp, timezone(timedelta(hours=+9))))[:-6]

    def get_title(self, video_id):
        """
        getthumbinfo APIから、タイトルをもらってくる

        :param str video_id: 動画ID
        :rtype:str
        """
        document = ElementTree.fromstring(self.session.get(URL.URL_Info + video_id).text)
        # 「status="ok"」 なら動画は生存 / 存在しない動画には「status="fail"」が返る
        if not document.get("status").lower() == "ok":
            self.logger.error(Msg.nd_deleted_or_private.format(video_id))
            return ""
        else:
            return html.unescape(document[0].find("title").text)

    def confirmation(self, mode, list_name, contents_to_be_deleted=None):
        """
        マイリスト自体を削除したり、マイリスト中の全てを削除する場合にユーザーの確認を取る。

        :param str mode:
        :param str list_name:
        :param list[str] contents_to_be_deleted:
        :rtype: bool
        """
        if mode == "purge":
            print(Msg.ml_will_purge.format(list_name))
        elif mode == "delete":
            print(Msg.ml_ask_delete_all.format(list_name))
            print("{}".format(contents_to_be_deleted))
        else:
            exit(mode)

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

    def should_continue(self, res, vd_id, list_name, count_now, count_whole):
        """
        次の項目に進んでよいかを判断する。

        致命的なエラーならば False を返し、差し支えないエラーならば True を返す。

        :param dict[str, str] res:
        :param str vd_id:
        :param str list_name:
        :param int count_now:
        :param int count_whole:
        :rtype: bool
        """
        try:
            reason = res["error"]
            if (reason["code"] == Err.INTERNAL or
                        reason["code"] == Err.MAINTENANCE):
                self.logger.error(Err.known_error.format(vd_id, reason["description"]))
                return False
            elif reason["code"] == Err.MAXERROR:
                self.logger.error(Err.over_load.format(list_name))
                return False
            elif reason["code"] == Err.EXIST:
                title = self.get_title(vd_id)
                self.logger.error(Err.already_exist.format(vd_id, title))
                return True
            elif reason["code"] == Err.NONEXIST:
                self.logger.error(Err.item_not_contained.format(list_name, vd_id))
                return True
            elif hasattr(Err, reason["code"]):
                self.logger.error(Err.known_error.format(vd_id, reason["description"]))
                return True
            else:
                return False
        except KeyError:
            self.logger.error(Err.unknown_error_itemid.format(
                count_now, count_whole, vd_id, res))
            return False

    def get_response(self, mode, is_def, list_id_to, video_or_item_id, list_id_from=None):
        if mode == "add":
            payload = {
                "item_type"      : 0,
                "item_id"        : video_or_item_id,
                "description"    : "",
                "token"          : self.token
            }
            if is_def:
                res = self.session.get(URL.URL_AddDef, params=payload).text
            else:
                payload.update({"group_id": str(list_id_to)})
                res = self.session.get(URL.URL_AddItem, params=payload).text
        elif mode == "copy" or mode == "move":
            payload = {
                "target_group_id": str(list_id_to),
                "id_list[0][]"   : video_or_item_id,
                "token"          : self.token
            }
            if is_def:
                if mode == "copy":
                    res = self.session.get(URL.URL_CopyDef, params=payload).text
                else:
                    res = self.session.get(URL.URL_MoveDef, params=payload).text
            else:
                payload.update({"group_id": str(list_id_from)})
                if mode == "copy":
                    res = self.session.get(URL.URL_CopyItem, params=payload).text
                else:
                    res = self.session.get(URL.URL_MoveItem, params=payload).text
        elif mode == "delete":
            payload = {
                "id_list[0][]"   : video_or_item_id,
                "token"          : self.token
            }
            if is_def:
                res = self.session.get(URL.URL_DeleteDef, params=payload).text
            else:
                payload.update({"group_id": str(list_id_to)})
                res = self.session.get(URL.URL_DeleteItem, params=payload).text
        elif mode == "purge":
            payload = {
                "group_id"       : str(list_id_to),
                "token"          : self.token
            }
            res = self.session.get(URL.URL_PurgeList, params=payload).text
        else:
            res = None  # ただの穴埋め
        return json.loads(res)

    def create_mylist(self, mylist_name, is_public=False, desc=None):
        """
        name を名前に持つマイリストを作る。

        :param str mylist_name: マイリストの名前
        :param bool is_public: True なら公開マイリストになる
        :param typing.Optional[str] desc: マイリストの説明文
        :rtype: bool
        """
        payload = {
            "name": mylist_name.encode("utf8"),
            "description": desc or "",
            "public": int(is_public),
            "default_sort": 0,
            "icon_id": 0,
            "token": self.token
        }
        res = self.session.get(URL.URL_AddMyList, params=payload).text
        try:
            result = json.loads(res)["status"]
            if result == "ok":
                self.logger.info(Msg.ml_done_create.format(mylist_name, is_public, desc))
                return True
            else:
                self.logger.error(Err.failed_to_create.format(mylist_name, result))
                return False
        except KeyError:
            self.logger.error(Err.unknown_error_list.format(res))
            return False

    def purge_mylist(self, list_id):
        """
        指定したマイリストを削除する。

        :param int | str list_id: マイリストの名前またはID
        :rtype: bool
        """
        list_id, list_name = self.get_id(list_id)

        if not self.confirmation("purge", list_name):
            exit(Msg.ml_answer_no)

        res = self.get_response("purge", False, list_id, None)
        try:
            if res["status"] == "ok":
                self.logger.info(Msg.ml_done_purge.format(list_name))
                return True
            else:
                self.logger.error(Err.failed_to_purge.format(list_name, res["status"]))
                return False
        except KeyError:
            self.logger.error(Err.unknown_error_list.format(res))
            return False

    def add(self, list_id, *videoids):
        """
        そのマイリストに、 指定した動画を追加する。

        :param int | str list_id: マイリストの名前またはID
        :param list[str] | tuple[str] videoids: 追加する動画ID
        :rtype: bool
        """
        list_id, list_name = self.get_id(list_id)
        self.logger.info(Msg.ml_will_add.format(list_name, list(videoids)))

        _done = []
        for _counter, vd_id in enumerate(videoids):
            _counter += 1
            res = self.get_response("add", list_id == Msg.ml_default_id, list_id, vd_id)

            if res["status"] != "ok" and not self.should_continue(res, vd_id, list_name, _counter, len(videoids)):
                # エラーが起きた場合
                self.logger.error(Err.remaining)
                self.logger.error(" ".join([i for i in videoids if i not in _done]))
                return False
            elif res["status"] == "ok":
                self.logger.info(Msg.ml_done_add.format(_counter, len(videoids), vd_id))
            _done.append(vd_id)
            sleep(0.5)
        return True

    def copy(self, list_id_from, list_id_to, *videoids):
        """
        そのマイリストに、 指定した動画をコピーする。

        :param int |  str list_id_from: 移動元のIDまたは名前
        :param int |  str list_id_to: 移動先のIDまたは名前
        :param list[str] |  tuple[str] videoids: 動画ID
        :rtype: bool
        """
        if list_id_from == list_id_to:
            exit(Err.list_names_are_same)
        return self._copy_or_move_item(True, list_id_from, list_id_to, *videoids)

    def move(self, list_id_from, list_id_to, *videoids):
        """
        そのマイリストに、 指定した動画を移動する。

        :param int |  str list_id_from: 移動元のIDまたは名前
        :param int |  str list_id_to: 移動先のIDまたは名前
        :param list[str] |  tuple[str] videoids: 動画ID
        :rtype: bool
        """
        if list_id_from == list_id_to:
            exit(Err.list_names_are_same)
        if list_id_to == Msg.ml_default_name:
            exit(Err.cant_move_to_deflist)
        return self._copy_or_move_item(False, list_id_from, list_id_to, *videoids)

    def _copy_or_move_item(self, is_copy, list_id_from, list_id_to, *videoids):
        """
        そのマイリストに、 指定した動画を移動またはコピーする。

        :param bool is_copy: コピーか移動かのフラグ (True でコピー、False で移動)
        :param int |  str list_id_from: 移動元のIDまたは名前
        :param int |  str list_id_to: 移動先のIDまたは名前
        :param list[str] |  tuple[str] videoids: 動画ID
        :rtype: bool
        """
        list_id_from, list_name_from = self.get_id(list_id_from)
        list_id_to, list_name_to = self.get_id(list_id_to)

        item_ids = self.get_item_ids(list_id_from, *videoids)
        if Msg.ALL_ITEM not in videoids:
            item_ids = {vd_id: item_ids[vd_id] for vd_id in videoids if vd_id in item_ids}

            # 指定したものが含まれているかの確認
            excluded = [vd_id for vd_id in videoids if vd_id not in item_ids]
            if len(excluded) > 0:
                self.logger.error(Err.item_not_contained.format(list_name_from, excluded))

        self.logger.info(Msg.ml_will_copyormove.format(
            ("移動", "コピー")[is_copy], list_name_from, list_name_to, sorted(item_ids.keys())))

        _done = []
        for _counter, vd_id in enumerate(item_ids):
            _counter += 1
            if is_copy:
                res = self.get_response("copy", list_id_from == Msg.ml_default_id,
                                        list_id_to, item_ids[vd_id], list_id_from)
            else:
                res = self.get_response("move", list_id_from == Msg.ml_default_id,
                                        list_id_to, item_ids[vd_id], list_id_from)

            if res["status"] != "ok" and not self.should_continue(res, vd_id, list_name_to, _counter, len(item_ids)):
                # エラーが起きた場合
                self.logger.error(Err.remaining)
                self.logger.error(" ".join([i for i in videoids if i not in _done]))
                return False
            if is_copy:
                self.logger.info(Msg.ml_done_copy.format(_counter, len(item_ids), vd_id))
            else:
                self.logger.info(Msg.ml_done_move.format(_counter, len(item_ids), vd_id))
            _done.append(vd_id)
        return True

    def delete(self, list_id, *videoids):
        """
        そのマイリストから、指定した動画を削除する。

        :param int |  str list_id: 移動元のIDまたは名前
        :param list[str] |  tuple[str] videoids: 動画ID
        :rtype: bool
        """
        list_id, list_name = self.get_id(list_id)

        item_ids = self.get_item_ids(list_id, *videoids)

        if len(videoids) == 1 and Msg.ALL_ITEM in videoids:
            # 全体モード
            if not self.confirmation("delete", list_name, sorted(item_ids.keys())):
                print(Msg.ml_answer_no) or exit()
            self.logger.info(Msg.ml_will_delete.format(list_name, sorted(item_ids.keys())))
        else:
            # 個別モード
            self.logger.info(Msg.ml_will_delete.format(list_name, list(videoids)))
            item_ids = {vd_id: item_ids[vd_id] for vd_id in videoids if vd_id in item_ids}

            # 指定したIDが含まれているかの確認
            excluded = [vd_id for vd_id in videoids if vd_id not in item_ids]
            if len(excluded) > 0:
                self.logger.error(Err.item_not_contained.format(list_name, excluded))

        _done = []
        for _counter, vd_id in enumerate(item_ids):
            _counter += 1
            res = self.get_response("delete", list_id == Msg.ml_default_id, list_id, item_ids[vd_id])

            if res["status"] != "ok" and not self.should_continue(res, vd_id, list_name, _counter, len(item_ids)):
                # エラーが起きた場合
                self.logger.error(Err.remaining)
                self.logger.error(" ".join([i for i in videoids if i not in _done]))
                return False
            elif res["status"] == "ok":
                self.logger.info(Msg.ml_done_delete.format(_counter, len(item_ids), vd_id))
            _done.append(vd_id)
        return True

    def show_meta(self):
        """
        マイリストのメタ情報を表示する。

        :rtype: list[list[str]]
        """
        if self.logger: self.logger.info(Msg.ml_loading_mylists)

        counts = len(json.loads(self.session.get(URL.URL_ListDef).text)["mylistitem"])
        container = [
            ["ID", "名前", "項目数", "状態", "作成日", "説明文"],
            # とりあえずマイリストのデータ
            [Msg.ml_default_id, Msg.ml_default_name, counts, "非公開", "--", ""]
        ]

        # その他のマイリストのデータ
        for item in sorted(self.mylists.values(), key=lambda this: this["since"]):
            response = self.session.get(URL.URL_ListOne, params={"group_id": item["id"]}).text
            counts = len(json.loads(response)["mylistitem"])

            container.append([
                item[MKey.ID], item[MKey.NAME], counts, item[MKey.PUBLICITY],
                item[MKey.SINCE], item[MKey.DESCRIPTION]
            ])
        return container

    def show_one(self, list_id):
        """
        そのマイリストに登録された動画を一覧する。

        deleted について:
            * 1 = 投稿者による削除
            * 2 = 運営による削除
            * 3 = 権利者による削除
            * 8 = 投稿者による非公開

        :param int |  str list_id: マイリストの名前またはID。
        :rtype: list[list[str]]
        """
        list_id, list_name = self.get_id(list_id)

        if self.logger: self.logger.info(Msg.ml_showing_mylist.format(list_name))
        if list_id == Msg.ml_default_id:
            jtext = json.loads(self.session.get(URL.URL_ListDef).text)
        else:
            jtext = json.loads(self.session.get(URL.URL_ListOne,
                                                params={"group_id": list_id}).text)

        container = [[
            "動画 ID", "タイトル",
            "投稿日", "再生数",
            "コメント数", "マイリスト数",
            "長さ", "状態",
            "メモ", "所屬",
            # "最近のコメント",
        ]]

        for item in jtext["mylistitem"]:
            data = item[MKey.ITEM_DATA]
            desc = html.unescape(item[MKey.DESCRIPTION])
            duration = int(data[Key.LENGTH_SECONDS])
            container.append([
                data[Key.VIDEO_ID],
                html.unescape(data[Key.TITLE]).replace(r"\/", "/"),
                self.get_jst_from_utime(data[Key.FIRST_RETRIEVE]),
                data[Key.VIEW_COUNTER],
                data[Key.NUM_RES],
                data[Key.MYLIST_COUNTER],
                "{}:{}".format(duration // 60, duration % 60),
                self.WHY_DELETED.get(data[Key.DELETED], "不明"),
                desc.strip().replace("\r", "").replace("\n", " ").replace(r"\/", "/"),
                list_name,
                # data[Key.LAST_RES_BODY],
            ])
        return container

    def show_through(self, simple=False):
        """
        全てのマイリストを表示する。

        :param bool simple:
        :rtype: list[list[str]]
        """
        container = []
        if simple:
            for l_id in self.mylists.keys():
                container.extend([[item[0]] for item in self.show_one(l_id)[1:]])
        else:
            for l_id in self.mylists.keys():
                container.extend(self.show_one(l_id)[1:])
        return container

    def export(self, list_id, file_name=None, table=False, tsv=False, mode_is_show=False):
        """
        そのマイリストに登録された動画のIDを一覧する。

        :param int |  str list_id: マイリストの名前またはID。0で「とりあえずマイリスト」。
        :param typing.Optional[str] file_name: ファイル名。ここにリストを書き出す。
        :param bool table: Trueで表形式で出力する。
        :param bool tsv: FalseでIDのみを、TrueでIDに加え他の情報もTSV表記で出力する。
        :param bool mode_is_show: show コマンドならば True。
        :rtype: None
        """
        if table:  # 表形式の場合
            if list_id == Msg.ALL_ITEM:
                if mode_is_show:
                    self._export_table(self.show_meta(), file_name)
                else:
                    self._export_table(self.show_through(), file_name)
            else:
                self._export_table(self.show_one(list_id), file_name)
        elif tsv:  # タブ区切りテキストの場合
            if list_id == Msg.ALL_ITEM:
                if mode_is_show:
                    self._export_tsv(self.show_meta(), file_name)
                else:
                    self._export_tsv(self.show_through(), file_name)
            else:
                self._export_tsv(self.show_one(list_id), file_name)
        else:  # 装飾を求めない場合
            if list_id == Msg.ALL_ITEM:
                self._export_id_only(self.show_through(simple=True), file_name)
            else:
                self._export_id_only(self.show_one(list_id)[1:], file_name)

    def _export_id_only(self, container, file_name=None):
        """
        動画IDだけを出力する。

        :param list[list[str]] container: 表示したい動画IDのリスト。
        :param str file_name: ファイル名。ここにリストを書き出す。
        """
        _ids = [item[0] for item in container if item is not None and len(item) > 0]

        if file_name:
            self.writer("\n".join(_ids), file_name)
        else:
            print("\n".join(_ids))

    def _export_tsv(self, container, file_name=None):
        """
        TSV形式で出力する。

        :param list[list[str]] container: 表示したい内容を含むリスト。
        :param typing.Optional[str] file_name: ファイル名。ここにリストを書き出す。
        """
        enco = get_encoding()

        if len(container) > 1: print(Msg.ml_items_counts, len(container) - 1)

        rows = [container.pop(0)]
        for row in container:
            rows.append([str(item) for item in row])

        if file_name:
            self.writer("\n".join(["\t".join(row) for row in rows]), file_name)
        else:
            for row in rows:
                print("\t".join(row).encode(enco, Msg.BACKSLASH).decode(enco))

    def _export_table(self, container, file_name=None):
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
        :param typing.Optional[str] file_name: ファイル名。ここにリストを書き出す。
        """
        enco = get_encoding()

        if len(container) > 1: print(Msg.ml_items_counts, len(container) - 1)

        cols = container.pop(0)
        table = PrettyTable(cols)
        for column in cols:
            table.align[column] = "l"
        for row in container:
            table.add_row(row)

        if file_name:
            self.writer(table.get_string(), file_name)
        else:
            print(table.get_string().encode(enco, Msg.BACKSLASH).decode(enco))

    def writer(self, text, file_name):
        """

        :param str text: 内容。
        :param str file_name: ファイル名。
        """
        with open(file_name, encoding="utf-8", mode="w") as fd:
            fd.write("{}\n".format(text))
        self.logger.info(Msg.ml_exported.format(abspath(file_name)))


def main(args):
    """
    :param args: ArgumentParserに解析された引数。
    :rtype: None
    """
    if args.what: print(args) or exit()

    logger = MyLogger(log_level=args.loglevel, log_file_name=Msg.LOG_FILE_NAME)

    username = getattr(args, "user")[0] if isinstance(getattr(args, "user"), list) else None
    password = getattr(args, "pass")[0] if isinstance(getattr(args, "pass"), list) else None
    instnc = NicoMyList((username, password), logger=logger)

    target = args.src[0]
    if args.id and target.isdecimal(): target = int(target)

    dest = args.to[0] if isinstance(args.to, list) else None
    file_name = args.out[0] if isinstance(args.out, list) else None

    """ エラーの除外 """
    if (args.add or args.create or args.purge) and Msg.ALL_ITEM == target:
        exit(Err.cant_perform_all)
    if args.show and Msg.ALL_ITEM != target:
        exit(Err.only_perform_all)
    if (args.copy or args.move) and dest is None:
        exit(Err.lack_arg.format("--to"))
    if (args.delete and (len(args.delete) > 1 and Msg.ALL_ITEM in args.delete) or
            (args.copy and len(args.copy) > 1 and Msg.ALL_ITEM in args.copy) or
            (args.move and len(args.move) > 1 and Msg.ALL_ITEM in args.move)):
        exit(Err.args_ambiguous)
    operand = []
    if args.add or args.copy or args.move or args.delete:
        if args.add:    operand = validator(args.add)
        elif args.copy: operand = validator(args.copy)
        elif args.move: operand = validator(args.move)
        else:           operand = validator(args.delete)
        if not operand: exit(Err.invalid_videoid)

    """ 本筋 """
    if args.export:
        if args.export == 1:  # 簡略化モード
            instnc.export(target, file_name)
        elif args.export == 2:  # TSVモード
            instnc.export(target, file_name, tsv=True)
        elif args.export >= 3:
            if PrettyTable:
                instnc.export(target, file_name, table=True)
            else:
                instnc.export(target, file_name, tsv=True)
    elif args.show:
        if PrettyTable:
            instnc.export(Msg.ALL_ITEM, file_name, table=True, mode_is_show=True)
        else:
            instnc.export(Msg.ALL_ITEM, file_name, tsv=True, mode_is_show=True)
    elif args.create:
        instnc.create_mylist(target)
    elif args.purge:
        instnc.purge_mylist(target)
    elif args.add:
        instnc.add(target, *operand)
    elif args.copy:
        instnc.copy(target, dest, *operand)
    elif args.move:
        instnc.move(target, dest, *operand)
    elif args.delete:
        instnc.delete(target, *operand)
    else:
        print(Err.no_commands)


if __name__ == "__main__":
    parser = ArgumentParser(fromfile_prefix_chars="+", description=Msg.ml_description)
    parser.add_argument("src", nargs=1, help=Msg.ml_help_src, metavar="マイリスト名")
    parser.add_argument("-i", "--id", action="store_true", help=Msg.ml_help_id)
    parser.add_argument("-w", "--what", action="store_true", help=Msg.nd_help_what)
    parser.add_argument("-l", "--loglevel", type=str.upper, default="INFO",
                        help=Msg.nd_help_loglevel,
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    parser.add_argument("-u", "--user", nargs=1, help=Msg.nd_help_username, metavar="MAIL")
    parser.add_argument("-p", "--pass", nargs=1, help=Msg.nd_help_password, metavar="PASSWORD")
    group_one = parser.add_argument_group(Msg.ml_help_group_a)
    group_one.add_argument("-t", "--to", nargs=1, help=Msg.ml_help_to, metavar="To")
    group_one.add_argument("-a", "--add", nargs="+", help=Msg.ml_help_add, metavar="sm...")
    group_one.add_argument("-d", "--delete", nargs="+", help=Msg.ml_help_delete, metavar="sm...")
    group_one.add_argument("-m", "--move", nargs="+", help=Msg.ml_help_move, metavar="sm...")
    group_one.add_argument("-c", "--copy", nargs="+", help=Msg.ml_help_copy, metavar="sm...")
    group_two = parser.add_argument_group(Msg.ml_help_group_b)
    group_two.add_argument("-s", "--show", action="store_true", help=Msg.ml_help_show)
    group_two.add_argument("-r", "--create", action="store_true", help=Msg.ml_help_create)
    group_two.add_argument("--purge", action="store_true", help=Msg.ml_help_purge)
    group_two.add_argument("-e", "--export", action="count", help=Msg.ml_help_export)
    group_one.add_argument("-o", "--out", nargs=1, help=Msg.ml_help_outfile, metavar="ファイル名")

    if len(argv) == 1:
        parser.print_help()
        exit()
    main(parser.parse_args())
