import os
import shutil
import subprocess

from typing import Union

from isubrip.enums import SubtitlesFormat
from isubrip.exceptions import FFmpegNotFound


class PlaylistDownloader:
    """
    A class for downloading M3U8 playlists.
    The class requires FFmpeg to be installed for downloads to work.
    """

    def __init__(self, ffmpeg_path: str = "ffmpeg", ffmpeg_args: Union[str, None] = None) -> None:
        """
        Create a new PlaylistDownloader instance.

        Args:
            ffmpeg_path (str, optional): The path to FFmpeg's executeable. "ffmpeg" can be used if it's in PATH. Defaults to "ffmpeg".
            ffmpeg_args (str, optional): Argunemts to run FFmpeg commands with. Defaults to None.

        Raises:
            FFmpegNotFound: FFmpeg executeable could not be found.
        """

        # Check whether FFmpeg is found, raise an exception if not
        if shutil.which(ffmpeg_path) is None:
            raise FFmpegNotFound("FFmpeg could not be found.")

        self.ffmpeg_path = ffmpeg_path
        self.ffmpeg_args = ffmpeg_args

    def download_subtitles(self, playlist_url: str, output_dir: str, file_name: str, file_format: SubtitlesFormat = SubtitlesFormat.VTT) -> str:
        """
        Download subtitles playlist to a file.

        Args:
            playlist_url (str): URL of the playlist to download.
            output_dir (str): Path to output directory (where the file will be saved).
            file_name (str): File name for the downloaded file.
            file_format (SubtitlesFormat, optional): File format to use for the downloaded file. Defaults to "SubtitlesFormat.VTT".

        Returns:
            str: A string with the path to the downloaded subtitles file
        """
        file_name += f".{file_format.name.lower()}"
        path = os.path.join(output_dir, file_name)

        ffmpeg_args_str = (self.ffmpeg_args + " ") if (self.ffmpeg_args is not None) else ''
        ffmpeg_command = f"{self.ffmpeg_path} " + ffmpeg_args_str + f"-i \"{playlist_url}\" \"{path}\""

        subprocess.run(ffmpeg_command, shell=True)

        return path
