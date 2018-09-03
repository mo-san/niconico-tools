# coding: UTF-8
import os
import random
import shutil
import sys
import tempfile
import time

import aiohttp
import pytest

import nicotools
from nicotools.nicodown import Video, Comment, Thumbnail, get_infos
from nicotools import utils

if sys.version_info >= (3, 5):
    if int(os.getenv("TEST_ASYNC", 0)):
        is_async = True
        waiting = 10
    else:
        waiting = 1
        is_async = False
    from nicotools.nicodown_async import Info, VideoDmc, VideoSmile
    from nicotools.nicodown_async import Comment as CommentAsync, Thumbnail as ThumbnailAsync
else:
    is_async = False
    waiting = 1
    Info = None
    VideoDmc = None
    VideoSmile = None
    CommentAsync = None
    ThumbnailAsync = None

SAVE_DIR_1 = "tests/downloads/"
SAVE_DIR_2 = "tests/downloads_async"

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
        "sm28492584": "【60fps】ぬるぬるフロッピーに入る ご注文はうさぎですか？OP",
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
        if is_async:
            cond = "download --nomulti -l {_mail} -p {_pass} -d {save_dir} --loglevel DEBUG " + cond
            time.sleep(1)
        else:
            cond = "download -l {_mail} -p {_pass} -d {save_dir} --loglevel DEBUG " + cond
        params = {"_mail": AUTH_N[0], "_pass": AUTH_N[1],
                  "save_dir": SAVE_DIR_1, "video_id": " ".join(rand(0))}
        params.update(kwargs)
        return nicotools.main(cond.format(**params).split(" "), async_=is_async)

    if is_async:
        def test_video_smile(self):
            c = "--smile -v {video_id}"
            assert self.send_param(c, video_id=rand()[0])

        def test_video_dmc(self):
            c = "--dmc -v {video_id}"
            assert self.send_param(c, video_id=rand()[0])

        def test_sleep_1(self):
            # アクセス制限回避のためすこし待つ
            time.sleep(waiting)

        def test_video_smile_more(self):
            c = "--smile --limit 10 -v {video_id}"
            assert self.send_param(c, video_id=rand()[0])

        def test_video_dmc_more(self):
            c = "--dmc --limit 10 -v {video_id}"
            assert self.send_param(c, video_id=rand()[0])

    else:
        def test_getthumbinfo_to_file_with_nonexist_id(self):
            with tempfile.TemporaryDirectory(prefix=__name__) as tmpdirname:
                c = "-i -o " + os.path.join(tmpdirname, "info.xml") + " sm1 {video_id}"
                assert self.send_param(c)

        def test_getthumbinfo_on_screen(self):
            c = "-i {video_id}"
            assert self.send_param(c)

        def test_video(self):
            c = "-v {video_id}"
            assert self.send_param(c, video_id=rand()[0])

        def test_thumbnail(self):
            c = "-t {video_id}"
            assert self.send_param(c)

        def test_other_directory(self):
            c = "-c {video_id}"
            assert self.send_param(c, save_dir=SAVE_DIR_2)

        def test_comment_thumbnail_1(self):
            c = "-ct {video_id}"
            assert self.send_param(c)

        def test_comment_in_xml(self):
            c = "-cx {video_id}"
            assert self.send_param(c)


class TestNicodownError:
    def send_param(self, cond, **kwargs):
        if isinstance(cond, str):
            cond = "download -l {_mail} -p {_pass} -d {save_dir} --loglevel DEBUG " + cond
            params = {"_mail"   : AUTH_N[0], "_pass": AUTH_N[1],
                      "save_dir": SAVE_DIR_1, "video_id": " ".join(rand(0))}
            params.update(kwargs)
            arg = cond.format(**params).split(" ")
        else:
            arg = cond
        return nicotools.main(arg, async_=is_async)

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


if is_async:
    class TestCommentAsync:
        def test_sleep(self):
            # アクセス制限回避のためすこし待つ
            time.sleep(waiting)

        def test_comment_single(self):
            try:
                db = Info(AUTH_N[0], AUTH_N[1], LOGGER).get_data(rand())
                assert CommentAsync().start(db, SAVE_DIR_2)
            except aiohttp.client_exceptions.ClientError:
                pass

        def test_comment_multi(self):
            try:
                db = Info(AUTH_N[0], AUTH_N[1], LOGGER).get_data(rand())
                assert CommentAsync().start(db, SAVE_DIR_2, xml=True)
            except aiohttp.client_exceptions.ClientError:
                pass

        def test_comment_without_directory(self):
            try:
                db = Info(AUTH_N[0], AUTH_N[1], LOGGER).get_data(rand())
                with pytest.raises(SyntaxError):
                    # noinspection PyTypeChecker
                    CommentAsync().start(db, None)
            except aiohttp.client_exceptions.ClientError:
                pass


    class TestThumbAsync:
        def test_sleep(self):
            # アクセス制限回避のためすこし待つ
            time.sleep(waiting)

        def test_thumbnail_single(self):
            try:
                db = Info(AUTH_N[0], AUTH_N[1], LOGGER).get_data(rand())
                assert ThumbnailAsync().start(db, SAVE_DIR_2)
            except aiohttp.client_exceptions.ClientError:
                pass

        def test_thumbnail_multi(self):
            try:
                db = Info(AUTH_N[0], AUTH_N[1], LOGGER).get_data(rand(0))
                assert ThumbnailAsync().start(db, SAVE_DIR_2)
            except aiohttp.client_exceptions.ClientError:
                pass


    class TestVideoSmile:
        def test_sleep(self):
            # アクセス制限回避のためすこし待つ
            time.sleep(waiting)

        def test_video_smile_normal_single(self):
            try:
                db = Info(AUTH_N[0], AUTH_N[1], LOGGER).get_data(rand())
                assert VideoSmile(multiline=False).start(db, SAVE_DIR_2)
            except aiohttp.client_exceptions.ClientError:
                pass

        def test_video_smile_premium_multi(self):
            if AUTH_P[0] is not None:
                try:
                    db = Info(AUTH_P[0], AUTH_P[1], LOGGER).get_data(rand(3))
                    assert VideoSmile(multiline=False).start(db, SAVE_DIR_2)
                except aiohttp.client_exceptions.ClientError:
                    pass


    class TestVideoDmc:
        def test_sleep(self):
            # アクセス制限回避のためすこし待つ
            time.sleep(waiting)

        def test_video_dmc_normal_single(self):
            try:
                db = Info(AUTH_N[0], AUTH_N[1], LOGGER).get_data(rand())
                assert VideoDmc(multiline=False).start(db, SAVE_DIR_2)
            except aiohttp.client_exceptions.ClientError:
                pass

        def test_video_dmc_premium_multi(self):
            if AUTH_P[0] is not None:
                try:
                    db = Info(AUTH_P[0], AUTH_P[1], LOGGER).get_data(rand(3))
                    assert VideoDmc(multiline=False).start(db, SAVE_DIR_2)
                except aiohttp.client_exceptions.ClientError:
                    pass

else:
    class TestComment:
        def test_comment_single(self):
            db = get_infos(rand()[0], LOGGER)
            assert Comment(AUTH_N[0], AUTH_N[1], LOGGER).start(db, SAVE_DIR_2)

        def test_comment_multi(self):
            db = get_infos(rand(0), LOGGER)
            assert Comment(AUTH_N[0], AUTH_N[1], LOGGER).start(db, SAVE_DIR_2, xml=True)

        def test_comment_without_directory(self):
            db = get_infos(rand()[0], LOGGER)
            with pytest.raises(SyntaxError):
                # noinspection PyTypeChecker
                Comment(AUTH_N[0], AUTH_N[1], LOGGER).start(db, None)


    class TestThumb:
        def test_thumbnail_single(self):
            db = get_infos(rand())
            assert Thumbnail(LOGGER).start(db, SAVE_DIR_2)

        def test_thumbnail_multi(self):
            db = get_infos(rand(0))
            assert Thumbnail(LOGGER).start(db, SAVE_DIR_2)

        def test_thumbnail_without_logger(self):
            db = get_infos(rand(0))
            assert Thumbnail().start(db, SAVE_DIR_2)


    class TestVideo:
        def test_video_normal_single(self):
            db = get_infos(rand()[0], LOGGER)
            assert Video(AUTH_N[0], AUTH_N[1], LOGGER).start(db, SAVE_DIR_2)

        def test_video_premium_multi(self):
            if AUTH_P[0] is not None:
                db = get_infos(rand(3), LOGGER)
                assert Video(AUTH_P[0], AUTH_P[1], LOGGER).start(db, SAVE_DIR_2)


def test_okatadsuke():
    for _parh in (SAVE_DIR_1, SAVE_DIR_2):
        shutil.rmtree(str(utils.make_dir(_parh)))
