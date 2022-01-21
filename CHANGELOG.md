# Changelog
## 1.0.6 [2021-07-23]
### Bug Fixes:
* Fixed an issue where in some cases subtitles won't download when using `DOWNLOAD_FILTER` because of letter casing not matching.
* Fixed and improved error handling, and added more descriptive error messages. ([Issue #9](https://github.com/MichaelYochpaz/iSubRip/issues/9))
---
## 1.0.5 [2021-05-27]
### Bug Fixes:
* Fixed subtitles for some movies not being found after previous changes. ([Issue #8](https://github.com/MichaelYochpaz/iSubRip/issues/8))
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
* Added a User-Agent for sessions to avoid the it being blocked.

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