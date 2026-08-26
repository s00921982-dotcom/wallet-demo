from flask import Flask, render_template, request, redirect, session
from datetime import datetime, timedelta
import sqlite3
import secrets
import hashlib
import re

app = Flask(__name__)

# Demo فقط
app.secret_key = "demo-wallet-secret-change-this"

DB = "wallet.db"
DEMO_CODE = "DEMO100"


# =========================
# Database
# =========================

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def column_exists(c, table, column):
    columns = c.execute(
        f"PRAGMA table_info({table})"
    ).fetchall()

    return any(row["name"] == column for row in columns)


def init():
    c = db()

    # Users
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            password TEXT,
            balance REAL NOT NULL DEFAULT 0
        )
    """)

    # Transactions
    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL,
            created TEXT NOT NULL,
            complete TEXT,
            paypal_email TEXT
        )
    """)

    # إصلاح قواعد البيانات القديمة تلقائيًا
    if not column_exists(c, "users", "username"):
        c.execute(
            "ALTER TABLE users ADD COLUMN username TEXT"
        )

    if not column_exists(c, "users", "password"):
        c.execute(
            "ALTER TABLE users ADD COLUMN password TEXT"
        )

    if not column_exists(c, "transactions", "paypal_email"):
        c.execute(
            "ALTER TABLE transactions ADD COLUMN paypal_email TEXT"
        )

    if not column_exists(c, "transactions", "user_id"):
        c.execute(
            "ALTER TABLE transactions ADD COLUMN user_id TEXT"
        )

    c.commit()
    c.close()


# =========================
# Helpers
# =========================

def hash_password(password):
    return hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()


def get_user_id():
    if "user_id" not in session:
        session["user_id"] = secrets.token_hex(16)

    return session["user_id"]


def ensure_user():
    user_id = get_user_id()

    c = db()

    user = c.execute(
        "SELECT user_id FROM users WHERE user_id=?",
        (user_id,)
    ).fetchone()

    if not user:
        c.execute("""
            INSERT INTO users
            (user_id, username, password, balance)
            VALUES (?, NULL, NULL, 0)
        """, (user_id,))

        c.commit()

    c.close()

    return user_id


def logged_in():
    return "user_id" in session


def update_status(user_id):
    c = db()

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    c.execute("""
        UPDATE transactions
        SET status='completed'
        WHERE user_id=?
        AND status='pending'
        AND complete IS NOT NULL
        AND complete <= ?
    """, (user_id, now))

    c.commit()
    c.close()


def valid_paypal_email(email):
    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    return re.match(pattern, email) is not None


# =========================
# Home
# =========================

@app.route("/")
def home():

    if not logged_in():
        return redirect("/login")

    user_id = ensure_user()

    update_status(user_id)

    c = db()

    user = c.execute("""
        SELECT balance, username
        FROM users
        WHERE user_id=?
    """, (user_id,)).fetchone()

    transactions = c.execute("""
        SELECT *
        FROM transactions
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 5
    """, (user_id,)).fetchall()

    message = session.pop(
        "message",
        None
    )

    balance = user["balance"]

    c.close()

    return render_template(
        "index.html",
        balance=balance,
        transactions=transactions,
        message=message,
        username=user["username"]
    )


# =========================
# Login
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get(
        "username",
        ""
    ).strip()

    password = request.form.get(
        "password",
        ""
    )

    if not username or not password:
        session["message"] = (
            "أدخل اسم المستخدم وكلمة المرور."
        )

        return redirect("/login")

    password_hash = hash_password(password)

    c = db()

    user = c.execute("""
        SELECT user_id, username
        FROM users
        WHERE username=?
        AND password=?
    """, (
        username,
        password_hash
    )).fetchone()

    c.close()

    if not user:

        session["message"] = (
            "اسم المستخدم أو كلمة المرور غير صحيحة."
        )

        return redirect("/login")

    session["user_id"] = user["user_id"]

    return redirect("/")


# =========================
# Register
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "GET":
        message = session.pop("message", None)
        return render_template(
            "register.html",
            message=message
        )

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    confirm = request.form.get("confirm_password", "")

    if not username or not password:
        session["message"] = "أدخل جميع البيانات."
        return redirect("/register")

    if len(username) < 3:
        session["message"] = "اسم المستخدم يجب أن يكون 3 أحرف على الأقل."
        return redirect("/register")

    if len(password) < 4:
        session["message"] = "كلمة المرور يجب أن تكون 4 أحرف على الأقل."
        return redirect("/register")

    if password != confirm:
        session["message"] = "كلمتا المرور غير متطابقتين."
        return redirect("/register")

    c = db()

    existing = c.execute(
        "SELECT user_id FROM users WHERE username=?",
        (username,)
    ).fetchone()

    if existing:
        c.close()
        session["message"] = "اسم المستخدم مستخدم مسبقًا."
        return redirect("/register")

    user_id = secrets.token_hex(16)
    password_hash = hash_password(password)

    c.execute("""
        INSERT INTO users
        (user_id, username, password, balance)
        VALUES (?, ?, ?, 0)
    """, (
        user_id,
        username,
        password_hash
    ))

    c.commit()
    c.close()

    session.clear()
    session["user_id"] = user_id
    session["message"] = "تم إنشاء الحساب بنجاح."

    return redirect("/")


# =========================
# Logout
# =========================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# =========================
# Demo Code
# =========================

@app.post("/redeem")
def redeem():

    if not logged_in():
        return redirect("/login")

    user_id = ensure_user()

    code = request.form.get(
        "code",
        ""
    ).strip().upper()

    if code != DEMO_CODE:

        session["message"] = (
            "الكود غير صحيح."
        )

        return redirect("/")

    c = db()

    existing = c.execute("""
        SELECT id
        FROM transactions
        WHERE user_id=?
        AND kind='إضافة رصيد Demo'
        LIMIT 1
    """, (user_id,)).fetchone()

    if existing:

        c.close()

        session["message"] = (
            "تم استخدام كود DEMO100 لهذا الحساب مسبقًا."
        )

        return redirect("/")

    c.execute("""
        UPDATE users
        SET balance = balance + 100
        WHERE user_id=?
    """, (user_id,))

    c.execute("""
        INSERT INTO transactions
        (user_id, kind, amount, status, created)
        VALUES (?, ?, ?, ?, ?)
    """, (
        user_id,
        "إضافة رصيد Demo",
        100,
        "completed",
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    ))

    c.commit()
    c.close()

    session["message"] = (
        "تمت إضافة 100$ إلى رصيد Demo الخاص بك."
    )

    return redirect("/")


# =========================
# Withdraw Demo
# =========================

@app.post("/withdraw")
def withdraw():

    if not logged_in():
        return redirect("/login")

    user_id = ensure_user()

    amount_text = request.form.get(
        "amount",
        "0"
    ).strip()

    paypal_email = request.form.get(
        "paypal_email",
        ""
    ).strip()

    days_text = request.form.get(
        "days",
        "7"
    ).strip()

    try:
        amount = float(amount_text)
        days = int(days_text)

    except ValueError:

        session["message"] = (
            "البيانات غير صحيحة."
        )

        return redirect("/")

    if amount <= 0:

        session["message"] = (
            "أدخل مبلغًا صحيحًا."
        )

        return redirect("/")

    if not valid_paypal_email(paypal_email):

        session["message"] = (
            "أدخل بريد PayPal صحيحًا."
        )

        return redirect("/")

    if days not in (7, 14):

        session["message"] = (
            "اختر مدة صحيحة."
        )

        return redirect("/")

    c = db()

    user = c.execute("""
        SELECT balance
        FROM users
        WHERE user_id=?
    """, (user_id,)).fetchone()

    if not user:

        c.close()

        session["message"] = (
            "الحساب غير موجود."
        )

        return redirect("/")

    balance = float(user["balance"])

    if amount > balance:

        c.close()

        session["message"] = (
            "الرصيد غير كافٍ."
        )

        return redirect("/")

    created = datetime.now()

    complete = created + timedelta(
        days=days
    )

    # خصم الرصيد داخل Demo فقط
    c.execute("""
        UPDATE users
        SET balance = balance - ?
        WHERE user_id=?
    """, (
        amount,
        user_id
    ))

    # حفظ طلب السحب وبريد PayPal
    c.execute("""
        INSERT INTO transactions
        (
            user_id,
            kind,
            amount,
            status,
            created,
            complete,
            paypal_email
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        "طلب سحب Demo",
        amount,
        "pending",
        created.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        complete.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        paypal_email
    ))

    c.commit()
    c.close()

    session["message"] = (
        "تم إنشاء طلب السحب Demo. "
        "لن يتم إرسال أموال حقيقية إلى PayPal."
    )

    return redirect("/")


# =========================
# Transactions
# =========================

@app.route("/transactions")
def transactions():

    if not logged_in():
        return redirect("/login")

    user_id = ensure_user()

    update_status(user_id)

    c = db()

    transactions = c.execute("""
        SELECT *
        FROM transactions
        WHERE user_id=?
        ORDER BY id DESC
    """, (user_id,)).fetchall()

    c.close()

    return render_template(
        "transactions.html",
        transactions=transactions
    )


# =========================
# Account
# =========================

@app.route("/account")
def account():

    if not logged_in():
        return redirect("/login")

    user_id = ensure_user()

    c = db()

    user = c.execute("""
        SELECT username, balance
        FROM users
        WHERE user_id=?
    """, (user_id,)).fetchone()

    c.close()

    return render_template(
        "account.html",
        user=user
    )


# =========================
# Demo Code Page
# =========================

@app.route("/code")
def code_page():

    if not logged_in():
        return redirect("/login")

    ensure_user()

    return render_template(
        "code.html"
    )


# =========================
# Start
# =========================

init()


if __name__ == "__main__":

    print("")
    print("==============================")
    print("        DEMO WALLET")
    print("==============================")
    print("http://127.0.0.1:5000")
    print("==============================")
    print("")
    print("Demo code: DEMO100")
    print("PayPal withdrawals are simulated only.")
    print("")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
