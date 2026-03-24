# claude_reviewer.py
# Sends file diffs to the Anthropic Claude API and parses the response.
#
# The main thing I had to think about here was the system prompt.
# Generic prompts give generic feedback. I wanted Claude to behave
# like a specific type of reviewer - someone senior, someone who
# prioritises real bugs over style opinions, and someone who gives
# actionable advice not just "this could be better".
#
# I also needed structured output so I can actually use the results
# programmatically. Getting Claude to return consistent JSON took a
# bit of prompt engineering.

import json
import re
import anthropic
from diff_parser import get_diff_position


# this is the most important part of the whole project honestly
# the prompt is what determines the quality of the reviews
SYSTEM_PROMPT = """You are a senior software engineer doing a code review.
You have 8 years of experience and you care about catching real problems,
not nitpicking style.

You review code diffs and give specific, line-level feedback. You focus on:

1. Security issues - SQL injection, hardcoded secrets, missing input validation,
   broken authentication, insecure defaults

2. Bugs - logic errors, null pointer issues, unhandled exceptions, off-by-one errors,
   race conditions, incorrect assumptions

3. Performance - N+1 queries, loading huge files into memory, O(n^2) loops,
   blocking calls in async code

4. Maintainability - functions that do too much, missing error handling,
   code that will be impossible to test or debug later

You do NOT comment on:
- Formatting, whitespace, or style (that's what linters are for)
- Things that are purely subjective preference
- Lines that look perfectly fine

You respond ONLY with a JSON array. No markdown, no explanation, just the array.
Each item has exactly these fields:

{
  "line_number": <integer - the line number in the new version of the file>,
  "severity": <"error" | "warning" | "suggestion">,
  "comment": <string - your feedback in GitHub markdown format>
}

If you find no real issues, return an empty array: []

Important rules:
- line_number must be a line that appears in the diff (a + or context line)
- Keep comments specific - mention the actual code, not vague generalities
- Maximum 5 comments per file - focus on the most important things
- error = definite bug or security hole
- warning = probably should fix this
- suggestion = consider this, but it's not urgent
"""


class ClaudeReviewer:

    def __init__(self, api_key):
        self.client = anthropic.Anthropic(api_key=api_key)

    def review_file(self, file_info):
        """
        Sends a single file diff to Claude and returns a list of
        comment dicts ready to post to GitHub.
        """
        filename = file_info["filename"]
        diff_text = file_info["diff_text"]

        if not diff_text.strip():
            return []

        # build the message - include filename so Claude has context
        # about what kind of file it's looking at
        user_message = (
            f"Please review this diff for `{filename}`:\n\n"
            f"```diff\n{diff_text}\n```\n\n"
            "Return a JSON array of issues. Return [] if the code looks fine."
        )

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_message}
                ],
            )
        except anthropic.APIError as e:
            print(f"[ERROR] Claude API error for {filename}: {e}")
            return []

        raw_text = response.content[0].text.strip()
        raw_comments = self._parse_json_response(raw_text, filename)

        # now we need to convert Claude's line numbers into GitHub diff positions
        # this is the part that took the most debugging to get right
        github_comments = []

        for item in raw_comments:
            line_num = item.get("line_number")
            severity = item.get("severity", "suggestion")
            comment_text = item.get("comment", "")

            if not line_num or not comment_text:
                continue

            # look up the diff position for this line number
            diff_pos = get_diff_position(file_info, line_num)

            if diff_pos is None:
                # Claude gave us a line number that's not in the diff
                # this can happen with context lines near the edge of a hunk
                print(f"[WARN] line {line_num} in {filename} not in diff, skipping")
                continue

            # format the comment with a severity badge
            if severity == "error":
                badge = "🔴 **Error**"
            elif severity == "warning":
                badge = "🟡 **Warning**"
            else:
                badge = "🔵 **Suggestion**"

            body = f"{badge}\n\n{comment_text}\n\n*— AI Code Reviewer*"

            github_comments.append({
                "path": filename,
                "position": diff_pos,
                "body": body,
            })

        return github_comments

    def _parse_json_response(self, raw_text, filename):
        # Claude usually returns clean JSON but sometimes wraps it in
        # markdown code fences even when you tell it not to
        # this handles both cases
        cleaned = re.sub(
            r"^```(?:json)?\s*|\s*```$",
            "",
            raw_text,
            flags=re.MULTILINE
        ).strip()

        try:
            parsed = json.loads(cleaned)

            # handle the case where Claude wraps the array in an object
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                for key in ("comments", "issues", "review", "results"):
                    if key in parsed and isinstance(parsed[key], list):
                        return parsed[key]

        except json.JSONDecodeError:
            print(f"[WARN] could not parse JSON response for {filename}")
            print(f"[WARN] raw response was: {raw_text[:300]}")

        return []
