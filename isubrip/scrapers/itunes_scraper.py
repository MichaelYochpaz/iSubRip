from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, urljoin, urlsplit

from httpx2 import HTTPError

from isubrip.logger import logger
from isubrip.scrapers.scraper import HLSScraper, PlaylistLoadError, ScraperError, ScraperFactory
from isubrip.subtitle_formats.webvtt import WebVTTSubtitles
from isubrip.utils import redact_url_query_param, remove_url_query_param, single_string_to_list

if TYPE_CHECKING:
    from collections.abc import Hashable

    import m3u8
    from m3u8.model import Media

    from isubrip.data_structures import Movie, ScrapedMediaResponse


REDIRECT_MAX_RETRIES = 5
REDIRECT_SLEEP_TIME = 2
REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
DSID_FALLBACK_STATUS_CODES = {401, 403, 404}
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
APPLE_MOVIE_MANIFEST_PATHS = {
    "play.itunes.apple.com": "/WebObjects/MZPlay.woa/hls/playlist.m3u8",
    "play-edge.itunes.apple.com": "/WebObjects/MZPlayLocal.woa/hls/playlist.m3u8",
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
        urls = single_string_to_list(item=url)
        anonymous_urls = [url_item for url_item in urls if not self._url_has_dsid(url=url_item)]
        dsid_urls = [url_item for url_item in urls if self._url_has_dsid(url=url_item)]

        # Preserve direct callers that explicitly provide only DSID-bearing URLs.
        if not anonymous_urls:
            supported_dsid_urls = [dsid_url for dsid_url in dsid_urls if self._is_apple_manifest_url(url=dsid_url)]

            if supported_dsid_urls:
                return await self._load_playlist_with_dsid_error(url=supported_dsid_urls, headers=headers)

            if dsid_urls:
                raise PlaylistLoadError(
                    "Refusing to send an Apple DSID to an unsupported or insecure playlist URL.",
                    url=remove_url_query_param(url=dsid_urls[-1], key="dsid"),
                )

            return await super().load_playlist(url=urls, headers=headers)

        anonymous_errors: dict[str, PlaylistLoadError] = {}

        for index, anonymous_url in enumerate(anonymous_urls, start=1):
            if len(anonymous_urls) > 1:
                logger.debug(f"Trying anonymous playlist candidate {index} of {len(anonymous_urls)}.")

            try:
                return await super().load_playlist(url=anonymous_url, headers=headers)

            except PlaylistLoadError as e:
                anonymous_errors[anonymous_url] = e

        fallback_urls = [
            dsid_url
            for dsid_url in dsid_urls
            if self._is_dsid_fallback_eligible(
                url=remove_url_query_param(url=dsid_url, key="dsid"),
                error=anonymous_errors.get(remove_url_query_param(url=dsid_url, key="dsid")),
            )
        ]

        if fallback_urls:
            logger.debug("Anonymous Apple movie manifest requests failed; trying the configured DSID fallback.")
            return await self._load_playlist_with_dsid_error(url=fallback_urls, headers=headers)

        # Prefer the last DSID-actionable failure, so a trailing unrelated error
        # (a timeout, a 5xx) cannot hide the guidance the user can act on.
        actionable_error = self._find_last_fallback_eligible_error(
            errors=[anonymous_errors[anonymous_url] for anonymous_url in anonymous_urls],
        )

        if actionable_error:
            raise PlaylistLoadError(
                "Apple's movie subtitle manifest is unavailable. The movie package may be unavailable, or Apple "
                "may require account entitlement. If the Apple account owns or has rented the movie, configure its "
                "numeric DSID using '--dsid', 'ISUBRIP_DSID', or 'scrapers.appletv.dsid'.",
                status_code=actionable_error.status_code,
                url=actionable_error.url,
            ) from actionable_error

        raise anonymous_errors[anonymous_urls[-1]]

    async def _load_playlist_with_dsid_error(
        self,
        url: str | list[str],
        headers: dict[str, str] | None = None,
    ) -> m3u8.M3U8:
        urls = single_string_to_list(item=url)
        errors: list[PlaylistLoadError] = []

        for index, dsid_url in enumerate(urls, start=1):
            if len(urls) > 1:
                logger.debug(f"Trying DSID fallback candidate {index} of {len(urls)}.")

            try:
                return await super().load_playlist(url=dsid_url, headers=headers)

            except PlaylistLoadError as e:
                errors.append(e)

        actionable_error = self._find_last_fallback_eligible_error(errors=errors)

        if actionable_error:
            raise PlaylistLoadError(
                "Apple's movie subtitle manifest remained unavailable after retrying with the configured DSID. "
                "The package may be unavailable; otherwise verify that the Apple account owns the movie or has "
                "an active rental.",
                status_code=actionable_error.status_code,
                url=actionable_error.url,
            ) from actionable_error

        if errors:
            raise errors[-1]

        return await super().load_playlist(url=urls, headers=headers)

    @classmethod
    def _find_last_fallback_eligible_error(
        cls,
        errors: list[PlaylistLoadError],
    ) -> PlaylistLoadError | None:
        return next(
            (
                error
                for error in reversed(errors)
                if cls._is_dsid_fallback_eligible(url=error.url, error=error)
            ),
            None,
        )

    @classmethod
    def _is_dsid_fallback_eligible(cls, url: str | None, error: PlaylistLoadError | None) -> bool:
        return bool(
            error
            and error.status_code in DSID_FALLBACK_STATUS_CODES
            and cls._is_apple_manifest_url(url=url),
        )

    @staticmethod
    def _is_apple_manifest_url(url: str | None) -> bool:
        if not url:
            return False

        url_parts = urlsplit(url)

        try:
            port = url_parts.port

        except ValueError:
            return False

        expected_path = APPLE_MOVIE_MANIFEST_PATHS.get(url_parts.hostname or "")
        return bool(
            url_parts.scheme.casefold() == "https"
            and port in (None, 443)
            and expected_path is not None
            and url_parts.path.casefold() == expected_path.casefold(),
        )

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
