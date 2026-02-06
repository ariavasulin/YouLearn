"""Google Drive tools via Composio SDK for Agno agents."""

from __future__ import annotations

import json
import os

import structlog
from agno.tools import Toolkit
from composio import Composio

log = structlog.get_logger()

# Latest toolkit version as of 2026-02-06
_TOOLKIT_VERSION = "20260204_00"


class ComposioDriveTools(Toolkit):
    """Search, list, and download files from Google Drive via Composio."""

    def __init__(
        self,
        api_key: str | None = None,
        user_id: str | None = None,
    ):
        self._api_key = api_key or os.getenv("COMPOSIO_API_KEY", "")
        self._composio = Composio(api_key=self._api_key)
        # Resolve user_id from connected accounts if not provided
        self._user_id = user_id or self._resolve_user_id()
        super().__init__(
            name="google_drive",
            tools=[self.find_file, self.list_files, self.download_file],
        )

    def _resolve_user_id(self) -> str:
        """Find the Google Drive connected account's user_id."""
        try:
            accounts = self._composio.connected_accounts.list()
            for acct in accounts.items:
                if acct.toolkit.slug == "googledrive" and acct.status == "ACTIVE":
                    return acct.user_id
        except Exception:
            log.warning("composio_user_id_resolve_failed")
        return "default"

    def _execute(self, slug: str, arguments: dict) -> dict:
        """Execute a Composio tool and return the result."""
        return self._composio.tools.execute(
            slug=slug,
            arguments=arguments,
            user_id=self._user_id,
            version=_TOOLKIT_VERSION,
        )

    def find_file(self, search_query: str) -> str:
        """Search for files in the student's Google Drive.

        Use this when the student asks to find or import a file from Drive.
        Returns file names, IDs, and metadata.

        Args:
            search_query: What to search for. Can be a filename, keyword,
                         or file type (e.g. "Lecture 3 slides", "midterm review").

        Returns:
            JSON with matching files including name, id, and mimeType.
        """
        result = self._execute("GOOGLEDRIVE_FIND_FILE", {
            "search_query": search_query,
        })
        if result.get("successful"):
            return json.dumps(result.get("data", {}), indent=2, default=str)
        return f"Drive search failed: {result.get('error', 'unknown error')}"

    def list_files(self, folder_id: str = "root") -> str:
        """List files and folders in Google Drive.

        Use this to browse the student's Drive contents. Call with no arguments
        to list root-level files, or pass a folder_id to list a specific folder.

        Args:
            folder_id: The Google Drive folder ID to list. Defaults to root.

        Returns:
            JSON with files including name, id, and mimeType.
        """
        result = self._execute("GOOGLEDRIVE_FIND_FILE", {
            "search_query": f"'{folder_id}' in parents",
        })
        if result.get("successful"):
            return json.dumps(result.get("data", {}), indent=2, default=str)
        return f"Drive list failed: {result.get('error', 'unknown error')}"

    def download_file(self, file_id: str, file_name: str) -> str:
        """Download a file from Google Drive.

        Use this after finding a file with find_file. Downloads the file content.

        Args:
            file_id: The Google Drive file ID (from find_file results).
            file_name: The filename to reference in the response.

        Returns:
            The file content or a download status message.
        """
        result = self._execute("GOOGLEDRIVE_DOWNLOAD_FILE", {
            "file_id": file_id,
        })
        if result.get("successful"):
            data = result.get("data", {})
            return json.dumps({
                "status": "downloaded",
                "file_name": file_name,
                "content": data,
            }, indent=2, default=str)
        return f"Drive download failed: {result.get('error', 'unknown error')}"
