# coding: UTF-8
import logging
from pathlib import Path
from typing import Any, List, Dict, Union, Optional, TypeVar, Tuple

import requests

from nicotools import utils

DatabaseType = Dict[str, Dict[str, Union[int, str, List[str]]]]
LoggerType = TypeVar("LoggerType", bound=logging.Logger)
IS_DEBUG = ...  # type: bool


def get_infos(queue: List[str], logger: Optional[LoggerType]=...) -> DatabaseType: ...


class Video(utils.Canopy):
    def __init__(self, mail: Optional[str]=...,
                 password: Optional[str]=...,
                 logger: Optional[LoggerType]=...,
                 session: requests.Session=...):
        super().__init__(...)
        self.session = ...  # type: requests.Session
    def start(self, glossary: DatabaseType, save_dir: Union[str, Path], chunk_size: int=...) -> bool: ...
    def download(self, video_id: str, chunk_size: int=...) -> bool: ...
    def _saver(self, video_id: str, video_data: requests.Response, chunk_size: int) -> bool: ...


class Thumbnail(utils.Canopy):
    def __init__(self, logger: Optional[LoggerType]=...):
        super().__init__(...)
    def start(self, glossary: DatabaseType, save_dir: Union[str, Path], is_large: bool=...) -> bool: ...
    def download(self, video_id: str, is_large: bool=...) -> bool: ...
    def _worker(self, video_id: str, url: str, is_large: bool=...) -> Union[bool, requests.Response]: ...
    def _saver(self, video_id: str, image_data: requests.Response, _: Any=...) -> bool: ...


class Comment(utils.Canopy):
    def __init__(self, mail: Optional[str]=...,
                 password: Optional[str]=...,
                 logger: Optional[LoggerType]=...,
                 session: requests.Session=...):
        super().__init__(...)
        self.session = ...  # type: requests.Session
    def start(self, glossary: DatabaseType, save_dir: Union[str, Path], xml: bool=...) -> bool: ...
    def download(self, video_id: str, xml: bool=...) -> bool: ...
    def _saver(self, video_id: str, comment_data: str, xml: bool) -> bool: ...
    def get_thread_key(self, video_id: str, needs_key: str) -> Tuple[str, str]: ...
    def make_param_xml(self, thread_id: str, user_id: str) -> str: ...
    def make_param_json(self, official_video: bool,
                        user_id: str,
                        user_key: str,
                        thread_id: str,
                        optional_thread_id: Optional[str]=...,
                        thread_key: Optional[str]=...,
                        force_184: Optional[str]=...) -> List[Dict]: ...
