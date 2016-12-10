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
it = None


# @pytest.mark.skip
# noinspection PyAttributeOutsideInit
class TestMla:
    def initialize(self):
        global it, list_id, list_name, list_id_to, list_name_to
        it = nicoml.NicoMyList(AUTH_N)
        list_id, list_name = self.get_id_name(TEST_LIST)
        list_id_to, list_name_to = self.get_id_name(TEST_LIST_TO)

    def get_id_name(self, name):
        target = it._get_id(name)
        if target[0] == -1:
            self.create(name)
            return self.get_id_name(name)
        return target

    def create(self, name):
        it.create_mylist(name)

    def purge(self, name):
        it.purge_mylist(name, True)

    @staticmethod
    def param(cond):
        cond = "mylist -u {_mail} -p {_pass} " + cond
        return cond.format(_mail=AUTH_N[0], _pass=AUTH_N[1]).split(" ")

    def nicoml_add_1(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --add {1}".format(list_name, VIDEO_IDS)
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname == "INFO"

    def nicoml_add_2(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --id --add {1}".format(list_id, VIDEO_IDS)
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname == "INFO"

    def nicoml_add_3(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --add +ids.txt".format(list_name)
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname == "INFO"

    def nicoml_del_1(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --delete {1}".format(list_name, VIDEO_IDS)
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname == "INFO"

    def nicoml_del_2(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --delete * --yes".format(list_name)
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname == "INFO"

    def nicoml_move_1(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --to {1} --move {2}".format(list_name, list_name_to, VIDEO_IDS)
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname == "INFO"

    def nicoml_move_2(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --to {1} --move *".format(list_name, list_name_to)
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname == "INFO"

    def nicoml_copy_1(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --to {1} --copy {2}".format(list_name_to, list_name, VIDEO_IDS)
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname == "INFO"

    def nicoml_copy_2(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --to {1} --copy *".format(list_name_to, list_name)
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname == "INFO"

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


# noinspection PyAttributeOutsideInit
class TestMlb:
    def initialize(self):
        global it, list_id, list_name, list_id_to, list_name_to
        it = nicoml.NicoMyList(AUTH_N)
        list_id, list_name = self.get_id_name(TEST_LIST)

    def get_id_name(self, name):
        target = it._get_id(name)
        if target[0] == -1:
            self.create()
            return self.get_id_name(name)
        return target

    def create(self):
        it.create_mylist(TEST_LIST)

    def purge(self):
        it.purge_mylist(TEST_LIST, True)

    @staticmethod
    def param(cond):
        cond = "mylist -u {_mail} -p {_pass} " + cond
        return cond.format(_mail=AUTH_N[0], _pass=AUTH_N[1]).split(" ")

    def ml_create(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --create".format(list_name)
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname == "INFO"

    def ml_purge(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --purge --yes".format(list_name)
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname == "INFO"

    def test_cp(self, caplog):
        self.ml_create(caplog)
        self.ml_purge(caplog)

    def test_export_everything(self, caplog):
        caplog.set_level(logging.INFO)
        c = "* --export --everything"
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname == "INFO"

    def test_export_meta(self, caplog):
        caplog.set_level(logging.INFO)
        c = "* --export"
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname == "INFO"

    def test_export_once(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --export".format(list_name)
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname == "INFO"

    def test_show_meta(self, caplog):
        caplog.set_level(logging.INFO)
        c = "* --show"
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname == "INFO"

    def test_show_once(self, caplog):
        caplog.set_level(logging.INFO)
        c = "{0} --show".format(list_name)
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname == "INFO"

    def test_show_everything_tsv(self, caplog):
        caplog.set_level(logging.INFO)
        c = "* --show --everything"
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname == "INFO"

    def test_show_everything_table(self, caplog):
        caplog.set_level(logging.INFO)
        c = "* --show --show --everything"
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname == "INFO"


@pytest.mark.skip
class TestErrors:
    @staticmethod
    def param(cond):
        cond = "mylist -u {_mail} -p {_pass} " + cond
        return cond.format(_mail=AUTH_N[0], _pass=AUTH_N[1]).split(" ")

    def test_nicoml_1(self, caplog):
        caplog.set_level(logging.INFO)
        c = ""
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname == "INFO"

    def test_nicoml_2(self, caplog):
        caplog.set_level(logging.INFO)
        c = ""
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname == "INFO"
