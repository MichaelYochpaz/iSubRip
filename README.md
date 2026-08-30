# iSubRip

**iSubRip** is a Python command-line tool for downloading subtitles from Apple TV movie URLs.

<div align="center">
  <a href="https://pypi.org/project/isubrip/"><img alt="Python Version" src="https://img.shields.io/pypi/pyversions/isubrip"></a>
  <a href="https://pypi.org/project/isubrip/"><img alt="PyPI Version" src="https://img.shields.io/pypi/v/isubrip"></a>
  <a href="https://github.com/MichaelYochpaz/iSubRip/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/MichaelYochpaz/iSubRip"></a>

  <a href="https://pepy.tech/project/isubrip"><img alt="Monthly Downloads" src="https://pepy.tech/badge/isubrip/month"></a>
  <a href="https://pepy.tech/project/isubrip"><img alt="Total Downloads" src="https://pepy.tech/badge/isubrip"></a>
  <a href="https://github.com/MichaelYochpaz/iSubRip"><img alt="Repo Stars" src="https://img.shields.io/github/stars/MichaelYochpaz/iSubRip?style=flat&color=gold"></a>
  <a href="https://github.com/MichaelYochpaz/iSubRip/issues"><img alt="Issues" src="https://img.shields.io/github/issues/MichaelYochpaz/iSubRip?color=red"></a>
</div>

<br/>

<div align="center">
  <img src="https://github.com/user-attachments/assets/ffdbb366-8ad0-427d-af00-9b70cc0d6b01" width="800">
</div>

---

## ✨ Features

- Download publicly accessible subtitles from Apple TV and iTunes movie pages.
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
isubrip [--dsid DSID] <URL> [URL...]
```

No Apple account or DSID is normally required. See [Apple DSID](#apple-dsid) for the optional owned/rented-content
fallback.

> [!TIP]
> Run `isubrip --help` for all command-line options.

## 🛠 Configuration

A [TOML](https://toml.io) configuration file is optional.

iSubRip looks for the configuration file in the following location, based on your operating system:

- **Windows**: `%USERPROFILE%\.isubrip\config.toml`
- **Linux / macOS**: `$HOME/.isubrip/config.toml`

### Path Examples

- **Windows**: `C:\Users\Michael\.isubrip\config.toml`
- **Linux**: `/home/Michael/.isubrip/config.toml`
- **macOS**: `/Users/Michael/.isubrip/config.toml`


### Example Configuration

```toml
[downloads]
folder = "C:\\Subtitles\\AppleTV"
languages = ["en-US", "fr-FR", "he"]
zip = false

[subtitles]
convert-to-srt = true
fix-rtl = true

[subtitles.webvtt]
subrip-alignment-conversion = true
```

> [!TIP]
> An example config with details and explanations for all available settings can be found [here](https://github.com/MichaelYochpaz/iSubRip/blob/main/example-config.toml).

### Apple DSID

iSubRip always attempts Apple movie manifests anonymously first. If those requests receive an HTTP 401, 403, or 404 response, iSubRip can retry with a configured DSID.

A DSID identifies the Apple account that owns or has rented the title and is never sent when an anonymous request succeeds.

Because Apple does not document this manifest API, a failed request does not prove that authentication is required.  
A movie package may instead be unavailable, unreleased, or no longer present.

#### Finding your DSID

> [!IMPORTANT]
> Support for locating or acquiring a DSID will not be provided.
> Please **do not** open issues requesting help with DSID acquisition.

Apple does not provide a documented way for third-party tools to look up a DSID.
You can try the following steps to find your DSID:

1. Sign in to [Apple TV's Billing page](https://tv.apple.com/account/billing) using the Apple Account that owns or has rented the movie. If prompted to add a payment method, you can skip it; no billing changes are required.
2. Open [ph2.tv.apple.com/settings](https://ph2.tv.apple.com/settings).
3. Locate the `dsId` key and copy its numeric value from the JSON response.

#### Configuring your DSID

Configure a DSID if you want iSubRip to retry failed anonymous requests for movies that the account owns or has rented.  
If multiple methods are configured, `--dsid` overrides the `ISUBRIP_DSID` environment variable, which overrides `config.toml`.

The configuration file is recommended for regular use:

```toml
[scrapers.appletv]
dsid = "1234567890"
```

You can instead use an environment variable:

```shell
# Linux / macOS
export ISUBRIP_DSID="1234567890"

# Windows PowerShell
$env:ISUBRIP_DSID = "1234567890"
```

For a one-off run, you can use the command-line flag:

```shell
isubrip --dsid 1234567890 <URL>
```

> [!WARNING]
> The DSID is a numeric Apple account identifier.
> It is not a password or authentication cookie, but it is persistent, tied to your account, and should not be shared publicly.
>
> Command-line arguments may be saved in shell history or visible to other local processes. It is safer to configure
> the DSID using the environment variable or the configuration file.

#### DSID troubleshooting

- If the response from [ph2.tv.apple.com/settings](https://ph2.tv.apple.com/settings) contains `"message": "Sign-In Required"`, make sure you authenticated on the Apple TV Billing page, even if you are already signed in on the main Apple TV website.
- Confirm that the DSID belongs to the Apple account that owns the movie or has an active rental.
- An Apple HTTP 401, 403, or 404 can mean that the movie package is unavailable, the account is not entitled to the title, the rental expired, or Apple changed the manifest access flow.

## 📜 Logs
Log files are created for each run in the following paths, depending on your operating system:

**Windows**: `%USERPROFILE%\.isubrip\logs`  
**Linux / macOS**: `$HOME/.isubrip/logs`  

Log rotation (deletion of old files once a certain number of files is reached) can be configured in the configuration file using the `general.log-rotation-size` setting. The default value is `15`.

For more details, see the [example configuration](https://github.com/MichaelYochpaz/iSubRip/blob/main/example-config.toml).


## 📓 Changelog
The changelog for the latest, and all previous versions, can be found [here](https://github.com/MichaelYochpaz/iSubRip/blob/main/CHANGELOG.md).

## 👨🏽‍💻 Contributing

This project is open-source but currently lacks the infrastructure to fully support external contributions.

If you wish to contribute, please open an issue first to discuss your proposed changes to avoid working on something that might not be accepted.

## 🙏🏽 Support
If you find this project helpful, please consider supporting it by:
- 🌟 Starring the repository
- 💖 [Sponsoring the project](https://github.com/sponsors/MichaelYochpaz)

## 📝 End User License Agreement
By using iSubRip, you agree to the following terms:

1. **Disclaimer of Affiliation**: iSubRip is an independent, open-source project. It is not affiliated with, endorsed by, or in any way officially connected to Apple Inc., iTunes, or Apple TV.
2. **Educational Purpose**: This tool is developed and provided for educational and research purposes only. It demonstrates techniques for accessing and processing subtitle data from HLS playlists for Apple TV / iTunes content the user is entitled to access.
3. **User Responsibility and Compliance**: Any use of iSubRip is solely at the user's own risk and discretion. Users are responsible for ensuring that their use of the tool complies with all applicable laws, regulations, and terms of service of the content providers. This includes adhering to local, state, national, and international laws and regulations.
4. **Limitation of Liability**: The developers of iSubRip shall not be held responsible for any legal consequences arising from the use of this tool. This includes, but is not limited to, claims of copyright infringement, intellectual property violations, or breaches of terms of service of content providers. Users assume all risks associated with acquiring and using subtitle data through this tool.

By using iSubRip, you acknowledge that you have read, understood, and agree to be bound by this agreement's terms and conditions.

## ⚖️ License
This project is licensed under the MIT License. For more details, see the [LICENSE file](https://github.com/MichaelYochpaz/iSubRip/blob/main/LICENSE).
