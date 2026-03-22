"""
Diff parser — converts a raw unified diff into structured per-file data.

The trickiest part of this project is mapping Claude's feedback to a
GitHub diff *position*. GitHub's inline comment API does NOT use actual
line numbers — it uses a 1-indexed counter that increments for every line
in the diff hunk (including the @@ header lines and context lines).

This module builds that position map so we can tell GitHub exactly which
diff line to attach a comment to.
"""

import re
from typing import Optional

# Extensions we skip — binary, generated, or not worth reviewing
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp4", ".mp3", ".wav", ".pdf",
    ".zip", ".tar", ".gz", ".rar",
    ".pyc", ".pyo", ".class", ".o", ".so", ".dll", ".exe",
}

SKIP_FILENAMES = {
    "package-lock.json", "yarn.lock", "poetry.lock",
    "Pipfile.lock", "composer.lock", "Gemfile.lock",
}

# Max diff lines per file sent to Claude (keep tokens reasonable)
MAX_DIFF_LINES = 300


def _should_skip(filename: str) -> bool:
    import os
    _, ext = os.path.splitext(filename.lower())
    base = os.path.basename(filename)
    return ext in SKIP_EXTENSIONS or base in SKIP_FILENAMES


def parse_diff(raw_diff: str) -> list[dict]:
    """
    Parse a raw unified diff into a list of file dicts.

    Returns a list of dicts, each with:
        filename    — path of the changed file
        reviewable  — bool (False for binary/skipped files)
        diff_text   — the raw diff text for this file (truncated if huge)
        position_map — dict mapping actual new-file line numbers → diff positions
        added_lines  — list of (line_number, diff_position, line_content) for + lines
    """
    files = []
    current_file: Optional[dict] = None

    # Split on "diff --git" boundaries
    file_sections = re.split(r"(?=^diff --git )", raw_diff, flags=re.MULTILINE)

    for section in file_sections:
        if not section.strip():
            continue

        # Extract filename from the "diff --git a/... b/..." header
        match = re.search(r"^diff --git a/(.+?) b/(.+?)$", section, re.MULTILINE)
        if not match:
            continue

        filename = match.group(2)  # use the "b/" (new) path

        if _should_skip(filename):
            files.append({
                "filename": filename,
                "reviewable": False,
                "diff_text": "",
                "position_map": {},
                "added_lines": [],
            })
            continue

        # Check for binary file marker
        if re.search(r"^Binary files", section, re.MULTILINE):
            files.append({
                "filename": filename,
                "reviewable": False,
                "diff_text": "",
                "position_map": {},
                "added_lines": [],
            })
            continue

        # Build the position map and collect added lines
        position_map, added_lines = _build_position_map(section)

        # Truncate very large diffs to avoid token explosion
        diff_lines = section.splitlines()
        if len(diff_lines) > MAX_DIFF_LINES:
            truncated = diff_lines[:MAX_DIFF_LINES]
            truncated.append(f"... (diff truncated at {MAX_DIFF_LINES} lines for review)")
            diff_text = "\n".join(truncated)
        else:
            diff_text = section

        files.append({
            "filename": filename,
            "reviewable": True,
            "diff_text": diff_text,
            "position_map": position_map,
            "added_lines": added_lines,
        })

    return files


def _build_position_map(diff_section: str) -> tuple[dict, list]:
    """
    Walk through the diff section line by line and build:

    position_map: { new_line_number: diff_position }
        Used to map from a line number (what Claude sees) to a
        GitHub diff position (what the API needs).

    added_lines: [ (new_line_number, diff_position, line_content) ]
        Only the "+" lines — the ones Claude should comment on.

    GitHub diff position rules:
    - The @@ hunk header line itself counts as position 1 (for that hunk).
    - Every subsequent line (context, +, -) increments the position counter.
    - Deleted lines (-) increment the position counter but have no new line number.
    - The counter is global across all hunks in the file (does NOT reset per hunk).
    """
    position_map: dict[int, int] = {}
    added_lines: list[tuple[int, int, str]] = []

    diff_position = 0   # 1-indexed counter across the entire file diff
    new_line_num = 0    # current line number in the new file

    lines = diff_section.splitlines()

    for line in lines:
        # Hunk header: @@ -old_start,old_count +new_start,new_count @@
        hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if hunk_match:
            diff_position += 1
            new_line_num = int(hunk_match.group(1)) - 1  # will be incremented on first real line
            continue

        # Skip file header lines (diff --git, index, ---, +++)
        if re.match(r"^(diff --git|index |--- |\\+\\+\\+ |new file|deleted file|old mode|new mode)", line):
            continue

        if diff_position == 0:
            # Haven't hit a hunk header yet
            continue

        if line.startswith("+"):
            # Added line
            new_line_num += 1
            diff_position += 1
            position_map[new_line_num] = diff_position
            added_lines.append((new_line_num, diff_position, line[1:]))  # strip leading +

        elif line.startswith("-"):
            # Deleted line — increments diff position but not the new file line number
            diff_position += 1

        else:
            # Context line (unchanged)
            new_line_num += 1
            diff_position += 1
            position_map[new_line_num] = diff_position

    return position_map, added_lines


def get_diff_position(file_info: dict, line_number: int) -> Optional[int]:
    """
    Given a file_info dict and a new-file line number,
    return the GitHub diff position for that line.
    Returns None if the line number isn't in the diff.
    """
    return file_info["position_map"].get(line_number)
