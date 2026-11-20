"""Tests for MCP file upload functionality via consolidated source_add."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def allowed_mcp_test_staging(monkeypatch):
    """Constrain MCP test uploads to their temporary staging root."""
    monkeypatch.setenv("NOTEBOOKLM_ALLOWED_FILE_DIRS", tempfile.gettempdir())


class TestMCPSourceAddFile:
    """Test file upload via the consolidated source_add MCP tool."""

    def test_source_add_file_exists(self):
        """Test that source_add tool with file type is available."""
        from notebooklm_tools.mcp.tools import sources

        # Check if source_add exists and supports file type
        assert hasattr(sources, "source_add")

    def test_source_add_file_calls_client(self):
        """Test that source_add file type calls client.add_file correctly."""
        from notebooklm_tools.mcp.tools import _utils, sources

        # Create a test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test content")
            temp_path = f.name

        try:
            # Mock the client
            mock_client = MagicMock()
            mock_client.add_file.return_value = {"id": "test-source-id", "title": "test.txt"}

            # Reset and patch get_client in sources module where it's imported
            _utils.reset_client()
            with patch("notebooklm_tools.mcp.tools.sources.get_client", return_value=mock_client):
                result = sources.source_add(
                    notebook_id="test-notebook-123", source_type="file", file_path=temp_path
                )

            # Verify client.add_file was called with correct args
            mock_client.add_file.assert_called_once_with(
                "test-notebook-123", temp_path, wait=False, wait_timeout=120.0
            )

            # Verify return value
            assert result["status"] == "success"
            assert result["source_id"] == "test-source-id"
            assert result["source_type"] == "file"
        finally:
            Path(temp_path).unlink()

    def test_source_add_file_requires_path(self):
        """Test that file_path is required for source_type=file."""
        from notebooklm_tools.mcp.tools import sources

        with patch("notebooklm_tools.mcp.tools.sources.get_client", return_value=MagicMock()):
            result = sources.source_add(
                notebook_id="test-notebook",
                source_type="file",
                # Missing file_path
            )

        assert result["status"] == "error"
        assert "file_path is required" in result["error"]

    def test_source_add_file_returns_server_path_and_reason(self, tmp_path):
        """File failures identify the server-side path that could not be read."""
        from notebooklm_tools.mcp.tools import sources

        requested_path = tmp_path / "missing.pdf"
        resolved_path = requested_path.resolve()
        mock_client = MagicMock()
        mock_client.add_file.side_effect = FileNotFoundError(f"File not found: {resolved_path}")

        with patch(
            "notebooklm_tools.mcp.tools.sources.get_client",
            return_value=mock_client,
        ):
            result = sources.source_add(
                notebook_id="test-notebook",
                source_type="file",
                file_path=str(requested_path),
            )

        assert result["status"] == "error"
        assert result["error"] == f"Could not add file source: File not found: {resolved_path}"
        assert "machine running nlm or the MCP server" in result["hint"]
        assert str(requested_path) in result["hint"]


def test_mcp_file_upload_requires_configured_root(monkeypatch, tmp_path):
    from notebooklm_tools.mcp.tools import sources

    monkeypatch.delenv("NOTEBOOKLM_ALLOWED_FILE_DIRS", raising=False)
    mock_client = MagicMock()
    with patch("notebooklm_tools.mcp.tools.sources.get_client", return_value=mock_client):
        result = sources.source_add("nb", "file", file_path=str(tmp_path / "secret.pdf"))

    assert result["status"] == "error"
    assert "NOTEBOOKLM_ALLOWED_FILE_DIRS" in result["error"]
    mock_client.add_file.assert_not_called()


def test_mcp_file_upload_rejects_non_staged_path(monkeypatch, tmp_path):
    from notebooklm_tools.mcp.tools import sources

    staged = tmp_path / "staged"
    staged.mkdir()
    monkeypatch.setenv("NOTEBOOKLM_ALLOWED_FILE_DIRS", str(staged))
    mock_client = MagicMock()
    with patch("notebooklm_tools.mcp.tools.sources.get_client", return_value=mock_client):
        result = sources.source_add("nb", "file", file_path=str(tmp_path / "private.pdf"))

    assert result["status"] == "error"
    assert "outside allowed directories" in result["error"]
    mock_client.add_file.assert_not_called()
