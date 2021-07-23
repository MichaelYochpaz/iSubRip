# Changelog
All notable changes to the script will be documented here.

## 1.0.6 - [2021-07-23]
* Fixed an issue where in some cases subtitles wouldn't download when using `DOWNLOAD_FILTER` because of letter casing not matching.
* Fixed and improved error handling, and added more descriptive error messages. ([#9](https://github.com/MichaelYochpaz/iSubRip/issues/9))

## 1.0.5 - [2021-05-27]
* Fixed subtitles for some movies not being found after changes in previous update. ([#8](https://github.com/MichaelYochpaz/iSubRip/issues/8))

## 1.0.4 - [2021-05-25]
* Fixed the script to work again after iTunes webpage data orientation slightly changed. ([#6](https://github.com/MichaelYochpaz/iSubRip/issues/6) , [#7](https://github.com/MichaelYochpaz/iSubRip/issues/7))

## 1.0.3 - [2021-04-30]
* Fixed an issue where subtitles for suggested movies are being downloaded if there isn't a playlist for the movie that's being scraped. ([#2](https://github.com/MichaelYochpaz/iSubRip/issues/2))
* Added a "cc" tag to closed-caption (CC) subtitles' filename to avoid filename collision. ([#3](https://github.com/MichaelYochpaz/iSubRip/issues/3))

## 1.0.2 - [2021-04-15]
* Fixed the script to work again after iTunes webpage data orientation slightly changed. ([#1](https://github.com/MichaelYochpaz/iSubRip/issues/1))
* Fixed `requirements.txt` to include `lxml`. ([#1](https://github.com/MichaelYochpaz/iSubRip/issues/1))
* Added a user-agent for the session used by the script to avoid the session from being blocked.
* `DOWNLOAD_FILTER` is no longer case-sensitive.

## 1.0.1 - [2020-12-13]
* Improved error handling.
* Fixed file name formatting.

## 1.0.0 - [2020-11-02]
* Initial release.
