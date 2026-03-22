"""
Claude reviewer — sends file diffs to the Anthropic API and parses
structured review comments back out.

Uses claude-sonnet-4-20250514. The system prompt is engineered to produce
JSON-structured output so we can reliably map comments to diff positions.
"""

import json
import re
import anthropic
from diff_parser import get_diff_position


SYSTEM_PROMPT = """You are an expert senior software engineer conducting a thorough code review.
Your job is to review code changes (unified diffs) and provide specific, actionable, 
line-level feedback. You focus on:

1. **Bugs and correctness** — logic errors, off-by-one errors, null/undefined handling,
   incorrect assumptions, race conditions, unhandled exceptions.

2. **Security vulnerabilities** — SQL injection, XSS, hardcoded secrets, insecure 
   defaults, improper input validation, dependency issues.

3. **Performance problems** — unnecessary loops inside loops, missing indexes, 
   blocking calls in async code, memory leaks, inefficient algorithms.

4. **Code quality** — overly complex functions, missing error handling, unclear 
   variable names, code that will be hard to maintain or test.

5. **Best practices** — language-specific idioms being violated, missing type hints,
   magic numbers/strings, violation of DRY or SOLID principles.

You do NOT comment on:
- Stylistic preferences (tabs vs spaces, formatting) — that's what linters are for.
- Things that are purely subjective with no clear better option.
- Lines that look perfectly fine — only comment when there is a real concern.

OUTPUT FORMAT — you MUST respond with valid JSON only. No markdown fences, no prose.
Return a JSON array of comment objects. Each object has exactly these fields:

{
  "line_number": <integer — the line number in the new file being commented on>,
  "severity": <"error" | "warning" | "suggestion">,
  "comment": <string — your review comment in GitHub Markdown format>
}

If you find no issues, return an empty array: []

Rules:
- line_number must be a line that appears in the diff (a + line or context line).
- Keep each comment focused and specific. Reference the actual code.
- Use markdown in the comment field — backticks for code, bold for emphasis.
- Maximum 5 comments per file. Prioritize the most important issues.
- severity "error" = likely bug or security issue. "warning" = should fix. 
  "suggestion" = consider changing.
"""


class ClaudeReviewer:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def review_file(self, file_info: dict) -> list[dict]:
        """
        Review a single file diff with Claude.
        Returns a list of comment dicts ready to post to GitHub.
        """
        filename = file_info["filename"]
        diff_text = file_info["diff_text"]

        if not diff_text.strip():
            return []

        user_message = (
            f"Please review the following code diff for `{filename}`.\n\n"
            f"```diff\n{diff_text}\n```\n\n"
            "Respond with a JSON array of review comments as specified. "
            "Only comment on real issues — return [] if the code looks fine."
        )

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
        except anthropic.APIError as e:
            print(f"[ERROR] Anthropic API error for {filename}: {e}")
            return []

        raw_text = response.content[0].text.strip()
        raw_comments = self._parse_response(raw_text, filename)

        # Map Claude's line numbers to GitHub diff positions
        github_comments = []
        for item in raw_comments:
            line_num = item.get("line_number")
            severity = item.get("severity", "suggestion")
            comment_text = item.get("comment", "")

            if not line_num or not comment_text:
                continue

            diff_pos = get_diff_position(file_info, line_num)
            if diff_pos is None:
                # Line not in diff — skip (can't attach inline comment)
                print(f"[WARN] Line {line_num} in {filename} not found in diff, skipping.")
                continue

            # Format the comment body with severity badge
            severity_badge = {
                "error":      "🔴 **Error**",
                "warning":    "🟡 **Warning**",
                "suggestion": "🔵 **Suggestion**",
            }.get(severity, "🔵 **Suggestion**")

            body = f"{severity_badge}\n\n{comment_text}\n\n*— AI Code Reviewer*"

            github_comments.append({
                "path": filename,
                "position": diff_pos,
                "body": body,
            })

        return github_comments

    def _parse_response(self, raw_text: str, filename: str) -> list[dict]:
        """Parse Claude's JSON response, with fallback handling."""
        # Strip markdown code fences if Claude added them despite instructions
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.MULTILINE).strip()

        try:
            parsed = json.loads(clean)
            if isinstance(parsed, list):
                return parsed
            # Sometimes Claude wraps in {"comments": [...]}
            if isinstance(parsed, dict):
                for key in ("comments", "review", "issues", "results"):
                    if key in parsed and isinstance(parsed[key], list):
                        return parsed[key]
        except json.JSONDecodeError:
            print(f"[WARN] Could not parse JSON response for {filename}.")
            print(f"[WARN] Raw response: {raw_text[:200]}")

        return []
