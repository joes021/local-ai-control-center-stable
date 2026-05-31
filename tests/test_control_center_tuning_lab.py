from copy import deepcopy
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import subprocess
import pytest

from local_ai_control_center_installer.control_center_backend.config import get_config


def test_control_center_config_exposes_tuning_lab_state_paths(tmp_path: Path, monkeypatch):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    config = get_config()

    assert (
        config.tuning_lab_history_path
        == install_root / "config" / "control-center" / "tuning-lab-history.json"
    )
    assert (
        config.tuning_lab_run_state_path
        == install_root / "config" / "control-center" / "tuning-lab-run-state.json"
    )
    assert (
        config.tuning_lab_runtime_profiles_path
        == install_root / "config" / "control-center" / "tuning-lab-runtime-profiles.json"
    )


def test_tuning_lab_summary_defaults_to_three_slots_and_empty_history(tmp_path: Path, monkeypatch):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    payload = tuning_lab_service.load_tuning_lab_summary()

    assert payload["status"] == "ok"
    assert payload["activeRun"] is None
    assert payload["queue"] == []
    assert payload["history"] == []
    assert payload["historyPage"] == 1
    assert payload["historyPageSize"] == 10
    assert payload["historyTotalPages"] == 1
    assert payload["goalOptions"] == [
        {"id": "code", "label": "Kodiranje"},
        {"id": "chat", "label": "Chat"},
        {"id": "benchmark", "label": "Benchmark"},
        {"id": "low-vram", "label": "Low VRAM"},
        {"id": "long-context", "label": "Dug kontekst"},
    ]
    assert [slot["id"] for slot in payload["slots"]] == [
        "baseline",
        "recommended",
        "custom",
    ]
    assert payload["slots"][0]["label"] == "Baseline"
    assert payload["slots"][1]["label"] == "Recommended"
    assert payload["slots"][2]["label"] == "Custom"
    assert payload["slots"][2]["source"] == "manual"
    assert payload["successCheckTemplates"][0]["id"] == "auto-detect"
    assert payload["batchPresets"][0]["id"] == "game-batch-01"
    assert payload["batchPresets"][0]["tasks"][0]["id"] == "jumping-ball-runner"
    assert payload["batchPresets"][0]["focusAreas"][0] == "stabilan throughput na malom scope-u"
    assert payload["batchPresets"][0]["tasks"][0]["scopeLabel"] == "jedan fajl"
    assert payload["batchPresets"][0]["tasks"][2]["expectedArtifact"] == "index.html + js/* + README.md"


def test_tuning_lab_prepares_copy_workspace_for_plain_directory(tmp_path: Path, monkeypatch):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    source_dir = tmp_path / "plain-project"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "README.md").write_text("hello", encoding="utf-8")

    workspace = tuning_lab_service.prepare_tuning_workspace(
        working_directory=str(source_dir),
        experiment_id="exp-copy",
        slot_id="baseline",
    )

    assert workspace["mode"] == "copy"
    assert Path(workspace["workspacePath"]).is_dir()
    assert (Path(workspace["workspacePath"]) / "README.md").read_text(encoding="utf-8") == "hello"


def test_tuning_lab_prepares_copy_workspace_without_recursing_into_internal_tuning_runs(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    source_dir = install_root
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "README.md").write_text("hello", encoding="utf-8")
    internal_tuning_root = source_dir / "config" / "control-center" / "tuning-lab"
    internal_tuning_root.mkdir(parents=True, exist_ok=True)
    (internal_tuning_root / "stale.txt").write_text("old run", encoding="utf-8")

    workspace = tuning_lab_service.prepare_tuning_workspace(
        working_directory=str(source_dir),
        experiment_id="exp-self-copy",
        slot_id="baseline",
    )

    workspace_path = Path(workspace["workspacePath"])
    assert workspace["mode"] == "copy"
    assert workspace_path.is_dir()
    assert (workspace_path / "README.md").read_text(encoding="utf-8") == "hello"
    assert not (workspace_path / "config" / "control-center" / "tuning-lab").exists()


def test_tuning_lab_prepares_copy_workspace_for_missing_directory(tmp_path: Path, monkeypatch):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    missing_dir = tmp_path / "missing-project"

    workspace = tuning_lab_service.prepare_tuning_workspace(
        working_directory=str(missing_dir),
        experiment_id="exp-missing",
        slot_id="baseline",
    )

    assert missing_dir.is_dir()
    assert workspace["mode"] == "copy"
    assert Path(workspace["workspacePath"]).is_dir()
    assert list(Path(workspace["workspacePath"]).iterdir()) == []


def test_tuning_lab_prepares_git_worktree_for_clean_repo(tmp_path: Path, monkeypatch):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    repo_dir = tmp_path / "repo-project"
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "tuning@example.invalid"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Tuning Lab"], cwd=repo_dir, check=True)
    (repo_dir / "app.py").write_text("print('ok')\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, check=True, capture_output=True, text=True)

    workspace = tuning_lab_service.prepare_tuning_workspace(
        working_directory=str(repo_dir),
        experiment_id="exp-git",
        slot_id="recommended",
    )

    assert workspace["mode"] == "git-worktree"
    assert Path(workspace["workspacePath"]).is_dir()
    assert (Path(workspace["workspacePath"]) / "app.py").read_text(encoding="utf-8") == "print('ok')\n"


def test_tuning_lab_winner_prefers_successful_and_faster_slot():
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    winner = tuning_lab_service.suggest_tuning_winner(
        [
            {
                "id": "baseline",
                "status": "completed",
                "taskCompleted": True,
                "successChecksPassed": True,
                "totalDurationMs": 28000,
                "averageOutputTokensPerSecond": 42.0,
                "averageTotalTokensPerSecond": 55.0,
            },
            {
                "id": "recommended",
                "status": "completed",
                "taskCompleted": True,
                "successChecksPassed": True,
                "totalDurationMs": 18000,
                "averageOutputTokensPerSecond": 38.0,
                "averageTotalTokensPerSecond": 48.0,
            },
            {
                "id": "custom",
                "status": "failed",
                "taskCompleted": False,
                "successChecksPassed": False,
                "totalDurationMs": 5000,
                "averageOutputTokensPerSecond": 80.0,
                "averageTotalTokensPerSecond": 100.0,
            },
        ]
    )

    assert winner == "recommended"


def test_tuning_lab_winner_falls_back_to_live_throughput_when_average_is_missing():
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    winner = tuning_lab_service.suggest_tuning_winner(
        [
            {
                "id": "baseline",
                "status": "completed",
                "taskCompleted": True,
                "successChecksPassed": True,
                "totalDurationMs": 20000,
                "averageOutputTokensPerSecond": 0.0,
                "averageTotalTokensPerSecond": 0.0,
                "liveOutputTokensPerSecond": 18.0,
                "liveTotalTokensPerSecond": 18.0,
            },
            {
                "id": "recommended",
                "status": "completed",
                "taskCompleted": True,
                "successChecksPassed": True,
                "totalDurationMs": 20000,
                "averageOutputTokensPerSecond": 0.0,
                "averageTotalTokensPerSecond": 0.0,
                "liveOutputTokensPerSecond": 24.0,
                "liveTotalTokensPerSecond": 24.0,
            },
        ]
    )

    assert winner == "recommended"


def test_parse_opencode_json_output_reads_tokens_from_step_finish_part_payload():
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    output = "\n".join(
        [
            json.dumps(
                {
                    "type": "tool_use",
                    "part": {"tool": "write", "state": {"status": "completed"}},
                }
            ),
            json.dumps(
                {
                    "type": "step_finish",
                    "part": {
                        "tokens": {"input": 10875, "output": 7142, "total": 18017},
                        "cost": 0,
                    },
                }
            ),
        ]
    )

    parsed = tuning_lab_service._parse_opencode_json_output(output)

    assert parsed["inputTokens"] == 10875
    assert parsed["outputTokens"] == 7142
    assert parsed["totalTokens"] == 18017


def test_parse_opencode_json_output_accumulates_step_finish_tokens_without_cache_reads():
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    output = "\n".join(
        [
            json.dumps(
                {
                    "type": "step_finish",
                    "part": {
                        "tokens": {
                            "input": 11059,
                            "output": 117,
                            "total": 11176,
                            "cache": {"read": 0, "write": 0},
                        },
                        "cost": 0,
                    },
                }
            ),
            json.dumps(
                {
                    "type": "step_finish",
                    "part": {
                        "tokens": {
                            "input": 81,
                            "output": 7494,
                            "total": 18750,
                            "cache": {"read": 11175, "write": 0},
                        },
                        "cost": 0,
                    },
                }
            ),
            json.dumps(
                {
                    "type": "step_finish",
                    "part": {
                        "tokens": {
                            "input": 21,
                            "output": 104,
                            "total": 18874,
                            "cache": {"read": 18749, "write": 0},
                        },
                        "cost": 0,
                    },
                }
            ),
        ]
    )

    parsed = tuning_lab_service._parse_opencode_json_output(output)

    assert parsed["inputTokens"] == 11161
    assert parsed["outputTokens"] == 7715
    assert parsed["totalTokens"] == 18876
    assert parsed["costUsd"] == 0.0


def test_rehydrate_history_slot_metrics_backfills_legacy_token_averages(tmp_path: Path):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    stdout_path = tmp_path / "opencode-output.jsonl"
    stdout_path.write_text(
        "\n".join(
            [
                json.dumps({"type": "text", "text": "Napravljen je rezultat."}),
                json.dumps(
                    {
                        "type": "step_finish",
                        "part": {
                            "tokens": {"input": 2500, "output": 1250, "total": 3750},
                            "cost": 0,
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    slot = {
        "stdoutPath": str(stdout_path),
        "inputTokens": 0,
        "outputTokens": 0,
        "totalTokens": 0,
        "costUsd": 0.0,
        "assistantText": "",
        "totalDurationMs": 25000,
        "averageOutputTokensPerSecond": 0.0,
        "averageTotalTokensPerSecond": 0.0,
    }

    changed = tuning_lab_service._rehydrate_history_slot_metrics(slot)

    assert changed is True
    assert slot["inputTokens"] == 2500
    assert slot["outputTokens"] == 1250
    assert slot["totalTokens"] == 3750
    assert slot["assistantText"] == "Napravljen je rezultat."
    assert slot["averageOutputTokensPerSecond"] == pytest.approx(50.0)
    assert slot["averageTotalTokensPerSecond"] == pytest.approx(150.0)


def test_rehydrate_history_slot_metrics_replaces_stale_nonzero_legacy_values(tmp_path: Path):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    stdout_path = tmp_path / "opencode-output.jsonl"
    stdout_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "step_finish",
                        "part": {
                            "tokens": {
                                "input": 11059,
                                "output": 117,
                                "total": 11176,
                                "cache": {"read": 0, "write": 0},
                            },
                            "cost": 0,
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "step_finish",
                        "part": {
                            "tokens": {
                                "input": 81,
                                "output": 7494,
                                "total": 18750,
                                "cache": {"read": 11175, "write": 0},
                            },
                            "cost": 0,
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "step_finish",
                        "part": {
                            "tokens": {
                                "input": 21,
                                "output": 104,
                                "total": 18874,
                                "cache": {"read": 18749, "write": 0},
                            },
                            "cost": 0,
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    slot = {
        "stdoutPath": str(stdout_path),
        "inputTokens": 21,
        "outputTokens": 104,
        "totalTokens": 18874,
        "costUsd": 0.0,
        "assistantText": "",
        "totalDurationMs": 469000,
        "averageOutputTokensPerSecond": 0.22,
        "averageTotalTokensPerSecond": 40.24,
    }

    changed = tuning_lab_service._rehydrate_history_slot_metrics(slot)

    assert changed is True
    assert slot["inputTokens"] == 11161
    assert slot["outputTokens"] == 7715
    assert slot["totalTokens"] == 18876
    assert slot["averageOutputTokensPerSecond"] == pytest.approx(16.45, rel=1e-3)
    assert slot["averageTotalTokensPerSecond"] == pytest.approx(40.25, rel=1e-3)


def test_tuning_lab_summary_reports_safe_workspace_and_prerequisite_blockers(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    payload = tuning_lab_service.load_tuning_lab_summary()

    assert payload["context"]["configuredWorkingDirectory"] == str(install_root)
    assert payload["context"]["workingDirectory"] == str(
        install_root / "workspaces" / "tuning-lab" / "scratch"
    )
    assert payload["context"]["workingDirectoryWasAdjusted"] is True
    assert payload["context"]["canQueue"] is False
    assert payload["context"]["runtimeBinaryReady"] is False
    assert payload["context"]["activeModelReady"] is False
    assert payload["context"]["opencodeReady"] is False
    assert any(
        "OpenCode nije instaliran" in message
        for message in payload["context"]["runBlockers"]
    )
    assert any(
        "Aktivan model nije podešen" in message
        for message in payload["context"]["runBlockers"]
    )


def test_tuning_lab_queue_returns_error_when_prerequisites_are_missing(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(tuning_lab_service, "_ensure_tuning_worker", lambda config=None: None)

    result = tuning_lab_service.enqueue_tuning_experiment(
        {
            "name": "Demo",
            "goal": "code",
            "taskPrompt": "Implement something small",
            "workingDirectory": str(install_root),
        }
    )

    assert result["status"] == "error"
    assert "OpenCode nije instaliran" in result["summary"]


def test_tuning_lab_slot_treats_zero_returncode_without_tokens_as_completed(tmp_path: Path, monkeypatch):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir(parents=True, exist_ok=True)
    artifact_root = (
        config.control_center_config_root
        / "tuning-lab"
        / "runs"
        / "tuning-red"
        / "baseline"
    )
    artifact_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        tuning_lab_service,
        "prepare_tuning_workspace",
        lambda **kwargs: {
            "mode": "copy",
            "workspacePath": str(workspace_path),
            "cleanupPath": str(workspace_path),
        },
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "_launch_slot_runtime",
        lambda **kwargs: {
            "process": None,
            "baseUrl": "http://127.0.0.1:49000",
            "commandPreview": "runtime-preview",
        },
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "create_tuning_runtime_profile",
        lambda **kwargs: {"token": "slot-token"},
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "_run_slot_opencode_task",
        lambda **kwargs: {
            "processReturncode": 0,
            "assistantText": "",
            "inputTokens": 0,
            "outputTokens": 0,
            "totalTokens": 0,
            "costUsd": 0.0,
            "stdoutPath": str(artifact_root / "opencode-output.jsonl"),
            "stdoutText": "",
            "stderrText": "",
            "commandPreview": "opencode-preview",
            "averageOutputTokensPerSecond": 0.0,
            "averageTotalTokensPerSecond": 0.0,
        },
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "_resolve_success_check_specs",
        lambda **kwargs: [{"label": "verify", "command": "ok", "kind": "custom"}],
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "_run_success_checks",
        lambda *args, **kwargs: [
            {
                "label": "verify",
                "command": "ok",
                "kind": "custom",
                "returncode": 0,
                "passed": True,
                "stdoutPath": str(artifact_root / "success.log"),
                "stdoutPreview": "",
                "stderrPreview": "",
            }
        ],
    )
    monkeypatch.setattr(tuning_lab_service, "_snapshot_directory", lambda path: {})
    monkeypatch.setattr(
        tuning_lab_service,
        "_build_diff_artifacts",
        lambda *args, **kwargs: {
            "changedFiles": ["tuning_lab_ready.txt"],
            "summary": "1 fajl(ova) je promenjeno.",
            "diffFiles": [
                {
                    "path": "tuning_lab_ready.txt",
                    "summary": "tuning_lab_ready.txt",
                    "diffText": "--- a/tuning_lab_ready.txt\n+++ b/tuning_lab_ready.txt\n+READY",
                    "isBinary": False,
                    "isTruncated": False,
                }
            ],
            "diffText": "--- a/tuning_lab_ready.txt\n+++ b/tuning_lab_ready.txt\n+READY",
        },
    )
    monkeypatch.setattr(tuning_lab_service, "_cleanup_workspace_path", lambda workspace_info: None)

    result = tuning_lab_service._run_tuning_slot(
        {
            "runId": "tuning-red",
            "workingDirectory": str(workspace_path),
            "taskPrompt": "create READY file",
        },
        {
            "id": "baseline",
            "label": "Baseline",
            "source": "current-system",
            "settingsPatch": {"temperature": 0.2},
        },
        config,
    )

    assert result["processReturncode"] == 0
    assert result["successChecksPassed"] is True
    assert result["changedFiles"] == ["tuning_lab_ready.txt"]
    assert result["diffFiles"][0]["path"] == "tuning_lab_ready.txt"
    assert result["taskCompleted"] is True
    assert result["status"] == "completed"


def test_tuning_lab_slot_retains_playable_artifacts_for_successful_html_output(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir(parents=True, exist_ok=True)
    (workspace_path / "index.html").write_text(
        "<!doctype html><html><body><script src='js/game.js'></script></body></html>",
        encoding="utf-8",
    )
    (workspace_path / "js").mkdir(parents=True, exist_ok=True)
    (workspace_path / "js" / "game.js").write_text("console.log('playable');\n", encoding="utf-8")
    artifact_root = (
        config.control_center_config_root
        / "tuning-lab"
        / "runs"
        / "tuning-play"
        / "baseline"
    )
    artifact_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        tuning_lab_service,
        "prepare_tuning_workspace",
        lambda **kwargs: {
            "mode": "copy",
            "workspacePath": str(workspace_path),
            "cleanupPath": str(workspace_path),
        },
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "_launch_slot_runtime",
        lambda **kwargs: {
            "process": None,
            "baseUrl": "http://127.0.0.1:49000",
            "commandPreview": "runtime-preview",
        },
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "create_tuning_runtime_profile",
        lambda **kwargs: {"token": "slot-token"},
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "_run_slot_opencode_task",
        lambda **kwargs: {
            "processReturncode": 0,
            "assistantText": "Finished game",
            "inputTokens": 10,
            "outputTokens": 20,
            "totalTokens": 30,
            "costUsd": 0.0,
            "stdoutPath": str(artifact_root / "opencode-output.jsonl"),
            "stdoutText": "",
            "stderrText": "",
            "commandPreview": "opencode-preview",
            "averageOutputTokensPerSecond": 12.0,
            "averageTotalTokensPerSecond": 15.0,
        },
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "_resolve_success_check_specs",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "_run_success_checks",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(tuning_lab_service, "_snapshot_directory", lambda path: {})
    monkeypatch.setattr(
        tuning_lab_service,
        "_build_diff_artifacts",
        lambda *args, **kwargs: {
            "changedFiles": ["index.html", "js/game.js"],
            "summary": "2 fajl(ova) je promenjeno.",
            "diffFiles": [],
            "diffText": "",
        },
    )
    monkeypatch.setattr(tuning_lab_service, "_cleanup_workspace_path", lambda workspace_info: None)

    result = tuning_lab_service._run_tuning_slot(
        {
            "runId": "tuning-play",
            "workingDirectory": str(workspace_path),
            "taskPrompt": "create playable game",
        },
        {
            "id": "baseline",
            "label": "Baseline",
            "source": "current-system",
            "settingsPatch": {"temperature": 0.2},
        },
        config,
    )

    assert result["status"] == "completed"
    assert result["playableEntryPath"] == "index.html"
    assert (artifact_root / "playable" / "index.html").is_file()
    assert (artifact_root / "playable" / "js" / "game.js").is_file()


def test_tuning_lab_slot_updates_active_run_with_visible_session_details(tmp_path: Path, monkeypatch):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir(parents=True, exist_ok=True)
    artifact_root = (
        config.control_center_config_root
        / "tuning-lab"
        / "runs"
        / "tuning-visible"
        / "baseline"
    )
    artifact_root.mkdir(parents=True, exist_ok=True)
    active_run_snapshots: list[dict[str, object]] = []

    monkeypatch.setattr(
        tuning_lab_service,
        "prepare_tuning_workspace",
        lambda **kwargs: {
            "mode": "copy",
            "workspacePath": str(workspace_path),
            "cleanupPath": str(workspace_path),
        },
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "_launch_slot_runtime",
        lambda **kwargs: {
            "process": type("Process", (), {"pid": 31001})(),
            "baseUrl": "http://127.0.0.1:49000",
            "commandPreview": "runtime-preview",
            "logPath": str(artifact_root / "runtime.log"),
        },
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "create_tuning_runtime_profile",
        lambda **kwargs: {"token": "slot-token"},
    )

    def fake_run_slot_opencode_task(**kwargs):
        kwargs["progress_callback"](
            "opencode",
            "OpenCode task radi",
            "Baseline trenutno izvršava zadatak nad izolovanim projektom.",
            log_excerpt="streaming output",
            slot_patch={
                "opencodePid": 41002,
                "opencodeSessionId": "ses_demo",
                "activeMessageId": "msg_demo",
                "opencodeCommand": "opencode-preview",
                "stdoutPath": str(artifact_root / "opencode-output.jsonl"),
                "stderrPath": str(artifact_root / "opencode-error.log"),
                "liveWorkspaceSummary": "Živi workspace trenutno ima 1 fajl.",
                "liveWorkspaceFiles": [
                    {
                        "path": "index.html",
                        "sizeBytes": 2048,
                        "modifiedAt": "2026-05-31T00:59:00+00:00",
                    }
                ],
                "livePreviewFilePath": "index.html",
                "livePreviewFileName": "index.html",
                "livePreviewText": "<!doctype html>\n<title>Demo</title>",
                "livePreviewModifiedAt": "2026-05-31T00:59:00+00:00",
                "liveOutputTokensPerSecond": 18.5,
                "liveTotalTokensPerSecond": 19.1,
                "lastLiveMeasuredAt": "2026-05-29T18:45:14+00:00",
            },
        )
        return {
            "processReturncode": 0,
            "assistantText": "Finished game",
            "inputTokens": 20,
            "outputTokens": 40,
            "totalTokens": 60,
            "costUsd": 0.0,
            "stdoutPath": str(artifact_root / "opencode-output.jsonl"),
            "stderrPath": str(artifact_root / "opencode-error.log"),
            "stdoutText": "",
            "stderrText": "",
            "commandPreview": "opencode-preview",
            "opencodeSessionId": "ses_demo",
            "activeMessageId": "msg_demo",
            "liveWorkspaceSummary": "Živi workspace trenutno ima 1 fajl.",
            "liveWorkspaceFiles": [
                {
                    "path": "index.html",
                    "sizeBytes": 2048,
                    "modifiedAt": "2026-05-31T00:59:00+00:00",
                }
            ],
            "livePreviewFilePath": "index.html",
            "livePreviewFileName": "index.html",
            "livePreviewText": "<!doctype html>\n<title>Demo</title>",
            "livePreviewModifiedAt": "2026-05-31T00:59:00+00:00",
            "averageOutputTokensPerSecond": 18.5,
            "averageTotalTokensPerSecond": 19.1,
        }

    monkeypatch.setattr(
        tuning_lab_service,
        "_run_slot_opencode_task",
        fake_run_slot_opencode_task,
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "_resolve_success_check_specs",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "_run_success_checks",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(tuning_lab_service, "_snapshot_directory", lambda path: {})
    monkeypatch.setattr(
        tuning_lab_service,
        "_build_diff_artifacts",
        lambda *args, **kwargs: {
            "changedFiles": ["index.html"],
            "summary": "1 fajl(ova) je promenjeno.",
            "diffFiles": [],
            "diffText": "",
        },
    )
    monkeypatch.setattr(tuning_lab_service, "_cleanup_workspace_path", lambda workspace_info: None)
    monkeypatch.setattr(tuning_lab_service, "_stop_slot_runtime", lambda runtime_session: None)
    monkeypatch.setattr(
        tuning_lab_service,
        "_write_active_run",
        lambda config, active_run: active_run_snapshots.append(deepcopy(active_run)),
    )

    result = tuning_lab_service._run_tuning_slot(
        {
            "runId": "tuning-visible",
            "workingDirectory": str(workspace_path),
            "taskPrompt": "create playable game",
            "currentSlotId": "baseline",
            "currentSlotLabel": "Baseline",
            "slots": [
                {
                    "id": "baseline",
                    "label": "Baseline",
                    "source": "current-system",
                    "settingsPatch": {"temperature": 0.2},
                }
            ],
        },
        {
            "id": "baseline",
            "label": "Baseline",
            "source": "current-system",
            "settingsPatch": {"temperature": 0.2},
        },
        config,
    )

    opencode_snapshot = next(
        item for item in active_run_snapshots if item.get("currentPhase") == "opencode"
    )
    running_slot = opencode_snapshot["slots"][0]

    assert running_slot["workspacePath"] == str(workspace_path)
    assert running_slot["runtimeBaseUrl"] == "http://127.0.0.1:49000"
    assert running_slot["runtimeCommand"] == "runtime-preview"
    assert running_slot["runtimePid"] == 31001
    assert running_slot["runtimeLogPath"] == str(artifact_root / "runtime.log")
    assert running_slot["opencodePid"] == 41002
    assert running_slot["opencodeSessionId"] == "ses_demo"
    assert running_slot["activeMessageId"] == "msg_demo"
    assert running_slot["opencodeCommand"] == "opencode-preview"
    assert running_slot["stdoutPath"] == str(artifact_root / "opencode-output.jsonl")
    assert running_slot["stderrPath"] == str(artifact_root / "opencode-error.log")
    assert running_slot["liveWorkspaceSummary"] == "Živi workspace trenutno ima 1 fajl."
    assert running_slot["liveWorkspaceFiles"][0]["path"] == "index.html"
    assert running_slot["livePreviewFilePath"] == "index.html"
    assert running_slot["livePreviewFileName"] == "index.html"
    assert "<title>Demo</title>" in running_slot["livePreviewText"]
    assert running_slot["liveOutputTokensPerSecond"] == 18.5
    assert running_slot["liveTotalTokensPerSecond"] == 19.1
    assert running_slot["lastLiveMeasuredAt"] == "2026-05-29T18:45:14+00:00"
    assert result["runtimePid"] == 31001
    assert result["opencodePid"] == 41002
    assert result["opencodeSessionId"] == "ses_demo"
    assert result["activeMessageId"] == "msg_demo"


def test_tuning_lab_collects_live_workspace_activity_preview(tmp_path: Path):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir(parents=True, exist_ok=True)
    older = workspace_path / "README.md"
    newer = workspace_path / "src" / "index.html"
    newer.parent.mkdir(parents=True, exist_ok=True)
    older.write_text("# demo\n", encoding="utf-8")
    newer.write_text("<!doctype html>\n<title>Jumping Ball Runner</title>\n", encoding="utf-8")

    activity = tuning_lab_service._collect_live_workspace_activity(workspace_path)

    assert "Živi workspace trenutno ima" in activity["summary"]
    assert activity["recentFiles"]
    assert activity["previewFilePath"] == "src/index.html"
    assert activity["previewFileName"] == "index.html"
    assert "Jumping Ball Runner" in activity["previewText"]


def test_tuning_lab_extracts_session_and_message_metadata_from_jsonl():
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    metadata = tuning_lab_service._parse_opencode_session_metadata(
        "\n".join(
            [
                '{"type":"step_start","sessionID":"ses_demo","part":{"messageID":"msg_demo","sessionID":"ses_demo","type":"step-start"}}',
                '{"type":"text","text":"Zdravo"}',
            ]
        )
    )

    assert metadata["sessionId"] == "ses_demo"
    assert metadata["messageId"] == "msg_demo"


def test_tuning_lab_builds_stricter_batch_prompt():
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    prompt = tuning_lab_service._build_tuning_lab_task_prompt(
        {
            "taskPrompt": "Napravi index.html igru.",
            "expectedArtifact": "index.html",
        }
    )

    assert "Tuning Lab automatizovani zadatak." in prompt
    assert "Obavezni izlazni artefakti: index.html." in prompt
    assert "Originalni zadatak:" in prompt
    assert "Napravi index.html igru." in prompt


def test_tuning_lab_batch_presets_require_key_gameplay_signals():
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    summary = tuning_lab_service.load_tuning_lab_summary()
    game_batch = next(
        batch for batch in summary["batchPresets"] if batch["id"] == "game-batch-01"
    )
    tasks = {task["id"]: task for task in game_batch["tasks"]}

    jumping_command = tasks["jumping-ball-runner"]["successChecks"][1]["command"]
    assert "Game Over|game over" in jumping_command
    assert "ArrowUp|Space|keydown|addEventListener" in jumping_command
    assert "localStorage" in jumping_command

    balloon_command = tasks["balloon-blaster"]["successChecks"][1]["command"]
    assert "power[- ]?up|PowerUp|powerUp" in balloon_command
    assert "difficulty|tezin" in balloon_command
    assert "localStorage" in balloon_command

    octopus_command = tasks["octopus-invaders"]["successChecks"][1]["command"]
    assert "Octopus Invaders|space shooter|canvas|boss|combo|health" in octopus_command
    assert "js\\game.js" in octopus_command


def test_tuning_lab_expected_artifact_presence_supports_literal_and_wildcard_entries(tmp_path: Path):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    workspace_path = tmp_path / "workspace"
    (workspace_path / "css").mkdir(parents=True, exist_ok=True)
    (workspace_path / "js").mkdir(parents=True, exist_ok=True)
    (workspace_path / "index.html").write_text("<!doctype html>", encoding="utf-8")
    (workspace_path / "README.md").write_text("# Demo", encoding="utf-8")
    (workspace_path / "js" / "game.js").write_text("console.log('ok')", encoding="utf-8")

    assert tuning_lab_service._expected_artifacts_present(
        {"expectedArtifact": "index.html + js/* + README.md"},
        workspace_path,
    )


def test_tuning_lab_workspace_output_detection_tolerates_same_second_file_write(tmp_path: Path):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir(parents=True, exist_ok=True)
    started_at = datetime.fromisoformat("2026-05-31T00:00:00.900000+00:00")

    detected = tuning_lab_service._workspace_activity_indicates_new_output(
        live_state={"hasWriteTool": False},
        workspace_activity={
            "latestModifiedAt": "2026-05-31T00:00:00+00:00",
            "previewModifiedAt": "2026-05-31T00:00:00+00:00",
        },
        started_at_utc=started_at,
        experiment={"expectedArtifact": ""},
        workspace_path=workspace_path,
    )

    assert detected is True


def test_tuning_lab_no_progress_timeout_depends_on_batch_difficulty():
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    assert tuning_lab_service._resolve_no_progress_timeout_seconds({"difficulty": "easy"}) == 300.0
    assert tuning_lab_service._resolve_no_progress_timeout_seconds({"difficulty": "medium"}) == 420.0
    assert tuning_lab_service._resolve_no_progress_timeout_seconds({"difficulty": "hard"}) == 600.0
    assert tuning_lab_service._resolve_no_progress_timeout_seconds({}) == 180.0


def test_run_slot_opencode_task_records_runtime_live_signal(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import benchmark_service
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()
    config.control_center_config_root.mkdir(parents=True, exist_ok=True)
    config.opencode_managed_config_path.parent.mkdir(parents=True, exist_ok=True)
    config.opencode_managed_config_path.write_text("{}", encoding="utf-8")

    executable_path = install_root / "tools" / "opencode" / "opencode.exe"
    executable_path.parent.mkdir(parents=True, exist_ok=True)
    executable_path.write_text("fake", encoding="utf-8")
    model_path = install_root / "models" / "recommended-6gb" / "demo.gguf"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text("model", encoding="utf-8")
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir(parents=True, exist_ok=True)
    slot_artifact_root = tmp_path / "artifacts"
    slot_artifact_root.mkdir(parents=True, exist_ok=True)

    spawned_commands: list[list[str]] = []

    class FakeProcess:
        def __init__(self, *args, **kwargs):
            spawned_commands.append(list(args[0]))
            self._polls = 0

        def poll(self):
            self._polls += 1
            if self._polls < 3:
                return None
            return 0

        def wait(self):
            return 0

    recorded_calls: list[dict[str, object]] = []

    monkeypatch.setattr(tuning_lab_service, "_resolve_opencode_executable_path", lambda config=None: executable_path)
    monkeypatch.setattr(
        tuning_lab_service,
        "load_runtime_state",
        lambda config=None: {
            "active_model_path": str(model_path),
            "active_model": "demo.gguf",
        },
    )
    monkeypatch.setattr(tuning_lab_service, "_build_slot_opencode_env", lambda **kwargs: {})
    monkeypatch.setattr(tuning_lab_service, "_parse_opencode_json_output", lambda text: {})
    monkeypatch.setattr(tuning_lab_service.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(tuning_lab_service.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        benchmark_service,
        "record_runtime_live_slot_metric",
        lambda base_url, **kwargs: recorded_calls.append({"base_url": base_url, **kwargs}) or None,
    )

    result = tuning_lab_service._run_slot_opencode_task(
        experiment={
            "taskPrompt": "Create index.html",
            "expectedArtifact": "index.html",
            "difficulty": "easy",
            "currentSlotLabel": "Baseline",
        },
        slot_settings={},
        runtime_profile_token="slot-token",
        workspace_path=workspace_path,
        slot_artifact_root=slot_artifact_root,
        config=config,
        progress_callback=None,
        upstream_base_url="http://127.0.0.1:49000",
    )

    assert result["processReturncode"] == 0
    assert spawned_commands
    assert "--print-logs" in spawned_commands[0]
    assert "--agent" in spawned_commands[0]
    assert "build" in spawned_commands[0]
    assert any("Originalni zadatak:" in part for part in spawned_commands[0])
    assert recorded_calls
    assert all(call["base_url"] == "http://127.0.0.1:49000" for call in recorded_calls)
    assert all(call["label"] == "tuning-lab-live" for call in recorded_calls)


def test_run_slot_opencode_task_auto_finishes_after_stable_success_probe(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()
    config.control_center_config_root.mkdir(parents=True, exist_ok=True)
    config.opencode_managed_config_path.parent.mkdir(parents=True, exist_ok=True)
    config.opencode_managed_config_path.write_text("{}", encoding="utf-8")

    executable_path = install_root / "tools" / "opencode" / "opencode.exe"
    executable_path.parent.mkdir(parents=True, exist_ok=True)
    executable_path.write_text("fake", encoding="utf-8")
    model_path = install_root / "models" / "recommended-6gb" / "demo.gguf"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text("model", encoding="utf-8")
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir(parents=True, exist_ok=True)
    slot_artifact_root = tmp_path / "artifacts"
    slot_artifact_root.mkdir(parents=True, exist_ok=True)

    progress_events: list[tuple[str, str]] = []
    success_check_calls: list[bool] = []

    class FakeProcess:
        def __init__(self, *args, **kwargs):
            self.pid = 43210
            self._stopped = False
            stdout_handle = kwargs["stdout"]
            stdout_handle.write(
                "\n".join(
                    [
                        '{"type":"step_start","sessionID":"ses_demo","part":{"messageID":"msg_demo","sessionID":"ses_demo","type":"step-start"}}',
                        '{"type":"tool_use","part":{"tool":"write","state":{"status":"completed","input":{"filePath":"index.html"}}}}',
                        '{"type":"step_finish","part":{"tokens":{"input":1200,"output":120,"total":1320},"cost":0}}',
                    ]
                )
                + "\n"
            )
            stdout_handle.flush()

        def poll(self):
            return 0 if self._stopped else None

        def wait(self):
            return 143 if self._stopped else 0

        def terminate(self):
            self._stopped = True

        def kill(self):
            self._stopped = True

    monkeypatch.setattr(tuning_lab_service, "_resolve_opencode_executable_path", lambda config=None: executable_path)
    monkeypatch.setattr(
        tuning_lab_service,
        "load_runtime_state",
        lambda config=None: {
            "active_model_path": str(model_path),
            "active_model": "demo.gguf",
        },
    )
    monkeypatch.setattr(tuning_lab_service, "_build_slot_opencode_env", lambda **kwargs: {})
    monkeypatch.setattr(tuning_lab_service, "_extract_runtime_speed_metrics", lambda log_text: {})
    monkeypatch.setattr(tuning_lab_service, "load_runtime_diagnostics", lambda **kwargs: {})
    monkeypatch.setattr(
        tuning_lab_service,
            "_collect_live_workspace_activity",
            lambda workspace_path, **kwargs: {
                "summary": "workspace ima index.html",
                "recentFiles": [{"path": "index.html", "sizeBytes": 2048, "modifiedAt": "2026-05-31T00:00:20+00:00"}],
                "previewFilePath": "index.html",
                "previewFileName": "index.html",
                "previewText": "<!doctype html><title>Jumping Ball Runner</title>",
                "previewModifiedAt": "2026-05-31T00:00:20+00:00",
                "latestModifiedAt": "2026-05-31T00:00:20+00:00",
            },
        )
    monkeypatch.setattr(
        tuning_lab_service,
        "_resolve_success_check_specs",
        lambda **kwargs: [{"label": "index", "command": "echo ok", "kind": "custom"}],
    )

    def fake_run_success_checks(*args, **kwargs):
        success_check_calls.append(bool(kwargs.get("persist_logs")))
        return [{"label": "index", "command": "echo ok", "kind": "custom", "returncode": 0, "passed": True, "stdoutPath": ""}]

    monkeypatch.setattr(tuning_lab_service, "_run_success_checks", fake_run_success_checks)
    monkeypatch.setattr(tuning_lab_service.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(tuning_lab_service.time, "sleep", lambda seconds: None)
    monotonic_values = iter([0.0] + [6.0] * 20)
    monkeypatch.setattr(
        tuning_lab_service.time,
        "monotonic",
        lambda: next(monotonic_values),
    )
    monkeypatch.setattr(tuning_lab_service, "_stop_process", lambda process: process.terminate())
    monkeypatch.setattr(
        tuning_lab_service,
        "datetime",
        type(
            "FrozenDateTime",
            (),
            {
                "_calls": 0,
                "now": staticmethod(
                    lambda tz=None, _state={"calls": 0}: (
                        datetime.fromisoformat("2026-05-31T00:00:00+00:00")
                        if (_state.__setitem__("calls", _state["calls"] + 1) or _state["calls"]) == 1
                        else datetime.fromisoformat("2026-05-31T00:00:40+00:00")
                    )
                ),
                "fromisoformat": staticmethod(datetime.fromisoformat),
                "fromtimestamp": staticmethod(datetime.fromtimestamp),
            },
        ),
    )

    result = tuning_lab_service._run_slot_opencode_task(
        experiment={"taskPrompt": "Create index.html", "currentSlotLabel": "Recommended"},
        slot_settings={},
        runtime_profile_token="slot-token",
        workspace_path=workspace_path,
        slot_artifact_root=slot_artifact_root,
        config=config,
        progress_callback=lambda phase, phase_label, summary, **kwargs: progress_events.append((phase, summary)),
        upstream_base_url="",
    )

    assert result["processReturncode"] == 0
    assert result["completionMode"] == "success-probe"
    assert result["successChecksVerifiedLive"] is True
    assert result["successCheckResults"][0]["passed"] is True
    assert success_check_calls == [True]
    assert any(phase == "opencode-stable-success" for phase, _ in progress_events)


def test_tuning_lab_slot_reuses_live_verified_success_checks(tmp_path: Path, monkeypatch):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()
    monkeypatch.setattr(
        tuning_lab_service,
        "prepare_tuning_workspace",
        lambda **kwargs: {
            "mode": "copy",
            "workspacePath": str(tmp_path / "workspace"),
            "cleanupPath": "",
        },
    )
    monkeypatch.setattr(tuning_lab_service, "_snapshot_directory", lambda path: {})
    monkeypatch.setattr(
        tuning_lab_service,
        "_launch_slot_runtime",
        lambda **kwargs: {
            "commandPreview": "runtime",
            "baseUrl": "http://127.0.0.1:49999",
            "runtimeDiagnostics": {},
            "runtimePid": 111,
            "logPath": str(tmp_path / "runtime.log"),
        },
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "create_tuning_runtime_profile",
        lambda **kwargs: {"token": "slot-token"},
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "_run_slot_opencode_task",
        lambda **kwargs: {
            "processReturncode": 0,
            "assistantText": "done",
            "inputTokens": 10,
            "outputTokens": 20,
            "totalTokens": 30,
            "costUsd": 0.0,
            "stdoutPath": "",
            "stderrPath": "",
            "runtimeDiagnostics": {},
            "successCheckResults": [
                {
                    "label": "index",
                    "command": "echo ok",
                    "kind": "custom",
                    "returncode": 0,
                    "passed": True,
                    "stdoutPath": "",
                }
            ],
            "successChecksVerifiedLive": True,
            "completionSummary": "gotovo",
            "completionMode": "success-probe",
        },
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "_run_success_checks",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("success checks should not rerun")),
    )
    monkeypatch.setattr(tuning_lab_service, "_stop_slot_runtime", lambda session: None)
    monkeypatch.setattr(tuning_lab_service, "_build_diff_artifacts", lambda *args, **kwargs: {"changedFiles": [], "summary": "Bez izmena", "diffFiles": [], "diffText": ""})
    monkeypatch.setattr(tuning_lab_service, "_preserve_playable_artifacts", lambda **kwargs: {})
    monkeypatch.setattr(tuning_lab_service, "_cleanup_workspace_path", lambda workspace_info: None)
    monkeypatch.setattr(tuning_lab_service, "_write_active_run", lambda *args, **kwargs: None)

    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir(parents=True, exist_ok=True)

    result = tuning_lab_service._run_tuning_slot(
        {
            "runId": "tuning-live-check",
            "workingDirectory": str(tmp_path / "project"),
            "taskPrompt": "create index.html",
            "startedAt": "2026-05-31T00:00:00+00:00",
            "slots": [{"id": "baseline"}],
            "currentSlotId": "baseline",
        },
        {
            "id": "baseline",
            "label": "Baseline",
            "source": "current-system",
            "settingsPatch": {"temperature": 0.8},
        },
        config,
    )

    assert result["status"] == "completed"
    assert result["successChecksPassed"] is True
    assert result["successChecks"][0]["passed"] is True
    assert result["completionMode"] == "success-probe"
    assert result["successChecksVerifiedLive"] is True


def test_run_slot_opencode_task_fails_fast_when_session_stalls_without_workspace_progress(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()
    config.control_center_config_root.mkdir(parents=True, exist_ok=True)
    config.opencode_managed_config_path.parent.mkdir(parents=True, exist_ok=True)
    config.opencode_managed_config_path.write_text("{}", encoding="utf-8")

    executable_path = install_root / "tools" / "opencode" / "opencode.exe"
    executable_path.parent.mkdir(parents=True, exist_ok=True)
    executable_path.write_text("fake", encoding="utf-8")
    model_path = install_root / "models" / "recommended-6gb" / "demo.gguf"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text("model", encoding="utf-8")
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir(parents=True, exist_ok=True)
    slot_artifact_root = tmp_path / "artifacts"
    slot_artifact_root.mkdir(parents=True, exist_ok=True)

    class FakeProcess:
        def __init__(self, *args, **kwargs):
            self.pid = 54321
            self._stopped = False
            kwargs["stdout"].write(
                '{"type":"step_start","sessionID":"ses_demo","part":{"messageID":"msg_demo","sessionID":"ses_demo","type":"step-start"}}\n'
            )
            kwargs["stdout"].flush()
            kwargs["stderr"].write(
                "INFO 2026-05-31T00:00:00 service=session.prompt session.id=ses_demo step=0 loop\n"
                "INFO 2026-05-31T00:00:01 service=bus type=message.part.updated publishing\n"
            )
            kwargs["stderr"].flush()

        def poll(self):
            return 0 if self._stopped else None

        def wait(self):
            return 143 if self._stopped else 0

        def terminate(self):
            self._stopped = True

        def kill(self):
            self._stopped = True

    monkeypatch.setattr(tuning_lab_service, "_resolve_opencode_executable_path", lambda config=None: executable_path)
    monkeypatch.setattr(
        tuning_lab_service,
        "load_runtime_state",
        lambda config=None: {
            "active_model_path": str(model_path),
            "active_model": "demo.gguf",
        },
    )
    monkeypatch.setattr(tuning_lab_service, "_build_slot_opencode_env", lambda **kwargs: {})
    monkeypatch.setattr(tuning_lab_service, "_extract_runtime_speed_metrics", lambda log_text: {})
    monkeypatch.setattr(tuning_lab_service, "load_runtime_diagnostics", lambda **kwargs: {})
    monkeypatch.setattr(
        tuning_lab_service,
        "_collect_live_workspace_activity",
        lambda workspace_path, **kwargs: {
            "summary": "Workspace još nema novih fajlova.",
            "recentFiles": [],
            "previewFilePath": "",
            "previewFileName": "",
            "previewText": "",
            "previewModifiedAt": "",
            "latestModifiedAt": "",
        },
    )
    monkeypatch.setattr(tuning_lab_service.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(tuning_lab_service.time, "sleep", lambda seconds: None)
    monotonic_values = iter([0.0, 181.0] + [181.0] * 20)
    monkeypatch.setattr(tuning_lab_service.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(tuning_lab_service, "_stop_process", lambda process: process.terminate())

    with pytest.raises(RuntimeError, match="nije napravio nijedan fajl"):
        tuning_lab_service._run_slot_opencode_task(
            experiment={"taskPrompt": "Create index.html", "currentSlotLabel": "Baseline"},
            slot_settings={},
            runtime_profile_token="slot-token",
            workspace_path=workspace_path,
            slot_artifact_root=slot_artifact_root,
            config=config,
            progress_callback=None,
            upstream_base_url="",
        )


def test_run_slot_opencode_task_keeps_running_while_runtime_tokens_are_flowing(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()
    config.control_center_config_root.mkdir(parents=True, exist_ok=True)
    config.opencode_managed_config_path.parent.mkdir(parents=True, exist_ok=True)
    config.opencode_managed_config_path.write_text("{}", encoding="utf-8")

    executable_path = install_root / "tools" / "opencode" / "opencode.exe"
    executable_path.parent.mkdir(parents=True, exist_ok=True)
    executable_path.write_text("fake", encoding="utf-8")
    model_path = install_root / "models" / "recommended-6gb" / "demo.gguf"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text("model", encoding="utf-8")
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir(parents=True, exist_ok=True)
    slot_artifact_root = tmp_path / "artifacts"
    slot_artifact_root.mkdir(parents=True, exist_ok=True)

    class FakeProcess:
        def __init__(self, *args, **kwargs):
            self.pid = 65432
            self._poll_calls = 0
            kwargs["stdout"].write(
                '{"type":"step_start","sessionID":"ses_demo","part":{"messageID":"msg_demo","sessionID":"ses_demo","type":"step-start"}}\n'
            )
            kwargs["stdout"].flush()
            kwargs["stderr"].write(
                "INFO 2026-05-31T00:03:01 service=session.prompt session.id=ses_demo step=0 loop\n"
                "INFO 2026-05-31T00:03:02 service=bus type=message.part.delta publishing\n"
            )
            kwargs["stderr"].flush()

        def poll(self):
            self._poll_calls += 1
            return None if self._poll_calls == 1 else 0

        def wait(self):
            return 0

        def terminate(self):
            return None

        def kill(self):
            return None

    monkeypatch.setattr(tuning_lab_service, "_resolve_opencode_executable_path", lambda config=None: executable_path)
    monkeypatch.setattr(
        tuning_lab_service,
        "load_runtime_state",
        lambda config=None: {
            "active_model_path": str(model_path),
            "active_model": "demo.gguf",
        },
    )
    monkeypatch.setattr(tuning_lab_service, "_build_slot_opencode_env", lambda **kwargs: {})
    monkeypatch.setattr(tuning_lab_service, "_extract_runtime_speed_metrics", lambda log_text: {})
    monkeypatch.setattr(tuning_lab_service, "load_runtime_diagnostics", lambda **kwargs: {})
    monkeypatch.setattr(
        tuning_lab_service,
        "_collect_live_workspace_activity",
        lambda workspace_path, **kwargs: {
            "summary": "Workspace još nema novih fajlova.",
            "recentFiles": [],
            "previewFilePath": "",
            "previewFileName": "",
            "previewText": "",
            "previewModifiedAt": "",
            "latestModifiedAt": "",
        },
    )
    monkeypatch.setattr(
        tuning_lab_service.benchmark_service,
        "record_runtime_live_slot_metric",
        lambda *args, **kwargs: {
            "completionTokensPerSecond": 18.5,
            "totalTokensPerSecond": 18.5,
            "measuredAt": "2026-05-31T00:03:01+00:00",
            "latestTimingLine": "slot print_timing: id 1 | task 1 |",
        },
    )
    monkeypatch.setattr(tuning_lab_service.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(tuning_lab_service.time, "sleep", lambda seconds: None)
    monotonic_values = iter([0.0, 181.0, 181.5, 182.0, 182.5, 183.0])
    monkeypatch.setattr(tuning_lab_service.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(
        tuning_lab_service,
        "datetime",
        type(
            "FrozenDateTime",
            (),
            {
                "now": staticmethod(lambda tz=None: datetime.fromisoformat("2026-05-31T00:03:01+00:00")),
                "fromisoformat": staticmethod(datetime.fromisoformat),
                "fromtimestamp": staticmethod(datetime.fromtimestamp),
            },
        ),
    )

    result = tuning_lab_service._run_slot_opencode_task(
        experiment={"taskPrompt": "Create index.html", "currentSlotLabel": "Baseline"},
        slot_settings={},
        runtime_profile_token="slot-token",
        workspace_path=workspace_path,
        slot_artifact_root=slot_artifact_root,
        config=config,
        progress_callback=None,
        upstream_base_url="http://127.0.0.1:3210/api/runtime-proxy/tuning/slot-token/v1",
    )

    assert result["processReturncode"] == 0
    assert result["liveOutputTokensPerSecond"] == 18.5


def test_tuning_lab_slot_converts_workspace_prepare_failure_into_failed_slot(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()
    monkeypatch.setattr(
        tuning_lab_service,
        "prepare_tuning_workspace",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("workspace boom")),
    )
    monkeypatch.setattr(tuning_lab_service, "_write_active_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(tuning_lab_service, "_cleanup_workspace_path", lambda workspace_info: None)

    result = tuning_lab_service._run_tuning_slot(
        {
            "runId": "tuning-workspace-fail",
            "workingDirectory": str(tmp_path / "missing-project"),
            "taskPrompt": "create index.html",
            "startedAt": "2026-05-29T00:00:00+00:00",
        },
        {
            "id": "baseline",
            "label": "Baseline",
            "source": "current-system",
            "settingsPatch": {"temperature": 0.8},
        },
        config,
    )

    assert result["status"] == "failed"
    assert result["taskCompleted"] is False
    assert result["successChecksPassed"] is True
    assert result["summary"] == "workspace boom"
    assert result["playableEntryPath"] == ""


def test_tuning_lab_build_diff_artifacts_returns_per_file_blocks(tmp_path: Path):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir(parents=True, exist_ok=True)
    target_file = workspace_path / "src" / "demo.txt"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text("nova vrednost\n", encoding="utf-8")

    artifacts = tuning_lab_service._build_diff_artifacts(
        {"src/demo.txt": {"digest": "before-hash", "text": "stara vrednost\n", "size": 14}},
        {"src/demo.txt": {"digest": "after-hash", "text": "nova vrednost\n", "size": 13}},
        workspace_path,
    )

    assert artifacts["changedFiles"] == ["src/demo.txt"]
    assert artifacts["diffFiles"][0]["path"] == "src/demo.txt"
    assert "+++ b/src/demo.txt" in artifacts["diffFiles"][0]["diffText"]


def test_tuning_lab_queue_apply_export_and_failed_history_flow(tmp_path: Path, monkeypatch):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    settings_path = install_root / "config" / "control-center" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        """
        {
          "profile": "balanced",
          "themeId": "dark-chocolate",
          "workflowPresetId": "research",
          "context": 262144,
          "outputTokens": 8192,
          "workingDirectory": "__WORKDIR__",
          "thinkingMode": "mid",
          "temperature": 0.8,
          "topK": 40,
          "topP": 0.95,
          "minP": 0.05,
          "repeatPenalty": 1.0,
          "repeatLastN": 64,
          "presencePenalty": 0.0,
          "frequencyPenalty": 0.0,
          "seed": -1,
          "buildSteps": 140,
          "planSteps": 100,
          "generalSteps": 110,
          "exploreSteps": 80,
          "accessMode": "local-only",
          "securityMode": "strict",
          "capabilityMode": "confirm-commands",
          "webSearchMode": "off",
          "webSearchProvider": "duckduckgo",
          "webSearchBaseUrlMode": "managed-local",
          "webSearchBaseUrl": "",
          "webSearchMaxResults": 5,
          "webSearchTimeoutSeconds": 20,
          "webSearchPromptPrefix": "/web"
        }
        """.replace("__WORKDIR__", str(tmp_path / "project").replace("\\", "\\\\")),
        encoding="utf-8",
    )
    active_model_path = install_root / "config" / "active-model.json"
    active_model_path.parent.mkdir(parents=True, exist_ok=True)
    active_model_path.write_text(
        """
        {
          "model_id": "demo-qwen",
          "model_path": "__MODEL__"
        }
        """.replace("__MODEL__", str(tmp_path / "model.gguf").replace("\\", "\\\\")),
        encoding="utf-8",
    )

    def fake_execute(experiment, config):
        completed = dict(experiment)
        completed["status"] = "completed"
        completed["slots"] = [
            {
                "id": "baseline",
                "label": "Baseline",
                "status": "failed",
                "taskCompleted": False,
                "successChecksPassed": False,
                "settingsPatch": {"temperature": 0.8},
                "summary": "Pao success check.",
                "changedFiles": ["README.md"],
                "diffSummary": "1 fajl promenjen",
                "totalDurationMs": 12000,
                "averageOutputTokensPerSecond": 20.0,
                "averageTotalTokensPerSecond": 28.0,
            },
            {
                "id": "recommended",
                "label": "Recommended",
                "status": "completed",
                "taskCompleted": True,
                "successChecksPassed": True,
                "settingsPatch": {"temperature": 0.2, "topK": 20},
                "summary": "Najstabilniji run.",
                "changedFiles": ["src/app.py"],
                "diffSummary": "1 fajl promenjen",
                "totalDurationMs": 8000,
                "averageOutputTokensPerSecond": 40.0,
                "averageTotalTokensPerSecond": 52.0,
            },
            {
                "id": "custom",
                "label": "Custom",
                "status": "completed",
                "taskCompleted": True,
                "successChecksPassed": True,
                "settingsPatch": {"temperature": 0.6},
                "summary": "Sporiji ali uspešan run.",
                "changedFiles": [],
                "diffSummary": "Bez izmena",
                "totalDurationMs": 11000,
                "averageOutputTokensPerSecond": 30.0,
                "averageTotalTokensPerSecond": 41.0,
            },
        ]
        completed["suggestedWinnerSlotId"] = "recommended"
        completed["winnerSummary"] = "Recommended je najbrži uspešan slot."
        completed["modelId"] = "demo-qwen"
        completed["modelFamily"] = "qwen"
        return completed

    monkeypatch.setattr(
        tuning_lab_service,
        "_execute_tuning_experiment",
        fake_execute,
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "_ensure_tuning_worker",
        lambda config=None: None,
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "_load_tuning_lab_prerequisites",
        lambda config, working_directory="": {
            "canQueue": True,
            "runBlockers": [],
            "configuredWorkingDirectory": working_directory or str(tmp_path / "project"),
            "workingDirectory": working_directory or str(tmp_path / "project"),
            "workingDirectoryWasAdjusted": False,
            "runtimeBinaryReady": True,
            "activeModelReady": True,
            "opencodeReady": True,
        },
    )

    queued = tuning_lab_service.enqueue_tuning_experiment(
        {
            "name": "Demo task",
            "goal": "code",
            "taskPrompt": "Implement small change",
            "workingDirectory": str(tmp_path / "project"),
        },
        start_worker=False,
    )

    assert queued["status"] == "accepted"
    run_id = queued["runId"]

    processed = tuning_lab_service.run_next_tuning_experiment()
    assert processed["status"] == "ok"
    assert processed["runId"] == run_id

    summary = tuning_lab_service.load_tuning_lab_summary()
    assert summary["activeRun"] is None
    assert summary["queue"] == []
    assert summary["history"][0]["runId"] == run_id
    assert summary["history"][0]["slots"][0]["status"] == "failed"
    assert summary["history"][0]["suggestedWinnerSlotId"] == "recommended"

    exported = tuning_lab_service.export_tuning_lab_run(run_id)
    assert exported["status"] == "ok"
    assert exported["experiment"]["runId"] == run_id

    applied = tuning_lab_service.apply_tuning_lab_winner(run_id)
    assert applied["status"] == "ok"

    updated_settings = settings_path.read_text(encoding="utf-8")
    assert '"temperature": 0.2' in updated_settings
    assert '"topK": 20' in updated_settings


def test_tuning_lab_delete_selected_history_and_artifacts(tmp_path: Path, monkeypatch):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()

    history_items = [
        {
            "runId": "tuning-keep",
            "name": "Zadrži me",
            "status": "completed",
            "slots": [],
        },
        {
            "runId": "tuning-delete",
            "name": "Obriši me",
            "status": "failed",
            "slots": [],
        },
    ]
    tuning_lab_service._save_history(config, history_items)
    tuning_lab_service._save_run_state(config, active_run=None, queue=[])

    keep_root = config.control_center_config_root / "tuning-lab" / "runs" / "tuning-keep"
    delete_root = config.control_center_config_root / "tuning-lab" / "runs" / "tuning-delete"
    keep_root.mkdir(parents=True, exist_ok=True)
    delete_root.mkdir(parents=True, exist_ok=True)
    (keep_root / "artifact.txt").write_text("keep", encoding="utf-8")
    (delete_root / "artifact.txt").write_text("delete", encoding="utf-8")

    result = tuning_lab_service.delete_tuning_lab_history(
        run_ids=["tuning-delete"],
        delete_artifacts=True,
        config=config,
    )

    assert result["status"] == "ok"
    assert "1 rezultat" in str(result["summary"])
    remaining_history = tuning_lab_service.load_tuning_lab_summary(config=config)["history"]
    assert [item["runId"] for item in remaining_history] == ["tuning-keep"]
    assert keep_root.exists()
    assert not delete_root.exists()


def test_tuning_lab_delete_all_history_keeps_active_run_and_its_artifacts(tmp_path: Path, monkeypatch):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()

    history_items = [
        {
            "runId": "tuning-old-1",
            "name": "Stari 1",
            "status": "completed",
            "slots": [],
        },
        {
            "runId": "tuning-old-2",
            "name": "Stari 2",
            "status": "failed",
            "slots": [],
        },
    ]
    tuning_lab_service._save_history(config, history_items)
    tuning_lab_service._save_run_state(
        config,
        active_run={
            "runId": "tuning-active",
            "name": "Aktivni",
            "status": "running",
            "slots": [],
        },
        queue=[],
    )

    old_one_root = config.control_center_config_root / "tuning-lab" / "runs" / "tuning-old-1"
    old_two_root = config.control_center_config_root / "tuning-lab" / "runs" / "tuning-old-2"
    active_root = config.control_center_config_root / "tuning-lab" / "runs" / "tuning-active"
    old_one_root.mkdir(parents=True, exist_ok=True)
    old_two_root.mkdir(parents=True, exist_ok=True)
    active_root.mkdir(parents=True, exist_ok=True)

    result = tuning_lab_service.delete_tuning_lab_history(
        delete_all=True,
        delete_artifacts=True,
        config=config,
    )

    assert result["status"] == "ok"
    assert "cela tuning lab istorija" in str(result["summary"]).lower()
    assert tuning_lab_service.load_tuning_lab_summary(config=config)["history"] == []
    assert not old_one_root.exists()
    assert not old_two_root.exists()
    assert active_root.exists()


def test_tuning_lab_summary_clamps_history_page_after_history_shrinks(tmp_path: Path, monkeypatch):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()

    history_items = []
    for index in range(12):
        history_items.append(
            {
                "runId": f"tuning-{index}",
                "name": f"Run {index}",
                "status": "completed",
                "slots": [],
            }
        )
    tuning_lab_service._save_history(config, history_items)
    payload = tuning_lab_service.load_tuning_lab_summary(history_page=2, config=config)
    assert payload["historyPage"] == 2
    assert len(payload["history"]) == 2

    tuning_lab_service.delete_tuning_lab_history(
        run_ids=["tuning-11", "tuning-10"],
        delete_artifacts=False,
        config=config,
    )
    clamped_payload = tuning_lab_service.load_tuning_lab_summary(history_page=2, config=config)

    assert clamped_payload["historyTotalPages"] == 1
    assert clamped_payload["historyPage"] == 1
    assert len(clamped_payload["history"]) == 10


def test_tuning_lab_delete_all_failed_keeps_non_failed_and_active_run(tmp_path: Path, monkeypatch):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()

    history_items = [
        {
            "runId": "tuning-completed",
            "name": "Uspeo",
            "status": "completed",
            "slots": [],
        },
        {
            "runId": "tuning-failed-1",
            "name": "Pao 1",
            "status": "failed",
            "slots": [],
        },
        {
            "runId": "tuning-failed-active",
            "name": "Aktivni failed snapshot",
            "status": "failed",
            "slots": [],
        },
        {
            "runId": "tuning-cancelled",
            "name": "Prekinut",
            "status": "cancelled",
            "slots": [],
        },
        {
            "runId": "tuning-failed-2",
            "name": "Pao 2",
            "status": "failed",
            "slots": [],
        },
    ]
    tuning_lab_service._save_history(config, history_items)
    tuning_lab_service._save_run_state(
        config,
        active_run={
            "runId": "tuning-failed-active",
            "name": "Aktivni failed snapshot",
            "status": "running",
            "slots": [],
        },
        queue=[],
    )

    failed_one_root = config.control_center_config_root / "tuning-lab" / "runs" / "tuning-failed-1"
    failed_two_root = config.control_center_config_root / "tuning-lab" / "runs" / "tuning-failed-2"
    completed_root = config.control_center_config_root / "tuning-lab" / "runs" / "tuning-completed"
    active_root = config.control_center_config_root / "tuning-lab" / "runs" / "tuning-failed-active"
    failed_one_root.mkdir(parents=True, exist_ok=True)
    failed_two_root.mkdir(parents=True, exist_ok=True)
    completed_root.mkdir(parents=True, exist_ok=True)
    active_root.mkdir(parents=True, exist_ok=True)

    result = tuning_lab_service.delete_tuning_lab_history(
        delete_failed=True,
        delete_artifacts=True,
        config=config,
    )

    assert result["status"] == "ok"
    assert "failed" in str(result["summary"]).lower()
    remaining_history = tuning_lab_service.load_tuning_lab_summary(config=config)["history"]
    assert [item["runId"] for item in remaining_history] == [
        "tuning-completed",
        "tuning-failed-active",
        "tuning-cancelled",
    ]
    assert not failed_one_root.exists()
    assert not failed_two_root.exists()
    assert completed_root.exists()
    assert active_root.exists()


def test_tuning_lab_enqueue_batch_expands_three_runs(tmp_path: Path, monkeypatch):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        tuning_lab_service,
        "_ensure_tuning_worker",
        lambda config=None: None,
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "_load_tuning_lab_prerequisites",
        lambda config, working_directory="": {
            "canQueue": True,
            "runBlockers": [],
            "configuredWorkingDirectory": working_directory or str(tmp_path / "project"),
            "workingDirectory": working_directory or str(tmp_path / "project"),
            "workingDirectoryWasAdjusted": False,
            "runtimeBinaryReady": True,
            "activeModelReady": True,
            "opencodeReady": True,
        },
    )

    result = tuning_lab_service.enqueue_tuning_batch(
        {
            "presetId": "game-batch-01",
            "workingDirectory": str(tmp_path / "project"),
            "slots": [
                {
                    "id": "custom",
                    "label": "Custom",
                    "source": "manual",
                    "settingsPatch": {
                        "temperature": 0.33,
                        "topK": 12,
                    },
                }
            ],
        },
        start_worker=False,
    )

    assert result["status"] == "accepted"
    assert len(result["runIds"]) == 3

    summary = tuning_lab_service.load_tuning_lab_summary()
    assert len(summary["queue"]) == 3
    assert summary["queue"][0]["name"].endswith("Jumping Ball Runner")
    assert summary["queue"][1]["name"].endswith("Balloon Blaster")
    assert summary["queue"][2]["name"].endswith("Octopus Invaders")
    assert summary["queue"][0]["successChecks"][0]["label"]
    custom_slot = next(slot for slot in summary["queue"][0]["slots"] if slot["id"] == "custom")
    assert custom_slot["settingsPatch"]["temperature"] == 0.33


def test_tuning_lab_summarizes_opencode_signal_for_humans():
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    excerpt = tuning_lab_service._summarize_opencode_signal_excerpt(
        "\n".join(
            [
                '{"type":"step_start","part":{"messageID":"msg_demo","type":"step-start"}}',
                '{"type":"tool_use","part":{"tool":"bash","state":{"status":"completed","input":{"description":"Check if index.html already exists"}}}}',
                '{"type":"step_finish","part":{"tokens":{"input":10889,"output":306,"total":11195},"cost":0}}',
            ]
        )
    )

    assert "OpenCode je preuzeo zadatak i otvorio novu poruku." in excerpt
    assert "ID poruke: msg_demo" in excerpt
    assert "Alat bash (completed): Check if index.html already exists" in excerpt
    assert "Korak završen: ulaz 10889 | izlaz 306 | ukupno 11195 | cost 0.0000" in excerpt


def test_tuning_lab_summarizes_write_tool_with_target_file():
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    excerpt = tuning_lab_service._summarize_opencode_signal_excerpt(
        "\n".join(
            [
                '{"type":"step_start","part":{"messageID":"msg_demo","type":"step-start"}}',
                '{"type":"tool_use","part":{"tool":"write","state":{"status":"completed","input":{"filePath":"index.html"}}}}',
            ]
        )
    )

    assert "OpenCode je preuzeo zadatak i otvorio novu poruku." in excerpt
    assert "Alat write (completed): upisan fajl index.html" in excerpt


def test_tuning_lab_extracts_runtime_prompt_speed_from_llama_log():
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    metrics = tuning_lab_service._extract_runtime_speed_metrics(
        """
0.46.217.334 I slot print_timing: id  2 | task 10 | prompt processing, n_tokens =   2047, progress = 0.19, t =  26.25 s / 77.98 tokens per second
0.53.010.000 I slot print_timing: id  2 | task 10 | generation, n_tokens =    128, t =   4.10 s / 31.22 tokens per second
5.48.913.350 I slot print_timing: id  2 | task 10 | n_decoded =   1656, tg =   9.97 t/s
"""
    )

    assert metrics["promptTokensPerSecond"] == 77.98
    assert metrics["generationTokensPerSecond"] == 9.97
    assert "prompt processing" in str(metrics["promptSummary"])
    assert "generacija" in str(metrics["generationSummary"])


def test_tuning_lab_success_check_with_select_string_quiet_passes(tmp_path: Path):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir(parents=True, exist_ok=True)
    slot_artifact_root = tmp_path / "artifacts"
    slot_artifact_root.mkdir(parents=True, exist_ok=True)
    (workspace_path / "index.html").write_text(
        "<!doctype html>\n<title>Jumping Ball Runner</title>\n<div>High Score</div>\n",
        encoding="utf-8",
    )

    results = tuning_lab_service._run_success_checks(
        [
            {
                "label": "Ključni stringovi postoje",
                "command": "if (Select-String -Path index.html -Pattern 'Jumping Ball Runner|High Score|Score' -AllMatches -Quiet) { exit 0 } else { exit 1 }",
                "kind": "custom",
            }
        ],
        workspace_path,
        slot_artifact_root,
    )

    assert len(results) == 1
    assert results[0]["passed"] is True
    assert results[0]["returncode"] == 0


def test_tuning_lab_builds_human_log_excerpt_with_runtime_fallback(tmp_path: Path):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    stdout_path = tmp_path / "opencode-output.jsonl"
    stderr_path = tmp_path / "opencode-error.log"
    stdout_path.write_text(
        '{"type":"step_start","part":{"messageID":"msg_demo","type":"step-start"}}\n',
        encoding="utf-8",
    )
    stderr_path.write_text("", encoding="utf-8")

    excerpt = tuning_lab_service._build_live_opencode_log_excerpt(
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        runtime_prompt_summary="prompt processing | 2047 tokena | 77.98 tok/s",
        runtime_generation_summary="generacija | 1656 tokena | 9.97 tok/s",
    )

    assert "OpenCode je preuzeo zadatak i otvorio novu poruku." in excerpt
    assert "Runtime prompt:" in excerpt
    assert "Runtime generacija:" in excerpt


def test_tuning_lab_builds_filtered_debug_excerpt_without_skill_dump_noise(tmp_path: Path):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    stdout_path = tmp_path / "opencode-output.jsonl"
    stderr_path = tmp_path / "opencode-error.log"
    stdout_path.write_text(
        "\n".join(
            [
                '{"type":"step_start","part":{"messageID":"msg_demo","type":"step-start"}}',
                '{"type":"tool_use","part":{"tool":"skill","state":{"status":"completed","input":{"description":"Load brainstorming skill"},"output":"<skill_content>very long dump</skill_content>"}}}',
                '{"type":"step_finish","part":{"tokens":{"input":2048,"output":128,"total":2176},"cost":0}}',
            ]
        ),
        encoding="utf-8",
    )
    stderr_path.write_text(
        "\n".join(
            [
                "INFO  2026-05-29T23:13:36 +1ms service=bus type=message.part.delta publishing",
                "WARN  tuning-lab live trace fallback",
            ]
        ),
        encoding="utf-8",
    )

    excerpt = tuning_lab_service._build_debug_opencode_excerpt(
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )

    assert "OpenCode je preuzeo zadatak i otvorio novu poruku." in excerpt
    assert "Alat skill (completed): Load brainstorming skill" in excerpt
    assert "Korak završen: ulaz 2048 | izlaz 128 | ukupno 2176 | cost 0.0000" in excerpt
    assert "WARN tuning-lab live trace fallback" in excerpt
    assert "<skill_content>" not in excerpt
    assert "message.part.delta publishing" not in excerpt


def test_tuning_lab_live_excerpt_hides_internal_info_noise(tmp_path: Path):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    stdout_path = tmp_path / "opencode-output.jsonl"
    stderr_path = tmp_path / "opencode-error.log"
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text(
        "\n".join(
            [
                "internal plugin INFO 2026-05-29T23:29:09 +0ms service=plugin name=nH loading",
                "INFO  2026-05-29T23:13:36 +1ms service=bus type=message.part.delta publishing",
                "INFO  2026-05-29T23:13:39 +0ms service=lsp all LSPs are disabled",
                "INFO  2026-05-29T23:13:40 +0ms service=db path=C:\\Users\\demo\\.local\\share\\opencode\\opencode.db opening database",
                "INFO  2026-05-29T23:13:41 +0ms service=tool.registry status=completed duration=0 webfetch",
            ]
        ),
        encoding="utf-8",
    )

    excerpt = tuning_lab_service._build_live_opencode_log_excerpt(
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )

    assert excerpt == "OpenCode proces je pokrenut i priprema prvi čitljivi događaj."


def test_tuning_lab_read_text_tail_does_not_depend_on_full_read(tmp_path: Path, monkeypatch):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    sample_path = tmp_path / "large.log"
    sample_path.write_text(("A" * 12000) + "\nTAIL-LINE-ONE\nTAIL-LINE-TWO\n", encoding="utf-8")

    def fail_read_text(*args, **kwargs):
        raise AssertionError("full read should not be used for tail access")

    monkeypatch.setattr(Path, "read_text", fail_read_text)

    excerpt = tuning_lab_service._read_text_tail(sample_path, limit=40)

    assert "TAIL-LINE-ONE" in excerpt
    assert "TAIL-LINE-TWO" in excerpt


def test_tuning_lab_reconcile_skips_lock_when_worker_is_alive(tmp_path: Path, monkeypatch):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()

    class ExplodingLock:
        def __enter__(self):
            raise AssertionError("run lock should not be acquired while worker is alive")

        def __exit__(self, exc_type, exc, tb):
            return False

    class AliveThread:
        def is_alive(self):
            return True

    monkeypatch.setattr(tuning_lab_service, "_RUN_LOCK", ExplodingLock())
    monkeypatch.setattr(tuning_lab_service, "_RUNNER_THREAD", AliveThread())

    tuning_lab_service._reconcile_orphaned_active_run(config)


def test_tuning_lab_cleans_stale_processes_without_touching_main_runtime(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()
    runs_root = config.control_center_config_root / "tuning-lab" / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)

    killed: list[int] = []
    monkeypatch.setattr(
        tuning_lab_service,
        "_list_local_process_records",
        lambda: [
            {
                "pid": 111,
                "name": "llama-server.exe",
                "commandLine": 'C:\\runtime\\llama-server.exe --host 127.0.0.1 --port 62132 --model "demo.gguf"',
            },
            {
                "pid": 222,
                "name": "llama-server.exe",
                "commandLine": 'C:\\runtime\\llama-server.exe --host 127.0.0.1 --port 39281 --model "demo.gguf"',
            },
            {
                "pid": 333,
                "name": "opencode.exe",
                "commandLine": f'C:\\tools\\opencode.exe --dir {runs_root}\\demo\\baseline\\copy --pure run',
            },
            {
                "pid": 444,
                "name": "opencode.exe",
                "commandLine": 'C:\\tools\\opencode.exe --dir C:\\Users\\demo\\workspace --pure run',
            },
        ],
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "_kill_process_tree",
        lambda pid: killed.append(pid) or True,
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "load_runtime_state",
        lambda resolved_config: {"port": 39281},
    )

    tuning_lab_service._cleanup_stale_tuning_processes(
        config,
        active_run=None,
        history_items=[
            {
                "runId": "tuning-demo",
                "slots": [
                    {"runtimeBaseUrl": "http://127.0.0.1:62132"},
                    {"runtimeBaseUrl": "http://127.0.0.1:39281"},
                ],
            }
        ],
    )

    assert killed == [111, 333]


def test_tuning_lab_reconciles_orphaned_active_run_into_failed_history(tmp_path: Path, monkeypatch):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()
    config.control_center_config_root.mkdir(parents=True, exist_ok=True)
    tuning_lab_service._save_run_state(
        config,
        active_run={
            "runId": "tuning-orphan",
            "name": "Orphan run",
            "status": "running",
            "startedAt": "2026-05-29T22:00:00+00:00",
            "slots": [
                {
                    "id": "baseline",
                    "label": "Baseline",
                    "status": "running",
                    "runtimePid": 12345,
                    "opencodePid": 23456,
                }
            ],
        },
        queue=[],
    )
    monkeypatch.setattr(tuning_lab_service, "_RUNNER_THREAD", None)
    monkeypatch.setattr(tuning_lab_service, "_list_local_process_records", lambda: [])

    payload = tuning_lab_service.load_tuning_lab_run_status(config=config)
    history = tuning_lab_service.load_tuning_lab_summary(config=config)["history"]

    assert payload == {}
    assert history
    assert history[0]["runId"] == "tuning-orphan"
    assert history[0]["status"] == "failed"
    assert history[0]["currentPhaseLabel"] == "Run je prekinut"
    assert history[0]["slots"][0]["status"] == "failed"


def test_tuning_lab_reconciles_orphaned_active_run_even_when_runtime_process_survives(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()
    config.control_center_config_root.mkdir(parents=True, exist_ok=True)
    tuning_lab_service._save_run_state(
        config,
        active_run={
            "runId": "tuning-orphan-live-runtime",
            "name": "Orphan run with live runtime",
            "status": "running",
            "startedAt": "2026-05-29T22:00:00+00:00",
            "slots": [
                {
                    "id": "baseline",
                    "label": "Baseline",
                    "status": "running",
                    "runtimePid": 12345,
                    "opencodePid": 23456,
                    "runtimeBaseUrl": "http://127.0.0.1:59858",
                }
            ],
        },
        queue=[],
    )
    monkeypatch.setattr(tuning_lab_service, "_RUNNER_THREAD", None)
    live_processes = [
        {
            "pid": 12345,
            "name": "llama-server.exe",
            "commandLine": str(install_root / "tools" / "turboquant" / "llama-server.exe")
            + " --port 59858",
        }
    ]
    monkeypatch.setattr(
        tuning_lab_service,
        "_list_local_process_records",
        lambda: list(live_processes),
    )
    killed: list[int] = []
    monkeypatch.setattr(
        tuning_lab_service,
        "_kill_process_tree",
        lambda pid: killed.append(pid) or live_processes.clear() or True,
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "load_runtime_state",
        lambda resolved_config: {"port": 3210},
    )

    payload = tuning_lab_service.load_tuning_lab_run_status(config=config)
    history = tuning_lab_service.load_tuning_lab_summary(config=config)["history"]

    assert payload == {}
    assert history
    assert history[0]["runId"] == "tuning-orphan-live-runtime"
    assert history[0]["status"] == "failed"
    assert "runner procesa" in history[0]["summary"]
    assert history[0]["slots"][0]["status"] == "failed"
    assert killed == [12345]


def test_tuning_lab_cleanup_kills_explicit_history_pids_even_without_command_match(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()

    monkeypatch.setattr(
        tuning_lab_service,
        "load_runtime_state",
        lambda config=None: {"port": 39281},
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "_list_local_process_records",
        lambda: [
            {"pid": 22222, "name": "opencode.exe", "commandLine": "C:\\Temp\\opencode.exe --weird"},
            {"pid": 33333, "name": "llama-server.exe", "commandLine": "C:\\Temp\\llama-server.exe --host 127.0.0.1 --port 55555"},
        ],
    )
    killed: list[int] = []
    monkeypatch.setattr(
        tuning_lab_service,
        "_kill_process_tree",
        lambda pid: killed.append(int(pid)) or True,
    )

    result = tuning_lab_service._cleanup_stale_tuning_processes(
        config,
        active_run=None,
        history_items=[
            {
                "runId": "tuning-cleanup",
                "slots": [
                    {
                        "id": "baseline",
                        "runtimePid": 33333,
                        "opencodePid": 22222,
                        "runtimeBaseUrl": "http://127.0.0.1:55555",
                    }
                ],
            }
        ],
    )

    assert result["killedPids"] == [22222, 33333]


def test_tuning_lab_slot_runtime_inherits_gpu_offload_launch_arguments(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True, exist_ok=True)
    binary_path = runtime_root / "llama-server.exe"
    binary_path.write_text("llama", encoding="utf-8")
    model_path = install_root / "models" / "unsloth" / "Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text("model", encoding="utf-8")
    config.active_model_config_path.parent.mkdir(parents=True, exist_ok=True)
    config.active_model_config_path.write_text(
        '{"model_id":"demo-model","model_path":"' + str(model_path).replace("\\", "\\\\") + '"}',
        encoding="utf-8",
    )
    artifact_root = config.control_center_config_root / "tuning-lab" / "runs" / "demo" / "baseline"
    artifact_root.mkdir(parents=True, exist_ok=True)

    captured: dict[str, object] = {}

    class FakeProcess:
        pid = 77701

    monkeypatch.setattr(
        tuning_lab_service,
        "load_runtime_state",
        lambda resolved_config: {
            "active_runtime": "llama.cpp",
            "active_binary": str(binary_path),
            "active_model_id": "demo-model",
            "active_model_path": str(model_path),
        },
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "classify_runtime_model_support",
        lambda **kwargs: (True, ""),
    )
    monkeypatch.setattr(tuning_lab_service, "_allocate_free_port", lambda: 49000)
    monkeypatch.setattr(tuning_lab_service, "_resolve_spec_type_for_runtime", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        tuning_lab_service,
        "_load_runtime_launch_argument_values",
        lambda *args, **kwargs: {"gpu_layers": 40, "flash_attn": "auto"},
    )
    def fake_launch_background_process(command, log_path):
        captured["command"] = command
        return FakeProcess()
    monkeypatch.setattr(
        tuning_lab_service,
        "_launch_background_process",
        fake_launch_background_process,
    )
    monkeypatch.setattr(tuning_lab_service, "_wait_for_runtime_ready", lambda *args, **kwargs: True)

    result = tuning_lab_service._launch_slot_runtime(
        slot_settings={
            "context": 262144,
            "temperature": 0.8,
            "topK": 40,
            "topP": 0.95,
            "minP": 0.05,
            "repeatPenalty": 1.0,
            "repeatLastN": 64,
            "presencePenalty": 0.0,
            "frequencyPenalty": 0.0,
            "seed": -1,
        },
        slot_artifact_root=artifact_root,
        config=config,
    )

    command = captured["command"]
    assert "--n-gpu-layers" in command
    assert command[command.index("--n-gpu-layers") + 1] == "40"
    assert "--flash-attn" in command
    assert command[command.index("--flash-attn") + 1] == "auto"
    assert result["runtimePid"] == 77701
    assert result["runtimeDiagnostics"]["status"] == "requested"
    assert result["runtimeDiagnostics"]["requestedGpuLayers"] == 40


def test_tuning_lab_slot_runtime_retries_without_explicit_main_gpu_when_runtime_rejects_it(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import tuning_lab_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True, exist_ok=True)
    binary_path = runtime_root / "llama-server.exe"
    binary_path.write_text("llama", encoding="utf-8")
    model_path = install_root / "models" / "unsloth" / "Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text("model", encoding="utf-8")
    config.active_model_config_path.parent.mkdir(parents=True, exist_ok=True)
    config.active_model_config_path.write_text(
        '{"model_id":"demo-model","model_path":"' + str(model_path).replace("\\", "\\\\") + '"}',
        encoding="utf-8",
    )
    artifact_root = config.control_center_config_root / "tuning-lab" / "runs" / "demo" / "baseline"
    artifact_root.mkdir(parents=True, exist_ok=True)

    launch_commands: list[list[str]] = []

    class FakeProcess:
        def __init__(self, pid: int) -> None:
            self.pid = pid

        def poll(self):
            return None

        def terminate(self) -> None:
            return None

        def kill(self) -> None:
            return None

    monkeypatch.setattr(
        tuning_lab_service,
        "load_runtime_state",
        lambda resolved_config: {
            "active_runtime": "llama.cpp",
            "active_binary": str(binary_path),
            "active_model_id": "demo-model",
            "active_model_path": str(model_path),
        },
    )
    monkeypatch.setattr(
        tuning_lab_service,
        "classify_runtime_model_support",
        lambda **kwargs: (True, ""),
    )
    monkeypatch.setattr(tuning_lab_service, "_allocate_free_port", lambda: 49000)
    monkeypatch.setattr(tuning_lab_service, "_resolve_spec_type_for_runtime", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        tuning_lab_service,
        "_load_runtime_launch_argument_values",
        lambda *args, **kwargs: {
            "gpu_layers": 40,
            "flash_attn": "auto",
            "main_gpu": 0,
            "split_mode": "none",
        },
    )

    def fake_launch_background_process(command, log_path):
        launch_commands.append(command)
        attempt = len(launch_commands)
        if attempt == 1:
            log_path.write_text(
                "E llama_prepare_model_devices: invalid value for main_gpu: 0 (available devices: 0)\n",
                encoding="utf-8",
            )
        else:
            log_path.write_text(
                "llm_load_tensors: offloaded 35/35 layers to GPU\n",
                encoding="utf-8",
            )
        return FakeProcess(77700 + attempt)

    monkeypatch.setattr(
        tuning_lab_service,
        "_launch_background_process",
        fake_launch_background_process,
    )

    wait_results = iter([False, True])
    monkeypatch.setattr(
        tuning_lab_service,
        "_wait_for_runtime_ready",
        lambda *args, **kwargs: next(wait_results),
    )

    result = tuning_lab_service._launch_slot_runtime(
        slot_settings={
            "context": 262144,
            "temperature": 0.8,
            "topK": 40,
            "topP": 0.95,
            "minP": 0.05,
            "repeatPenalty": 1.0,
            "repeatLastN": 64,
            "presencePenalty": 0.0,
            "frequencyPenalty": 0.0,
            "seed": -1,
        },
        slot_artifact_root=artifact_root,
        config=config,
    )

    assert len(launch_commands) == 2
    assert "--main-gpu" in launch_commands[0]
    assert "--split-mode" in launch_commands[0]
    assert "--main-gpu" not in launch_commands[1]
    assert "--split-mode" not in launch_commands[1]
    assert "main_gpu" not in result["launchArguments"]
    assert "split_mode" not in result["launchArguments"]
    assert result["launchFallbackApplied"] is True
    assert "ponovio start bez `--main-gpu`" in result["launchFallbackReason"]
    assert "ponovio start bez `--main-gpu`" in result["runtimeDiagnostics"]["summary"]
    assert result["runtimePid"] == 77702
