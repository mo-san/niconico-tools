# coding: UTF-8
import os
import random
import shutil
import time

import aiohttp
import pytest

import nicotools
from nicotools import utils
from nicotools.download import Info, VideoDmc, VideoSmile, Comment, Thumbnail

Waiting = 10
SAVE_DIR = "tests/downloads/"

# "N" は一般会員の認証情報、 "P" はプレミアム会員の認証情報
AUTH_N = (os.getenv("addr_n"), os.getenv("pass_n"))
AUTH_P = (os.getenv("addr_p"), os.getenv("pass_p"))
LOGGER = utils.NTLogger(log_level=10)


def rand(num=1):
    """
    動画IDをランダムに取り出す。0を指定すると全てを返す。

    "nm11028783 sm7174241 ... so8999636" のリスト
    :param int num:
    :rtype: list[str]
    """
    video_id = list({
        "nm11028783": "[オリジナル曲] august [初音ミク]",
        "sm7174241": "【ピアノ楽譜】 Windows 起動音 [Win3.1 ～ Vista]",
        "sm12169079": "【初音ミク】なでなで【オリジナル】",
        "sm1097445": "【初音ミク】みくみくにしてあげる♪【してやんよ】",
        "sm30134391": "音声込みで26KBに圧縮されたスズメバチに刺されるゆうさく",
        "so8999636": "【初音ミク】「Story」 １９’s Sound Factory",
        "watch/1278053154": "「カラフル×メロディ」　オリジナル曲　vo.初音ミク＆鏡音リン【Project DIVA 2nd】",
        "http://www.nicovideo.jp/watch/1341499584": "【sasakure.UK×DECO*27】39【Music Video】",
    })

    if num == 0:
        return video_id
    else:
        return random.sample(video_id, num)


class TestUtils:
    def test_get_encoding(self):
        assert utils.get_encoding()

    def test_validator(self):
        assert utils.validator(["*", "sm9", "-d"]) == []
        assert (set(utils.validator(
            ["*", " http://www.nicovideo.jp/watch/1341499584",
             " sm1234 ", "watch/sm123456",
             " nm1234 ", "watch/nm123456",
             " so1234 ", "watch/so123456",
             " 123456 ", "watch/1278053154"])) ==
            {"*", "1341499584",
             "sm1234", "sm123456",
             "nm1234", "nm123456",
             "so1234", "so123456",
             "123456", "1278053154"})

    def test_make_dir(self):
        save_dir = ["test", "foo", "foo/bar", "some/thing/text.txt"]
        paths = [utils.make_dir(name) for name in save_dir]
        try:
            for participant, result in zip(save_dir, paths):
                assert str(result).replace("\\", "/").replace("//", "/").endswith(participant)
        finally:
            try:
                for _parh in {item.split("/")[0] for item in save_dir}:
                    shutil.rmtree(_parh)
            except FileNotFoundError:
                pass


class TestUtilsError:
    def test_logger(self):
        with pytest.raises(ValueError):
            # noinspection PyTypeChecker
            utils.NTLogger(log_level=None)

    def test_make_dir(self):
        if os.name == "nt":
            save_dir = ["con", ":"]
            for name in save_dir:
                with pytest.raises(NameError):
                    utils.make_dir(name)
        else:
            with pytest.raises(NameError):
                utils.make_dir("/{}/downloads".format(__name__))


class TestLogin:
    def test_login_1(self):
        if AUTH_P[0] is not None:
            _ = utils.LogIn(*AUTH_P).session
            sess = utils.LogIn().session
            assert utils.LogIn(*AUTH_N, session=sess).is_login is True

    def test_login_2(self):
        if AUTH_P[0] is not None:
            sess = utils.LogIn(*AUTH_P).session
            assert "-" in utils.LogIn(None, None, session=sess).token

    def test_login_3(self):
        assert "-" in utils.LogIn(*AUTH_N).token


class TestNicodown:
    def send_param(self, cond, **kwargs):
        cond = "download --nomulti -l {_mail} -p {_pass} -d {save_dir} --loglevel DEBUG " + cond
        params = {"_mail"   : AUTH_N[0], "_pass": AUTH_N[1],
                  "save_dir": SAVE_DIR, "video_id": " ".join(rand(0))}
        params.update(kwargs)
        time.sleep(1)
        return nicotools.main(cond.format(**params).split(" "))

    def test_video_smile(self):
        c = "--smile -v {video_id}"
        assert self.send_param(c, video_id=rand()[0])

    def test_video_dmc(self):
        c = "--dmc -v {video_id}"
        assert self.send_param(c, video_id=rand()[0])

    def test_sleep_1(self):
        # アクセス制限回避のためすこし待つ
        time.sleep(Waiting)

    def test_video_smile_more(self):
        c = "--smile --limit 10 -v {video_id}"
        assert self.send_param(c, video_id=rand()[0])

    def test_video_dmc_more(self):
        c = "--dmc --limit 10 -v {video_id}"
        assert self.send_param(c, video_id=rand()[0])


class TestNicodownError:
    def send_param(self, cond, **kwargs):
        arg = cond
        if isinstance(cond, str):
            cond = "download -l {_mail} -p {_pass} -d {save_dir} --loglevel DEBUG " + cond
            params = {"_mail"   : AUTH_N[0], "_pass": AUTH_N[1],
                      "save_dir": SAVE_DIR, "video_id": " ".join(rand(0))}
            params.update(kwargs)
            arg = cond.format(**params).split(" ")
        return nicotools.main(arg)

    def test_without_commands(self):
        with pytest.raises(SystemExit):
            c = "{video_id}"
            self.send_param(c)

    def test_invalid_directory_on_windows(self):
        if os.name == "nt":
            c = "-c {video_id}"
            with pytest.raises(NameError):
                self.send_param(c, save_dir="nul")

    def test_no_args(self):
        with pytest.raises(SystemExit):
            self.send_param(None)

    def test_one_arg(self):
        with pytest.raises(SystemExit):
            self.send_param(["download"])

    def test_what_command(self):
        with pytest.raises(SystemExit):
            self.send_param(["download", "-c", "sm9", "-w"])

    def test_invalid_videoid(self):
        with pytest.raises(SystemExit):
            self.send_param(["download", "-c", "sm9", "hello"])


class TestThumbAsync:
    def test_sleep(self):
        # アクセス制限回避のためすこし待つ
        time.sleep(Waiting)

    def test_thumbnail_single(self):
        try:
            db = Info(AUTH_N[0], AUTH_N[1], LOGGER).get_data(rand())
            assert Thumbnail().start(db, SAVE_DIR)
        except aiohttp.client_exceptions.ClientError:
            pass

    def test_thumbnail_multi(self):
        try:
            db = Info(AUTH_N[0], AUTH_N[1], LOGGER).get_data(rand(0))
            assert Thumbnail().start(db, SAVE_DIR)
        except aiohttp.client_exceptions.ClientError:
            pass


class TestCommentAsync:
    def test_sleep(self):
        # アクセス制限回避のためすこし待つ
        time.sleep(Waiting)

    def test_comment_single(self):
        try:
            db = Info(AUTH_N[0], AUTH_N[1], LOGGER).get_data(rand())
            assert Comment().start(db, SAVE_DIR)
        except aiohttp.client_exceptions.ClientError:
            pass

    def test_comment_multi(self):
        try:
            db = Info(AUTH_N[0], AUTH_N[1], LOGGER).get_data(rand())
            assert Comment().start(db, SAVE_DIR, xml=True)
        except aiohttp.client_exceptions.ClientError:
            pass

    def test_comment_without_directory(self):
        try:
            db = Info(AUTH_N[0], AUTH_N[1], LOGGER).get_data(rand())
            with pytest.raises(SyntaxError):
                # noinspection PyTypeChecker
                Comment().start(db, None)
        except aiohttp.client_exceptions.ClientError:
            pass


class TestVideoSmile:
    def test_sleep(self):
        # アクセス制限回避のためすこし待つ
        time.sleep(Waiting)

    def test_video_smile_normal_single(self):
        try:
            db = Info(AUTH_N[0], AUTH_N[1], LOGGER).get_data(rand())
            assert VideoSmile(multiline=False).start(db, SAVE_DIR)
        except aiohttp.client_exceptions.ClientError:
            pass

    def test_video_smile_premium_multi(self):
        if AUTH_P[0] is not None:
            try:
                db = Info(AUTH_P[0], AUTH_P[1], LOGGER).get_data(rand(3))
                assert VideoSmile(multiline=False).start(db, SAVE_DIR)
            except aiohttp.client_exceptions.ClientError:
                pass


class TestVideoDmc:
    def test_sleep(self):
        # アクセス制限回避のためすこし待つ
        time.sleep(Waiting)

    def test_video_dmc_normal_single(self):
        try:
            db = Info(AUTH_N[0], AUTH_N[1], LOGGER).get_data(rand())
            assert VideoDmc(multiline=False).start(db, SAVE_DIR)
        except aiohttp.client_exceptions.ClientError:
            pass

    def test_video_dmc_premium_multi(self):
        if AUTH_P[0] is not None:
            try:
                db = Info(AUTH_P[0], AUTH_P[1], LOGGER).get_data(rand(3))
                assert VideoDmc(multiline=False).start(db, SAVE_DIR)
            except aiohttp.client_exceptions.ClientError:
                pass


def test_okatadsuke():
    shutil.rmtree(str(utils.make_dir(SAVE_DIR)))
