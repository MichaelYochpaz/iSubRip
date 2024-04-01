from __future__ import annotations

from typing import Any

from isubrip.data_structures import SubtitlesFormatType
from isubrip.subtitle_formats.subtitles import Subtitles, SubtitlesCaptionBlock


class SubRipCaptionBlock(SubtitlesCaptionBlock):
    """A subtitles caption block based on the SUBRIP format."""
    def __str__(self) -> str:
        result_str = ""
        time_format = "%H:%M:%S,%f"

        result_str += f"{self.start_time.strftime(time_format)[:-3]} --> {self.end_time.strftime(time_format)[:-3]}\n"
        result_str += f"{self.payload}"

        return result_str

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, type(self)) and \
               self.start_time == other.start_time and self.end_time == other.end_time and self.payload == other.payload

    def to_srt(self) -> SubRipCaptionBlock:
        return self


class SubRipSubtitles(Subtitles[SubRipCaptionBlock]):
    """An object representing a SubRip subtitles file."""
    format = SubtitlesFormatType.SUBRIP

    def _dumps(self) -> str:
        subtitles_str = ""
        count = 0

        for block in self.blocks:
            subtitles_str += f"{(count + 1)}\n{str(block)}\n\n"
            count += 1

        return subtitles_str.rstrip('\n')

    def _loads(self, data: str) -> None:
        raise NotImplementedError("SubRip subtitles loading is not supported.")
