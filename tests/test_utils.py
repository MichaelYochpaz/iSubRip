import datetime as dt

import pytest

from isubrip.data_structures import Episode, Movie, Season, Series
from isubrip.utils import (
    format_media_description,
    sanitize_path_segment,
    slugify_title,
)


class TestSlugifyTitle:
    @pytest.mark.parametrize(
        ("input_title", "separator", "expected_output"),
        [
            ("The Lord of the Rings: The Fellowship of the Ring", ".",
             "The.Lord.of.the.Rings.The.Fellowship.of.the.Ring"),
            ("The Lord of the Rings: The Fellowship of the Ring", " ",
             "The Lord of the Rings The Fellowship of the Ring"),

            ("Once Upon a Time... in Hollywood", ".", "Once.Upon.a.Time.in.Hollywood"),
            ("Once Upon a Time... in Hollywood", " ", "Once Upon a Time... in Hollywood"),

            ("Dr. Strangelove or: How I Learned to Stop Worrying and Love the Bomb?", ".",
             "Dr.Strangelove.or.How.I.Learned.to.Stop.Worrying.and.Love.the.Bomb"),
            ("Dr. Strangelove or: How I Learned to Stop Worrying and Love the Bomb?", " ",
             "Dr. Strangelove or How I Learned to Stop Worrying and Love the Bomb"),

            ("Mission: Impossible - The Final Reckoning", ".", "Mission.Impossible.The.Final.Reckoning"),
            ("Mission: Impossible - The Final Reckoning", " ", "Mission Impossible - The Final Reckoning"),

            ("Deadpool & Wolverine", ".", "Deadpool.&.Wolverine"),
            ("Deadpool & Wolverine", " ", "Deadpool & Wolverine"),

            ("50/50", ".", "50.50"),
            ("50/50", " ", "50 50"),
            ("50 / 50", ".", "50.50"),
            ("50 / 50", " ", "50 50"),

            ("V/H/S", ".", "V.H.S"),
            ("V/H/S", " ", "V H S"),

            ("What If...?", ".", "What.If."),
            ("What If...?", " ", "What If..."),
        ],
    )
    def test_slugify_title(self, input_title: str, separator: str, expected_output: str) -> None:
        assert slugify_title(title=input_title, separator=separator) == expected_output


class TestSanitizePath:
    @pytest.mark.parametrize(
        ("name", "expected_name"),
        [
            ("A/B/C", "ABC"),
            ("A<B>C", "ABC"),
            ('A"B"C', "ABC"),
            ("A:B:C", "ABC"),
            ("A|B|C", "ABC"),
            ("A?B?C", "ABC"),
            ("A*B*C", "ABC"),
        ],
    )
    def test_sanitize_common_illegal_chars(self, name: str, expected_name: str) -> None:
        assert sanitize_path_segment(name) == expected_name

    @pytest.mark.parametrize(
        ("name", "expected_unix", "expected_windows"),
        [
            ("name.", "name.", "name"),
            ("name..", "name..", "name"),
            ("name ", "name ", "name"),
            (" name", " name", " name"),
            ("name. ", "name. ", "name"),
            ("COM1", "COM1", "_COM1"),
            ("Con.Air", "Con.Air", "_Con.Air"),
            ("aux.txt", "aux.txt", "_aux.txt"),
            ("", "_", "_"),
        ],
    )
    def test_sanitize_platform_specific(self, name: str, expected_unix: str, expected_windows: str) -> None:
        # Test Unix-like behavior
        assert sanitize_path_segment(name, platform='linux') == expected_unix

        # Test Windows behavior
        assert sanitize_path_segment(name, platform='win32') == expected_windows


class TestFormatMediaDescription:
    def test_movie_with_datetime_and_id(self) -> None:
        movie = Movie(name="Inception", release_date=dt.datetime(2010, 7, 16), id="ID123")
        assert format_media_description(media_data=movie) == "Inception [2010] (ID: ID123)"

    def test_series_with_year_no_id(self) -> None:
        series = Series(series_name="The Office", series_release_date=2005)
        assert format_media_description(media_data=series) == "The Office [2005]"

    def test_season_full_with_name_and_id(self) -> None:
        season = Season(series_name="True Detective", series_release_date=2024,
                        season_number=4, season_name="Night Country", id="ID321")
        assert format_media_description(media_data=season) == "True Detective - Season 4 - Night Country (ID: ID321)"

    def test_season_full_with_name_and_id_and_extra_spaces(self) -> None:
        season = Season(series_name=" True Detective ", series_release_date=2024,
                        season_number=4, season_name=" Night Country  ", id="ID321")
        assert format_media_description(media_data=season) == "True Detective - Season 4 - Night Country (ID: ID321)"

    def test_season_shortened_no_id(self) -> None:
        season = Season(series_name="Stranger Things", season_number=3)
        assert format_media_description(media_data=season, shortened=True) == "Season 3"

    def test_episode_full_with_name_and_id(self) -> None:
        ep = Episode(series_name="Breaking Bad",
                     season_number=5, episode_number=14, episode_name="Ozymandias", id="ID111")
        assert format_media_description(media_data=ep) == "Breaking Bad - S05E14 - Ozymandias (ID: ID111)"

    def test_episode_shortened_no_id(self) -> None:
        ep = Episode(series_name="Breaking Bad",
                     season_number=5, episode_number=14, episode_name="Ozymandias", id="ID111")
        assert format_media_description(media_data=ep, shortened=True) == "S05E14 - Ozymandias (ID: ID111)"
