"""
GitHub API client — fetches PR diffs and posts inline review comments.
Uses the GitHub REST API v3.
"""

import requests


GITHUB_API = "https://api.github.com"

# File extensions worth reviewing. Binary and lock files are skipped.
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2",
    ".ttf", ".eot", ".mp4", ".mp3", ".pdf", ".zip", ".tar", ".gz",
    "package-lock.json", "yarn.lock", "poetry.lock", "Pipfile.lock",
    ".min.js", ".min.css",
}


class GitHubClient:
    def __init__(self, token: str, repo: str):
        self.repo = repo
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def _url(self, path: str) -> str:
        return f"{GITHUB_API}/repos/{self.repo}{path}"

    def get_pr_diff(self, pr_number: int) -> str:
        """Fetch the unified diff for a pull request."""
        url = self._url(f"/pulls/{pr_number}")
        resp = self.session.get(
            url,
            headers={**self.session.headers, "Accept": "application/vnd.github.v3.diff"},
        )
        resp.raise_for_status()
        return resp.text

    def post_review(self, pr_number: int, commit_sha: str, comments: list[dict]):
        """
        Post an inline review with comments to a pull request.

        Each comment dict must have:
            path       — file path relative to repo root
            position   — line position in the diff (1-indexed)
            body       — markdown comment text
        """
        url = self._url(f"/pulls/{pr_number}/reviews")
        payload = {
            "commit_id": commit_sha,
            "event": "COMMENT",
            "body": (
                "## AI Code Review\n\n"
                "I reviewed the changes in this PR and found the following points "
                "worth addressing. These are AI-generated suggestions — please use "
                "your judgment before acting on them.\n\n"
                f"_{len(comments)} inline comment(s) posted below._"
            ),
            "comments": [
                {
                    "path": c["path"],
                    "position": c["position"],
                    "body": c["body"],
                }
                for c in comments
            ],
        }
        resp = self.session.post(url, json=payload)
        if not resp.ok:
            print(f"[WARN] GitHub API returned {resp.status_code}: {resp.text}")
            # Fallback: post as a single PR comment instead of inline
            self._post_fallback_comment(pr_number, comments)
        return resp

    def post_review_no_issues(self, pr_number: int, commit_sha: str):
        """Post an LGTM review when no issues are found."""
        url = self._url(f"/pulls/{pr_number}/reviews")
        payload = {
            "commit_id": commit_sha,
            "event": "COMMENT",
            "body": (
                "## AI Code Review\n\n"
                "Reviewed the changes in this PR — no significant issues found. "
                "Code looks clean. Nice work! :white_check_mark:"
            ),
            "comments": [],
        }
        resp = self.session.post(url, json=payload)
        resp.raise_for_status()

    def _post_fallback_comment(self, pr_number: int, comments: list[dict]):
        """Fallback: post all comments as a single issue comment."""
        url = self._url(f"/issues/{pr_number}/comments")
        body_lines = ["## AI Code Review\n"]
        for c in comments:
            body_lines.append(f"**`{c['path']}`** (diff position {c['position']})\n")
            body_lines.append(c["body"])
            body_lines.append("\n---\n")
        self.session.post(url, json={"body": "\n".join(body_lines)})
