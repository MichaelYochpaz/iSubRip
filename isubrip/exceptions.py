# --------------- Scraping --------------- #

class ScrapeError(Exception):
    """An issue while scraping the page."""
    pass


class InvalidURL(ScrapeError):
    """An invalid URL has been used."""
    pass


class PageLoadError(ScrapeError):
    """The Page did not load properly."""
    pass


# --------------- Config --------------- #

class ConfigError(Exception):
    """An issue with a config file."""
    pass


class DefaultConfigNotFound(ConfigError):
    """Default config file could not be found."""
    pass


class ConfigValueMissing(ConfigError):
    """A required config value is missing."""
    pass


class InvalidConfigValue(ConfigError):
    """An invalid value has been used."""
    pass
