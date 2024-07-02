# iSubRip
**iSubRip** is a Python command-line tool for scraping and downloading subtitles from AppleTV and iTunes movie pages.

<div align="center">
  <a href="https://python.org/pypi/isubrip"><img alt="Python Version" src="https://img.shields.io/pypi/pyversions/isubrip"></a>
  <a href="https://python.org/pypi/isubrip"><img alt="PyPI Version" src="https://img.shields.io/pypi/v/isubrip"></a>
  <a href="https://github.com/MichaelYochpaz/iSubRip/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/MichaelYochpaz/iSubRip"></a>

  <a href="https://python.org/pypi/isubrip"><img alt="Monthly Downloads" src="https://pepy.tech/badge/isubrip/month"></a>
  <a href="https://python.org/pypi/isubrip"><img alt="Total Downloads" src="https://pepy.tech/badge/isubrip"></a>
  <a href="https://github.com/MichaelYochpaz/iSubRip"><img alt="Repo Stars" src="https://img.shields.io/github/stars/MichaelYochpaz/iSubRip?style=flat&color=gold"></a>
  <a href="https://github.com/MichaelYochpaz/iSubRip/issues"><img alt="Issues" src="https://img.shields.io/github/issues/MichaelYochpaz/iSubRip?color=red"></a>
</div>

<br/>

<div align="center">
  <img src="https://github-production-user-asset-6210df.s3.amazonaws.com/8832013/290989935-e6a17af6-1ebb-456d-a024-dc6e84dd64b2.gif" width="800">
</div>


---

## ✨ Features
- Scrape subtitles from AppleTV and iTunes movies without needing a purchase or account.
- Retrieve the expected streaming release date (if available) for unreleased movies.
- Utilize asynchronous downloading to speed up the download of chunked subtitles.
- Automatically convert subtitles to SubRip (SRT) format.
- Fix right-to-left (RTL) alignment in RTL language subtitles automatically.
- Configure settings such as download folder, preferred languages, and toggling features.

## 🚀 Quick Start
### Installation
```shell
pip install isubrip
```

### Usage
```shell
isubrip <URL> [URL...]
```
<sub>(URL can be either an AppleTV or iTunes movie URL)</sub>

<br/>

> [!WARNING]
> iSubRip is not recommended for use as a library in other projects.  
> The API frequently changes, and breaking changes to the API are common, even in minor versions.
>
> Support will not be provided for issues arising from using this package as a library.
## 🛠 Configuration
A [TOML](https://toml.io) configuration file can be created to customize various options and features.

The configuration file will be searched for in one of the following paths based on your operating system:

- **Windows**: `%USERPROFILE%\.isubrip\config.toml`
- **Linux / macOS**: `$HOME/.isubrip/config.toml`

### Path Examples
- **Windows**: `C:\Users\Michael\.isubrip\config.toml`
- **Linux**: `/home/Michael/.isubrip/config.toml`
- **macOS**: `/Users/Michael/.isubrip/config.toml`


### Example Configuration
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

An example config with details and explanations for all available settings can be found [here](https://github.com/MichaelYochpaz/iSubRip/blob/main/config.toml).

## 📜 Logs
Log files are created for each run in the following paths, depending on your operating system:

**Windows**: `%USERPROFILE%\.isubrip\logs`  
**Linux / macOS**: `$HOME/.isubrip/logs`  

Log rotation (deletion of old files once a certain number of files is reached) can be configured in the configuration file using the `general.log-rotation-size` setting. The default value is `15`.

For more details, see the [example configuration](https://github.com/MichaelYochpaz/iSubRip/blob/main/config.toml).


## 📓 Changelog
The changelog for the latest, and all previous versions, can be found [here](https://github.com/MichaelYochpaz/iSubRip/blob/main/CHANGELOG.md).

## 👨🏽‍💻 Contributing
This project is open-source but currently lacks the infrastructure to fully support external contributions.

If you wish to contribute, please open an issue first to discuss your proposed changes to avoid working on something that might not be accepted.

## 🙏🏽 Support
If you find this project helpful, please consider supporting it by:
- 🌟 Starring the repository
- 💖 [Sponsoring the project](https://github.com/sponsors/MichaelYochpaz)

## ❤️ Special Thanks
Thanks to **JetBrains** for generously providing a free open-source [PyCharm](https://www.jetbrains.com/pycharm/) license to help work on this project, through their [Open Source Support Program](https://www.jetbrains.com/community/opensource/).

[![PyCharm Logo](https://resources.jetbrains.com/storage/products/company/brand/logos/PyCharm_icon.svg)](https://www.jetbrains.com/community/opensource/#support)

## 📝 End User License Agreement
By using iSubRip, you agree to the following terms:

1. **Disclaimer of Affiliation**: iSubRip is an independent, open-source project. It is not affiliated with, endorsed by, or in any way officially connected to Apple Inc., iTunes, or AppleTV.
2. **Educational Purpose**: This tool is developed and provided for educational and research purposes only. It demonstrates techniques for accessing and processing publicly available, unencrypted subtitle data from HLS playlists.
3. **User Responsibility and Compliance**: Any use of iSubRip is solely at the user's own risk and discretion. Users are responsible for ensuring that their use of the tool complies with all applicable laws, regulations, and terms of service of the content providers. This includes adhering to local, state, national, and international laws and regulations.
4. **Limitation of Liability**: The developers of iSubRip shall not be held responsible for any legal consequences arising from the use of this tool. This includes, but is not limited to, claims of copyright infringement, intellectual property violations, or breaches of terms of service of content providers. Users assume all risks associated with acquiring and using subtitle data through this tool.

By using iSubRip, you acknowledge that you have read, understood, and agree to be bound by this agreement's terms and conditions.

## ⚖️ License
This project is licensed under the MIT License. For more details, see the [LICENSE file](https://github.com/MichaelYochpaz/iSubRip/blob/main/LICENSE).
