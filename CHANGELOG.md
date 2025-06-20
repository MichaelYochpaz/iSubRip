# Changelog
## 2.6.5 [2025-06-20]
### Changes:
* Added missing languages to the list of RTL languages (relevant if the `languages.fix-rtl` config setting is enabled).
* Minor improvements to the download progress bar.

### Bug Fixes:
* Fixed an issue where in some cases, the "Downloaded subtitles (X/Y)" progress log line would print repeatedly. ([Issue #87](https://github.com/MichaelYochpaz/iSubRip/issues/87))
---
## 2.6.4 [2025-06-13]
### Changes:
* Minor improvements to the download progress bar.

### Bug Fixes:
* Fixed an issue where if there is no config file, an error is raised instead of using default settings. ([Issue #86](https://github.com/MichaelYochpaz/iSubRip/issues/86))
---
## 2.6.3 [2025-03-17]
### Bug Fixes:
* Fixed an issue where logs containing the percentage character (`%`) would raise an error. ([Issue #82](https://github.com/MichaelYochpaz/iSubRip/issues/82))
---
## 2.6.2 [2025-02-04]
### Bug Fixes:
* Fixed an issue where AppleTV API calls would fail due to changes on AppleTV requiring a missing `utsk` parameter. ([Issue #80](https://github.com/MichaelYochpaz/iSubRip/issues/80))
* Fixed an issue where iTunes URLs would not work due to iTunes no longer redirecting to AppleTV. A different method will be used now to find corresponding AppleTV URLs. Also added a retry mechanism as it appears to be a bit unreliable at times. (thanks @yonatand1230 for suggesting this method!). ([Issue #78](https://github.com/MichaelYochpaz/iSubRip/issues/78))
* Removed progress bar when where there are no matching subtitles to download (previously, it would just show 0/0 with 0% progress).
---
## 2.6.1 [2025-01-31]
### Bug Fixes:
* Fixed a backwards compatibility issue in code, which would cause errors when running on Python versions lower than 3.12. ([Issue #78](https://github.com/MichaelYochpaz/iSubRip/issues/78))
---
## 2.6.0 [2025-01-28]
**The following update contains breaking changes to the config file.  
If you are using one, please update your config file accordingly.**

### Added:
* Added a new `general.log-level` config setting, the log level of stdout (console) output. Set to `info` by default. Can be changed to `debug`, `warning`, or `error`. See the updated [example config](https://github.com/MichaelYochpaz/iSubRip/blob/main/example-config.toml) for an example.

### Changes:
* Console output has been overhauled and improved, with colorful interactive output.
* Config file is now parsed and validated in a more reliable and efficient manner. Configuration errors will now be more readable and descriptive.
* **Breaking config changes** - the `scrapers` config category has been updated. Settings that should apply for all scrapers are now under the `scrapers.default` category instead of straight under `scrapers`. See the updated [example config](https://github.com/MichaelYochpaz/iSubRip/blob/main/example-config.toml) for examples.
* Updated AppleTV scraper request parameters.
* Minor improvements to logs.
* Python 3.8 is no longer supported. Minimum supported version has been updated to 3.9.

### Bug Fixes:
* Fixed an issue where if `verify-ssl` is set to `false`, and the `urllib3` package (which isn't a dependency of iSubRip) is not installed, an error could be thrown.
---
## 2.5.6 [2024-07-07]
### Bug Fixes:
* Fixed an issue where the update message from version `2.5.4` to `2.5.5` would still appear after updating. ([Issue #73](https://github.com/MichaelYochpaz/iSubRip/issues/73))
---
## 2.5.5 [2024-07-06]
### Added:
* Added new `timeout` setting to the config file, for the option to change the timeout for all / specific scrapers. See the updated [example config](https://github.com/MichaelYochpaz/iSubRip/blob/main/example-config.toml) for usage examples. ([Issue #71](https://github.com/MichaelYochpaz/iSubRip/issues/71))

### Changes:
* Default timeout for requests has been updated from 5 seconds to 10 seconds. ([Issue #71](https://github.com/MichaelYochpaz/iSubRip/issues/71))
---
## 2.5.4 [2024-04-28]
### Bug Fixes:
* Fixed an issue where if the `logs` directory does not exist, the folder isn't created, causing an error. ([Issue #67](https://github.com/MichaelYochpaz/iSubRip/issues/67))
* Fixed an issue where the summary log of successful and failed download would not account for failed downloads. ([Issue #68](https://github.com/MichaelYochpaz/iSubRip/issues/68))
---
## 2.5.3 [2024-04-09]
### Added:
* Added new `proxy` and `verify-ssl` settings to the config file, for allowing the usage of a proxy when making requests, and disabling SSL verification. See the updated [example config](https://github.com/MichaelYochpaz/iSubRip/blob/main/example-config.toml) for usage examples.

### Changes:
* `subtitles.rtl-languages` config setting is no longer supported, and its values are now hardcoded and can't be modified.

### Bug Fixes:
* Fixed an issue where in some cases, `STYLE` blocks would repeat throughout the subtitles file, and cause inaccurate cue count. ([Issue #63](https://github.com/MichaelYochpaz/iSubRip/issues/63))
* Fixed an issue where the WebVTT Style blocks would have their `STYLE` tag replaced with a `REGION` tag in downloaded subtitles.
* Fixed an issue where an empty playlist (with a size of 0 bytes) would be reported as a valid playlist with no matching subtitles. ([Issue #65](https://github.com/MichaelYochpaz/iSubRip/issues/65))
---
## 2.5.2 [2024-01-06]
### Bug Fixes:
* Fixed an issue where errors would not be handled gracefully, and cause an unexpected crash. ([Issue #55](https://github.com/MichaelYochpaz/iSubRip/issues/55))
---
## 2.5.1 [2023-12-23]
### Bug Fixes:
* Fixed an issue where source abbreviation was missing from file names of downloaded subtitles files. ([Issue #53](https://github.com/MichaelYochpaz/iSubRip/issues/53))
---
## 2.5.0 [2023-12-16]
### Added:
* Added logs. See the new [Logs section in the README](https://github.com/MichaelYochpaz/iSubRip#logs) for more information.
* Added a new `subtitles.webvtt.subrip-alignment-conversion` config setting (which is off by default), which if set to true, will add the `{\an8}` tag at the start of lines that are annotated at the top (with the `line:0.00%` WebVTT setting) when converting to SubRip. ([Issue #35](https://github.com/MichaelYochpaz/iSubRip/issues/35))
* Implemented caching for AppleTV's storefront configuration data, which should reduce the amount of requests used when scraping multiple AppleTV URLs from the same storefront.

### Changes:
* Big backend changes to the structure of the code, mostly to improve modularity and allow for easier development in the future, and improve performance.
* Updated the CLI output to utilize logs and print with colors according to log-level.
* Improved error handling in some cases where an invalid URL is used.

### Bug Fixes:
* Fixed an issue where if a movie is a pre-order with a set release date, a message with availability date wouldn't be printed in some cases.
---
## 2.4.3 [2023-06-18]
### Bug Fixes:
* Fixed an issue where some AppleTV URLs (or iTunes links that refer to such URLs) would not be matched in some cases, resulting in a "No matching scraper was found..." error. ([Issue #46](https://github.com/MichaelYochpaz/iSubRip/issues/46))
---
## 2.4.2 [2023-06-02]
### Changes:
* Improved error handling for subtitles downloads. ([Issue #44](https://github.com/MichaelYochpaz/iSubRip/issues/44))

### Bug Fixes:
* Fixed an issue where using a ZIP file, and saving to a different drive than the OS drive would fail. ([Issue #43](https://github.com/MichaelYochpaz/iSubRip/issues/43))
---
## 2.4.1 [2023-05-25]
### Bug Fixes:
* Fixed an issue where saving subtitles to a different drive than the OS drive would fail. ([Issue #41](https://github.com/MichaelYochpaz/iSubRip/issues/41))
* Fixed AppleTV URLs with multiple iTunes playlists causing an error. ([Issue #42](https://github.com/MichaelYochpaz/iSubRip/issues/42))
---
## 2.4.0 [2023-05-23]
### Added:
- iTunes links will now redirect to AppleTV and scrape metadata from there, as AppleTV has additional and more accurate metadata.
- Improved error messages to be more informative and case-specific:
  - If a movie is a pre-order and has no available playlist, a proper error message will be printed with its release date (if available).
  - If trying to scrape AppleTV+ content or series (which aren't currently supported), a proper error will be printed.

### Changes:
- A major refactor to the code, to make it more modular and allow for easier development of new features in the future.
- Multiple changes (with some breaking changes) to the config file:
  - The `downloads.format` setting is deprecated, and replaced by the `subtitles.convert-to-srt` setting.
  - The `downloads.merge-playlists` setting is deprecated, with no replacement.  
    If an AppleTV link has multiple playlists, they will be downloaded separately.
  - The `downloads.user-agent` setting is deprecated, with no replacement.
    The user-agent used by the scraper, will be used for downloads as well.
  - The `scraping` config category no longer exists, and is replaced by a `scrapers` category, which has a sub-category with settings for each scraper (for example, a `scrapers.itunes` sub-category).
- Old config paths that were previously deprecated are no longer supported and will no longer work.
  The updated config settings can be found in the [example config](https://github.com/MichaelYochpaz/iSubRip/blob/main/example-config.toml).

### Notes:
* This release includes a major rewrite of the code, which may have introduced new bugs to some core features. If you encountered one, [please report it](https://github.com/MichaelYochpaz/iSubRip/issues/new/choose).
* Minimum supported Python version bumped to 3.8.
* `beautifulsoup4` and `lxml` packages are no longer required or used.
---
## 2.3.3 [2022-10-09]
### Changes:
* Added release year to zip file names. ([Issue #31](https://github.com/MichaelYochpaz/iSubRip/issues/31))
* If the generated path for a zip file is already taken, a number will be appended at the end of the file's name to avoid overwriting. ([Issue #34](https://github.com/MichaelYochpaz/iSubRip/issues/34))

### Bug Fixes:
* Fixed an exception being thrown if the path to downloads folder on the config is invalid.
* Fixed AppleTV URLs without a movie title not working. ([Issue #29](https://github.com/MichaelYochpaz/iSubRip/issues/29))
* Fixed issues for movies with specific characters (`/`, `:`), and Windows reserved names in their title. ([Issue #30](https://github.com/MichaelYochpaz/iSubRip/issues/30))
---
## 2.3.2 [2022-08-06]
### Changes:
* Changed config paths to the following locations:  
Windows: `%USERPROFILE%\.isubrip\config.json`  
Linux / macOS: `$HOME/.isubrip/config.json`  
More info under Notes (and examples on the [README](https://github.com/MichaelYochpaz/iSubRip#configuration) file).

### Bug Fixes:
* Fixed an error with AppleTV links for movies released before 1970 (Epoch time). ([Issue #21](https://github.com/MichaelYochpaz/iSubRip/issues/21))
* Fixed config file not being loaded on macOS. ([Issue #22](https://github.com/MichaelYochpaz/iSubRip/issues/22))
* Fixed AppleTV scraping from the same storefront. ([Issue #24](https://github.com/MichaelYochpaz/iSubRip/issues/24))

### Notes:
* Running iSubRip with a config file in the previous locations will still work, but support for them will be dropped in the future.  
* `xdg` package is no longer required or used.
---
## 2.3.1 [2022-07-15]
### Changes:
* Improved AppleTV scraping to utilize AppleTV's API instead of scraping HTML.

### Bug Fixes:
* Fixed HTML escaped (for non-English) characters not matching AppleTV's URL RegEx. ([Issue #15](https://github.com/MichaelYochpaz/iSubRip/issues/15))
---
## 2.3.0 [2022-06-23]
### Added:
* AppleTV movie URLs are now supported.
* Added a `merge-playlists` config option to treat multiple playlists that can be found on AppleTV pages as one (more info on the example config).

### Changes:
* Improved subtitles parser to perserve additional WebVTT data.
* The config value `user-agent` under `scraping` is now separated to 2 different values: `itunes-user-agent`, and `appletv-user-agent`.

### Bug Fixes:
* Fixed movie titles with invalid Windows file-name characters (example: '?') causing a crash. ([Issue #14](https://github.com/MichaelYochpaz/iSubRip/issues/14))
* Fixed iTunes store URLs without a movie title not working. ([Issue #13](https://github.com/MichaelYochpaz/iSubRip/issues/13))
---
## 2.2.0 [2022-04-25]
### Added:
* Replaced FFmpeg usage for parsing with a native subtitles parser (downloads are much faster now).
* Added a `remove-duplicates` configuration remove duplicate paragraphs. (Was previously automatically fixed by FFmpeg.)
* Added `fix-rtl` and `rtl-languages` configuration to fix RTL in RTL-languaged subtitles (has to be enabled in the config).

### Changes:
* FFmpeg is no longer required or used, and all FFmpeg-related settings are deprecated.

### Notes:
* `fix-rtl` is off by default and has to be enabled on the config. Check the `config.toml` example file for more info.
* Minimum supported Python version bumped to 3.7.
---
## 2.1.2 [2022-04-03]
### Bug Fixes:
* Fixed subtitles being downloaded twice, which causes long (doubled) download times.
---
## 2.1.1 [2022-03-28]
### Bug Fixes:
* Fixed a compatibility issue with Python versions that are lower than 3.10.
* Fixed downloading subtitles to an archive file not working properly.
* Fixed a bug where the code continues to run if subtitles download failed, as if the download was successful.
---
## 2.1.0 [2022-03-19]
### Added:
* A note will be printed if a newer version is available on PyPI (can be disabled on the config).
* Config will now be checked for errors before running.

### Changes:
* Big improvements to scraping, which is now far more reliable.
* Added release year to subtitles file names.
* Config structure slightly changed.

### Notes:
* If you use a user-config, it might need to be updated to match the new config structure.
  Example of an updated valid structure can be found [here](https://github.com/MichaelYochpaz/iSubRip/blob/main/example-config.toml).
---
## 2.0.0 [2022-01-30]
The script is now a Python package that can be installed using pip.

### Added:
* Added a config file for changing configurations. (Example can be found [here](https://github.com/MichaelYochpaz/iSubRip/blob/main/example-config.toml))
* Added an option to choose subtitles format (vtt / srt).
* Added an option to choose whether to zip subtitles files or not.
* Multiple links can be passed for downloading subtitles for multiple movies one after another.
* Temporary files are automatically removed if the script stops unexpectedly.

### Changes:
* A complete code overhaul from a single python script file to a package, while utilizing OOP and classes.
* Improved scraping algorithm for faster playlist scraping.
* FFmpeg will now automatically overwrite existing subtitles with the same file name.

### Bug Fixes:
* Fixed a bug where in some cases, no subtitles were found since the title has HTML escaped characters, which causes bad matching when checking if a valid playlist was found.
---
## 1.0.6 [2021-07-23]
### Bug Fixes:
* Fixed an issue where in some cases subtitles won't download when using `DOWNLOAD_FILTER` because of letter casing not matching.
* Fixed and improved error handling, and added more descriptive error messages. ([Issue #9](https://github.com/MichaelYochpaz/iSubRip/issues/9))
---
## 1.0.5 [2021-05-27]
### Bug Fixes:
* Fixed subtitles for some movies not being found after previous release. ([Issue #8](https://github.com/MichaelYochpaz/iSubRip/issues/8))
---
## 1.0.4 [2021-05-25]
### Bug Fixes:
* Fixed the script not working after iTunes webpage data orientation slightly changed. ([Issue #6](https://github.com/MichaelYochpaz/iSubRip/issues/6) , [Issue #7](https://github.com/MichaelYochpaz/iSubRip/issues/7))
---
## 1.0.3 [2021-04-30]
### Bug Fixes:
* Fixed a bug where subtitles for suggested movies are being downloaded if movie's main playlist is not found. ([Issue #2](https://github.com/MichaelYochpaz/iSubRip/issues/2))
* Added a "cc" tag to closed-caption subtitles' filename to avoid a collision with non-cc subtitles. ([Issue #3](https://github.com/MichaelYochpaz/iSubRip/issues/3))
---
## 1.0.2 [2021-04-15]
### Added:
* Added a User-Agent for sessions to avoid being blocked.

### Changes:
* `DOWNLOAD_FILTER` is no longer case-sensitive.
* Added `lxml` to `requirements.txt`. ([Issue #1](https://github.com/MichaelYochpaz/iSubRip/issues/1))

### Bug Fixes:
* Fixed the script not working after iTunes webpage data orientation slightly changed. ([Issue #1](https://github.com/MichaelYochpaz/iSubRip/issues/1))
---
## 1.0.1 [2020-12-13]
### Changes:
* Improved error handling.
  
### Bug Fixes:
* Fixed file name formatting.
---
## 1.0.0 [2020-11-02]
* Initial release.