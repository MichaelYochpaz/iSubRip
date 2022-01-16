
import re
import html
import json
from urllib.error import HTTPError
import m3u8
from typing import Union
from enum import Enum
from requests.sessions import session
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
from m3u8.model import M3U8

from playlist_downloader import PlaylistDownloader


class iSubRip:
    """A class for scraping and downloading subtitles off of iTunes movie pages."""


    class ScrapeError(Exception):
        """An issue while scraping the page."""
        pass


    class InvalidURL(ScrapeError):
        """An invalid URL has been used."""
        pass


    class PageLoadError(ScrapeError):
        """The Page did not load properly."""
        pass


    class PlaylistDownloadError(ScrapeError):
        """The playlist could not be downloaded."""
        pass


    class SubtitlesType(Enum):
        """Subtitles type (Normal / CC / Forced)."""
        NORMAL = 1
        CC = 2
        FORCED = 3


    @staticmethod
    def find_m3u8_playlist(itunes_url: str, user_agent: str = None) -> tuple[str, Union[M3U8, None]]:
        """
        Scrape an iTunes page to find the URL of the M3U8 playlist.

        Args:
            itunes_url (str): URL of an iTunes movie page to scrape.
            user_agent (str, optional): User-Agent string to use for scraping. Defaults to None.

        Raises:
            InvalidURL: An inavlid iTunes URL was provided.
            ConnectionError: A connection error occurred while trying to request the page.
            HTTPError: An error while trying to download m3u8 playlist data.
            PageLoadError: The page did not load properly.

        Returns:
            tuple[str, M3U8 | None]: The movie's name and an M3U8 object of the playlist if the playlist is found, and None otherwise.
        """

        # Check whether URL is valid
        regex_exp = r"https?://itunes.apple.com/[a-z]{2}/movie/[a-zA-Z0-9\-%]+/id[0-9]+($|(\?.*))"
        if re.match(regex_exp, itunes_url) == None:
            raise iSubRip.InvalidURL(f"{itunes_url} is not a valid iTunes movie URL.")

        site_page: BeautifulSoup = BeautifulSoup(session().get(itunes_url, headers={"User-Agent": user_agent}).text, "lxml")
        movie_metadata: Union[Tag, NavigableString, None] = site_page.find("script", attrs={"name": "schema:movie", "type": 'application/ld+json'})

        if (not isinstance(movie_metadata, Tag)):
            raise iSubRip.PageLoadError("The page did not load properly.")
        
        # Convert to dictionary structure
        movie_metadata_dict: dict = json.loads(str(movie_metadata.contents[0]).strip())

        media_type: str = movie_metadata_dict['@type']
        movie_title: str = html.unescape(movie_metadata_dict['name'])

        if media_type != "Movie":
            raise iSubRip.InvalidURL("The provided iTunes URL is not for a movie.")
        
        # Scrape a dictionary on the webpage for playlists data
        playlists_data_tag: Union[Tag, NavigableString, None] = site_page.find("script", attrs={"id": "shoebox-ember-data-store", "type": "fastboot/shoebox"})

        # fastboot/shoebox data could not be found
        if (not isinstance(playlists_data_tag, Tag)):
            raise iSubRip.PageLoadError("fastboot/shoebox data could not be found.")

        # Convert to dictionary structure
        playlists_data: dict[str, dict] = json.loads(str(playlists_data_tag.contents[0]).strip())

        # Loop safely over different structures to find a matching playlist
        for key in playlists_data.keys():
                if isinstance(playlists_data[key].get("included"), list):
                    for item in playlists_data[key]["included"]:
                        if (isinstance(item.get("attributes"), dict) and
                        isinstance(item["attributes"].get("assets"), list) and
                        len(item["attributes"]["assets"]) > 0 and
                        isinstance(item["attributes"]["assets"][0], dict) and
                        isinstance(item["attributes"]["assets"][0].get("hlsUrl"), str)):
                            m3u8_url: str = item["attributes"]["assets"][0]["hlsUrl"]

                            try:
                                playlist: M3U8 = m3u8.load(m3u8_url)

                            # If m3u8 playlist is invalid, skip it
                            except ValueError:
                                continue

                            except HTTPError:
                                continue
                            
                            # Assure playlist is for the correct movie
                            if iSubRip.is_playlist_valid(playlist, movie_title):
                                return (movie_title, playlist)

        return (movie_title, None)


    @staticmethod
    def find_matching_subtitles(main_playlist: M3U8, filter: list = []):
        """
        Find and yield iTunes subtitles playlists within main_playlist that match the filter.

        Args:
            main_playlist (M3U8): an M3U8 object of the main playlist.
            filter (list, optional): A list of subtitles language codes (ISO 639-1) or names to use as a filter. Defaults to [].

        Yields:
            Tuple: A Tuple with a matching playlist and it's metadata using the following structure:
            (Language Code, Language Name, SubtitlesType, Playlist URL)
        """

        for playlist in main_playlist.media:
            # Check whether playlist is valid and matches filter
            # "group_id" can be either ["subtitles_ak" / "subtitles_vod-ak-amt.tv.apple.com"] or ["subtitles_ap2" / "subtitles_ap3" / "subtitles_vod-ap-amt.tv.apple.com" / "subtitles_vod-ap1-amt.tv.apple.com" / "subtitles_vod-ap3-amt.tv.apple.com"]
            if ((playlist.type == "SUBTITLES") and
            (playlist.group_id in ("subtitles_ak", "subtitles_vod-ak-amt.tv.apple.com"))):

                language_code: str = playlist.language
                language_name: str = playlist.name
                sub_type: iSubRip.SubtitlesType = iSubRip.SubtitlesType.NORMAL
                
                # Playlist does not match filter
                if (len(filter) != 0) and not (language_code in filter or language_name in filter):
                    continue

                # Find subtitles type (Normal / Forced / Closed Captions)
                if (playlist.forced == "YES"):
                    sub_type = iSubRip.SubtitlesType.FORCED

                elif (playlist.characteristics != None and "public.accessibility" in playlist.characteristics):
                    sub_type = iSubRip.SubtitlesType.CC

                yield (language_code, language_name, sub_type, playlist.uri)


    @staticmethod
    def download_playlist(playlist_downloader: PlaylistDownloader, playlist_url: str, file_name: str) -> None:
        """
        Download and convert subtitles from a playlist to a subtitles file.

        Args:
            playlist_downloader (PlaylistDownloader): A PlaylistDownloader object to use for downloading.
            playlist_url (str): URL of the subtitles playlist to use for download.
            file_name (str): File name to use for the subtitles file.
        """

        playlist_downloader.download_subtitles(playlist_url, file_name, PlaylistDownloader.SubtitlesFormat.SRT)


    @staticmethod
    def is_playlist_valid(playlist: m3u8.M3U8, movie_title: str) -> bool:
        """
        Check whether an iTunes M3U8 playlist title matches a movie title.

        Args:
            playlist (M3U8): An M3U8 playlist to do the check on
            movie_title (str): The title to compare the playlist's title against.

        Returns:
            bool: True if the title matches the title of the playlist, and False otherwise.
        """        
        for sessionData in playlist.session_data:
            if sessionData.data_id == "com.apple.hls.title":
                return movie_title == sessionData.value

        return False