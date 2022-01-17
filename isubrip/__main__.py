import sys
from typing import Union, Any
import os
import tomli
from xdg import xdg_config_home
from mergedeep import merge

from scraper import iSubRip
from playlist_downloader import PlaylistDownloader
from utils.enums import SubtitlesType, SubtitlesFormat


def parse_config(user_config_path: Union[str, None] = None) -> dict[str, Any]:
    """Parse and config file and save settings to a dictionary.

    Args:
        user_config (str, optional): Path to an additional optional config to use for overwriting default settings. Defaults to None.

    Returns:
        dict: A dictionary containing all settings.
    """    
    # Load settings from default config file
    with open ("isubrip/default_config.toml", "r") as config_file:
        config: Union[dict[str, Any], None] = tomli.loads(config_file.read())

    config["user-config"] = False

    # If a user config file exists, load it and update default config with it's values
    if(user_config_path != None):
        # User config file could not be found
        if not os.path.isfile(user_config_path):
            raise FileNotFoundError(f"Error: Config file \"{user_config_path}\" could not be found.")
            
        with open (user_config_path, "r") as config_file:
            user_config: Union[dict[str, Any], None] = tomli.loads(config_file.read())

        # Change config["ffmpeg"]["args"] value to None if empty
        if config["ffmpeg"]["args"] == "":
            config["ffmpeg"]["args"] = None

        # Merge user_config with the default config, and override existing config values with values from user_config
        merge(config, user_config)
        config["user-config"] = True

    return config


def find_config_file() -> Union[str, None]:
    config_path = None

    # Windows
    if sys.platform == "win32":
        config_path = f"{os.getenv('appdata')}\\iSubRip\\config.toml"

    # Linux
    elif sys.platform == "linux":
        config_path = f"{xdg_config_home().resolve()}/iSubRip/config.toml"
    
    # MacOS
    elif sys.platform == "darwin":
        config_path = r"~/Library/Application Support/isubrip/config.toml"

    if (config_path != None) and (os.path.exists(config_path)):
        return config_path
    
    return None


def main() -> None:
    config: dict[str, Any] = parse_config(find_config_file())

    # Invalid amount of arguments
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(0)

    # Remove last char from from user's folder input if it's '/'
    if config["downloads"]["folder"][-1:] == '/': 
        config["downloads"]["folder"] = config["downloads"]["folder"][:-1]

    playlist_downloader: Union[PlaylistDownloader, None] = None
    # Check and print and exit if an error is raised during object creation
    try:
        playlist_downloader = PlaylistDownloader(config["downloads"]["folder"], config["ffmpeg"]["path"], config["ffmpeg"]["args"])

    except Exception as e:
        print(f"Error: {e}")
        exit(1)

    for url in sys.argv[1:]:
        try:
            print(f"Scraping {url}...")
            movie_data = iSubRip.find_m3u8_playlist(url, config["downloads"]["user-agent"])

            if movie_data.playlist == None:
                print(f"Error: Main m3u8 playlist for \"{movie_data.name}\" could not be found / downloaded.")
                continue
            
            print(f"Found movie \"{movie_data.name}\".")

            for subtitles in iSubRip.find_matching_subtitles(movie_data.playlist, config["downloads"]["filter"]):
                subtitles_type_str = ('[' + subtitles.subtitles_type.name + ']') if (subtitles.subtitles_type != SubtitlesType.NORMAL) else ''

                print(f"Found \"{subtitles.language_name}\" ({subtitles.language_code}) " + subtitles_type_str + f"subtitles. Downloading...")
                file_name = format_file_name(movie_data.name, subtitles.language_code, subtitles.subtitles_type)

                # Download subtitles
                playlist_downloader.download_subtitles(subtitles.playlist_url, file_name, SubtitlesFormat.VTT)

            print(f"All matching subtitles for {movie_data.name} downloaded.")

        except Exception as e:
            print(f"Error: {e}\nSkipping...")
            continue


def format_title(title: str) -> str:
        return title.replace(': ', '.').replace(' - ', '-').replace(', ', '.').replace('. ', '.').replace(' ', '.').replace('(', '').replace(')', '').replace('&amp;', '&')


def format_file_name(title: str, language_code: str, type: SubtitlesType) -> str:
    file_name = f"{format_title(title)}.iT.WEB.{language_code}"

    if type is not SubtitlesType.NORMAL:
        file_name += '.' + type.name

    return file_name


def format_zip_name(title: str) -> str: 
    return f"{format_title(title)}.iT.WEB"


def print_usage() -> None:
    print(f"Usage: {sys.argv[0]} <iTunes movie URL>")


if __name__ == "__main__":
    main()