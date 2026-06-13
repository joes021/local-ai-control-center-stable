from pathlib import Path

from local_ai_control_center_installer.release_preflight import (
    ReleasePreflightFinding,
    scan_release_preflight_paths,
)


def test_release_preflight_flags_hardcoded_user_paths_and_machine_markers(tmp_path: Path):
    report = tmp_path / "report.md"
    local_user = "Azdaha" + "I9"
    remote_user = "Server" + "1"
    remote_host = remote_user + "@"
    remote_ip = ".".join(["100", "108", "15", "57"])
    report.write_text(
        "\n".join(
            [
                "Repo: C:\\Users\\" + local_user + "\\Documents\\local-ai-control-center-stable",
                "Install: C:\\Users\\" + remote_user + "\\LocalAIControlCenter",
                "Host: " + remote_host + remote_ip,
            ]
        ),
        encoding="utf-8",
    )

    findings = scan_release_preflight_paths([report])

    assert findings == [
        ReleasePreflightFinding(
            path=report,
            line_number=1,
            rule_id="hardcoded-windows-user-path",
            match="C:\\Users\\" + local_user,
        ),
        ReleasePreflightFinding(
            path=report,
            line_number=2,
            rule_id="hardcoded-windows-user-path",
            match="C:\\Users\\" + remote_user,
        ),
        ReleasePreflightFinding(
            path=report,
            line_number=3,
            rule_id="named-remote-host",
            match=remote_host,
        ),
        ReleasePreflightFinding(
            path=report,
            line_number=3,
            rule_id="hardcoded-private-ip",
            match=remote_ip,
        ),
    ]


def test_release_preflight_allows_generic_placeholders_and_reserved_examples(tmp_path: Path):
    report = tmp_path / "public.md"
    report.write_text(
        "\n".join(
            [
                r"Repo: C:\repo\local-ai-control-center-stable",
                r"Install: C:\Users\<user>\LocalAIControlCenter",
                r"Remote: C:\Users\<remote-user>\LocalAIControlCenter",
                "Host: example-host",
                "Fleet URL: http://192.0.2.10:3210",
            ]
        ),
        encoding="utf-8",
    )

    findings = scan_release_preflight_paths([report])

    assert findings == []
