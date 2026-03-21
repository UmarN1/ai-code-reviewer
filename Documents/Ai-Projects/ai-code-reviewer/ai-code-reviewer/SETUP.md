# Complete Setup Guide — Step by Step

Follow these steps exactly. Estimated time: **20–30 minutes**.

---

## Part 1 — Prerequisites

You need:
- A GitHub account
- Git installed on your computer ([download](https://git-scm.com/downloads))
- An Anthropic account ([sign up free](https://console.anthropic.com))

---

## Part 2 — Create the GitHub Repository

1. Go to [github.com/new](https://github.com/new)
2. Repository name: `ai-code-reviewer`
3. Set to **Public** (recruiters need to see it)
4. Do NOT initialise with README (we'll push our own)
5. Click **Create repository**
6. Copy the repository URL shown on screen (e.g. `https://github.com/YOURNAME/ai-code-reviewer.git`)

---

## Part 3 — Set Up Locally and Push

Open your terminal. Run these commands one at a time:

```bash
# 1. Clone or move to the project folder
cd ai-code-reviewer

# 2. Initialise git
git init

# 3. Add all files
git add .

# 4. Make your first commit
git commit -m "feat: initial commit — AI-powered GitHub Actions code reviewer"

# 5. Set the branch name to main
git branch -M main

# 6. Connect to your GitHub repo (replace YOUR_USERNAME with your actual GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/ai-code-reviewer.git

# 7. Push to GitHub
git push -u origin main
```

After this, go to your GitHub repo page and refresh — you should see all the files.

---

## Part 4 — Add Your Anthropic API Key

**Get the key:**
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Click **API Keys** in the left sidebar
3. Click **Create Key** → name it "github-reviewer"
4. Copy the key immediately (you can only see it once)

**Add it to GitHub:**
1. Go to your repo on GitHub
2. Click **Settings** (top tab)
3. In the left sidebar: **Secrets and variables** → **Actions**
4. Click **New repository secret**
5. Name: `ANTHROPIC_API_KEY` (exactly this, capital letters)
6. Value: paste your key
7. Click **Add secret**

---

## Part 5 — Enable Actions Write Permissions

This is required so the bot can post comments on PRs.

1. In your repo, click **Settings**
2. Left sidebar: **Actions** → **General**
3. Scroll down to **Workflow permissions**
4. Select **Read and write permissions**
5. Check the box: **Allow GitHub Actions to create and approve pull requests**
6. Click **Save**

---

## Part 6 — Create Your Demo PR

This is what recruiters will see. Follow this exactly.

**Step 1 — Create a branch:**
```bash
git checkout -b feature/user-authentication
```

**Step 2 — The `auth/user_service.py` file is already in your repo.**
It contains intentional bugs that Claude will catch and comment on.
This is your demo file.

**Step 3 — Make a small change to trigger a new commit:**
```bash
# Open auth/user_service.py and add a comment at the top, or just touch the file
echo "# Updated" >> auth/user_service.py
git add auth/user_service.py
git commit -m "feat: add user authentication and email processing service"
git push origin feature/user-authentication
```

**Step 4 — Open the PR:**
1. Go to your GitHub repo
2. You'll see a yellow banner: "feature/user-authentication had recent pushes"
3. Click **Compare & pull request**
4. Title: `feat: Add user authentication service`
5. Description: `Adds user lookup, authentication, and email processing functionality.`
6. Click **Create pull request**

**Step 5 — Watch it run:**
1. Click the **Checks** tab on your PR
2. You'll see **AI Code Reviewer** with a yellow spinner
3. Wait 30–60 seconds
4. Click **Files changed** tab
5. You should see inline comments from the AI on the problematic lines

---

## Part 7 — Screenshot for Your Portfolio

**Best screenshot:** The **Files changed** tab with 3–5 coloured inline AI comments visible.

**How to record a GIF (free):**
- Mac: Use [Gifox](https://gifox.io) (free tier) or QuickTime + convert
- Windows: Use [ScreenToGif](https://www.screentogif.com) (free)
- Any OS: Use [LICEcap](https://www.cockos.com/licecap) (free)

Record yourself:
1. Opening the PR
2. Clicking "Files changed"
3. Slowly scrolling through the AI comments

Add this GIF to your README by uploading it to the repo and referencing it as `![Demo](demo.gif)`.

---

## Part 8 — Make It Look Even Better

**Add a repo description:**
On your GitHub repo page, click the gear icon next to "About" and add:
> "GitHub Action that uses Claude AI to automatically review pull requests and post inline code review comments"

**Add topics:**
In the same About section, add topics:
`github-actions`, `ai`, `code-review`, `anthropic`, `claude`, `python`, `devops`, `mlops`

**Pin it to your profile:**
Go to your GitHub profile → click **Customize your pins** → select `ai-code-reviewer`

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Action doesn't trigger | Check the workflow file is at exactly `.github/workflows/ai-review.yml` |
| `401 Unauthorized` error | Re-add the `ANTHROPIC_API_KEY` secret — it may have been entered incorrectly |
| Comments don't appear inline | Check Settings → Actions → Workflow permissions are set to Read and Write |
| Action succeeds but no comments | Open the Action logs and look for `[INFO]` lines — Claude may have found no issues |
| Push rejected | Run `git pull origin main --rebase` first then push again |
