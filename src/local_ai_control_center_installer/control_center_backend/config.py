from dataclasses import dataclass
import os
from pathlib import Path

from local_ai_control_center_installer.platform_paths import default_install_root_for_platform

DEFAULT_INSTALL_ROOT = default_install_root_for_platform()


@dataclass(frozen=True)
class ControlCenterConfig:
    ui_host: str
    ui_port: int
    install_root: Path
    access_mode: str
    start_port: int = 3210
    end_port: int = 3299

    @property
    def ui_url(self) -> str:
        return f"http://{self.ui_host}:{self.ui_port}/"

    @property
    def control_center_config_root(self) -> Path:
        return self.install_root / "config" / "control-center"

    @property
    def active_model_config_path(self) -> Path:
        return self.install_root / "config" / "active-model.json"

    @property
    def runtime_endpoint_config_path(self) -> Path:
        return self.install_root / "config" / "runtime-endpoint.json"

    @property
    def opencode_managed_config_path(self) -> Path:
        return self.install_root / "config" / "opencode" / "managed-config.json"

    @property
    def custom_models_registry_path(self) -> Path:
        return self.control_center_config_root / "custom-models.json"

    @property
    def settings_path(self) -> Path:
        return self.control_center_config_root / "settings.json"

    @property
    def model_overrides_path(self) -> Path:
        return self.control_center_config_root / "model-overrides.json"

    @property
    def turboquant_config_path(self) -> Path:
        return self.control_center_config_root / "turboquant-config.json"

    @property
    def turboquant_presets_path(self) -> Path:
        return self.control_center_config_root / "turboquant-presets.json"

    @property
    def settings_profiles_path(self) -> Path:
        return self.control_center_config_root / "settings-profiles.json"

    @property
    def opencode_step_presets_path(self) -> Path:
        return self.control_center_config_root / "opencode-step-presets.json"

    @property
    def model_download_progress_path(self) -> Path:
        return self.control_center_config_root / "model-download-progress.json"

    @property
    def model_action_state_root(self) -> Path:
        return self.control_center_config_root / "model-actions"

    @property
    def browser_catalog_cache_path(self) -> Path:
        return self.control_center_config_root / "browser-catalog-cache.json"

    @property
    def update_progress_path(self) -> Path:
        return self.control_center_config_root / "update-progress.json"

    @property
    def benchmark_history_path(self) -> Path:
        return self.control_center_config_root / "benchmark-history.json"

    @property
    def benchmark_live_history_path(self) -> Path:
        return self.control_center_config_root / "benchmark-live-history.json"

    @property
    def benchmark_live_slots_snapshot_path(self) -> Path:
        return self.control_center_config_root / "benchmark-live-slots.json"

    @property
    def benchmark_run_state_path(self) -> Path:
        return self.control_center_config_root / "benchmark-run-state.json"

    @property
    def benchmark_batteries_path(self) -> Path:
        return self.control_center_config_root / "benchmark-batteries.json"

    @property
    def benchmark_saved_runs_path(self) -> Path:
        return self.control_center_config_root / "benchmark-saved-runs.json"

    @property
    def search_history_path(self) -> Path:
        return self.control_center_config_root / "search-history.json"

    @property
    def knowledge_sources_path(self) -> Path:
        return self.control_center_config_root / "knowledge-sources.json"

    @property
    def knowledge_history_path(self) -> Path:
        return self.control_center_config_root / "knowledge-history.json"

    @property
    def knowledge_index_path(self) -> Path:
        return self.control_center_config_root / "knowledge-index.sqlite3"

    @property
    def updates_download_root(self) -> Path:
        return self.install_root / "updates"


def get_config() -> ControlCenterConfig:
    raw_port = os.environ.get("LACC_UI_PORT", "3210").strip() or "3210"
    try:
        ui_port = int(raw_port)
    except ValueError:
        ui_port = 3210

    raw_install_root = (
        os.environ.get("LACC_INSTALL_ROOT")
        or os.environ.get("LOCAL_AI_CONTROL_CENTER_INSTALL_ROOT")
        or str(DEFAULT_INSTALL_ROOT)
    )
    install_root = Path(raw_install_root).expanduser().resolve()

    access_mode = (
        os.environ.get("LACC_UI_ACCESS_MODE", "local-only").strip().lower()
        or "local-only"
    )
    if access_mode not in {"local-only", "tailscale"}:
        access_mode = "local-only"

    return ControlCenterConfig(
        ui_host="127.0.0.1",
        ui_port=ui_port,
        install_root=install_root,
        access_mode=access_mode,
    )
