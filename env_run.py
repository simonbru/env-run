#!/usr/bin/env python

import logging
import os
import shlex
import subprocess
import sys
from enum import Enum, IntEnum
from pathlib import Path
from pprint import pformat, pprint
from typing import Dict, List, Literal, Union
import typing

import toml
from pydantic import (
    BaseModel,
    BaseSettings,
    Field,
    validator,
)

logger = logging.getLogger("erun")


# class LogLevel(str, Enum):
#     """
#     See `logging._nameToLevel`
#     """
#     CRITICAL = "CRITICAL"
#     FATAL = "FATAL"
#     ERROR = "ERROR"
#     WARN = "WARN"
#     WARNING = "WARNING"
#     INFO = "INFO"
#     DEBUG = "DEBUG"


# class LogLevel(Enum):
#     """
#     See `logging._nameToLevel`
#     """
#     CRITICAL = logging.CRITICAL
#     FATAL = logging.FATAL
#     ERROR = logging.ERROR
#     WARN = logging.WARN
#     WARNING = logging.WARNING
#     INFO = logging.INFO
#     DEBUG = logging.DEBUG


LogLevel = Literal[
    "CRITICAL",
    "FATAL",
    "ERROR",
    "WARN",
    "WARNING",
    "INFO",
    "DEBUG",
]


class Preset(str, Enum):
    compose = "compose"
    native = "native"
    vagrant = "vagrant"
    vssh = "vssh"


class Placeholder(str, Enum):
    cmd = "{cmd}"
    args = "{args}"
    shell_args = "{shell_args}"

    ANY_ARGS = {args, shell_args}


def guess_preset():
    current_dir = Path().resolve()
    for path in (current_dir, *current_dir.parents):
        if path.joinpath(".vagrant/vssh.cfg").exists():
            return Preset.vssh
        elif path.joinpath(".vagrant").exists():
            return Preset.vagrant
    return Preset.native


# def default_args(cls, v, values):
#     logger.debug("default_args")
#     if v is not None:
#         return v
#     elif values["preset"] in (Preset.vagrant, Preset.vssh):
#         return [Placeholder.shell_args]
#     else:
#         return [Placeholder.args]


class CommandSettings(BaseModel):
    preset: Preset = Field(default_factory=guess_preset)
    # preset: Preset = Field()
    prefix: List[str] = None
    args: List[Union[Placeholder, str]] = None
    # type: EnvType = None

    # class Config:
    #     validate_all = True

    # @validator("preset", pre=True, always=True)
    # def guess_preset(cls, v):
    #     logger.debug("guess_preset")
    #     if v is not None:
    #         return v
    #     return "vagrant"

    @validator("prefix", pre=True, always=True)
    def default_prefix(cls, v, values):
        if v is not None:
            return v
        elif values.get("preset") == Preset.vagrant:
            return ["vagrant", "ssh", "--"]
        elif values.get("preset") == Preset.vssh:
            return ["vssh"]
        else:
            return []

    # @validator("args", pre=True, always=True)
    # def default_args(cls, v, values):
    #     logger.debug("default_args")
    #     if v is not None:
    #         return v
    #     elif values["preset"] in (Preset.vagrant, Preset.vssh):
    #         return [Placeholder.shell_args]
    #     else:
    #         return [Placeholder.args]

    @validator("args", each_item=True)
    def clean_args(cls, v):
        try:
            return Placeholder(v)
        except ValueError:
            return v

    @validator("args", always=True)
    def default_placeholders(cls, v, values):
        """
        Set default args and append placeholders to args if not already specified.
        """
        if v is None:
            v = [Placeholder.cmd]

        if any(arg in Placeholder.ANY_ARGS for arg in v):
            return v
        elif values.get("preset") in (Preset.vagrant, Preset.vssh):
            return [*v, Placeholder.shell_args]
        else:
            return [*v, Placeholder.args]


class Settings(BaseSettings):
    default: CommandSettings = {}
    commands: Dict[str, CommandSettings] = {}
    log: LogLevel = "INFO"

    class Config:
        env_prefix = "erun_"


def read_raw_settings():
    current_dir = Path().resolve()
    for path in (current_dir, *current_dir.parents):
        config_path = path / ".erun.toml"
        if config_path.exists():
            logger.debug(f"Read configuration from: %s", config_path)
            raw_data = config_path.read_text()
            return toml.loads(raw_data)
    return {}


def run_command(settings: Settings, args: List[str]) -> int:
    command, *args = args
    if command in settings.commands:
        command_settings = settings.commands[command]
    else:
        command_settings = settings.default
    final_args = command_settings.prefix.copy()
    for settings_arg in command_settings.args:
        if settings_arg == Placeholder.cmd:
            final_args.append(command)
        elif settings_arg == Placeholder.args:
            final_args += args
        elif settings_arg == Placeholder.shell_args:
            final_args += [shlex.quote(arg) for arg in args]
        else:
            final_args.append(settings_arg)
    logger.debug("final_args: %s", final_args)
    result = subprocess.run(final_args)
    return result.returncode


def main():
    # settings = Settings(**{"docker-compose": "cool"})
    # settings = Settings(
    #     **{
    #         "commands": {"black": {"truc": "asd"}},
    #         "default": {"truc": 4},
    #     }
    # )

    # file_config = toml.loads(open(".erun.toml").read())
    # logger.debug("file_config:", pformat(file_config))
    # settings = Settings(**file_config)
    logging.basicConfig(style="{", format="{message}")
    # Manually read log level from environment to display log messages before
    # settings are parsed. It will be reset according to parsed settings.
    early_log_level = os.environ.get("ERUN_LOG")
    if early_log_level and early_log_level in typing.get_args(LogLevel):
        logger.setLevel(early_log_level)

    raw_setings = read_raw_settings()
    logger.debug("raw_setings:", pformat(raw_setings))
    settings = Settings(**raw_setings)
    # print(settings.log)
    # print(logger.getEffectiveLevel())
    # print(logger.isEnabledFor(logging.DEBUG))
    # import ipdb; ipdb.set_trace()

    # settings = Settings()
    logger.setLevel(settings.log)
    logger.debug("settings: %s", pformat(settings.dict()))
    args = sys.argv[1:]
    if not args:
        print("Usage: erun COMMAND [...ARGS]", file=sys.stderr)
        sys.exit(1)
    exit_code = run_command(settings, args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()