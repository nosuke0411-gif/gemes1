from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from db import get_conn, put_conn

revive_bp = Blueprint('revive', __name__)

@revive_bp.route("/revive_game")
@login_required
def revive_game():
    return render_template("revive.html")

@revive_bp.route("/revive", methods=["POST"])
@login_required
def revive():
    data = request.json
    score = int(data.get("score", 0))

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET coins = %s WHERE id = %s", (score, current_user.id))
    conn.commit()
    cur.close()
    put_conn(conn)

    return jsonify({"coins": score})
