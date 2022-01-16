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