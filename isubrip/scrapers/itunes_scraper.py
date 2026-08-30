from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, urljoin, urlsplit

from httpx2 import HTTPError

from isubrip.logger import logger
from isubrip.scrapers.scraper import HLSScraper, PlaylistLoadError, ScraperError, ScraperFactory
from isubrip.subtitle_formats.webvtt import WebVTTSubtitles
from isubrip.utils import redact_url_query_param

if TYPE_CHECKING:
    from collections.abc import Hashable

    import m3u8
    from m3u8.model import Media

    from isubrip.data_structures import Movie, ScrapedMediaResponse


REDIRECT_MAX_RETRIES = 5
REDIRECT_SLEEP_TIME = 2
REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
APPLE_SUBTITLE_CDN_HOST_REGEX = re.compile(
    r"vod-(?:ap|fa|ak)-(?P<family>amt|aoc)\.tv\.apple\.com",
    flags=re.IGNORECASE,
)
APPLE_SUBTITLE_GROUP_ID_REGEX = re.compile(
    r"subtitles_(?:(?:ap|fa|ak)|vod-(?:ap|fa|ak)-(?P<family>amt|aoc)\.tv\.apple\.com)",
    flags=re.IGNORECASE,
)
APPLE_SUBTITLE_RENDITION_ATTRIBUTES = (
    "type",
    "language",
    "name",
    "default",
    "autoselect",
    "forced",
    "assoc_language",
    "instream_id",
    "characteristics",
    "channels",
    "stable_rendition_id",
)
APPLE_MANIFEST_HOSTS = {
    "play.itunes.apple.com",
    "play-edge.itunes.apple.com",
}


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
        HLSScraper.M3U8Attribute.GROUP_ID.value: [
            "subtitles_ap",
            "subtitles_fa",
            "subtitles_ak",
            "subtitles_vod-ap-amt.tv.apple.com",
            "subtitles_vod-fa-amt.tv.apple.com",
            "subtitles_vod-ak-amt.tv.apple.com",
            "subtitles_vod-ap-aoc.tv.apple.com",
            "subtitles_vod-fa-aoc.tv.apple.com",
            "subtitles_vod-ak-aoc.tv.apple.com",
        ],
        **HLSScraper._subtitles_filters,  # noqa: SLF001
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._appletv_scraper = ScraperFactory.get_scraper_instance(
            scraper_id="appletv",
            raise_error=True,
        )

    def _get_subtitle_media_group_key(self, subtitles_media: Media) -> Hashable:
        subtitle_url = subtitles_media.uri
        group_id_match = APPLE_SUBTITLE_GROUP_ID_REGEX.fullmatch(subtitles_media.group_id or "")

        if not subtitle_url or not group_id_match:
            return super()._get_subtitle_media_group_key(subtitles_media=subtitles_media)

        url_parts = urlsplit(subtitle_url)
        host_match = APPLE_SUBTITLE_CDN_HOST_REGEX.fullmatch(url_parts.hostname or "")

        if host_match:
            cdn_family = host_match.group("family").casefold()
            canonical_url = url_parts._replace(netloc=f"vod-apple-{cdn_family}.tv.apple.com").geturl()

        else:
            cdn_family = (group_id_match.group("family") or "generic").casefold()
            canonical_url = subtitle_url

        rendition_attributes = tuple(
            getattr(subtitles_media, attribute_name, None)
            for attribute_name in APPLE_SUBTITLE_RENDITION_ATTRIBUTES
        )
        return cdn_family, canonical_url, rendition_attributes

    async def get_data(self, url: str) -> ScrapedMediaResponse[Movie]:
        """
        Scrape iTunes to find info about a movie, and it's M3U8 main_playlist.

        Args:
            url (str): An iTunes store movie URL.

        Raises:
            ScraperError: If the Apple TV redirect cannot be retrieved or is invalid.

        Returns:
            ScrapedMediaResponse: Media data returned by the Apple TV scraper.
        """
        regex_match = self.match_url(url, raise_error=True)
        url_data = regex_match.groupdict()
        country_code: str = url_data["country_code"]
        media_id: str = url_data["media_id"]
        appletv_redirect_finding_url = f"https://tv.apple.com/{country_code}/movie/{media_id}"

        logger.debug("Attempting to fetch redirect location from: " + appletv_redirect_finding_url)

        response = None
        redirect_location = None

        for attempt in range(REDIRECT_MAX_RETRIES + 1):
            try:
                response = await self._client.get(url=appletv_redirect_finding_url, follow_redirects=False)

            except HTTPError as e:
                if attempt >= REDIRECT_MAX_RETRIES:
                    raise ScraperError("AppleTV redirect request failed after multiple attempts.") from e

                logger.debug(
                    f"AppleTV redirect request failed ({type(e).__name__}), retrying... "
                    f"({attempt + 1}/{REDIRECT_MAX_RETRIES})",
                )
                await asyncio.sleep(REDIRECT_SLEEP_TIME)
                continue

            redirect_location = response.headers.get("Location")

            if response.status_code in REDIRECT_STATUS_CODES and redirect_location:
                break

            is_transient_failure = response.status_code == 429 or response.status_code >= 500
            is_incomplete_redirect = response.status_code in REDIRECT_STATUS_CODES and not redirect_location

            if attempt >= REDIRECT_MAX_RETRIES or not (is_transient_failure or is_incomplete_redirect):
                break

            logger.debug(
                f"AppleTV redirect URL not found (Response code: {response.status_code}), retrying... "
                f"({attempt + 1}/{REDIRECT_MAX_RETRIES})",
            )
            await asyncio.sleep(REDIRECT_SLEEP_TIME)

        if response is None:
            raise ScraperError("AppleTV redirect request failed.")

        if response.status_code not in REDIRECT_STATUS_CODES or not redirect_location:
            raise ScraperError(f"AppleTV redirect URL not found (Response code: {response.status_code}).")

        redirect_location = urljoin(appletv_redirect_finding_url, redirect_location)

        logger.debug(f"Redirect URL: {redact_url_query_param(url=redirect_location, key='dsid')}")

        if not self._appletv_scraper.match_url(redirect_location):
            raise ScraperError("Redirect URL is not a valid AppleTV URL.")

        return await self._appletv_scraper.get_data(url=redirect_location)

    async def load_playlist(self, url: str | list[str], headers: dict[str, str] | None = None) -> m3u8.M3U8:
        try:
            return await super().load_playlist(url=url, headers=headers)

        except PlaylistLoadError as e:
            if e.status_code == 404 and self._is_apple_manifest_url(url=e.url):
                if self._url_has_dsid(url=e.url):
                    raise PlaylistLoadError(
                        "Apple denied access to movie's subtitle manifest (HTTP 404). Verify that the "
                        "configured DSID belongs to the Apple account that owns the movie or has an active rental.",
                        status_code=e.status_code,
                        url=e.url,
                    ) from e

                raise PlaylistLoadError(
                    "Apple denied access to movie's subtitle manifest (HTTP 404) because no DSID was included. "
                    "Set the numeric DSID for the Apple account that owns the movie or has an active rental using "
                    "the '--dsid' command-line option, the 'ISUBRIP_DSID' environment variable, or the "
                    "'scrapers.appletv.dsid' setting in config.toml",
                    status_code=e.status_code,
                    url=e.url,
                ) from e

            raise

    @staticmethod
    def _is_apple_manifest_url(url: str | None) -> bool:
        if not url:
            return False

        url_parts = urlsplit(url)
        return url_parts.hostname in APPLE_MANIFEST_HOSTS and url_parts.path.endswith("/playlist.m3u8")

    @staticmethod
    def _url_has_dsid(url: str | None) -> bool:
        if not url:
            return False

        return any(key.casefold() == "dsid" for key, _ in parse_qsl(urlsplit(url).query, keep_blank_values=True))

    @staticmethod
    def parse_language_name(media_data: Media) -> str | None:
        name: str | None = media_data.name

        if name:
            return name.replace(' (forced)', '').strip()

        return None
