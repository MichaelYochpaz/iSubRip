# iSubRip
A Python script to scrape and download subtitles off of iTunes using iTunes movie pages.  
Latest version: 1.0.1 ([changelog](https://github.com/MichaelYochpaz/iSubRip/blob/main/CHANGELOG.md))

##  Requirements
* [FFmpeg](https://github.com/FFmpeg/FFmpeg) (If FFmpeg is not set in [PATH](https://en.wikipedia.org/wiki/PATH_(variable)), enter FFmpeg's path in `FFMPEG_PATH` under configuration)

##  Installation
```
> git clone https://github.com/MichaelYochpaz/iSubRip.git iSubRip
> cd iSubRip && pip3 install -r requirements.txt
```

## Configuration
* `DOWNLOAD_FILTER (Default: [])` - A list of subtitles languages to download.  
Only iTunes language codes (list can be found [here](https://gist.github.com/daFish/5990634)) or language names can be used.
Leave empty to download all available subtitles.  
Example: `["en", "he"]`

* `DOWNLOAD_FOLDER (Default: "")` - Folder to save subtitles files to. Leave empty to use current working directory.  
Example: `"C:\Subtitles"`

* `FFMPEG_PATH (Default: "ffmpeg")` - FFmpeg's location. Use default "ffmpeg" value if FFmpeg is in PATH.  
Example: `"C:\FFmpeg\ffmpeg.exe"`

* `FFMPEG_ARGUMENTS (Default: "-loglevel warning -hide_banner")` - Arguments to run FFmpeg commands with. 

## Usage

Usage: ```iSubRip.py <iTunes movie URL>```  
Example: ```iSubRip.py https://itunes.apple.com/gb/movie/interstellar-2014/id965491522```
