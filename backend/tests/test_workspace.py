"""Workspace manager tests."""

import pytest

from app.workspace.manager import WorkspaceManager


@pytest.mark.asyncio
async def test_workspace_lifecycle():
    mgr = WorkspaceManager()
    ws = await mgr.create_workspace("test-project")
    assert ws.workspace_id
    assert ws.root_path.exists()

    # Write and read file
    await mgr.write_file(ws.workspace_id, "hello.txt", "hello world")
    content = await mgr.read_file(ws.workspace_id, "hello.txt")
    assert content == "hello world"

    # Edit file
    success = await mgr.edit_file(ws.workspace_id, "hello.txt", "world", "universe")
    assert success
    content = await mgr.read_file(ws.workspace_id, "hello.txt")
    assert content == "hello universe"

    # List files
    files = await mgr.list_files(ws.workspace_id)
    assert any("hello.txt" in f for f in files)

    # Execute command
    result = await mgr.exec_command(ws.workspace_id, "echo test123")
    assert result.exit_code == 0
    assert "test123" in result.stdout

    # History
    history = mgr.get_execution_history(ws.workspace_id)
    assert len(history) == 1

    # Path traversal protection
    with pytest.raises(PermissionError):
        await mgr.read_file(ws.workspace_id, "../../etc/passwd")

    # Destroy
    await mgr.destroy_workspace(ws.workspace_id)
    assert not ws.root_path.exists()
