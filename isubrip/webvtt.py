from abc import ABC, abstractmethod
from datetime import time

from isubrip.constants import RTL_CHAR, RTL_CONTROL_CHARS
from isubrip.enums import SubtitlesFormat


# Documentation:
# https://www.w3.org/TR/webvtt1/#cues
# https://developer.mozilla.org/en-US/docs/Web/API/WebVTT_API#webvtt_cues


class WebVTTBlock(ABC):
    """
    Abstract base class for WEBVTT cue blocks.
    """
    @abstractmethod
    def __str__(self):
        pass

    @abstractmethod
    def __eq__(self, other):
        pass


class Caption(WebVTTBlock):
    """An object represnting a WebVTT caption block."""
    header = None

    def __init__(self, start_time: time, end_time: time, payload, settings: str = "", identifier: str = ""):
        """
        Create a new object representing a caption block.

        Args:
            start_time (time): Cue start time.
            end_time (time): Cue end time.
            settings (str): Cue settings.
            payload (str): Cue payload.
        """
        self.identifier = identifier
        self.start_time = start_time
        self.end_time = end_time
        self.settings = settings
        self.payload = payload

    def __eq__(self, other):
        return isinstance(other, type(self)) and \
            self.start_time == other.start_time and self.end_time == other.end_time and self.payload == other.payload

    def __str__(self):
        return self.to_string(SubtitlesFormat.VTT)

    def to_string(self, subtitles_format: SubtitlesFormat) -> str:
        result_str = ""
        time_format = None

        # Add timestamps
        if subtitles_format == SubtitlesFormat.VTT:
            # Add identifier (if it exists)
            if self.identifier:
                result_str += f"{self.identifier}\n"

            time_format = "%H:%M:%S.%f"

        elif subtitles_format == SubtitlesFormat.SRT:
            time_format = "%H:%M:%S,%f"

        result_str += f"{self.start_time.strftime(time_format)[:-3]} --> {self.end_time.strftime(time_format)[:-3]}"

        # Add settings (if WebVTT format)
        if subtitles_format == SubtitlesFormat.VTT:
            result_str += f" {self.settings}\n"

        else:
            result_str += "\n"

        # Add payload
        result_str += f"{self.payload}"

        return result_str

    def fix_rtl(self) -> None:
        """Fix Caption payload direction to RTL."""
        # Remove previous RTL-related formatting
        for char in RTL_CONTROL_CHARS:
            self.payload = self.payload.replace(char, '')

        # Add RLM char at the start of every line
        self.payload = RTL_CHAR + self.payload.replace("\n", f"\n{RTL_CHAR}")


class Comment(WebVTTBlock):
    """An object represnting a WebVTT comment block."""
    header = "NOTE"

    def __init__(self, payload, inline: bool = False):
        """
        Create a new object representing a comment block.

        Args:
            payload (str): Comment payload.
        """
        self.payload = payload
        self.inline = inline

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.inline == other.inline and self.payload == other.payload

    def __str__(self):
        if self.inline:
            return f"{self.header} {self.payload}"

        else:
            if self.payload:
                return f"{self.header}\n{self.payload}"

            else:
                return self.header


# Style, Chapter, Region
class Style(WebVTTBlock):
    """An object represnting a WebVTT style block."""
    header = "STYLE"

    def __init__(self, payload):
        """
        Create a new object representing a style block.

        Args:
            payload (str): Style payload.
        """
        self.payload = payload

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.payload == other.payload

    def __str__(self):
        return f"{self.header} {self.payload}"


class Region(WebVTTBlock):
    """An object represnting a WebVTT region block."""
    header = "REGION"

    def __init__(self, payload):
        """
        Create a new object representing a style block.

        Args:
            payload (str): Region payload.
        """
        self.payload = payload

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.payload == other.payload

    def __str__(self) -> str:
        return f"{self.header} {self.payload}"
