from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from httpx import HTTPError

from isubrip.logger import logger
from isubrip.scrapers.scraper import HLSScraper, ScraperError, ScraperFactory
from isubrip.subtitle_formats.webvtt import WebVTTSubtitles
from isubrip.utils import raise_for_status

if TYPE_CHECKING:
    from m3u8.model import Media

    from isubrip.data_structures import Movie, ScrapedMediaResponse


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
        url = regex_match.group(1)
        logger.debug(f"Fetching data from iTunes URL: {url}.")
        response = await self._async_session.get(url=url, follow_redirects=False)

        try:
            raise_for_status(response=response)

        except HTTPError as e:
            if response.status_code == 404:
                raise ScraperError(
                    "Media not found. This could indicate that the provided URL is invalid.",
                ) from e

            raise

        redirect_location = response.headers.get("Location")

        if response.status_code != 301 or not redirect_location:
            logger.debug(f"iTunes URL: {url} did not redirect to an Apple TV URL.\n"
                         f"Response status code: {response.status_code}.\n"
                         f"Response headers:\n{response.headers}.\n"
                         f"Response data:\n{response.text}.")
            raise ScraperError("Apple TV redirect URL not found.")

        if not self._appletv_scraper.match_url(redirect_location):
            logger.debug(f"iTunes URL: {url} redirected to an invalid Apple TV URL: '{redirect_location}'.")
            raise ScraperError("Redirect URL is not a valid Apple TV URL.")

        return await self._appletv_scraper.get_data(redirect_location)

    def parse_language_name(self, media_data: Media) -> str | None:
        name: str | None = media_data.name

        if name:
            return name.replace(' (forced)', '').strip()

        return None
