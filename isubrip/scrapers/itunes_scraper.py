from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Any

from isubrip.logger import logger
from isubrip.scrapers.scraper import HLSScraper, ScraperError, ScraperFactory
from isubrip.subtitle_formats.webvtt import WebVTTSubtitles

if TYPE_CHECKING:
    from m3u8.model import Media

    from isubrip.data_structures import Movie, ScrapedMediaResponse


REDIRECT_MAX_RETRIES = 5
REDIRECT_SLEEP_TIME = 2

class ItunesScraper(HLSScraper):
    """An iTunes movie data scraper."""
    id = "itunes"
    name = "iTunes"
    abbreviation = "iT"
    url_regex = re.compile(r"(?i)(?P<base_url>https?://itunes\.apple\.com/(?:(?P<country_code>[a-z]{2})/)?(?P<media_type>movie|tv-show|tv-season|show)/(?:(?P<media_name>[\w\-%]+)/)?(?P<media_id>id\d{9,10}))(?:\?(?P<url_params>.*))?")
    subtitles_class = WebVTTSubtitles
    is_movie_scraper = True
    uses_scrapers = ["appletv"]

    _subtitles_filters = {
        HLSScraper.M3U8Attribute.GROUP_ID.value: ["subtitles_ak", "subtitles_vod-ak-amt.tv.apple.com"],
        **HLSScraper._subtitles_filters,  # noqa: SLF001
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._appletv_scraper = ScraperFactory.get_scraper_instance(
            scraper_id="appletv",
            raise_error=True,
        )

    async def get_data(self, url: str) -> ScrapedMediaResponse[Movie]:
        """
        Scrape iTunes to find info about a movie, and it's M3U8 main_playlist.

        Args:
            url (str): An iTunes store movie URL.

        Raises:
            InvalidURL: `itunes_url` is not a valid iTunes store movie URL.
            PageLoadError: HTML page did not load properly.
            HTTPError: HTTP request failed.

        Returns:
            Movie: A Movie (NamedTuple) object with movie's name, and an M3U8 object of the main_playlist
            if the main_playlist is found. None otherwise.
        """
        regex_match = self.match_url(url, raise_error=True)
        url_data = regex_match.groupdict()
        country_code: str = url_data["country_code"]
        media_id: str = url_data["media_id"]
        appletv_redirect_finding_url = f"https://tv.apple.com/{country_code}/movie/{media_id}"

        logger.debug("Attempting to fetch redirect location from: " + appletv_redirect_finding_url)

        retries = 0
        while True:
            response = await self._async_session.get(url=appletv_redirect_finding_url, follow_redirects=False)
            if response.status_code != 301 and retries < REDIRECT_MAX_RETRIES:
                retries += 1
                logger.debug(f"AppleTV redirect URL not found (Response code: {response.status_code}),"
                               f" retrying... ({retries}/{REDIRECT_MAX_RETRIES})")
                await asyncio.sleep(REDIRECT_SLEEP_TIME)
                continue
            break

        redirect_location = response.headers.get("Location")

        if response.status_code != 301 or not redirect_location:
            raise ScraperError(f"AppleTV redirect URL not found (Response code: {response.status_code}).")

        # Add 'https:' if redirect_location starts with '//'
        if redirect_location.startswith('//'):
            redirect_location = "https:" + redirect_location

        logger.debug(f"Redirect URL: {redirect_location}")

        if not self._appletv_scraper.match_url(redirect_location):
            raise ScraperError("Redirect URL is not a valid AppleTV URL.")

        return await self._appletv_scraper.get_data(url=redirect_location)

    @staticmethod
    def parse_language_name(media_data: Media) -> str | None:
        name: str | None = media_data.name

        if name:
            return name.replace(' (forced)', '').strip()

        return None
