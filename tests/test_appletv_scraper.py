from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any

import pytest

from isubrip.scrapers.appletv_scraper import AppleTVScraper
from isubrip.scrapers.scraper import ScraperError


def make_playable(movie_id: str) -> dict[str, Any]:
    return {
        "channelId": "tvs.sbd.9001",
        "isEntitledToPlay": False,
        "isDownloadable": False,
        "canonicalId": f"canonical-{movie_id}",
        "canonicalMetadata": {"movieTitle": f"Movie {movie_id}", "releaseDate": 1704067200000},
        "itunesMediaApiData": {
            "id": movie_id,
            "offers": [{"hlsUrl": f"https://example.com/{movie_id}.m3u8", "durationInMilliseconds": 90000}],
        },
    }


def make_scraper(monkeypatch: pytest.MonkeyPatch, playables: list[dict[str, Any]]) -> AppleTVScraper:
    scraper = object.__new__(AppleTVScraper)
    monkeypatch.setattr(scraper, "config", None)

    async def fetch_api_data(**_kwargs: Any) -> dict[str, Any]:
        return {"playables": {str(index): playable for index, playable in enumerate(playables)}}

    monkeypatch.setattr(scraper, "_fetch_api_data", fetch_api_data)
    return scraper


INVALID_MEDIA_DATA: list[dict[str, Any]] = [
    {},
    {"itunesMediaApiData": None},
    {"itunesMediaApiData": []},
    {"itunesMediaApiData": "unavailable"},
    {"itunesMediaApiData": {}},
    {"itunesMediaApiData": {"id": None}},
    {"itunesMediaApiData": {"id": 123}},
    {"itunesMediaApiData": {"id": ""}},
    {"itunesMediaApiData": {"id": " \t\n"}},
]


@pytest.mark.parametrize("invalid_media_data", INVALID_MEDIA_DATA)
@pytest.mark.parametrize("invalid_first", [True, False])
def test_get_movie_data_skips_invalid_itunes_siblings(
    monkeypatch: pytest.MonkeyPatch,
    invalid_media_data: dict[str, Any],
    invalid_first: bool,
) -> None:
    invalid = {"channelId": "tvs.sbd.9001", **invalid_media_data}
    valid = [make_playable("101"), make_playable("102")]
    playables = [invalid, *valid] if invalid_first else [*valid, invalid]
    scraper = make_scraper(monkeypatch, playables)

    response = asyncio.run(scraper.get_movie_data("143441", "canonical-movie"))

    assert [movie.id for movie in response.media_data] == ["101", "102"]
    assert [movie.name for movie in response.media_data] == ["Movie 101", "Movie 102"]
    assert [movie.playlist for movie in response.media_data] == [
        ["https://example.com/101.m3u8"],
        ["https://example.com/102.m3u8"],
    ]
    assert all(movie.duration == dt.timedelta(seconds=90) for movie in response.media_data)
    assert response.metadata_scraper == "appletv"
    assert response.playlist_scraper == "itunes"
    assert response.original_data == {"playables": {str(i): playable for i, playable in enumerate(playables)}}


def test_get_movie_data_reports_all_invalid_itunes_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    playables = [{"channelId": "tvs.sbd.9001", **invalid} for invalid in INVALID_MEDIA_DATA]
    scraper = make_scraper(monkeypatch, playables)

    with pytest.raises(ScraperError) as exc_info:
        asyncio.run(scraper.get_movie_data("143441", "canonical-movie"))

    assert str(exc_info.value) == "No usable iTunes movie metadata was found for this storefront."


@pytest.mark.parametrize("offer_fields", [{}, {"offers": None}, {"offers": []}])
@pytest.mark.parametrize("preorder", [False, True])
def test_get_movie_data_preserves_metadata_without_offers(
    monkeypatch: pytest.MonkeyPatch,
    offer_fields: dict[str, Any],
    preorder: bool,
) -> None:
    playable = make_playable("101")
    playable["itunesMediaApiData"] = {"id": "101", **offer_fields}
    if preorder:
        playable["itunesMediaApiData"]["futureRentalAvailabilityDate"] = "2030-01-02"
    scraper = make_scraper(monkeypatch, [playable])

    response = asyncio.run(scraper.get_movie_data("143441", "canonical-movie"))

    assert len(response.media_data) == 1
    movie = response.media_data[0]
    assert movie.id == "101"
    assert movie.playlist is None
    assert movie.duration is None
    assert movie.preorder_availability_date == (dt.datetime(2030, 1, 2) if preorder else None)


@pytest.mark.parametrize(
    ("playables", "message"),
    [
        ([], "No iTunes playables could be found."),
        ([{"channelId": "tvs.sbd.9000"}], "No iTunes playables could be found."),
        ([{"channelId": "tvs.sbd.4000"}], "Scraping AppleTV+ content is not currently supported."),
    ],
)
def test_get_movie_data_preserves_missing_channel_errors(
    monkeypatch: pytest.MonkeyPatch,
    playables: list[dict[str, Any]],
    message: str,
) -> None:
    scraper = make_scraper(monkeypatch, playables)

    with pytest.raises(ScraperError) as exc_info:
        asyncio.run(scraper.get_movie_data("143441", "canonical-movie"))

    assert str(exc_info.value) == message


def test_get_movie_data_does_not_hide_unrelated_metadata_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    playable = make_playable("101")
    del playable["canonicalMetadata"]["movieTitle"]
    scraper = make_scraper(monkeypatch, [playable, make_playable("102")])

    with pytest.raises(KeyError, match="movieTitle"):
        asyncio.run(scraper.get_movie_data("143441", "canonical-movie"))
