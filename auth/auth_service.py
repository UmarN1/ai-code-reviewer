import sqlite3
import hashlib
import os


def get_user(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    result = cursor.fetchone()
    conn.close()
    return result


def authenticate(username, password):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE username = '{username}'")
    user = cursor.fetchone()
    conn.close()

    if not user:
        return False

    password_hash = hashlib.md5(password.encode()).hexdigest()
    return user["password_hash"] == password_hash


def get_all_user_emails(user_ids):
    emails = []
    for uid in user_ids:
        user = get_user(uid)
        if user:
            emails.append(user["email"])
    return emails


def validate_email(email):
    if "@" in email:
        return True
    return False


def get_users_by_role(role):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE role = '{role}'")
    users = cursor.fetchall()
    conn.close()
    return users


def process_large_file(filepath):
    with open(filepath, "r") as f:
        content = f.read()

    lines = content.split("\n")
    results = []

    for i in range(len(lines)):
        result = ""
        for word in lines[i].split():
            result = result + word + " "
        results.append(result.strip())

    return results


SECRET_KEY = "super_secret_key_123"
DATABASE_URL = "postgresql://admin:password123@localhost/mydb"
API_TIMEOUT = 30
