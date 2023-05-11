from __future__ import annotations

import datetime as dt
import os
import re
import sys

from abc import ABCMeta
from os import PathLike
from pathlib import Path
from typing import Any, Iterable, Union, get_args, get_origin

from isubrip.data_structures import EpisodeData, MovieData, SubtitlesData, SubtitlesFormat, SubtitlesType


class SingletonMeta(ABCMeta):
    """
    A metaclass that implements the Singleton pattern.
    When a class using this metaclass is initialized, it will return the same instance every time.
    """
    _instances: dict[object, object] = {}

    def __call__(cls, *args, **kwargs) -> object:
        if cls._instances.get(cls) is None:
            cls._instances[cls] = super().__call__(*args, **kwargs)

        return cls._instances[cls]


def check_type(value: Any, type_) -> bool:
    """
    Check if a value is of a certain type.
    Works with parameterized generics.

    Args:
        value: Value to check.
        type_: Type to check against.

    Returns:
        bool: True if the value is of the specified type, False otherwise.
    """
    origin = get_origin(type_)
    args = get_args(type_)

    if origin is Union:
        return any(check_type(value, union_sub_type) for union_sub_type in args)

    elif origin is tuple:
        if args[-1] is Ellipsis:
            # Example: (int, str, ...)
            args_len = len(args)

            return check_type(value[:args_len - 1], tuple(args[:-1])) and \
                all(check_type(item, args[-2]) for item in value[args_len - 1:])

        else:
            return isinstance(value, tuple) and \
                len(value) == len(args) and \
                all(check_type(item, item_type) for item, item_type in zip(value, args))

    elif origin is list:
        return isinstance(value, list) and \
            all(check_type(item, args[0]) for item in value)

    elif origin is dict:
        return isinstance(value, dict) and \
            all(check_type(k, args[0]) and check_type(v, args[1]) for k, v in value.items())

    return isinstance(value, type_)


def download_subtitles_to_file(media_data: MovieData | EpisodeData, subtitles_data: SubtitlesData,
                               output_path: str | PathLike, overwrite: bool = False) -> Path:
    """
    Download subtitles to a file.

    Args:
        media_data (MovieData | EpisodeData): An object containing media data.
        subtitles_data (SubtitlesData): A SubtitlesData object containing subtitles data.
        output_path (str | PathLike): Path to the output folder.
        overwrite (bool, optional): Whether to overwrite files if they already exist. Defaults to True.

    Returns:
        Path: Path to the downloaded subtitles file.

    Raises:
        ValueError: If the path in `output_path` does not exist.
    """
    if not os.path.isdir(output_path):
        raise ValueError(f'Invalid path: {output_path}')

    if isinstance(media_data, MovieData):
        file_name = generate_release_name(title=media_data.name,
                                          release_year=media_data.release_date.year,
                                          media_source=media_data.source.abbreviation,
                                          language_code=subtitles_data.language_code,
                                          subtitles_type=subtitles_data.special_type,
                                          file_format=subtitles_data.subtitles_format)
    elif isinstance(media_data, EpisodeData):
        file_name = generate_release_name(title=media_data.name,
                                          release_year=media_data.release_date.year,
                                          season_number=media_data.season_number,
                                          episode_number=media_data.episode_number,
                                          episode_name=media_data.episode_name,
                                          media_source=media_data.source.abbreviation,
                                          language_code=subtitles_data.language_code,
                                          subtitles_type=subtitles_data.special_type,
                                          file_format=subtitles_data.subtitles_format)

    else:
        raise TypeError(f'This function only supports MovieData and EpisodeData objects. Got {type(media_data)}.')

    file_path = Path(output_path) / file_name

    if file_path.exists() and not overwrite:
        file_path = generate_non_conflicting_path(file_path)

    with open(file_path, 'wb') as f:
        f.write(subtitles_data.content)

    return file_path


def generate_non_conflicting_path(file_path: str | Path, has_extension: bool = True) -> Path:
    """
    Generate a non-conflicting path for a file.
    If the file already exists, a number will be added to the end of the file name.

    Args:
        file_path (str | Path): Path to a file.
        has_extension (bool, optional): Whether the name of the file includes file extension. Defaults to True.

    Returns:
        Path: A non-conflicting file path.
    """
    if isinstance(file_path, str):
        file_path = Path(file_path)

    if not file_path.exists():
        return file_path

    i = 1
    while True:
        if has_extension:
            new_file_path = file_path.parent / f'{file_path.stem}-{i}{file_path.suffix}'

        else:
            new_file_path = file_path.parent / f'{file_path}-{i}'

        if not new_file_path.exists():
            return new_file_path

        i += 1


def generate_release_name(title: str,
                          release_year: int | None = None,
                          season_number: int | None = None,
                          episode_number: int | None = None,
                          episode_name: str | None = None,
                          media_source: str | None = None,
                          source_type: str | None = "WEB",
                          additional_info: str | list[str] | None = None,
                          language_code: str | None = None,
                          subtitles_type: SubtitlesType | None = None,
                          file_format: str | SubtitlesFormat | None = None) -> str:
    """
    Generate a release name.

    Args:
        title (str): Media title.
        release_year (int | None, optional): Release year. Defaults to None.
        season_number (int | None, optional): Season number. Defaults to None.
        episode_number (int | None, optional): Episode number. Defaults to None.
        episode_name (str | None, optional): Episode name. Defaults to None.
        media_source (str | None, optional): Media source name (full or abbreviation). Defaults to None.
        source_type(str | None, optional): General source type (WEB, BluRay, etc.). Defaults to None.
        additional_info (list[str] | str | None, optional): Additional info to add to the file name. Defaults to None.
        language_code (str | None, optional): Language code. Defaults to None.
        subtitles_type (SubtitlesType | None, optional): Subtitles type. Defaults to None.
        file_format (SubtitlesFormat | str | None, optional): File format to use.  Defaults to None.

    Returns:
        str: Generated file name.
    """
    file_name = standardize_title(title)

    if release_year is not None and str(release_year) not in file_name:
        file_name += f'.{release_year}'

    if season_number is not None:
        file_name += f'.S{season_number:02}'

    if episode_number is not None:
        file_name += f'.E{episode_number:02}'

    if episode_name is not None:
        file_name += f'.{standardize_title(episode_name)}'

    if media_source is not None:
        file_name += f'.{media_source}'

    if source_type is not None:
        file_name += f'.{source_type}'

    if additional_info is not None:
        if isinstance(additional_info, (list, tuple)):
            additional_info = '.'.join(additional_info)

        file_name += f'.{additional_info}'

    if language_code is not None:
        file_name += f'.{language_code}'

    if subtitles_type is not None:
        file_name += f'.{subtitles_type.value.lower()}'

    if file_format is not None:
        if isinstance(file_format, SubtitlesFormat):
            file_format = file_format.value.file_extension

        file_name += f'.{file_format}'

    return file_name


def merge_dict_values(*dictionaries: dict) -> dict:
    """
    A function for merging the values of multiple dictionaries using the same keys.
    If a key already exists, the value will be added to a list of values mapped to that key.

    Args:
        *dictionaries (dict): Dictionaries to merge.

    Returns:
        dict: A merged dictionary.
    """
    result: dict = {}

    for dict_ in dictionaries:
        for key, value in dict_.items():
            if key in result:
                if isinstance(result[key], list) and value not in result[key]:
                    result[key].append(value)

                elif isinstance(result[key], tuple) and value not in result[key]:
                    result[key] = result[key] + (value,)

                elif value != result[key]:
                    result[key] = [result[key], value]
            else:
                result[key] = value

    return result


def single_to_list(obj) -> list:
    """
    Convert a single non-iterable object to a list.
    If None is passed, an empty list will be returned.

    Args:
        obj: Object to convert.

    Returns:
        list: A list containing the object.
            If the object is already an iterable, it will be converted to a list.
    """
    if isinstance(obj, Iterable) and not isinstance(obj, str):
        return list(obj)

    elif obj is None:
        return []

    return [obj]


def split_subtitles_timestamp(timestamp: str) -> tuple[dt.time, dt.time]:
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
    return dt.time.fromisoformat(start_time), dt.time.fromisoformat(end_time)


def standardize_title(title: str) -> str:
    """
    Format movie title to a standardized title that can be used as a file name.

    Args:
        title (str): A movie title.

    Returns:
        str: The movie title, in a file-name-friendly format.
    """
    windows_reserved_file_names = ("CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4",
                                   "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2",
                                   "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9")

    title = title.strip()

    # Replacements will be done in the same order of this list
    replacement_pairs = [
        (': ', '.'),
        (':', '.'),
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

    # If running on Windows, rename Windows reserved names to allow file creation
    if sys.platform == 'win32':
        split_title = title.split('.')

        if split_title[0].upper() in windows_reserved_file_names:
            if len(split_title) > 1:
                return split_title[0] + split_title[1] + '.'.join(split_title[2:])

            elif len(split_title) == 1:
                return "_" + title

    return title
