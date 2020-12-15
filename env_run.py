#!/usr/bin/env python

from enum import Enum
from pathlib import Path
from pprint import pformat, pprint
from typing import Dict, List

import toml
from pydantic import (
    BaseModel,
    BaseSettings,
    Field,
    PyObject,
    RedisDsn,
    PostgresDsn,
    validator,
)


class ComposeSettings(BaseModel):
    container: str = None
    compose = True


class EnvType(str, Enum):
    compose = "compose"
    native = "native"
    vagrant = "vagrant"


def guess_env_type():
    if Path(".vagrant").exists():
        return EnvType.vagrant
    else:
        return EnvType.native

class CommandSettings(BaseModel):
    type: EnvType = Field(default_factory=guess_env_type)
    # type: EnvType = None
    compose: ComposeSettings = None

    # class Config:
    #     validate_all = True

    @validator("type", pre=True)
    def guess_type(cls, v):
        print("guess_type")
        if v is not None:
            return v
        return "vagrant"

    # @validator("type", pre=True)
    # def guess_type(cls, v):
    #     print("guess_type")
    #     if v is not None:
    #         return v
    #     return "vagrant"


class Settings(BaseSettings):
    default: CommandSettings = {}
    commands: Dict[str, CommandSettings] = {}

    class Config:
        env_prefix = "erun_"


def main():
    # settings = Settings(**{"docker-compose": "cool"})
    # settings = Settings(
    #     **{
    #         "commands": {"black": {"truc": "asd"}},
    #         "default": {"truc": 4},
    #     }
    # )

    file_config = toml.loads(open(".erun.toml").read())
    print("file_config:", pformat(file_config))
    settings = Settings(**file_config)

    # settings = Settings()

    pprint(settings.dict())


if __name__ == "__main__":
    main()