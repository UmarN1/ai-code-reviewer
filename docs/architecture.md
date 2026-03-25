# Architecture & Design Decisions

This document explains some of the technical decisions I made while building this project and why I made them. Mostly writing this so I remember my own reasoning, but also useful if anyone else wants to understand how it works or contribute.

---

## Why GitHub Actions instead of a hosted service

The obvious alternative was to build a small Flask or FastAPI app, host it somewhere like AWS Lambda or a VPS, and set up a GitHub webhook to call it on every PR. I actually started going down that route but switched to GitHub Actions for a few reasons.

First, there is no infrastructure to maintain. No server, no uptime monitoring, no deployment pipeline for the reviewer itself. The action just runs inside GitHub's own infrastructure every time a PR is opened.

Second, the authentication story is much simpler. GitHub Actions gets a `GITHUB_TOKEN` automatically with the right permissions scoped to the repo. With a webhook approach I would have had to manage token rotation, validate webhook signatures, and handle retries if my server was down when GitHub called it.

The tradeoff is less flexibility — you can not do things like cache results between runs easily. But for a code reviewer that runs on every PR, Actions is the right call.

---

## The diff position problem

This was the most frustrating thing to figure out and the part I am most proud of solving.

When you want to post an inline comment on a PR, GitHub's API does not accept a regular line number. It wants a `position` value which is a counter that increments for every single line in the raw unified diff — including the `@@` hunk headers and unchanged context lines.

So if you have a diff that looks like this:

```
@@ -1,3 +1,5 @@        <- position 1
 import os              <- position 2
+import sqlite3         <- position 3  (new line number: 2)
+                       <- position 4  (new line number: 3)
 def main():            <- position 5  (new line number: 4)
-    pass               <- position 6  (no new line number, deleted)
+    run()              <- position 7  (new line number: 5)
```

If Claude says "there is an issue on line 2 of the new file", I need to translate that to position 3 before I can post the comment. Get this wrong and the comment either fails silently or lands on the completely wrong line.

I solved this by walking through the diff line by line in `diff_parser.py` and building a lookup table: `{ new_file_line_number: diff_position }`. Deleted lines increment the diff position counter but do not get a new line number. Hunk headers increment the position counter and reset the new line number to wherever that hunk starts.

It took me longer than I want to admit to get this right but the end result is comments landing on exactly the right lines every time.

---

## Why structured JSON output from Claude instead of freeform text

My first attempt at the Claude integration just asked it to write review comments in plain text and then I tried to parse out which file and line number each comment referred to. This was a mess — Claude would sometimes say "on line 42" and sometimes "at line 42" and sometimes just reference the function name without a line number at all.

Switching to structured JSON output fixed all of that. The system prompt explicitly tells Claude to return an array of objects with `line_number`, `severity`, and `comment` fields and nothing else. Now the parsing is just `json.loads()` and everything is reliable.

The one annoying thing is Claude sometimes wraps the JSON in markdown code fences even when told not to. So `claude_reviewer.py` strips those out before parsing just in case.

---

## Why post the summary as an issue comment instead of a review body

GitHub's Pull Request Reviews API lets you include a body text along with inline comments when you submit a review. I initially put the summary there but it showed up in a weird place in the UI — kind of attached to the review submission rather than standing out as its own thing.

Posting it as a separate issue comment (via `/issues/{pr_number}/comments`) means it shows up at the top of the conversation tab as the first thing anyone sees when they open the PR. Much more visible and readable.

The tradeoff is it counts as two API calls instead of one but that is not a concern here.

---

## Why truncate diffs at 300 lines

Claude has a context window large enough to handle much bigger diffs but there are two reasons I added the truncation limit.

First, cost. Sending a 2000 line diff to Claude for every PR review would get expensive fast, especially if someone accidentally commits a generated file or a large data file. The 300 line limit keeps each review under about half a cent.

Second, very long diffs usually mean a PR that is too big to review properly anyway. If someone is changing 2000 lines at once the right feedback is probably "break this into smaller PRs" rather than a detailed line-by-line review.

300 lines felt like the right balance — enough to catch real issues in a normal sized PR without the cost going out of control.

---

## What I would do differently

A few things I would change if I built this again:

**Caching** — right now every run reviews every changed file from scratch. It would be more efficient to store a hash of each file's diff and skip re-reviewing files that have not changed since the last run.

**Config file** — currently you have to edit the Python files to change things like the truncation limit or which file types to skip. A `.ai-reviewer.yml` config file in the repo root would be much cleaner.

**Better fallback handling** — the current fallback when inline comments fail is to post everything as one big comment. It works but the formatting is not great. A better approach would be to retry the inline review with only the comments that failed rather than falling back for everything.

**Tests** — there are no unit tests for the diff parser which is the most logic-heavy part of the codebase. The position mapping logic in particular would benefit from a proper test suite with real diff examples as fixtures.
