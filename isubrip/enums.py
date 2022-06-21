from enum import Enum


class DataSource(Enum):
    """Subtitles source."""
    ITUNES = 1
    APPLETV = 2


class SubtitlesType(Enum):
    """Subtitles type (Normal / CC / Forced)."""
    NORMAL = 1
    CC = 2
    FORCED = 3


class SubtitlesFormat(Enum):
    """Subtitles format (srt / vtt)."""
    SRT = 1
    VTT = 2


class ArchiveFormat(Enum):
    """Archive Format (zip / tar / tar.gz)."""
    ZIP = 1
    TAR = 2
    TAR_GZ = 3
