# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only disposable DB snapshots SOLELY for delivery-history comparisons.

Not imported by any plugin and never used to reconstruct outcome order or as a
fallback for public reads. Native mutations remain tools/dispatcher operations.
"""
from contextlib import closing
from pathlib import Path
import sqlite3


def snapshot(base: Path, task_id: str) -> dict:
    """Reject symlink escapes; compare full history beyond public last-50 events."""
    root = base.resolve(strict=True)
    if not root.name.startswith("outcome-phase0-"):
        raise RuntimeError("snapshot is not disposable")
    path = root / "board-root/kanban/boards/phase0/kanban.db"
    if path.resolve(strict=True) != path or not path.is_relative_to(root):
        raise RuntimeError("snapshot path escaped disposable board")
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        return {name: [dict(row) for row in connection.execute(query, (task_id,))]
                for name, query in {
                    "task": "SELECT * FROM tasks WHERE id = ?",
                    "runs": "SELECT * FROM task_runs WHERE task_id = ? ORDER BY id",
                    "events": "SELECT * FROM task_events WHERE task_id = ? ORDER BY id",
                    "comments": "SELECT author, body, created_at FROM task_comments WHERE task_id = ? ORDER BY id",
                }.items()}


def preserved(before: dict, after: dict, additions: int) -> bool:
    """Permit only native comment-event additions, never rewrites of prior rows."""
    extra = after["events"][len(before["events"]):]
    return (before["task"] == after["task"] and before["runs"] == after["runs"] and
            after["events"][:len(before["events"])] == before["events"] and
            after["comments"][:len(before["comments"])] == before["comments"] and
            len(after["comments"]) == len(before["comments"]) + additions and
            len(extra) == additions and all(row["kind"] == "commented" for row in extra))
