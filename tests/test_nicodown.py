# coding: utf-8
import os
import pytest

import logging

import nicotools
from nicotools.nicodown import GetVideos, GetComments, GetThumbnails, get_infos
from nicotools.utils import get_encoding, validator, LogIn, NTLogger, make_dir

SAVE_DIR_1 = "./tests/downloads/"
SAVE_DIR_2 = "./tests/aaaaa"
OUTPUT = "tests/downloads/info.xml"
INPUT = "tests/ids.txt"
AUTH_N = (os.getenv("addr_n"), os.getenv("pass_n"))
AUTH_P = (os.getenv("addr_p"), os.getenv("pass_p"))

# "nm11028783 sm7174241 ... so8999636" のような文字列
VIDEO_ID = " ".join({
    "nm11028783": "[オリジナル曲] august [初音ミク]",
    "sm7174241": "【ピアノ楽譜】 Windows 起動音 [Win3.1 ～ Vista]",
    "sm12169079": "【初音ミク】なでなで【オリジナル】",
    "sm28492584": "【60fps】ぬるぬるフロッピーに入る ご注文はうさぎですか？OP",
    "sm30134391": "音声込みで26KBに圧縮されたスズメバチに刺されるゆうさく",
    "so8999636": "【初音ミク】「Story」 １９’s Sound Factory",
    "watch/1278053154": "「カラフル×メロディ」　オリジナル曲　vo.初音ミク＆鏡音リン【Project DIVA 2nd】",
    "http://www.nicovideo.jp/watch/1341499584": "【sasakure.UK×DECO*27】39【Music Video】",
})
LOGGER = NTLogger(log_level=logging.DEBUG)


class TestUtils:
    def test_get_encoding(self):
        assert get_encoding()

    def test_validator(self):
        assert (validator(
            ["*", " http://www.nicovideo.jp/watch/1341499584",
             " sm1234 ", "watch/sm123456",
             " nm1234 ", "watch/nm123456",
             " so1234 ", "watch/so123456",
             " 123456 ", "watch/1278053154"]) ==
            ["*", "1341499584",
             "sm1234", "sm123456",
             "nm1234", "nm123456",
             "so1234", "so123456",
             "123456", "1278053154"])
        assert validator(["*", "sm9", "-d"]) == []

    def test_logger(self):
        with pytest.raises(ValueError):
            NTLogger(log_level=-1)


class TestLogin:
    def test_login_1(self):
        _ = LogIn(*AUTH_P).session
        sess = LogIn().session
        assert LogIn(*AUTH_N, session=sess).is_login is True

    def test_login_2(self):
        sess = LogIn(*AUTH_P).session
        assert "-" in LogIn(None, None, session=sess).token

    def test_login_3(self):
        assert "-" in LogIn(*AUTH_N).token


class TestNicodown:
    def param(self, cond, **kwargs):
        cond = "download -u {_mail} -p {_pass} -d {save_dir} " + cond
        params = {"_mail": AUTH_N[0], "_pass": AUTH_N[1],
                  "save_dir": SAVE_DIR_1, "video_id": VIDEO_ID}
        params.update(kwargs)
        return cond.format(**params).split(" ")

    def test_getthumbinfo_to_file_with_nonexist_id(self):
        c = "-i -o " + OUTPUT + " sm1 {video_id}"
        assert nicotools.main(self.param(c))

    def test_getthumbinfo_on_screen(self):
        c = "-i {video_id}"
        assert nicotools.main(self.param(c))

    def test_without_commands(self):
        with pytest.raises(SystemExit):
            c = "{video_id}"
            nicotools.main(self.param(c))

    def test_invalid_directory_on_windows(self):
        if os.name == "nt":
            c = "-c {video_id}"
            with pytest.raises(OSError):
                nicotools.main(self.param(c, save_dir="nul"))

    def test_no_args(self):
        with pytest.raises(SystemExit):
            nicotools.main()

    def test_one_arg(self):
        with pytest.raises(SystemExit):
            nicotools.main(["download"])

    def test_what_command(self):
        with pytest.raises(SystemExit):
            nicotools.main(["download", "-c", "sm9", "-w"])

    def test_invalid_videoid(self):
        with pytest.raises(SystemExit):
            nicotools.main(["download", "-c", "sm9", "hello"])

    def test_video(self):
        c = "-v {video_id}"
        nicotools.main(self.param(c, video_id=VIDEO_ID.split(" ")[0]))

    def test_thumbnail(self):
        c = "-t {video_id}"
        nicotools.main(self.param(c))

    def test_other_directory(self):
        c = "-c {video_id}"
        nicotools.main(self.param(c, save_dir=SAVE_DIR_2))

    def test_comment_thumbnail_1(self):
        c = "-ct {video_id}"
        nicotools.main(self.param(c))

    def test_comment_thumbnail_2(self):
        c = "-ct +" + INPUT
        nicotools.main(self.param(c))

    def test_comment_in_xml(self):
        c = "-cx {video_id}"
        nicotools.main(self.param(c))


class TestComment:
    def test_comment_single(self):
        db = get_infos([VIDEO_ID.split(" ")[0]], LOGGER)
        assert GetComments(AUTH_N[0], AUTH_N[1], LOGGER).start(db, SAVE_DIR_1)

    def test_comment_multi(self):
        db = get_infos(VIDEO_ID.split(" "), LOGGER)
        assert GetComments(AUTH_N[0], AUTH_N[1], LOGGER).start(db, SAVE_DIR_1, xml=True)

    def test_comment_without_directory(self):
        db = get_infos([VIDEO_ID.split(" ")[0]], LOGGER)
        with pytest.raises(ValueError):
            # noinspection PyTypeChecker
            GetComments(AUTH_N[0], AUTH_N[1], LOGGER).start(db, None)


class TestThumb:
    def test_thumbnail_single(self):
        db = get_infos([VIDEO_ID.split(" ")[0]])
        assert GetThumbnails(LOGGER).start(db, SAVE_DIR_1)

    def test_thumbnail_multi(self):
        db = get_infos(VIDEO_ID.split(" "))
        assert GetThumbnails(LOGGER).start(db, SAVE_DIR_1)

    def test_thumbnail_without_logger(self):
        db = get_infos(VIDEO_ID.split(" "))
        assert GetThumbnails().start(db, SAVE_DIR_1)


class TestVideo:
    def test_video_normal_single(self):
        db = get_infos([VIDEO_ID.split(" ")[0]], LOGGER)
        assert GetVideos(AUTH_N[0], AUTH_N[1], LOGGER).start(db, SAVE_DIR_1)

    def test_video_premium_multi(self):
        db = get_infos(VIDEO_ID.split(" ")[0:2], LOGGER)
        assert GetVideos(AUTH_P[0], AUTH_P[1], LOGGER).start(db, SAVE_DIR_1)


def test_okatadsuke():
    import shutil
    for _parh in (SAVE_DIR_1, SAVE_DIR_2):
        shutil.rmtree(str(make_dir(_parh)))

# test_video()
# test_comment()
# test_thumbnail()
