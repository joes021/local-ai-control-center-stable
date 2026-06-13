from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import sys
import threading
import time
import webbrowser

from local_ai_control_center_installer.control_center_runtime import (
    DEFAULT_PANEL_PORT,
    DEFAULT_PANEL_URL,
    ControlCenterRuntimeDeployment,
    deploy_control_center_runtime,
    launch_control_center,
)


DEFAULT_STARTUP_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class StartupLaunchContext:
    install_root: Path
    panel_url: str
    health_url: str
    install_root_text: str


def build_startup_launch_context(install_root: str | Path) -> StartupLaunchContext:
    normalized_install_root = Path(install_root).expanduser().resolve()
    panel_url = DEFAULT_PANEL_URL
    return StartupLaunchContext(
        install_root=normalized_install_root,
        panel_url=panel_url,
        health_url=f"{panel_url.rstrip('/')}/health",
        install_root_text=str(normalized_install_root),
    )


def _open_browser(url: str) -> bool:
    try:
        if webbrowser.open(url):
            return True
    except Exception:  # noqa: BLE001
        pass
    if os.name == "nt" and hasattr(os, "startfile"):
        try:
            os.startfile(url)  # type: ignore[attr-defined]
            return True
        except Exception:  # noqa: BLE001
            return False
    return False


def build_python_startup_deployment(
    *,
    install_root: str | Path,
    current_python: str,
) -> ControlCenterRuntimeDeployment:
    normalized_install_root = Path(install_root).expanduser().resolve()
    python_executable = Path(current_python).expanduser().resolve()
    src_root = Path(__file__).resolve().parents[1]
    command = (
        str(python_executable),
        "-m",
        "local_ai_control_center_installer.control_center_panel",
        "--install-root",
        str(normalized_install_root),
        "--host",
        "127.0.0.1",
        "--port",
        str(DEFAULT_PANEL_PORT),
        "--access-mode",
        "local-only",
    )
    env_overrides = {
        "LACC_INSTALL_ROOT": str(normalized_install_root),
        "LACC_UI_PORT": str(DEFAULT_PANEL_PORT),
        "LACC_UI_ACCESS_MODE": "local-only",
        "PYTHONPATH": str(src_root),
    }
    panel_root = normalized_install_root / "control-center"
    return ControlCenterRuntimeDeployment(
        install_root=normalized_install_root,
        panel_root=panel_root,
        executable_path=python_executable,
        launcher_path=panel_root / "Open-RuntimePilot.cmd",
        command=command,
        url=DEFAULT_PANEL_URL,
        port=DEFAULT_PANEL_PORT,
        access_mode="local-only",
        strategy="python-startup-shortcut",
        env_overrides=env_overrides,
    )


def run_startup_sequence(
    *,
    install_root: str | Path,
    current_python: str | None = None,
    frozen: bool | None = None,
    frozen_executable: str | Path | None = None,
    timeout_seconds: float = DEFAULT_STARTUP_TIMEOUT_SECONDS,
    deployment_builder=build_python_startup_deployment,
    deploy_runtime=deploy_control_center_runtime,
    launch_runtime=launch_control_center,
    open_browser=_open_browser,
) -> ControlCenterRuntimeDeployment:
    if frozen:
        deployment = deploy_runtime(
            install_root,
            current_python=current_python,
            frozen=frozen,
            frozen_executable=frozen_executable,
        )
    else:
        deployment = deployment_builder(
            install_root=install_root,
            current_python=current_python or sys.executable,
        )
    launch_runtime(deployment, timeout_seconds=timeout_seconds)
    if not open_browser(deployment.url):
        raise RuntimeError(
            f"Browser nije mogao da se otvori za RuntimePilot portal: {deployment.url}"
        )
    return deployment


def run_control_center_startup_entry(
    argv: list[str] | None = None,
    *,
    ui_runner=None,
) -> int:
    parser = argparse.ArgumentParser(prog="RuntimePilot startup")
    parser.add_argument("--install-root", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_STARTUP_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)

    ui_runner = ui_runner or _run_startup_window
    context = build_startup_launch_context(args.install_root)
    return ui_runner(
        context=context,
        timeout_seconds=args.timeout_seconds,
        current_python=sys.executable,
        frozen=bool(getattr(sys, "frozen", False)),
        frozen_executable=sys.executable,
    )


def _run_startup_window(
    *,
    context: StartupLaunchContext,
    timeout_seconds: float,
    current_python: str,
    frozen: bool,
    frozen_executable: str,
) -> int:
    try:
        import tkinter as tk
    except Exception:  # noqa: BLE001
        run_startup_sequence(
            install_root=context.install_root,
            current_python=current_python,
            frozen=frozen,
            frozen_executable=frozen_executable,
            timeout_seconds=timeout_seconds,
        )
        return 0

    root = tk.Tk()
    root.title("RuntimePilot startup")
    root.configure(bg="#14110d")
    root.geometry("1060x560")
    root.minsize(900, 500)

    icon_path = context.install_root / "control-center" / "RuntimePilot.ico"
    try:
        if icon_path.is_file():
            root.iconbitmap(default=str(icon_path))
    except Exception:  # noqa: BLE001
        pass

    shell = tk.Frame(root, bg="#231e19", bd=1, relief="solid", padx=28, pady=24)
    shell.pack(fill="both", expand=True, padx=18, pady=18)

    brand = tk.Label(
        shell,
        text="RUNTIMEPILOT STARTUP",
        bg="#231e19",
        fg="#cbb089",
        font=("Segoe UI", 13, "normal"),
        anchor="w",
    )
    brand.pack(fill="x")

    title_label = tk.Label(
        shell,
        text="Panel se podiže",
        bg="#231e19",
        fg="#fff9ee",
        font=("Segoe UI", 28, "bold"),
        anchor="w",
        pady=12,
    )
    title_label.pack(fill="x")

    intro_label = tk.Label(
        shell,
        text="Pokrećem lokalni RuntimePilot i proveravam kada je portal spreman za rad u browseru.",
        bg="#231e19",
        fg="#ddd3c5",
        font=("Segoe UI", 15),
        justify="left",
        anchor="w",
    )
    intro_label.pack(fill="x")

    status_frame = tk.Frame(shell, bg="#1a1713", bd=1, relief="solid", padx=18, pady=16)
    status_frame.pack(fill="x", pady=(18, 0))

    status_title_var = tk.StringVar(value="Čekam health signal...")
    status_detail_var = tk.StringVar(
        value="Backend se podiže i čim potvrdi da je spreman, portal će se otvoriti automatski."
    )
    attempt_var = tk.StringVar(value="pokretanje")

    status_title_label = tk.Label(
        status_frame,
        textvariable=status_title_var,
        bg="#1a1713",
        fg="#fff8ec",
        font=("Segoe UI", 18, "bold"),
        anchor="w",
    )
    status_title_label.pack(fill="x")

    status_detail_label = tk.Label(
        status_frame,
        textvariable=status_detail_var,
        bg="#1a1713",
        fg="#ded4c6",
        font=("Segoe UI", 14),
        justify="left",
        anchor="w",
        wraplength=920,
        pady=8,
    )
    status_detail_label.pack(fill="x")

    progress_canvas = tk.Canvas(
        status_frame,
        height=10,
        bg="#2a241d",
        highlightthickness=1,
        highlightbackground="#69573a",
        bd=0,
    )
    progress_canvas.pack(fill="x", pady=(8, 0))
    progress_bar = progress_canvas.create_rectangle(0, 0, 220, 10, fill="#d9c29a", outline="#d9c29a")

    meta_frame = tk.Frame(shell, bg="#231e19")
    meta_frame.pack(fill="x", pady=(18, 0))

    def _make_meta_button(label: str, value: str, command) -> None:
        row = tk.Frame(meta_frame, bg="#231e19")
        row.pack(fill="x", pady=4)
        tk.Label(
            row,
            text=label,
            bg="#231e19",
            fg="#fff8ec",
            font=("Segoe UI", 12, "bold"),
            width=10,
            anchor="w",
        ).pack(side="left")
        tk.Button(
            row,
            text=value,
            command=command,
            bg="#3a3128",
            fg="#f7efe2",
            activebackground="#4a3e31",
            activeforeground="#fffaf2",
            relief="solid",
            bd=1,
            anchor="w",
            padx=10,
            pady=6,
            cursor="hand2",
        ).pack(side="left", fill="x", expand=True)

    def set_status(title: str, detail: str, attempt: str) -> None:
        status_title_var.set(title)
        status_detail_var.set(detail)
        attempt_var.set(attempt)

    def open_url(url: str) -> None:
        _open_browser(url)

    def open_install_folder() -> None:
        try:
            os.startfile(str(context.install_root))
            set_status(
                "Otvoren je RuntimePilot folder",
                "Sada možeš direktno da proveriš fajlove ili ručno dodaš antivirus exception samo za ovu lokaciju.",
                "folder otvoren",
            )
        except Exception:  # noqa: BLE001
            set_status(
                "Folder nije mogao da se otvori",
                "Windows nije uspeo da otvori RuntimePilot folder automatski.",
                "folder greška",
            )

    _make_meta_button("Portal", context.panel_url, lambda: open_url(context.panel_url))
    _make_meta_button("Provera", context.health_url, lambda: open_url(context.health_url))

    attempt_row = tk.Frame(meta_frame, bg="#231e19")
    attempt_row.pack(fill="x", pady=4)
    tk.Label(
        attempt_row,
        text="Stanje",
        bg="#231e19",
        fg="#fff8ec",
        font=("Segoe UI", 12, "bold"),
        width=10,
        anchor="w",
    ).pack(side="left")
    tk.Label(
        attempt_row,
        textvariable=attempt_var,
        bg="#231e19",
        fg="#ded4c6",
        font=("Segoe UI", 12),
        anchor="w",
    ).pack(side="left", fill="x", expand=True)

    action_row = tk.Frame(shell, bg="#231e19")
    action_row.pack(fill="x", pady=(18, 0))

    tk.Button(
        action_row,
        text="Otvori portal odmah",
        command=lambda: (open_url(context.panel_url), root.after(900, root.destroy)),
        bg="#c3a36b",
        fg="#17120d",
        activebackground="#d1b381",
        activeforeground="#17120d",
        relief="solid",
        bd=1,
        padx=14,
        pady=8,
        cursor="hand2",
    ).pack(side="left", padx=(0, 10))

    tk.Button(
        action_row,
        text="Otvori RuntimePilot folder",
        command=open_install_folder,
        bg="#332a22",
        fg="#f5eee2",
        activebackground="#43372c",
        activeforeground="#fffaf2",
        relief="solid",
        bd=1,
        padx=14,
        pady=8,
        cursor="hand2",
    ).pack(side="left", padx=(0, 10))

    def copy_install_path() -> None:
        try:
            root.clipboard_clear()
            root.clipboard_append(context.install_root_text)
            root.update_idletasks()
            set_status(
                "Putanja je kopirana",
                "Možeš odmah da je nalepiš u antivirus exception polje ako bude potrebno.",
                "putanja kopirana",
            )
        except Exception:  # noqa: BLE001
            set_status(
                "Kopiranje nije uspelo",
                "Clipboard nije mogao da prihvati putanju, pa koristi dugme za otvaranje foldera.",
                "clipboard greška",
            )

    tk.Button(
        action_row,
        text="Kopiraj putanju za exception",
        command=copy_install_path,
        bg="#332a22",
        fg="#f5eee2",
        activebackground="#43372c",
        activeforeground="#fffaf2",
        relief="solid",
        bd=1,
        padx=14,
        pady=8,
        cursor="hand2",
    ).pack(side="left")

    notice = tk.Label(
        shell,
        text=(
            "Ovaj startup više ne koristi mshta.exe. Radi kao običan lokalni Python GUI koji podiže RuntimePilot, "
            "čeka health i tek onda otvara portal u podrazumevanom browseru."
        ),
        bg="#231e19",
        fg="#d5b884",
        font=("Segoe UI", 12),
        justify="left",
        anchor="w",
        wraplength=940,
        pady=20,
    )
    notice.pack(fill="x")

    result: dict[str, object] = {"deployment": None, "error": None}
    started_at = time.monotonic()
    finished = threading.Event()
    slow_message_shown = {"value": False}
    close_scheduled = {"value": False}
    pulse_state = {"offset": 0}

    def pulse_progress() -> None:
        pulse_state["offset"] = (pulse_state["offset"] + 28) % 720
        left = pulse_state["offset"]
        progress_canvas.coords(progress_bar, left, 0, left + 220, 10)
        if not finished.is_set():
            root.after(120, pulse_progress)

    def worker() -> None:
        try:
            result["deployment"] = run_startup_sequence(
                install_root=context.install_root,
                current_python=current_python,
                frozen=frozen,
                frozen_executable=frozen_executable,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            result["error"] = str(exc)
        finally:
            finished.set()

    def poll_worker() -> None:
        if finished.is_set():
            if result["error"] is not None:
                set_status(
                    "Portal nije mogao da se podigne",
                    str(result["error"]),
                    "greška pri pokretanju",
                )
                return

            deployment = result["deployment"]
            if isinstance(deployment, ControlCenterRuntimeDeployment):
                set_status(
                    "Portal je otvoren",
                    "RuntimePilot je podignut i browser je pozvan tek pošto je health potvrđen.",
                    "spremno",
                )
                if not close_scheduled["value"]:
                    close_scheduled["value"] = True
                    root.after(1500, root.destroy)
            return

        elapsed = time.monotonic() - started_at
        if elapsed >= 7.0 and not slow_message_shown["value"]:
            slow_message_shown["value"] = True
            set_status(
                "Pokretanje traje malo duže",
                "RuntimePilot i dalje čeka da lokalni panel vrati zdrav odgovor. Ako je runtime težak, ovo je kratko vreme normalno.",
                "čekam odgovor",
            )
        root.after(250, poll_worker)

    threading.Thread(target=worker, daemon=True).start()
    pulse_progress()
    poll_worker()
    root.mainloop()
    return 0


def _module_main(argv: list[str] | None = None) -> int:
    return run_control_center_startup_entry(argv)


if __name__ == "__main__":
    raise SystemExit(_module_main())
