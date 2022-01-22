import sys
from typing import Any

import isubrip.utils as utils
from isubrip.scraper import iSubRip
from isubrip.playlist_downloader import PlaylistDownloader
from isubrip.types import SubtitlesType, SubtitlesFormat
from isubrip.exceptions import InvalidConfigValue

def main() -> None:
    config: dict[str, Any] = utils.parse_config(utils.find_config_file())

    # Invalid amount of arguments
    if len(sys.argv) < 2:
        print_usage()
        exit(0)

    # Remove last char from from user's folder input if it's '/'
    if config["downloads"]["folder"][-1:] == '/': 
        config["downloads"]["folder"] = config["downloads"]["folder"][:-1]

    # Check and print and exit if an error is raised during object creation
    try:
        playlist_downloader = PlaylistDownloader(config["downloads"]["folder"], config["ffmpeg"]["path"], config["ffmpeg"]["args"])

    except Exception as e:
        print(f"Error: {e}")
        exit(1)

    for url in sys.argv[1:]:
        try:
            print(f"\nScraping {url}...")
            movie_data = iSubRip.find_m3u8_playlist(url, config["downloads"]["user-agent"])
            print(f"Found movie \"{movie_data.name}\".")


            if movie_data.playlist == None:
                print(f"Error: Main m3u8 playlist could not be found / downloaded.")
                continue
            
            downloaded_subtitles = 0

            for subtitles in iSubRip.find_matching_subtitles(movie_data.playlist, config["downloads"]["filter"]):
                subtitles_type_str = (' [' + subtitles.subtitles_type.name.lower() + ']') if (subtitles.subtitles_type != SubtitlesType.NORMAL) else ''

                print(f"Found \"{subtitles.language_name}\" ({subtitles.language_code})" + subtitles_type_str + f" subtitles. Downloading...")
                file_name = utils.format_file_name(movie_data.name, subtitles.language_code, subtitles.subtitles_type)

                # Download subtitles
                playlist_downloader.download_subtitles(subtitles.playlist_url, file_name, SubtitlesFormat.VTT)
                downloaded_subtitles += 1

            print(f"{downloaded_subtitles} matching subtitles for \"{movie_data.name}\" were found and downloaded.")

        except Exception as e:
            print(f"Error: {e}\nSkipping...")
            continue


def print_usage() -> None:
    """Print usage information."""
    print(f"Usage: {sys.argv[0]} <iTunes movie URL>")


if __name__ == "__main__":
    main()