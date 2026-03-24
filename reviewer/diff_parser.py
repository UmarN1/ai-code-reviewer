# diff_parser.py
# Parses the raw unified diff that GitHub gives us and breaks it down
# into individual files with their changed lines.
#
# The trickiest part of this whole project was figuring out GitHub's
# diff position system. When you post an inline comment on a PR,
# GitHub doesn't let you use actual line numbers - it uses a "position"
# counter that increments for every line in the raw diff output,
# including the @@ headers and unchanged context lines.
#
# I had to read through GitHub's API docs a few times before this
# clicked. The position map we build here converts real line numbers
# (what Claude gives us back) into diff positions (what GitHub needs).

import re
import os

# anything over this many lines gets truncated before sending to Claude
# keeps the API costs reasonable and avoids token limit issues
MAX_DIFF_LINES = 300

# file types to skip - binary files, generated files, lockfiles etc.
# these aren't worth reviewing and would just waste tokens
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp4", ".mp3", ".wav",
    ".pdf", ".zip", ".tar", ".gz", ".rar",
    ".pyc", ".pyo", ".class", ".o", ".so", ".dll", ".exe",
}

SKIP_FILENAMES = {
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
    "Pipfile.lock",
    "composer.lock",
    "Gemfile.lock",
}


def should_skip_file(filename):
    # check if this file type is worth reviewing
    _, ext = os.path.splitext(filename.lower())
    base = os.path.basename(filename)

    if ext in SKIP_EXTENSIONS:
        return True
    if base in SKIP_FILENAMES:
        return True
    # skip minified files
    if filename.endswith(".min.js") or filename.endswith(".min.css"):
        return True

    return False


def parse_diff(raw_diff):
    """
    Takes the raw unified diff string and returns a list of file dicts.

    Each dict has:
        filename     - path of the file that changed
        reviewable   - False if we're skipping this file
        diff_text    - the actual diff content (truncated if huge)
        position_map - maps real line numbers to GitHub diff positions
        added_lines  - list of (line_num, diff_position, content) for new lines
    """
    results = []

    # split the big diff into sections by file
    # each section starts with "diff --git a/... b/..."
    file_sections = re.split(r"(?=^diff --git )", raw_diff, flags=re.MULTILINE)

    for section in file_sections:
        if not section.strip():
            continue

        # get the filename from the diff header
        header_match = re.search(
            r"^diff --git a/(.+?) b/(.+?)$",
            section,
            re.MULTILINE
        )
        if not header_match:
            continue

        # use the "b/" path (the new version of the file)
        filename = header_match.group(2)

        # skip files we don't want to review
        if should_skip_file(filename):
            results.append({
                "filename": filename,
                "reviewable": False,
                "diff_text": "",
                "position_map": {},
                "added_lines": [],
            })
            continue

        # skip binary files
        if re.search(r"^Binary files", section, re.MULTILINE):
            results.append({
                "filename": filename,
                "reviewable": False,
                "diff_text": "",
                "position_map": {},
                "added_lines": [],
            })
            continue

        # build the position map for this file
        position_map, added_lines = build_position_map(section)

        # truncate really big diffs so we don't blow up the API costs
        diff_lines = section.splitlines()
        if len(diff_lines) > MAX_DIFF_LINES:
            diff_lines = diff_lines[:MAX_DIFF_LINES]
            diff_lines.append(f"... (truncated at {MAX_DIFF_LINES} lines)")
            diff_text = "\n".join(diff_lines)
        else:
            diff_text = section

        results.append({
            "filename": filename,
            "reviewable": True,
            "diff_text": diff_text,
            "position_map": position_map,
            "added_lines": added_lines,
        })

    return results


def build_position_map(diff_section):
    """
    This is the key function - it walks through every line of the diff
    and builds a map from real file line numbers to GitHub diff positions.

    GitHub diff position rules (took me a while to figure these out):
    - The @@ hunk header counts as position 1 for that hunk
    - Every line after that increments the counter, including context lines
    - Deleted lines (-) increment the position but don't have a new line number
    - The counter does NOT reset between hunks - it keeps going for the whole file

    So if you want to comment on line 42 of the file, you first need to
    find what diff position that line ended up at. That's what the map is for.
    """
    position_map = {}   # line_number -> diff_position
    added_lines = []    # list of (line_number, diff_position, content)

    diff_position = 0
    current_line_number = 0

    for line in diff_section.splitlines():

        # hunk header like: @@ -10,7 +10,9 @@
        # the number after the + is where the new file starts from
        hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if hunk_match:
            diff_position += 1
            # subtract 1 because we increment before using it
            current_line_number = int(hunk_match.group(1)) - 1
            continue

        # skip the file header lines at the top of each section
        if re.match(r"^(diff --git|index |--- |\+\+\+ |new file|deleted file|old mode|new mode)", line):
            continue

        # haven't hit a hunk header yet, skip
        if diff_position == 0:
            continue

        if line.startswith("+"):
            # added line - both counters go up
            current_line_number += 1
            diff_position += 1
            position_map[current_line_number] = diff_position
            added_lines.append((current_line_number, diff_position, line[1:]))

        elif line.startswith("-"):
            # deleted line - only diff position goes up
            # (this line doesn't exist in the new file so no line number)
            diff_position += 1

        else:
            # context line (unchanged) - both counters go up
            current_line_number += 1
            diff_position += 1
            position_map[current_line_number] = diff_position

    return position_map, added_lines


def get_diff_position(file_info, line_number):
    # helper to look up the diff position for a given line number
    # returns None if that line isn't in the diff
    return file_info["position_map"].get(line_number)
