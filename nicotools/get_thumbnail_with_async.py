# coding: utf-8
import asyncio
import functools
import html
from pathlib import Path
from typing import Union, List, Dict, Optional

import aiohttp
from bs4 import BeautifulSoup

from nicotools import utils
from nicotools.utils import Msg, KeyGTI, URL


class GetThumbnailAsync(utils.Canopy):
    def __init__(self, logger: utils.NTLogger=None, limit: int=8,
                 session: aiohttp.ClientSession=None, return_session: bool=False):
        super().__init__(logger=logger)
        self.undone = []
        self.__bucket = {}
        self.session = session or self.loop.run_until_complete(self.get_session())
        self.__return_session = return_session
        self.__parallel_limit = limit

    async def get_session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession()

    def start(self, glossary: Union[List, Dict],
              save_dir: Union[str, Path], is_large=True)\
            -> Union[bool, aiohttp.ClientSession]:
        """

        :param dict[str, dict[str, int | str]] | list[str] glossary:
        :param str | Path save_dir:
        :param bool is_large: 大きいサムネイルを取りに行くかどうか
        :rtype: bool | aiohttp.ClientSession
        """
        utils.check_arg(locals())
        self.logger.debug("Directory to save in: {}".format(save_dir))
        self.logger.debug("Dictionary of Videos: {}".format(glossary))
        if isinstance(glossary, list):
            glossary = utils.validator(glossary)
            glossary = self.loop.run_until_complete(self.get_infos(glossary))
        del self.__bucket
        self.glossary = glossary
        self.save_dir = utils.make_dir(save_dir)
        self.logger.info(Msg.nd_start_dl_pict.format(len(self.glossary)))
        self.loop.run_until_complete(self.download(list(self.glossary)))
        while len(self.undone) > 0:
            self.logger.debug("いくつか残ってる。{}".format(self.undone))
            self.loop.run_until_complete(self.download(self.undone, False))
        self.logger.debug("全部終わった")
        if self.__return_session:
            return self.session
        else:
            self.session.close()
            return True

    async def download(self, video_ids: list, islarge: bool=True) -> None:
        urls = self.make_urls(video_ids, islarge)
        sem = asyncio.Semaphore(self.__parallel_limit)

        futures = []
        for video_id, _url in zip(video_ids, urls):
            coro = self.worker(sem, video_id, _url)
            f = asyncio.ensure_future(coro)
            f.add_done_callback(functools.partial(self.saver, video_id))
            futures.append(f)
        await asyncio.wait(futures, loop=self.loop)

    async def worker(self, semaphore: asyncio.Semaphore, video_id: str, url: str) -> Optional[bytes]:
        self.logger.debug("_worker", locals())
        async with semaphore:
            self.logger.debug(
                Msg.nd_download_pict_async.format(
                    video_id, self.glossary[video_id][KeyGTI.TITLE]))
            try:
                async with self.session.get(url, timeout=10) as response:
                    self.logger.debug(video_id, response.status)
                    if response.status == 200:
                        # ダウンロードに成功したら「未完了のリスト」から取り除く
                        if video_id in self.undone:
                            self.undone.remove(video_id)
                        return await response.content.read()
                    else:
                        self.undone.append(video_id)
                        return None
            except asyncio.TimeoutError:
                self.logger.warning("{} が時間切れ".format(video_id))
                self.undone.append(video_id)
                return None

    def saver(self, video_id: str, coroutine: asyncio.Task) -> None:
        image_data = coroutine.result()
        if image_data:
            file_path = self.make_name(video_id, "jpg")
            self.logger.debug("File Path: {}".format(file_path))

            with file_path.open('wb') as f:
                f.write(image_data)
            self.logger.info(Msg.nd_download_done.format(file_path))

    def make_urls(self, video_ids: List[str], is_large: bool=True) -> List[str]:
        if is_large:
            urls = ["{0}.L".format(self.glossary[_id][KeyGTI.THUMBNAIL_URL]) for _id in video_ids]
        else:
            urls = [self.glossary[_id][KeyGTI.THUMBNAIL_URL] for _id in video_ids]
        return urls

    async def get_infos(self, queue: List[str]) -> Dict[str, Dict]:
        """
        getthumbinfo APIから、細かな情報をもらってくる

        * file_name         str
        * thumbnail_url     str
        * title             str
        * video_id          str

        :param list[str] queue: 動画IDのリスト
        :rtype: dict[str, dict]
        """
        sem = asyncio.Semaphore(self.__parallel_limit)
        futures = []
        for video_id in queue:
            f = asyncio.ensure_future(self.get_infos_worker(sem, video_id))
            f.add_done_callback(functools.partial(self.get_infos_second, video_id))
            futures.append(f)
        await asyncio.wait(futures, loop=self.loop)
        return self.__bucket

    async def get_infos_worker(self, semaphore: asyncio.Semaphore, video_id: str) -> str:
        async with semaphore:
            async with self.session.get(URL.URL_Info + video_id) as resp:
                return await resp.text()

    def get_infos_second(self, video_id: str, coroutine: asyncio.Task) -> None:
        soup = BeautifulSoup(coroutine.result(), "html.parser")
        if soup.nicovideo_thumb_response["status"].lower() == "ok":
            self.__bucket[video_id] = {
                    KeyGTI.FILE_NAME    : utils.t2filename(soup.select(KeyGTI.TITLE)[0].text),
                    KeyGTI.THUMBNAIL_URL: soup.select(KeyGTI.THUMBNAIL_URL)[0].text,
                    KeyGTI.TITLE        : html.unescape(soup.select(KeyGTI.TITLE)[0].text),
                    KeyGTI.VIDEO_ID     : video_id
                }


if __name__ == "__main__":
    _video_ids = ["sm30214903", "sm1028001", "sm30219950", "sm30220861"]
    _save_dir = "D:/Downloads/thumbnails/"
    GetThumbnailAsync().start(_video_ids, _save_dir)
