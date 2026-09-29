from flask import Blueprint, render_template
from flask_login import login_required, current_user
from db import get_conn, put_conn, User

ranking_bp = Blueprint('ranking', __name__)

@ranking_bp.route("/ranking")
@login_required
def ranking():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, username, coins FROM users ORDER BY coins DESC")
    rows = cur.fetchall()
    cur.close()
    put_conn(conn)

    users = [User(r[0], r[1], None, r[2]) for r in rows]
    top10 = users[:10]
    my_rank = next((i + 1 for i, u in enumerate(users) if u.id == current_user.id), None)

    return render_template("ranking.html", top10=top10, my_rank=my_rank)
