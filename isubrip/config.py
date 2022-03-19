from typing import Any, Union

import tomli
from mergedeep import merge

from isubrip.enums import SubtitlesFormat
from isubrip.exceptions import ConfigValueMissing, InvalidConfigValue
from isubrip.namedtuples import ConfigSetting


class Config:
    """A class for managing iSubRip config files."""

    def __init__(self) -> None:
        """Create a new ConfigManager instance."""
        self.config_dict: dict = {}
        self.config_loaded: bool = False

        # List of valid subtitle formats as strings
        self._valid_subtitle_formats: set = set(item.name.upper() for item in SubtitlesFormat)

    def __getattr__(self, key: str) -> Any:
        """Allow access to config settings using attributes.

        Args:
            key (str): Config key to get.

        Returns:
            Any: The corresponding value for the key in the config.
        """
        if key in self.config_dict:
            return self.config_dict[key]

    def loads(self, config_data: str) -> None:
        """Parse a tomli iSubRip config from a string.

        Args:
            config_data (str): Config file data as a string.

        Raises:
            FileNotFoundError: Config file could not be found in the specified path.
            TOMLDecodeError: Config file is not a valid TOML file.
            ConfigValueMissing: A required config value is missing.
            InvalidConfigValue: An invalid value was used in the config file.

        Returns:
            dict: A dictionary containing all settings.
        """

        # Load settings from default config file
        loaded_data: dict = tomli.loads(config_data)

        if not self.config_loaded:
            temp_config: dict = loaded_data
            self.config_loaded = True

        else:
            temp_config: dict = dict(merge(self.config_dict, loaded_data))

        # Convert download format from string to SubtitlesFormat enum
        if isinstance(temp_config["downloads"]["format"], str) and temp_config["downloads"]["format"].upper() in self._valid_subtitle_formats:
            temp_config["downloads"]["format"] = SubtitlesFormat[temp_config["downloads"]["format"].upper()]

        elif not isinstance(temp_config["downloads"]["format"], SubtitlesFormat):
            raise InvalidConfigValue(f"Invalid config value for downloads.format: {temp_config['downloads']['format']}")

        self._standardize_config_(temp_config)
        self.check_config(temp_config)
        self.config_dict = temp_config

    def _standardize_config_(self, config_dict: dict) -> None:
        """Standardize a config dictionary and fix issues.

        Args:
            config_dict (dict): Config dictionary to standardize.
        """
        # If languages list is empty, change it to None
        if not config_dict["downloads"]["languages"]:
            config_dict["downloads"]["languages"] = None

        # Remove a trialing slash / backslash from path
        if isinstance(config_dict["downloads"]["format"], str):
            config_dict["downloads"]["folder"] = config_dict["downloads"]["folder"].rstrip(r"\/")

        # Change ffmpeg-args value to None if empty
        if config_dict["ffmpeg"]["args"] == "":
            config_dict["ffmpeg"]["args"] = None

    def check_config(self, config_dict: dict) -> None:
        """Check the config for invalid values.
        Raises an error if an invalid value is found.
    
        Args:
            config_dict (dict): Config dictionary to check.

        Raises:
            ConfigValueMissing: A required config value is missing.
            InvalidConfigValue: An invalid value was used in the config file.
        """
        
        # List of config values and their corresponding types
        setting_list = [
            ConfigSetting("general", "check-for-updates", bool),
            ConfigSetting("downloads", "languages", Union[list, None]),
            ConfigSetting("downloads", "format", SubtitlesFormat),
            ConfigSetting("downloads", "folder", str),
            ConfigSetting("downloads", "zip", bool),
            ConfigSetting("scraping", "user-agent", str),
            ConfigSetting("ffmpeg", "path", str),
            ConfigSetting("ffmpeg", "args", Union[str, None])
            ]

        # Assure each config value exists and is of the correct type
        for setting in setting_list:
            if setting.category not in config_dict:
                raise ConfigValueMissing(f"Config category \'{setting.category}\' with required settings is missing.")

            if setting.key in config_dict[setting.category]:
                setting_value = config_dict[setting.category][setting.key]

                if not isinstance(setting_value, setting.type):
                    raise InvalidConfigValue(f"Invalid config value type for {setting.category}.{setting.key}: \'{setting_value}\'\
                    \nExpected {setting.type}, received: {type(setting_value)}.")

            else:
                raise ConfigValueMissing(f"Missing required config value: \'{setting.category}.{setting.key}\'")
