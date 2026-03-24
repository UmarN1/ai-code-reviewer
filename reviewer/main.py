import os
import sys

from github_client import GitHubClient
from diff_parser import parse_diff
from claude_reviewer import ClaudeReviewer
from summary import build_summary


def main():
    # get all the env variables we need
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    github_token = os.environ.get("GITHUB_TOKEN")
    repo_name = os.environ.get("REPO_NAME")
    pr_number = os.environ.get("PR_NUMBER")
    base_sha = os.environ.get("BASE_SHA")
    head_sha = os.environ.get("HEAD_SHA")

    # make sure everything is set before we do anything
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
        print(f"[ERROR] missing env vars: {', '.join(missing)}")
        sys.exit(1)

    pr_number = int(pr_number)

    print(f"[INFO] reviewing PR #{pr_number} in {repo_name}")
    print(f"[INFO] base: {base_sha[:7]} head: {head_sha[:7]}")

    gh = GitHubClient(token=github_token, repo=repo_name)
    reviewer = ClaudeReviewer(api_key=anthropic_key)

    # fetch the diff from github
    raw_diff = gh.get_pr_diff(pr_number)

    if not raw_diff.strip():
        print("[INFO] no diff found, skipping")
        return

    # split into individual files and filter out ones we cant review
    files = parse_diff(raw_diff)
    reviewable = [f for f in files if f["reviewable"]]

    if not reviewable:
        print("[INFO] no reviewable files found, probably all binary or lock files")
        return

    print(f"[INFO] found {len(reviewable)} file(s) to review")

    all_comments = []
    files_reviewed = []

    for file_info in reviewable:
        path = file_info["filename"]
        print(f"[INFO] reviewing {path}...")

        comments = reviewer.review_file(file_info)
        files_reviewed.append(path)

        if comments:
            all_comments.extend(comments)
            print(f"[INFO] got {len(comments)} comment(s) for {path}")
        else:
            print(f"[INFO] no issues found in {path}")

    # post the summary first so it shows up at the top of the PR
    summary = build_summary(files_reviewed, all_comments)
    gh.post_summary_comment(pr_number=pr_number, summary_text=summary)

    # then post the inline comments
    if all_comments:
        gh.post_review(
            pr_number=pr_number,
            commit_sha=head_sha,
            comments=all_comments,
        )
        print(f"[INFO] done - posted {len(all_comments)} inline comment(s)")
    else:
        gh.post_review_no_issues(pr_number=pr_number, commit_sha=head_sha)
        print("[INFO] no issues found, posted lgtm review")


if __name__ == "__main__":
    main()
