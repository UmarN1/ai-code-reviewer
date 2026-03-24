# main.py
# Entry point for the AI code reviewer action.
# I wrote this to tie everything together - it grabs the diff,
# sends it off to Claude, then posts the results back to GitHub.
#
# Author: Umar Naveed
# Built as part of my cloud portfolio - github.com/UmarN1

import os
import sys

from github_client import GitHubClient
from diff_parser import parse_diff
from claude_reviewer import ClaudeReviewer
from summary import build_summary


def main():
    # all these come from GitHub Actions environment variables
    # ANTHROPIC_API_KEY comes from our repo secret
    # everything else GitHub provides automatically
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    github_token = os.environ.get("GITHUB_TOKEN")
    repo_name = os.environ.get("REPO_NAME")
    pr_number = os.environ.get("PR_NUMBER")
    base_sha = os.environ.get("BASE_SHA")
    head_sha = os.environ.get("HEAD_SHA")

    # bail out early if anything is missing
    # better to fail fast than to get weird errors halfway through
    missing = []
    if not anthropic_key:
        missing.append("ANTHROPIC_API_KEY")
    if not github_token:
        missing.append("GITHUB_TOKEN")
    if not repo_name:
        missing.append("REPO_NAME")
    if not pr_number:
        missing.append("PR_NUMBER")
    if not base_sha:
        missing.append("BASE_SHA")
    if not head_sha:
        missing.append("HEAD_SHA")

    if missing:
        print(f"[ERROR] missing required env vars: {', '.join(missing)}")
        print("[ERROR] check your GitHub Actions secrets and workflow file")
        sys.exit(1)

    pr_number = int(pr_number)

    print(f"[INFO] starting review for PR #{pr_number} in {repo_name}")
    print(f"[INFO] base: {base_sha[:7]} | head: {head_sha[:7]}")

    gh = GitHubClient(token=github_token, repo=repo_name)
    reviewer = ClaudeReviewer(api_key=anthropic_key)

    # fetch the raw unified diff from github
    print("[INFO] fetching PR diff from GitHub...")
    raw_diff = gh.get_pr_diff(pr_number)

    if not raw_diff.strip():
        print("[INFO] diff is empty - nothing to review")
        return

    # parse the diff into individual file chunks
    files = parse_diff(raw_diff)
    reviewable_files = [f for f in files if f["reviewable"]]

    if not reviewable_files:
        print("[INFO] no reviewable files found")
        print("[INFO] (binary files, lock files, and generated files are skipped)")
        return

    print(f"[INFO] found {len(reviewable_files)} file(s) to review")

    # review each file and collect all the comments
    all_comments = []
    files_reviewed = []

    for file_info in reviewable_files:
        filename = file_info["filename"]
        print(f"[INFO] reviewing {filename}...")

        comments = reviewer.review_file(file_info)
        files_reviewed.append(filename)

        if comments:
            all_comments.extend(comments)
            print(f"[INFO]   found {len(comments)} issue(s)")
        else:
            print(f"[INFO]   no issues found")

    # post the summary comment first so it appears at the top of the PR
    # this gives reviewers a quick overview without having to scroll through everything
    print("[INFO] posting summary comment...")
    summary = build_summary(files_reviewed, all_comments)
    gh.post_summary_comment(pr_number=pr_number, summary_text=summary)

    # now post all the inline comments on the actual code lines
    if all_comments:
        print(f"[INFO] posting {len(all_comments)} inline comment(s)...")
        gh.post_review(
            pr_number=pr_number,
            commit_sha=head_sha,
            comments=all_comments,
        )
        print("[INFO] done!")
    else:
        gh.post_review_no_issues(pr_number=pr_number, commit_sha=head_sha)
        print("[INFO] no issues found - posted LGTM review")


if __name__ == "__main__":
    main()
