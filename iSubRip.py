#!/usr/bin/env python3

## ------------- iSubRip --------------
##  Made By: Michael Yochpaz (C) 2020
##  https://github.com/MichaelYochpaz/iSubRip
##  Version: 1.0
##  License: GPLv3
##
## ----------- Description ------------
## - This script scrapes subtitles off of iTunes movies using a URL of the movie.
##
## ------------ Requirments -----------
## - FFmpeg is required for this script to work. If FFmpeg is not in PATH, enter FFmpeg's path in "FFMPEG_PATH"
##
## --------------- Usage --------------
## - iSubRip <iTunes movie URL>

import sys
import os
import subprocess
import tempfile
import shutil
import json
import requests
from bs4 import BeautifulSoup
import m3u8

#---------------| Settings |---------------
DOWNLOAD_FILTER = [] # - Download specific langauges. Use either a language name or a country code. Leave empty to download all available subtitles.
DOWNLOAD_FOLDER = "" # - Path to download subtitles to. Leave empty to save to current directory.
FFMPEG_PATH = "ffmpeg" # - Leave as "ffmpeg" if FFmpeg is in PATH. If not, change value to FFmpeg's path.
FFMPEG_ARGUMENTS = "-loglevel warning -hide_banner" # - Arguments to run FFmpeg with.
#------------------------------------------

def main():
    global DOWNLOAD_FILTER, DOWNLOAD_FOLDER

    if len(sys.argv) == 1: # No arguments given
        print_usage()
        sys.exit(0)


    if shutil.which(FFMPEG_PATH) == None: # FFmpeg is not installed or not in PATH
        raise SystemExit(f"FFmpeg installation could not be found.\nFFmpeg is required for using this script.")


    if not os.path.exists(DOWNLOAD_FOLDER): # If the folder that was set to save to does not exist
        if DOWNLOAD_FOLDER == "":
            DOWNLOAD_FOLDER = os.getcwd()

        else:
            raise SystemExit(f"Folder {DOWNLOAD_FOLDER} not found.")
    
    if "itunes.apple.com" in sys.argv[1] and "/movie/" in sys.argv[1]: # Make sure the given URL is valid
        url = sys.argv[1]
        get_subtitles(url)

    else:
        raise SystemExit(f"Unsupported / Invalid URL.")


    if DOWNLOAD_FOLDER[-1:] == '/': # Remove last char from from user's folder input if it's '/'
        DOWNLOAD_FOLDER = DOWNLOAD_FOLDER[:-1]


def get_subtitles(url: str):
    try:
        print(f'Scarping {url}')
        page = BeautifulSoup(requests.get(url).text, "lxml")
        data = json.loads(page.find('script', type='application/ld+json').contents[0]) # Scrape a dictionary on the webpage that contains movie metdata.

        type = data['@type']
        title = data['name']

        if type == "Movie":
            print(f'Found Movie: "{title}"')

        page_script = page.find(id="shoebox-ember-data-store")
        page_script_dict = json.loads(page_script.renderContents()) 

    except:
        print("Could not load " + url)
        exit(1)
    
    for item in page_script_dict["included"]:
        if "assets" in item["attributes"]:
            playlist = m3u8.load(item["attributes"]["assets"][0]["hlsUrl"])
            break

    subtitles_playlists = []

    for p in playlist.media:
        if p.type == "SUBTITLES" and p.group_id == "subtitles_ak" and (len(DOWNLOAD_FILTER) == 0 or p.language in DOWNLOAD_FILTER or p.name in DOWNLOAD_FILTER):  # group_id can be either "subtitles_ak" or "subtitles_ap3"
            is_forced = (p.forced == "YES")
            subtitles_playlists.append((p.uri, p.language, is_forced))

    if len(subtitles_playlists) == 0: # No matching subtitles found
        print("No subtitles matching the filter were found.")

    elif len(subtitles_playlists) == 1: # One matching subtitles file found
        ffmpeg_command = f'{FFMPEG_PATH} {FFMPEG_ARGUMENTS} -i "{subtitles_playlists[0][0]}" "{DOWNLOAD_FOLDER}/{format_file_name(title, subtitles_playlists[0][1], subtitles_playlists[0][2])}"'
        subprocess.call(ffmpeg_command, shell=False, stderr=subprocess.DEVNULL)

    else: # Multiple matching subtitles files found
        temp_dir = tempfile.mkdtemp(dir=tempfile.gettempdir()) # Create a temporary folder to download subtitles files to
        processes = []
        for p in subtitles_playlists:
            ffmpeg_command = f'{FFMPEG_PATH} {FFMPEG_ARGUMENTS} -i "{p[0]}" "{temp_dir}/{format_file_name(title, p[1], p[2])}"'
            processes.append(subprocess.Popen(ffmpeg_command, shell=False, stderr=subprocess.DEVNULL))

        is_finished = False

        while not is_finished: # Loop runs until all subtitle downloading subprocesses are done
            is_finished = True
            for p in processes:
                if p.poll() is None:
                    is_finished = False

        shutil.make_archive(f"{DOWNLOAD_FOLDER}/{format_zip_name(title)}", 'zip', temp_dir) # Create a zip file
        shutil.rmtree(temp_dir) # Temporary directory cleanup

    print("Subtitles downloaded successfully.")


def format_file_name(title: str, language_code: str, is_forced: bool):
    if is_forced:
        return f"{title.replace(': ', '.').replace(' - ', '-').replace('. ', '.').replace(' ', '.')}.iT.WEB.{language_code}.forced.vtt"

    else:
        return f"{title.replace(': ', '.').replace(' - ', '-').replace('. ', '.').replace(' ', '.')}.iT.WEB.{language_code}.vtt"


def format_zip_name(title: str):
    return f"{title.replace(': ', '.').replace(' - ', '-').replace('. ', '.').replace(' ', '.')}.iT.WEB"


def print_usage():
    print(f"Usage: {sys.argv[0]} <iTunes movie URL>")


if __name__ == "__main__":
    main()