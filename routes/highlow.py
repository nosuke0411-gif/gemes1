import random
from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user
from db import get_conn, put_conn

highlow_bp = Blueprint('highlow', __name__)

SUIT_MAP = {
    "S": {"symbol": "♠", "name": "spades", "color": "black"},
    "H": {"symbol": "♥", "name": "hearts", "color": "red"},
    "D": {"symbol": "♦", "name": "diamonds", "color": "red"},
    "C": {"symbol": "♣", "name": "clubs", "color": "black"}
}

VAL_MAP = {
    1: 'A', 2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7',
    8: '8', 9: '9', 10: '10', 11: 'J', 12: 'Q', 13: 'K'
}

def generate_card():
    value = random.randint(1, 13)
    suit_code = random.choice(["S", "H", "D", "C"])
    return value, suit_code

def calc_round_multiplier(current_value, choice):
    """ベースカードの数字と選択(high/low)に応じた理論倍率を計算"""
    choice = choice.lower()
    if choice == "high":
        prob = (13 - current_value) / 13.0
    else:
        prob = (current_value - 1) / 13.0

    if prob <= 0:
        prob = 1.0 / 13.0  # 判定限界補正
    
    # 配当倍率 (1 / 確率)
    raw_mult = 1.0 / prob
    return round(raw_mult, 2)


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
    
    suit_info = SUIT_MAP[suit]
    return render_template("highlow.html", 
                           coins=coins, 
                           value=value, 
                           suit=suit, 
                           suit_emoji=suit_info["symbol"])


@highlow_bp.route("/highlow_start", methods=["POST"])
@login_required
def highlow_start():
    data = request.json or {}
    bet = int(data.get("bet", 0))

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT coins FROM users WHERE id=%s", (current_user.id,))
    row = cur.fetchone()
    coins = row[0] if row else 0

    if bet <= 0 or bet > coins:
        cur.close()
        put_conn(conn)
        return jsonify({"success": False, "msg": "ベット額が不正です"}), 400

    # ベット額をコインから引く
    coins -= bet
    cur.execute("UPDATE users SET coins=%s WHERE id=%s", (coins, current_user.id))
    conn.commit()
    cur.close()
    put_conn(conn)

    # 最初のベースカード生成
    base_val, base_suit = generate_card()

    session["hl_bet"] = bet
    session["hl_multiplier"] = 1.0
    session["hl_streak"] = 0
    session["hl_current_value"] = base_val
    session["hl_current_suit"] = base_suit

    return jsonify({
        "success": True,
        "coins": coins,
        "bet": bet,
        "streak": 0,
        "multiplier": 1.0,
        "base_card": {
            "value": base_val,
            "val_str": VAL_MAP[base_val],
            "suit": base_suit,
            "symbol": SUIT_MAP[base_suit]["symbol"],
            "color": SUIT_MAP[base_suit]["color"]
        },
        "msg": "「HIGH」か「LOW」を選択してください"
    })


@highlow_bp.route("/highlow_play2", methods=["POST"])
@login_required
def highlow_play2():
    data = request.json or {}
    choice = str(data.get("choice", "")).lower()

    current_value = session.get("hl_current_value")
    current_suit = session.get("hl_current_suit")
    multiplier = session.get("hl_multiplier", 1.0)
    streak = session.get("hl_streak", 0)
    bet = session.get("hl_bet", 0)

    if not current_value or bet <= 0:
        return jsonify({"success": False, "msg": "ゲームが開始されていません"}), 400

    # 次のカードを引く
    next_value, next_suit = generate_card()

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT coins FROM users WHERE id=%s", (current_user.id,))
    coins = cur.fetchone()[0]
    cur.close()
    put_conn(conn)

    next_card_info = {
        "value": next_value,
        "val_str": VAL_MAP[next_value],
        "suit": next_suit,
        "symbol": SUIT_MAP[next_suit]["symbol"],
        "color": SUIT_MAP[next_suit]["color"]
    }

    # 1. DRAW（引き分け）の場合
    if next_value == current_value:
        session["hl_current_value"] = next_value
        session["hl_current_suit"] = next_suit
        est_payout = int(bet * multiplier)
        
        return jsonify({
            "success": True,
            "result": "draw",
            "next_card": next_card_info,
            "streak": streak,
            "multiplier": round(multiplier, 2),
            "est_payout": est_payout,
            "coins": coins,
            "msg": f"🤝 DRAW! 同じ数字 ({VAL_MAP[next_value]}) でした。再挑戦できます！"
        })

    # 2. 勝敗判定
    is_win = (next_value > current_value) if choice == "high" else (next_value < current_value)

    if is_win:
        round_mult = calc_round_multiplier(current_value, choice)
        multiplier = round(multiplier * round_mult, 2)
        streak += 1
        est_payout = int(bet * multiplier)

        session["hl_multiplier"] = multiplier
        session["hl_streak"] = streak
        session["hl_current_value"] = next_value
        session["hl_current_suit"] = next_suit

        return jsonify({
            "success": True,
            "result": "win",
            "next_card": next_card_info,
            "streak": streak,
            "multiplier": multiplier,
            "est_payout": est_payout,
            "coins": coins,
            "msg": f"🎉 WIN! {streak}連勝中! (現在倍率: x{multiplier} / 配当予想: ${est_payout:,})"
        })
    else:
        # LOSEの場合
        session.pop("hl_bet", None)
        session.pop("hl_multiplier", None)
        session.pop("hl_streak", None)
        session.pop("hl_current_value", None)
        session.pop("hl_current_suit", None)

        return jsonify({
            "success": True,
            "result": "lose",
            "next_card": next_card_info,
            "streak": 0,
            "multiplier": 0,
            "est_payout": 0,
            "coins": coins,
            "msg": f"💥 LOSE... 残念！カードは [ {VAL_MAP[next_value]} ] でした（賭け金没収）"
        })


@highlow_bp.route("/highlow_cashout", methods=["POST"])
@login_required
def highlow_cashout():
    bet = session.get("hl_bet", 0)
    multiplier = session.get("hl_multiplier", 0)
    payout = int(bet * multiplier)

    if payout <= 0:
        return jsonify({"success": False, "msg": "キャッシュアウトできる配当がありません"}), 400

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
    session.pop("hl_streak", None)
    session.pop("hl_current_value", None)
    session.pop("hl_current_suit", None)

    return jsonify({
        "success": True,
        "payout": payout,
        "coins": coins,
        "msg": f"💰 CASH OUT! ${payout:,} を獲得しました！"
    })
