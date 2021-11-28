# iSubRip
A Python script to scrape and download subtitles off of iTunes movie pages.  
Latest version: [1.0.6](https://github.com/MichaelYochpaz/iSubRip/blob/main/iSubRip.py) ([changelog](https://github.com/MichaelYochpaz/iSubRip/blob/main/CHANGELOG.md))

<br/>
<p align="center">
  <a href="#"><img src="https://user-images.githubusercontent.com/8832013/111081939-59f1fe80-850e-11eb-94ad-0a77baff88ed.gif" width="600"></a>
</p>

##  Requirements
* Python 3.6+
* [FFmpeg](https://github.com/FFmpeg/FFmpeg) (If FFmpeg is not set in [PATH](https://en.wikipedia.org/wiki/PATH_(variable)), enter FFmpeg's path in `FFMPEG_PATH` under configuration)

##  Installation
```
> git clone https://github.com/MichaelYochpaz/iSubRip.git iSubRip
> cd iSubRip && pip3 install -r requirements.txt
```

## Configuration
* `DOWNLOAD_FILTER (Default: [])` - A list of subtitle languages to download.  
Only iTunes language codes (list can be found [here](https://datahub.io/core/language-codes/r/0.html)) or language names can be used.
Leave empty to download all available subtitles.  
Example: `["en", "he"]`

* `DOWNLOAD_FOLDER (Default: "")` - Folder to save subtitle files to. Leave empty to use current working directory.  
Example: `"C:\Subtitles"`

* `FFMPEG_PATH (Default: "ffmpeg")` - FFmpeg's location. Use default "ffmpeg" value if FFmpeg is in PATH.  
Example: `"C:\FFmpeg\ffmpeg.exe"`

* `FFMPEG_ARGUMENTS (Default: "-loglevel warning -hide_banner")` - Arguments to run FFmpeg commands with.  

* `HEADERS (Default: {"User-Agent" : "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_2_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15"})` - Session headers to run scraper with.  

## Usage

Usage: ```python iSubRip.py <iTunes movie URL>```  
Example: ```python iSubRip.py https://itunes.apple.com/gb/movie/interstellar-2014/id965491522```

##
This script was made for educational purposes only.  
Any use of the script is at your own responsibility.
