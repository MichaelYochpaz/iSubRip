from __future__ import annotations

import re

from datetime import time

from isubrip.constants import WEBVTT_CAPTION_BLOCK_REGEX, WEBVTT_COMMENT_HEADER_REGEX
from isubrip.enums import SubtitlesFormat
from isubrip.webvtt import WebVTTBlock, Caption, Comment, Region, Style


class Subtitles:
    """An object representing subtitles, made out of WebVTTBlocks."""
    remove_duplicates = False
    fix_rtl = False
    rtl_languages = []

    def __init__(self, language_code: str = None):
        """Initalize a new Subtitles object."""
        self.language_code: str = language_code
        self.blocks: list[WebVTTBlock] = []

    def __add__(self, block: WebVTTBlock) -> Subtitles:
        self.add_block(block)
        return self

    def _dumps_vtt(self) -> str:
        """
        Dump subtitles to a string in VTT format.

        Returns:
            str: The subtitles formatted as a string in VTT format.
        """
        subtitles_str = "WEBVTT\n\n"

        for block in self.blocks:
            subtitles_str += str(block) + "\n\n"

        return subtitles_str.rstrip('\n')

    def _dumps_srt(self) -> str:
        """
        Dump subtitles to a string in SRT format.

        Returns:
            str: The subtitles formatted as a string in SRT format.
        """
        subtitles_str = ""
        count = 0

        for block in self.blocks:
            if isinstance(block, Caption):
                subtitles_str += f"{(count + 1)}\n{block.to_string(SubtitlesFormat.SRT)}\n\n"
                count += 1

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
        return time.fromisoformat(start_time), time.fromisoformat(end_time)

    def add_block(self, block: WebVTTBlock) -> None:
        """
        Add a new WebVTT block to current subtitles.

        Args:
            block (WebVTTBlock): A block object to append.
        """
        # Don't append if `remove-duplicates` is set to true and block is same as previous one
        if not (Subtitles.remove_duplicates and len(self.blocks) > 0 and self.blocks[-1] == block):
            # Fix RTL before appending if `fix-rtl` is set to true and language is an RTL language
            if isinstance(block, Caption) and Subtitles.fix_rtl and self.language_code in Subtitles.rtl_languages:
                block.fix_rtl()

            self.blocks.append(block)

    def append_subtitles(self, subtitles: Subtitles) -> None:
        """
        Append an existing subtitles object.

        Args:
            subtitles (Subtitles): Subtitles object to append to current subtitels.
        """
        for block in subtitles.blocks:
            self.add_block(block)

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
        prev_line: str = ""

        line_split_generator = iter(subtitles_data.splitlines())
        for line in line_split_generator:
            # TODO: Change 're' functinos to Walrus operator inside if statemetns once minimum Python version is 3.8
            caption_block_regex = re.match(WEBVTT_CAPTION_BLOCK_REGEX, line)
            comment_block_regex = re.match(WEBVTT_COMMENT_HEADER_REGEX, line)

            # If the line is a timestamp
            if caption_block_regex:
                # If previous line wasn't empty, add it as an identifier
                if prev_line:
                    caption_identifier = prev_line

                else:
                    caption_identifier = ""

                caption_timestamps = Subtitles._split_timestamp(caption_block_regex.group(1))
                caption_settings = caption_block_regex.group(2)
                caption_payload = ""

                for additional_line in line_split_generator:
                    if not additional_line:
                        line = additional_line
                        break

                    caption_payload += additional_line + "\n"

                caption_payload = caption_payload.rstrip("\n")
                subtitles_obj.add_block(Caption(identifier=caption_identifier,
                                                start_time=caption_timestamps[0],
                                                end_time=caption_timestamps[1],
                                                settings=caption_settings,
                                                payload=caption_payload))

            elif comment_block_regex:
                comment_payload = ""
                inline = False

                if comment_block_regex.group(1) is not None:
                    comment_payload += comment_block_regex.group(1) + "\n"
                    inline = True

                for additional_line in line_split_generator:
                    if not additional_line:
                        line = additional_line
                        break

                    comment_payload += additional_line + "\n"

                subtitles_obj.add_block(Comment(comment_payload.rstrip("\n"), inline=inline))

            elif line.rstrip(' \t') == Region.header:
                region_payload = ""

                for additional_line in line_split_generator:
                    if not additional_line:
                        line = additional_line
                        break

                    region_payload += additional_line + "\n"

                subtitles_obj.add_block(Region(region_payload.rstrip("\n")))

            elif line.rstrip(' \t') == Style.header:
                style_payload = ""

                for additional_line in line_split_generator:
                    if not additional_line:
                        line = additional_line
                        break

                    style_payload += additional_line + "\n"

                subtitles_obj.add_block(Region(style_payload.rstrip("\n")))

            prev_line = line
        return subtitles_obj

    def dumps(self, subtitles_format: SubtitlesFormat = SubtitlesFormat.VTT) -> str:
        """
        Dump subtitles to a string.

        Args:
            subtitles_format (SubtitlesFormat): Subtitles format specification to use.

        Returns:
            str: The subtitles formatted as a string matching the specified subtitles format.
        """
        if subtitles_format == SubtitlesFormat.VTT:
            return self._dumps_vtt()

        elif subtitles_format == SubtitlesFormat.SRT:
            return self._dumps_srt()
