# iSubRip
A Python script to scrape and download subtitles off of iTunes using iTunes movie pages.  
Latest version: 1.0.1 ([changelog](https://github.com/MichaelYochpaz/iSubRip/blob/main/CHANGELOG.md))

##  Requirements
* FFmpeg is required for the script to work. If FFmpeg is not in PATH, enter FFmpeg's path in `FFMPEG_PATH`.

## Configuration
* `DOWNLOAD_FILTER (Default: [])` - A list of specific languages to download.  
Only iTunes anguage codes (list can be found [here](https://gist.github.com/daFish/5990634)) or language names can be used.
Leave empty to download all available subtitles.  
Example: `["en", "he"]`

* `DOWNLOAD_FOLDER (Default: "")` - Folder to save subtitles to. Leave empty to use the folder the script is running from.  
Example: `"C:\Subtitles"`

* `FFMPEG_PATH (Default: "ffmpeg:")`- FFmpeg's location. Use default "ffmpeg" value if FFmpeg is in PATH.  
Example: `"C:\FFmpeg\ffmpeg.exe"`

* `FFMPEG_ARGUMENTS (Default: "-loglevel warning -hide_banner")` = Which arguments to run FFmpeg commands with. 

## Usage

Usage: ```iSubRip <iTunes movie URL>```  
Example: ```iSubRip https://itunes.apple.com/gb/movie/interstellar-2014/id965491522```
