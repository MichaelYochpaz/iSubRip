from __future__ import annotations

import datetime as dt
from enum import Enum
import fnmatch
import re
from typing import Iterator

from requests.exceptions import HTTPError

from isubrip.data_structures import Episode, MediaData, Movie, ScrapedMediaResponse, Season, Series, SubtitlesData
from isubrip.logger import logger
from isubrip.scrapers.scraper import HLSScraper, ScraperError
from isubrip.subtitle_formats.webvtt import WebVTTSubtitles
from isubrip.utils import convert_epoch_to_datetime, parse_url_params, raise_for_status


class AppleTVScraper(HLSScraper):
    """An Apple TV scraper."""
    id = "appletv"
    name = "Apple TV"
    abbreviation = "ATV"
    url_regex = re.compile(r"(?P<base_url>https?://tv\.apple\.com/(?:(?P<country_code>[a-z]{2})/)?(?P<media_type>movie|episode|season|show)/(?:(?P<media_name>[\w\-%]+)/)?(?P<media_id>umc\.cmc\.[a-z\d]{23,25}))(?:\?(?P<url_params>.*))?", flags=re.IGNORECASE)  # noqa: E501
    subtitles_class = WebVTTSubtitles
    is_movie_scraper = True
    is_series_scraper = True
    uses_scrapers = ["itunes"]

    _api_base_url = "https://tv.apple.com/api/uts/v3"
    _api_base_params = {
        "utscf": "OjAAAAAAAAA~",
        "caller": "js",
        "v": "66",
        "pfm": "web",
    }
    _default_storefront = "US"  # Has to be uppercase
    _storefronts_mapping = {
        "AF": "143610", "AO": "143564", "AI": "143538", "AL": "143575", "AD": "143611", "AE": "143481", "AR": "143505",
        "AM": "143524", "AG": "143540", "AU": "143460", "AT": "143445", "AZ": "143568", "BE": "143446", "BJ": "143576",
        "BF": "143578", "BD": "143490", "BG": "143526", "BH": "143559", "BS": "143539", "BA": "143612", "BY": "143565",
        "BZ": "143555", "BM": "143542", "BO": "143556", "BR": "143503", "BB": "143541", "BN": "143560", "BT": "143577",
        "BW": "143525", "CF": "143623", "CA": "143455", "CH": "143459", "CL": "143483", "CN": "143465", "CI": "143527",
        "CM": "143574", "CD": "143613", "CG": "143582", "CO": "143501", "CV": "143580", "CR": "143495", "KY": "143544",
        "CY": "143557", "CZ": "143489", "DE": "143443", "DM": "143545", "DK": "143458", "DO": "143508", "DZ": "143563",
        "EC": "143509", "EG": "143516", "ES": "143454", "EE": "143518", "ET": "143569", "FI": "143447", "FJ": "143583",
        "FR": "143442", "FM": "143591", "GA": "143614", "GB": "143444", "GE": "143615", "GH": "143573", "GN": "143616",
        "GM": "143584", "GW": "143585", "GR": "143448", "GD": "143546", "GT": "143504", "GY": "143553", "HK": "143463",
        "HN": "143510", "HR": "143494", "HU": "143482", "ID": "143476", "IN": "143467", "IE": "143449", "IQ": "143617",
        "IS": "143558", "IL": "143491", "IT": "143450", "JM": "143511", "JO": "143528", "JP": "143462", "KZ": "143517",
        "KE": "143529", "KG": "143586", "KH": "143579", "KN": "143548", "KR": "143466", "KW": "143493", "LA": "143587",
        "LB": "143497", "LR": "143588", "LY": "143567", "LC": "143549", "LI": "143522", "LK": "143486", "LT": "143520",
        "LU": "143451", "LV": "143519", "MO": "143515", "MA": "143620", "MC": "143618", "MD": "143523", "MG": "143531",
        "MV": "143488", "MX": "143468", "MK": "143530", "ML": "143532", "MT": "143521", "MM": "143570", "ME": "143619",
        "MN": "143592", "MZ": "143593", "MR": "143590", "MS": "143547", "MU": "143533", "MW": "143589", "MY": "143473",
        "NA": "143594", "NE": "143534", "NG": "143561", "NI": "143512", "NL": "143452", "NO": "143457", "NP": "143484",
        "NR": "143606", "NZ": "143461", "OM": "143562", "PK": "143477", "PA": "143485", "PE": "143507", "PH": "143474",
        "PW": "143595", "PG": "143597", "PL": "143478", "PT": "143453", "PY": "143513", "PS": "143596", "QA": "143498",
        "RO": "143487", "RU": "143469", "RW": "143621", "SA": "143479", "SN": "143535", "SG": "143464", "SB": "143601",
        "SL": "143600", "SV": "143506", "RS": "143500", "ST": "143598", "SR": "143554", "SK": "143496", "SI": "143499",
        "SE": "143456", "SZ": "143602", "SC": "143599", "TC": "143552", "TD": "143581", "TH": "143475", "TJ": "143603",
        "TM": "143604", "TO": "143608", "TT": "143551", "TN": "143536", "TR": "143480", "TW": "143470", "TZ": "143572",
        "UG": "143537", "UA": "143492", "UY": "143514", "US": "143441", "UZ": "143566", "VC": "143550", "VE": "143502",
        "VG": "143543", "VN": "143471", "VU": "143609", "WS": "143607", "XK": "143624", "YE": "143571", "ZA": "143472",
        "ZM": "143622", "ZW": "143605",
    }

    class Channel(Enum):
        """
        An Enum representing AppleTV channels.
        Value represents the channel ID as used by the API.
        """
        APPLE_TV_PLUS = "tvs.sbd.4000"
        DISNEY_PLUS = "tvs.sbd.1000216"
        ITUNES = "tvs.sbd.9001"
        HULU = "tvs.sbd.10000"
        MAX = "tvs.sbd.9050"
        NETFLIX = "tvs.sbd.9000"
        PRIME_VIDEO = "tvs.sbd.12962"
        STARZ = "tvs.sbd.1000308"

    def __init__(self, user_agent: str | None = None, config_data: dict | None = None):
        super().__init__(user_agent=user_agent, config_data=config_data)
        self._config_data = config_data
        self._storefront_locale_mapping_cache: dict[str, str] = {}

    def _decide_locale(self, preferred_locales: str | list[str], default_locale: str, locales: list[str]) -> str:
        """
        Decide which locale to use.

        Args:
            preferred_locales (str | list[str]): The preferred locales to use.
            default_locale (str): The default locale to use if there is no match.
            locales (list[str]): The locales to search in.

        Returns:
            str: The locale to use.
        """
        if isinstance(preferred_locales, str):
            preferred_locales = [preferred_locales]

        for locale in preferred_locales:
            if locale in locales:
                return locale.replace("_", "-")

        if result := fnmatch.filter(locales, "en_*"):
            return result[0].replace("_", "-")

        return default_locale

    def _fetch_api_data(self, storefront_id: str, endpoint: str, additional_params: dict | None = None) -> dict:
        """
        Send a request to AppleTV's API and return the JSON response.

        Args:
            endpoint (str): The endpoint to send the request to.
            additional_params (dict[str, str]): Additional parameters to send with the request.

        Returns:
            dict: The JSON response.

        Raises:
            HttpError: If an HTTP error response is received.
        """
        logger.debug(f"Preparing to fetch '{endpoint}' using storefront '{storefront_id}'.")

        if storefront_cached_local := self._storefront_locale_mapping_cache.get(storefront_id):
            logger.debug(f"Using cached locale for storefront '{storefront_id}': '{storefront_cached_local}'.")
            locale = storefront_cached_local

        else:
            storefront_data = \
                self._get_configuration_data(storefront_id=storefront_id)["applicationProps"]["storefront"]

            default_locale = storefront_data["defaultLocale"]
            available_locales = storefront_data["localesSupported"]

            logger.debug(f"Available locales for storefront '{storefront_id}': {available_locales}'. "
                         f"Storefront's default locale: '{default_locale}'.")

            locale = self._decide_locale(
                preferred_locales=["en_US", "en_GB"],
                default_locale=default_locale,
                locales=available_locales,
            )

            logger.debug(f"Selected locale for storefront '{storefront_id}': '{locale}'")

            self._storefront_locale_mapping_cache[storefront_id] = locale

        request_params = self._generate_api_request_params(storefront_id=storefront_id, locale=locale)

        if additional_params:
            request_params.update(additional_params)

        response = self._session.get(url=f"{self._api_base_url}{endpoint}", params=request_params)

        try:
            raise_for_status(response)

        except HTTPError as e:
            if response.status_code == 404:
                raise ScraperError(
                    "Media not found. This could indicate that the provided URL is invalid.",
                ) from e

            raise

        response_json: dict = response.json()
        response_data: dict = response_json.get("data", {})

        return response_data

    def _generate_api_request_params(self, storefront_id: str,
                                     locale: str | None = None, utsk: str | None = None) -> dict:
        """
        Generate request params for the AppleTV's API.

        Args:
            storefront_id (str): ID of the storefront to use.
            locale (str | None, optional): ID of the locale to use. Defaults to None.
            utsk (str | None, optional): utsk data. Defaults to None.

        Returns:
            dict: The request params, generated from the given arguments.
        """
        params = self._api_base_params.copy()
        params["sf"] = storefront_id

        if utsk:
            params["utsk"] = utsk

        if locale:
            params["locale"] = locale

        return params

    def _get_configuration_data(self, storefront_id: str) -> dict:
        """
        Get configuration data for the given storefront ID.

        Args:
            storefront_id (str): The ID of the storefront to get the configuration data for.

        Returns:
            dict: The configuration data.
        """
        logger.debug(f"Fetching configuration data for storefront '{storefront_id}'...")
        url = f"{self._api_base_url}/configurations"
        params = self._generate_api_request_params(storefront_id=storefront_id)
        response = self._session.get(url=url, params=params)
        raise_for_status(response)
        logger.debug("Configuration data fetched successfully.")

        response_data: dict = response.json()["data"]
        return response_data

    def _map_playables_by_channel(self, playables: list[dict]) -> dict[str, dict]:
        """
        Map playables by channel name.

        Args:
            playables (list[dict]): Playables data to map.

        Returns:
            dict: The mapped playables (in a `channel_name (str): [playables]` format).
        """
        mapped_playables: dict = {}

        for playable in playables:
            if channel_id := playable.get("channelId"):
                mapped_playables.setdefault(channel_id, []).append(playable)

        return mapped_playables

    def get_movie_data(self, storefront_id: str, movie_id: str) -> ScrapedMediaResponse[Movie]:
        data = self._fetch_api_data(
            storefront_id=storefront_id,
            endpoint=f"/movies/{movie_id}",
        )

        mapped_playables = self._map_playables_by_channel(playables=data["playables"].values())
        logger.debug(f"Available channels for movie '{movie_id}': "
                     f"{' '.join(list(mapped_playables.keys()))}")

        if self.Channel.ITUNES.value not in mapped_playables:
            if self.Channel.APPLE_TV_PLUS.value in mapped_playables:
                raise ScraperError("Scraping AppleTV+ content is not currently supported.")

            raise ScraperError("No iTunes playables could be found.")

        return_data = []

        for playable_data in mapped_playables[self.Channel.ITUNES.value]:
            return_data.append(self._extract_itunes_movie_data(playable_data))

        if len(return_data) > 1:
            logger.debug(f"{len(return_data)} iTunes playables were found for movie '{movie_id}'.")

        else:
            return_data = return_data[0]

        return ScrapedMediaResponse(
            media_data=return_data,
            metadata_scraper=self.id,
            playlist_scraper="itunes",
            original_data=data,
        )

    def _extract_itunes_movie_data(self, playable_data: dict) -> Movie:
        """
        Extract movie data from an AppleTV's API iTunes playable data.

        Args:
            playable_data (dict): The playable data from the AppleTV API.

        Returns:
            Movie: A Movie object.
        """
        itunes_movie_id = playable_data["itunesMediaApiData"]["id"]
        appletv_movie_id = playable_data["canonicalId"]
        movie_title = playable_data["canonicalMetadata"]["movieTitle"]
        movie_release_date = convert_epoch_to_datetime(playable_data["canonicalMetadata"]["releaseDate"] // 1000)

        movie_playlists = []
        movie_duration = None

        if offers := playable_data["itunesMediaApiData"].get("offers"):
            for offer in offers:
                if (playlist := offer.get("hlsUrl")) and offer["hlsUrl"] not in movie_playlists:
                    movie_playlists.append(playlist)

            if movie_duration_int := offers[0].get("durationInMilliseconds"):
                movie_duration = dt.timedelta(milliseconds=movie_duration_int)

        if movie_expected_release_date := playable_data["itunesMediaApiData"].get("futureRentalAvailabilityDate"):
            movie_expected_release_date = dt.datetime.strptime(movie_expected_release_date, "%Y-%m-%d")

        return Movie(
            id=itunes_movie_id,
            referer_id=appletv_movie_id,
            name=movie_title,
            release_date=movie_release_date,
            duration=movie_duration,
            preorder_availability_date=movie_expected_release_date,
            playlist=movie_playlists if movie_playlists else None,
        )

    def get_episode_data(self, storefront_id: str, episode_id: str) -> ScrapedMediaResponse[Episode]:
        raise NotImplementedError("Series scraping is not currently supported.")

    def get_season_data(self, storefront_id: str, season_id: str, show_id: str) -> ScrapedMediaResponse[Season]:
        raise NotImplementedError("Series scraping is not currently supported.")

    def get_show_data(self, storefront_id: str, show_id: str) -> ScrapedMediaResponse[Series]:
        raise NotImplementedError("Series scraping is not currently supported.")

    def get_data(self, url: str) -> ScrapedMediaResponse[MediaData]:
        regex_match = self.match_url(url=url, raise_error=True)
        url_data = regex_match.groupdict()

        media_type = url_data["media_type"]

        if storefront_code := url_data.get("country_code"):
            storefront_code = storefront_code.upper()

        else:
            storefront_code = self._default_storefront

        media_id = url_data["media_id"]

        if storefront_code not in self._storefronts_mapping:
            raise ScraperError(f"ID mapping for storefront '{storefront_code}' could not be found.")

        storefront_id = self._storefronts_mapping[storefront_code]

        if media_type == "movie":
            return self.get_movie_data(storefront_id=storefront_id, movie_id=media_id)

        if media_type == "episode":
            return self.get_episode_data(storefront_id=storefront_id, episode_id=media_id)

        if media_type == "season":
            if (url_params := url_data.get("url_params")) and (show_id := parse_url_params(url_params).get("showId")):
                return self.get_season_data(storefront_id=storefront_id, season_id=media_id, show_id=show_id)

            raise ScraperError("Invalid AppleTV URL: Missing 'showId' parameter.")

        if media_type == "show":
            return self.get_show_data(storefront_id=storefront_id, show_id=media_id)

        raise ScraperError(f"Invalid media type '{media_type}'.")

    def get_subtitles(self, main_playlist: str | list[str], language_filter: list[str] | str | None = None,
                      subrip_conversion: bool = False) -> Iterator[SubtitlesData]:
        raise NotImplementedError("Subtitles scraping for AppleTV+ is not currently supported.")
