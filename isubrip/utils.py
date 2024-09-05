from __future__ import annotations

from abc import ABCMeta
import datetime as dt
from functools import lru_cache
from pathlib import Path
import re
import secrets
import shutil
import sys
from typing import TYPE_CHECKING, Any, Literal, Type, overload

from isubrip.constants import TEMP_FOLDER_PATH, TITLE_REPLACEMENT_STRINGS, WINDOWS_RESERVED_FILE_NAMES
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


class TempDirGenerator:
    """A class for generating temporary directories, and disposing them once the object is destroyed."""
    _generated_temp_directories: list[Path] = []

    def __exit__(self, exc_type: Type[BaseException] | None,
                 exc_val: BaseException | None, exc_tb: TracebackType | None) -> None:
        self.cleanup()

    @classmethod
    def generate(cls, directory_name: str | None = None) -> Path:
        """
        Generate a temporary directory within 'TEMP_FOLDER_PATH'.

        Args:
            directory_name (str | None, optional): Name of the directory to generate.
                If not specified, a random string will be generated. Defaults to None.

        Returns:
            Path: Path to the generated directory.
        """
        directory_name = directory_name or secrets.token_hex(5)
        full_path = TEMP_FOLDER_PATH / directory_name

        if full_path.is_dir():
            if full_path in cls._generated_temp_directories:  # Generated by this class
                logger.debug(f"Using previously generated temporary directory: '{full_path}'.")
                return full_path

            logger.debug(f"Temporary directory '{full_path}' already exists. "
                         f"Emptying the directory from all contents...")
            shutil.rmtree(full_path)
            full_path.mkdir(parents=True)

        else:
            full_path.mkdir(parents=True)
            logger.debug(f"Temporary directory has been generated: '{full_path}'")

        cls._generated_temp_directories.append(full_path)
        return full_path

    @classmethod
    def cleanup(cls) -> None:
        """Remove all temporary directories generated by this object."""
        for temp_directory in cls._generated_temp_directories:
            logger.debug(f"Removing temporary directory: '{temp_directory}'")

            try:
                shutil.rmtree(temp_directory)

            except Exception as e:
                logger.debug(f"Failed to remove temporary directory '{temp_directory}': {e}")

        cls._generated_temp_directories = []


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
    validation_errors = exc.errors()
    error_str = ""

    for validation_error in validation_errors:
        value: Any = validation_error['input']
        value_type: str = type(value).__name__
        location: list[str] = [str(item) for item in validation_error["loc"]]
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

        error_str += f"'{location_str}' (value: '{value}', type: '{value_type}'): {error_msg}\n"

    return error_str


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
        description_str = f"{media_data.name} [{release_year}]"

        if media_data.id:
            description_str += f" (ID: {media_data.id})"

        return description_str

    if isinstance(media_data, Series):
        description_str = f"{media_data.series_name}"

        if media_data.series_release_date:
            if isinstance(media_data.series_release_date, dt.datetime):
                description_str += f" [{media_data.series_release_date.year}]"

            else:
                description_str += f" [{media_data.series_release_date}]"

        if media_data.id:
            description_str += f" (ID: {media_data.id})"

        return description_str

    if isinstance(media_data, Season):
        if shortened:
            description_str = f"Season {media_data.season_number:02d}"

        else:
            description_str = f"{media_data.series_name} - Season {media_data.season_number:02d}"

        if media_data.season_name:
            description_str += f" - {media_data.season_name}"

        if media_data.id:
            description_str += f" (ID: {media_data.id})"

        return description_str

    if isinstance(media_data, Episode):
        if shortened:
            description_str = f"S{media_data.season_number:02d}E{media_data.episode_number:02d}"

        else:
            description_str = (f"{media_data.series_name} - "
                               f"S{media_data.season_number:02d}E{media_data.episode_number:02d}")

        if media_data.episode_name:
            description_str += f" - {media_data.episode_name}"

        if media_data.id:
            description_str += f" (ID: {media_data.id})"

        return description_str

    raise ValueError(f"Unsupported media type: '{type(media_data)}'")


@lru_cache
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
        file_format (SubtitlesFormat | str | None, optional): File format to use.  Defaults to None.

    Returns:
        str: Generated file name.
    """
    file_name = standardize_title(title).rstrip('.')

    if release_date is not None:
        if isinstance(release_date, dt.datetime):
            release_year = release_date.year

        else:
            release_year = release_date

        file_name += f".{release_year}"

    if season_number is not None and episode_number is not None:
        file_name += f".S{season_number:02}E{episode_number:02}"

    if episode_name is not None:
        file_name += f".{standardize_title(episode_name).rstrip('.')}"

    if media_source is not None:
        file_name += f".{media_source}"

    if source_type is not None:
        file_name += f".{source_type}"

    if additional_info is not None:
        if isinstance(additional_info, (list, tuple)):
            additional_info = '.'.join(additional_info)

        file_name += f".{additional_info}"

    if language_code is not None:
        file_name += f".{language_code}"

    if subtitles_type is not None:
        file_name += f".{subtitles_type.value.lower()}"

    if file_format is not None:
        if isinstance(file_format, SubtitlesFormatType):
            file_format = file_format.value.file_extension

        file_name += f".{file_format}"

    return file_name


def format_subtitles_description(language_code: str, language_name: str | None = None,
                                 special_type: SubtitlesType | None = None) -> str:
    if language_name:
        language_str = f"{language_name} ({language_code})"

    else:
        language_str = language_code

    if special_type:
        language_str += f" [{special_type.value}]"

    return language_str


def get_model_field(model: BaseModel | None, field: str, convert_to_dict: bool = False) -> Any:
    """
    Get a field from a Pydantic model.

    Args:
        model (BaseModel | None): A Pydantic model.
        field (str): Field name to retrieve.
        convert_to_dict (bool, optional): Whether to convert the field value to a dictionary. Defaults to False.

    Returns:
        Any: The field value.
    """
    if model and hasattr(model, field):
        field_value = getattr(model, field)

        if convert_to_dict:
            return field_value.dict()

        return field_value

    return None


def generate_media_folder_name(media_data: Movie | Episode, source: str | None = None) -> str:
    """
    Generate a folder name for media data.

    Args:
        media_data (Movie | Episode): A movie or episode data object.
        source (str | None, optional): Abbreviation of the source to use for file names. Defaults to None.

    Returns:
        str: A folder name for the media data.
    """
    if isinstance(media_data, Movie):
        return format_release_name(
            title=media_data.name,
            release_date=media_data.release_date,
            media_source=source,
        )

    # elif isinstance(media_data, Episode):
    return format_release_name(
        title=media_data.series_name,
        season_number=media_data.season_number,
        episode_number=media_data.episode_number,
        media_source=source,
    )


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


def generate_temp_media_path(media_data: Movie | Episode, source: str | None = None) -> Path:
    """
    Generate a temporary directory for downloading media data.

    Args:
        media_data (Movie | Episode): A movie or episode data object.
        source (str | None, optional): Abbreviation of the source to use for file names. Defaults to None.

    Returns:
        Path: A path to the temporary folder.
    """
    temp_folder_name = generate_media_folder_name(media_data=media_data, source=source)
    path = generate_non_conflicting_path(file_path=TEMP_FOLDER_PATH / temp_folder_name, has_extension=False)

    return TempDirGenerator.generate(directory_name=path.name)


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


def normalize_config_name(name: str) -> str:
    """
    Normalize a config category / field name (used for creating an alias).

    Args:
        name (str): The name to normalize.

    Returns:
        str: The normalized name.
    """
    return name.lower().replace('_', '-')


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


@lru_cache
def standardize_title(title: str) -> str:
    """
    Format movie title to a standardized title that can be used as a file name.

    Args:
        title (str): A movie title.

    Returns:
        str: The movie title, in a file-name-friendly format.
    """
    title = title.strip()

    for string, replacement_string in TITLE_REPLACEMENT_STRINGS.items():
        title = title.replace(string, replacement_string)

    title = re.sub(r"\.+", ".", title)  # Replace multiple dots with a single dot

    # If running on Windows, rename Windows reserved names to allow file creation
    if sys.platform == 'win32':
        split_title = title.split('.')

        if split_title[0].upper() in WINDOWS_RESERVED_FILE_NAMES:
            if len(split_title) > 1:
                return split_title[0] + split_title[1] + '.'.join(split_title[2:])

            if len(split_title) == 1:
                return "_" + title

    return title
