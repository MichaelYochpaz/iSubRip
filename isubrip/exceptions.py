class ScrapeError(Exception):
    """An issue while scraping the page."""
    pass

class InvalidURL(ScrapeError):
    """An invalid URL has been used."""
    pass

class PageLoadError(ScrapeError):
    """The Page did not load properly."""
    pass

class PlaylistDownloadError(ScrapeError):
    """The playlist could not be downloaded."""
    pass



class FFmpegNotFound(Exception):
    """FFmpeg could not be found."""
    pass



class ConfigError(Exception):
    """An issue with a config file."""
    pass

class DefaultConfigNotFound(ConfigError):
    """Default config file could not be found."""
    pass

class UserConfigNotFound(ConfigError):
    """User config file could not be found."""
    pass

class InvalidConfigValue(ConfigError):
    """An invalid value has been used."""
    pass