import re

from os import PathLike
from typing import Optional, Union, Tuple, List

from isubrip.config import Config
from isubrip.enums import SubtitlesFormat, SubtitlesType


def standardize_title(title: str) -> str:
    """
    Format movie title to a standardized title that can be used as a file name.

    Args:
        title (str): A movie title.

    Returns:
        str: The title, in a file-name-friendly format.
    """
    # Replacements will be done in the same order of this list
    replacement_pairs = [
        (': ', '.'),
        (' - ', '-'),
        (', ', '.'),
        ('. ', '.'),
        (' ', '.'),
        ('|', '.'),
        ('/', '.'),
        ('<', ''),
        ('>', ''),
        ('(', ''),
        (')', ''),
        ('"', ''),
        ('?', ''),
        ('*', ''),
    ]

    for pair in replacement_pairs:
        title = title.replace(pair[0], pair[1])

    title = re.sub(r"\.+", ".", title)  # Replace multiple dots with a single dot

    return title


def generate_release_name(title: str, release_year: Optional[int] = None,
                          season_number: Optional[int] = None, episode_number: Optional[int] = None,
                          media_source: Optional[str] = None, source_type: Optional[str] = "WEB",
                          additional_info: Union[List[str], Tuple[str], str] = None,
                          subtitles_info: Union[str, Tuple[str, SubtitlesType], None] = None,
                          file_format: Union[SubtitlesFormat, str, None] = None) -> str:
    """
    Generate a release name.

    Args:
        title (str): Media title.
        release_year (int, optional): Release year.
        season_number (int, optional): Season number.
        episode_number (int, optional): Episode number.
        media_source (str, optional): Source (abbreviation or full name).
        source_type(str, optional): General source type (WEB, BluRay, etc.).
        additional_info (List[str] | Tuple[str] | str, optional): Additional info to add to the file name.
        subtitles_info (str | Tuple[str, SubtitlesType], optional): Subtitles info.
            Either a language code (str), or a language code and a subtitles type (str, SubtitlesType).
        file_format (SubtitlesFormat | str, optional): File format to use.

    Returns:
        str: Generated file name.
    """
    file_name = standardize_title(title)

    if release_year is not None:
        file_name += f'.{release_year}'

    if season_number is not None:
        file_name += f'.S{season_number:02}'

    if episode_number is not None:
        file_name += f'.E{episode_number:02}'

    if media_source is not None:
        file_name += f'.{media_source}'

    if source_type is not None:
        file_name += f'.{source_type}'

    if additional_info is not None:
        if isinstance(additional_info, (list, tuple)):
            additional_info = '.'.join(additional_info)

        file_name += f'.{additional_info}'

    if subtitles_info is not None:
        if isinstance(subtitles_info, tuple):
            file_name += f'.{subtitles_info[0]}'

            if subtitles_info[1] != SubtitlesType.NORMAL:
                file_name += f'.{subtitles_info[1].name.lower()}'

        else:
            file_name += f'.{subtitles_info}'

    if file_format is not None:
        if isinstance(file_format, SubtitlesFormat):
            file_format = file_format.name.lower()

        file_name += f'.{file_format}'

    return file_name


def parse_config(file_path: Union[str, PathLike], *file_paths: Union[str, PathLike]) -> Config:
    """
    Parse config files by order and return a Config object.

    Args:
        file_path (str): A config file to parse.
        *file_paths (str, optional): Additional config files to parse (will override previous settings).

    Returns:
        Config: A parsed Config object.
    """
    config = Config()
    file_paths: tuple = (file_path,) + file_paths

    for file_path in file_paths:
        with open(file_path, 'r') as data:
            config.loads(data.read())

    return config
