import os
from requests import Session

import m3u8

from isubrip.enums import SubtitlesFormat
from isubrip.subtitles import Subtitles


class PlaylistDownloader:
    """A class for downloading & converting m3u8 playlists into subtitles."""
    def __init__(self, user_agent: str = None) -> None:
        """
        Create a new PlaylistDownloader instance.

        Args:
            user_agent (str, optional): User agent to use when downloading. Uses default user-agent if not set.
        """
        self.session = Session()
        self.session.headers.update({"user-agent": user_agent})

    def download_subtitles(self, playlist_url: str, output_dir: str, file_name: str, file_format: SubtitlesFormat = SubtitlesFormat.VTT) -> str:
        """
        Download subtitles playlist to a file.

        Args:
            playlist_url (str): URL of the playlist to download.
            output_dir (str): Path to output directory (where the file will be saved).
            file_name (str): File name for the downloaded file.
            file_format (SubtitlesFormat, optional): File format to use for the downloaded file. Defaults to "SubtitlesFormat.VTT".

        Returns:
            str: Path to the downloaded subtitles file.
        """
        file_name += f".{file_format.name.lower()}"
        path = os.path.join(output_dir, file_name)

        subtitles_obj = Subtitles()
        playlist = m3u8.load(playlist_url)

        for segment in playlist.segments:
            data = self.session.get(segment.absolute_uri).content.decode('utf-8')
            subtitles_obj.append_subtitles(Subtitles.loads(data))

        with open(path, 'w', encoding="utf-8") as f:
            f.write(subtitles_obj.dumps(file_format))

        return path
