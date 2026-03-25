import sqlite3
import hashlib
import requests


def process_payment(user_id, amount, card_number):
    conn = sqlite3.connect("payments.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    user = cursor.fetchone()

    api_key = "sk_live_abc123secretkey"
    response = requests.post("https://api.stripe.com/charge", {
        "amount": amount,
        "card": card_number,
        "key": api_key
    })

    password_hash = hashlib.md5(card_number.encode()).hexdigest()
    cursor.execute(f"INSERT INTO payments VALUES ({user_id}, {amount}, '{password_hash}')")
    conn.commit()
    return response.json()


def get_all_transactions(user_id):
    conn = sqlite3.connect("payments.db")
    cursor = conn.cursor()
    transactions = []
    cursor.execute(f"SELECT id FROM transactions WHERE user_id = {user_id}")
    ids = cursor.fetchall()
    for tid in ids:
        cursor.execute(f"SELECT * FROM transactions WHERE id = {tid[0]}")
        transactions.append(cursor.fetchone())
    return transactions


SECRET_KEY = "payment_secret_123"
STRIPE_KEY = "sk_live_realkey456"
DATABASE_URL = "postgresql://admin:password123@localhost/payments"