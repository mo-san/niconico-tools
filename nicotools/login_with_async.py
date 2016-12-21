# coding: utf-8
import asyncio
import re
from getpass import getpass
from pathlib import Path
from typing import Dict, Union

import aiohttp
from bs4 import BeautifulSoup

from nicotools import utils
from nicotools.utils import Msg, URL, Err, COOKIE_FILE_NAME


class LogInAsync:
    def __init__(self, loop: asyncio.AbstractEventLoop=None,
                 mail: str=None, password: str=None, session: aiohttp.ClientSession=None):
        self.is_login = False
        self._auth = None
        self.session = None  # type: aiohttp.ClientSession
        self.loop = loop or asyncio.get_event_loop()

        if session and not (mail or password):
            print("init:1")
            self.session = session
        elif not (session or mail or password):
            print("init:2")
            self.loop.run_until_complete(self.get_session())
        else:
            print("init:3")
            self._auth = self._ask_credentials(mail=mail, password=password)
            self.loop.run_until_complete(self.get_session(self._auth))

            # print("init:4")
            # self.token = self.loop.run_until_complete(self.get_token(self.session))
            # print(self.token)

    async def get_session(self, auth: Dict=None):
        print(locals())

        # 認証情報が渡ってきている⇔セッションがある
        if auth is not None:
            # 以前のセッションがあれば捨てて強制的にログインしに行く
            if self.session:
                self.session.close()
            session = aiohttp.ClientSession()
            print("get_session:1")
            # async with session.post(URL.URL_LogIn, params=auth) as res:
            # async with session.get(URL.URL_LogIn, allow_redirects=True) as resp:
            #     print(resp.url)
            #     response = await resp.text()
            #     url = self.login_url(response)
            # async with session.post(resp.url + url, params=auth) as resp_2:
            async with session.post(URL.URL_LogIn, params=auth) as resp_2:
                print(resp_2.url)
                response = await resp_2.text()
                print(response[response.find("<title>"):response.find("</title>")+8])
            with open("nicologin.html", "w", encoding="utf-8") as f:
                f.write(response)
            if self._we_have_logged_in(response):
                print("get_session:3")
                self.save_cookies(session.cookie_jar)
                self.is_login = True
            else:
                print("get_session:4")
                return await self.get_session(self._ask_credentials())
        else:
            session = aiohttp.ClientSession()
            print("get_session:2")
            self.load_cookies(session.cookie_jar)
        self.session = session
        return self.session

    def login_url(self, content: str):
        soup = BeautifulSoup(content, "html.parser")
        url = soup.select("#login_form")[0]["action"]
        print(url)
        return url

    def _we_have_logged_in(self, response: str) -> bool:
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

    async def get_token(self, session: aiohttp.ClientSession) -> str:
        """
        マイリストの操作に必要な"NicoAPI.token"を取ってくる。

        :param aiohttp.ClientSession session:
        :rtype: str
        """
        async with session.get(URL.URL_MyListTop) as resp:
            htmltext = await resp.text()
        try:
            fragment = htmltext.split("NicoAPI.token = \"")[1]
            return fragment[:fragment.find("\"")]
        except IndexError:
            self._auth = self._ask_credentials()
            session = await self.get_session(self._auth)
            return await self.get_token(session)

    @classmethod
    def _ask_credentials(cls, mail=None, password=None):
        """
        メールアドレスとパスワードをユーザーに求める。

        :param str mail: メールアドレス。
        :param str password: パスワード
        :rtype: dict[str, str]
        """
        ma, pw = mail, password
        try:
            if ma is None:
                r = re.compile("^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*$")
                while True:
                    print(Msg.input_mail)
                    ma = input("-=>")
                    if not ma: continue
                    if r.match(ma): break
            if pw is None:
                while True:
                    print(Msg.input_pass)
                    pw = getpass("-=>")
                    if pw: break
        except (EOFError, KeyboardInterrupt):
            exit(Err.keyboard_interrupt)
        return {
            "mail_tel": ma,
            "password": pw
        }

    @classmethod
    def save_cookies(cls, aiohttp_cookiejar: aiohttp.CookieJar,
                     file_name: Union[str, Path]=COOKIE_FILE_NAME) -> None:
        """
        クッキーを保存する。保存場所は基本的にユーザーのホームディレクトリ。
        """
        file_path = utils.make_dir(Path.home() / file_name)
        aiohttp_cookiejar.save(file_path=file_path)

    @classmethod
    def load_cookies(cls, aiohttp_cookiejar: aiohttp.CookieJar,
                     file_name: Union[str, Path]=COOKIE_FILE_NAME) -> None:
        """
        クッキーを読み込む。
        """
        file_path = utils.make_dir(Path.home() / file_name)
        aiohttp_cookiejar.load(file_path=file_path)
