from __future__ import annotations

from pathlib import Path

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.state_helpers import (
    action_result,
)


def load_logs_result(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    log_paths = [
        config.install_root / "logs" / "install.log",
        config.install_root / "logs" / "runtime-server.log",
        config.install_root / "logs" / "opencode-launch.log",
    ]
    available = [path for path in log_paths if path.is_file()]
    if not available:
        return action_result(
            "ok",
            "logs",
            "Nema dostupnih logova u install root-u.",
            stdout="Nema log fajlova u install root-u.",
        )

    sections: list[str] = []
    for path in available:
        sections.append(f"===== {path.name} =====")
        sections.append(_tail_text(path, max_lines=120))
        sections.append("")

    return action_result(
        "ok",
        "logs",
        f"Ucitan je pregled {len(available)} log fajla.",
        stdout="\n".join(sections).strip(),
    )


def _tail_text(path: Path, *, max_lines: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "Log nije mogao da se procita."
    if len(lines) <= max_lines:
        return "\n".join(lines) if lines else "(prazan log)"
    return "\n".join(lines[-max_lines:])
