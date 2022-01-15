#!/usr/bin/env python3

## -------------- iSubRip ---------------------------
##  GitHub: https://github.com/MichaelYochpaz/iSubRip
##  Version: 1.0.6
## --------------------------------------------------

import sys
import os
import tempfile
import tomli
import html
import json
import m3u8
import subprocess
import shutil
from enum import Enum
from xdg import xdg_config_home
from mergedeep import merge
from requests.sessions import session
from requests.exceptions import ConnectionError
from bs4 import BeautifulSoup

class subtitles_type(Enum):
    none = 1
    cc = 2
    forced = 3

def parse_config() -> dict:
    # Load settings from default config file
    with open ("default_config.toml", "r") as config_file:
        config = tomli.loads(config_file.read())

    user_config = find_config_file()
    config["user-config"] = False

    # If a user config file exists, load it and update default config with it's values
    if(user_config != None):
        with open (user_config, "r") as config_file:
            user_config = tomli.loads(config_file.read())

        # The function merges user_config with the default config, and overrides existing config values with values from user_config
        merge(config, user_config)
        config["user-config"] = True

    # Convert all language codes to lower case
    for i in range(len(config["downloads"]["filter"])):
        config["downloads"]["filter"][i] = config["downloads"]["filter"][i].lower()

    return config


def find_config_file() -> str:
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
    global config
    config = parse_config()

    # Invalid amount of arguments
    if len(sys.argv) != 2:
        print_usage()
        sys.exit(0)

    # If FFmpeg is not installed or not set in PATH
    if shutil.which(config["ffmpeg"]["path"]) == None:
        raise SystemExit(f"Error: FFmpeg installation could not be found.\nFFmpeg is required for using this script.")

    # If downloads folder does not exist
    if not os.path.exists(config["downloads"]["folder"]):
        raise SystemExit(f"Error: Folder \"{config['downloads']['folder']}\" could not be found.")

    # Remove last char from from user's folder input if it's '/'
    if config["downloads"]["folder"][-1:] == '/': 
        config["downloads"]["folder"] = config["downloads"]["folder"][:-1]
    
    # Check if the URL is valid
    if "itunes.apple.com" in sys.argv[1] and "/movie/" in sys.argv[1]: 
        url = sys.argv[1]
        if get_subtitles(url):
            print("Subtitles downloaded successfully.")

        else:
            print("Download failed.")

    else:
        raise SystemExit(f"Error: Unsupported / Invalid URL.")


def get_subtitles(url: str) -> bool:
    try:
        print(f'Scarping {url}')
        site_page = BeautifulSoup(session().get(url, headers={"User-Agent" : config["downloads"]["useragent"]}).text, "lxml")
        
        # Scrape a dictionary on the webpage that contains metdata about the movie
        head_data = site_page.find("head").find("script", attrs={"name": "schema:movie", "type": 'application/ld+json'} )

        if head_data == None:
            print("Error: The page did not load properly.\n" +
            "Try running the script again in a few seconds / minutes.")
            return False
        
        # Convert to dictionary structure
        head_data_dict = json.loads(head_data.contents[0])
        type = head_data_dict['@type']
        title = html.unescape(head_data_dict['name'])

        if type == "Movie":
            print(f'Found Movie: "{title}"')

        # Scrape a dictionary on the webpage that contains playlists data
        playlists_data = site_page.find("script", attrs={"id": "shoebox-ember-data-store", "type": "fastboot/shoebox"})

        if playlists_data == None:
            print("Error: Playlists data could not be found.")
            return False

        # Convert to dictionary structure
        playlists_data_dict = json.loads(playlists_data.renderContents())

        # Memory cleanup
        del site_page, head_data, head_data_dict

    except ConnectionError:
        print("Error: A connection error has occurred.\n" +
        "Try running the script again in a few seconds / minutes.")
        return False

    playlist = None

    for item in playlists_data_dict[next(iter(playlists_data_dict))]["included"]:
        if "assets" in item["attributes"] and "hlsUrl" in item["attributes"]["assets"][0]:
            m3u8_url = item["attributes"]["assets"][0]["hlsUrl"]
            try:
                playlist = m3u8.load(m3u8_url)

            except Exception:
                continue

            # Check if the first playlist found matches the movie that's being scraped (If not, it usually means that then movie isn't available yet)
            if is_playlist_valid(title, playlist):
                break

            else:
                print("Error: Couldn't find a valid playlist for the movie.")
                return False

    if playlist is None:
        print("Error: Couldn't find any playlists.\n" + 
        "Try running the script again in a few seconds / minutes.")
        return False

    subtitles_playlists = []

    for p in playlist.media:
        # "group_id" can be either ["subtitles_ak" / "subtitles_vod-ak-amt.tv.apple.com"] or ["subtitles_ap2" / "subtitles_ap3" / "subtitles_vod-ap-amt.tv.apple.com" / "subtitles_vod-ap1-amt.tv.apple.com" / "subtitles_vod-ap3-amt.tv.apple.com"]
        if p.type == "SUBTITLES" and (p.group_id == "subtitles_ak" or p.group_id == "subtitles_vod-ak-amt.tv.apple.com") and (len(config["downloads"]["filter"]) == 0 or p.language.lower() in config["downloads"]["filter"] or p.name.lower() in config["downloads"]["filter"]): 
            if (p.characteristics != None and "public.accessibility" in p.characteristics):
                sub_type = subtitles_type.cc

            elif (p.forced == "YES"):
                sub_type = subtitles_type.forced

            else:
                sub_type = subtitles_type.none

            subtitles_playlists.append((p.uri, p.language, sub_type))

    # No matching subtitles files found
    if len(subtitles_playlists) == 0: 
        print("No subtitles matching the filter were found.")
        return False

    # One matching subtitles file found
    elif len(subtitles_playlists) == 1:
        ffmpeg_command = f'{config["ffmpeg"]["path"]} {config["ffmpeg"]["args"]} -i "{subtitles_playlists[0][0]}" "{config["downloads"]["folder"]}/{format_file_name(title, subtitles_playlists[0][1], subtitles_playlists[0][2])}"'
        subprocess.run(ffmpeg_command, shell=False)

    # Multiple matching subtitle files found
    else: 
        # Generate a temporary folder to download subtitle files to
        temp_dir = tempfile.mkdtemp(dir=tempfile.gettempdir())
        processes = []
        for p in subtitles_playlists:
            ffmpeg_command = f'{config["ffmpeg"]["path"]} {config["ffmpeg"]["args"]} -i "{p[0]}" "{temp_dir}/{format_file_name(title, p[1], p[2])}"'
            processes.append(subprocess.Popen(ffmpeg_command, shell=False))

        # Loop over all subprocesses and wait for them to finish
        for p in processes:
            p.communicate()

        # Create a zip file & cleanup temporary directory
        shutil.make_archive(f"{config['downloads']['folder']}/{format_zip_name(title)}", "zip", temp_dir) 
        shutil.rmtree(temp_dir)

    return True


def is_playlist_valid(title: str, playlist: m3u8.M3U8) -> bool:
    for sessionData in playlist.session_data:
        if sessionData.data_id == "com.apple.hls.title":
            return (title in sessionData.value or sessionData.value in title)


def format_title(title: str) -> str:
        return title.replace(': ', '.').replace(' - ', '-').replace(', ', '.').replace('. ', '.').replace(' ', '.').replace('(', '').replace(')', '').replace('&amp;', '&')


def format_file_name(title: str, language_code: str, type: subtitles_type) -> str:
        return f"{format_title(title)}.iT.WEB.{language_code}{('.' + type.name) if (type is not subtitles_type.none) else ''}.vtt"


def format_zip_name(title: str) -> str: 
    return f"{format_title(title)}.iT.WEB"


def print_usage() -> None:
    print(f"Usage: {sys.argv[0]} <iTunes movie URL>")


if __name__ == "__main__":
    main()