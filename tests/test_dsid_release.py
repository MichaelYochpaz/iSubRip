from __future__ import annotations

import asyncio
import datetime as dt
import logging
import re
from typing import TYPE_CHECKING, Any

import httpx2
from pydantic import ValidationError
import pytest

from isubrip.__main__ import format_cli_command_for_logging, load_config, main, parse_cli_args, parse_config
from isubrip.commands.download import download, download_media_item
from isubrip.config import Config
from isubrip.constants import PACKAGE_NAME, PACKAGE_VERSION
from isubrip.data_structures import Movie, ScrapedMediaResponse, SubtitlesDownloadResults
from isubrip.scrapers.appletv_scraper import AppleTVScraper
from isubrip.scrapers.itunes_scraper import REDIRECT_SLEEP_TIME, ItunesScraper
from isubrip.scrapers.scraper import HLSScraper, PlaylistLoadError, ScraperError, ScraperFactory
from isubrip.subtitle_formats.webvtt import WebVTTSubtitles
from isubrip.utils import (
    add_or_replace_url_query_param,
    format_config_validation_error,
    raise_for_status,
    redact_url_query_param,
)

if TYPE_CHECKING:
    from pathlib import Path


class PlaylistTestScraper(HLSScraper):
    id = "playlist-test"
    name = "Playlist Test"
    abbreviation = "PT"
    url_regex = re.compile(".*")
    subtitles_class = WebVTTSubtitles

    async def get_data(self, url: str) -> ScrapedMediaResponse:
        raise NotImplementedError


def make_itunes_scraper(handler: httpx2.MockTransport | None = None) -> ItunesScraper:
    scraper = object.__new__(ItunesScraper)
    scraper._playlist_filters = None  # noqa: SLF001

    if handler:
        scraper._client = httpx2.AsyncClient(transport=handler, headers={"User-Agent": "test"})  # noqa: SLF001

    return scraper


def close_scraper(scraper: HLSScraper) -> None:
    if hasattr(scraper, "_client"):
        asyncio.run(scraper.async_close())


@pytest.mark.parametrize("redirect_status", [301, 302, 303, 307, 308])
def test_itunes_get_data_accepts_standard_relative_redirects(redirect_status: int) -> None:
    requests: list[str] = []
    redirected_urls: list[str] = []
    expected_response = ScrapedMediaResponse(
        media_data=[],
        metadata_scraper="appletv",
        playlist_scraper="itunes",
        original_data={},
    )

    class FakeAppleTVScraper:
        @staticmethod
        def match_url(url: str) -> bool:
            redirected_urls.append(url)
            return True

        @staticmethod
        async def get_data(url: str) -> ScrapedMediaResponse:
            redirected_urls.append(url)
            return expected_response

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(str(request.url))
        return httpx2.Response(
            redirect_status,
            headers={"Location": "/us/movie/test/umc.cmc.12345678901234567890123"},
            request=request,
        )

    scraper = make_itunes_scraper(handler=httpx2.MockTransport(handler))
    scraper._appletv_scraper = FakeAppleTVScraper()  # type: ignore[assignment]  # noqa: SLF001

    try:
        response = asyncio.run(
            scraper.get_data("https://itunes.apple.com/us/movie/test/id1234567890"),
        )
    finally:
        close_scraper(scraper=scraper)

    expected_redirect = "https://tv.apple.com/us/movie/test/umc.cmc.12345678901234567890123"
    assert response is expected_response
    assert requests == ["https://tv.apple.com/us/movie/id1234567890"]
    assert redirected_urls == [expected_redirect, expected_redirect]


def test_itunes_get_data_retries_transport_and_server_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_count = 0
    sleep_delays: list[float] = []
    expected_response = ScrapedMediaResponse(
        media_data=[],
        metadata_scraper="appletv",
        playlist_scraper="itunes",
        original_data={},
    )

    class FakeAppleTVScraper:
        @staticmethod
        def match_url(url: str) -> bool:  # noqa: ARG004
            return True

        @staticmethod
        async def get_data(url: str) -> ScrapedMediaResponse:  # noqa: ARG004
            return expected_response

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal request_count
        request_count += 1

        if request_count == 1:
            raise httpx2.ConnectError("Temporary connection failure.", request=request)

        if request_count == 2:
            return httpx2.Response(500, request=request)

        return httpx2.Response(
            301,
            headers={"Location": "//tv.apple.com/us/movie/test/umc.cmc.12345678901234567890123"},
            request=request,
        )

    async def fake_sleep(delay: float) -> None:
        sleep_delays.append(delay)

    monkeypatch.setattr("isubrip.scrapers.itunes_scraper.asyncio.sleep", fake_sleep)
    scraper = make_itunes_scraper(handler=httpx2.MockTransport(handler))
    scraper._appletv_scraper = FakeAppleTVScraper()  # type: ignore[assignment]  # noqa: SLF001

    try:
        response = asyncio.run(
            scraper.get_data("https://itunes.apple.com/us/movie/test/id1234567890"),
        )
    finally:
        close_scraper(scraper=scraper)

    assert response is expected_response
    assert request_count == 3
    assert sleep_delays == [REDIRECT_SLEEP_TIME, REDIRECT_SLEEP_TIME]


def test_itunes_get_data_does_not_retry_a_permanent_404(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[str] = []
    sleep_delays: list[float] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(str(request.url))
        return httpx2.Response(404, request=request)

    async def fake_sleep(delay: float) -> None:
        sleep_delays.append(delay)

    monkeypatch.setattr("isubrip.scrapers.itunes_scraper.asyncio.sleep", fake_sleep)
    scraper = make_itunes_scraper(handler=httpx2.MockTransport(handler))

    try:
        with pytest.raises(ScraperError, match=r"Response code: 404"):
            asyncio.run(scraper.get_data("https://itunes.apple.com/us/movie/test/id1234567890"))
    finally:
        close_scraper(scraper=scraper)

    assert requests == ["https://tv.apple.com/us/movie/id1234567890"]
    assert sleep_delays == []


def test_add_or_replace_url_query_param_appends_to_url_without_query() -> None:
    assert add_or_replace_url_query_param(
        url="https://play.itunes.apple.com/playlist.m3u8",
        key="dsid",
        value="123",
    ) == "https://play.itunes.apple.com/playlist.m3u8?dsid=123"


def test_add_or_replace_url_query_param_appends_to_existing_query() -> None:
    assert add_or_replace_url_query_param(
        url="https://play.itunes.apple.com/playlist.m3u8?cc=US&a=1",
        key="dsid",
        value="123",
    ) == "https://play.itunes.apple.com/playlist.m3u8?cc=US&a=1&dsid=123"


def test_add_or_replace_url_query_param_replaces_existing_value_and_duplicates() -> None:
    assert add_or_replace_url_query_param(
        url="https://play.itunes.apple.com/playlist.m3u8?cc=US&dsid=111&a=1&dsid=222",
        key="dsid",
        value="333",
    ) == "https://play.itunes.apple.com/playlist.m3u8?cc=US&a=1&dsid=333"


def test_add_or_replace_url_query_param_replaces_key_case_insensitively() -> None:
    assert add_or_replace_url_query_param(
        url="https://example.com/playlist.m3u8?DSID=old&cc=US",
        key="dsid",
        value="new",
    ) == "https://example.com/playlist.m3u8?cc=US&dsid=new"


def test_add_or_replace_url_query_param_preserves_existing_query_encoding_and_fragment() -> None:
    assert add_or_replace_url_query_param(
        url="https://example.com/playlist.m3u8?opaque=a%2Fb%20c&flag&empty=&dsid=old#part",
        key="dsid",
        value="123",
    ) == "https://example.com/playlist.m3u8?opaque=a%2Fb%20c&flag&empty=&dsid=123#part"


def test_redact_url_query_param_redacts_without_changing_original_url() -> None:
    url = "https://play.itunes.apple.com/playlist.m3u8?cc=US&dsid=111&a=1&dsid=222"

    assert redact_url_query_param(url=url, key="dsid") == (
        "https://play.itunes.apple.com/playlist.m3u8?cc=US&dsid=REDACTED&a=1&dsid=REDACTED"
    )
    assert url == "https://play.itunes.apple.com/playlist.m3u8?cc=US&dsid=111&a=1&dsid=222"


def test_redact_url_query_param_is_case_insensitive_and_preserves_other_parameters() -> None:
    assert redact_url_query_param(
        url="https://example.com/playlist.m3u8?opaque=a%2Fb%20c&DSID=123&flag",
        key="dsid",
    ) == "https://example.com/playlist.m3u8?opaque=a%2Fb%20c&DSID=REDACTED&flag"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1234567890", "1234567890"),
        (" 1234567890 ", "1234567890"),
        (1234567890, "1234567890"),
    ],
)
def test_appletv_dsid_config_validation_accepts_supported_values(value: Any, expected: str) -> None:
    assert AppleTVScraper.ScraperConfig(dsid=value).dsid == expected


@pytest.mark.parametrize("value", ["mz_at0-123", "123 456", "123.456", "١٢٣", True, False, -123])
def test_appletv_dsid_config_validation_rejects_invalid_values(value: Any) -> None:
    with pytest.raises(ValidationError, match="DSID"):
        AppleTVScraper.ScraperConfig(dsid=value)


@pytest.mark.parametrize("value", [None, "", "   "])
def test_appletv_dsid_config_treats_empty_values_as_unset(value: Any) -> None:
    assert AppleTVScraper.ScraperConfig(dsid=value).dsid is None


def test_application_config_allows_an_unset_appletv_dsid() -> None:
    assert Config.model_validate({}).scrapers.appletv.dsid is None

    config = Config.model_validate({"scrapers": {"appletv": {"dsid": "1234567890"}}})
    assert config.scrapers.appletv.dsid == "1234567890"


def test_load_config_uses_cli_then_environment_then_toml_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[scrapers.appletv]\ndsid = "111"\n', encoding="utf-8")

    monkeypatch.setenv("ISUBRIP_DSID", "222")
    assert load_config(config_file_location=config_path).scrapers.appletv.dsid == "222"
    assert load_config(config_file_location=config_path, dsid_override="333").scrapers.appletv.dsid == "333"

    monkeypatch.delenv("ISUBRIP_DSID")
    assert load_config(config_file_location=config_path).scrapers.appletv.dsid == "111"


def test_load_config_ignores_empty_cli_and_environment_dsid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[scrapers.appletv]\ndsid = "111"\n', encoding="utf-8")
    monkeypatch.setenv("ISUBRIP_DSID", "  ")

    assert load_config(config_file_location=config_path, dsid_override="").scrapers.appletv.dsid == "111"


def test_load_config_allows_no_file_and_no_dsid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ISUBRIP_DSID", raising=False)
    assert load_config(config_file_location=None).scrapers.appletv.dsid is None


def test_cli_dsid_is_parsed_but_redacted_from_command_log() -> None:
    account_dsid = "9988776655"
    url = "https://tv.apple.com/us/movie/test/umc.cmc.12345678901234567890123"
    cli_args = parse_cli_args([url, "--dsid", account_dsid])
    logged_command = format_cli_command_for_logging(cli_args=cli_args)

    assert cli_args.urls == [url]
    assert cli_args.dsid == account_dsid
    assert account_dsid not in logged_command
    assert "--dsid REDACTED" in logged_command


def test_cli_command_log_redacts_dsid_from_input_url() -> None:
    account_dsid = "9988776655"
    url = f"https://itunes.apple.com/us/movie/test/id1234567890?DSID={account_dsid}"
    logged_command = format_cli_command_for_logging(cli_args=parse_cli_args([url]))

    assert account_dsid not in logged_command
    assert "DSID=REDACTED" in logged_command


@pytest.mark.parametrize(
    ("args", "expected_exit_code", "expected_output"),
    [
        (["--help"], 0, "Download subtitles from Apple TV or iTunes movie URLs."),
        (["--version"], 0, f"{PACKAGE_NAME} {PACKAGE_VERSION}"),
        ([], 2, "the following arguments are required: URL"),
    ],
)
def test_cli_information_and_missing_url_exit_codes(
    args: list[str],
    expected_exit_code: int,
    expected_output: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_cli_args(args)

    captured = capsys.readouterr()
    assert exc_info.value.code == expected_exit_code
    assert expected_output in captured.out + captured.err


@pytest.mark.parametrize(("download_succeeded", "expected_exit_code"), [(True, None), (False, 1)])
def test_main_maps_download_result_to_exit_code(
    download_succeeded: bool,
    expected_exit_code: int | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_main() -> bool:
        return download_succeeded

    monkeypatch.setattr("isubrip.__main__._main", fake_main)
    monkeypatch.setattr("isubrip.__main__.handle_log_rotation", lambda rotation_size: None)  # noqa: ARG005
    monkeypatch.setattr(ScraperFactory, "get_initialized_scrapers", staticmethod(list))

    if expected_exit_code is None:
        assert main() is None
        return

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == expected_exit_code


@pytest.mark.parametrize(
    ("urls", "expected"),
    [
        (["https://example.com/success"], True),
        (["https://example.com/failure"], False),
        (["https://example.com/failure", "https://example.com/success"], True),
    ],
)
def test_download_aggregates_success_across_urls(
    urls: list[str],
    expected: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MetadataScraper:
        async def get_data(self, url: str) -> ScrapedMediaResponse[Movie]:
            return ScrapedMediaResponse(
                media_data=[Movie(name=url, release_date=2026, playlist="https://example.com/master.m3u8")],
                metadata_scraper="metadata-test",
                playlist_scraper=PlaylistTestScraper.id,
                original_data={},
            )

    playlist_scraper = object.__new__(PlaylistTestScraper)

    def fake_get_scraper_instance(
        scraper_id: str | None = None,  # noqa: ARG001
        url: str | None = None,
        **kwargs: Any,  # noqa: ARG001
    ) -> MetadataScraper | PlaylistTestScraper:
        return MetadataScraper() if url is not None else playlist_scraper

    async def fake_download_media(**kwargs: Any) -> bool:
        media_item: Movie = kwargs["media_item"]
        return media_item.name.endswith("/success")

    monkeypatch.setattr(ScraperFactory, "get_scraper_instance", staticmethod(fake_get_scraper_instance))
    monkeypatch.setattr("isubrip.commands.download.download_media", fake_download_media)

    assert asyncio.run(download(*urls, download_path=tmp_path)) is expected


def test_download_reports_failure_without_logging_url_dsid(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    account_dsid = "9988776655"
    url = f"https://example.com/not-supported?dsid={account_dsid}"

    with caplog.at_level(logging.DEBUG, logger=PACKAGE_NAME):
        assert asyncio.run(download(url, download_path=tmp_path)) is False

    assert account_dsid not in caplog.text
    assert "dsid=REDACTED" in caplog.text


def test_config_validation_error_omits_input_values() -> None:
    invalid_dsid = "mz_at0-1234567890"
    unrelated_value = "opaque-config-value"

    with pytest.raises(ValidationError) as exc_info:
        Config.model_validate(
            {
                "scrapers": {
                    "appletv": {
                        "dsid": invalid_dsid,
                        "legacy": {"token": unrelated_value},
                    },
                },
            },
        )

    formatted_error = format_config_validation_error(exc=exc_info.value)
    assert invalid_dsid not in formatted_error
    assert unrelated_value not in formatted_error
    assert "  - scrapers.appletv.dsid: Apple DSID" in formatted_error


def test_invalid_cli_dsid_error_identifies_the_cli_source(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("[general]\ncheck-for-updates = false\n", encoding="utf-8")
    invalid_dsid = "mz_at0-1234567890"

    with caplog.at_level(logging.DEBUG, logger=PACKAGE_NAME), pytest.raises(SystemExit):
        parse_config(config_file_location=config_path, dsid_override=invalid_dsid)

    assert "Invalid DSID from the --dsid option" in caplog.text
    assert "Invalid configuration file" not in caplog.text
    assert invalid_dsid not in caplog.text


def test_invalid_environment_dsid_error_identifies_the_environment_source(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("[general]\ncheck-for-updates = false\n", encoding="utf-8")
    invalid_dsid = "not-a-dsid"
    monkeypatch.setenv("ISUBRIP_DSID", invalid_dsid)

    with caplog.at_level(logging.DEBUG, logger=PACKAGE_NAME), pytest.raises(SystemExit):
        parse_config(config_file_location=config_path)

    assert "Invalid DSID from the ISUBRIP_DSID environment variable" in caplog.text
    assert "Invalid configuration file" not in caplog.text
    assert invalid_dsid not in caplog.text


def test_raise_for_status_omits_response_body_from_logs(caplog: pytest.LogCaptureFixture) -> None:
    response_body_marker = "opaque-auth-response-value"
    request = httpx2.Request("GET", "https://example.com/api")
    response = httpx2.Response(500, text=response_body_marker, request=request)

    with caplog.at_level(logging.DEBUG, logger=PACKAGE_NAME), pytest.raises(httpx2.HTTPStatusError):
        raise_for_status(response=response)

    assert response_body_marker not in caplog.text
    assert "Response body omitted from logs" in caplog.text


@pytest.mark.parametrize("required_params_type", ["Default", "WithoutUtsk"])
def test_appletv_request_params_follow_the_route_advertised_parameter_class(
    required_params_type: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scraper = object.__new__(AppleTVScraper)
    scraper._storefronts_request_params_cache = {}  # noqa: SLF001
    configuration_data = {
        "applicationProps": {
            "requiredParamsMap": {
                "Default": {"caller": "web", "utsk": "public-token", "v": "100"},
                "WithoutUtsk": {"caller": "web", "v": "100"},
            },
            "routes": {
                "movieDetail": {
                    "path": "/uts/v3/movies/{movieId}",
                    "requiredParamsType": required_params_type,
                },
            },
            "storefront": {
                "defaultLocale": "en_US",
                "localesSupported": ["en_US"],
            },
        },
    }

    async def fake_get_configuration_data(storefront_id: str) -> dict:  # noqa: ARG001
        return configuration_data

    monkeypatch.setattr(scraper, "_get_configuration_data", fake_get_configuration_data)
    request_params = asyncio.run(
        scraper._fetch_request_params(  # noqa: SLF001
            storefront_id="143441",
            route_path="/uts/v3/movies/{movieId}",
        ),
    )

    assert ("utsk" in request_params) is (required_params_type == "Default")
    assert request_params["sf"] == "143441"
    assert request_params["locale"] == "en-US"


def test_appletv_api_failure_does_not_expose_public_utsk(monkeypatch: pytest.MonkeyPatch) -> None:
    public_utsk = "public-token-that-must-not-be-logged"

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(500, request=request)

    scraper = object.__new__(AppleTVScraper)
    scraper._client = httpx2.AsyncClient(  # noqa: SLF001
        transport=httpx2.MockTransport(handler),
        headers={"User-Agent": "test"},
    )

    async def fake_fetch_request_params(**kwargs: Any) -> dict[str, str]:  # noqa: ARG001
        return {"utsk": public_utsk}

    monkeypatch.setattr(scraper, "_fetch_request_params", fake_fetch_request_params)

    try:
        with pytest.raises(ScraperError, match=r"Apple TV API request failed \(HTTP 500\)") as exc_info:
            asyncio.run(scraper._fetch_api_data(storefront_id="143441", endpoint="/movies/test"))  # noqa: SLF001
    finally:
        close_scraper(scraper=scraper)

    assert public_utsk not in str(exc_info.value)


def test_appletv_transport_failure_does_not_expose_public_utsk(monkeypatch: pytest.MonkeyPatch) -> None:
    public_utsk = "public-token-that-must-not-be-logged"

    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError(f"Failed request: {request.url}", request=request)

    scraper = object.__new__(AppleTVScraper)
    scraper._client = httpx2.AsyncClient(  # noqa: SLF001
        transport=httpx2.MockTransport(handler),
        headers={"User-Agent": "test"},
    )

    async def fake_fetch_request_params(**kwargs: Any) -> dict[str, str]:  # noqa: ARG001
        return {"utsk": public_utsk}

    monkeypatch.setattr(scraper, "_fetch_request_params", fake_fetch_request_params)

    try:
        with pytest.raises(ScraperError, match=r"Apple TV API request failed\.") as exc_info:
            asyncio.run(scraper._fetch_api_data(storefront_id="143441", endpoint="/movies/test"))  # noqa: SLF001
    finally:
        close_scraper(scraper=scraper)

    assert public_utsk not in str(exc_info.value)


def test_download_media_item_reports_no_matching_subtitles_as_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    movie = Movie(name="Test Movie", release_date=2026, playlist="https://example.com/master.m3u8")

    async def fake_download_subtitles(**kwargs: Any) -> SubtitlesDownloadResults:
        return SubtitlesDownloadResults(
            media_data=kwargs["media_data"],
            successful_subtitles=[],
            failed_subtitles=[],
            is_zip=False,
        )

    monkeypatch.setattr("isubrip.commands.download.download_subtitles", fake_download_subtitles)

    assert asyncio.run(
        download_media_item(
            scraper=object.__new__(PlaylistTestScraper),
            media_item=movie,
            download_path=tmp_path,
        ),
    ) is False


def test_download_media_item_reports_playlist_failure_alongside_future_rental_date(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    movie = Movie(
        name="Test Movie",
        release_date=2026,
        preorder_availability_date=dt.datetime(2027, 1, 1),
        playlist="https://example.com/master.m3u8",
    )

    async def fake_download_subtitles(**kwargs: Any) -> SubtitlesDownloadResults:  # noqa: ARG001
        raise PlaylistLoadError("Actionable playlist failure.")

    monkeypatch.setattr("isubrip.commands.download.download_subtitles", fake_download_subtitles)

    with caplog.at_level(logging.INFO, logger=PACKAGE_NAME):
        result = asyncio.run(
            download_media_item(
                scraper=object.__new__(PlaylistTestScraper),
                media_item=movie,
                download_path=tmp_path,
            ),
        )

    assert result is False
    assert "available to rent on" in caplog.text
    assert "currently unavailable" not in caplog.text
    assert "Actionable playlist failure" in caplog.text


def test_appletv_movie_extraction_adds_dsid_to_every_playlist() -> None:
    scraper = object.__new__(AppleTVScraper)
    scraper.config = AppleTVScraper.ScraperConfig(dsid="1234567890")
    playable_data = {
        "canonicalId": "umc.cmc.test",
        "isEntitledToPlay": False,
        "canonicalMetadata": {
            "movieTitle": "Test Movie",
            "releaseDate": 1_609_459_200_000,
        },
        "itunesMediaApiData": {
            "id": "123",
            "offers": [
                {
                    "hlsUrl": (
                        "https://play.itunes.apple.com/WebObjects/MZPlay.woa/hls/playlist.m3u8"
                        "?cc=US&a=1&dsid=old&id=2"
                    ),
                },
                {
                    "hlsUrl": (
                        "https://play.itunes.apple.com/WebObjects/MZPlay.woa/hls/playlist.m3u8"
                        "?cc=US&a=3&id=4"
                    ),
                },
            ],
        },
    }

    movie = scraper._extract_itunes_movie_data(playable_data=playable_data)  # noqa: SLF001

    assert movie.playlist == [
        (
            "https://play.itunes.apple.com/WebObjects/MZPlay.woa/hls/playlist.m3u8"
            "?cc=US&a=1&id=2&dsid=1234567890"
        ),
        (
            "https://play.itunes.apple.com/WebObjects/MZPlay.woa/hls/playlist.m3u8"
            "?cc=US&a=3&id=4&dsid=1234567890"
        ),
    ]


def test_appletv_movie_extraction_preserves_free_playlist_without_runtime_dsid() -> None:
    scraper = object.__new__(AppleTVScraper)
    scraper.config = None
    playable_data = {
        "canonicalId": "umc.cmc.test",
        "isEntitledToPlay": True,
        "entitlementReason": "Free",
        "canonicalMetadata": {
            "movieTitle": "Test Movie",
            "releaseDate": 1_609_459_200_000,
        },
        "itunesMediaApiData": {
            "id": "123",
            "offers": [{"hlsUrl": "https://play.itunes.apple.com/playlist.m3u8?cc=US"}],
        },
    }

    movie = scraper._extract_itunes_movie_data(playable_data=playable_data)  # noqa: SLF001
    assert movie.playlist == ["https://play.itunes.apple.com/playlist.m3u8?cc=US"]


def test_appletv_movie_extraction_preserves_playlist_when_entitlement_is_unknown() -> None:
    scraper = object.__new__(AppleTVScraper)
    scraper.config = None
    playable_data = {
        "canonicalId": "umc.cmc.test",
        "canonicalMetadata": {
            "movieTitle": "Test Movie",
            "releaseDate": 1_609_459_200_000,
        },
        "itunesMediaApiData": {
            "id": "123",
            "offers": [{"hlsUrl": "https://play.itunes.apple.com/playlist.m3u8?cc=US"}],
        },
    }

    movie = scraper._extract_itunes_movie_data(playable_data=playable_data)  # noqa: SLF001

    assert movie.playlist == ["https://play.itunes.apple.com/playlist.m3u8?cc=US"]


def test_appletv_movie_extraction_requires_dsid_before_loading_paid_playlist() -> None:
    scraper = object.__new__(AppleTVScraper)
    scraper.config = None
    playable_data = {
        "canonicalId": "umc.cmc.test",
        "isEntitledToPlay": False,
        "entitlementReason": "Unknown",
        "canonicalMetadata": {
            "movieTitle": "Test Movie",
            "releaseDate": 1_609_459_200_000,
        },
        "itunesMediaApiData": {
            "id": "123",
            "offers": [
                {
                    "hlsUrl": (
                        "https://play-edge.itunes.apple.com/WebObjects/MZPlayLocal.woa/hls/playlist.m3u8"
                        "?cc=US&a=1"
                    ),
                },
            ],
        },
    }

    with pytest.raises(ScraperError, match="DSID authentication is required") as exc_info:
        scraper._extract_itunes_movie_data(playable_data=playable_data)  # noqa: SLF001

    assert "--dsid" in str(exc_info.value)
    assert "command-line option" in str(exc_info.value)
    assert "ISUBRIP_DSID" in str(exc_info.value)
    assert "environment variable" in str(exc_info.value)
    assert "scrapers.appletv.dsid" in str(exc_info.value)


def test_itunes_load_playlist_explains_missing_dsid_on_apple_404() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(404, request=request)

    scraper = make_itunes_scraper(handler=httpx2.MockTransport(handler))

    try:
        with pytest.raises(PlaylistLoadError, match="no DSID was included") as exc_info:
            asyncio.run(
                scraper.load_playlist(
                    url="https://play.itunes.apple.com/WebObjects/MZPlay.woa/hls/playlist.m3u8?cc=US&a=1",
                ),
            )
    finally:
        close_scraper(scraper=scraper)

    assert "active rental" in str(exc_info.value)


def test_itunes_load_playlist_explains_missing_dsid_on_play_edge_404() -> None:
    requests: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(str(request.url))
        return httpx2.Response(404, request=request)

    scraper = make_itunes_scraper(handler=httpx2.MockTransport(handler))
    playlist_url = (
        "https://play-edge.itunes.apple.com/WebObjects/MZPlayLocal.woa/hls/playlist.m3u8?cc=US&a=1"
    )

    try:
        with pytest.raises(PlaylistLoadError, match="no DSID was included"):
            asyncio.run(scraper.load_playlist(url=playlist_url))
    finally:
        close_scraper(scraper=scraper)

    assert requests == [playlist_url]


def test_itunes_load_playlist_explains_entitlement_failure_when_dsid_is_present() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(404, request=request)

    scraper = make_itunes_scraper(handler=httpx2.MockTransport(handler))

    try:
        with pytest.raises(PlaylistLoadError, match="Apple denied access") as exc_info:
            asyncio.run(
                scraper.load_playlist(
                    url=(
                        "https://play.itunes.apple.com/WebObjects/MZPlay.woa/hls/playlist.m3u8"
                        "?cc=US&a=1&dsid=1234567890"
                    ),
                ),
            )
    finally:
        close_scraper(scraper=scraper)

    assert "1234567890" not in str(exc_info.value)
    assert "configured DSID" in str(exc_info.value)


def test_itunes_load_playlist_recognizes_case_insensitive_dsid_key() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(404, request=request)

    scraper = make_itunes_scraper(handler=httpx2.MockTransport(handler))

    try:
        with pytest.raises(PlaylistLoadError, match="configured DSID") as exc_info:
            asyncio.run(
                scraper.load_playlist(
                    url=(
                        "https://play.itunes.apple.com/WebObjects/MZPlay.woa/hls/playlist.m3u8"
                        "?cc=US&DSID=1234567890"
                    ),
                ),
            )
    finally:
        close_scraper(scraper=scraper)

    assert "no DSID was included" not in str(exc_info.value)
