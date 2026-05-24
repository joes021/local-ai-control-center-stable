from __future__ import annotations

import argparse
import os

from local_ai_control_center_installer.control_center_backend.services.updates_service import (
    run_update_install_worker,
)


def run_update_install_worker_entry(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-root", required=True)
    parser.add_argument("--action-id", required=True)
    args = parser.parse_args(argv)

    os.environ["LACC_INSTALL_ROOT"] = args.install_root
    result = run_update_install_worker(args.action_id)
    return 0 if result.get("status") == "ok" else 1


def main() -> int:
    return run_update_install_worker_entry()


if __name__ == "__main__":
    raise SystemExit(main())
