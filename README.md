# iSubRip
A Python package for scraping and downloading subtitles from iTunes movie pages.  
Latest version: 2.1.0 ([changelog](https://github.com/MichaelYochpaz/iSubRip/blob/main/CHANGELOG.md))  

</br>
  
[![PyPI - Version](https://img.shields.io/pypi/v/isubrip)](https://python.org/pypi/isubrip)
[![PyPI - Downloads](https://pepy.tech/badge/isubrip)](https://python.org/pypi/isubrip)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/isubrip)](https://python.org/pypi/isubrip)
[![GitHub - License](https://img.shields.io/github/license/MichaelYochpaz/iSubRip)](https://github.com/MichaelYochpaz/iSubRip/blob/main/LICENSE)
[![GitHub - issues](https://img.shields.io/github/issues/MichaelYochpaz/iSubRip)](https://github.com/MichaelYochpaz/iSubRip/issues)
[![GitHub - Repo stars](https://img.shields.io/github/stars/MichaelYochpaz/iSubRip.svg?color=yellow)](https://github.com/MichaelYochpaz/iSubRip)
  
<p align="center">
  <a href="#"><img src="https://user-images.githubusercontent.com/8832013/151677574-0539aa8b-7f88-4ae8-a85d-948c5338c873.png" width="800"></a>
</p>


##  Requirements
* Python 3.6+
* [FFmpeg](https://github.com/FFmpeg/FFmpeg) (If FFmpeg is not set in [PATH](https://en.wikipedia.org/wiki/PATH_(variable)), use a config file to set it's path.)

##  Installation
### pip:
```
pip3 install isubrip
```

## Usage
Usage: ```isubrip <iTunes movie URL> [iTunes movie URL...]```  

## Configuration
The script uses a [TOML](https://toml.io) config file for the settings.  

Config file locations: 

**Windows**: ```%AppData%/iSubRip/config.toml```  
**Linux**: ```$XDG_CONFIG_HOME/iSubRip/config.toml```  
**MacOS**: ```~/Library/Application Support/isubrip/config.toml```  

An example config file with documentation can be found [here](https://github.com/MichaelYochpaz/iSubRip/blob/main/config.toml)

### Notes
* All settings are optional. Any settings not specified in the config will result in using the default value (set in the default.toml file).

* If you are running the script on a Linux machine and XDG_CONFIG_HOME is not set in your environment,  
  the value will default to ~/.config.
