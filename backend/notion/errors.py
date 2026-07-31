# [Input] Shared Notion connector backend modules.
# [Output] Provide typed connector/auth/operation/snapshot exceptions.
# [Pos] error node in backend/notion
# [Sync] 2026-07-04: initial connector error hierarchy for auth, discovery,
#                    persistence, and workspace snapshot materialization.

"""Notion connector backend exceptions."""
from __future__ import annotations


class NotionConnectorError(Exception):
    """Base exception for Notion connector backend failures."""


class NotionConfigError(NotionConnectorError):
    """Invalid connector configuration or missing runtime settings."""


class NotionAuthError(NotionConnectorError):
    """Authentication flow failed."""


class NotionAuthTimeoutError(NotionAuthError):
    """Authentication polling timed out before confirmation."""


class NotionCLIUnavailableError(NotionAuthError):
    """The `ntn` CLI was not found on PATH."""


class NotionOperationError(NotionConnectorError):
    """A read-only Notion CLI operation failed."""


class NotionSnapshotError(NotionConnectorError):
    """Snapshot persistence or materialization failed."""


class NotionSnapshotNotReadyError(NotionSnapshotError):
    """A current canonical snapshot is not yet available."""


class NotionConnectorNotFoundError(NotionConnectorError):
    """Requested connector does not exist or does not belong to the user."""

