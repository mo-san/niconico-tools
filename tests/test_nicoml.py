# coding: UTF-8
import logging
import os
import random
import sys
import tempfile

import pytest

import nicotools

if sys.version_info[0] == 3 and sys.version_info[1] >= 5:
    if int(os.getenv("TEST_ASYNC", 0)):
        is_async = True
        waiting = 10
    else:
        waiting = 1
        is_async = False
    from nicotools import nicoml_async as nicoml, utils
else:
    is_async = False
    waiting = 1
    Info = None
    VideoDmc = None
    VideoSmile = None
    CommentAsync = None
    ThumbnailAsync = None
    from nicotools import nicoml, utils

# ランダムな8桁の数字
TEST_LIST = "TEST_{}".format(int(random.uniform(10**7, 10**8-1)))
TEST_LIST_TO = "TEST_TO_{}".format(int(random.uniform(10**7, 10**8-1)))
INSANE_NAME = "🕒🕘🕒🕘"  # 時計の絵文字4つ

# テスト用の一般会員の認証情報
AUTH_N = (os.getenv("addr_n"), os.getenv("pass_n"))

__ids = {
    "watch/sm9": "新・豪血寺一族 -煩悩解放 - レッツゴー！陰陽師",
    "watch/sm8628149": "【東方】Bad Apple!!　ＰＶ【影絵】",
    "watch/sm2057168": "M.C.ドナルドはダンスに夢中なのか？最終鬼畜道化師ドナルド・Ｍ",
    "watch/sm22954889": "幕末志士達のスマブラ６４実況プレイ",
    "watch/sm1097445": "【初音ミク】みくみくにしてあげる♪【してやんよ】",
    "watch/sm10780722": "おちゃめ機能　歌った",
    "watch/sm15630734": "『初音ミク』千本桜『オリジナル曲PV』",
    "watch/sm1715919": "初音ミク　が　オリジナル曲を歌ってくれたよ「メルト」",
    "watch/sm9354085": "自演乙",
    "watch/sm6188097": "【マリオ64実況】　奴が来る　伍【幕末志士】",
    "watch/sm2049295": "【 Silver Forest × U.N.オーエンは彼女なのか？ 】 −sweet little sister−",
    "watch/sm500873": "組曲『ニコニコ動画』 "
}
# "sm9 sm8628149 ... sm500873" のようにただの文字列
if is_async:
    VIDEO_ID = " ".join(list(__ids))
else:
    VIDEO_ID = " ".join(random.sample(list(__ids), 3))


def param(cond):
    cond = "mylist -l {_mail} -p {_pass} --loglevel DEBUG " + cond
    return cond.format(_mail=AUTH_N[0], _pass=AUTH_N[1]).split(" ")


@pytest.fixture(scope="class")
def instance():
    logger = utils.NTLogger(file_name=utils.LOG_FILE_ML, log_level=logging.DEBUG)
    return nicoml.NicoMyList(AUTH_N[0], AUTH_N[1], logger=logger)


# noinspection PyShadowingNames
@pytest.fixture(scope="class")
def id_and_name(instance):
    result = instance.get_list_id(TEST_LIST)
    if result.get("error"):
        instance.create_mylist(TEST_LIST)
        result = instance.get_list_id(TEST_LIST)

    class O:
        id = result["list_id"]
        name = result["list_name"]

        @classmethod
        def close(cls):
            # 終わったら片付けるための関数
            try:
                c = "{} --purge --id --yes".format(cls.id)
                nicotools.main(param(c))
            except utils.MylistNotFoundError:
                pass

    return O


# noinspection PyShadowingNames
@pytest.fixture(scope="class")
def id_and_name_to(instance):
    result = instance.get_list_id(TEST_LIST_TO)
    if result.get("error"):
        instance.create_mylist(TEST_LIST_TO)
        result = instance.get_list_id(TEST_LIST_TO)

    class O:
        id = result["list_id"]
        name = result["list_name"]

        @classmethod
        def close(cls):
            # 終わったら片付けるための関数
            try:
                c = "{} --purge --id --yes".format(cls.id)
                nicotools.main(param(c))
            except utils.MylistNotFoundError:
                pass
    return O


# noinspection PyShadowingNames
class TestNicoml:
    def test_nicoml_add_1(self, caplog, id_and_name):
        caplog.set_level(logging.DEBUG)
        c = "{} --add {}".format(id_and_name.name, VIDEO_ID)
        try:
            assert nicotools.main(param(c))
        except utils.MylistAPIError as error:
            if not error.ok:
                print(error, file=sys.stderr)

    def test_nicoml_move_1(self, caplog, id_and_name, id_and_name_to):
        caplog.set_level(logging.DEBUG)
        c = "{} --to {} --move {}".format(id_and_name.name, id_and_name_to.name, VIDEO_ID)
        try:
            assert nicotools.main(param(c))
        except utils.MylistAPIError as error:
            if not error.ok:
                print(error, file=sys.stderr)

    def test_nicoml_copy_1(self, caplog, id_and_name, id_and_name_to):
        caplog.set_level(logging.DEBUG)
        c = "{} --to {} --copy {}".format(id_and_name_to.name, id_and_name.name, VIDEO_ID)
        try:
            assert nicotools.main(param(c))
        except utils.MylistAPIError as error:
            if not error.ok:
                print(error, file=sys.stderr)

    def test_nicoml_del_1(self, caplog, id_and_name):
        caplog.set_level(logging.DEBUG)
        c = "{} --delete {}".format(id_and_name.name, VIDEO_ID)
        try:
            assert nicotools.main(param(c))
        except utils.MylistAPIError as error:
            if not error.ok:
                print(error, file=sys.stderr)

    def test_close(self, id_and_name, id_and_name_to):
        id_and_name.close()
        id_and_name_to.close()


# noinspection PyShadowingNames
class TestNicomlInAnotherWay:
    def test_nicoml_add_2(self, caplog, id_and_name):
        caplog.set_level(logging.DEBUG)
        c = "{} --id --add {}".format(id_and_name.id, VIDEO_ID)
        try:
            assert nicotools.main(param(c))
        except utils.MylistAPIError as error:
            if not error.ok:
                print(error, file=sys.stderr)

    def test_nicoml_move_2(self, caplog, id_and_name, id_and_name_to):
        caplog.set_level(logging.DEBUG)
        c = "{} --to {} --move *".format(id_and_name.name, id_and_name_to.name)
        try:
            assert nicotools.main(param(c))
        except utils.MylistAPIError as error:
            if not error.ok:
                print(error, file=sys.stderr)

    def test_nicoml_copy_2(self, caplog, id_and_name, id_and_name_to):
        caplog.set_level(logging.DEBUG)
        c = "{} --to {} --copy *".format(id_and_name_to.name, id_and_name.name)
        try:
            assert nicotools.main(param(c))
        except utils.MylistAPIError as error:
            if not error.ok:
                print(error, file=sys.stderr)

    def test_nicoml_del_2(self, caplog, id_and_name):
        caplog.set_level(logging.DEBUG)
        c = "{} --delete * --yes".format(id_and_name.name)
        try:
            assert nicotools.main(param(c))
        except utils.MylistAPIError as error:
            if not error.ok:
                print(error, file=sys.stderr)

    def test_close(self, id_and_name, id_and_name_to):
        id_and_name.close()
        id_and_name_to.close()


# noinspection PyShadowingNames
class TestNicomlDeflist:
    def test_add_to_deflist(self, caplog):
        caplog.set_level(logging.DEBUG)
        c = "{} --add {}".format("とりあえずマイリスト", VIDEO_ID)
        try:
            assert nicotools.main(param(c))
        except utils.MylistAPIError as error:
            if not error.ok:
                print(error, file=sys.stderr)

    def test_move_from_deflist(self, caplog, id_and_name_to):
        caplog.set_level(logging.DEBUG)
        c = "{} --to {} --move {}".format("とりあえずマイリスト", id_and_name_to.name, VIDEO_ID)
        try:
            assert nicotools.main(param(c))
        except utils.MylistAPIError as error:
            if not error.ok:
                print(error, file=sys.stderr)

    def test_copy_to_deflist(self, caplog, id_and_name_to):
        caplog.set_level(logging.DEBUG)
        c = "{} --to {} --copy {}".format(id_and_name_to.name, "とりあえずマイリスト", VIDEO_ID)
        try:
            assert nicotools.main(param(c))
        except utils.MylistAPIError as error:
            if not error.ok:
                print(error, file=sys.stderr)

    def test_show_everything_tsv(self, caplog):
        caplog.set_level(logging.DEBUG)
        c = "* --show --everything"
        try:
            assert nicotools.main(param(c))
        except utils.MylistAPIError as error:
            if not error.ok:
                print(error, file=sys.stderr)

    def test_del_from_deflist(self, caplog):
        caplog.set_level(logging.DEBUG)
        c = "{} --delete {}".format("とりあえずマイリスト", VIDEO_ID)
        try:
            assert nicotools.main(param(c))
        except utils.MylistAPIError as error:
            if not error.ok:
                print(error, file=sys.stderr)

    def test_close(self, id_and_name, id_and_name_to):
        id_and_name.close()
        id_and_name_to.close()


# noinspection PyShadowingNames
class TestOtherCommands:
    def test_create_purge(self, id_and_name):
        with tempfile.TemporaryDirectory(prefix=__name__) as tmpdirname:
            # c = "{} --create".format(id_and_name.name)
            # assert nicotools.main(param(c))
            c = "{} --id --export --out {}_export.txt".format(
                id_and_name.id, os.path.join(tmpdirname, id_and_name.name))
            assert nicotools.main(param(c))
            c = "{} --id --show".format(id_and_name.id)
            assert nicotools.main(param(c))
            c = "{} --id --show --show --out {}_show.txt".format(
                id_and_name.id, os.path.join(tmpdirname, id_and_name.name))
            assert nicotools.main(param(c))
            c = "{} --id --purge --yes".format(id_and_name.id)
            assert nicotools.main(param(c))

    def test_export_everything(self):
        c = "* --export --everything"
        assert nicotools.main(param(c))

    def test_export_meta(self):
        c = "* --export"
        assert nicotools.main(param(c))

    def test_show_meta_tsv(self):
        c = "* --show"
        assert nicotools.main(param(c))

    def test_show_meta_table(self):
        c = "* --show --show"
        assert nicotools.main(param(c))

    def test_show_everything_tsv(self):
        c = "* --show --everything"
        assert nicotools.main(param(c))

    def test_show_everything_table(self):
        c = "* --show --show --everything"
        assert nicotools.main(param(c))

    def test_close(self, id_and_name, id_and_name_to):
        id_and_name.close()
        id_and_name_to.close()


# noinspection PyShadowingNames
class TestErrors:
    def test_add_all(self):
        with pytest.raises(SystemExit):
            c = "とりあえずマイリスト --add *"
            nicotools.main(param(c))

    def test_create_deflist(self):
        with pytest.raises(SystemExit):
            c = "とりあえずマイリスト --create"
            nicotools.main(param(c))

    def test_purge_deflist(self):
        with pytest.raises(SystemExit):
            c = "とりあえずマイリスト --purge"
            nicotools.main(param(c))

    def test_copy_to_same(self):
        with pytest.raises(SystemExit):
            c = "{} --copy * --to {}".format("なまえ", "なまえ")
            nicotools.main(param(c))

    def test_move_without_to(self):
        with pytest.raises(SystemExit):
            c = "とりあえずマイリスト --move *"
            nicotools.main(param(c))

    def test_copy_without_to(self):
        with pytest.raises(SystemExit):
            c = "とりあえずマイリスト --copy *"
            nicotools.main(param(c))

    def test_delete_ambiguous(self):
        with pytest.raises(SystemExit):
            c = "とりあえずマイリスト --delete sm9 *"
            nicotools.main(param(c))

    def test_add_all_internal(self, instance):
        with pytest.raises(utils.MylistError):
            instance.add(utils.ALL_ITEM, "sm9")
        with pytest.raises(utils.MylistError):
            instance.add(utils.DEFAULT_ID, utils.ALL_ITEM)

    def test_delete_ambiguous_internal(self, instance):
        with pytest.raises(utils.MylistError):
            instance.delete(utils.DEFAULT_ID, utils.ALL_ITEM, "sm9")

    def test_copy_same_internal(self, instance):
        with pytest.raises(utils.MylistError):
            instance.copy(1, 1, utils.ALL_ITEM)

    def test_copy_ambiguous_internal(self, instance):
        with pytest.raises(utils.MylistError):
            instance.copy(utils.DEFAULT_ID, 1, utils.ALL_ITEM, "sm9")

    def test_create_allname_internal(self, instance):
        with pytest.raises(utils.MylistError):
            instance.create_mylist(utils.DEFAULT_NAME)

    def test_create_null_internal(self, instance):
        with pytest.raises(utils.MylistError):
            instance.create_mylist("")

    def test_purge_def_internal(self, instance):
        with pytest.raises(utils.MylistError):
            instance.purge_mylist(utils.DEFAULT_NAME)

    def test_purge_all_internal(self, instance):
        with pytest.raises(utils.MylistError):
            instance.create_mylist(utils.ALL_ITEM)

    def test_purge_null_internal(self, instance):
        with pytest.raises(utils.MylistError):
            instance.create_mylist("")

    def test_no_commands(self):
        with pytest.raises(SystemExit):
            c = "とりあえずマイリスト"
            nicotools.main(param(c))

    def test_list_not_exists_and_create_special_characters_name(self, instance):
        c = "{} --show".format(INSANE_NAME)
        with pytest.raises(utils.MylistNotFoundError):
            nicotools.main(param(c))
        instance.create_mylist(INSANE_NAME)
        # 作ったばかりなのでマイリストIDは、手持ちの中で最大。
        insane_id = max(instance.mylists)
        instance.purge_mylist(insane_id, confident=True)

    def test_delete_not_existing_items(self):
        c = "とりあえずマイリスト --add {}".format(VIDEO_ID)
        assert nicotools.main(param(c))

        c = "とりあえずマイリスト --delete {}".format(VIDEO_ID)
        assert nicotools.main(param(c))
        c = "とりあえずマイリスト --delete {}".format(VIDEO_ID)
        assert nicotools.main(param(c)) is False
