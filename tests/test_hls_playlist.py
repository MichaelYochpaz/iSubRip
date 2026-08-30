from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING

import httpx2
import m3u8
import pytest

from isubrip.constants import PACKAGE_NAME
from isubrip.data_structures import SubtitleMediaGroup
from isubrip.scrapers.itunes_scraper import ItunesScraper
from isubrip.scrapers.scraper import HLSScraper, PlaylistLoadError, SubtitlesDownloadError
from isubrip.subtitle_formats.webvtt import WebVTTSubtitles

if TYPE_CHECKING:
    from isubrip.data_structures import ScrapedMediaResponse

SEGMENT_PLAYLIST = """#EXTM3U
#EXT-X-TARGETDURATION:10
#EXTINF:10,
segment-0.ts
#EXT-X-ENDLIST
"""
WEBVTT_SEGMENT = b"""WEBVTT

00:00:00.000 --> 00:00:01.000
Fallback candidate
"""


class PlaylistTestScraper(HLSScraper):
    id = "playlist-test"
    name = "Playlist Test"
    abbreviation = "PT"
    url_regex = re.compile(".*")
    subtitles_class = WebVTTSubtitles

    async def get_data(self, url: str) -> ScrapedMediaResponse:
        raise NotImplementedError


def make_playlist_scraper(handler: httpx2.MockTransport) -> PlaylistTestScraper:
    scraper = object.__new__(PlaylistTestScraper)
    scraper._playlist_filters = None  # noqa: SLF001
    scraper._client = httpx2.AsyncClient(transport=handler, headers={"User-Agent": "test"})  # noqa: SLF001
    return scraper


def make_itunes_scraper() -> ItunesScraper:
    scraper = object.__new__(ItunesScraper)
    scraper._playlist_filters = None  # noqa: SLF001
    return scraper


def close_scraper(scraper: HLSScraper) -> None:
    if hasattr(scraper, "_client"):
        asyncio.run(scraper.async_close())


@pytest.mark.parametrize(
    "group_id",
    [
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
)
def test_itunes_subtitle_filters_match_all_known_apple_groups(group_id: str) -> None:
    scraper = make_itunes_scraper()
    playlist = m3u8.loads(
        f"""#EXTM3U
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="{group_id}",LANGUAGE="en",NAME="English",URI="sub.m3u8"
""",
    )

    assert len(scraper.find_matching_subtitles(main_playlist=playlist)) == 1


def test_itunes_subtitle_filters_reject_unknown_group() -> None:
    scraper = make_itunes_scraper()
    playlist = m3u8.loads(
        """#EXTM3U
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subtitles_unknown",LANGUAGE="en",NAME="English",URI="sub.m3u8"
""",
    )

    assert scraper.find_matching_subtitles(main_playlist=playlist) == []


def test_itunes_subtitle_matching_deduplicates_apple_cdn_mirrors() -> None:
    scraper = make_itunes_scraper()
    playlist = m3u8.loads(
        """#EXTM3U
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subtitles_vod-ap-amt.tv.apple.com",LANGUAGE="en",NAME="English",STABLE-RENDITION-ID="subtitle-en",PATHWAY-ID="ap",URI="https://vod-ap-amt.tv.apple.com/assets/en/subtitles.m3u8"
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subtitles_vod-ak-amt.tv.apple.com",LANGUAGE="en",NAME="English",STABLE-RENDITION-ID="subtitle-en",PATHWAY-ID="ak",URI="https://vod-ak-amt.tv.apple.com/assets/en/subtitles.m3u8"
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subtitles_vod-fa-amt.tv.apple.com",LANGUAGE="en",NAME="English",STABLE-RENDITION-ID="subtitle-en",PATHWAY-ID="fa",URI="https://vod-fa-amt.tv.apple.com/assets/en/subtitles.m3u8"
""",
    )

    matching_subtitle_groups = scraper.find_matching_subtitle_groups(main_playlist=playlist)

    assert len(matching_subtitle_groups) == 1
    assert [candidate.absolute_uri for candidate in matching_subtitle_groups[0].candidates] == [
        "https://vod-ap-amt.tv.apple.com/assets/en/subtitles.m3u8",
        "https://vod-ak-amt.tv.apple.com/assets/en/subtitles.m3u8",
        "https://vod-fa-amt.tv.apple.com/assets/en/subtitles.m3u8",
    ]
    assert scraper.find_matching_subtitles(main_playlist=playlist) == [matching_subtitle_groups[0].primary]


def test_itunes_subtitle_matching_keeps_apple_cdn_families_separate() -> None:
    scraper = make_itunes_scraper()
    playlist = m3u8.loads(
        """#EXTM3U
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subtitles_vod-ap-amt.tv.apple.com",LANGUAGE="en",NAME="English",URI="https://vod-ap-amt.tv.apple.com/assets/en/subtitles.m3u8"
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subtitles_vod-ak-aoc.tv.apple.com",LANGUAGE="en",NAME="English",URI="https://vod-ak-aoc.tv.apple.com/assets/en/subtitles.m3u8"
""",
    )

    matching_subtitle_groups = scraper.find_matching_subtitle_groups(main_playlist=playlist)

    assert len(matching_subtitle_groups) == 2


def test_itunes_subtitle_matching_keeps_distinct_renditions() -> None:
    scraper = make_itunes_scraper()
    playlist = m3u8.loads(
        """#EXTM3U
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subtitles_vod-ap-amt.tv.apple.com",LANGUAGE="en",NAME="English",FORCED=NO,URI="https://vod-ap-amt.tv.apple.com/assets/en/subtitles.m3u8"
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subtitles_vod-ak-amt.tv.apple.com",LANGUAGE="en",NAME="English",FORCED=NO,URI="https://vod-ak-amt.tv.apple.com/assets/en/subtitles.m3u8"
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subtitles_vod-ap-amt.tv.apple.com",LANGUAGE="en",NAME="English (forced)",FORCED=YES,URI="https://vod-ap-amt.tv.apple.com/assets/en/subtitles.m3u8"
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subtitles_vod-ak-amt.tv.apple.com",LANGUAGE="en",NAME="English (forced)",FORCED=YES,URI="https://vod-ak-amt.tv.apple.com/assets/en/subtitles.m3u8"
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subtitles_vod-ap-amt.tv.apple.com",LANGUAGE="en",NAME="English",FORCED=NO,URI="https://vod-ap-amt.tv.apple.com/assets/en/subtitles-alternate.m3u8"
""",
    )

    matching_subtitle_groups = scraper.find_matching_subtitle_groups(main_playlist=playlist)

    assert [
        (media_group.primary.name, media_group.primary.forced, len(media_group.candidates))
        for media_group in matching_subtitle_groups
    ] == [
        ("English", "NO", 2),
        ("English (forced)", "YES", 2),
        ("English", "NO", 1),
    ]


def test_itunes_subtitle_matching_keeps_different_queries_separate() -> None:
    scraper = make_itunes_scraper()
    playlist = m3u8.loads(
        """#EXTM3U
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subtitles_vod-ap-amt.tv.apple.com",LANGUAGE="en",NAME="English",URI="https://vod-ap-amt.tv.apple.com/assets/en/subtitles.m3u8?token=one"
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subtitles_vod-ak-amt.tv.apple.com",LANGUAGE="en",NAME="English",URI="https://vod-ak-amt.tv.apple.com/assets/en/subtitles.m3u8?token=two"
""",
    )

    assert len(scraper.find_matching_subtitle_groups(main_playlist=playlist)) == 2


def test_find_matching_subtitles_does_not_mutate_class_filters() -> None:
    scraper = make_itunes_scraper()
    playlist = m3u8.loads(
        """#EXTM3U
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subtitles_ak",LANGUAGE="en",NAME="English",URI="sub.m3u8"
""",
    )
    original_filters = {
        key: value.copy() if isinstance(value, list) else value
        for key, value in ItunesScraper._subtitles_filters.items()  # noqa: SLF001
    }

    assert len(scraper.find_matching_subtitles(main_playlist=playlist, language_filter=["en"])) == 1
    assert ItunesScraper._subtitles_filters == original_filters  # noqa: SLF001


@pytest.mark.parametrize("first_candidate_succeeds", [True, False])
def test_download_subtitle_group_uses_ordered_end_to_end_fallbacks(first_candidate_succeeds: bool) -> None:
    requests: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(str(request.url))

        if request.url.path == "/playlist.m3u8":
            return httpx2.Response(200, text=SEGMENT_PLAYLIST, request=request)

        if request.url.host == "first.example" and not first_candidate_succeeds:
            return httpx2.Response(503, request=request)

        return httpx2.Response(200, content=WEBVTT_SEGMENT, request=request)

    scraper = make_playlist_scraper(handler=httpx2.MockTransport(handler))
    main_playlist = m3u8.loads(
        """#EXTM3U
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subtitles",LANGUAGE="en",NAME="English",URI="https://first.example/playlist.m3u8"
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subtitles",LANGUAGE="en",NAME="English",URI="https://second.example/playlist.m3u8"
""",
    )
    media_group = SubtitleMediaGroup(candidates=tuple(main_playlist.media))

    try:
        subtitles_data = asyncio.run(scraper.download_subtitle_group(media_group=media_group))
    finally:
        close_scraper(scraper=scraper)

    assert b"Fallback candidate" in subtitles_data.content
    assert requests == (
        [
            "https://first.example/playlist.m3u8",
            "https://first.example/segment-0.ts",
        ]
        if first_candidate_succeeds
        else [
            "https://first.example/playlist.m3u8",
            "https://first.example/segment-0.ts",
            "https://second.example/playlist.m3u8",
            "https://second.example/segment-0.ts",
        ]
    )


def test_download_subtitle_group_raises_after_all_candidates_fail() -> None:
    requests: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(str(request.url))
        return httpx2.Response(404, request=request)

    scraper = make_playlist_scraper(handler=httpx2.MockTransport(handler))
    main_playlist = m3u8.loads(
        """#EXTM3U
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subtitles",LANGUAGE="en",NAME="English",URI="https://first.example/playlist.m3u8"
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subtitles",LANGUAGE="en",NAME="English",URI="https://second.example/playlist.m3u8"
""",
    )
    media_group = SubtitleMediaGroup(candidates=tuple(main_playlist.media))

    try:
        with pytest.raises(SubtitlesDownloadError) as exc_info:
            asyncio.run(scraper.download_subtitle_group(media_group=media_group))
    finally:
        close_scraper(scraper=scraper)

    assert isinstance(exc_info.value.original_exc, PlaylistLoadError)
    assert requests == [
        "https://first.example/playlist.m3u8",
        "https://second.example/playlist.m3u8",
    ]


def test_load_playlist_continues_to_successful_fallback() -> None:
    requests: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(str(request.url))

        if request.url == httpx2.URL("https://first.example/playlist.m3u8"):
            return httpx2.Response(404, request=request)

        if request.url == httpx2.URL("https://second.example/playlist.m3u8"):
            return httpx2.Response(200, text=SEGMENT_PLAYLIST, request=request)

        return httpx2.Response(500, request=request)

    scraper = make_playlist_scraper(handler=httpx2.MockTransport(handler))

    try:
        playlist = asyncio.run(
            scraper.load_playlist(
                url=[
                    "https://first.example/playlist.m3u8",
                    "https://second.example/playlist.m3u8",
                ],
            ),
        )
    finally:
        close_scraper(scraper=scraper)

    assert requests == [
        "https://first.example/playlist.m3u8",
        "https://second.example/playlist.m3u8",
    ]
    assert playlist.base_uri == "https://second.example/"
    assert len(playlist.segments) == 1


def test_load_playlist_rejects_redirect_response_with_body() -> None:
    requests: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(str(request.url))

        if request.url.path == "/redirect.m3u8":
            return httpx2.Response(
                302,
                headers={"Location": "https://fallback.example/playlist.m3u8"},
                text=SEGMENT_PLAYLIST.replace("segment-0.ts", "redirect-body.ts"),
                request=request,
            )

        if request.url == httpx2.URL("https://fallback.example/playlist.m3u8"):
            return httpx2.Response(
                200,
                text=SEGMENT_PLAYLIST.replace("segment-0.ts", "fallback-body.ts"),
                request=request,
            )

        return httpx2.Response(500, request=request)

    scraper = make_playlist_scraper(handler=httpx2.MockTransport(handler))

    try:
        playlist = asyncio.run(
            scraper.load_playlist(
                url=[
                    "https://example.com/redirect.m3u8",
                    "https://fallback.example/playlist.m3u8",
                ],
            ),
        )
    finally:
        close_scraper(scraper=scraper)

    assert requests == [
        "https://example.com/redirect.m3u8",
        "https://fallback.example/playlist.m3u8",
    ]
    assert playlist.base_uri == "https://fallback.example/"
    assert len(playlist.segments) == 1
    assert playlist.segments[0].uri == "fallback-body.ts"


def test_load_playlist_uses_the_scraper_client_timeout() -> None:
    observed_read_timeouts: list[float] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        observed_read_timeouts.append(request.extensions["timeout"]["read"])
        return httpx2.Response(200, text=SEGMENT_PLAYLIST, request=request)

    scraper = object.__new__(PlaylistTestScraper)
    scraper._playlist_filters = None  # noqa: SLF001
    scraper._client = httpx2.AsyncClient(  # noqa: SLF001
        transport=httpx2.MockTransport(handler),
        headers={"User-Agent": "test"},
        timeout=17,
    )

    try:
        asyncio.run(scraper.load_playlist(url="https://example.com/playlist.m3u8"))
    finally:
        close_scraper(scraper=scraper)

    assert observed_read_timeouts == [17]


def test_load_playlist_rejects_invalid_success_body_and_uses_fallback() -> None:
    requests: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(str(request.url))

        if request.url.host == "invalid.example":
            return httpx2.Response(200, text="<html>Access denied</html>", request=request)

        return httpx2.Response(200, text=SEGMENT_PLAYLIST, request=request)

    scraper = make_playlist_scraper(handler=httpx2.MockTransport(handler))

    try:
        playlist = asyncio.run(
            scraper.load_playlist(
                url=[
                    "https://invalid.example/playlist.m3u8",
                    "https://fallback.example/playlist.m3u8",
                ],
            ),
        )
    finally:
        close_scraper(scraper=scraper)

    assert requests == [
        "https://invalid.example/playlist.m3u8",
        "https://fallback.example/playlist.m3u8",
    ]
    assert playlist.base_uri == "https://fallback.example/"


@pytest.mark.parametrize(
    "response_body",
    ["opaque-invalid-playlist-body", "<html>Denied</html>", "#EXTM3U-invalid", "   "],
)
def test_load_playlist_rejects_all_invalid_success_bodies(response_body: str) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, text=response_body, request=request)

    scraper = make_playlist_scraper(handler=httpx2.MockTransport(handler))

    try:
        with pytest.raises(PlaylistLoadError, match="invalid M3U8 response") as exc_info:
            asyncio.run(scraper.load_playlist(url="https://example.com/playlist.m3u8"))
    finally:
        close_scraper(scraper=scraper)

    assert response_body not in str(exc_info.value)


def test_load_playlist_all_failures_raise_without_exposing_dsid(caplog: pytest.LogCaptureFixture) -> None:
    account_dsid = "1234567890"
    response_body_marker = "opaque-auth-value"
    playlist_url = f"https://play.itunes.apple.com/playlist.m3u8?cc=US&dsid={account_dsid}"

    def handler(request: httpx2.Request) -> httpx2.Response:  # noqa: ARG001
        return httpx2.Response(404, text=f'{{"dsid":"{account_dsid}","token":"{response_body_marker}"}}')

    scraper = make_playlist_scraper(handler=httpx2.MockTransport(handler))

    try:
        with caplog.at_level(logging.DEBUG, logger=PACKAGE_NAME), pytest.raises(PlaylistLoadError) as exc_info:
            asyncio.run(scraper.load_playlist(url=playlist_url))
    finally:
        close_scraper(scraper=scraper)

    assert account_dsid not in str(exc_info.value)
    assert account_dsid not in caplog.text
    assert response_body_marker not in str(exc_info.value)
    assert response_body_marker not in caplog.text
    assert "dsid=REDACTED" in caplog.text
