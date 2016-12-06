# coding: utf-8
import logging
import requests
from requests.cookies import RequestsCookieJar
from typing import Optional, Union, Dict, TypeVar, Tuple, List

LoggerType = TypeVar("LoggerType", bound=logging.Logger)

def get_encoding() -> str: ...
def validator(input_list: List[str]) -> List[str]: ...


class URL:
    URL_LogIn  = ...  # type: str
    URL_Watch  = ...  # type: str
    URL_GetFlv = ...  # type: str
    URL_Info   = ...  # type: str
    URL_Pict   = ...  # type: str
    URL_GetThreadKey = ...  # type: str
    URL_Message_New = ...  #type: str

    URL_MyListTop  = ...  # type: str
    URL_ListAll    = ...  # type: str
    URL_AddMyList  = ...  # type: str
    URL_PurgeList  = ...  # type: str
    URL_ListOne    = ...  # type: str
    URL_AddItem    = ...  # type: str
    URL_DeleteItem = ...  # type: str
    URL_CopyItem   = ...  # type: str
    URL_MoveItem   = ...  # type: str
    URL_UpdateItem = ...  # type: str

    URL_ListDef   = ...  # type: str
    URL_AddDef    = ...  # type: str
    URL_DeleteDef = ...  # type: str
    URL_CopyDef   = ...  # type: str
    URL_MoveDef   = ...  # type: str
    URL_UpdateDef = ...  # type: str


class Msg:
    LOG_FILE_ND = ...  # type: str
    LOG_FILE_ML = ...  # type: str
    COOKIE_FILE_NAME = ...  # type: str
    ALL_ITEM = ...  # type: str

    BACKSLASH = ...  # type: str
    CHARREF = ...  # type: str
    REPLACE = ...  # type: str


class Err:
    MAXERROR = ...  # type: str
    EXIST = ...  # type: str
    NONEXIST = ...  # type: str

    COMMANDERROR = ...  # type: str
    PARAMERROR = ...  # type: str
    INVALIDTOKEN = ...  # type: str
    EXPIRETOKEN = ...  # type: str
    NOAUTH = ...  # type: str
    SECRETUSER = ...  # type: str
    INVALIDUSER = ...  # type: str
    INVALIDVIDEO = ...  # type: str

    MAINTENANCE = ...  # type: str
    INTERNAL = ...  # type: str


class LogIn:
    def __init__(self, auth: Tuple[Optional[str], Optional[str]],
                 logger:LoggerType=..., session: requests.Session=...) -> None:
        self.session = ...  #type: Optional[requests.Session]
        self.token = ...  # type: Optional[str]
        self.auth = ...  # type: Optional[Dict[str, str]]
        self.logger = ...  #type: Optional[NDLogger]
        self.is_silent = ...  # type: bool
    class AltLogger:
        def emitter(self, text: str, err: bool=..., en: str=...) -> None: ...
        def debug(self, text: str) -> None: ...
        def info(self, text: str) -> None: ...
        def error(self, text: str) -> None: ...
        def warning(self, text: str) -> None: ...
        def critical(self, text: str) -> None: ...

    def get_session(self, force_login: bool=...) -> requests.Session: ...
    def get_token(self) -> str: ...
    def get_credentials(self, mail: str=..., password: str=...) -> Dict[str, str]: ...
    def save_cookies(self, requests_cookiejar: RequestsCookieJar,
                     file_name: str=...) -> None: ...
    def load_cookies(self, file_name: str=...) -> RequestsCookieJar: ...


class NDLogger(logging.Logger):
    def __init__(self, file_name: str=..., name: str=...,
                 log_level: Union[str, int]=logging.INFO):
        self.enco = ...  # type: str
        self.log_level = ...  # type: str
        self.logger = ...  #type: logging.Logger
        logging.Logger.__init__(self, name, log_level)
    def forwarding(self, level: int, msg: str, *args, **kwargs) -> None: ...
    def debug(self, msg: str, *args, **kwargs) -> None: ...
    def info(self, msg: str, *args, **kwargs): ...
    def warning(self, msg: str, *args, **kwargs): ...
    def error(self, msg: str, *args, **kwargs): ...
    def critical(self, msg: str, *args, **kwargs): ...


class Key:
    CH_ID           = ...  # type: str
    CH_NAME         = ...  # type: str
    CH_ICON_URL     = ...  # type: str
    COMMENT_NUM     = ...  # type: str
    FIRST_RETRIEVE  = ...  # type: str
    DELETED         = ...  # type: str
    DESCRIPTION     = ...  # type: str
    EMBEDDABLE      = ...  # type: str
    FILE_NAME       = ...  # type: str
    LAST_RES_BODY   = ...  # type: str
    LENGTH          = ...  # type: str
    LENGTH_SECONDS  = ...  # type: str
    NUM_RES         = ...  # type: str
    MYLIST_COUNTER  = ...  # type: str
    MOVIE_TYPE      = ...  # type: str
    NO_LIVE_PLAY    = ...  # type: str
    SIZE_HIGH       = ...  # type: str
    SIZE_LOW        = ...  # type: str
    TAGS            = ...  # type: str
    TAGS_LIST       = ...  # type: str
    THUMBNAIL_URL   = ...  # type: str
    TITLE           = ...  # type: str
    USER_ID         = ...  # type: str
    USER_NAME       = ...  # type: str
    USER_ICON_URL   = ...  # type: str
    VIDEO_ID        = ...  # type: str
    VIEW_COUNTER    = ...  # type: str

class MKey:
    ID = ...  # type: str
    NAME = ...  # type: str
    IS_PUBLIC = ...  # type: str
    PUBLICITY = ...  # type: str
    SINCE = ...  # type: str
    DESCRIPTION = ...  # type: str
    ITEM_DATA = ...  # type: str
