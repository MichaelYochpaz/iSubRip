# iSubRip
A Python package for scraping and downloading subtitles from AppleTV / iTunes movie pages.  
Latest version: 2.5.0 ([changelog](https://github.com/MichaelYochpaz/iSubRip/blob/main/CHANGELOG.md))  

<br/>
  
[![PyPI - Version](https://img.shields.io/pypi/v/isubrip)](https://python.org/pypi/isubrip)
[![PyPI - Monthly Downloads](https://pepy.tech/badge/isubrip/month)](https://python.org/pypi/isubrip)
[![PyPI - Total Downloads](https://pepy.tech/badge/isubrip)](https://python.org/pypi/isubrip)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/isubrip)](https://python.org/pypi/isubrip)
[![GitHub - License](https://img.shields.io/github/license/MichaelYochpaz/iSubRip)](https://github.com/MichaelYochpaz/iSubRip/blob/main/LICENSE)
[![GitHub - issues](https://img.shields.io/github/issues/MichaelYochpaz/iSubRip)](https://github.com/MichaelYochpaz/iSubRip/issues)
[![GitHub - Repo stars](https://img.shields.io/github/stars/MichaelYochpaz/iSubRip.svg?color=yellow)](https://github.com/MichaelYochpaz/iSubRip)

<p align="center">
  <a href="#"><img src="https://github-production-user-asset-6210df.s3.amazonaws.com/8832013/290989935-e6a17af6-1ebb-456d-a024-dc6e84dd64b2.gif" width="800"></a>
</p>


##  Requirements
* Python 3.8+

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
A [TOML](https://toml.io) config file can be created and used to configure different options and features.
A config file will be looked for in one of the following paths (according to OS): 

**Windows**: `%USERPROFILE%\.isubrip\config.toml`  
**Linux / macOS**: `$HOME/.isubrip/config.toml`  

### Examples:
**Windows**: `C:\Users\Michael\.isubrip\config.toml`  
**Linux**: `/home/Michael/.isubrip/config.toml`  
**macOS**: `/Users/Michael/.isubrip/config.toml`  

---

### Example Config:
```toml
[downloads]
folder = "C:\\Subtitles\\iTunes"
languages = ["en-US", "fr-FR", "he"]
zip = false

[subtitles]
convert-to-srt = true
fix-rtl = true

[subtitles.webvtt]
subrip-alignment-conversion = true
```

A complete config with all the available options and explanations for each configuration can be found [here](https://github.com/MichaelYochpaz/iSubRip/blob/main/config.toml).

## Logs
A log file, containing debug information, will be created for each run on one of the following paths (according to OS):

**Windows**: `%USERPROFILE%\.isubrip\logs`  
**Linux / macOS**: `$HOME/.isubrip/logs`  

Log rotation (deletion of old files, once a certain amount of files is reached) can be configured in the config file using the `general.log-rotation-size` setting. The default log rotation value is `15`.