from __future__ import annotations

from collections.abc import Callable

from local_ai_control_center_installer.session import InstallerSession


NO_WINDOWS_STRATEGY_ERROR = (
    "No supported Windows TurboQuant install path is currently packaged."
)

StrategyResolver = Callable[[], object | None]
StrategyInstaller = Callable[[InstallerSession, object], InstallerSession | None]


def apply_turboquant(
    session: InstallerSession,
    *,
    resolve_windows_strategy: StrategyResolver | None = None,
    install_strategy: StrategyInstaller | None = None,
) -> InstallerSession:
    if session.attempt_turboquant is not True:
        session.turboquant_status = "skipped"
        session.turboquant_error = None
        return session

    if not _core_prerequisites_ready(session):
        session.turboquant_status = "skipped"
        session.turboquant_error = None
        return session

    resolve_windows_strategy = resolve_windows_strategy or _resolve_packaged_windows_strategy
    strategy = resolve_windows_strategy()
    if strategy is None:
        session.turboquant_status = "failed"
        session.turboquant_error = NO_WINDOWS_STRATEGY_ERROR
        return session

    install_strategy = install_strategy or _install_packaged_windows_strategy
    try:
        updated = install_strategy(session, strategy) or session
    except Exception as exc:
        session.turboquant_status = "failed"
        session.turboquant_error = str(exc)
        return session

    if updated.turboquant_status == "skipped":
        updated.turboquant_status = "ready"
    if updated.turboquant_status == "ready":
        updated.turboquant_error = None
    return updated


def _core_prerequisites_ready(session: InstallerSession) -> bool:
    return (
        session.bootstrap_status == "ready"
        and session.runtime_payload_status == "ready"
        and session.server_verification_status == "ready"
        and session.opencode_artifact_status == "ready"
        and session.opencode_verification_status == "ready"
    )


def _resolve_packaged_windows_strategy() -> object | None:
    return None


def _install_packaged_windows_strategy(
    session: InstallerSession,
    strategy: object,
) -> InstallerSession:
    del strategy
    session.turboquant_status = "ready"
    session.turboquant_error = None
    return session
