from pathlib import Path


def test_control_center_source_tree_exists():
    assert Path("frontend/src/App.tsx").is_file()
    assert Path(
        "src/local_ai_control_center_installer/control_center_backend/main.py"
    ).is_file()
