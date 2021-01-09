#!/usr/bin/env python

import shlex
import subprocess
import sys
from enum import Enum
from pathlib import Path
from pprint import pformat, pprint
from typing import Dict, List, Union

import toml
from pydantic import (
    BaseModel,
    BaseSettings,
    Field,
    validator,
)


class Preset(str, Enum):
    compose = "compose"
    native = "native"
    vagrant = "vagrant"
    vssh = "vssh"


class Placeholder(str, Enum):
    args = "{args}"
    shell_args = "{shell_args}"


def guess_preset():
    current_dir = Path().resolve()
    for path in (current_dir, *current_dir.parents):
        if path.joinpath(".vagrant/vssh.cfg").exists():
            return Preset.vssh
        elif path.joinpath(".vagrant").exists():
            return Preset.vagrant
    return Preset.native


# def default_args(cls, v, values):
#     print("default_args")
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
    args: List[Union[Placeholder, str]] = []
    # type: EnvType = None

    # class Config:
    #     validate_all = True

    # @validator("preset", pre=True, always=True)
    # def guess_preset(cls, v):
    #     print("guess_preset")
    #     if v is not None:
    #         return v
    #     return "vagrant"

    @validator("prefix", pre=True, always=True)
    def default_prefix(cls, v, values):
        print("default_prefix", v)
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
    #     print("default_args")
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
    def default_placeholder(cls, v, values):
        """
        Append placeholder to args if not already specified.
        """
        print("default_placeholder")
        # TODO: add placeholder for subcommand
        if any(isinstance(arg, Placeholder) for arg in v):
            return v
        elif values.get("preset") in (Preset.vagrant, Preset.vssh):
            return [*v, Placeholder.shell_args]
        else:
            return [*v, Placeholder.args]


# class SubCommandSettings(CommandSettings):
    


class Settings(BaseSettings):
    default: CommandSettings = {}
    commands: Dict[str, CommandSettings] = {}

    class Config:
        env_prefix = "erun_"


def read_raw_settings():
    current_dir = Path().resolve()
    for path in (current_dir, *current_dir.parents):
        config_path = path / ".erun.toml"
        if config_path.exists():
            raw_data = config_path.read_text()
            return toml.loads(raw_data)
    return {}


def run_command(settings: Settings, args: List[str]) -> int:
    if len(args) > 0 and args[0] in settings.commands:
        command = args[0]
        command_settings = settings.commands[command]
    else:
        command_settings = settings.default
    final_args = command_settings.prefix.copy()
    for settings_arg in command_settings.args:
        if settings_arg == Placeholder.args:
            final_args += args
        elif settings_arg == Placeholder.shell_args:
            final_args += [shlex.quote(arg) for arg in args]
        else:
            final_args.append(settings_arg)
    print("final_args:", pformat(final_args))
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
    # print("file_config:", pformat(file_config))
    # settings = Settings(**file_config)

    raw_config = read_raw_settings()
    print("raw_config:", pformat(raw_config))
    settings = Settings(**raw_config)
    
    # settings = Settings()

    pprint(settings.dict())
    # input()
    exit_code = run_command(settings, sys.argv[1:])
    sys.exit(exit_code)


if __name__ == "__main__":
    main()