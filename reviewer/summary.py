def build_summary(files_reviewed, all_comments):
    # count up each severity type
    errors = 0
    warnings = 0
    suggestions = 0

    for comment in all_comments:
        body = comment.get("body", "")
        if "Error" in body:
            errors += 1
        elif "Warning" in body:
            warnings += 1
        elif "Suggestion" in body:
            suggestions += 1

    total = errors + warnings + suggestions

    # pick a verdict based on what was found
    if errors > 0:
        verdict = "Changes requested — there are errors that should be fixed before merging."
    elif warnings > 0:
        verdict = "Mostly looks good but a few things are worth addressing."
    elif suggestions > 0:
        verdict = "Looks good — just a couple of minor suggestions."
    else:
        verdict = "No issues found. Looks clean!"

    lines = []
    lines.append("## AI Code Review Summary")
    lines.append("")
    lines.append(f"_{verdict}_")
    lines.append("")

    if total > 0:
        lines.append("### Issues found")
        lines.append("")
        if errors > 0:
            lines.append(f"- 🔴 **{errors} error(s)** — needs fixing before merge")
        if warnings > 0:
            lines.append(f"- 🟡 **{warnings} warning(s)** — should look at these")
        if suggestions > 0:
            lines.append(f"- 🔵 **{suggestions} suggestion(s)** — optional improvements")
        lines.append("")
    else:
        lines.append(":white_check_mark: No issues found across all reviewed files.")
        lines.append("")

    # list out which files were checked and how many issues each had
    if files_reviewed:
        lines.append("### Files reviewed")
        lines.append("")

        for filename in files_reviewed:
            file_comments = [c for c in all_comments if c.get("path") == filename]
            count = len(file_comments)

            if count == 0:
                lines.append(f"- `{filename}` — no issues")
            elif count == 1:
                lines.append(f"- `{filename}` — 1 issue found")
            else:
                lines.append(f"- `{filename}` — {count} issues found")

        lines.append("")

    lines.append("---")
    lines.append("_Reviewed by Claude Sonnet · [AI Code Reviewer](https://github.com/UmarN1/ai-code-reviewer)_")

    return "\n".join(lines)
