from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List
from xml.etree import ElementTree

import requests
from config import Config


class VmixInputType(Enum):
    IMAGE = "Image"
    VIDEO = "Video"
    AUDIO = "Audio"
    VIDEO_LIST = "VideoList"
    GT = "GT"
    PRODUCTION_CLOCKS = "ProductionClocks"
    XAML = "Xaml"
    NDI = "NDI"
    CAPTURE = "Capture"
    COLOUR = "Colour"
    PLACEHOLDER = "Placeholder"
    UNKNOWN = "UNKNOWN"

    @staticmethod
    def parse(t: str) -> VmixInputType:
        try:
            return VmixInputType(t)
        except Exception:
            return VmixInputType.UNKNOWN


@dataclass(frozen=True)
class VmixInput:
    key: str
    number: int
    type: VmixInputType
    title: str
    short_title: str


@dataclass(frozen=True)
class VmixState:
    inputs: List[VmixInput]


class VmixClient:
    def __init__(self, config: Config) -> None:
        self._cfg = config

    def set_text(self, input: str, value: str) -> None:
        response = requests.get(
            url=self._cfg.vmix_base_url,
            params={"Function": "SetText", "Input": input, "Value": value},
            timeout=self._cfg.timeout_seconds,
        )
        response.raise_for_status()

    def list_remove_all(self, input: str) -> None:
        response = requests.get(
            url=self._cfg.vmix_base_url,
            params={"Function": "ListRemoveAll", "Input": input},
            timeout=self._cfg.timeout_seconds,
        )
        response.raise_for_status()

    def list_add(self, input: str, file: Path) -> None:
        response = requests.get(
            url=self._cfg.vmix_base_url,
            params={
                "Function": "ListAdd",
                "Input": input,
                "Value": str(file.resolve()),
            },
            timeout=self._cfg.timeout_seconds,
        )
        response.raise_for_status()

    def restart_all(self) -> None:
        current_state = self.get_current_state()
        for inp in current_state.inputs:
            if inp.type in {VmixInputType.VIDEO, VmixInputType.VIDEO_LIST}:
                self.restart(inp.key)

    def restart(self, input: str) -> None:
        response = requests.get(
            url=self._cfg.vmix_base_url,
            params={"Function": "Restart", "Input": input},
            timeout=self._cfg.timeout_seconds,
        )
        response.raise_for_status()

    def get_current_state(self) -> VmixState:
        response = requests.get(
            url=self._cfg.vmix_base_url, timeout=self._cfg.timeout_seconds
        )
        response.raise_for_status()
        root = ElementTree.fromstring(response.text)
        inputs = root.find("./inputs")
        if inputs is None:
            raise ValueError(
                "XML parsing error: the vMix API response is missing the list of inputs."
            )
        return VmixState(
            [
                VmixInput(
                    key=inp.attrib["key"],
                    number=int(inp.attrib["number"]),
                    type=VmixInputType.parse(inp.attrib["type"]),
                    title=inp.attrib["title"],
                    short_title=inp.attrib["shortTitle"],
                )
                for inp in inputs
            ]
        )
