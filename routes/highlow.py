import random
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
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

def calc_multiplier(current_value, choice):
    choice = choice.lower()
    if choice == "high":
        prob = (13 - current_value) / 13
    else:
        prob = (current_value - 1) / 13

    if prob <= 0:
        return 1.10
    return round(1 / prob, 2)

def build_card_html(card_id_prefix, value, suit_code, is_hidden=False, extra_class=""):
    suit_info = SUIT_MAP.get(suit_code, SUIT_MAP["S"])
    val_str = VAL_MAP.get(value, str(value))
    is_red = suit_info["color"] == "red"
    flipped_class = "flipped" if not is_hidden else ""

    return f"""
    <div class="card-container {flipped_class} {extra_class}" id="{card_id_prefix}-container">
        <div class="card-inner">
            <div class="card-front {'red' if is_red else 'black'}" id="{card_id_prefix}-front">
                <div class="card-corner top-left">
                    <span class="corner-val">{val_str}</span>
                    <span class="corner-suit">{suit_info['symbol']}</span>
                </div>
                <div class="card-center">{suit_info['symbol']}</div>
                <div class="card-corner bottom-right">
                    <span class="corner-val">{val_str}</span>
                    <span class="corner-suit">{suit_info['symbol']}</span>
                </div>
            </div>
            <div class="card-back">
                <div class="card-back-pattern">
                    <div class="card-back-emblem">👑</div>
                </div>
            </div>
        </div>
    </div>
    """

def render_full_game_view(coins, streak, base_val, base_suit, next_val=None, next_suit=None, 
                         next_hidden=True, multiplier=1.0, bet=10, result_msg="", 
                         game_over=False, next_card_class=""):
    
    base_card_html = build_card_html("card-base", base_val, base_suit, is_hidden=False)
    
    if next_hidden or next_val is None:
        next_card_html = build_card_html("card-next", 1, "S", is_hidden=True)
    else:
        next_card_html = build_card_html("card-next", next_val, next_suit, is_hidden=False, extra_class=next_card_class)

    est_payout = int(bet * multiplier)

    # Action buttons render
    if game_over:
        control_buttons = f"""
        <button class="btn btn-gold" onclick="location.reload()">
            ✨ もう一度遊ぶ
        </button>
        """
    else:
        cashout_btn_display = "block" if streak > 0 else "none"
        control_buttons = f"""
        <div class="btn-group" id="choice-btns">
            <button class="btn btn-high" onclick="play('HIGH')">
                ▲ HIGH
            </button>
            <button class="btn btn-low" onclick="play('LOW')">
                ▼ LOW
            </button>
        </div>

        <button class="btn btn-cashout" id="cashout-btn" style="display: {cashout_btn_display}; margin-top: 8px;" onclick="cashout()">
            💰 CASH OUT (<span>${est_payout}</span>)
        </button>
        """

    return f"""
    <div class="top-bar">
        <h1 class="brand-title gold-text">
            👑 HIGH & LOW <span class="vip-tag">VIP WIDE</span>
        </h1>
        <div class="top-stats">
            <div class="stat-badge">
                <span class="stat-label">STREAK:</span>
                <span class="stat-value">{streak}</span>
            </div>
            <div class="stat-badge">
                <span class="stat-label">CHIPS:</span>
                <span class="stat-value">{coins:,}</span>
            </div>
        </div>
    </div>

    <div class="main-layout">
        <div class="table-board">
            <div class="table-logo">ROYAL HIGH & LOW</div>

            <div class="multiplier-badge">
                <span>CURRENT MULTIPLIER:</span>
                <span class="multiplier-val">x{round(multiplier, 2)}</span>
            </div>

            <div class="arena">
                <div class="card-slot">
                    <div class="slot-label">BASE CARD</div>
                    {base_card_html}
                </div>

                <div class="card-slot">
                    <div class="slot-label">NEXT CARD</div>
                    {next_card_html}
                </div>
            </div>

            <div class="result-banner" id="result-message">
                {result_msg}
            </div>
        </div>

        <div class="controls-panel">
            <div class="panel-header">GAME STATUS & CONTROLS</div>

            <div style="background: rgba(0,0,0,0.5); padding: 12px; border-radius: 16px; border: 1px solid rgba(212,175,55,0.2); text-align: center;">
                <div style="font-size: 11px; color: #aaa; font-weight: 700;">CURRENT BET</div>
                <div style="font-size: 22px; color: #ffd700; font-weight: 900;">${bet:,}</div>
                <div style="font-size: 11px; color: #2ecc71; margin-top: 4px; font-weight: 700;">
                    POTENTIAL WIN: ${est_payout:,}
                </div>
            </div>

            <div id="action-controls" style="display: flex; flex-direction: column; gap: 8px;">
                {control_buttons}
            </div>

            <button class="btn-sub" onclick="location.href='/games'">◀ ゲーム一覧へ戻る</button>
        </div>
    </div>
    """


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
                           suit_emoji=suit_info["symbol"],
                           suit_name=suit_info["name"])


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
    session["hl_streak"] = 0
    session["hl_current_value"] = current_value
    session["hl_current_suit"] = current_suit

    html = render_full_game_view(
        coins=coins,
        streak=0,
        base_val=current_value,
        base_suit=current_suit,
        next_hidden=True,
        multiplier=1.0,
        bet=bet,
        result_msg="「HIGH」か「LOW」かを選択してください"
    )
    return jsonify({"html": html})


@highlow_bp.route("/highlow_play2", methods=["POST"])
@login_required
def highlow_play2():
    data = request.json or {}
    choice = str(data.get("choice", "")).lower()

    current_value = session.get("hl_current_value", 7)
    current_suit = session.get("hl_current_suit", "S")
    multiplier = session.get("hl_multiplier", 1.0)
    streak = session.get("hl_streak", 0)
    bet = session.get("hl_bet", 0)

    next_value, next_suit = generate_card()

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT coins FROM users WHERE id=%s", (current_user.id,))
    coins = cur.fetchone()[0]
    cur.close()
    put_conn(conn)

    # Draw case
    if next_value == current_value:
        est_payout = int(bet * multiplier)
        result_msg = f"🤝 DRAW! 引き分け（同じ数字: {VAL_MAP[next_value]}）のため再挑戦できます！"
        
        session["hl_current_value"] = next_value
        session["hl_current_suit"] = next_suit

        html = render_full_game_view(
            coins=coins,
            streak=streak,
            base_val=next_value,
            base_suit=next_suit,
            next_val=next_value,
            next_suit=next_suit,
            next_hidden=False,
            multiplier=multiplier,
            bet=bet,
            result_msg=result_msg
        )
        return jsonify({"html": html})

    win = (next_value > current_value) if choice == "high" else (next_value < current_value)
    round_multiplier = calc_multiplier(current_value, choice)

    if win:
        streak += 1
        multiplier *= round_multiplier
        est_payout = int(bet * multiplier)
        result_msg = f"🎉 WIN! {streak}連勝中! (現在倍率: x{round(multiplier, 2)} / 予想配当: ${est_payout:,})"

        session["hl_multiplier"] = multiplier
        session["hl_streak"] = streak
        session["hl_current_value"] = next_value
        session["hl_current_suit"] = next_suit

        html = render_full_game_view(
            coins=coins,
            streak=streak,
            base_val=next_value,
            base_suit=next_suit,
            next_val=next_value,
            next_suit=next_suit,
            next_hidden=False,
            next_card_class="win",
            multiplier=multiplier,
            bet=bet,
            result_msg=result_msg
        )
    else:
        session["hl_multiplier"] = 0
        session["hl_streak"] = 0
        result_msg = f"💥 LOSE... 残念！カードは [ {VAL_MAP[next_value]} ] でした（賭け金没収）"

        html = render_full_game_view(
            coins=coins,
            streak=0,
            base_val=current_value,
            base_suit=current_suit,
            next_val=next_value,
            next_suit=next_suit,
            next_hidden=False,
            next_card_class="lose",
            multiplier=0,
            bet=bet,
            result_msg=result_msg,
            game_over=True
        )

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
    session.pop("hl_streak", None)
    session.pop("hl_current_value", None)
    session.pop("hl_current_suit", None)

    return f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>High & Low - CASH OUT</title>
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@700;900&family=Montserrat:wght@700;900&display=swap" rel="stylesheet">
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            padding: 0;
            width: 100vw;
            height: 100vh;
            font-family: 'Montserrat', sans-serif;
            background: radial-gradient(circle at center, #1a2638 0%, #05070a 80%);
            color: #ffffff;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .cashout-card {{
            background: linear-gradient(180deg, rgba(20, 15, 12, 0.95) 0%, rgba(8, 5, 3, 0.98) 100%);
            border: 2px solid #d4af37;
            border-radius: 30px;
            padding: 40px;
            width: 90%;
            max-width: 520px;
            text-align: center;
            box-shadow: 0 15px 40px rgba(0,0,0,0.9);
        }}
        .gold-title {{
            font-family: 'Cinzel', serif;
            font-size: 28px;
            color: #ffd700;
            margin-bottom: 20px;
            letter-spacing: 2px;
        }}
        .payout-val {{
            font-size: 42px;
            font-weight: 900;
            color: #2ecc71;
            margin: 15px 0;
            text-shadow: 0 0 15px rgba(46, 204, 113, 0.4);
        }}
        .btn-gold {{
            background: linear-gradient(135deg, #ffe066 0%, #d4af37 50%, #aa7c11 100%);
            color: #1a0f00;
            padding: 14px 28px;
            font-size: 16px;
            font-weight: 900;
            border-radius: 25px;
            border: none;
            cursor: pointer;
            width: 100%;
            margin-top: 15px;
        }}
        .btn-sub {{
            background: transparent;
            border: none;
            color: #aaa;
            margin-top: 15px;
            cursor: pointer;
            font-size: 13px;
        }}
    </style>
    </head>
    <body>
        <div class="cashout-card">
            <div class="gold-title">💰 CASH OUT SUCCESSFUL</div>
            <div style="color: #aaa; font-weight: 700;">獲得コイン</div>
            <div class="payout-val">+${payout:,}</div>
            <div style="color: #ffd700; margin-bottom: 20px;">現在の総所持コイン: ${coins:,}</div>

            <button class="btn-gold" onclick="location.href='/highlow'">新しくゲームを始める</button>
            <br>
            <button class="btn-sub" onclick="location.href='/games'">◀ ゲーム一覧へ戻る</button>
        </div>
    </body>
    </html>
    """
