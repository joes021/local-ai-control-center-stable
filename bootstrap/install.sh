#!/usr/bin/env bash
set -euo pipefail

test_python_requirement() {
  local command_path="$1"

  "${command_path}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1
}

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
src_root="${repo_root}/src"

python_command=""
python_candidates=(
  python3.13
  python3.12
  python3.11
  python3
  python
)

for candidate in "${python_candidates[@]}"; do
  if command -v "${candidate}" >/dev/null 2>&1 && test_python_requirement "$(command -v "${candidate}")"; then
    python_command="$(command -v "${candidate}")"
    break
  fi
done

if [[ -z "${python_command}" ]]; then
  echo "Python 3.11+ was not found on PATH." >&2
  echo "Bootstrap cannot continue without Python." >&2
  exit 1
fi

export PYTHONPATH="${src_root}${PYTHONPATH:+:${PYTHONPATH}}"

cd "${repo_root}"
"${python_command}" -m local_ai_control_center_installer.main
