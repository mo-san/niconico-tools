# coding: utf-8
import logging
import os
import pytest

from nicotools.nicodown import GetVideos, GetComments, GetThumbnails, get_infos
from nicotools.utils import get_encoding, validator, LogIn, NTLogger
import nicotools

SAVE_DIR = "D:/Projects/PycharmProjects/niconico-tools/test/Downloads/"

AUTH_N = (os.getenv("addr1"), os.getenv("pass1"))
AUTH_P = (os.getenv("addr2"), os.getenv("pass2"))


# @pytest.mark.skip
def test_get_encoding():
    assert get_encoding()


# @pytest.mark.skip
def test_validator():
    assert (validator(
        ["*", " http://www.nicovideo.jp/watch/sm123456",
         " sm1234 ", "watch/sm123456",
         " nm1234 ", "watch/nm123456",
         " so1234 ", "watch/so123456",
         " 123456 ", "watch/123456"]) ==
        ["*", "sm123456",
         "sm1234", "sm123456", "nm1234", "nm123456",
         "so1234", "so123456", "123456", "123456"])
    assert validator(["*", "sm9", "-d"]) == []


# @pytest.mark.skip
class TestLogin:
    def test_login_1(self, caplog):
        # noinspection PyUnusedLocal
        sess = LogIn(AUTH_P).session
        sess = LogIn().session
        caplog.set_level(logging.DEBUG)
        assert LogIn(AUTH_N, session=sess).token.startswith("25844085-")

    def test_login_2(self, caplog):
        sess = LogIn(AUTH_P).session
        caplog.set_level(logging.DEBUG)
        assert LogIn((None, None), session=sess).token.startswith("1608038-")

    def test_login_3(self, caplog):
        _ml_ = os.getenv("addr1")
        _pw_ = os.getenv("pass1")
        caplog.set_level(logging.DEBUG)
        assert LogIn((_ml_, _pw_)).token.startswith("25844085-")
        # assert LogIn((None, _pw_)).token.startswith("25844085-")
        # assert LogIn((_ml_, None)).token.startswith("25844085-")
        # assert LogIn((None, None)).token.startswith("25844085-")
        # for record in caplog.records:
        #     assert record.levelname == 'DEBUG'
        # assert 'wally' not in caplog.text
        # assert caplog.record_tuples == [("root", logging.DEBUG, "25844085")]


# @pytest.mark.skip
class TestNicodown:
    @staticmethod
    def param(cond):
        videoid = "so8999636 nm11028783 sm7174241 watch/1341499584 http://www.nicovideo.jp/watch/1278053154"
        return cond.format(_mail=AUTH_N[0], _pass=AUTH_N[1], save_dir=SAVE_DIR, videoid=videoid).split(" ")

    def test_nicodown_1(self):
        with pytest.raises(SystemExit):
            c = "d -u {_mail} -p {_pass} -d {save_dir} -i -o test/Downloads/info.xml {videoid}"
            nicotools.main(self.param(c))

    def test_nicodown_2(self):
        with pytest.raises(SystemExit):
            c = "d -u {_mail} -p {_pass} -d {save_dir} -i {videoid}"
            nicotools.main(self.param(c))

    def test_nicodown_3(self):
        with pytest.raises(SystemExit):
            c = "download -u {_mail} -p {_pass} -d {save_dir} {videoid}"
            nicotools.main(self.param(c))

    def test_nicodown_4(self, caplog):
        c = "download -u {_mail} -p {_pass} -d {save_dir} -ct {videoid}"
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname in ("INFO", "DEBUG")

    def test_nicodown_5(self, caplog):
        c = "download -u {_mail} -p {_pass} -d {save_dir} -ct +test/ids.txt"
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname in ("INFO", "DEBUG")

    def test_nicodown_6(self, caplog):
        c = "download -u {_mail} -p {_pass} -d {save_dir} -cx {videoid}"
        nicotools.main(self.param(c))
        for record in caplog.records:
            assert record.levelname in ("INFO", "DEBUG")

    def test_nicodown_7(self, caplog):
        c = "download -u {_mail} -p {_pass} -d {save_dir} -v {videoid}"
        a = c.format(_mail=AUTH_N[0], _pass=AUTH_N[1], save_dir=SAVE_DIR, videoid="sm7174241").split(" ")
        nicotools.main(a)
        for record in caplog.records:
            assert record.levelname in ("INFO", "DEBUG")

    def test_nicodown_8(self, caplog):
        c = "download -u {_mail} -p {_pass} -d {save_dir} -c {videoid}"
        a = c.format(_mail=AUTH_N[0], _pass=AUTH_N[1], save_dir="test/aaaaa", videoid="1278053154").split(" ")
        nicotools.main(a)
        for record in caplog.records:
            assert record.levelname in ("INFO", "DEBUG")

    def test_nicodown_9(self, caplog):
        c = "download -u {_mail} -p {_pass} -d {save_dir} -c {videoid}"
        a = c.format(_mail=AUTH_N[0], _pass=AUTH_N[1], save_dir="hello/world", videoid="1278053154").split(" ")
        nicotools.main(a)
        for record in caplog.records:
            assert record.levelname in ("INFO", "DEBUG")

    def test_nicodown_10(self):
        c = "download -u {_mail} -p {_pass} -d {save_dir} -c {videoid}"
        a = c.format(_mail=AUTH_N[0], _pass=AUTH_N[1], save_dir="nul", videoid="1278053154").split(" ")
        with pytest.raises(SystemExit):
            nicotools.main(a)

    def test_nicodown_11(self):
        with pytest.raises(SystemExit):
            nicotools.main()

    def test_nicodown_12(self):
        with pytest.raises(SystemExit):
            nicotools.main(["download"])

    def test_nicodown_13(self):
        with pytest.raises(SystemExit):
            nicotools.main(["download", "-c", "sm9", "-w"])

    def test_nicodown_14(self):
        with pytest.raises(SystemExit):
            nicotools.main(["download", "-c", "sm9", "hello"])


def test_logger():
    with pytest.raises(ValueError):
        NTLogger(log_level=-1)


# @pytest.mark.skip
class TestComment:
    def test_comment1(self):
        logger = NTLogger()
        videoid = "so14436608 nm11028783 sm12169079 watch/1341499584"
        database = get_infos(videoid.split(" "), logger)
        assert GetComments(AUTH_N, logger).start(database, SAVE_DIR)

    def test_comment_2(self):
        logger = NTLogger()
        database = get_infos(["nm11028783"], logger)
        assert GetComments(AUTH_N, logger).start(database, SAVE_DIR)

    def test_comment_3(self):
        logger = NTLogger()
        database = get_infos(["nm11028783"], logger)
        with pytest.raises(SystemExit):
            # noinspection PyTypeChecker
            GetComments(AUTH_N, logger).start(database, None)


# @pytest.mark.skip
class TestThumb:
    def test_thumbnail_1(self):
        videoid = "nm11028783 sm12169079 sm9269975"
        logger = NTLogger()
        database = get_infos(videoid.split(" "))
        assert GetThumbnails(logger).start(database, SAVE_DIR)

    def test_thumbnail_2(self):
        videoid = "nm11028783 sm12169079 sm9269975"
        database = get_infos(videoid.split(" "))
        assert GetThumbnails().start(database, SAVE_DIR)


# @pytest.mark.skip
class TestVideo:
    def test_video_normal(self):
        logger = NTLogger()
        videoid = "sm7174241"
        database = get_infos(videoid.split(" "), logger)
        assert GetVideos(AUTH_N, logger).start(database, SAVE_DIR)

    def test_video_premium(self):
        logger = NTLogger()
        videoid = "sm1978440 so8999636"
        database = get_infos(videoid.split(" "), logger)
        assert GetVideos(AUTH_P, logger).start(database, SAVE_DIR)


# test_video()
# test_comment()
# test_thumbnail()
