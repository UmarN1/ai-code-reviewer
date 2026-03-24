import json
import re
import anthropic
from diff_parser import get_diff_position


# tried a few different prompts, this one gives the most useful results
SYSTEM_PROMPT = """You are a senior software engineer doing a thorough code review.
Look at the diff and identify real problems worth fixing.

Things to look for:
- Bugs and logic errors
- Security issues (SQL injection, hardcoded secrets, weak crypto, missing input validation)
- Performance problems (N+1 queries, loading entire files into memory, nested loops)
- Missing error handling
- Anything that would cause problems in production

Do NOT comment on:
- Code style or formatting
- Subjective naming preferences
- Things that look perfectly fine

Only flag things that genuinely need attention.

You must respond with a JSON array only. No extra text or markdown around it.
Each item should look like this:
{
  "line_number": <the line number in the new file>,
  "severity": <"error" or "warning" or "suggestion">,
  "comment": <your feedback as a markdown string>
}

Return [] if you find nothing wrong.

Important:
- line_number must be a line that actually appears in the diff
- be specific, reference the actual code in your comment
- max 5 comments per file, focus on the worst issues
- error = likely bug or security hole, warning = should fix, suggestion = nice to have
"""


class ClaudeReviewer:
    def __init__(self, api_key):
        self.client = anthropic.Anthropic(api_key=api_key)

    def review_file(self, file_info):
        filename = file_info["filename"]
        diff_text = file_info["diff_text"]

        if not diff_text.strip():
            return []

        prompt = (
            f"Please review this diff for `{filename}`:\n\n"
            f"```diff\n{diff_text}\n```\n\n"
            "Return a JSON array of issues you find. Return [] if everything looks fine."
        )

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIError as e:
            print(f"[ERROR] claude API error for {filename}: {e}")
            return []

        raw_text = response.content[0].text.strip()
        raw_comments = self._parse_response(raw_text, filename)

        # convert claude's line numbers to github diff positions
        # this is necessary because github's inline comment api doesnt
        # accept regular line numbers, it needs the diff position
        github_comments = []

        for item in raw_comments:
            line_num = item.get("line_number")
            severity = item.get("severity", "suggestion")
            comment_body = item.get("comment", "")

            if not line_num or not comment_body:
                continue

            diff_pos = get_diff_position(file_info, line_num)
            if diff_pos is None:
                # line wasnt in the diff so we cant attach a comment to it
                print(f"[WARN] line {line_num} not found in diff for {filename}, skipping")
                continue

            severity_label = {
                "error":      "🔴 **Error**",
                "warning":    "🟡 **Warning**",
                "suggestion": "🔵 **Suggestion**",
            }.get(severity, "🔵 **Suggestion**")

            full_comment = f"{severity_label}\n\n{comment_body}\n\n*— AI Code Reviewer*"

            github_comments.append({
                "path": filename,
                "position": diff_pos,
                "body": full_comment,
            })

        return github_comments

    def _parse_response(self, raw_text, filename):
        # claude sometimes wraps the json in markdown fences even when told not to
        # so we strip those out just in case
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.MULTILINE).strip()

        try:
            parsed = json.loads(clean)

            if isinstance(parsed, list):
                return parsed

            # sometimes it returns {"comments": [...]} instead of just the array
            if isinstance(parsed, dict):
                for key in ("comments", "issues", "review"):
                    if key in parsed and isinstance(parsed[key], list):
                        return parsed[key]

        except json.JSONDecodeError:
            print(f"[WARN] couldnt parse json response for {filename}")
            print(f"[WARN] response was: {raw_text[:200]}")

        return []
