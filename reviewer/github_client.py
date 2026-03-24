import requests

GITHUB_API = "https://api.github.com"

# extensions we skip - no point reviewing images or lock files
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf",
    ".mp4", ".mp3", ".pdf",
    ".zip", ".tar", ".gz",
    ".pyc",
}

SKIP_FILENAMES = {
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
    "Pipfile.lock",
}


class GitHubClient:
    def __init__(self, token, repo):
        self.repo = repo
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def _url(self, path):
        return f"{GITHUB_API}/repos/{self.repo}{path}"

    def get_pr_diff(self, pr_number):
        # have to use a different accept header to get the raw diff format
        url = self._url(f"/pulls/{pr_number}")
        headers = {
            **self.session.headers,
            "Accept": "application/vnd.github.v3.diff"
        }
        resp = self.session.get(url, headers=headers)
        resp.raise_for_status()
        return resp.text

    def post_summary_comment(self, pr_number, summary_text):
        # this posts to the PR conversation tab, not as an inline review comment
        url = self._url(f"/issues/{pr_number}/comments")
        resp = self.session.post(url, json={"body": summary_text})

        if not resp.ok:
            print(f"[WARN] summary comment failed with status {resp.status_code}")
            print(f"[WARN] {resp.text[:200]}")
        else:
            print("[INFO] summary comment posted ok")

        return resp

    def post_review(self, pr_number, commit_sha, comments):
        url = self._url(f"/pulls/{pr_number}/reviews")

        # build the payload - grouping all comments into one review is cleaner
        payload = {
            "commit_id": commit_sha,
            "event": "COMMENT",
            "body": "",
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
            # inline review failed, fall back to posting as a regular comment
            print(f"[WARN] review post failed with {resp.status_code}, trying fallback")
            self._post_fallback(pr_number, comments)

        return resp

    def post_review_no_issues(self, pr_number, commit_sha):
        url = self._url(f"/pulls/{pr_number}/reviews")
        payload = {
            "commit_id": commit_sha,
            "event": "COMMENT",
            "body": "Reviewed the changes - everything looks good :white_check_mark:",
            "comments": [],
        }
        resp = self.session.post(url, json=payload)
        resp.raise_for_status()

    def _post_fallback(self, pr_number, comments):
        # if the inline review api fails for some reason we at least
        # want to post the feedback somewhere visible
        # TODO: maybe log which comments failed and why
        url = self._url(f"/issues/{pr_number}/comments")

        lines = ["## AI Code Review\n"]
        for c in comments:
            lines.append(f"**`{c['path']}`** (diff position {c['position']})\n")
            lines.append(c["body"])
            lines.append("\n---\n")

        self.session.post(url, json={"body": "\n".join(lines)})
        print("[INFO] posted fallback comment")
