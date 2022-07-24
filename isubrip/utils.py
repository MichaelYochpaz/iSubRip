import re

from os import PathLike
from typing import Union

from isubrip.config import Config


def format_title(title: str) -> str:
    """Format movie title to a standardized title that can be used as a file name.

    Args:
        title (str): An iTunes movie title.

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
