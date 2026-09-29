import random
from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user
from db import get_conn, put_conn

highlow_bp = Blueprint('highlow', __name__)

suit_map = {"S": "♠️", "H": "♥️", "D": "♦️", "C": "♣️"}

def generate_card():
    value = random.randint(1, 13)
    suit = random.choice(["S", "H", "D", "C"])
    return value, suit

def calc_multiplier(current_value, choice):
    if choice == "high":
        prob = (13 - current_value) / 13
    else:
        prob = (current_value - 1) / 13

    if prob <= 0:
        return None
    return round(1 / prob, 3)

@highlow_bp.route("/highlow")
@login_required
def highlow():
    value, suit = generate_card()
    coins = current_user.coins
    suit_emoji = suit_map[suit]
    return render_template("highlow.html", coins=coins, value=value, suit=suit, suit_emoji=suit_emoji)

@highlow_bp.route("/highlow_start", methods=["POST"])
@login_required
def highlow_start():
    data = request.json
    current_value = int(data["current_value"])
    current_suit = data["current_suit"]
    bet = int(data["bet"])

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT coins FROM users WHERE id=%s", (current_user.id,))
    coins = cur.fetchone()[0]

    if bet <= 0 or bet > coins:
        cur.close()
        put_conn(conn)
        return jsonify({"html": "<p>ベット額が不正です</p>"}), 400

    coins -= bet
    cur.execute("UPDATE users SET coins=%s WHERE id=%s", (coins, current_user.id))
    conn.commit()
    cur.close()
    put_conn(conn)

    session["hl_bet"] = bet
    session["hl_multiplier"] = 1.0
    session["hl_current_value"] = current_value
    session["hl_current_suit"] = current_suit

    suit_emoji = suit_map[current_suit]
    html = f"""
    <p>コイン: {coins}</p>
    <div class="row">
        <div class="card">{suit_emoji} {current_value}</div>
        <div class="card">？</div>
    </div>
    <p>累積倍率: 1.0</p>
    <button onclick="play('high')">High</button><br>
    <button onclick="play('low')">Low</button><br>
    <button onclick="location.href='/games'">ゲーム一覧へ戻る</button>
    """
    return jsonify({"html": html})

@highlow_bp.route("/highlow_play2", methods=["POST"])
@login_required
def highlow_play2():
    data = request.json
    choice = data["choice"]

    current_value = session.get("hl_current_value")
    current_suit = session.get("hl_current_suit")
    multiplier = session.get("hl_multiplier")

    next_value, next_suit = generate_card()
    suit_emoji1 = suit_map[current_suit]
    suit_emoji2 = suit_map[next_suit]

    if next_value == current_value:
        html = f"""
        <h2>引き分け！</h2>
        <div class="row">
            <div class="card">{suit_emoji1} {current_value}</div>
            <div class="card">{suit_emoji2} {next_value}</div>
        </div>
        <p>累積倍率: {multiplier}</p>
        <button onclick="play('high')">High</button><br>
        <button onclick="play('low')">Low</button><br>
        <button id="cashout_btn" onclick="cashout()">やめる（払い戻し）</button>
        <button onclick="location.href='/games'">ゲーム一覧へ</button>
        """
        session["hl_current_value"] = next_value
        session["hl_current_suit"] = next_suit
        return jsonify({"html": html})

    win = (next_value > current_value) if choice == "high" else (next_value < current_value)
    new_multiplier = calc_multiplier(current_value, choice)

    if win:
        multiplier *= new_multiplier
        result_text = f"勝ち！ 倍率 ×{new_multiplier} → 累積 {round(multiplier, 3)}"
    else:
        multiplier = 0
        result_text = "負け…（払い戻しなし）"

    session["hl_multiplier"] = multiplier
    session["hl_current_value"] = next_value
    session["hl_current_suit"] = next_suit

    html = f"""
    <h2>{result_text}</h2>
    <div class="row">
        <div class="card">{suit_emoji1} {current_value}</div>
        <div class="card">{suit_emoji2} {next_value}</div>
    </div>
    <p>累積倍率: {round(multiplier,3)}</p>
    <button onclick="play('high')">High</button><br>
    <button onclick="play('low')">Low</button><br>
    <button id="cashout_btn" onclick="cashout()">やめる（払い戻し）</button>
    <button onclick="location.href='/games'">ゲーム一覧へ</button>
    """
    return jsonify({"html": html})

@highlow_bp.route("/highlow_cashout")
@login_required
def highlow_cashout():
    bet = session.get("hl_bet", 0)
    multiplier = session.get("hl_multiplier", 0)
    payout = int(bet * multiplier)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT coins FROM users WHERE id=%s", (current_user.id,))
    coins = cur.fetchone()[0]

    coins += payout
    cur.execute("UPDATE users SET coins=%s WHERE id=%s", (coins, current_user.id))
    conn.commit()
    cur.close()
    put_conn(conn)

    session.pop("hl_bet", None)
    session.pop("hl_multiplier", None)
    session.pop("hl_current_value", None)
    session.pop("hl_current_suit", None)

    return f"""
    <div style="text-align:center; padding-top:40px;">
        <h2>払い戻し</h2>
        <p>+{payout} コイン</p>
        <p>現在のコイン: {coins}</p>
        <button onclick="location.href='/games'">ゲーム一覧へ戻る</button>
    </div>
    """
