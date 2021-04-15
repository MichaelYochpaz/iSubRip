#!/usr/bin/env python3

## -------------- iSubRip ---------------------------
##  GitHub: https://github.com/MichaelYochpaz/iSubRip
##  Version: 1.0.2
## --------------------------------------------------

import sys
import os
import subprocess
import tempfile
import shutil
import json
import requests
from bs4 import BeautifulSoup
import m3u8

# -------------------------| Settings |-------------------------
DOWNLOAD_FILTER = [] # A list of subtitle languages to download. Only iTunes language codes names can be used. Leave empty to download all available subtitles.
DOWNLOAD_FOLDER = r"" # Folder to save subtitle files to. Leave empty to use current working directory.
FFMPEG_PATH = "ffmpeg" # FFmpeg's location. Use default "ffmpeg" value if FFmpeg is in PATH.
FFMPEG_ARGUMENTS = "-loglevel warning -hide_banner" # Arguments to run FFmpeg with.
HEADERS = {"User-Agent" : "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.72 Safari/537.36"} # Session headers to run scraper with.
# --------------------------------------------------------------

def main():
    global DOWNLOAD_FILTER, DOWNLOAD_FOLDER
    # Convert DOWNLOAD_FILTER to lower case to make filter case-insensitive
    DOWNLOAD_FILTER = [item.lower() for item in DOWNLOAD_FILTER]

    # Invalid amount of arguments
    if len(sys.argv) != 2:
        print_usage()
        sys.exit(0)

    # FFmpeg is not installed or not in PATH
    if shutil.which(FFMPEG_PATH) == None:
        raise SystemExit(f"FFmpeg installation could not be found.\nFFmpeg is required for using this script.")

    # If no "DOWNLOAD_FOLDER" was set and if folder path is valid.
    if not os.path.exists(DOWNLOAD_FOLDER):
        if DOWNLOAD_FOLDER == "":
            DOWNLOAD_FOLDER = os.getcwd()

        else:
            raise SystemExit(f"Folder {DOWNLOAD_FOLDER} not found.")

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
        raise SystemExit(f"Unsupported / Invalid URL.")


def get_subtitles(url: str):
    try:
        print(f'Scarping {url}')
        page = BeautifulSoup(requests.session().get(url, headers=HEADERS).text, "lxml")
        
        # A dictionary on the webpage that contains metdata.
        data = json.loads(page.find('script', type='application/ld+json').contents[0])
        type = data['@type']
        title = data['name']

        if type == "Movie":
            print(f'Found Movie: "{title}"')

        page_script = page.find(id="shoebox-ember-data-store")
        page_script_dict = json.loads(page_script.renderContents())

        # Cleanup
        del page
        del data

    except Exception as e:
        print(e)
        return False

    found = False
    for item in page_script_dict[next(iter(page_script_dict))]["included"]:
        if "assets" in item["attributes"]:
            try:
                playlist = m3u8.load(item["attributes"]["assets"][0]["hlsUrl"])
                found = True
                break

            except:
                continue
        
    if not found:
        return False   

    subtitles_playlists = []

    for p in playlist.media:
        if p.type == "SUBTITLES" and p.group_id == "subtitles_ak" and (len(DOWNLOAD_FILTER) == 0 or p.language in DOWNLOAD_FILTER or p.name.lower() in DOWNLOAD_FILTER):  # group_id can be either "subtitles_ak" or "subtitles_ap3"
            is_forced = (p.forced == "YES")
            subtitles_playlists.append((p.uri, p.language, is_forced))

    # No matching subtitle files found
    if len(subtitles_playlists) == 0: 
        print("No subtitles matching the filter were found.")
        return False

    # One matching subtitle files found
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


def format_title(title: str):
        return title.replace(': ', '.').replace(' - ', '-').replace(', ', '.').replace('. ', '.').replace(' ', '.').replace('(', '').replace(')', '').replace('&amp;', '&')


def format_file_name(title: str, language_code: str, is_forced: bool):
        return f"{format_title(title)}.iT.WEB.{language_code}{'.forced' if is_forced else ''}.vtt"


def format_zip_name(title: str):
    return f"{format_title(title)}.iT.WEB"


def print_usage():
    print(f"Usage: {sys.argv[0]} <iTunes movie URL>")


if __name__ == "__main__":
    main()
