# iSubRip
A Python package for scraping and downloading subtitles from iTunes movie pages.  
Latest version: 2.2.0 ([changelog](https://github.com/MichaelYochpaz/iSubRip/blob/main/CHANGELOG.md))  

<br/>
  
[![PyPI - Version](https://img.shields.io/pypi/v/isubrip)](https://python.org/pypi/isubrip)
[![PyPI - Monthly Downloads](https://pepy.tech/badge/isubrip/month)](https://python.org/pypi/isubrip)
[![PyPI - Total Downloads](https://pepy.tech/badge/isubrip)](https://python.org/pypi/isubrip)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/isubrip)](https://python.org/pypi/isubrip)
[![GitHub - License](https://img.shields.io/github/license/MichaelYochpaz/iSubRip)](https://github.com/MichaelYochpaz/iSubRip/blob/main/LICENSE)
[![GitHub - issues](https://img.shields.io/github/issues/MichaelYochpaz/iSubRip)](https://github.com/MichaelYochpaz/iSubRip/issues)
[![GitHub - Repo stars](https://img.shields.io/github/stars/MichaelYochpaz/iSubRip.svg?color=yellow)](https://github.com/MichaelYochpaz/iSubRip)

<p align="center">
  <a href="#"><img src="https://user-images.githubusercontent.com/8832013/151677574-0539aa8b-7f88-4ae8-a85d-948c5338c873.png" width="800"></a>
</p>


##  Requirements
* Python 3.7+

##  Installation
### PyPI (Recommended)
```
python3 -m pip install isubrip
```

### Git Source Code
```
python3 -m pip install -e git+https://github.com/MichaelYochpaz/iSubRip.git#egg=isubrip
```

## Usage
```
isubrip <iTunes movie URL> [iTunes movie URL...]
```  

## Configuration
It's possible to configure different options and enable / disable different features using a [TOML](https://toml.io) config file.   
A config file will be looked for in one of the following paths according to OS: 

**Windows**: ```%AppData%/iSubRip/config.toml```  
**Linux**: ```$XDG_CONFIG_HOME/iSubRip/config.toml```  
**MacOS**: ```~/Library/Application Support/isubrip/config.toml```  

---

### Example Config:
```toml
[downloads]
folder = "C:\\iTunes-Subtitles"
format = "srt"
languages = ["en-US"]
zip = false

[subtitles]
fix-rtl = true
```

A complete config with all the available options and explanations for each configuration can be found [here](https://github.com/MichaelYochpaz/iSubRip/blob/main/config.toml)

### Notes
* All settings are optional. Not specifying a setting will result in using the default value (set in the `default_config.toml` file).
* If running on a Linux machine and `XDG_CONFIG_HOME` is not set, the value of `XDG_CONFIG_HOME` will default to `~/.config`.
