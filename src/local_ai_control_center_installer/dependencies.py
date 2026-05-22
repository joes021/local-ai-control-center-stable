from collections.abc import Callable

from local_ai_control_center_installer.session import DependencyRecord, InstallerSession


def evaluate_dependency(
    name: str,
    required: bool,
    detected_version: str | None,
) -> DependencyRecord:
    if detected_version:
        return DependencyRecord(
            name=name,
            required=required,
            detected=True,
            version=detected_version,
            status="ready",
        )
    return DependencyRecord(
        name=name,
        required=required,
        detected=False,
        status="missing-installable" if required else "warning",
        install_offered=required,
    )


def apply_dependency_decision(
    record: DependencyRecord,
    user_accepts_install: bool,
    install_fn: Callable[[DependencyRecord], bool],
) -> DependencyRecord:
    if record.detected:
        return record

    record.user_accepted_install = user_accepts_install
    if not user_accepts_install:
        if record.required:
            record.status = "missing-blocking"
            record.blocking_reason = _blocking_reason(record.name)
        return record

    record.install_attempted = True
    record.install_succeeded = bool(install_fn(record))
    if record.install_succeeded:
        record.detected = True
        record.status = "ready"
        record.blocking_reason = None
        return record

    record.status = "failed-install"
    if record.required:
        record.blocking_reason = _blocking_reason(record.name)
    return record


def scan_all_dependencies(
    session: InstallerSession,
    probes: dict[str, Callable[[], str | None]],
) -> InstallerSession:
    session.dependencies = [
        evaluate_dependency("python", required=True, detected_version=probes["python"]()),
    ]
    return session


def _blocking_reason(name: str) -> str:
    if name == "build-tools":
        return (
            "Required build-tools are unavailable, so server startup is not usable "
            "and the server cannot be used reliably."
        )
    return f"Required dependency '{name}' is unavailable, so the server cannot be used reliably."
