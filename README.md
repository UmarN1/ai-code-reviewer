# AI Code Reviewer

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-enabled-2088FF?logo=github-actions&logoColor=white)
![Claude API](https://img.shields.io/badge/Claude-Sonnet_4-orange?logo=anthropic&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

---

## What is this?

Every engineering team has the same problem — code review is slow, inconsistent, and the most experienced people are always the most stretched. Junior devs wait days for feedback. Senior engineers spend hours reviewing instead of building. And the obvious bugs? They still slip through.

I built this to solve that.

**AI Code Reviewer** is a GitHub Action that automatically reviews every pull request the moment it's opened. It reads the diff, understands what changed, and posts specific inline comments directly on the lines that need attention — just like a senior engineer would, but in under 30 seconds.

No server to maintain. No subscription. No setup beyond adding one API key. It just works, on every PR, every time.

---

## What it actually catches

This is not a linter. It does not care about semicolons or tab widths. It thinks like an engineer.

**Security vulnerabilities**

```python
# What it catches:
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")

# What it posts on that exact line:
# 🔴 Error
# Classic SQL injection. user_id is interpolated directly into the query
# string — an attacker can pass "1 OR 1=1" and dump your entire users table.
# Fix: cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

**Performance problems**

```python
# What it catches:
for uid in user_ids:
    user = get_user(uid)  # one DB call per user

# 🟡 Warning
# N+1 query pattern. This fires one database round trip per user_id.
# With 1000 users that is 1000 queries. Batch into WHERE id IN (...).
```

**Broken cryptography**

```python
# What it catches:
password_hash = hashlib.md5(password.encode()).hexdigest()

# 🔴 Error
# MD5 is cryptographically broken for password hashing.
# Rainbow tables can reverse MD5 hashes in seconds.
# Use bcrypt or argon2 with a salt instead.
```

**Hardcoded secrets**

```python
# What it catches immediately:
SECRET_KEY = "super_secret_key_123"
DATABASE_URL = "postgresql://admin:password123@localhost/mydb"

# Credentials in source code get picked up by automated scanners
# within minutes of being pushed to a public repo.
```

---

## The hard part — diff position mapping

The interesting technical challenge here is not calling an AI API. That part is straightforward. The hard part is GitHub's diff position system.

When you post an inline comment on a PR, GitHub does not let you say "attach this to line 42 of the file." It uses a position counter that increments for every line in the raw unified diff — including hunk headers and unchanged context lines. Get this wrong and your comments either fail silently or land on completely the wrong lines.

Here is what the mapping looks like:

```
Raw diff line          What it is          Position counter
─────────────────────────────────────────────────────────
@@ -1,3 +1,6 @@       Hunk header         1  (resets here)
 import os             Context line        2
+import sqlite3        Added line          3  ← commentable
+def get_user(uid):    Added line          4  ← commentable
-old_function()        Deleted line        5  (no new line number)
 print("hello")        Context line        6
```

diff_parser.py walks every line of the raw diff and builds a lookup table: new file line number → GitHub diff position. Claude returns comments with real line numbers. The mapper converts them before hitting the GitHub API. This is what makes the comments land on the exact right lines every time.

---

## How the full pipeline works

```
PR opened or updated
        │
        ▼
GitHub Actions triggers ai-review.yml
        │
        ▼
Fetch raw unified diff via GitHub REST API
        │
        ▼
diff_parser.py
  → splits diff into per-file chunks
  → builds position map { line_number → diff_position }
  → skips binary files, lock files, minified assets
        │
        ▼
claude_reviewer.py
  → sends each file diff to Claude Sonnet
  → structured system prompt: act as senior engineer
  → requests JSON output: [{ line_number, severity, comment }]
        │
        ▼
Map line numbers → diff positions
        │
        ▼
github_client.py posts inline review
via GitHub Pull Request Reviews API
        │
        ▼
Comments appear on the exact lines in the PR
within 30 seconds of the PR being opened
```

---

## Project structure

```
ai-code-reviewer/
├── .github/
│   └── workflows/
│       └── ai-review.yml        the Action definition
├── reviewer/
│   ├── main.py                  orchestrates the full pipeline
│   ├── github_client.py         GitHub API: fetch diff, post comments
│   ├── diff_parser.py           unified diff parser + position mapper
│   └── claude_reviewer.py       Anthropic API integration + JSON parser
├── auth/
│   └── database_service.py      demo file used to trigger the reviewer
├── requirements.txt
└── .gitignore
```

---

## Setup

### 1. Fork this repo

Click Fork at the top right.

### 2. Get an Anthropic API key

Go to console.anthropic.com → API Keys → Create Key. Cost is roughly $0.002 per PR review. A $5 credit covers thousands of reviews.

### 3. Add the secret

Settings → Secrets and variables → Actions → New repository secret

| Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | your key starting with sk-ant- |

GITHUB_TOKEN is provided automatically by GitHub — you do not need to add it.

### 4. Set workflow permissions

Settings → Actions → General → Workflow permissions → Read and write permissions → check Allow GitHub Actions to create and approve pull requests → Save.

### 5. Open a pull request

The Action triggers automatically on every PR. Done.

---

## Why I built this

I wanted to understand how GitHub Actions works beyond the YAML — specifically how an Action authenticates, interacts with the GitHub REST API, parses real data formats, and writes structured output back into the platform.

The diff position mapping turned out to be the most technically interesting problem. GitHub's documentation on it is sparse. Solving it required understanding the unified diff format at a byte level and reverse engineering how GitHub counts positions across multi-hunk diffs with deletions mixed in.

The AI side was deliberately kept simple. The value is not in doing anything exotic with the model — it is in the system prompt engineering that makes Claude act like a specific kind of reviewer, and the structured JSON output that makes the results usable programmatically rather than just readable by a human.

---

## What I would add next

- A top-level PR summary comment giving an overview of the entire changeset
- A .ai-reviewer.yml config file so teams can tune severity thresholds per repo
- Language-specific system prompts — different focus areas for Python vs Go vs JavaScript
- Token usage logging so teams can track and predict API costs
- Skip logic to avoid re-reviewing files that have not changed since the last run

---

## Cost

| Usage | Monthly cost |
|---|---|
| 10 PRs | ~$0.02 |
| 50 PRs | ~$0.10 |
| 200 PRs | ~$0.40 |

Large diffs are automatically truncated at 300 lines per file to keep costs predictable.

---

## License

MIT. Use it, fork it, build on it.
