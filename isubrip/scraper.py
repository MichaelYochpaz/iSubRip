import json
import re
from datetime import datetime
from typing import Union, Iterator
from urllib.error import HTTPError

import m3u8
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
from m3u8.model import M3U8
from requests.sessions import session

from isubrip.enums import SubtitlesType
from isubrip.constants import ITUNES_STORE_REGEX
from isubrip.namedtuples import MovieData, SubtitlesData
from isubrip.exceptions import InvalidURL, PageLoadError


class Scraper:
    """A class for scraping and downloading subtitles off of iTunes movie pages."""

    @staticmethod
    def find_movie_data(itunes_url: str, user_agent: Union[str, None] = None) -> MovieData:
        """
        Scrape an iTunes store page to find movie info and it's M3U8 playlist.

        Args:
            itunes_url (str): An iTunes store movie URL.
            user_agent (str | None, optional): A dictionary with iTunes data loaded from a JSON response. Defaults to None.
        
        Raises:
            InvalidURL: `itunes_url` is not a valid iTunes store movie URL.
            PageLoadError: HTML page did not load properly.  

        Returns:
            MovieData: A MovieData (NamedTuple) object with movie's name, and an M3U8 object of the playlist
            if the playlist is found. None otherwise.
        """
        # Check whether URL is valid
        if re.match(ITUNES_STORE_REGEX, itunes_url) is None:
            raise InvalidURL(f"{itunes_url} is not a valid iTunes movie URL.")

        user_agent_header = {"User-Agent": user_agent} if user_agent is not None else None
        response = session().get(itunes_url, headers=user_agent_header)

        # Response is JSON formatted
        if "application/json" in response.headers['content-type']:
            try:
                json_data = json.loads(response.text)

            except json.JSONDecodeError:
                raise PageLoadError("Recieved an invalid JSON response.")

            return Scraper._find_playlist_data_json_(json_data)

        # Response is HTML formatted
        else:
            html_data = BeautifulSoup(response.text, "lxml")
            return Scraper._find_playlist_data_html_(html_data)

    @staticmethod
    def _find_playlist_data_json_(json_data: dict) -> MovieData:
        """
        Scrape an iTunes JSON response to find movie info and it's M3U8 playlist.

        Args:
            json_data (dict): A dictionary with iTunes data loaded from a JSON response.

        Returns:
            MovieData: A MovieData (NamedTuple) object with movie's name, and an M3U8 object of the playlist
            if the playlist is found. None otherwise.
        """
        movie_id = json_data["pageData"]["id"]
        movie_data = json_data["storePlatformData"]["product-dv"]["results"][movie_id]

        movie_title = movie_data["nameRaw"]
        movie_release_year = datetime.strptime(movie_data["releaseDate"], '%Y-%m-%d').year
        
        # Loop safely to find a matching playlist
        for offer in movie_data["offers"]:
            if isinstance(offer.get("type"), str) and offer["type"] in ["buy", "rent"]:
                if isinstance(offer.get("assets"), list) and len(offer["assets"]) > 0:
                    for asset in offer["assets"]:
                        m3u8_url: str = asset["hlsUrl"]

                        # Assure playlist is valid
                        try:
                            m3u8.load(m3u8_url)

                        # If m3u8 playlist is invalid, skip it
                        except ValueError:
                            continue

                        except HTTPError:
                            continue
                        
                        return MovieData(movie_id, movie_title, movie_release_year, m3u8_url)

        return MovieData(movie_id, movie_title, movie_release_year, None)

    @staticmethod
    def _find_playlist_data_html_(html_data: BeautifulSoup) -> MovieData:
        """
        Scrape an iTunes HTML page to find movie info and it's M3U8 playlist.

        Args:
            html_data (BeautifulSoup): A BeautifulSoup object of the page.

        Raises:
            PageLoadError: HTML page did not load properly.

        Returns:
            MovieData: A MovieData (NamedTuple) object with movie's name, and an M3U8 object of the playlist
            if the playlist is found. None otherwise.
        """
        # NOTE: This function is less reliable than `_find_playlist_data_json_`.

        movie_id_tag: Union[Tag, NavigableString, None] = html_data.find("meta", attrs={"name": "apple:content_id"})
        if not isinstance(movie_id_tag, Tag):
            raise PageLoadError("HTML page did not load properly.")

        movie_id: str = movie_id_tag.attrs["content"]

        # Scrape a dictionary on the webpage for playlists data
        shoebox_data_tag: Union[Tag, NavigableString, None] = html_data.find("script", attrs={"id": "shoebox-ember-data-store", "type": "fastboot/shoebox"})

        # fastboot/shoebox data could not be found
        if not isinstance(shoebox_data_tag, Tag):
            raise PageLoadError("fastboot/shoebox data could not be found.")

        # Convert to dictionary structure
        shoebox_data: dict[str, dict] = json.loads(str(shoebox_data_tag.contents[0]).strip())

        # Loop safely to find a matching playlist
        if isinstance(shoebox_data[movie_id].get("included"), list):
            movie_data: dict = shoebox_data[movie_id]
            movie_title: str = movie_data["data"]["attributes"]["name"]
            movie_release_year = datetime.strptime(movie_data["data"]["attributes"]["releaseDate"], '%Y-%m-%d').year

            for item in movie_data["included"]:
                if isinstance(item.get("type"), str) and item["type"] == "offer":
                    if isinstance(item.get("attributes"), dict) and \
                        isinstance(item["attributes"].get("assets"), list) and len(item["attributes"]["assets"]) > 0:

                        for asset in item["attributes"]["assets"]:
                            if isinstance(asset, dict) and isinstance(asset.get("hlsUrl"), str):
                                m3u8_url: str = item["attributes"]["assets"][0]["hlsUrl"]

                                # Try to load the playlist, to assure it's valid
                                try:
                                    m3u8.load(m3u8_url)

                                # If m3u8 playlist is invalid, skip it
                                except (ValueError, HTTPError):
                                    continue

                                return MovieData(movie_id, movie_title, movie_release_year, m3u8_url)
        else:
            raise PageLoadError("Invalid shoebox data.")

        return MovieData(movie_id, movie_title, movie_release_year, None)

    @staticmethod
    def find_subtitles(main_playlist: M3U8, subtitles_filter: Union[list, None] = None) -> Iterator[SubtitlesData]:
        """
        Find and yield playlists within main_playlist for subtitles that match a filter.

        Args:
            main_playlist (M3U8): an M3U8 object of the main playlist.
            subtitles_filter (list, optional): A list of subtitles language codes (ISO 639-1) or names to use as a filter. Defaults to None.

        Yields:
            SubtitlesData: A NamedTuple with a matching playlist, and it's metadata:
            Language Code, Language Name, SubtitlesType, Playlist URL.
        """
        if subtitles_filter is not None:
            # Convert filters to lower-case for case-insensitive matching
            subtitles_filter = [f.lower() for f in subtitles_filter]

        for playlist in main_playlist.media:
            # Check whether playlist is valid and matches filter
            # "group_id" can be either ["subtitles_ak" / "subtitles_vod-ak-amt.tv.apple.com"] or
            # ["subtitles_ap2" / "subtitles_ap3" / "subtitles_vod-ap-amt.tv.apple.com" / "subtitles_vod-ap1-amt.tv.apple.com" / "subtitles_vod-ap3-amt.tv.apple.com"]
            if (playlist.type == "SUBTITLES") and (playlist.group_id in ("subtitles_ak", "subtitles_vod-ak-amt.tv.apple.com")):

                language_code: str = playlist.language
                language_name: str = playlist.name
                sub_type: SubtitlesType = SubtitlesType.NORMAL

                # Playlist does not match filter
                if subtitles_filter is not None and not (language_code.lower() in subtitles_filter or language_name in subtitles_filter):
                    continue

                # Change subtitles type to "Forced" / "Closed Captions" if needed.
                if playlist.forced == "YES":
                    sub_type = SubtitlesType.FORCED

                elif playlist.characteristics is not None and "public.accessibility" in playlist.characteristics:
                    sub_type = SubtitlesType.CC

                yield SubtitlesData(language_code, language_name, sub_type, playlist.uri)
