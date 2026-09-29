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
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT coins FROM users WHERE id=%s", (current_user.id,))
    row = cur.fetchone()
    coins = row[0] if row else current_user.coins
    cur.close()
    put_conn(conn)
    suit_emoji = suit_map[suit]
    return render_template("highlow.html", coins=coins, value=value, suit=suit, suit_emoji=suit_emoji)

@highlow_bp.route("/highlow_start", methods=["POST"])
@login_required
def highlow_start():
    data = request.json or {}
    current_value = int(data.get("current_value", 1))
    current_suit = data.get("current_suit", "S")
    bet = int(data.get("bet", 0))

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT coins FROM users WHERE id=%s", (current_user.id,))
    row = cur.fetchone()
    coins = row[0] if row else 0

    if bet <= 0 or bet > coins:
        cur.close()
        put_conn(conn)
        return jsonify({"html": '<div class="result-banner warning">ベット額が不正です</div>'}), 400

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
    <div class="top-bar">
        <h2>High & Low</h2>
        <div class="coin-badge">💰 <span>{coins}</span> コイン</div>
    </div>

    <div class="table-board">
        <div class="hand-section">
            <div class="section-title">現在のカード vs 次のカード</div>
            <div class="cards-row">
                <div class="card">{suit_emoji} {current_value}</div>
                <div class="card hidden-card">❓</div>
            </div>
        </div>
        <div class="multiplier-badge">累積倍率: <span>1.000x</span> (予想配当: {bet} コイン)</div>
    </div>

    <div class="result-banner">High (高い) か Low (低い) を選択してください</div>

    <div class="controls">
        <div class="action-row">
            <button class="btn btn-high" onclick="play('high')">🔥 High (高い)</button>
            <button class="btn btn-low" onclick="play('low')">❄️ Low (低い)</button>
        </div>
        <button class="btn btn-back" onclick="location.href='/games'">ゲーム一覧へ戻る</button>
    </div>
    """
    return jsonify({"html": html})

@highlow_bp.route("/highlow_play2", methods=["POST"])
@login_required
def highlow_play2():
    data = request.json or {}
    choice = data.get("choice")

    current_value = session.get("hl_current_value")
    current_suit = session.get("hl_current_suit")
    multiplier = session.get("hl_multiplier", 1.0)
    bet = session.get("hl_bet", 0)

    next_value, next_suit = generate_card()
    suit_emoji1 = suit_map[current_suit]
    suit_emoji2 = suit_map[next_suit]

    # 現在のコイン数を取得
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT coins FROM users WHERE id=%s", (current_user.id,))
    coins = cur.fetchone()[0]
    cur.close()
    put_conn(conn)

    if next_value == current_value:
        est_payout = int(bet * multiplier)
        html = f"""
        <div class="top-bar">
            <h2>High & Low</h2>
            <div class="coin-badge">💰 <span>{coins}</span> コイン</div>
        </div>

        <div class="table-board">
            <div class="hand-section">
                <div class="section-title">引き分け！（同値）</div>
                <div class="cards-row">
                    <div class="card">{suit_emoji1} {current_value}</div>
                    <div class="card">{suit_emoji2} {next_value}</div>
                </div>
            </div>
            <div class="multiplier-badge">累積倍率: <span>{round(multiplier, 3)}x</span> (予想配当: {est_payout} コイン)</div>
        </div>

        <div class="result-banner">引き分け！同じ数字でした。もう一度選択できます。</div>

        <div class="controls">
            <div class="action-row">
                <button class="btn btn-high" onclick="play('high')">🔥 High (高い)</button>
                <button class="btn btn-low" onclick="play('low')">❄️ Low (低い)</button>
            </div>
            <button id="cashout_btn" class="btn btn-cashout" onclick="cashout()">💰 やめる（{est_payout} コイン獲得）</button>
            <button class="btn btn-back" onclick="location.href='/games'">ゲーム一覧へ</button>
        </div>
        """
        session["hl_current_value"] = next_value
        session["hl_current_suit"] = next_suit
        return jsonify({"html": html})

    win = (next_value > current_value) if choice == "high" else (next_value < current_value)
    new_multiplier = calc_multiplier(current_value, choice)

    if win and new_multiplier:
        multiplier *= new_multiplier
        multiplier_round = round(multiplier, 3)
        est_payout = int(bet * multiplier)
        result_msg = f"🎉 勝利！ 次の倍率 ×{new_multiplier} ➔ 累積 {multiplier_round}x"

        session["hl_multiplier"] = multiplier
        session["hl_current_value"] = next_value
        session["hl_current_suit"] = next_suit

        html = f"""
        <div class="top-bar">
            <h2>High & Low</h2>
            <div class="coin-badge">💰 <span>{coins}</span> コイン</div>
        </div>

        <div class="table-board">
            <div class="hand-section">
                <div class="section-title">結果判定</div>
                <div class="cards-row">
                    <div class="card">{suit_emoji1} {current_value}</div>
                    <div class="card win-card">{suit_emoji2} {next_value}</div>
                </div>
            </div>
            <div class="multiplier-badge">累積倍率: <span>{multiplier_round}x</span> (予想配当: {est_payout} コイン)</div>
        </div>

        <div class="result-banner">{result_msg}</div>

        <div class="controls">
            <div class="action-row">
                <button class="btn btn-high" onclick="play('high')">🔥 High (高い)</button>
                <button class="btn btn-low" onclick="play('low')">❄️ Low (低い)</button>
            </div>
            <button id="cashout_btn" class="btn btn-cashout" onclick="cashout()">💰 やめる（{est_payout} コイン獲得）</button>
            <button class="btn btn-back" onclick="location.href='/games'">ゲーム一覧へ</button>
        </div>
        """
    else:
        multiplier = 0
        session["hl_multiplier"] = 0
        result_msg = "💀 残念... 予測が外れました。（賭け金没収）"

        html = f"""
        <div class="top-bar">
            <h2>High & Low</h2>
            <div class="coin-badge">💰 <span>{coins}</span> コイン</div>
        </div>

        <div class="table-board">
            <div class="hand-section">
                <div class="section-title">結果判定</div>
                <div class="cards-row">
                    <div class="card">{suit_emoji1} {current_value}</div>
                    <div class="card lose-card">{suit_emoji2} {next_value}</div>
                </div>
            </div>
            <div class="multiplier-badge lose-text">ゲームオーバー</div>
        </div>

        <div class="result-banner">{result_msg}</div>

        <div class="controls">
            <button class="btn btn-start" onclick="location.reload()">もう一度遊ぶ</button>
            <button class="btn btn-back" onclick="location.href='/games'">ゲーム一覧へ</button>
        </div>
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
    <div class="top-bar">
        <h2>High & Low</h2>
        <div class="coin-badge">💰 <span>{coins}</span> コイン</div>
    </div>
    <div class="table-board" style="text-align: center; padding: 40px 20px;">
        <h2 style="color: #ffd700; margin-bottom: 10px;">💰 払い戻し完了！</h2>
        <p style="font-size: 22px; margin: 15px 0;">+<strong>{payout}</strong> コイン 獲得</p>
        <p style="color: #a0d8b3;">現在の所持コイン: {coins}</p>
    </div>
    <div class="controls" style="margin-top: 20px;">
        <button class="btn btn-start" onclick="location.href='/highlow'">新しくゲームを始める</button>
        <button class="btn btn-back" onclick="location.href='/games'">ゲーム一覧へ戻る</button>
    </div>
    """
