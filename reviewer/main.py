"""
AI Code Reviewer — main entrypoint.
Orchestrates: fetch diff → parse → review with Claude → post comments to GitHub.
"""

import os
import sys
from github_client import GitHubClient
from diff_parser import parse_diff
from claude_reviewer import ClaudeReviewer


def main():
    # ── Environment ────────────────────────────────────────────────────────────
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    github_token = os.environ.get("GITHUB_TOKEN")
    repo_name = os.environ.get("REPO_NAME")
    pr_number = os.environ.get("PR_NUMBER")
    base_sha = os.environ.get("BASE_SHA")
    head_sha = os.environ.get("HEAD_SHA")

    missing = [
        name for name, val in {
            "ANTHROPIC_API_KEY": anthropic_key,
            "GITHUB_TOKEN": github_token,
            "REPO_NAME": repo_name,
            "PR_NUMBER": pr_number,
            "BASE_SHA": base_sha,
            "HEAD_SHA": head_sha,
        }.items() if not val
    ]
    if missing:
        print(f"[ERROR] Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    pr_number = int(pr_number)

    print(f"[INFO] Reviewing PR #{pr_number} in {repo_name}")
    print(f"[INFO] Comparing {base_sha[:7]}...{head_sha[:7]}")

    # ── Fetch diff from GitHub ─────────────────────────────────────────────────
    gh = GitHubClient(token=github_token, repo=repo_name)
    raw_diff = gh.get_pr_diff(pr_number)

    if not raw_diff.strip():
        print("[INFO] No diff found. Nothing to review.")
        return

    # ── Parse diff into per-file chunks ───────────────────────────────────────
    files = parse_diff(raw_diff)
    reviewable = [f for f in files if f["reviewable"]]

    if not reviewable:
        print("[INFO] No reviewable files (skipping binary/deleted files).")
        return

    print(f"[INFO] Found {len(reviewable)} file(s) to review.")

    # ── Review each file with Claude ──────────────────────────────────────────
    reviewer = ClaudeReviewer(api_key=anthropic_key)
    all_comments = []

    for file_info in reviewable:
        path = file_info["filename"]
        print(f"[INFO] Reviewing: {path}")
        comments = reviewer.review_file(file_info)
        if comments:
            all_comments.extend(comments)
            print(f"[INFO]   → {len(comments)} comment(s) generated.")
        else:
            print(f"[INFO]   → No issues found.")

    # ── Post review to GitHub ─────────────────────────────────────────────────
    if all_comments:
        gh.post_review(
            pr_number=pr_number,
            commit_sha=head_sha,
            comments=all_comments,
        )
        print(f"[INFO] Posted review with {len(all_comments)} inline comment(s).")
    else:
        gh.post_review_no_issues(pr_number=pr_number, commit_sha=head_sha)
        print("[INFO] No issues found. Posted LGTM review.")


if __name__ == "__main__":
    main()
