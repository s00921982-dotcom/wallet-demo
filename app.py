from flask import Flask, render_template, request, redirect, session
from datetime import datetime, timedelta
import sqlite3
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

DB = "wallet.db"

# رمز دولي  — 
DEMO_CODE = "DEMO100"


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init():
    c = db()

    c.execute("""
        CREATE TABLE IF NOT EXISTS wallet (
            id INTEGER PRIMARY KEY,
            balance REAL NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS codes (
            code TEXT PRIMARY KEY,
            amount REAL NOT NULL,
            used INTEGER NOT NULL DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL,
            created TEXT NOT NULL,
            complete TEXT
        )
    """)

    if not c.execute(
        "SELECT id FROM wallet WHERE id=1"
    ).fetchone():
        c.execute(
            "INSERT INTO wallet(id,balance) VALUES(1,0)"
        )

    if not c.execute(
        "SELECT code FROM codes WHERE code=?",
        (DEMO_CODE,)
    ).fetchone():
        c.execute(
            "INSERT INTO codes(code,amount,used) VALUES(?,?,0)",
            (DEMO_CODE, 100)
        )

    c.commit()
    c.close()


def update_status():
    c = db()

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    c.execute("""
        UPDATE transactions
        SET status='completed'
        WHERE status='pending'
        AND complete IS NOT NULL
        AND complete <= ?
    """, (now,))

    c.commit()
    c.close()


@app.route("/")
def home():

    update_status()

    c = db()

    balance = c.execute(
        "SELECT balance FROM wallet WHERE id=1"
    ).fetchone()["balance"]

    transactions = c.execute("""
        SELECT *
        FROM transactions
        ORDER BY id DESC
        LIMIT 5
    """).fetchall()

    message = session.pop("message", None)

    c.close()

    return render_template(
        "index.html",
        balance=balance,
        transactions=transactions,
        message=message
    )


@app.post("/redeem")
def redeem():

    code = request.form.get(
        "code", ""
    ).strip().upper()

    c = db()

    row = c.execute("""
        SELECT *
        FROM codes
        WHERE code=?
        AND used=0
    """, (code,)).fetchone()

    if row:

        c.execute("""
            UPDATE wallet
            SET balance=balance+?
            WHERE id=1
        """, (row["amount"],))

        c.execute("""
            UPDATE codes
            SET used=1
            WHERE code=?
        """, (code,))

        c.execute("""
            INSERT INTO transactions
            (kind,amount,status,created)
            VALUES(?,?,?,?)
        """, (
            "إضافة رصيد ",
            row["amount"],
            "completed",
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        ))

        c.commit()

        session["message"] = (
            "تمت إضافة الرصيد ."
        )

    else:

        session["message"] = (
            "الكود غير صحيح أو تم استخدامه مسبقًا."
        )

    c.close()

    return redirect("/")


@app.post("/withdraw")
def withdraw():

    try:

        amount = float(
            request.form.get("amount", "0")
        )

        days = int(
            request.form.get("days", "7")
        )

    except ValueError:

        session["message"] = (
            "البيانات غير صحيحة."
        )

        return redirect("/")

    c = db()

    balance = c.execute(
        "SELECT balance FROM wallet WHERE id=1"
    ).fetchone()["balance"]

    if amount <= 0:

        session["message"] = (
            "أدخل مبلغًا صحيحًا."
        )

        c.close()
        return redirect("/")

    if amount > balance:

        session["message"] = (
            "الرصيد  غير كافٍ."
        )

        c.close()
        return redirect("/")

    if days not in (7, 14):

        session["message"] = (
            "اختر مدة صحيحة."
        )

        c.close()
        return redirect("/")

    created = datetime.now()

    complete = created + timedelta(
        days=days
    )

    c.execute("""
        UPDATE wallet
        SET balance=balance-?
        WHERE id=1
    """, (amount,))

    c.execute("""
        INSERT INTO transactions
        (kind,amount,status,created,complete)
        VALUES(?,?,?,?,?)
    """, (
        "طلب سحب ",
        amount,
        "pending",
        created.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        complete.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    ))

    c.commit()
    c.close()

    session["message"] = (
        "تم إنشاء طلب السحب ."
    )

    return redirect("/")


@app.route("/transactions")
def transactions():

    update_status()

    c = db()

    transactions = c.execute("""
        SELECT *
        FROM transactions
        ORDER BY id DESC
    """).fetchall()

    c.close()

    return render_template(
        "transactions.html",
        transactions=transactions
    )


@app.route("/account")
def account():

    return render_template(
        "account.html"
    )


@app.route("/code")
def code_page():

    return render_template(
        "code.html"
    )


init()

if __name__ == "__main__":

    init()

    print("")
    print("==============================")
    print("       DEMO WALLET")
    print("==============================")
    print("http://127.0.0.1:5000")
    print("==============================")
    print("")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
