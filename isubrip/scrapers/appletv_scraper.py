from __future__ import annotations

from isubrip.data_structures import MovieData
from isubrip.scrapers.itunes_scraper import iTunesScraper
from isubrip.scrapers.scraper import M3U8Scraper, MediaSourceData, MovieScraper, ScraperException, \
    SeriesScraper, ScraperFactory
from isubrip.subtitle_formats.webvtt import WebVTTSubtitles


class AppleTVPlusScraper(M3U8Scraper, MovieScraper, SeriesScraper):
    """
    An Apple TV+ movie data scraper.
    Also works for Apple TV items that include iTunes links (by redirecting to the iTunes scraper).
    """
    url_regex = r"(https?://tv\.apple\.com/([a-z]{2})/(movie|show)/(?:[\w\-%]+/)?(umc\.cmc\.[a-z\d]{24,25}))(?:\?.*)?"
    service_data = MediaSourceData(id="appletvplus", name="Apple TV+", abbreviation="ATVP")
    subtitles_class = WebVTTSubtitles
    is_movie_scraper = True
    is_series_scraper = True
    uses_scrapers = [iTunesScraper]

    _api_url = "https://tv.apple.com/api/uts/v3/movies/"
    _api_request_params = {
        "utscf": "OjAAAAAAAAA~",
        "utsk": "6e3013c6d6fae3c2::::::235656c069bb0efb",
        "caller": "web",
        "v": "58",
        "pfm": "web",
        "locale": "en-US"
    }
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

    def __init__(self, config_data: dict | None = None):
        super().__init__(config_data=config_data)
        self.itunes_scraper = ScraperFactory().get_scraper_instance_by_scraper(
            scraper_class=iTunesScraper,
            scrapers_config_data=config_data,
        )

    def fetch_api_data(self, url: str) -> dict:
        """
        Send a request to AppleTV's API and return the JSON response.

        Args:
            url: The URL to send the request to.

        Returns:
            dict: The JSON response.

        Raises:
            HttpError: If an HTTP error response is received.
        """
        regex_match = self.match_url(url, raise_error=True)

        # Add storefront ID to params
        request_params = self._api_request_params.copy()

        if regex_match.group(2).upper() in self._storefronts_mapping:
            request_params["sf"] = self._storefronts_mapping[regex_match.group(2).upper()]

        else:
            raise ScraperException(f"ID mapping for storefront '{regex_match.group(2).upper()}' could not be found.")

        response = self._session.get(self._api_url + regex_match.group(4), params=request_params)
        response.raise_for_status()
        response_json = response.json()

        return response_json.get("data", {})

    def get_data(self, url: str) -> MovieData | list[MovieData] | None:
        json_data = self.fetch_api_data(url)
        itunes_channel: str | None = None
        appletvplus_channel: str | None = None

        for channel in json_data["channels"].values():
            if channel.get("isAppleTvPlus", False):
                appletvplus_channel = channel["id"]

            elif channel.get("isItunes", False):
                itunes_channel = channel["id"]
        
        if appletvplus_channel:
            media_type = json_data.get("content", {}).get("type")

            if media_type in ("Movie", "Show"):
                for playable in json_data["playables"].values():
                    if playable.get("channelId") == appletvplus_channel:
                        raise NotImplementedError("AppleTV+ content scraping is not currently supported.")

            else:
                raise ScraperException(f"Unsupported media type: '{media_type}'.")

        elif itunes_channel:
            itunes_playables = []

            for playable in json_data["playables"].values():
                if playable.get("channelId", '') == itunes_channel:
                    itunes_playables.append(playable)

            return self._get_data_itunes(playables_data=itunes_playables)

        return None

    def _get_data_itunes(self, playables_data: list[dict]) -> MovieData | list[MovieData]:
        results = []

        for playable_data in playables_data:
            itunes_url = playable_data["punchoutUrls"]["open"].replace("itmss://", "https://")
            results.append(self.itunes_scraper.get_data(itunes_url))

        if len(results) == 1:
            return results[0]

        return results
