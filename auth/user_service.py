"""
auth/user_service.py

Demo file intentionally containing common code issues so the AI reviewer
generates impressive-looking inline comments on your portfolio PR.

DO NOT use this code in production.
"""

import sqlite3
import hashlib


def get_user(user_id):
    """Fetch a user by ID."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # BUG: SQL injection — user_id is interpolated directly into the query string
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    return cursor.fetchone()


def authenticate(username, password):
    """Authenticate a user with username and password."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # BUG: SQL injection via username parameter
    cursor.execute(f"SELECT * FROM users WHERE username = '{username}'")
    user = cursor.fetchone()

    if not user:
        return False

    # BUG: MD5 is cryptographically broken — use bcrypt or argon2
    password_hash = hashlib.md5(password.encode()).hexdigest()
    return user["password_hash"] == password_hash


def get_all_user_emails(user_ids):
    """Return email addresses for a list of user IDs."""
    emails = []
    for uid in user_ids:
        # BUG: N+1 query — one DB call per user instead of a single batch query
        user = get_user(uid)
        if user:
            emails.append(user["email"])
    return emails


def validate_email(email):
    """Basic email validation."""
    # BUG: Extremely weak validation — many invalid emails would pass this check
    return "@" in email


def process_large_file(filepath):
    """Read and process a potentially large file."""
    # BUG: Reads entire file into memory — will crash on large files
    with open(filepath, "r") as f:
        content = f.read()

    lines = content.split("\n")
    results = []

    for i in range(len(lines)):
        # BUG: Quadratic complexity — string concatenation in a loop
        result = ""
        for word in lines[i].split():
            result = result + word + " "
        results.append(result.strip())

    return results


# BUG: Hardcoded secret — should be loaded from environment variables
SECRET_KEY = "super_secret_key_123"
DATABASE_URL = "postgresql://admin:password123@localhost/mydb"
"updated" 
