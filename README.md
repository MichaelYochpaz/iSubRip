# iSubRip
A Python script to scrape and download subtitles off of iTunes movie pages.  
Latest version: [1.0.6](https://github.com/MichaelYochpaz/iSubRip/blob/main/iSubRip.py) ([changelog](https://github.com/MichaelYochpaz/iSubRip/blob/main/CHANGELOG.md))

<br/>
<p align="center">
  <a href="#"><img src="https://user-images.githubusercontent.com/8832013/111081939-59f1fe80-850e-11eb-94ad-0a77baff88ed.gif" width="600"></a>
</p>

##  Requirements
* Python 3.7+
* [FFmpeg](https://github.com/FFmpeg/FFmpeg) (If FFmpeg is not set in [PATH](https://en.wikipedia.org/wiki/PATH_(variable)), enter FFmpeg's path in `FFMPEG_PATH` under configuration)

##  Installation
```
> git clone https://github.com/MichaelYochpaz/iSubRip.git iSubRip
> cd iSubRip && pip3 install -r requirements.txt
```

## Configuration
The uses a [TOML](https://toml.io) config file for the settings.  

Configuration file locations: 

**Windows**: %AppData%/iSubRip/config.toml  
**Linux**: $XDG_CONFIG_HOME/iSubRip/config.toml  
**MacOS**: ~/Library/Application Support/isubrip/config.toml  

An example config file with documentation can be found [here](https://github.com/MichaelYochpaz/iSubRip/blob/main/config.toml)

### Notes
* All settings are optional. Any settings not specified in the config will result in using the default value (set in the default.toml file).
* If you are running the script on a Linux machine and XDG_CONFIG_HOME is not set in your environment, the value will default to ~/.config.

## Usage

Usage: ```python iSubRip.py <iTunes movie URL>```  
Example: ```python iSubRip.py https://itunes.apple.com/gb/movie/interstellar-2014/id965491522```

##
This script was made for educational purposes only.  
Any use of the script is at your own responsibility.
