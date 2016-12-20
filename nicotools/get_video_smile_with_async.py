# coding: utf-8
import asyncio
import os
from pathlib import Path
from typing import Union, List, Optional

import aiohttp
import functools
from tqdm import tqdm

from nicotools import utils
from nicotools.get_info_with_async import GetInfoAsync
from nicotools.utils import KeyDmc


class GetSmileVideosAsync(utils.Canopy):
    def __init__(self, loop: asyncio.AbstractEventLoop=None,
                 mail: str=None, password: str=None,
                 logger: utils.NTLogger=None,
                 session: aiohttp.ClientSession=None,
                 return_session=False,
                 division: int=4,
                 limit: int=4,
                 multiline_progressbars=True):
        super().__init__(loop=loop, logger=logger)
        self.__mail = mail
        self.__password = password
        self.__downloaded_size = None  # type: List[int]
        self.__multiline = multiline_progressbars
        self.__division = division
        self.session = session
        self.__return_session = return_session
        self.__parallel_limit = limit

    def start(self, glossary: Union[list, dict], save_dir: str,
              chunk_size: int=1024*50) -> Optional[aiohttp.ClientSession]:
        self.save_dir = utils.make_dir(save_dir)
        self.__downloaded_size = [0] * self.__division

        if isinstance(glossary, list):
            glossary, self.session = GetInfoAsync(
                mail=self.__mail, password=self.__password,
                session=self.session, return_session=True).get_data(glossary)
        else:
            self.session = self.loop.run_until_complete(self.get_session())
        self.glossary = glossary

        sem = asyncio.Semaphore(self.__parallel_limit)
        self.loop.run_until_complete(self._push_file_size(sem))
        self.loop.run_until_complete(self._broker(self.__division, chunk_size))
        if self.__return_session:
            return self.session
        else:
            self.session.close()
            return None

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session:
            return self.session
        else:
            cook = utils.LogIn(mail=self.__mail, password=self.__password).cookie
            return aiohttp.ClientSession(cookies=cook)

    async def _push_file_size(self, semaphore: asyncio.Semaphore):
        video_ids = sorted(self.glossary)
        tasks = [self._get_file_size_worker(video_id) for video_id in video_ids]
        async with semaphore:
            result = await asyncio.gather(*tasks)
        for _id, size in zip(video_ids, result):
            self.glossary[_id][KeyDmc.FILE_SIZE] = size

    async def _get_file_size_worker(self, video_id: str) -> int:
        vid_url = self.glossary[video_id][KeyDmc.VIDEO_URL]
        self.logger.debug("Video ID: {}, Video URL: {}".format(video_id, vid_url))
        async with self.session.head(vid_url) as resp:
            headers = resp.headers
            self.logger.debug(str(headers))
            return int(headers["content-length"])

    async def _broker(self, division: int, chunk_size: int):
        futures = []
        for video_id in self.glossary:
            coro = self._download(video_id, division, chunk_size)
            f = asyncio.ensure_future(coro)
            f.add_done_callback(functools.partial(self._combiner, video_id, division))
            futures.append(f)
        await asyncio.wait(futures, loop=self.loop)

    async def _download(self, video_id: str, division: int, chunk_size: int):
        file_path = self.make_name(video_id, self.glossary[video_id][KeyDmc.MOVIE_TYPE])

        video_url = self.glossary[video_id][KeyDmc.VIDEO_URL]
        file_size = self.glossary[video_id]["file_size"]
        headers = [
            {"Range": "bytes={}-{}".format(
                int(file_size*order/division),
                int((file_size*(order+1))/division-1)
            )} for order in range(division)]
        [self.logger.debug(str(h)) for h in headers]

        if self.__multiline:
            progress_bars = [tqdm(total=int(file_size / division),
                                  leave=False, position=order,
                                  unit="B", unit_scale=True)
                             for order in range(division)]  # type: List[tqdm]
            tasks = [self._downlaod_worker(file_path, video_url, header, order, chunk_size, pbar)
                     for header, order, pbar
                     in zip(headers, range(division), progress_bars)]
            progress_bars = await asyncio.gather(*tasks)  # type: List[tqdm]
            # ネストの「内側」から順に消さないと棒が画面に残る。
            for pbar in reversed(progress_bars):
                pbar.close()
        else:
            tasks = [self._downlaod_worker(file_path, video_url, header, order, chunk_size)
                     for header, order
                     in zip(headers, range(division))]
            await asyncio.gather(*tasks, self._counter_whole(file_size))

    async def _downlaod_worker(self, file_path: Union[str, Path], video_url: str,
                               header: dict, order: int, chunk_size: int=1024*50, pbar: tqdm=None) -> tqdm:
        file_path = Path("{}.{:03}".format(file_path, order))
        # => video.mp4.000 ～ video.mp4.003 (4分割の場合)
        with file_path.open("wb") as fd:
            async with self.session.get(url=video_url, headers=header) as video_data:
                self.logger.debug("Started! Header: %s, Video URL: %s", header, video_url)
                while True:
                    data = await video_data.content.read(chunk_size)
                    if not data:
                        break
                    downloaded_size = fd.write(data)
                    self.__downloaded_size[order] += downloaded_size
                    if pbar:
                        pbar.update(downloaded_size)
        self.logger.debug("Done! Header: %s", header)
        return pbar

    async def _counter_whole(self, file_size: int, interval: int=1):
        with tqdm(total=file_size, unit="B") as bar:
            oldsize = 0
            while True:
                newsize = sum(self.__downloaded_size)
                if newsize >= file_size:
                    bar.update(file_size - oldsize)
                    break
                bar.update(newsize - oldsize)
                oldsize = newsize
                await asyncio.sleep(interval)

    def _combiner(self, video_id: str, division: int, coroutine: asyncio.Task):
        if coroutine.done() and not coroutine.cancelled():
            file_path = self.make_name(video_id, self.glossary[video_id][KeyDmc.MOVIE_TYPE])
            file_names = ["{}.{:03}".format(file_path, order) for order in range(division)]
            self.logger.debug("File names: {}".format(file_names))
            with file_path.open("wb") as fd:
                for name in file_names:
                    with open(name, "rb") as file:
                        fd.write(file.read())
                    os.remove(name)
