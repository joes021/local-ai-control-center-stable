from local_ai_control_center_installer.runtime_manifest import (
    StarterModelOption,
    list_prompt_starter_models,
    load_runtime_manifest,
    resolve_requested_starter_model,
)


def test_load_runtime_manifest_exposes_three_prompt_visible_models():
    manifest = load_runtime_manifest()

    catalog = list_prompt_starter_models(manifest)

    assert [item.model_id for item in catalog] == [
        "recommended-6gb",
        "recommended-12gb",
        "recommended-24gb",
    ]
    assert [item.prompt_order for item in catalog] == [1, 2, 3]
    assert [item.prompt_label for item in catalog] == [
        "recommended-6gb",
        "recommended-12gb",
        "recommended-24gb",
    ]
    assert [item.recommended_default for item in catalog] == [True, False, False]


def test_load_runtime_manifest_keeps_pinned_size_and_digest_truth_for_starter_models():
    manifest = load_runtime_manifest()

    assert manifest["starter_models"]["recommended-6gb"]["size_bytes"] == 4683073536
    assert (
        manifest["starter_models"]["recommended-6gb"]["sha256"]
        == "fa9e1815472201e7dea978475c1f3ca7bc7df773eaeb3b3a383258c25b052f6f"
    )
    assert manifest["starter_models"]["recommended-12gb"]["size_bytes"] == 8988110272
    assert (
        manifest["starter_models"]["recommended-12gb"]["sha256"]
        == "f87bfd654aed5318df1819cc17b5204270b69d05d905c0fa6960d84e4843ba18"
    )
    assert manifest["starter_models"]["recommended-24gb"]["size_bytes"] == 19851335872
    assert (
        manifest["starter_models"]["recommended-24gb"]["sha256"]
        == "2687a00b84e7e35c652ea0024cb8747070b090e9f311ab9b6461b8a71c2bc50f"
    )


def test_list_prompt_starter_models_rejects_missing_prompt_metadata():
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "runtime-sha",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": "file-sha"},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "model-sha",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
                "size_bytes": 1,
                "prompt_order": 1,
                "recommended_default": True,
            }
        },
    }

    try:
        list_prompt_starter_models(manifest)
    except ValueError as error:
        assert "prompt_label" in str(error)
    else:
        raise AssertionError("Expected missing prompt_label metadata to fail.")


def test_resolve_requested_starter_model_returns_execution_entry_for_24gb():
    manifest = load_runtime_manifest()

    starter_model = resolve_requested_starter_model(manifest, "recommended-24gb")

    assert starter_model["id"] == "recommended-24gb"
    assert starter_model["target_filename"] == "recommended-24gb.gguf"
    assert starter_model["install_subdir"] == "models/recommended-24gb"
    assert starter_model["size_bytes"] == 19851335872
    assert "9d3053fce650fe1cdbdb75998c2a87add9d178ef" in starter_model["url"]


def test_starter_model_option_is_frozen():
    option = StarterModelOption(
        model_id="recommended-6gb",
        prompt_label="recommended-6gb",
        prompt_order=1,
        recommended_default=True,
    )

    assert option.model_id == "recommended-6gb"
