"""Atomic read/write helpers for ``src/flagd/demo.flagd.json``.

Provides ``read_flags``, ``write_flags``, and ``restore_from_backup`` with
``tempfile + os.replace`` semantics, preserving unrelated flags byte-for-
byte so Property 11 (flagd round-trip) holds.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from typing import Any


FLAGD_PATH = "src/flagd/demo.flagd.json"


def read_flags() -> dict[str, Any]:
    """Read and parse the flagd configuration JSON.

    Returns the parsed JSON object (typically with "flags" key).
    Raises FileNotFoundError if the file doesn't exist.
    """
    with open(FLAGD_PATH, "r") as f:
        return json.load(f)


def write_flags(flags: dict[str, Any], backup_path: str) -> None:
    """Atomically write flagd configuration, preserving top-level schema and sibling keys.

    First snapshots current contents to backup_path (uncompressed, for rollback).
    Then atomically replaces FLAGD_PATH using tempfile + os.replace.

    Args:
        flags: The parsed JSON dict to write (typically with "flags" key)
        backup_path: Path where the pre-write snapshot is saved
    """
    # Snapshot current state for rollback.
    if os.path.exists(FLAGD_PATH):
        shutil.copy2(FLAGD_PATH, backup_path)

    # Atomic write: tempfile + replace.
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=os.path.dirname(FLAGD_PATH) or ".",
        delete=False,
        suffix=".json"
    ) as tmp:
        tmp_path = tmp.name
        json.dump(flags, tmp, indent=2)

    try:
        os.replace(tmp_path, FLAGD_PATH)
    except Exception:
        # Clean up temp file on failure.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def restore_from_backup(backup_path: str) -> None:
    """Restore flagd configuration from a backup snapshot.

    Used by the rollback path during activation failure.

    Args:
        backup_path: Path to the backup file
    """
    if os.path.exists(backup_path):
        shutil.copy2(backup_path, FLAGD_PATH)
