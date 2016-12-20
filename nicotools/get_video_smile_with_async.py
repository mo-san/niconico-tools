# coding: utf-8
import asyncio
import os
import sys
from pathlib import Path
from typing import Union, List, Optional

import aiohttp
import functools
from tqdm import tqdm

sys.path.insert(0, r"../")
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
                 chunk_size=1024*50,
                 multiline=True):
        super().__init__(loop=loop, logger=logger)
        self.__mail = mail
        self.__password = password
        self.__downloaded_size = None  # type: List[int]
        self.__multiline = multiline
        self.__division = division
        self.session = session
        self.__return_session = return_session
        self.__parallel_limit = limit
        self.__chunk_size = chunk_size

    def start(self, glossary: Union[list, dict], save_dir: str) -> Optional[aiohttp.ClientSession]:
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
        self.loop.run_until_complete(self._broker())
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
        vid_url = self.glossary[video_id][KeyDmc.VIDEO_URL_SM]
        self.logger.debug("Video ID: {}, Video URL: {}".format(video_id, vid_url))
        async with self.session.head(vid_url) as resp:
            headers = resp.headers
            self.logger.debug(str(headers))
            return int(headers["content-length"])

    async def _broker(self):
        futures = []
        for video_id in self.glossary:
            coro = self._download(video_id)
            f = asyncio.ensure_future(coro)
            f.add_done_callback(functools.partial(self._combiner, video_id))
            futures.append(f)
        await asyncio.wait(futures, loop=self.loop)

    async def _download(self, video_id: str):
        division = self.__division
        file_path = self.make_name(video_id, self.glossary[video_id][KeyDmc.MOVIE_TYPE])

        video_url = self.glossary[video_id][KeyDmc.VIDEO_URL_SM]
        file_size = self.glossary[video_id][KeyDmc.FILE_SIZE]
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
            tasks = [self._download_worker(file_path, video_url, header, order, pbar)
                     for header, order, pbar
                     in zip(headers, range(division), progress_bars)]
            progress_bars = await asyncio.gather(*tasks)  # type: List[tqdm]
            # ネストの「内側」から順に消さないと棒が画面に残る。
            for pbar in reversed(progress_bars):
                pbar.close()
        else:
            tasks = [self._download_worker(file_path, video_url, header, order)
                     for header, order
                     in zip(headers, range(division))]
            await asyncio.gather(*tasks, self._counter_whole(file_size))

    async def _download_worker(self, file_path: Union[str, Path], video_url: str,
                               header: dict, order: int, pbar: tqdm=None) -> tqdm:
        file_path = Path("{}.{:03}".format(file_path, order))
        # => video.mp4.000 ～ video.mp4.003 (4分割の場合)
        with file_path.open("wb") as fd:
            async with self.session.get(url=video_url, headers=header) as video_data:
                self.logger.debug("Started! Header: {}, Video URL: {}".format(header, video_url))
                while True:
                    data = await video_data.content.read(self.__chunk_size)
                    if not data:
                        break
                    downloaded_size = fd.write(data)
                    self.__downloaded_size[order] += downloaded_size
                    if pbar:
                        pbar.update(downloaded_size)
        self.logger.debug("Order: {} Done!".format(order))
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

    def _combiner(self, video_id: str, coroutine: asyncio.Task):
        if coroutine.done() and not coroutine.cancelled():
            file_path = self.make_name(video_id, self.glossary[video_id][KeyDmc.MOVIE_TYPE])
            file_names = ["{}.{:03}".format(file_path, order) for order in range(self.__division)]
            self.logger.debug("File names: {}".format(file_names))
            with file_path.open("wb") as fd:
                for name in file_names:
                    with open(name, "rb") as file:
                        fd.write(file.read())
                    os.remove(name)

if __name__ == "__main__":
    _video_ids = ["sm30214903", "sm1028001", "sm30219950", "sm30220861"]
    _save_dir = "D:/Downloads/videos/"
    GetSmileVideosAsync(mail=os.getenv("addr_p"), password=os.getenv("pass_p"),
                        logger=utils.NTLogger(log_level=20)).start(_video_ids, _save_dir)
