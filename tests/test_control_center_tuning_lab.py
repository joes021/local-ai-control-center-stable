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
    assert result["taskCompleted"] is True
    assert result["status"] == "completed"


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
