from __future__ import annotations

import os.path
import typing
from copy import deepcopy
from enum import Enum
from typing import Any, NamedTuple, Type

import tomli
from mergedeep import merge

from isubrip.utils import check_type, single_to_list


class DuplicateBehavior(Enum):
    """
    An Enum representing optional behaviors for when a duplicate config key is found.

    Attributes:
        OVERWRITE: Overwrite the existing value with the new value.
        IGNORE: Ignore the new value and keep the existing value.
        RAISE_ERROR: Raise an error.
    """
    OVERWRITE = 1
    IGNORE = 2
    RAISE_ERROR = 3


class SpecialConfigType(Enum):
    """
    An Enum representing special config value properties to validate.

    Attributes:
        EXISTING_FILE_PATH: The value must be of a path to an existing file.
        EXISTING_FOLDER_PATH: The value must be of a path to an existing folder.
    """
    EXISTING_FILE_PATH = 1
    EXISTING_FOLDER_PATH = 2


class ConfigSetting(NamedTuple):
    """
    A NamedTuple representing a config setting.

    Attributes:
        key (str): Dictionary key used to access the setting.
        type (type): Variable type of the value of the setting. Used for validation.
        category (str | list[str], optional): A category that the setting is under.
            Categories are used to group related settings' keys together in a sub-dictionary.
            A list can be used to nest categories (first item is the top-level category). Defaults to None.
        required (bool, optional): Whether the setting is required. Defaults to False.
        enum_type (type[Enum], optional): An Enum that the settings values will be converted to. Defaults to None.
        special_type (SpecialConfigType | list[SpecialConfigType], optional): A special property of the setting's value
            to validate, represented by a SpecialConfigType value. Defaults to None.
    """
    key: str
    # TODO: Use `types.UnionType` instead of `typing._UnionGenericAlias`, once minimum Python version >= 3.10.
    # TODO: Update 'InvalidConfigType' exception as well.
    type: type | typing._UnionGenericAlias  # type: ignore[name-defined]
    category: str | list[str] | None = None
    required: bool = False
    enum_type: Type[Enum] | None = None
    special_type: SpecialConfigType | list[SpecialConfigType] | None = None

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, ConfigSetting):
            return self.key == other.key and self.category == other.category
        return False


class Config:
    """A class for managing iSubRip config files."""
    def __init__(self, config_settings: list[ConfigSetting] | None = None, config_data: dict | None = None):
        """
        Create a new Config instance.

        Args:
            config_settings (list[ConfigSetting], optional): A list of ConfigSettings objects
                that will be used for validations. Defaults to None.
            config_data (dict, optional): A dict of config data to add to the config. Defaults to None.
        """
        self._config_settings: list = []
        self._config_data: dict = {}

        if config_settings:
            self.add_settings(config_settings, check_config=False)

        if config_data:
            self._config_data = deepcopy(config_data)

    def __getattr__(self, key: str) -> Any:
        """
        Allow access to config settings using attributes.

        Args:
            key (str): Config key to get.

        Returns:
            Any: The corresponding value for the key in the config.
        """
        if self._config_data and key in self._config_data:
            return self._config_data[key]

        else:
            raise AttributeError(f"Attribute \'{key}\' does not exist.")

    def __getitem__(self, key: str) -> Any:
        """
        Allow access to config settings using dict-like syntax.

        Args:
            key (str): Config key to get.

        Returns:
            Any: The corresponding value for the key in the config.
        """
        return self._config_data[key]

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a config value.

        Args:
            key (str): Config key to get.
            default (Any, optional): Default value to return if the key does not exist. Defaults to None.

        Returns:
            Any: The corresponding value for the key in the config or the default value if the key does not exist.
        """
        return self._config_data.get(key, default)

    @property
    def data(self):
        return self._config_data

    def add_settings(self, config_settings: ConfigSetting | list[ConfigSetting],
                     duplicate_behavior: DuplicateBehavior = DuplicateBehavior.OVERWRITE,
                     check_config: bool = True) -> None:
        """
        Add new config settings to the config.

        Args:
            config_settings (ConfigSetting | list[ConfigSetting]): A ConfigSetting object or a list of ConfigSetting
                objects to add to the config.
            duplicate_behavior (DuplicateBehavior, optional): Behaviour to apply if a duplicate is found.
                Defaults to DuplicateBehavior.OVERWRITE.
            check_config (bool, optional): Whether to check the config after loading it. Defaults to True.
        """
        config_settings_copy = deepcopy(single_to_list(config_settings))

        for config_setting in config_settings_copy:
            if config_setting in self._config_settings:
                if duplicate_behavior == DuplicateBehavior.OVERWRITE:
                    self._config_settings.remove(config_setting)
                    self._config_settings.append(config_setting)

                elif duplicate_behavior == DuplicateBehavior.RAISE_ERROR:
                    raise ValueError(f"Duplicate config setting: {config_setting}")

            else:
                self._config_settings.append(config_setting)

        if check_config:
            self.check()

    def loads(self, config_data: str, check_config: bool = True) -> None:
        """
        Parse a tomli config from a string.

        Args:
            config_data (str): Config file data as a string.
            check_config (bool, optional): Whether to check the config after loading it. Defaults to True.

        Raises:
            FileNotFoundError: Config file could not be found in the specified path.
            TOMLDecodeError: Config file is not a valid TOML file.
            ConfigValueMissing: A required config value is missing.
            InvalidConfigValue: An invalid value was used in the config file.
        """
        # Load settings from default config file
        loaded_data: dict = tomli.loads(config_data)

        if self._config_data:
            temp_config = dict(merge(self._config_data, loaded_data))

        else:
            temp_config = loaded_data

        self._config_data = temp_config

        if check_config and self._config_settings:
            self.check()

    @staticmethod
    def _map_config_settings(settings: list[ConfigSetting], data: dict) -> dict[ConfigSetting, Any]:
        """
        Map config settings to their values.
        This function wil also unflatten data.

        Args:
            settings (list[ConfigSetting]): A list or tuple of ConfigSettings objects.
            data (dict): A dictionary containing the config data.

        Returns:
            dict[ConfigSetting, Any]: A dictionary mapping config settings to their values.
        """
        mapped_settings: dict = {}

        for setting in settings:
            if setting.category:
                setting_categories = single_to_list(setting.category)
                config_dict_iter: dict = data

                for setting_category in setting_categories:
                    if setting_category not in config_dict_iter:
                        mapped_settings[setting] = None
                        break

                    config_dict_iter = config_dict_iter[setting_category]

            else:
                config_dict_iter = data

            if setting.key not in config_dict_iter:
                mapped_settings[setting] = None

            else:
                value = config_dict_iter[setting.key]
                enum_type = setting.enum_type

                if enum_type is not None:
                    try:
                        value = enum_type(value)

                    except ValueError as e:
                        setting_path = '.'.join(single_to_list(setting.category))
                        raise InvalidConfigValueEnum(setting_path=setting_path,
                                                     value=value, enum_type=enum_type) from e

                if type(value) in (list, tuple) and len(value) == 0:
                    value = None

                special_types = single_to_list(setting.special_type)

                if SpecialConfigType.EXISTING_FILE_PATH in special_types:
                    value = value.rstrip(r"\/")

                mapped_settings[setting] = value

        return mapped_settings

    def check(self) -> None:
        """
        Check whether the config is valid by comparing config's data to the config settings.
        Raises an error if an invalid value is found.

        Raises:
            MissingConfigValue: A required config value is missing.
            InvalidConfigValue: An invalid value was used in the config file.
        """
        if self._config_data is None or not self._config_settings:
            return

        mapped_config = Config._map_config_settings(self._config_settings, self._config_data)

        for setting, value in mapped_config.items():
            if isinstance(setting.category, (list, tuple)):
                setting_path = '.'.join(setting.category) + f".{setting.key}"

            elif isinstance(setting.category, str):
                setting_path = setting.category + f".{setting.key}"

            else:
                setting_path = setting.key

            if value is None:
                if setting.required:
                    raise MissingRequiredConfigSetting(setting_path=setting_path)

                else:
                    continue

            if setting.enum_type is None and not check_type(value, setting.type):
                raise InvalidConfigType(setting_path=setting_path, value=value, expected_type=setting.type)

            special_types = single_to_list(setting.special_type)

            if SpecialConfigType.EXISTING_FILE_PATH in special_types:
                if not os.path.isfile(value):
                    raise InvalidConfigFilePath(setting_path=setting_path, value=value)

            elif SpecialConfigType.EXISTING_FOLDER_PATH in special_types:
                if not os.path.isdir(value):
                    raise InvalidConfigFolderPath(setting_path=setting_path, value=value)


class ConfigException(Exception):
    pass


class MissingRequiredConfigSetting(ConfigException):
    """A required config value is missing."""
    def __init__(self, setting_path: str):
        super().__init__(f"Missing required config value: '{setting_path}'.")


class InvalidConfigValue(ConfigException):
    """An invalid config setting has been set."""
    def __init__(self, setting_path: str, value: Any, additional_note: str | None = None):
        message = f"Invalid config value for '{setting_path}': '{value}'."

        if additional_note:
            message += f"\n{additional_note}"

        super().__init__(message)


class InvalidConfigValueEnum(InvalidConfigValue):
    """An invalid config value of an enum type setting has been set."""
    def __init__(self, setting_path: str, value: Any, enum_type: type[Enum]):
        enum_options = ', '.join([f"'{option.name}'" for option in enum_type])

        super().__init__(
            setting_path=setting_path,
            value=value,
            additional_note=f"Value can only be one of: {enum_options}.",
        )


class InvalidConfigType(InvalidConfigValue):
    """An invalid config value type has been set."""
    def __init__(self, setting_path: str, expected_type: type | typing._UnionGenericAlias, value: Any):
        expected_type_str = expected_type.__name__ if hasattr(expected_type, '__name__') else str(expected_type)
        value_type_str = type(value).__name__ if hasattr(type(value), '__name__') else str(type(value))

        super().__init__(
            setting_path=setting_path,
            value=value,
            additional_note=f"Expected type: '{expected_type_str}'. Received: '{value_type_str}'.",
        )


class InvalidConfigFilePath(InvalidConfigValue):
    """An invalid config value of a file path has been set."""
    def __init__(self, setting_path: str, value: str):
        super().__init__(
            setting_path=setting_path,
            value=value,
            additional_note=f"File '{value}' not found.",
        )


class InvalidConfigFolderPath(InvalidConfigValue):
    """An invalid config value of a folder path has been set."""
    def __init__(self, setting_path: str, value: str):
        super().__init__(
            setting_path=setting_path,
            value=value,
            additional_note=f"Folder '{value}' not found.",
        )
