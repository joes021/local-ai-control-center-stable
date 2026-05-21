from dataclasses import asdict, dataclass, field


@dataclass
class DependencyRecord:
    name: str
    required: bool
    detected: bool = False
    version: str | None = None
    status: str = "unknown"
    install_offered: bool = False
    user_accepted_install: bool | None = None
    install_attempted: bool = False
    install_succeeded: bool | None = None
    blocking_reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class InstallerSession:
    bootstrap_status: str = "failed"
    product_installation_status: str = "incomplete"
    runtime_payload_status: str = "skipped"
    runtime_artifact_status: str = "skipped"
    starter_model_status: str = "skipped"
    active_model_config_status: str = "skipped"
    platform: str | None = None
    started_at: str | None = None
    existing_install_detected: bool = False
    install_mode: str | None = None
    install_root: str | None = None
    runtime_artifact_id: str | None = None
    runtime_artifact_path: str | None = None
    starter_model: str | None = None
    starter_model_path: str | None = None
    active_model_config_path: str | None = None
    runtime_metadata_path: str | None = None
    install_opencode: bool = False
    attempt_turboquant: bool = False
    additional_model_paths: list[str] = field(default_factory=list)
    last_successful_step: str | None = None
    failing_step: str | None = None
    error_message: str | None = None
    dependencies: list[DependencyRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
