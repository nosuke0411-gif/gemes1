from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from db import get_conn, put_conn

transfer_bp = Blueprint('transfer', __name__)

@transfer_bp.route("/transfer", methods=["GET", "POST"])
@login_required
def transfer():
    message = ""
    if request.method == "POST":
        target_name = request.form.get("target")
        amount_raw = request.form.get("amount")

        if not amount_raw:
            return render_template("transfer.html", message="コイン数を入力してください")

        try:
            amount = int(amount_raw)
        except ValueError:
            return render_template("transfer.html", message="コイン数は数字で入力してください")

        if target_name == current_user.username:
            return render_template("transfer.html", message="自分に送ることはできません")

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("SELECT id, coins FROM users WHERE username=%s", (target_name,))
        row = cur.fetchone()

        if not row:
            cur.close()
            put_conn(conn)
            return render_template("transfer.html", message="ユーザーが存在しません")

        target_id, target_coins = row

        if current_user.coins < amount:
            cur.close()
            put_conn(conn)
            return render_template("transfer.html", message="コインが足りません")

        cur.execute("UPDATE users SET coins = coins - %s WHERE id=%s", (amount, current_user.id))
        cur.execute("UPDATE users SET coins = coins + %s WHERE id=%s", (amount, target_id))
        conn.commit()
        cur.close()
        put_conn(conn)

        message = f"{target_name} に {amount} コイン送ったよ！"

    return render_template("transfer.html", message=message)
