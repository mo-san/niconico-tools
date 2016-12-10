# coding: utf-8
import os
import pytest
import logging
from datetime import datetime

import nicotools
from nicotools import nicoml

SAVE_DIR = "/tests/Downloads/"
TEST_LIST = "TEST_LIST" + str(datetime.now()).replace(" ", "_")
TEST_LIST_TO = "TEST_LIST_TO" + str(datetime.now()).replace(" ", "_")
AUTH_N = (os.getenv("addr_n"), os.getenv("pass_n"))
VIDEO_IDS = {
    "watch/sm8628149": "【東方】Bad Apple!!　ＰＶ【影絵】",
    "watch/sm9": "新・豪血寺一族 -煩悩解放 - レッツゴー！陰陽師",
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
VIDEO_IDS = " ".join(list(VIDEO_IDS.keys()))
list_id = 0
list_name = ""
list_id_to = 0
list_name_to = ""
it = None  # type: nicoml.NicoMyList


class TestMla:
    def initialize(self):
        global it, list_id, list_name, list_id_to, list_name_to
        it = nicoml.NicoMyList(AUTH_N[0], AUTH_N[1])
        list_id, list_name = self.get_id_name(TEST_LIST)
        list_id_to, list_name_to = self.get_id_name(TEST_LIST_TO)

    def get_id_name(self, name):
        result = it._get_list_id(name)
        if result.get("error"):
            self.create(name)
            return self.get_id_name(name)
        return result["list_id"], result["list_name"]

    def create(self, name):
        it.create_mylist(name)

    def purge(self, name):
        it.purge_mylist(name, True)

    def param(self, cond):
        cond = "mylist -u {_mail} -p {_pass} " + cond
        return cond.format(_mail=AUTH_N[0], _pass=AUTH_N[1]).split(" ")

    def nicoml_add_1(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --add {1}".format(list_name, VIDEO_IDS)
        assert nicotools.main(self.param(c))

    def nicoml_add_2(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --id --add {1}".format(list_id, VIDEO_IDS)
        assert nicotools.main(self.param(c))

    def nicoml_add_3(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --add +ids.txt".format(list_name)
        assert nicotools.main(self.param(c))

    def nicoml_del_1(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --delete {1}".format(list_name, VIDEO_IDS)
        assert nicotools.main(self.param(c))

    def nicoml_del_2(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --delete * --yes".format(list_name)
        assert nicotools.main(self.param(c))

    def nicoml_move_1(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --to {1} --move {2}".format(list_name, list_name_to, VIDEO_IDS)
        assert nicotools.main(self.param(c))

    def nicoml_move_2(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --to {1} --move *".format(list_name, list_name_to)
        assert nicotools.main(self.param(c))

    def nicoml_copy_1(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --to {1} --copy {2}".format(list_name_to, list_name, VIDEO_IDS)
        assert nicotools.main(self.param(c))

    def nicoml_copy_2(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --to {1} --copy *".format(list_name_to, list_name)
        assert nicotools.main(self.param(c))

    def test_amcdpr_1(self, caplog):
        caplog.set_level(logging.INFO)
        self.initialize()
        self.nicoml_add_1(caplog)
        self.nicoml_move_1(caplog)
        self.nicoml_copy_1(caplog)
        self.nicoml_del_1(caplog)
        self.test_okatadsuke()

    def test_amcdpr_2(self, caplog):
        caplog.set_level(logging.INFO)
        self.initialize()
        self.nicoml_add_2(caplog)
        self.nicoml_move_2(caplog)
        self.nicoml_copy_2(caplog)
        self.nicoml_del_2(caplog)
        self.test_okatadsuke()

    def test_okatadsuke(self):
        self.purge(list_name)
        self.purge(list_name_to)


class TestMlb:
    def get_id_name(self, name):
        result = it._get_list_id(name)
        if result.get("error"):
            it.create_mylist(name)
            return self.get_id_name(name)
        return result["list_id"], result["list_name"]

    def param(self, cond):
        cond = "mylist -u {_mail} -p {_pass} " + cond
        return cond.format(_mail=AUTH_N[0], _pass=AUTH_N[1]).split(" ")

    def test_initialize(self):
        global it, list_id, list_name, list_id_to, list_name_to
        it = nicoml.NicoMyList(AUTH_N[0], AUTH_N[1])
        list_id, list_name = self.get_id_name(TEST_LIST)
        list_id_to, list_name_to = self.get_id_name(TEST_LIST_TO)

    def test_create_purge(self):
        c = "{0} --create".format(list_name)
        assert nicotools.main(self.param(c))
        c = "{0} --id --export".format(list_id)
        assert nicotools.main(self.param(c))
        c = "{0} --id --show".format(list_id)
        assert nicotools.main(self.param(c))
        c = "{0} --id --purge --yes".format(list_id)
        assert nicotools.main(self.param(c))

    def test_export_everything(self):
        c = "* --export --everything"
        assert nicotools.main(self.param(c))

    def test_export_meta(self):
        c = "* --export"
        assert nicotools.main(self.param(c))

    def test_show_meta(self):
        c = "* --show"
        assert nicotools.main(self.param(c))

    def test_show_everything_tsv(self):
        c = "* --show --everything"
        assert nicotools.main(self.param(c))

    def test_show_everything_table(self):
        c = "* --show --show --everything"
        assert nicotools.main(self.param(c))

    def test_okatadsuke(self):
        it.purge_mylist(list_name, True)
        it.purge_mylist(list_name_to, True)


class TestErrors:
    def initialize(self):
        global it, list_id, list_name, list_id_to, list_name_to
        it = nicoml.NicoMyList(AUTH_N[0], AUTH_N[1])
        list_id, list_name = self.get_id_name(TEST_LIST)
        list_id_to, list_name_to = self.get_id_name(TEST_LIST_TO)

    def get_id_name(self, name):
        result = it._get_list_id(name)
        if result.get("error"):
            it.create_mylist(name)
            return self.get_id_name(name)
        return result["list_id"], result["list_name"]

    def nicoml_add_1(self):
        c = "とりあえずマイリスト --add {0}".format(VIDEO_IDS)
        assert nicotools.main(self.param(c))

    def param(self, cond):
        cond = "mylist -u {_mail} -p {_pass} " + cond
        return cond.format(_mail=AUTH_N[0], _pass=AUTH_N[1]).split(" ")

    def test_prepare(self):
        self.initialize()
        self.nicoml_add_1()

    def test_add_all(self):
        with pytest.raises(SystemExit):
            c = "とりあえずマイリスト --add *"
            nicotools.main(self.param(c))

    def test_create_deflist(self):
        with pytest.raises(SystemExit):
            c = "とりあえずマイリスト --create"
            nicotools.main(self.param(c))

    def test_purge_deflist(self):
        with pytest.raises(SystemExit):
            c = "とりあえずマイリスト --purge"
            nicotools.main(self.param(c))

    def test_move_to_deflist(self):
        with pytest.raises(SystemExit):
            c = "{0} --move * --to とりあえずマイリスト".format(list_name)
            nicotools.main(self.param(c))

    def test_copy_to_same(self):
        with pytest.raises(SystemExit):
            c = "{0} --copy * --to {0}".format(list_name)
            nicotools.main(self.param(c))

    def test_move_without_to(self):
        with pytest.raises(SystemExit):
            c = "とりあえずマイリスト --move *"
            nicotools.main(self.param(c))

    def test_copy_without_to(self):
        with pytest.raises(SystemExit):
            c = "とりあえずマイリスト --copy *"
            nicotools.main(self.param(c))

    def test_delete_ambiguous(self):
        with pytest.raises(SystemExit):
            c = "とりあえずマイリスト --delete sm9 *"
            nicotools.main(self.param(c))

    def test_no_commands(self):
        with pytest.raises(SystemExit):
            c = "とりあえずマイリスト"
            nicotools.main(self.param(c))

    def test_list_not_exists(self):
        c = "🕒🕘🕒🕘 --show"
        assert nicotools.main(self.param(c)) is False

    def test_item_not_exists(self):
        c = "🕒🕘🕒🕘 --create"
        nicotools.main(self.param(c))
        c = "🕒🕘🕒🕘 --delete {0}".format(VIDEO_IDS)
        assert nicotools.main(self.param(c)) is False

    def nicoml_del_from_deflist(self):
        c = "とりあえずマイリスト --delete {0}".format(VIDEO_IDS)
        nicotools.main(self.param(c))

    def test_okatadsuke(self):
        self.nicoml_del_from_deflist()
        it.purge_mylist(list_name, True)
        it.purge_mylist(list_name_to, True)
