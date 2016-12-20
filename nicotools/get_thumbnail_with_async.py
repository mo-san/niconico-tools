# coding: utf-8
import asyncio
from pathlib import Path
from typing import Union, List, Dict

import aiohttp

from nicotools import utils
from nicotools import nicodown
from nicotools.utils import Msg, KeyGTI


class GetThumbnailAsync(utils.Canopy):
    def __init__(self, logger: utils.NTLogger=None, limit: int=4,
                 session: aiohttp.ClientSession=None, return_session: bool=False):
        super().__init__(logger=logger)
        self.undone = []
        self.session = session or aiohttp.ClientSession()
        self.__return_session = return_session
        self.__parallel_limit = limit

    def start(self, glossary: Union[List, Dict], save_dir: Union[str, Path], is_large=True)\
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
            # TODO: ここを非同期でやる
            glossary = nicodown.get_infos(glossary, self.logger)
        self.glossary = glossary
        self.save_dir = utils.make_dir(save_dir)
        self.logger.info(Msg.nd_start_dl_pict.format(len(self.glossary)))
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.download(list(self.glossary)))
        while len(self.undone) > 0:
            self.logger.info("いくつか残ってる。{}".format(self.undone))
            loop.run_until_complete(self.download(self.undone, False))
        self.logger.info("全部終わった")
        if self.__return_session:
            return self.session
        else:
            self.session.close()
            return True

    async def download(self, video_ids: list, islarge=True) -> None:
        urls = self.make_urls(video_ids, islarge)
        sem = asyncio.Semaphore(self.__parallel_limit)
        tasks = [self.bound_worker(sem, self.session, _id, _url) for _id, _url in zip(video_ids, urls)]
        await asyncio.gather(*tasks)

    async def bound_worker(self, semaphore: asyncio.Semaphore,
                           session: aiohttp.ClientSession, video_id: str, url: str) -> None:
        async with semaphore:
            self.logger.info(
                Msg.nd_download_pict_async.format(video_id, self.glossary[video_id][KeyGTI.TITLE]))
            image_data = await self.worker(session, video_id, url)
            if image_data:
                self.saver(video_id, image_data)

    async def worker(self, session: aiohttp.ClientSession, video_id: str, url: str) -> bytes:
        self.logger.debug("_worker", locals())
        try:
            async with session.get(url, timeout=10) as response:
                self.logger.debug(video_id, response.status)
                if response.status == 200:
                    # ダウンロードに成功したら「未完了のリスト」から取り除く
                    if video_id in self.undone:
                        self.undone.remove(video_id)
                    return await response.content.read()
                else:
                    self.undone.append(video_id)
        except asyncio.TimeoutError:
            self.logger.warning(video_id, "時間切れ")
            self.undone.append(video_id)

    def saver(self, video_id: str, image_data: bytes) -> None:
        file_path = self.make_name(video_id, "jpg")
        self.logger.debug("File Path: {}".format(file_path))

        with file_path.open('wb') as f:
            f.write(image_data)
        self.logger.info(Msg.nd_download_done.format(file_path))

    def make_urls(self, video_ids: list, is_large: bool=True) -> list:
        if is_large:
            urls = [self.glossary[_id][KeyGTI.THUMBNAIL_URL] + ".L" for _id in video_ids]
        else:
            urls = [self.glossary[_id][KeyGTI.THUMBNAIL_URL] for _id in video_ids]
        return urls


if __name__ == "__main__":
    _video_ids = ["sm30214903", "sm1028001", "sm30219950", "sm30220861"]
    _save_dir = "D:/Downloads/thumbnails/"
    GetThumbnailAsync().start(_video_ids, _save_dir)
