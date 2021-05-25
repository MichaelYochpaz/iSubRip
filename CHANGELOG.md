# Changelog
All notable changes to the script will be documented here.

## 1.0.4 - [2021-05-25]
* Fixed the script to work again after iTunes webpage data orientation slightly changed. ([Issue #6](https://github.com/MichaelYochpaz/iSubRip/issues/6), [Issue #7](https://github.com/MichaelYochpaz/iSubRip/issues/7))

## 1.0.3 - [2021-04-30]
* Fixed an issue where subtitles for suggested movies are being downloaded if there isn't a playlist for the movie that's being scraped. ([Issue #2](https://github.com/MichaelYochpaz/iSubRip/issues/2))
* Added a "cc" tag to closed-caption (CC) subtitles' filename to avoid filename collision. ([Issue #3](https://github.com/MichaelYochpaz/iSubRip/issues/3))

## 1.0.2 - [2021-04-15]
* Fixed the script to work again after iTunes webpage data orientation slightly changed. ([Issue #1](https://github.com/MichaelYochpaz/iSubRip/issues/1))
* Fixed `requirements.txt` to include `lxml`. ([Issue #1](https://github.com/MichaelYochpaz/iSubRip/issues/1))
* Added a user-agent for the session used by the script to avoid the session from being blocked.
* `DOWNLOAD_FILTER` is no longer case-sensitive.
* A few additional small code and comments improvements.

## 1.0.1 - [2020-12-13]
* Improved error handling.
* A small fix to file name formatting.
* Updated code comments for better readability.

## 1.0.0 - [2020-11-02]
* Initial release.
