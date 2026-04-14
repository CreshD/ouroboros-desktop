import pathlib
import types

import ouroboros.agent_startup_checks as startup_mod
import ouroboros.world_profiler as world_profiler
from ouroboros.memory import Memory
from ouroboros.tools.registry import ToolRegistry


def test_check_version_sync_ignores_non_release_tag(tmp_path, monkeypatch):
    (tmp_path / "VERSION").write_text("4.7.0\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('version = "4.7.0"\n', encoding="utf-8")
    (tmp_path / "README.md").write_text("**Version:** 4.7.0\n", encoding="utf-8")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "ARCHITECTURE.md").write_text("# Ouroboros v4.7.0\n", encoding="utf-8")

    env = types.SimpleNamespace(
        repo_dir=tmp_path,
        repo_path=lambda rel: tmp_path / rel,
    )

    monkeypatch.setattr(
        startup_mod.subprocess,
        "run",
        lambda *args, **kwargs: types.SimpleNamespace(returncode=0, stdout="v4.6.0-test1\n"),
    )

    result, issues = startup_mod.check_version_sync(env)

    assert issues == 0
    assert result["status"] == "ok"
    assert result["latest_tag"] == "4.6.0-test1"
    assert result["tag_sync"] == "ignored_non_release_tag"


def test_memory_ensure_files_generates_world_profile(tmp_path, monkeypatch):
    calls = []

    def fake_generate(output_path: str):
        calls.append(output_path)
        pathlib.Path(output_path).write_text("# WORLD\n", encoding="utf-8")

    monkeypatch.setattr(world_profiler, "generate_world_profile", fake_generate)

    memory = Memory(drive_root=tmp_path, repo_dir=tmp_path)
    memory.ensure_files()
    memory.ensure_files()

    assert calls == [str(memory.world_path())]
    assert memory.world_path().read_text(encoding="utf-8") == "# WORLD\n"


def test_check_frozen_tool_parity_not_applicable_when_not_frozen(tmp_path, monkeypatch):
    """When sys.frozen is False, the check returns no issues (not applicable)."""
    tools_dir = tmp_path / "ouroboros/tools"
    tools_dir.mkdir(parents=True)

    # Create some fake tools
    (tools_dir / "core.py").write_text("def get_tools(): pass\n", encoding="utf-8")
    (tools_dir / "search.py").write_text("def get_tools(): pass\n", encoding="utf-8")

    env = types.SimpleNamespace(
        repo_dir=tmp_path,
        repo_path=lambda rel: tmp_path / rel,
    )

    monkeypatch.setattr(startup_mod.sys, "frozen", False, raising=False)

    result, issues = startup_mod.check_frozen_tool_parity(env)

    assert issues == 0
    assert result["frozen"] is False
    assert result["mismatches"] == []


def test_check_frozen_tool_parity_detects_missing_tool(tmp_path, monkeypatch):
    """When a new tool exists in the directory but not in the frozen list."""
    tools_dir = tmp_path / "ouroboros/tools"
    tools_dir.mkdir(parents=True)

    # Create tools: core.py, search.py, and NEW_TOOL.py (not in frozen list)
    (tools_dir / "core.py").write_text("def get_tools(): pass\n", encoding="utf-8")
    (tools_dir / "search.py").write_text("def get_tools(): pass\n", encoding="utf-8")
    (tools_dir / "NEW_TOOL.py").write_text("def get_tools(): pass\n", encoding="utf-8")

    env = types.SimpleNamespace(
        repo_dir=tmp_path,
        repo_path=lambda rel: tmp_path / rel,
    )

    monkeypatch.setattr(startup_mod.sys, "frozen", True, raising=False)

    # Mock the frozen list to not include NEW_TOOL
    fake_frozen_list = ["core", "search"]
    monkeypatch.setattr(
        ToolRegistry,
        "_FROZEN_TOOL_MODULES",
        fake_frozen_list,
    )

    result, issues = startup_mod.check_frozen_tool_parity(env)

    assert issues == 1
    assert result["frozen"] is True
    assert len(result["mismatches"]) == 1
    assert result["mismatches"][0]["type"] == "missing_from_frozen"
    assert "NEW_TOOL" in result["mismatches"][0]["tools"]


def test_check_frozen_tool_parity_detects_extra_in_frozen_list(tmp_path, monkeypatch):
    """When the frozen list refers to a tool that no longer exists."""
    tools_dir = tmp_path / "ouroboros/tools"
    tools_dir.mkdir(parents=True)

    # Only create core.py (removed old_tool.py)
    (tools_dir / "core.py").write_text("def get_tools(): pass\n", encoding="utf-8")

    env = types.SimpleNamespace(
        repo_dir=tmp_path,
        repo_path=lambda rel: tmp_path / rel,
    )

    monkeypatch.setattr(startup_mod.sys, "frozen", True, raising=False)

    # Mock the frozen list to include missing tool
    fake_frozen_list = ["core", "old_tool"]
    monkeypatch.setattr(
        ToolRegistry,
        "_FROZEN_TOOL_MODULES",
        fake_frozen_list,
    )

    result, issues = startup_mod.check_frozen_tool_parity(env)

    assert issues == 1
    assert result["frozen"] is True
    assert len(result["mismatches"]) == 1
    assert result["mismatches"][0]["type"] == "extra_in_frozen"
    assert "old_tool" in result["mismatches"][0]["tools"]


def test_check_frozen_tool_parity_ok_when_lists_match(tmp_path, monkeypatch):
    """When the frozen list and actual directory are in sync."""
    tools_dir = tmp_path / "ouroboros/tools"
    tools_dir.mkdir(parents=True)

    # Create tools matching the frozen list
    (tools_dir / "core.py").write_text("def get_tools(): pass\n", encoding="utf-8")
    (tools_dir / "search.py").write_text("def get_tools(): pass\n", encoding="utf-8")

    env = types.SimpleNamespace(
        repo_dir=tmp_path,
        repo_path=lambda rel: tmp_path / rel,
    )

    monkeypatch.setattr(startup_mod.sys, "frozen", True, raising=False)

    # Mock the frozen list to match actual tools
    fake_frozen_list = ["core", "search"]
    monkeypatch.setattr(
        ToolRegistry,
        "_FROZEN_TOOL_MODULES",
        fake_frozen_list,
    )

    result, issues = startup_mod.check_frozen_tool_parity(env)

    assert issues == 0
    assert result["frozen"] is True
    assert result["mismatches"] == []


def test_check_uncommitted_changes_skips_auto_rescue_outside_launcher(monkeypatch, tmp_path):
    env = types.SimpleNamespace(
        repo_dir=tmp_path,
        repo_path=lambda rel: tmp_path / rel,
        launcher_managed=False,
    )
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:3] == ["git", "status", "--porcelain"]:
            return types.SimpleNamespace(returncode=0, stdout=" M server.py\n")
        raise AssertionError(cmd)

    monkeypatch.delenv("OUROBOROS_MANAGED_BY_LAUNCHER", raising=False)
    monkeypatch.setattr(startup_mod.subprocess, "run", fake_run)

    result, issues = startup_mod.check_uncommitted_changes(env)

    assert issues == 1
    assert result["status"] == "warning"
    assert result["auto_committed"] is False
    assert result["auto_rescue_skipped"] == "not_launcher_managed"
    assert calls == [["git", "status", "--porcelain"]]


def test_check_uncommitted_changes_auto_rescue_when_launcher_managed(monkeypatch, tmp_path):
    env = types.SimpleNamespace(
        repo_dir=tmp_path,
        repo_path=lambda rel: tmp_path / rel,
        branch_dev="ouroboros",
        launcher_managed=True,
    )
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:3] == ["git", "status", "--porcelain"]:
            return types.SimpleNamespace(returncode=0, stdout=" M server.py\n")
        if cmd[:2] == ["git", "add"]:
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")
        if cmd[:2] == ["git", "commit"]:
            return types.SimpleNamespace(returncode=0, stdout="[ouroboros abc123] auto-rescue\n", stderr="")
        raise AssertionError(cmd)

    monkeypatch.setattr(startup_mod.subprocess, "run", fake_run)

    result, issues = startup_mod.check_uncommitted_changes(env)

    assert issues == 1
    assert result["status"] == "warning"
    assert result["auto_committed"] is True
    assert [cmd[:2] for cmd in calls] == [["git", "status"], ["git", "add"], ["git", "commit"]]
