from __future__ import annotations

import re
from datetime import time
from typing import Union

from isubrip.constants import RTL_CHAR, RTL_CONTROL_CHARS, TIMESTAMP_REGEX
from isubrip.enums import SubtitlesFormat


class Subtitles:
    fix_rtl = False
    rtl_languages = []

    """An object representing subtitles, made out of paragraphs."""

    def __init__(self, language_code: str = None):
        """Initalize a new Subtitles object."""
        self.language_code = language_code
        self.paragraphs = []

    def __add__(self, paragraph: Paragraph) -> Subtitles:
        """
        Add a new paragraph to current subtitles.

        Args:
            paragraph (Paragraph): A paragraph object to append.
        """
        self.add_paragraph(paragraph)
        return self

    def _dumps_vtt(self) -> str:
        """
        Dump subtitles to a string in VTT format.

        Returns:
            str: The subtitles formatted as a string in VTT format.
        """
        subtitles_str = "WEBVTT\n\n"

        for paragraph in self.paragraphs:
            subtitles_str += f"{paragraph.to_string(SubtitlesFormat.VTT)}\n\n"

        return subtitles_str.rstrip('\n')

    def _dumps_srt(self) -> str:
        """
        Dump subtitles to a string in SRT format.

        Returns:
            str: The subtitles formatted as a string in SRT format.
        """
        subtitles_str = ""

        for idx, paragraph in enumerate(self.paragraphs):
            subtitles_str += f"{(idx + 1)}\n{paragraph.to_string(SubtitlesFormat.SRT)}\n\n"

        return subtitles_str.rstrip('\n')

    @staticmethod
    def _split_timestamp(timestamp: str) -> tuple[time, time]:
        """
        Splits a timestamp into start and end.

        Args:
            timestamp (str): A subtitles timestamp. For example: "00:00:00.000 --> 00:00:00.000"

        Returns:
            tuple(time, time): A tuple containing start and end times as a datetime object.
        """
        # Support ',' character in timestamp's milliseconds (used in srt format).
        timestamp = timestamp.replace(',', '.')

        start_time, end_time = timestamp.split(" --> ")
        t = time.fromisoformat(start_time)
        return time.fromisoformat(start_time), time.fromisoformat(end_time)

    def add_paragraph(self, paragraph: Paragraph) -> None:
        """
        Add a new paragraph to current subtitles.

        Args:
            paragraph (Paragraph): A paragraph object to append.
        """
        # Fix RTL before appending if `fix-rtl` is set to true and language is an RTL language
        if Subtitles.fix_rtl and self.language_code in Subtitles.rtl_languages:
            paragraph.fix_rtl()

        self.paragraphs.append(paragraph)

    def append_subtitles(self, subtitles: Subtitles) -> None:
        """
        Append an existing subtitles object.

        Args:
            subtitles (Subtitles): Subtitles object to append to current subtitels.
        """
        for paragraph in subtitles.paragraphs:
            self.add_paragraph(paragraph)

    @staticmethod
    def loads(subtitles_data: str) -> Subtitles:
        """
        Load subtitles from a string.

        Args:
            subtitles_data (str): Subtitles data to load.

        Returns:
            Subtitles: A Subtitles object loaded from the string.
        """
        subtitles_obj = Subtitles()

        regex_split = re.split(rf"^(?:[0-9]+\n)?({TIMESTAMP_REGEX}).*\n", subtitles_data, flags=re.MULTILINE)

        paragraph_timestamp: Union[str, None] = None
        paragraph_text = ""

        for line in regex_split:
            if re.match(TIMESTAMP_REGEX, line):
                if paragraph_timestamp is not None:
                    timestamps = Subtitles._split_timestamp(paragraph_timestamp)
                    subtitles_obj += Paragraph(timestamps[0], timestamps[1], paragraph_text.rstrip("\n"))
                paragraph_timestamp = line
                paragraph_text = ""

            elif paragraph_timestamp is not None:
                paragraph_text += line

        if paragraph_timestamp is not None:
            timestamps = Subtitles._split_timestamp(paragraph_timestamp)
            subtitles_obj.add_paragraph(Paragraph(timestamps[0], timestamps[1], paragraph_text.rstrip("\n")))

        return subtitles_obj

    def dumps(self, subtitles_format: SubtitlesFormat = SubtitlesFormat.VTT) -> str:
        """
        Dump subtitles to a string.

        Args:
            subtitles_format (SubtitlesFormat): Subtitles format specification to use.

        Returns:
            str: The subtitles formatted as a string matching the specified subtitles format.
        """
        subtitles_str = ""

        if subtitles_format == SubtitlesFormat.VTT:
            return self._dumps_vtt()

        elif subtitles_format == SubtitlesFormat.SRT:
            return self._dumps_srt()


class Paragraph:
    """An object represnting a subtitles paragraph."""

    def __init__(self, start_time: time, end_time: time, text: str):
        """
        Create a new Paragraph object.

        Args:
            start_time (time): Paragraph start time.
            end_time (time): Paragraph end time.
            text: Paragraph text.
        """
        self.start_time = start_time
        self.end_time = end_time
        self.text = text

    def fix_rtl(self) -> None:
        """Fix paragraph direction to RTL."""
        # Remove previous RTL-related formatting
        for char in RTL_CONTROL_CHARS:
            self.text = self.text.replace(char, "")

        # Add RLM char at the start and on every new line
        self.text = RTL_CHAR + self.text.replace("\n", f"\n{RTL_CHAR}")

    def to_string(self, subtitles_format: SubtitlesFormat) -> str:
        """
        Convert current paragraph to a subtitles-formatted string.

        Args:
            subtitles_format (SubtitlesFormat): Subtitles format specification to use.

        Returns:
            str: The paragraph formatted as a string matching the specified subtitles format.
        """
        time_format = None

        if subtitles_format == SubtitlesFormat.VTT:
            time_format = "%H:%M:%S.%f"

        elif subtitles_format == SubtitlesFormat.SRT:
            time_format = "%H:%M:%S,%f"

        timestamp = f"{self.start_time.strftime(time_format)[:-3]} --> {self.end_time.strftime(time_format)[:-3]}"
        return f"{timestamp}\n{self.text}"
