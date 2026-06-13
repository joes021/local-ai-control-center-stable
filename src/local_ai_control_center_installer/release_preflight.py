from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


TEXT_FILE_SUFFIXES = {
    ".bat",
    ".cmd",
    ".conf",
    ".css",
    ".cfg",
    ".env",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".ps1",
    ".py",
    ".pyi",
    ".sh",
    ".svg",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
SKIPPED_DIR_NAMES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".superpowers",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}
INSTALLER_SCOPE_TARGETS = (
    "frontend",
    "packaging",
    "pyproject.toml",
    "src",
    "tests",
)
PUBLIC_SCOPE_TARGETS = (
    "README.md",
    "docs",
    "frontend",
    "packaging",
    "pyproject.toml",
    "src",
    "tests",
)


@dataclass(frozen=True)
class ReleasePreflightFinding:
    path: Path
    line_number: int
    rule_id: str
    match: str


@dataclass(frozen=True)
class _Rule:
    rule_id: str
    pattern: re.Pattern[str]


RULES = (
    _Rule(
        rule_id="hardcoded-windows-user-path",
        pattern=re.compile(
            r"C:(?:\\|/)Users(?:\\|/)(?!<user>(?:\\|/)?)(?!<remote-user>(?:\\|/)?)(?!Public(?:\\|/)?)(?!Default(?: User)?(?:\\|/)?)"
            r"(?P<value>[^\\/\s`\"'>]+)"
        ),
    ),
    _Rule(
        rule_id="named-remote-host",
        pattern=re.compile(r"(?P<value>" + "Server" + "1" + "@)"),
    ),
    _Rule(
        rule_id="hardcoded-private-ip",
        pattern=re.compile(r"(?P<value>" + "100" + r"\." + "108" + r"\." + "15" + r"\." + "57)"),
    ),
    _Rule(
        rule_id="hardcoded-codex-cache-path",
        pattern=re.compile(r"(?P<value>" + "codex" + "-" + "runtimes)"),
    ),
)


def _iter_text_paths(path: Path) -> list[Path]:
    if path.is_file():
        if path.suffix.lower() in TEXT_FILE_SUFFIXES or path.name in {"README", "LICENSE"}:
            return [path]
        return []
    if not path.exists():
        return []

    results: list[Path] = []
    for child in path.rglob("*"):
        if child.is_dir() and child.name in SKIPPED_DIR_NAMES:
            continue
        if not child.is_file():
            continue
        if any(part in SKIPPED_DIR_NAMES for part in child.parts):
            continue
        if child.suffix.lower() in TEXT_FILE_SUFFIXES or child.name in {"README", "LICENSE"}:
            results.append(child)
    return results


def scan_release_preflight_paths(paths: list[Path] | tuple[Path, ...]) -> list[ReleasePreflightFinding]:
    findings: list[ReleasePreflightFinding] = []
    for path in paths:
        for text_path in _iter_text_paths(path):
            try:
                content = text_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for line_number, line in enumerate(content.splitlines(), start=1):
                for rule in RULES:
                    for match in rule.pattern.finditer(line):
                        raw_match = match.group("value")
                        if rule.rule_id == "hardcoded-windows-user-path":
                            findings.append(
                                ReleasePreflightFinding(
                                    path=text_path,
                                    line_number=line_number,
                                    rule_id=rule.rule_id,
                                    match=f"C:\\Users\\{raw_match}",
                                )
                            )
                        else:
                            findings.append(
                                ReleasePreflightFinding(
                                    path=text_path,
                                    line_number=line_number,
                                    rule_id=rule.rule_id,
                                    match=raw_match,
                                )
                            )
    return findings


def resolve_scope_targets(repo_root: Path, scopes: tuple[str, ...]) -> list[Path]:
    normalized_scopes = scopes or ("public",)
    targets: list[Path] = []
    for scope in normalized_scopes:
        if scope == "installer":
            scope_targets = INSTALLER_SCOPE_TARGETS
        elif scope == "public":
            scope_targets = PUBLIC_SCOPE_TARGETS
        else:
            raise ValueError(f"Unknown preflight scope: {scope}")
        for target in scope_targets:
            resolved = repo_root / target
            if resolved.exists() and resolved not in targets:
                targets.append(resolved)
    return targets


def _format_finding(repo_root: Path, finding: ReleasePreflightFinding) -> str:
    try:
        relative_path = finding.path.relative_to(repo_root)
    except ValueError:
        relative_path = finding.path
    return f"{relative_path}:{finding.line_number}: {finding.rule_id}: {finding.match}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="release-preflight")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--scope",
        action="append",
        choices=("installer", "public"),
        help="Which release surface to scan. Defaults to public.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    targets = resolve_scope_targets(repo_root, tuple(args.scope or ()))
    findings = scan_release_preflight_paths(targets)
    if not findings:
        print("Release preflight passed.")
        return 0

    print("Release preflight failed. Sanitize these traces before building a public installer:")
    for finding in findings:
        print(f" - {_format_finding(repo_root, finding)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
