# iSubRip

A Python script to rip subtitles off of iTunes movies using an iTunes movie URL.


##  Requirements
* FFmpeg is required for this script to work. If FFmpeg is not in PATH, enter FFmpeg's executable path in `FFMPEG_PATH`.

## Configuration
* `DOWNLOAD_FILTER (Default: [])` - A list of specific languages to download.  
Use language codes (list can be found [here](https://gist.github.com/daFish/5990634)) or language names.  
Leave empty to download all of the available subtitles.  
Example: `['en', 'fr', 'es']`

* `DOWNLOAD_FOLDER (Default: "")` - Folder to save subtitles to. Leave empty to the folder the script is running from.  
Example: `"C:\Subtitles"`

* `FFMPEG_PATH (Default: "ffmpeg:")`- FFmpeg's location. Use default "ffmpeg" value if FFmpeg is in PATH.  
Example: `"C:\FFmpeg\ffmpeg.exe"`

* `FFMPEG_ARGUMENTS (Default: "-loglevel warning -hide_banner")` = Which arguments to run FFmpeg commands with. 

## Usage

Usage: ```iSubRip <iTunes movie URL>```