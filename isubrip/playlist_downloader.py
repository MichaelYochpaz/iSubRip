import asyncio
from pathlib import Path

import aiohttp
import m3u8

from os import PathLike
from typing import Union

from isubrip.enums import SubtitlesFormat
from isubrip.namedtuples import SubtitlesData, MovieData
from isubrip.subtitles import Subtitles
from isubrip.utils import generate_release_name


class PlaylistDownloader:
    """A class for downloading & converting m3u8 playlists into subtitles."""
    def __init__(self, user_agent: str = None) -> None:
        """
        Create a new PlaylistDownloader instance.

        Args:
            user_agent (str): User agent to use when downloading. Uses default user-agent if not set.
        """
        self.session = aiohttp.ClientSession()

        if user_agent is not None:
            self.session.headers.update({"user-agent": user_agent})

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    async def _download_segment(self, segment_url: str) -> str:
        """
        Download an m3u8 segment.

        Args:
            segment_url (str): Segment URL to download.

        Returns:
            str: Downloaded segment data as a string.
        """
        data = await self.session.get(segment_url)
        content = await data.read()
        return content.decode('utf-8')

    def close(self) -> None:
        """Close aiohttp session."""
        async_loop = asyncio.get_event_loop()
        close_task = async_loop.create_task(self.session.close())
        async_loop.run_until_complete(asyncio.gather(close_task))

    def get_subtitles(self, subtitles_data: SubtitlesData) -> Subtitles:
        """
        Get a subtitles object parsed from a playlist.

        Args:
            subtitles_data (SubtitlesData): A SubtitlesData namedtuple with information about the subtitles.

        Returns:
            Subtitles: A Subtitles object representing the subtitles.
        """
        subtitles = Subtitles(subtitles_data.language_code)
        playlist = m3u8.load(subtitles_data.playlist_url)

        async_loop = asyncio.get_event_loop()
        async_tasks = [async_loop.create_task(self._download_segment(segment.absolute_uri)) for segment in playlist.segments]
        segments = async_loop.run_until_complete(asyncio.gather(*async_tasks))

        for segment in segments:
            subtitles.append_subtitles(Subtitles.loads(segment))

        return subtitles

    def download_subtitles(self, movie_data: MovieData, subtitles_data: SubtitlesData, output_dir: Union[str, PathLike], file_format: SubtitlesFormat = SubtitlesFormat.VTT) -> Path:
        """
        Download a subtitles file from a playlist.

        Args:
            movie_data (MovieData): A MovieData namedtuple with information about the movie.
            subtitles_data (SubtitlesData): A SubtitlesData namedtuple with information about the subtitles.
            output_dir (str | PathLike): Path to output directory (where the file will be saved).
            file_format (SubtitlesFormat, optional): File format to use for the downloaded file. Defaults to `VTT`.

        Returns:
            str: Path to the downloaded subtitles file.
        """
        file_name = generate_release_name(
            title=movie_data.name,
            release_year=movie_data.release_year,
            media_source="iT",
            subtitles_info=(subtitles_data.language_code, subtitles_data.subtitles_type),
            file_format=file_format
        )

        # Convert to Path object if necessary
        if isinstance(output_dir, str):
            output_dir = Path(output_dir)

        path = output_dir / file_name

        with open(path, 'w', encoding="utf-8") as f:
            f.write(self.get_subtitles(subtitles_data).dumps(file_format))

        return path
