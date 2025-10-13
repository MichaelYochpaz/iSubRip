from __future__ import annotations

from abc import ABCMeta
import datetime as dt
from functools import lru_cache
import logging
from pathlib import Path
import re
import secrets
import shutil
import sys
from typing import TYPE_CHECKING, Any, Literal, cast, overload

from wcwidth import wcswidth

from isubrip.constants import WINDOWS_RESERVED_FILE_NAMES, temp_folder_path
from isubrip.data_structures import (
    Episode,
    MediaBase,
    Movie,
    Season,
    Series,
    SubtitlesData,
    SubtitlesFormatType,
    SubtitlesType,
    T,
)
from isubrip.logger import logger

if TYPE_CHECKING:
    from os import PathLike
    from types import TracebackType

    import httpx
    from pydantic import BaseModel, ValidationError


class SingletonMeta(ABCMeta):
    """
    A metaclass that implements the Singleton pattern.
    When a class using this metaclass is initialized, it will return the same instance every time.
    """
    _instances: dict[object, object] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> object:
        if cls._instances.get(cls) is None:
            cls._instances[cls] = super().__call__(*args, **kwargs)

        return cls._instances[cls]


class TemporaryDirectory:
    """
    A context manager for creating and managing a temporary directory.

    Args:
        directory_name (str | None, optional): Name of the directory to generate.
            If not specified, a random string will be generated. Defaults to None.
    """
    def __init__(self, directory_name: str | None = None):
        if directory_name:
            self.directory_name = sanitize_path_segment(directory_name)
        else:
            self.directory_name = secrets.token_hex(5)

        self.path = temp_folder_path() / self.directory_name

    def __enter__(self) -> Path:
        """Create the temporary directory and return its path."""
        if self.path.is_dir():
            logger.debug(f"Temporary directory '{self.path}' already exists. "
                         f"Emptying directory from all contents...")
            shutil.rmtree(self.path)

        self.path.mkdir(parents=True)
        logger.debug(f"Temporary directory has been generated: '{self.path}'")
        return self.path

    def __exit__(self, exc_type: type[BaseException] | None,
                 exc_val: BaseException | None, exc_tb: TracebackType | None) -> None:
        """Clean up the temporary directory."""
        self.cleanup()

    def cleanup(self) -> None:
        """Remove the temporary directory."""
        if not self.path.exists():
            return

        logger.debug(f"Removing temporary directory: '{self.path}'")
        try:
            shutil.rmtree(self.path)
        except Exception as e:
            logger.warning(f"Failed to remove temporary directory '{self.path}': {e}")


def convert_epoch_to_datetime(epoch_timestamp: int) -> dt.datetime:
    """
    Convert an epoch timestamp to a datetime object.

    Args:
        epoch_timestamp (int): Epoch timestamp.

    Returns:
        datetime: A datetime object representing the timestamp.
    """
    if epoch_timestamp >= 0:
        return dt.datetime.fromtimestamp(epoch_timestamp)

    return dt.datetime(1970, 1, 1) + dt.timedelta(seconds=epoch_timestamp)


def convert_log_level(log_level: str) -> int:
    """
    Convert a log level string to a logging level.

    Args:
        log_level (str): Log level string.

    Returns:
        int: Logging level.
    
    Raises:
        ValueError: If the log level is invalid.
    """
    log_level_upper = log_level.upper()
    if log_level_upper not in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
        raise ValueError(f"Invalid log level: {log_level}")

    return cast("int", getattr(logging, log_level_upper))


def download_subtitles_to_file(media_data: Movie | Episode, subtitles_data: SubtitlesData, output_path: str | PathLike,
                               source_abbreviation: str | None = None, overwrite: bool = False) -> Path:
    """
    Download subtitles to a file.

    Args:
        media_data (Movie | Episode): An object containing media data.
        subtitles_data (SubtitlesData): A SubtitlesData object containing subtitles data.
        output_path (str | PathLike): Path to the output folder.
        source_abbreviation (str | None, optional): Abbreviation of the source the subtitles are downloaded from.
            Defaults to None.
        overwrite (bool, optional): Whether to overwrite files if they already exist. Defaults to True.

    Returns:
        Path: Path to the downloaded subtitles file.

    Raises:
        ValueError: If the path in `output_path` does not exist.
    """
    output_path = Path(output_path)

    if not output_path.is_dir():
        raise ValueError(f"Invalid path: {output_path}")

    if isinstance(media_data, Movie):
        file_name = format_release_name(title=media_data.name,
                                        release_date=media_data.release_date,
                                        media_source=source_abbreviation,
                                        language_code=subtitles_data.language_code,
                                        subtitles_type=subtitles_data.special_type,
                                        file_format=subtitles_data.subtitles_format)
    else:  # isinstance(media_data, Episode):
        file_name = format_release_name(title=media_data.series_name,
                                        release_date=media_data.release_date,
                                        season_number=media_data.season_number,
                                        episode_number=media_data.episode_number,
                                        episode_name=media_data.episode_name,
                                        media_source=source_abbreviation,
                                        language_code=subtitles_data.language_code,
                                        subtitles_type=subtitles_data.special_type,
                                        file_format=subtitles_data.subtitles_format)

    file_path = output_path / file_name

    if file_path.exists() and not overwrite:
        file_path = generate_non_conflicting_path(file_path=file_path)

    with file_path.open('wb') as f:
        f.write(subtitles_data.content)

    return file_path

def format_config_validation_error(exc: ValidationError) -> str:
    """
    Format a Pydantic ValidationError into a human-readable string.

    Args:
        exc (ValidationError): The ValidationError instance containing validation errors.

    Returns:
        str: A formatted string describing the validation errors, including the location,
             type, value, and error messages for each invalid field.
    """
    validation_errors = exc.errors()
    error_str = ""

    consolidated_errors: dict[str, dict[str, Any]] = {}

    for validation_error in validation_errors:
        value: Any = validation_error['input']
        value_type: str = type(value).__name__
        location: list[str] = [str(item) for item in validation_error['loc']]
        error_msg: str = validation_error['msg']

        # When the expected type is a union, Pydantic returns several errors for each type,
        # with the type being the last item in the location list
        if (
                isinstance(location[-1], str) and
                (location[-1].endswith(']') or location[-1] in ('str', 'int', 'float', 'bool'))
        ):
            location.pop()

        if len(location) > 1:
            location_str = ".".join(location)

        else:
            location_str = location[0]

        if location_str in consolidated_errors:
            consolidated_errors[location_str]['errors'].append(error_msg)

        else:
            consolidated_errors[location_str] = {}
            consolidated_errors[location_str]['info'] = {
                "value": value,
                "type": value_type,
            }
            consolidated_errors[location_str]['errors'] = [error_msg]

    for error_loc, error_data in consolidated_errors.items():
        error_type = error_data['info']['type']
        error_value = error_data['info']['value']
        error_str += f"'{error_loc}' (type: '{error_type}', value: '{error_value}'):\n"
        
        for error in error_data['errors']:
            error_str += f"    {error}\n"

    return error_str


def format_list(items: list[str], width: int = 80) -> str:
    """
    Format a list of strings into a grid-like display with dynamic column widths.
    
    The function automatically calculates the optimal number of columns based on the maximum item width 
    and the desired total width. It properly handles Unicode characters by using their display width.

    Args:
        items (list[str]): List of strings to format
        width (int, optional): Maximum width of the output in characters. Defaults to 80.

    Returns:
        str: A formatted string with items arranged in columns

    Example:
        >>> items = ["Item 1", "Long Item 2", "Item 3", "Item 4"]
        >>> print(format_list(items, width=40))
        Item 1      Long Item 2
        Item 3      Item 4
    """
    if not items:
        return ""
    
    # Calculate true display width for each item and add spacing
    item_widths = [(s, wcswidth(s)) for s in items]
    column_width = max(width for _, width in item_widths) + 4  # Add spacing between columns
    columns = max(1, width // column_width)  # At least one column
    
    # Build rows with proper spacing
    rows = []
    for i in range(0, len(item_widths), columns):
        row_items = item_widths[i:i + columns]
        cols = []
        for text, text_width in row_items:
            padding = " " * (column_width - text_width)
            cols.append(f"{text}{padding}")
        rows.append("".join(cols).rstrip())
    
    return "\n".join(rows)


def format_media_description(media_data: MediaBase, shortened: bool = False) -> str:
    """
    Generate a short description string of a media object.

    Args:
        media_data (MediaBase): An object containing media data.
        shortened (bool, optional): Whether to generate a shortened description. Defaults to False.

    Returns:
        str: A short description string of the media object.
    """
    if isinstance(media_data, Movie):
        release_year = (
            media_data.release_date.year
            if isinstance(media_data.release_date, dt.datetime)
            else media_data.release_date
        )
        description_str = f"{media_data.name.strip()} [{release_year}]"

        if media_data.id:
            description_str += f" (ID: {media_data.id})"

        return description_str

    if isinstance(media_data, Series):
        description_str = f"{media_data.series_name.strip()}"

        if media_data.series_release_date:
            if isinstance(media_data.series_release_date, dt.datetime):
                description_str += f" [{media_data.series_release_date.year}]"

            else:
                description_str += f" [{media_data.series_release_date}]"

        if media_data.id:
            description_str += f" (ID: {media_data.id})"

        return description_str

    if isinstance(media_data, Season):
        description_str = ""

        if not shortened:
            description_str = f"{media_data.series_name.strip()} - "

        description_str += f"Season {media_data.season_number}"

        if media_data.season_name:
            description_str += f" - {media_data.season_name.strip()}"

        if media_data.id:
            description_str += f" (ID: {media_data.id})"

        return description_str

    if isinstance(media_data, Episode):
        description_str = ""

        if not shortened:
            description_str = f"{media_data.series_name.strip()} - "
    
        description_str += f"S{media_data.season_number:02d}E{media_data.episode_number:02d}"

        if media_data.episode_name:
            description_str += f" - {media_data.episode_name.strip()}"

        if media_data.id:
            description_str += f" (ID: {media_data.id})"

        return description_str

    raise ValueError(f"Unsupported media type: '{type(media_data)}'")


def format_release_name(title: str,
                        release_date: dt.datetime | int | None = None,
                        season_number: int | None = None,
                        episode_number: int | None = None,
                        episode_name: str | None = None,
                        media_source: str | None = None,
                        source_type: str | None = "WEB",
                        additional_info: str | list[str] | None = None,
                        language_code: str | None = None,
                        subtitles_type: SubtitlesType | None = None,
                        file_format: str | SubtitlesFormatType | None = None) -> str:
    """
    Format a release name.

    Args:
        title (str): Media title.
        release_date (int | None, optional): Release date (datetime), or year (int) of the media. Defaults to None.
        season_number (int | None, optional): Season number. Defaults to None.
        episode_number (int | None, optional): Episode number. Defaults to None.
        episode_name (str | None, optional): Episode name. Defaults to None.
        media_source (str | None, optional): Media source name (full or abbreviation). Defaults to None.
        source_type(str | None, optional): General source type (WEB, BluRay, etc.). Defaults to None.
        additional_info (list[str] | str | None, optional): Additional info to add to the file name. Defaults to None.
        language_code (str | None, optional): Language code. Defaults to None.
        subtitles_type (SubtitlesType | None, optional): Subtitles type. Defaults to None.
        file_format (SubtitlesFormat | str | None, optional): File format to use. Defaults to None.

    Returns:
        str: Generated file name.
    """
    file_name = slugify_title(title=title, separator=".")

    if release_date is not None:
        if isinstance(release_date, dt.datetime):
            release_year = release_date.year
        else:
            release_year = release_date
        file_name += f".{release_year}"

    if season_number is not None and episode_number is not None:
        file_name += f".S{season_number:02}E{episode_number:02}"

    if episode_name is not None:
        file_name += f".{slugify_title(title=episode_name, separator='.')}"

    if media_source is not None:
        file_name += f".{media_source}"

    if source_type is not None:
        file_name += f".{source_type}"

    if additional_info is not None:
        if isinstance(additional_info, list | tuple):
            additional_info = '.'.join(additional_info)
        file_name += f".{additional_info}"

    if language_code is not None:
        file_name += f".{language_code}"

    if subtitles_type is not None:
        file_name += f".{subtitles_type.value.lower()}"

    sanitized_basename = sanitize_path_segment(file_name)

    if file_format is not None:
        if isinstance(file_format, SubtitlesFormatType):
            file_format_str = file_format.value.file_extension
        else:
            file_format_str = file_format.lstrip('.')

        return f"{sanitized_basename}.{file_format_str}"

    return sanitized_basename


@lru_cache
def format_subtitles_description(language_code: str | None = None, language_name: str | None = None,
                                 special_type: SubtitlesType | None = None) -> str:
    """
    Format a subtitles description using its attributes.

    Args:
        language_code (str | None, optional): Language code. Defaults to None.
        language_name (str | None, optional): Language name. Defaults to None.
        special_type (SubtitlesType | None, optional): Subtitles type. Defaults to None.

    Returns:
        str: Formatted subtitles description.
    
    Raises:
        ValueError: If neither `language_code` nor `language_name` is provided.
    """
    if language_name and language_code:
        language_str = f"{language_name} ({language_code})"

    elif result := (language_name or language_code):
        language_str = result

    else:
        raise ValueError("Either 'language_code' or 'language_name' must be provided.")
    
    if special_type:
        language_str += f" [{special_type.value}]"

    return language_str


def get_model_field(model: BaseModel | None, field: str, convert_to_dict: bool = False, **kwargs: Any) -> Any:
    """
    Get a field from a Pydantic model.

    Args:
        model (BaseModel | None): A Pydantic model.
        field (str): Field name to retrieve.
        convert_to_dict (bool, optional): Whether to convert the field value to a dictionary. Defaults to False.
        **kwargs: Additional keyword arguments to pass to the serialization method (`model_dump`).
            Relevant only if `convert_to_dict` is True, and `field_value` is a Pydantic model.

    Returns:
        Any: The field value.
    """
    if model and hasattr(model, field):
        field_value = getattr(model, field)

        if convert_to_dict and hasattr(field_value, 'model_dump'):
            return field_value.model_dump(**kwargs)

        return field_value

    return None


def generate_media_folder_name(media_data: Movie | Episode, source: str | None = None, separator: str = ".") -> str:
    """
    Generate a folder name for media data.

    Args:
        media_data (Movie | Episode): A movie or episode data object.
        source (str | None, optional): Abbreviation of the source to use for file names. Defaults to None.
        separator (str, optional): A separator to use between words. Defaults to ".".

    Returns:
        str: A folder name for the media data.
    """
    if isinstance(media_data, Movie):
        folder_name = slugify_title(title=media_data.name, separator=separator)
        if media_data.release_date:
            release_year = media_data.release_date.year if isinstance(media_data.release_date, dt.datetime) \
                else media_data.release_date
            folder_name += f".{release_year}"
        if source:
            folder_name += f".{source}"

    else:  # Episode
        folder_name = slugify_title(title=media_data.series_name, separator=separator)
        if media_data.season_number is not None and media_data.episode_number is not None:
            folder_name += f".S{media_data.season_number:02}E{media_data.episode_number:02}"
        if source:
            folder_name += f".{source}"

    return sanitize_path_segment(folder_name)


def generate_non_conflicting_path(file_path: Path, has_extension: bool = True) -> Path:
    """
    Generate a non-conflicting path for a file.
    If the file already exists, a number will be added to the end of the file name.

    Args:
        file_path (Path): Path to a file.
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
            new_file_path = file_path.parent / f"{file_path.stem}-{i}{file_path.suffix}"

        else:
            new_file_path = file_path.parent / f"{file_path}-{i}"

        if not new_file_path.exists():
            return new_file_path

        i += 1




def merge_dict_values(*dictionaries: dict) -> dict:
    """
    A function for merging the values of multiple dictionaries using the same keys.
    If a key already exists, the value will be added to a list of values mapped to that key.

    Examples:
        merge_dict_values({'a': 1, 'b': 3}, {'a': 2, 'b': 4}) -> {'a': [1, 2], 'b': [3, 4]}
        merge_dict_values({'a': 1, 'b': 2}, {'a': 1, 'b': [2, 3]}) -> {'a': 1, 'b': [2, 3]}

    Note:
        This function support only merging of lists or single items (no tuples or other iterables),
        and without any nesting (lists within lists).

    Args:
        *dictionaries (dict): Dictionaries to merge.

    Returns:
        dict: A merged dictionary.
    """
    _dictionaries: list[dict] = [d for d in dictionaries if d]

    if len(_dictionaries) == 0:
        return {}

    if len(_dictionaries) == 1:
        return _dictionaries[0]

    result: dict = {}

    for _dict in _dictionaries:
        for key, value in _dict.items():
            if key in result:
                if isinstance(result[key], list):
                    if isinstance(value, list):
                        result[key].extend(value)
                    else:
                        result[key].append(value)
                else:
                    if isinstance(value, list):
                        result[key] = [result[key], *value]
                    else:
                        result[key] = [result[key], value]
            else:
                result[key] = value

    return result


def raise_for_status(response: httpx.Response) -> None:
    """
    Raise an exception if the response status code is invalid.
    Uses 'response.raise_for_status()' internally, with additional logging.

    Args:
        response (httpx.Response): A response object.
    """
    truncation_threshold = 1500

    if not response.is_error:
        return

    if len(response.text) > truncation_threshold:
        # Truncate the response as in some cases there could be an unexpected long HTML response
        response_text = response.text[:truncation_threshold].rstrip() + " <TRUNCATED...>"

    else:
        response_text = response.text

    logger.debug(f"Response status code: {response.status_code}")

    if response.headers.get('Content-Type'):
        logger.debug(f"Response type: {response.headers['Content-Type']}")

    logger.debug(f"Response text: {response_text}")

    response.raise_for_status()


def parse_url_params(url_params: str) -> dict:
    """
    Parse GET parameters from a URL to a dictionary.

    Args:
        url_params (str): URL parameters. (e.g. 'param1=value1&param2=value2')

    Returns:
        dict: A dictionary containing the URL parameters.
    """
    url_params = url_params.split('?')[-1].rstrip('&')
    params_list = url_params.split('&')

    if len(params_list) == 0 or \
            (len(params_list) == 1 and '=' not in params_list[0]):
        return {}

    return {key: value for key, value in (param.split('=') for param in params_list)}


@overload
def return_first_valid(*values: T | None, raise_error: Literal[True] = ...) -> T:
    ...


@overload
def return_first_valid(*values: T | None, raise_error: Literal[False] = ...) -> T | None:
    ...


def return_first_valid(*values: T | None, raise_error: bool = False) -> T | None:
    """
    Return the first non-None value from a list of values.

    Args:
        *values (T): Values to check.
        raise_error (bool, optional): Whether to raise an error if all values are None. Defaults to False.

    Returns:
        T | None: The first non-None value, or None if all values are None and `raise_error` is False.

    Raises:
        ValueError: If all values are None and `raise_error` is True.
    """
    for value in values:
        if value is not None:
            return value

    if raise_error:
        raise ValueError("No valid value found.")

    return None

def single_string_to_list(item: str | list[str]) -> list[str]:
    """
    Convert a single string to a list containing the string.
    If None is passed, an empty list will be returned.

    Args:
        item (str | list[str]): A string or a list of strings.

    Returns:
        list[str]: A list containing the string, or an empty list if None was passed.
    """
    if item is None:
        return []

    if isinstance(item, list):
        return item

    return [item]


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


_REMOVED_CHARS_SLUG = str.maketrans("", "", '<>():"?*')
_REMOVED_CHARS_FS = str.maketrans("", "", '<>:"/\\|?*')
_REPLACE_WITH_SEPARATOR = [" - ", " & ", ",", ":", "|", "/", " "]


@lru_cache
def slugify_title(title: str, separator: str = " ") -> str:
    """
    Normalize a title into a slug-like string for creating name components.
    This function is for normalization, not for filesystem safety.

    Args:
        title (str): A media title.
        separator (str, optional): A separator to use between words. Defaults to " ".

    Returns:
        str: A slugified title.
    """
    title = title.strip()
    title = title.replace("…", "...")

    # Replace multi-character sequences first
    for item in _REPLACE_WITH_SEPARATOR:
        if separator == " " and item in (" & ", " - "):
            continue
        if item == " & ":
            title = title.replace(item, f"{separator}&{separator}")
        else:
            title = title.replace(item, separator)

    # Remove invalid characters for a slug
    title = title.translate(_REMOVED_CHARS_SLUG)

    # Replace multiple separators with a single one
    if separator:
        title = re.sub(f"[{re.escape(separator)}]+", separator, title)

    return title


@lru_cache
def sanitize_path_segment(segment: str, platform: str | None = None) -> str:
    """
    Sanitize a file or directory name (path segment) for a given OS.

    Args:
        segment (str): The path segment to sanitize (file or directory name).
        platform (str | None, optional): Target platform ('win32', 'linux', 'darwin'). 
            Defaults to 'sys.platform' (current platform).

    Returns:
        str: A sanitized path segment safe for use on the target filesystem.
    """
    if platform is None:
        platform = sys.platform

    # Remove characters illegal on all filesystems
    segment = segment.translate(_REMOVED_CHARS_FS)

    if platform == "win32":
        # On Windows, remove trailing dots and spaces
        segment = segment.rstrip(". ")

        # Handle reserved device names (match first segment before dot)
        base_name, _, _ = segment.partition('.')
        if base_name.upper() in WINDOWS_RESERVED_FILE_NAMES:
            segment = f"_{segment}"

    # Ensure the segment is not empty
    if not segment:
        return "_"

    return segment
