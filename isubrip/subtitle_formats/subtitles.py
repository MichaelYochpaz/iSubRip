from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import time
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar

from isubrip.constants import RTL_LANGUAGES
from isubrip.logger import logger

if TYPE_CHECKING:
    from isubrip.data_structures import SubtitlesFormatType
    from isubrip.subtitle_formats.subrip import SubRipCaptionBlock, SubRipSubtitles

RTL_CONTROL_CHARS = ('\u200e', '\u200f', '\u202a', '\u202b', '\u202c', '\u202d', '\u202e')
RTL_CHAR = '\u202b'

SubtitlesT = TypeVar('SubtitlesT', bound='Subtitles')
SubtitlesBlockT = TypeVar('SubtitlesBlockT', bound='SubtitlesBlock')


class SubtitlesBlock(ABC):
    """
    Abstract base class for subtitles blocks.

    Attributes:
        modified (bool): Whether the block has been modified.
    """

    def __init__(self) -> None:
        self.modified: bool = False

    @abstractmethod
    def __copy__(self) -> SubtitlesBlock:
        """Create a copy of the block."""

    @abstractmethod
    def __eq__(self, other: Any) -> bool:
        """Check if two objects are equal."""

    @abstractmethod
    def __str__(self) -> str:
        """Return a string representation of the block."""


class SubtitlesCaptionBlock(SubtitlesBlock, ABC):
    """
    A base class for subtitles caption blocks.

    Attributes:
        start_time (time): Start timestamp of the caption block.
        end_time (time): End timestamp of the caption block.
        payload (str): Caption block's payload.
    """

    def __init__(self, start_time: time, end_time: time, payload: str):
        """
        Initialize a new SubtitlesCaptionBlock object.

        Args:
            start_time: Start timestamp of the caption block.
            end_time: End timestamp of the caption block.
            payload: Caption block's payload.
        """
        super().__init__()
        self.start_time = start_time
        self.end_time = end_time
        self.payload = payload

    def __copy__(self) -> SubtitlesCaptionBlock:
        copy = self.__class__(self.start_time, self.end_time, self.payload)
        copy.modified = self.modified
        return copy

    def fix_rtl(self) -> None:
        """Fix payload's text direction to RTL."""
        previous_payload = self.payload

        # Remove previous RTL-related formatting
        for char in RTL_CONTROL_CHARS:
            self.payload = self.payload.replace(char, '')

        # Add RLM char at the start of every line
        self.payload = RTL_CHAR + self.payload.replace("\n", f"\n{RTL_CHAR}")

        if self.payload != previous_payload:
            self.modified = True

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
        _modified (bool): Whether the subtitles have been modified.
        format (SubtitlesFormatType): [Class Attribute] Format of the subtitles (contains name and file extension).
        language_code (str): Language code of the subtitles.
        blocks (list[SubtitlesBlock]): A list of subtitles blocks that make up the subtitles.
        encoding (str): Encoding of the subtitles.
        raw_data (bytes | None): Raw data of the subtitles.
    """
    format: ClassVar[SubtitlesFormatType]

    def __init__(self, data: bytes | None, language_code: str, encoding: str = "utf-8"):
        """
        Initialize a new Subtitles object.

        Args:
            data (bytes | None): Raw data of the subtitles.
            language_code (str): Language code of the subtitles.
            encoding (str, optional): Encoding of the subtitles. Defaults to "utf-8".
        """
        self._modified = False
        self.raw_data = None

        self.blocks: list[SubtitlesBlockT] = []

        self.language_code = language_code
        self.encoding = encoding

        if data:
            self.raw_data = data
            self._load(data=data)

    def __add__(self: SubtitlesT, obj: SubtitlesBlockT | SubtitlesT) -> SubtitlesT:
        """
        Add a new subtitles block, or append blocks from another subtitles object.

        Args:
            obj (SubtitlesBlock | Subtitles): A subtitles block or another subtitles object.

        Returns:
            Subtitles: The current subtitles object.
        """
        if isinstance(obj, SubtitlesBlock):
            self.add_blocks(obj)

        elif isinstance(obj, self.__class__):
            self.append_subtitles(obj)

        else:
            logger.warning(f"Cannot add object of type '{type(obj)}' to '{type(self)}' object. Skipping...")

        return self

    def __copy__(self: SubtitlesT) -> SubtitlesT:
        """Create a copy of the subtitles object."""
        copy = self.__class__(data=None, language_code=self.language_code, encoding=self.encoding)
        copy.raw_data = self.raw_data
        copy.blocks = [block.__copy__() for block in self.blocks]
        copy._modified = self.modified()  # noqa: SLF001
        return copy

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, type(self)) and self.blocks == other.blocks

    def __str__(self) -> str:
        return self.dumps()

    def _dump(self) -> bytes:
        """
        Dump subtitles object to bytes representing the subtitles.

        Returns:
            bytes: The subtitles in a bytes object.
        """
        return self._dumps().encode(encoding=self.encoding)

    @abstractmethod
    def _dumps(self) -> str:
        """
        Dump subtitles object to a string representing the subtitles.

        Returns:
            str: The subtitles in a string format.
        """
        ...

    def _load(self, data: bytes) -> None:
        """
        Load and parse subtitles data from bytes.

        Args:
            data (bytes): Subtitles data to load.
        """
        parsed_data = data.decode(encoding=self.encoding)
        self._loads(data=parsed_data)

    @abstractmethod
    def _loads(self, data: str) -> None:
        """
        Load and parse subtitles data from a string.

        Args:
            data (bytes): Subtitles data to load.
        """
        ...

    def dump(self) -> bytes:
        """
        Dump subtitles to a bytes object representing the subtitles.
        Returns the original raw subtitles data if they have not been modified, and raw data is available.

        Returns:
            bytes: The subtitles in a bytes object.
        """
        if self.raw_data is not None and not self.modified():
            logger.debug("Returning original raw data as subtitles have not been modified.")
            return self.raw_data

        return self._dump()

    def dumps(self) -> str:
        """
        Dump subtitles to a string representing the subtitles.
        Returns the original raw subtitles data if they have not been modified, and raw data is available.

        Returns:

        """
        if self.raw_data is not None and not self.modified():
            logger.debug("Returning original raw data (decoded) as subtitles have not been modified.")
            return self.raw_data.decode(encoding=self.encoding)

        return self._dumps()

    def add_blocks(self: SubtitlesT,
                   blocks: SubtitlesBlockT | list[SubtitlesBlockT],
                   set_modified: bool = True) -> SubtitlesT:
        """
        Add a new subtitles block to current subtitles.

        Args:
            blocks (SubtitlesBlock | list[SubtitlesBlock]):
                A block object or a list of block objects to append.
            set_modified (bool, optional): Whether to set the subtitles as modified. Defaults to True.

        Returns:
            Subtitles: The current subtitles object.
        """
        if isinstance(blocks, list):
            if not blocks:
                return self

            self.blocks.extend(blocks)

        else:
            self.blocks.append(blocks)

        if set_modified:
            self._modified = True

        return self

    def append_subtitles(self: SubtitlesT,
                         subtitles: SubtitlesT) -> SubtitlesT:
        """
        Append subtitles to an existing subtitles object.

        Args:
            subtitles (Subtitles): Subtitles object to append to current subtitles.

        Returns:
            Subtitles: The current subtitles object.
        """
        if subtitles.blocks:
            self.add_blocks(deepcopy(subtitles.blocks))

            if subtitles.modified():
                self._modified = True

        return self

    def polish(self: SubtitlesT,
               fix_rtl: bool = False,
               remove_duplicates: bool = True,
               ) -> SubtitlesT:
        """
        Apply various fixes to subtitles.

        Args:
            fix_rtl (bool, optional): Whether to fix text direction of RTL languages. Defaults to False.
            remove_duplicates (bool, optional): Whether to remove duplicate captions. Defaults to True.

        Returns:
            Subtitles: The current subtitles object.
        """
        fix_rtl = (fix_rtl and self.language_code.split('-')[0] in RTL_LANGUAGES)

        if not any((
                fix_rtl,
                remove_duplicates,
        )):
            return self

        previous_block: SubtitlesBlockT | None = None

        for block in self.blocks:
            if fix_rtl:
                block.fix_rtl()

            if remove_duplicates and previous_block is not None and block == previous_block:
                self.blocks.remove(previous_block)
                self._modified = True

            previous_block = block

        return self

    def modified(self) -> bool:
        """
        Check if the subtitles have been modified (by checking if any of its blocks have been modified).

        Returns:
            bool: True if the subtitles have been modified, False otherwise.
        """
        return self._modified or any(block.modified for block in self.blocks)

    def to_srt(self) -> SubRipSubtitles:
        """
        Convert subtitles to SRT format.

        Returns:
            SubRipSubtitles: The subtitles in SRT format.
        """
        from isubrip.subtitle_formats.subrip import SubRipSubtitles

        subrip_subtitles = SubRipSubtitles(
            data=None,
            language_code=self.language_code,
            encoding=self.encoding,
        )
        subrip_blocks = [block.to_srt() for block in self.blocks if isinstance(block, SubtitlesCaptionBlock)]
        subrip_subtitles.add_blocks(subrip_blocks)

        return subrip_subtitles


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
