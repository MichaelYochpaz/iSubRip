from enum import Enum

class SubtitlesType(Enum):
    """Subtitles type (Normal / CC / Forced)."""
    NORMAL = 1
    CC = 2
    FORCED = 3


class SubtitlesFormat(Enum):        
    """Subtitles format (srt / vtt)."""
    SRT = 1
    VTT = 2