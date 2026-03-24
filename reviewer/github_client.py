# github_client.py
# All the GitHub API calls live here - fetching diffs and posting comments.
# I kept it in its own file so main.py stays clean and readable.
#
# One thing that tripped me up early on: you need different Accept headers
# depending on what you're asking GitHub for. Regular JSON vs raw diff format
# are completely different endpoints basically.

import requests

GITHUB_API = "https://api.github.com"

# these file types aren't worth reviewing - no point sending a
# minified JS file or a lockfile to Claude
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot",
    ".mp4", ".mp3", ".pdf",
    ".zip", ".tar", ".gz",
    ".pyc", ".pyo", ".class",
    ".min.js", ".min.css",
}

SKIP_FILENAMES = {
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
    "Pipfile.lock",
    "composer.lock",
}


class GitHubClient:

    def __init__(self, token, repo):
        self.repo = repo

        # using a session so we don't have to pass headers every single time
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def _url(self, path):
        # helper so I don't have to type the full URL every time
        return f"{GITHUB_API}/repos/{self.repo}{path}"

    def get_pr_diff(self, pr_number):
        # GitHub needs a special Accept header to return the raw diff
        # without this it just returns the PR metadata as JSON
        url = self._url(f"/pulls/{pr_number}")
        diff_headers = {
            **self.session.headers,
            "Accept": "application/vnd.github.v3.diff",
        }
        resp = self.session.get(url, headers=diff_headers)
        resp.raise_for_status()
        return resp.text

    def post_summary_comment(self, pr_number, summary_text):
        # this posts a regular comment on the PR conversation tab
        # it shows up at the top before all the inline comments
        # using /issues/ endpoint because GitHub treats PR comments
        # the same as issue comments under the hood
        url = self._url(f"/issues/{pr_number}/comments")
        resp = self.session.post(url, json={"body": summary_text})

        if not resp.ok:
            print(f"[WARN] summary comment failed: {resp.status_code}")
            print(f"[WARN] {resp.text[:300]}")
        else:
            print("[INFO] summary posted ok")

        return resp

    def post_review(self, pr_number, commit_sha, comments):
        # post all inline comments as a single PR review
        # doing it as one review is cleaner than posting them individually
        # and means GitHub groups them all under one "AI Code Reviewer reviewed" entry
        url = self._url(f"/pulls/{pr_number}/reviews")

        payload = {
            "commit_id": commit_sha,
            "event": "COMMENT",
            "body": "",  # summary is already posted separately
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
            # if inline comments fail, fall back to a single regular comment
            # so the feedback isn't completely lost
            print(f"[WARN] inline review failed with {resp.status_code}, using fallback")
            self._post_as_single_comment(pr_number, comments)

        return resp

    def post_review_no_issues(self, pr_number, commit_sha):
        # called when claude finds nothing wrong - still post something
        # so people know the review actually ran
        url = self._url(f"/pulls/{pr_number}/reviews")
        payload = {
            "commit_id": commit_sha,
            "event": "COMMENT",
            "body": "Reviewed the changes in this PR — no issues found. Code looks clean! :white_check_mark:",
            "comments": [],
        }
        resp = self.session.post(url, json=payload)
        resp.raise_for_status()

    def _post_as_single_comment(self, pr_number, comments):
        # fallback method - if we can't post inline comments for some reason,
        # dump everything into one big comment instead
        url = self._url(f"/issues/{pr_number}/comments")

        lines = ["## AI Code Review (inline comments unavailable)\n"]
        for c in comments:
            lines.append(f"**File:** `{c['path']}` | **Diff position:** {c['position']}\n")
            lines.append(c["body"])
            lines.append("\n---\n")

        body = "\n".join(lines)
        resp = self.session.post(url, json={"body": body})

        if resp.ok:
            print("[INFO] fallback comment posted successfully")
        else:
            print(f"[ERROR] fallback also failed: {resp.status_code}")
