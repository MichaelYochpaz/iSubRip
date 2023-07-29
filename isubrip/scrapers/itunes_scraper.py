from __future__ import annotations

from typing import TYPE_CHECKING

from isubrip.logger import logger
from isubrip.scrapers.scraper import M3U8Scraper, MovieScraper, ScraperError, ScraperFactory
from isubrip.subtitle_formats.webvtt import WebVTTSubtitles
from isubrip.utils import raise_for_status

if TYPE_CHECKING:
    from isubrip.data_structures import Movie, ScrapedMediaResponse


class ItunesScraper(M3U8Scraper, MovieScraper):
    """An iTunes movie data scraper."""
    id = "itunes"
    name = "iTunes"
    abbreviation = "iT"
    url_regex = r"(?P<base_url>https?://itunes\.apple\.com/(?:(?P<country_code>[a-z]{2})/)?(?P<media_type>movie|tv-show|tv-season|show)/(?:(?P<media_name>[\w\-%]+)/)?(?P<media_id>id\d{9,10}))(?:\?(?P<url_params>(?:).*))?"  # noqa: E501
    subtitles_class = WebVTTSubtitles
    is_movie_scraper = True
    uses_scrapers = ["appletv"]

    def __init__(self, config_data: dict | None = None):
        super().__init__(config_data=config_data)
        self._appletv_scraper = ScraperFactory().get_scraper_instance(scraper_id="appletv",
                                                                      config_data=self._config_data,
                                                                      raise_error=True)

    def get_data(self, url: str) -> ScrapedMediaResponse[Movie]:
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
        response = self._session.get(url=url, allow_redirects=False)
        raise_for_status(response=response)

        redirect_location = response.headers.get("Location")

        if response.status_code != 301 or not redirect_location:
            logger.debug(f"iTunes URL: {url} did not redirect to an Apple TV URL."
                         f"\nResponse code: '{response.status_code}'.")
            raise ScraperError("Apple TV redirect URL not found.")

        if not self._appletv_scraper.match_url(redirect_location):
            logger.debug(f"iTunes URL: {url} redirected to an invalid Apple TV URL: '{redirect_location}'.")
            raise ScraperError("Redirect URL is not a valid Apple TV URL.")

        return self._appletv_scraper.get_data(redirect_location)
