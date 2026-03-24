import re
import os

# skip these file types - binary files will just break things
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".otf",
    ".mp4", ".mp3", ".pdf",
    ".zip", ".tar", ".gz",
    ".pyc", ".pyo",
}

SKIP_FILENAMES = {
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
    "Pipfile.lock",
}

# dont send massive diffs to claude, it gets expensive fast
MAX_DIFF_LINES = 300


def _should_skip(filename):
    _, ext = os.path.splitext(filename.lower())
    base = os.path.basename(filename)
    return ext in SKIP_EXTENSIONS or base in SKIP_FILENAMES


def parse_diff(raw_diff):
    files = []

    # split the big diff string into sections per file
    file_sections = re.split(r"(?=^diff --git )", raw_diff, flags=re.MULTILINE)

    for section in file_sections:
        if not section.strip():
            continue

        # grab the filename from the diff header
        match = re.search(r"^diff --git a/(.+?) b/(.+?)$", section, re.MULTILINE)
        if not match:
            continue

        # use the b/ path (new file name) in case it was renamed
        filename = match.group(2)

        if _should_skip(filename):
            files.append({
                "filename": filename,
                "reviewable": False,
                "diff_text": "",
                "position_map": {},
                "added_lines": [],
            })
            continue

        if re.search(r"^Binary files", section, re.MULTILINE):
            files.append({
                "filename": filename,
                "reviewable": False,
                "diff_text": "",
                "position_map": {},
                "added_lines": [],
            })
            continue

        position_map, added_lines = _build_position_map(section)

        # truncate really big diffs so we dont blow up the token limit
        diff_lines = section.splitlines()
        if len(diff_lines) > MAX_DIFF_LINES:
            diff_text = "\n".join(diff_lines[:MAX_DIFF_LINES])
            diff_text += f"\n... (truncated after {MAX_DIFF_LINES} lines)"
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


def _build_position_map(diff_section):
    # this was the trickiest part to figure out
    # github doesnt use actual line numbers for inline comments, it uses
    # a position counter that increments for every line in the diff
    # including the @@ hunk headers and context lines
    # so we have to track both the real line number and the diff position

    position_map = {}
    added_lines = []

    diff_position = 0
    new_line_num = 0

    for line in diff_section.splitlines():
        # hunk header like @@ -1,3 +4,6 @@
        hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if hunk_match:
            diff_position += 1
            new_line_num = int(hunk_match.group(1)) - 1
            continue

        # skip the diff file headers
        if re.match(r"^(diff --git|index |--- |\+\+\+ |new file|deleted file|old mode|new mode)", line):
            continue

        if diff_position == 0:
            continue

        if line.startswith("+"):
            # added line - track both the line number and diff position
            new_line_num += 1
            diff_position += 1
            position_map[new_line_num] = diff_position
            added_lines.append((new_line_num, diff_position, line[1:]))

        elif line.startswith("-"):
            # deleted line - only diff position goes up, no new line number
            diff_position += 1

        else:
            # context line (unchanged)
            new_line_num += 1
            diff_position += 1
            position_map[new_line_num] = diff_position

    return position_map, added_lines


def get_diff_position(file_info, line_number):
    return file_info["position_map"].get(line_number)
