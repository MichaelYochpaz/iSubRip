from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import time
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar

if TYPE_CHECKING:
    from isubrip.data_structures import SubtitlesFormatType
    from isubrip.subtitle_formats.subrip import SubRipCaptionBlock, SubRipSubtitles

RTL_CONTROL_CHARS = ('\u200e', '\u200f', '\u202a', '\u202b', '\u202c', '\u202d', '\u202e')
RTL_CHAR = '\u202b'
RTL_LANGUAGES = ["ar", "he"]

SubtitlesT = TypeVar('SubtitlesT', bound='Subtitles')
SubtitlesBlockT = TypeVar('SubtitlesBlockT', bound='SubtitlesBlock')


class SubtitlesBlock(ABC):
    """Abstract base class for subtitles blocks."""
    @abstractmethod
    def __str__(self) -> str:
        pass

    @abstractmethod
    def __eq__(self, other: Any) -> bool:
        pass


class SubtitlesCaptionBlock(SubtitlesBlock, ABC):
    """A base class for subtitles caption blocks."""

    def __init__(self, start_time: time, end_time: time, payload: str):
        """
        Initialize a new SubtitlesCaptionBlock object.

        Args:
            start_time: Start timestamp of the caption block.
            end_time: End timestamp of the caption block.
            payload: Caption block's payload (text).
        """
        self.start_time = start_time
        self.end_time = end_time
        self.payload = payload

    def fix_rtl(self) -> None:
        """Fix text direction to RTL."""
        # Remove previous RTL-related formatting
        for char in RTL_CONTROL_CHARS:
            self.payload = self.payload.replace(char, '')

        # Add RLM char at the start of every line
        self.payload = RTL_CHAR + self.payload.replace("\n", f"\n{RTL_CHAR}")

    @abstractmethod
    def to_srt(self) -> SubRipCaptionBlock:
        """
        Convert WebVTT caption block to SRT caption block.

        Returns:
            SubRipCaptionBlock: The caption block in SRT format.
        """
        ...


class Subtitles(Generic[SubtitlesBlockT], ABC):
    """
    An object representing subtitles, made out of blocks.

    Attributes:
        format (SubtitlesFormatType): [Class Attribute] Format of the subtitles (contains name and file extension).
        language_code (str): Language code of the subtitles.
        blocks (list[SubtitlesBlock]): A list of subtitles blocks that make up the subtitles.
        encoding (str): Encoding of the subtitles.
    """
    format: ClassVar[SubtitlesFormatType]

    def __init__(self, language_code: str, blocks: list[SubtitlesBlockT] | None = None, encoding: str = "utf-8"):
        """
        Initialize a new Subtitles object.

        Args:
            language_code (str): Language code of the subtitles.
            blocks (list[SubtitlesBlock] | None, optional): A list of subtitles to initialize the object with.
                Defaults to None.
            encoding (str, optional): Encoding of the subtitles. Defaults to "utf-8".
        """
        self.language_code = language_code
        self.encoding = encoding

        if blocks is None:
            self.blocks = []

        else:
            self.blocks = blocks

    def __add__(self: SubtitlesT, obj: SubtitlesBlockT | SubtitlesT) -> SubtitlesT:
        """
        Add a new subtitles block, or append blocks from another subtitles object.

        Args:
            obj (SubtitlesBlock | Subtitles): A subtitles block or another subtitles object.

        Returns:
            Subtitles: The current subtitles object.
        """
        if isinstance(obj, SubtitlesBlock):
            self.add_block(obj)

        elif isinstance(obj, self.__class__):
            self.append_subtitles(obj)

        return self

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, type(self)) and self.blocks == other.blocks

    def __str__(self) -> str:
        return self.dumps()

    def dump(self) -> bytes:
        return self.dumps().encode(encoding=self.encoding)

    @abstractmethod
    def dumps(self) -> str:
        """Dump subtitles object to a string representing the subtitles."""
        ...

    @classmethod
    def load(cls, data: bytes, language_code: str, encoding: str = "utf-8") -> Subtitles:
        parsed_data = data.decode(encoding=encoding)
        return cls.loads(data=parsed_data, language_code=language_code, encoding=encoding)

    @classmethod
    @abstractmethod
    def loads(cls, data: str, language_code: str, encoding: str = "utf-8") -> Subtitles:
        ...

    def add_block(self: SubtitlesT, block: SubtitlesBlockT | list[SubtitlesBlockT]) -> SubtitlesT:
        """
        Add a new subtitles block to current subtitles.

        Args:
            block (SubtitlesBlock | list[SubtitlesBlock]):
                A block object or a list of block objects to append.

        Returns:
            Subtitles: The current subtitles object.
        """
        if isinstance(block, list):
            self.blocks.extend(block)

        else:
            self.blocks.append(block)

        return self

    def append_subtitles(self: SubtitlesT, subtitles: SubtitlesT) -> SubtitlesT:
        """
        Append subtitles to an existing subtitles object.

        Args:
            subtitles (Subtitles): Subtitles object to append to current subtitles.

        Returns:
            Subtitles: The current subtitles object.
        """
        for block in subtitles.blocks:
            self.add_block(block)

        return self

    def polish(self: SubtitlesT, fix_rtl: bool = False,
               rtl_languages: list[str] | None = None, remove_duplicates: bool = False) -> SubtitlesT:
        """
        Apply various fixes to subtitles.

        Args:
            fix_rtl (bool, optional): Whether to fix text direction of RTL languages. Defaults to False.
            rtl_languages (list[str] | None, optional): Language code of the RTL language.
                If not set, a default list of RTL languages will be used. Defaults to None.
            remove_duplicates (bool, optional): Whether to remove duplicate captions. Defaults to False.

        Returns:
            Subtitles: The current subtitles object.
        """
        rtl_language = rtl_languages if rtl_languages is not None else RTL_LANGUAGES
        rtl_fix_needed = (fix_rtl and self.language_code in rtl_language)

        if not any((
                rtl_fix_needed,
                remove_duplicates,
        )):
            return self

        previous_block: SubtitlesBlockT | None = None

        for block in self.blocks:
            if rtl_fix_needed:
                block.fix_rtl()

            if remove_duplicates and previous_block is not None and block == previous_block:
                self.blocks.remove(previous_block)

            previous_block = block

        return self

    def to_srt(self) -> SubRipSubtitles:
        """
        Convert subtitles to SRT format.

        Returns:
            SubRipSubtitles: The subtitles in SRT format.
        """
        from isubrip.subtitle_formats.subrip import SubRipSubtitles

        return SubRipSubtitles(
            language_code=self.language_code,
            blocks=[block.to_srt() for block in self.blocks if isinstance(block, SubtitlesCaptionBlock)],
            encoding=self.encoding,
        )


def split_timestamp(timestamp: str) -> tuple[time, time]:
    """
    Split a subtitles timestamp into start and end.

    Args:
        timestamp (str): A subtitles timestamp. For example: "00:00:00.000 --> 00:00:00.000"

    Returns:
        tuple(time, time): A tuple containing start and end times as a datetime object.
    """
    # Support ',' character in timestamp's milliseconds (used in SubRip format).
    timestamp = timestamp.replace(',', '.')

    start_time, end_time = timestamp.split(" --> ")
    return time.fromisoformat(start_time), time.fromisoformat(end_time)
