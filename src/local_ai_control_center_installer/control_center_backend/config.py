from dataclasses import dataclass


@dataclass(frozen=True)
class ControlCenterConfig:
    ui_port: int = 3210
    start_port: int = 3210
    end_port: int = 3299


def get_config() -> ControlCenterConfig:
    return ControlCenterConfig()
