from copy import deepcopy
from pathlib import Path
import subprocess

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
                "opencodeCommand": "opencode-preview",
                "stdoutPath": str(artifact_root / "opencode-output.jsonl"),
                "stderrPath": str(artifact_root / "opencode-error.log"),
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
    assert running_slot["opencodeCommand"] == "opencode-preview"
    assert running_slot["stdoutPath"] == str(artifact_root / "opencode-output.jsonl")
    assert running_slot["stderrPath"] == str(artifact_root / "opencode-error.log")
    assert running_slot["liveOutputTokensPerSecond"] == 18.5
    assert running_slot["liveTotalTokensPerSecond"] == 19.1
    assert running_slot["lastLiveMeasuredAt"] == "2026-05-29T18:45:14+00:00"
    assert result["runtimePid"] == 31001
    assert result["opencodePid"] == 41002


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
        experiment={"taskPrompt": "Create index.html", "currentSlotLabel": "Baseline"},
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
    assert recorded_calls
    assert all(call["base_url"] == "http://127.0.0.1:49000" for call in recorded_calls)
    assert all(call["label"] == "tuning-lab-live" for call in recorded_calls)


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
