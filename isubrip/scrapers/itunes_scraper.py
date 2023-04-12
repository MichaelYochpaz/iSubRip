from __future__ import annotations

import json
from datetime import datetime

import m3u8
from bs4 import BeautifulSoup, Tag, NavigableString
from requests import HTTPError

from isubrip.data_structures import MediaSourceData, MovieData
from isubrip.scrapers.scraper import M3U8Scraper, MovieScraper, ScraperException
from isubrip.subtitle_formats.webvtt import WebVTTSubtitles


class iTunesScraper(M3U8Scraper, MovieScraper):
    """An iTunes movie data scraper."""
    url_regex = r"(https?://itunes\.apple\.com/[a-z]{2}/movie/(?:[\w\-%]+/)?(id\d{9,10}))(?:\?.*)?"
    service_data = MediaSourceData(id="itunes", name="iTunes", abbreviation="iT")
    subtitles_class = WebVTTSubtitles
    is_movie_scraper = True

    def get_data(self, url: str) -> MovieData:
        """
        Scrape iTunes to find info about a movie, and it's M3U8 main_playlist.

        Args:
            url (str): An iTunes store movie URL.

        Raises:
            InvalidURL: `itunes_url` is not a valid iTunes store movie URL.
            PageLoadError: HTML page did not load properly.
            HTTPError: HTTP request failed.

        Returns:
            MovieData: A MovieData (NamedTuple) object with movie's name, and an M3U8 object of the main_playlist
            if the main_playlist is found. None otherwise.
        """
        regex_match = self.match_url(url, raise_error=True)

        url = regex_match.group(1)
        response = self._session.get(url)
        response.raise_for_status()

        # Response is JSON formatted
        if "application/json" in response.headers['content-type']:
            try:
                json_data = json.loads(response.content)

            except json.JSONDecodeError:
                raise ScraperException("Received an invalid JSON response.")

            return self._find_playlist_data_json(json_data)

        # Response is HTML formatted
        elif "text/html" in response.headers['content-type'] and response.status_code != 404:
            html_data = BeautifulSoup(response.content, "lxml")
            return self._find_playlist_data_html(html_data)

        raise ScraperException("Received an unexpected response.")

    def _find_playlist_data_json(self, json_data: dict) -> MovieData:
        """
        Scrape an iTunes JSON response to get movie info.

        Args:
            json_data (dict): A dictionary with iTunes data loaded from a JSON response.

        Returns:
            MovieData: A MovieData (NamedTuple) object with movie's name, and an M3U8 object of the main_playlist
            if the main_playlist is found. None otherwise.
        """
        itunes_id = json_data["pageData"]["id"]
        movie_data = json_data["storePlatformData"]["product-dv"]["results"][itunes_id]

        movie_title = movie_data["nameRaw"]
        movie_release_year = datetime.strptime(movie_data["releaseDate"], '%Y-%m-%d').year

        # Loop safely to find a matching main_playlist
        for offer in movie_data["offers"]:
            if isinstance(offer.get("type"), str) and offer["type"] in ["buy", "rent"]:
                if isinstance(offer.get("assets"), list) and len(offer["assets"]) > 0:
                    for asset in offer["assets"]:
                        playlist_url: str = asset["hlsUrl"]

                        # Assure main_playlist is valid
                        try:
                            m3u8.load(playlist_url)

                        # If m3u8 main_playlist is invalid, skip it
                        except (ValueError, HTTPError):
                            continue

                        return MovieData(
                            id=itunes_id,
                            name=movie_title,
                            release_year=movie_release_year,
                            playlist=playlist_url,
                            source=self.service_data,
                            scraper=self,
                        )

        return MovieData(
            id=itunes_id,
            name=movie_title,
            release_year=movie_release_year,
            playlist=None,
            source=self.service_data,
            scraper=self,
        )

    def _find_playlist_data_html(self, html_data: BeautifulSoup) -> MovieData:
        """
        Scrape an iTunes HTML page to get movie info.

        Note:
            This function uses web-scraping and because of that,
            it's a lot less reliable than `_find_playlist_data_itunes_json_`.

        Args:
            html_data (BeautifulSoup): A BeautifulSoup object of the page.

        Raises:
            PageLoadError: HTML page did not load properly.

        Returns:
            MovieData: A MovieData (NamedTuple) object with movie's name, and an M3U8 object of the main_playlist
            if the main_playlist is found. None otherwise.
        """
        itunes_id_tag: Tag | NavigableString | None = html_data.find("meta", attrs={"name": "apple:content_id"})
        if not isinstance(itunes_id_tag, Tag):
            raise ScraperException("HTML page did not load properly.")

        itunes_id: str = itunes_id_tag.attrs["content"]

        # Scrape a dictionary on the webpage that has playlists data
        shoebox_data_tag: Tag | NavigableString | None = \
            html_data.find("script", attrs={"id": "shoebox-ember-data-store", "type": "fastboot/shoebox"})

        # fastboot/shoebox data could not be found
        if not isinstance(shoebox_data_tag, Tag):
            raise ScraperException("fastboot/shoebox data could not be found.")

        # Convert to dictionary structure
        shoebox_data: dict = json.loads(str(shoebox_data_tag.contents[0]).strip())

        # Loop safely to find a matching main_playlist
        if isinstance(shoebox_data[itunes_id].get("included"), list):
            movie_data: dict = shoebox_data[itunes_id]
            movie_title: str = movie_data["data"]["attributes"]["name"]
            movie_release_year = datetime.strptime(movie_data["data"]["attributes"]["releaseDate"], '%Y-%m-%d').year

            for item in movie_data["included"]:
                if isinstance(item.get("type"), str) and item["type"] == "offer":
                    if isinstance(item.get("attributes"), dict) and \
                        isinstance(item["attributes"].get("assets"), list) and \
                            len(item["attributes"]["assets"]) > 0:

                        for asset in item["attributes"]["assets"]:
                            if isinstance(asset, dict) and isinstance(asset.get("hlsUrl"), str):
                                playlist_url: str = item["attributes"]["assets"][0]["hlsUrl"]

                                # Try loading the main_playlist to assure it's working
                                try:
                                    m3u8.load(playlist_url)

                                # If m3u8 main_playlist is invalid, skip it
                                except (ValueError, HTTPError):
                                    continue

                                return MovieData(
                                    id=itunes_id,
                                    name=movie_title,
                                    release_year=movie_release_year,
                                    playlist=playlist_url,
                                    source=self.service_data,
                                    scraper=self,
                                )
        else:
            raise ScraperException("Invalid shoebox data.")

        return MovieData(
            id=itunes_id,
            name=movie_title,
            release_year=movie_release_year,
            playlist=None,
            source=self.service_data,
            scraper=self,
        )
