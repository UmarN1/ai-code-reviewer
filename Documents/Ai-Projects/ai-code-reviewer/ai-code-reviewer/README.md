# AI Code Reviewer

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-enabled-2088FF?logo=github-actions&logoColor=white)
![Claude API](https://img.shields.io/badge/Claude-Sonnet_4-orange?logo=anthropic&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

A GitHub Action that automatically reviews every pull request using the **Anthropic Claude API**. When a PR is opened or updated, the action fetches the diff, sends each changed file to Claude acting as a senior engineer, and posts **inline review comments** directly on the relevant lines of code.

No manual code review bot setup. No hosted servers. Pure serverless GitHub Actions.

---

## Demo

When a PR is opened, the bot automatically appears:

```
🔴 Error

The `user_id` parameter is passed directly into the SQL query string without
sanitisation. This is a classic SQL injection vulnerability.

Consider using parameterised queries instead:

cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))

— AI Code Reviewer
```

```
🟡 Warning

`fetch_data()` is called inside a `for` loop on line 34, resulting in N+1
database queries. Consider batching this into a single query outside the loop
and filtering in memory, or using `SELECT ... WHERE id IN (...)`.

— AI Code Reviewer
```

```
🔵 Suggestion

This function is 87 lines long and handles both validation and persistence.
Consider splitting into `validate_payload()` and `save_record()` — it will
be significantly easier to unit test each concern independently.

— AI Code Reviewer
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GitHub Repository                        │
│                                                                 │
│  Developer opens PR                                             │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────────┐    triggers    ┌──────────────────────┐   │
│  │   Pull Request   │ ─────────────▶│  GitHub Actions       │   │
│  │  (code changes)  │               │  ai-review.yml        │   │
│  └─────────────────┘               └──────────┬───────────┘   │
│                                               │                │
│                                               ▼                │
│                                    ┌──────────────────────┐   │
│                                    │  Python Runner        │   │
│                                    │  ubuntu-latest        │   │
│                                    └──────────┬───────────┘   │
│                                               │                │
└───────────────────────────────────────────────┼────────────────┘
                                                │
          ┌─────────────────────────────────────┤
          │                                     │
          ▼                                     ▼
  ┌──────────────────┐               ┌─────────────────────┐
  │   GitHub REST API │               │  Anthropic Claude   │
  │                  │               │  claude-sonnet-4    │
  │  GET /pulls/diff  │               │                     │
  │  POST /reviews    │               │  Senior engineer    │
  └──────────────────┘               │  system prompt      │
                                     └─────────────────────┘
```

**Flow:**
1. PR opened/updated → GitHub Actions triggers `ai-review.yml`
2. `main.py` fetches the raw unified diff via GitHub API
3. `diff_parser.py` splits diff into per-file chunks and builds the **diff position map** (the tricky part — maps actual line numbers to GitHub's 1-indexed diff position counter)
4. `claude_reviewer.py` sends each file diff to Claude with a structured system prompt requesting JSON output
5. Claude returns an array of `{ line_number, severity, comment }` objects
6. Comments are mapped from line numbers → diff positions and posted as **inline PR review comments** via GitHub API

---

## How It Works

### Diff Position Mapping

GitHub's inline comment API doesn't use actual line numbers — it uses a **diff position** counter that increments for every line in the unified diff (including hunk headers and context lines). This is the most technically challenging part of the project.

`diff_parser.py` solves this by walking the raw diff line-by-line:

- `@@` hunk header → position increments, new line counter resets to hunk start
- `+` added line → both counters increment; position is recorded in the map
- `-` deleted line → only diff position increments (no new line number)
- ` ` context line → both counters increment

This produces a `position_map: { new_line_number → diff_position }` used to attach Claude's comments to the exact correct line in the GitHub UI.

### Claude System Prompt

The system prompt instructs Claude to act as a senior engineer and return structured JSON:

```json
[
  {
    "line_number": 42,
    "severity": "error",
    "comment": "SQL injection vulnerability — use parameterised queries."
  }
]
```

This structured output approach is more reliable than parsing freeform text and allows clean mapping to GitHub's review comment API.

---

## Setup

### 1. Fork or clone this repository

```bash
git clone https://github.com/YOUR_USERNAME/ai-code-reviewer.git
cd ai-code-reviewer
```

### 2. Get your Anthropic API key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up / log in
3. Navigate to **API Keys** → **Create Key**
4. Copy the key (starts with `sk-ant-...`)

### 3. Add the secret to your GitHub repository

1. Go to your repo on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `ANTHROPIC_API_KEY`
5. Value: paste your key
6. Click **Add secret**

> **Note on `GITHUB_TOKEN`:** You do NOT need to add this manually. GitHub automatically provides it to every Actions workflow. It's already referenced in the workflow YAML as `${{ secrets.GITHUB_TOKEN }}`.

### 4. Enable Actions write permissions

1. Go to **Settings** → **Actions** → **General**
2. Scroll to **Workflow permissions**
3. Select **Read and write permissions**
4. Check **Allow GitHub Actions to create and approve pull requests**
5. Click **Save**

### 5. Push the code and open a test PR

The action triggers automatically on any pull request. See the [Demo section](#creating-a-demo-pr) below.

---

## Configuration

| Environment Variable | Source | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | GitHub Secret | Your Anthropic API key |
| `GITHUB_TOKEN` | Auto-provided | GitHub token for posting comments |
| `REPO_NAME` | Auto-provided | `owner/repo` format |
| `PR_NUMBER` | Auto-provided | Pull request number |
| `BASE_SHA` | Auto-provided | Base commit SHA |
| `HEAD_SHA` | Auto-provided | Head commit SHA |

### Customising the reviewer

Edit `reviewer/claude_reviewer.py` to adjust:

- **`SYSTEM_PROMPT`** — change what Claude looks for or how it formats comments
- **`max_tokens`** — increase for more detailed reviews (higher cost)
- **`MAX_DIFF_LINES`** in `diff_parser.py` — controls truncation of large files

---

## Creating a Demo PR

To create a convincing demo for your portfolio:

### Step 1 — create a feature branch with intentional issues

```bash
git checkout -b feature/user-authentication
```

Create a file `auth/user_service.py` with realistic but flawed code:

```python
import sqlite3

def get_user(user_id):
    # SQL injection vulnerability — Claude will catch this
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    return cursor.fetchone()

def process_users(user_ids):
    results = []
    for uid in user_ids:
        # N+1 query problem — Claude will catch this too
        user = get_user(uid)
        results.append(user)
    return results

def validate_email(email):
    # Weak validation — Claude will flag this
    return "@" in email
```

### Step 2 — commit and push

```bash
git add .
git commit -m "feat: add user authentication service"
git push origin feature/user-authentication
```

### Step 3 — open a pull request

Go to your GitHub repo → **Pull requests** → **New pull request**
Set base: `main`, compare: `feature/user-authentication` → **Create pull request**

### Step 4 — watch the action run

Click the **Checks** tab on your PR. You'll see `AI Code Reviewer` running.
After ~30 seconds, inline comments will appear on the **Files changed** tab.

### Step 5 — screenshot for your portfolio

The **Files changed** tab with inline AI comments is the money screenshot.
Use [LICEcap](https://www.cockos.com/licecap/) (free) to record a GIF of:
1. Opening the PR
2. Clicking Files changed
3. Scrolling through the inline AI comments

---

## Common Errors & Fixes

### Action fails: `Resource not accessible by integration`

**Cause:** The `GITHUB_TOKEN` doesn't have write permissions to post PR reviews.

**Fix:** Go to **Settings → Actions → General → Workflow permissions** and select **Read and write permissions**.

---

### Comments post as a single PR comment instead of inline

**Cause:** The diff position mapping failed for those lines, so the fallback was triggered.

**Fix:** This usually happens with newly created files. Check the Actions log for `[WARN] Line X not found in diff` messages. The `diff_parser.py` position map handles standard diffs correctly — if you're seeing this, open an issue with your diff.

---

### `anthropic.APIError: 401 Unauthorized`

**Cause:** The `ANTHROPIC_API_KEY` secret is wrong or not set.

**Fix:** Go to **Settings → Secrets → Actions** and verify `ANTHROPIC_API_KEY` is set and starts with `sk-ant-`.

---

### Action runs but posts no comments

**Cause:** Claude found no issues (possible!) or the files were skipped (binary, lock files, etc).

**Fix:** Check the Actions log. Look for `[INFO] No issues found` or `[INFO] Found 0 file(s) to review`. Try the demo PR setup above which uses code with intentional issues.

---

### `ModuleNotFoundError`

**Cause:** Dependencies not installed or `PYTHONPATH` issue.

**Fix:** Ensure `requirements.txt` is in the repo root and the workflow `pip install -r requirements.txt` step runs before `python reviewer/main.py`.

---

## Project Structure

```
ai-code-reviewer/
├── .github/
│   └── workflows/
│       └── ai-review.yml        # GitHub Actions workflow definition
├── reviewer/
│   ├── main.py                  # Entrypoint — orchestrates the review pipeline
│   ├── github_client.py         # GitHub REST API — fetch diff, post comments
│   ├── diff_parser.py           # Unified diff parser + position map builder
│   └── claude_reviewer.py       # Anthropic API integration + response parsing
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Cost

Each PR review costs approximately **$0.001–$0.005** depending on the size of the diff. A busy repo with 50 PRs/month would cost roughly **$0.10–$0.25/month**.

---

## License

MIT — use this however you want.
