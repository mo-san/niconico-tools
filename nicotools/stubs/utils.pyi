# coding: UTF-8
from requests.cookies import RequestsCookieJar
from typing import Optional, Union, Dict, TypeVar, Tuple, List, Any, Set
import asyncio
import logging
from pathlib import Path

import requests

LoggerType = TypeVar("NTLogger", bound=logging.Logger)

ALL_ITEM = ... # type: str
LOG_FILE_ND = ...  # type: str
LOG_FILE_ML = ...  # type: str
IS_DEBUG = ...  # type: int
COOKIE_FILE_NAME = ...  # type: str

BACKSLASH = ...  # type: str
CHARREF = ...  # type: str
REPLACE = ...  # type: str

def get_encoding() -> str: ...
def print_info(queue: List[str], file_name: Optional[Union[str, Path]]=...) -> bool: ...
def validator(input_list: List[str] | Tuple[str] | Set[str]) -> List[str]: ...
def make_dir(directory: Union[str, Path]) -> Path: ...
def t2filename(text : str) -> str: ...
def check_arg(parameters: Dict[str, Any]) -> None: ...
def sizeof_fmt(num: int) -> str: ...
def get_from_getflv(video_id: str, session: requests.Session) -> Optional[Dict[str, str]]: ...
def extract_getflv(content: str) -> Optional[Dict[str, str]]: ...

class MylistError(Exception): ...
class MylistNotFoundError(MylistError): ...
class MylistArgumentError(MylistError): ...


class Canopy:
    def __init__(self, loop: asyncio.AbstractEventLoop=None, logger=None):
        self.loop = loop or asyncio.get_event_loop()
        self.glossary = None
        self.save_dir = None  # type: Path
        self.logger = self.get_logger(logger)  # type: LoggerType
    def make_name(self, video_id: str, ext: str) -> Path: ...
    def get_logger(self, logger: Optional[LoggerType]) -> LoggerType: ...
    def start(self, glossary, save_dir, option): ...
    def download(self, video_id, flag): ...
    def _saver(self, video_id, data, option): ...


class LogIn:
    __singleton__ = ...  # type: LogIn
    is_login = ...  # type: bool
    cookie = ...  # type: Dict

    @classmethod
    def __new__(cls, *more, **kwargs) -> TypeVar("LogIn"): ...
    def __init__(self, mail: Optional[str]=...,
                 password: Optional[str]=...,
                 session: Optional[requests.Session]=...):
        self._auth = {}
        self.session = session
        self.token = self.get_token(self.session)
    def get_session(self, auth: Optional[Dict[str, str]]=...,
                    force_login: bool=...) -> requests.Session: ...
    def _we_have_logged_in(self, response: str) -> bool: ...
    def get_token(self, session: requests.Session) -> str: ...
    @classmethod
    def _ask_credentials(cls, mail: Optional[str]=...,
                         password: Optional[str]=...) -> Dict[str, str]: ...
    @classmethod
    def save_cookies(cls, requests_cookiejar: RequestsCookieJar,
                     file_name: str=...) -> Dict: ...
    @classmethod
    def load_cookies(cls, file_name: str=...) -> Optional[Dict]: ...


class NTLogger(logging.Logger):
    def __init__(self, file_name: Optional[Union[str, Path]]=...,
                 name: str=..., log_level: Union[int, str]=...):
        self.log_level = ...  # type: Union[int, str]
        self._is_debug = ...  # type: bool
        super().__init__(...)
        self.logger = ...  # type: logging.Logger
    def get_formatter(self) -> logging.Formatter: ...
    def forwarding(self, level: int, msg: Any, *args: Any, **kwargs: Any) -> None: ...
    def debug(self, msg: Any, *args: Any, **kwargs: Any) -> None: ...
    def info(self, msg: Any, *args: Any, **kwargs: Any) -> None: ...
    def warning(self, msg: Any, *args: Any, **kwargs: Any) -> None: ...
    def error(self, msg: Any, *args: Any, **kwargs: Any) -> None: ...
    def critical(self, msg: Any, *args: Any, **kwargs: Any) -> None: ...


class URL:
    URL_LogIn  = ...  # type: str
    URL_Watch  = ...  # type: str
    URL_GetFlv = ...  # type: str
    URL_Info   = ...  # type: str
    URL_Pict   = ...  # type: str
    URL_GetThreadKey = ...  # type: str
    URL_Message_New_JSON = ...  #type: str
    URL_Message_New_XML = ...  #type: str

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
    ml_default_name = ...  # type: str
    ml_default_id = ...  # type: str
    ml_description = ...  # type: str
    ml_help_group_b = ...  # type: str
    ml_help_group_a = ...  # type: str
    ml_help_add = ...  # type: str
    ml_help_delete = ...  # type: str
    ml_help_move = ...  # type: str
    ml_help_copy = ...  # type: str
    ml_help_export = ...  # type: str
    ml_help_show = ...  # type: str
    ml_help_outfile = ...  # type: str
    ml_help_purge = ...  # type: str
    ml_help_create = ...  # type: str
    ml_help_src = ...  # type: str
    ml_help_to = ...  # type: str
    ml_help_id = ...  # type: str
    ml_help_everything = ...  # type: str
    ml_help_yes = ...  # type: str
    ml_help_each = ...  # type: str

    nd_description = ...  # type: str
    nd_help_video_id = ...  # type: str
    nd_help_password = ...  # type: str
    nd_help_mail = ...  # type: str
    nd_help_destination = ...  # type: str
    nd_help_outfile = ...  # type: str
    nd_help_comment = ...  # type: str
    nd_help_video = ...  # type: str
    nd_help_thumbnail = ...  # type: str
    nd_help_xml = ...  # type: str
    nd_help_info = ...  # type: str
    nd_help_what = ...  # type: str
    nd_help_loglevel = ...  # type: str
    nd_help_nomulti = ...  # type: str
    nd_help_limit = ...  # type: str
    nd_help_dmc = ...  # type: str
    nd_help_smile = ...  # type: str

    input_mail = ...  # type: str
    input_pass = ...  # type: str

    nd_start_download = ...  # type: str
    nd_download_done = ...  # type: str
    nd_download_video = ...  # type: str
    nd_download_pict = ...  # type: str
    nd_download_pict_async = ...  # type: str
    nd_download_comment = ...  # type: str
    nd_start_dl_video = ...  # type: str
    nd_start_dl_pict = ...  # type: str
    nd_start_dl_comment = ...  # type: str
    nd_file_name = ...  # type: str
    nd_video_url_is = ...  # type: str
    nd_deleted_or_private = ...  # type: str

    ml_exported = ...  # type: str
    ml_items_counts = ...  # type: str
    ml_fetching_mylist_id = ...  # type: str
    ml_showing_mylist = ...  # type: str
    ml_loading_mylists = ...  # type: str
    ml_mylist_found = ...  # type: str

    ml_ask_delete_all = ...  # type: str
    ml_confirmation = ...  # type: str
    ml_answer_yes = ...  # type: str
    ml_answer_no = ...  # type: str
    ml_answer_invalid = ...  # type: str
    ml_deleted_or_private = ...  # type: str

    ml_done_add = ...  # type: str
    ml_done_delete = ...  # type: str
    ml_done_copy = ...  # type: str
    ml_done_move = ...  # type: str
    ml_done_purge = ...  # type: str
    ml_done_create = ...  # type: str

    ml_will_add = ...  # type: str
    ml_will_delete = ...  # type: str
    ml_will_copy = ...  # type: str
    ml_will_move = ...  # type: str
    ml_will_purge = ...  # type: str


class Err:
    failed_operation        = ...  # type: str
    waiting_for_permission  = ...  # type: str
    name_replaced           = ...  # type: str
    cant_create             = ...  # type: str
    deflist_to_create_or_purge = ...  # type: str
    not_installed           = ...  # type: str
    invalid_argument        = ...  # type: str
    invalid_dirname         = ...  # type: str
    invalid_auth            = ...  # type: str
    invalid_videoid         = ...  # type: str
    connection_404          = ...  # type: str
    connection_timeout      = ...  # type: str
    keyboard_interrupt      = ...  # type: str
    not_specified           = ...  # type: str
    videoids_contain_all    = ...  # type: str
    list_names_are_same     = ...  # type: str
    cant_perform_all        = ...  # type: str
    only_perform_all        = ...  # type: str
    no_commands             = ...  # type: str
    item_not_contained      = ...  # type: str
    name_ambiguous          = ...  # type: str
    name_ambiguous_detail   = ...  # type: str
    mylist_not_exist        = ...  # type: str
    mylist_id_not_exist     = ...  # type: str
    over_load               = ...  # type: str
    remaining               = ...  # type: str
    already_exist           = ...  # type: str
    known_error             = ...  # type: str
    unknown_error_itemid    = ...  # type: str
    unknown_error           = ...  # type: str
    failed_to_create        = ...  # type: str
    failed_to_purge         = ...  # type: str
    invalid_spec            = ...  # type: str
    no_items                = ...  # type: str

    MAXERROR        = ...  # type: str
    EXIST           = ...  # type: str
    NONEXIST        = ...  # type: str

    COMMANDERROR    = ...  # type: str
    PARAMERROR      = ...  # type: str
    INVALIDTOKEN    = ...  # type: str
    EXPIRETOKEN     = ...  # type: str
    NOAUTH          = ...  # type: str
    SECRETUSER      = ...  # type: str
    INVALIDUSER     = ...  # type: str
    INVALIDVIDEO    = ...  # type: str

    MAINTENANCE     = ...  # type: str
    INTERNAL        = ...  # type: str


class KeyGTI:
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
    FILE_SIZE       = ...  # type: str
    V_OR_T_ID       = ...  # type: str
    WATCH_URL       = ...  # type: str


class MKey:
    ID          = ...  # type: str
    NAME        = ...  # type: str
    IS_PUBLIC   = ...  # type: str
    PUBLICITY   = ...  # type: str
    SINCE       = ...  # type: str
    DESCRIPTION = ...  # type: str
    ITEM_DATA   = ...  # type: str


class KeyDmc:
    FILE_NAME       = ...  # type: str
    FILE_SIZE       = ...  # type: str

    VIDEO_ID        = ...  # type: str
    VIDEO_URL_SM    = ...  # type: str
    TITLE           = ...  # type: str
    THUMBNAIL_URL   = ...  # type: str
    ECO             = ...  # type: str
    MOVIE_TYPE      = ...  # type: str
    DELETED         = ...  # type: str
    IS_DELETED      = ...  # type: str
    IS_PUBLIC       = ...  # type: str
    IS_OFFICIAL     = ...  # type: str
    IS_PREMIUM      = ...  # type: str
    USER_ID         = ...  # type: str
    USER_KEY        = ...  # type: str
    MSG_SERVER      = ...  # type: str
    THREAD_ID       = ...  # type: str

    API_URL         = ...  # type: str
    RECIPE_ID       = ...  # type: str
    CONTENT_ID      = ...  # type: str
    VIDEO_SRC_IDS   = ...  # type: str
    AUDIO_SRC_IDS   = ...  # type: str
    HEARTBEAT       = ...  # type: str
    TOKEN           = ...  # type: str
    SIGNATURE       = ...  # type: str
    AUTH_TYPE       = ...  # type: str
    C_K_TIMEOUT     = ...  # type: str
    SVC_USER_ID     = ...  # type: str
    PLAYER_ID       = ...  # type: str
    PRIORITY        = ...  # type: str

    OPT_THREAD_ID   = ...  # type: str
    NEEDS_KEY       = ...  # type: str


class KeyGetFlv:
    THREAD_ID       = ...  # type: str
    LENGTH          = ...  # type: str
    VIDEO_URL       = ...  # type: str
    MSG_SERVER      = ...  # type: str
    MSG_SUB         = ...  # type: str
    USER_ID         = ...  # type: str
    IS_PREMIUM      = ...  # type: str
    NICKNAME        = ...  # type: str
    USER_KEY        = ...  # type: str

    OPT_THREAD_ID   = ...  # type: str
    NEEDS_KEY       = ...  # type: str
