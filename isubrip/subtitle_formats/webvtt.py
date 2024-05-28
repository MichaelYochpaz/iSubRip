from __future__ import annotations

from abc import ABCMeta
import re
from typing import TYPE_CHECKING, Any, ClassVar

from isubrip.data_structures import SubtitlesFormatType
from isubrip.subtitle_formats.subrip import SubRipCaptionBlock
from isubrip.subtitle_formats.subtitles import RTL_CHAR, Subtitles, SubtitlesBlock, SubtitlesCaptionBlock
from isubrip.utils import split_subtitles_timestamp

if TYPE_CHECKING:
    from datetime import time

# WebVTT Documentation:
# https://www.w3.org/TR/webvtt1/#cues
# https://developer.mozilla.org/en-US/docs/Web/API/WebVTT_API#webvtt_cues


class WebVTTBlock(SubtitlesBlock, metaclass=ABCMeta):
    """
    Abstract base class for WEBVTT cue blocks.
    """
    is_caption_block: bool = False


class WebVTTCaptionBlock(SubtitlesCaptionBlock, WebVTTBlock):
    """An object representing a WebVTT caption block."""
    subrip_alignment_conversion: ClassVar[bool] = False

    is_caption_block: bool = True

    def __init__(self, start_time: time, end_time: time, payload: str, settings: str = "", identifier: str = ""):
        """
        Initialize a new object representing a WebVTT caption block.

        Args:
            start_time (time): Cue start time.
            end_time (time): Cue end time.
            settings (str): Cue settings.
            payload (str): Cue payload.
        """
        super().__init__(start_time=start_time, end_time=end_time, payload=payload)
        self.identifier = identifier
        self.settings = settings

    def to_srt(self) -> SubRipCaptionBlock:
        # Add a {\an8} tag at the start of the payload if it has 'line:0.00%' in the settings
        if "line:0.00%" in self.settings and self.subrip_alignment_conversion:
            # If the payload starts with an RTL control char, add the tag after it
            if self.payload.startswith(RTL_CHAR):
                payload = RTL_CHAR + WEBVTT_ALIGN_TOP_TAG + self.payload[len(RTL_CHAR):]

            else:
                payload = WEBVTT_ALIGN_TOP_TAG + self.payload

        else:
            payload = self.payload

        return SubRipCaptionBlock(start_time=self.start_time, end_time=self.end_time, payload=payload)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, type(self)) and \
            self.start_time == other.start_time and self.end_time == other.end_time and self.payload == other.payload

    def __str__(self) -> str:
        result_str = ""
        time_format = "%H:%M:%S.%f"

        # Add identifier (if it exists)
        if self.identifier:
            result_str += f"{self.identifier}\n"

        result_str += f"{self.start_time.strftime(time_format)[:-3]} --> {self.end_time.strftime(time_format)[:-3]}"

        if self.settings:
            result_str += f" {self.settings}"

        result_str += f"\n{self.payload}"

        return result_str


class WebVTTCommentBlock(WebVTTBlock):
    """An object representing a WebVTT comment block."""
    header = "NOTE"

    def __init__(self, payload: str, inline: bool = False) -> None:
        """
        Initialize a new object representing a WebVTT comment block.

        Args:
            payload (str): Comment payload.
        """
        super().__init__()
        self.payload = payload
        self.inline = inline

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, type(self)) and self.inline == other.inline and self.payload == other.payload

    def __str__(self) -> str:
        if self.inline:
            return f"{self.header} {self.payload}"

        if self.payload:
            return f"{self.header}\n{self.payload}"

        return self.header


class WebVTTStyleBlock(WebVTTBlock):
    """An object representing a WebVTT style block."""
    header = "STYLE"

    def __init__(self, payload: str) -> None:
        """
        Initialize a new object representing a WebVTT style block.

        Args:
            payload (str): Style payload.
        """
        super().__init__()
        self.payload = payload

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, type(self)) and self.payload == other.payload

    def __str__(self) -> str:
        return f"{self.header}\n{self.payload}"


class WebVTTRegionBlock(WebVTTBlock):
    """An object representing a WebVTT region block."""
    header = "REGION"

    def __init__(self, payload: str) -> None:
        """
        Initialize a new object representing a WebVTT region block.

        Args:
            payload (str): Region payload.
        """
        super().__init__()
        self.payload = payload

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, type(self)) and self.payload == other.payload

    def __str__(self) -> str:
        return f"{self.header} {self.payload}"


class WebVTTSubtitles(Subtitles[WebVTTBlock]):
    """An object representing a WebVTT subtitles file."""
    format = SubtitlesFormatType.WEBVTT

    def _dumps(self) -> str:
        """
        Dump subtitles to a string representing the subtitles in a WebVTT format.

        Returns:
            str: The subtitles in a string using a WebVTT format.
        """
        subtitles_str = "WEBVTT\n\n"

        for block in self.blocks:
            subtitles_str += str(block) + "\n\n"

        return subtitles_str.rstrip('\n')

    def _loads(self, data: str) -> None:
        """
        Load and parse WebVTT subtitles data from a string.

        Args:
            data (bytes): Subtitles data to load.
        """
        prev_line: str = ""
        lines_iterator = iter(data.splitlines())

        for line in lines_iterator:
            # If the line is a timestamp
            if caption_block_regex := re.match(WEBVTT_CAPTION_BLOCK_REGEX, line):
                # If previous line wasn't empty, add it as an identifier
                if prev_line:
                    caption_identifier = prev_line

                else:
                    caption_identifier = ""

                caption_timestamps = split_subtitles_timestamp(caption_block_regex.group(1))
                caption_settings = caption_block_regex.group(2)
                caption_payload = ""

                for additional_line in lines_iterator:
                    if not additional_line:
                        line = additional_line
                        break

                    caption_payload += additional_line + "\n"

                caption_payload = caption_payload.rstrip("\n")
                self.blocks.append(WebVTTCaptionBlock(
                    identifier=caption_identifier,
                    start_time=caption_timestamps[0],
                    end_time=caption_timestamps[1],
                    settings=caption_settings,
                    payload=caption_payload))

            elif comment_block_regex := re.match(WEBVTT_COMMENT_HEADER_REGEX, line):
                comment_payload = ""
                inline = False

                if comment_block_regex.group(1) is not None:
                    comment_payload += comment_block_regex.group(1) + "\n"
                    inline = True

                for additional_line in lines_iterator:
                    if not additional_line:
                        line = additional_line
                        break

                    comment_payload += additional_line + "\n"

                self.blocks.append(WebVTTCommentBlock(comment_payload.rstrip("\n"), inline=inline))

            elif line.rstrip(' \t') == WebVTTRegionBlock.header:
                region_payload = ""

                for additional_line in lines_iterator:
                    if not additional_line:
                        line = additional_line
                        break

                    region_payload += additional_line + "\n"

                self.blocks.append(WebVTTRegionBlock(region_payload.rstrip("\n")))

            elif line.rstrip(' \t') == WebVTTStyleBlock.header:
                style_payload = ""

                for additional_line in lines_iterator:
                    if not additional_line:
                        line = additional_line
                        break

                    style_payload += additional_line + "\n"

                self.blocks.append(WebVTTStyleBlock(style_payload.rstrip("\n")))

            prev_line = line

    def remove_head_blocks(self) -> None:
        """
        Remove all head blocks (Style / Region) from the subtitles.

        NOTE:
            Comment blocks are removed as well if they are before the first caption block (since they're probably
            related to the head blocks).
        """
        for block in self.blocks:
            if isinstance(block, WebVTTCaptionBlock):
                break

            if isinstance(block, (WebVTTCommentBlock, WebVTTStyleBlock, WebVTTRegionBlock)):
                self.blocks.remove(block)


# --- Constants ---
WEBVTT_PERCENTAGE_REGEX = r"\d{1,3}(?:\.\d+)?%"
WEBVTT_CAPTION_TIMINGS_REGEX = \
    r"(?:[0-5]\d:)?[0-5]\d:[0-5]\d[\.,]\d{3}[ \t]+-->[ \t]+(?:[0-5]\d:)?[0-5]\d:[0-5]\d[\.,]\d{3}"

WEBVTT_CAPTION_SETTING_ALIGNMENT_REGEX = r"align:(?:start|center|middle|end|left|right)"
WEBVTT_CAPTION_SETTING_LINE_REGEX = rf"line:(?:{WEBVTT_PERCENTAGE_REGEX}|-?\d+%)(?:,(?:start|center|middle|end))?"
WEBVTT_CAPTION_SETTING_POSITION_REGEX = rf"position:{WEBVTT_PERCENTAGE_REGEX}(?:,(?:start|center|middle|end))?"
WEBVTT_CAPTION_SETTING_REGION_REGEX = r"region:(?:(?!(?:-->)|\t)\S)+"
WEBVTT_CAPTION_SETTING_SIZE_REGEX = rf"size:{WEBVTT_PERCENTAGE_REGEX}"
WEBVTT_CAPTION_SETTING_VERTICAL_REGEX = r"vertical:(?:lr|rl)"

WEBVTT_CAPTION_SETTINGS_REGEX = ("(?:"
                                 f"(?:{WEBVTT_CAPTION_SETTING_ALIGNMENT_REGEX})|"
                                 f"(?:{WEBVTT_CAPTION_SETTING_LINE_REGEX})|"
                                 f"(?:{WEBVTT_CAPTION_SETTING_POSITION_REGEX})|"
                                 f"(?:{WEBVTT_CAPTION_SETTING_REGION_REGEX})|"
                                 f"(?:{WEBVTT_CAPTION_SETTING_SIZE_REGEX})|"
                                 f"(?:{WEBVTT_CAPTION_SETTING_VERTICAL_REGEX})|"
                                 f"(?:[ \t]+)"
                                 ")*")

WEBVTT_CAPTION_BLOCK_REGEX = re.compile(rf"^({WEBVTT_CAPTION_TIMINGS_REGEX})[ \t]*({WEBVTT_CAPTION_SETTINGS_REGEX})?")
WEBVTT_COMMENT_HEADER_REGEX = re.compile(rf"^{WebVTTCommentBlock.header}(?:$|[ \t])(.+)?")

WEBVTT_ALIGN_TOP_TAG = "{\\an8}"
