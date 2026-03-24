# database_service.py
# User management and database operations.
#
# NOTE: this file is intentionally left with some common issues
# so the AI reviewer has something meaningful to flag on demo PRs.
# In a real project these would all be fixed.

import sqlite3
import hashlib


def get_user(user_id):
    """Look up a user by their ID."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # this is vulnerable to SQL injection - user_id goes straight
    # into the query string without any sanitisation
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")

    return cursor.fetchone()


def authenticate(username, password):
    """Check if a username and password combination is valid."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # also SQL injection vulnerable
    cursor.execute(f"SELECT * FROM users WHERE username = '{username}'")
    user = cursor.fetchone()

    if not user:
        return False

    # MD5 is not safe for password hashing - should use bcrypt or argon2
    password_hash = hashlib.md5(password.encode()).hexdigest()
    return user["password_hash"] == password_hash


def get_emails_for_users(user_ids):
    """Get email addresses for a list of user IDs."""
    emails = []

    for uid in user_ids:
        # hitting the database once per user - this is the N+1 problem
        # with a large list this gets very slow
        user = get_user(uid)
        if user:
            emails.append(user["email"])

    return emails


def validate_email(email):
    """Basic check that an email address looks valid."""
    # this is way too simple - lots of invalid strings would pass this
    return "@" in email


def read_and_process_file(filepath):
    """Read a file and clean up the whitespace in each line."""

    # reads the whole file into memory at once - bad idea for large files
    with open(filepath, "r") as f:
        content = f.read()

    lines = content.split("\n")
    processed = []

    for i in range(len(lines)):
        # string concatenation inside a loop - this is O(n^2)
        # would be faster to use join() or a list
        result = ""
        for word in lines[i].split():
            result = result + word + " "
        processed.append(result.strip())

    return processed


# hardcoded credentials - these should come from environment variables
# anyone with access to this repo can see these
SECRET_KEY = "super_secret_key_123"
DATABASE_URL = "postgresql://admin:password123@localhost/mydb"
