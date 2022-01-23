import os
import shutil
import subprocess

from isubrip.enums import SubtitlesFormat
from isubrip.exceptions import FFmpegNotFound


class PlaylistDownloader:
    """
    A class for downloading M3U8 playlists.\n
    The class required ffmpeg to be installed for the download to work.
    """

    def __init__(self, output_dir: str, ffmpeg_path: str = "ffmpeg", ffmpeg_args: str = None) -> None:
        """
        Create a new PlaylistDownloader instance.

        Args:
            output_dir (str): A folder to save the downloaded files to.
            ffmpeg_path (str, optional): The path to FFmpeg's executeable. "ffmpeg" can be used if it's in PATH. Defaults to "ffmpeg".
            ffmpeg_args (str, optional): Argunemts to run FFmpeg commands with. Defaults to None.

        Raises:
            FileNotFoundError: Output directory could not be found.
            PermissionError: Output directory is not writable.
            PlaylistDownloader.FFmpegNotFound: FFmpeg executeable could not be found.
        """
        self.output_dir = output_dir
        self.ffmpeg_path = ffmpeg_path
        self.ffmpeg_args = ffmpeg_args

        # Check whether output directory exists
        if not os.path.exists(self.output_dir):
            raise FileNotFoundError(f"Folder {self.output_dir} could not be found.")

        # Check whether the user has write permissions to directory.
        if not os.access(self.output_dir, os.W_OK):
            raise PermissionError(f"Folder {self.output_dir} is not writable.")

        # Check whether FFmpeg is found
        if shutil.which(self.ffmpeg_path) is None:
            raise FFmpegNotFound("FFmpeg could not be found.")

    def download_subtitles(self, playlist_url: str, file_name: str, file_format: SubtitlesFormat = SubtitlesFormat.SRT) -> None:
        """
        Download a subtitles playlist to a file.

        Args:
            playlist_url (str): Link to the playlist to download
            file_name (str): Name for the downloaded file
            file_format (SubtitlesFormat, optional): Format to use for saving the subtitles. Defaults to SubtitlesFormat.SRT.
        """
        file_name += '.' + file_format.name.lower()
        path = os.path.join(self.output_dir, file_name)

        ffmpeg_args_str = (self.ffmpeg_args + " ") if (self.ffmpeg_args is not None) else ''
        ffmpeg_command = f"{self.ffmpeg_path} " + ffmpeg_args_str + f"-i \"{playlist_url}\" \"{path}\""

        subprocess.run(ffmpeg_command, shell=False)
