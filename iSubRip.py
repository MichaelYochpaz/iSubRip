#!/usr/bin/env python3

## -------------- iSubRip ---------------------------
##  GitHub: https://github.com/MichaelYochpaz/iSubRip
##  Version: 1.0.6
## --------------------------------------------------

import sys
import os
import subprocess
import tempfile
import shutil
import json
import m3u8
from requests.sessions import session
from requests.exceptions import ConnectionError
from enum import Enum
from bs4 import BeautifulSoup


# -------------------------| Settings |-------------------------
DOWNLOAD_FILTER = [] # A list of subtitle languages to download. Only iTunes language codes names can be used. Leave empty to download all available subtitles.
DOWNLOAD_FOLDER = r"" # Folder to save subtitle files to. Leave empty to use current working directory.
FFMPEG_PATH = "ffmpeg" # FFmpeg's location. Use default "ffmpeg" value if FFmpeg is in PATH.
FFMPEG_ARGUMENTS = "-loglevel warning -hide_banner" # Arguments to run FFmpeg with.
HEADERS = {"User-Agent" : "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"} # Session headers to run scraper with.
# --------------------------------------------------------------

class subtitles_type(Enum):
    none = 1
    cc = 2
    forced = 3


def main() -> None:
    global DOWNLOAD_FILTER, DOWNLOAD_FOLDER
    # Convert DOWNLOAD_FILTER to lower case to make filter case-insensitive
    DOWNLOAD_FILTER = [item.lower() for item in DOWNLOAD_FILTER]

    # Invalid amount of arguments
    if len(sys.argv) != 2:
        print_usage()
        sys.exit(0)

    # If FFmpeg is not installed or not set in PATH
    if shutil.which(FFMPEG_PATH) == None:
        raise SystemExit(f"Error: FFmpeg installation could not be found.\nFFmpeg is required for using this script.")

    # If no "DOWNLOAD_FOLDER" was set and if folder path is valid
    if not os.path.exists(DOWNLOAD_FOLDER):
        if DOWNLOAD_FOLDER == "":
            DOWNLOAD_FOLDER = os.getcwd()

        else:
            raise SystemExit(f"Error: Folder {DOWNLOAD_FOLDER} not found.")

    # Remove last char from from user's folder input if it's '/'
    if DOWNLOAD_FOLDER[-1:] == '/': 
        DOWNLOAD_FOLDER = DOWNLOAD_FOLDER[:-1]
    
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
        page = BeautifulSoup(session().get(url, headers=HEADERS).text, "lxml")
        
        # A dictionary on the webpage that contains metdata
        data = json.loads(page.find('script', type='application/ld+json').contents[0])
        type = data['@type']
        title = data['name']

        if type == "Movie":
            print(f'Found Movie: "{title}"')

        page_script = page.find(id="shoebox-ember-data-store")
        page_script_dict = json.loads(page_script.renderContents())

        # Memory cleanup
        del page, data

    except ConnectionError:
        print("Error: A connection error has occurred.\n" +
        "Try running the script again in a few seconds / minutes.")
        return False

    playlist = None

    for item in page_script_dict[next(iter(page_script_dict))]["included"]:
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
                print("Error: Couldn't find a valid playlist for the movie.\n"+
                "This usually means that the movie isn't available on iTunes yet.")
                return False

    if playlist is None:
        print("Error: Couldn't find any playlists. This could be a result of the site not being loaded properly." + 
        "\nTry running the script again in a few seconds / minutes.")
        return False

    subtitles_playlists = []

    for p in playlist.media:
        # "group_id" can be either ["subtitles_ak" / "subtitles_vod-ak-amt.tv.apple.com"] or ["subtitles_ap2" / "subtitles_ap3" / "subtitles_vod-ap-amt.tv.apple.com" / "subtitles_vod-ap1-amt.tv.apple.com" / "subtitles_vod-ap3-amt.tv.apple.com"]
        if p.type == "SUBTITLES" and (p.group_id == "subtitles_ak" or p.group_id == "subtitles_vod-ak-amt.tv.apple.com") and (len(DOWNLOAD_FILTER) == 0 or p.language.lower() in DOWNLOAD_FILTER or p.name.lower() in DOWNLOAD_FILTER): 
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
        ffmpeg_command = f'{FFMPEG_PATH} {FFMPEG_ARGUMENTS} -i "{subtitles_playlists[0][0]}" "{DOWNLOAD_FOLDER}/{format_file_name(title, subtitles_playlists[0][1], subtitles_playlists[0][2])}"'
        subprocess.call(ffmpeg_command, shell=False)

    # Multiple matching subtitle files found
    else: 
        # Generate a temporary folder to download subtitle files to
        temp_dir = tempfile.mkdtemp(dir=tempfile.gettempdir())
        processes = []
        for p in subtitles_playlists:
            ffmpeg_command = f'{FFMPEG_PATH} {FFMPEG_ARGUMENTS} -i "{p[0]}" "{temp_dir}/{format_file_name(title, p[1], p[2])}"'
            processes.append(subprocess.Popen(ffmpeg_command, shell=False))

        # Loop over all subprocesses and wait for them to finish
        for p in processes:
            p.communicate()

        # Create a zip file & cleanup temporary directory
        shutil.make_archive(f"{DOWNLOAD_FOLDER}/{format_zip_name(title)}", "zip", temp_dir) 
        shutil.rmtree(temp_dir)

    return True


def is_playlist_valid(title: str, playlist: m3u8.M3U8) -> bool:
    for sessionData in playlist.session_data:
        if sessionData.data_id == "com.apple.hls.title":
            return (sessionData.value == title)


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