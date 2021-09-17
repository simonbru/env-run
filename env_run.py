#!/usr/bin/env python

import argparse
import logging
import os
import shlex
import subprocess
import sys
import typing
from enum import Enum
from pathlib import Path
from pprint import pformat
from typing import Dict, List, Literal, Union

import toml
from pydantic import (
    BaseModel,
    BaseSettings,
    Field,
    validator,
)

logger = logging.getLogger("erun")


# See `logging._nameToLevel`
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


class CommandSettings(BaseModel):
    preset: Preset = Field(default_factory=guess_preset)
    prefix: List[str] = None
    args: List[Union[Placeholder, str]] = None

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

    @validator("args", each_item=True)
    def parse_args(cls, v):
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

    @validator("log", pre=True)
    def validate_log(cls, v, field):
        if not v:
            return field.default
        return v.upper()

    class Config:
        env_prefix = "erun_"


def read_raw_settings():
    current_dir = Path().resolve()
    for path in (current_dir, *current_dir.parents):
        config_path = path / ".erun.toml"
        if config_path.exists():
            logger.debug("Read configuration from: %s", config_path)
            raw_data = config_path.read_text()
            return toml.loads(raw_data)
    return {}


def run_command(settings: Settings, args: List[str], dry_run: bool = False) -> int:
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
    if dry_run:
        print("Would run:")
        print(shlex.join(final_args))
        return 0
    else:
        result = subprocess.run(final_args)
        return result.returncode


def main():
    logging.basicConfig(style="{", format="{message}")

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", "-n", action="store_true")
    # Use argparse.PARSER to ignore option arguments (e.g. "-n")
    # after the first positional argument.
    parser.add_argument("ARGS", nargs=argparse.PARSER)
    options = parser.parse_args()

    # Manually read log level from environment to display log messages before
    # settings are parsed. It will be reset according to parsed settings.
    early_log_level = (os.environ.get("ERUN_LOG") or "").upper()
    if early_log_level and early_log_level in typing.get_args(LogLevel):
        logger.setLevel(early_log_level)

    # Read and apply settings
    raw_setings = read_raw_settings()
    logger.debug("raw_setings: %s", pformat(raw_setings))
    settings = Settings(**raw_setings)
    logger.setLevel(settings.log)
    logger.debug("settings: %s", pformat(settings.dict()))

    exit_code = run_command(settings, options.ARGS, dry_run=options.dry_run)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
