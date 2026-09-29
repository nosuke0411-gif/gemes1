import random
from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user
from db import get_conn, put_conn

blackjack_bp = Blueprint('blackjack', __name__)

SUIT_MAP = {"S": "♠️", "H": "♥️", "D": "♦️", "C": "♣️"}
CARD_NAMES = {1: "A", 11: "J", 12: "Q", 13: "K"}

def get_card_display(card):
    """カード表示用テキスト（例: ♠️ A）を返す"""
    val, suit = card
    val_str = CARD_NAMES.get(val, str(val))
    return f"{SUIT_MAP[suit]} {val_str}"

def calculate_hand_value(hand):
    """手札の合計値を計算する（Aは21を超えないように1または11で自動計算）"""
    total = 0
    aces = 0
    for val, suit in hand:
        if val == 1:
            aces += 1
            total += 11
        elif val >= 10:
            total += 10
        else:
            total += val

    # 21を超えている場合はAを11から1に変換
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1

    return total

def create_shuffled_deck():
    """52枚のトランプ山札を生成してシャッフル"""
    deck = [(val, suit) for val in range(1, 14) for suit in ["S", "H", "D", "C"]]
    random.shuffle(deck)
    return deck

@blackjack_bp.route("/blackjack")
@login_required
def blackjack_page():
    """ブラックジャック画面の表示"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT coins FROM users WHERE id=%s", (current_user.id,))
    row = cur.fetchone()
    coins = row[0] if row else current_user.coins
    cur.close()
    put_conn(conn)
    return render_template("blackjack.html", coins=coins)

@blackjack_bp.route("/blackjack/start", methods=["POST"])
@login_required
def blackjack_start():
    """ゲーム開始処理（ベット・初期2枚の配布・ブラックジャック即時判定）"""
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
        return jsonify({"success": False, "error": "ベット額が不正です"}), 400

    # コイン消費
    coins -= bet
    cur.execute("UPDATE users SET coins=%s WHERE id=%s", (coins, current_user.id))
    conn.commit()
    cur.close()
    put_conn(conn)

    # デッキの作成と初期ディール
    deck = create_shuffled_deck()
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]

    session["bj_deck"] = deck
    session["bj_player_hand"] = player_hand
    session["bj_dealer_hand"] = dealer_hand
    session["bj_bet"] = bet
    session["bj_game_over"] = False

    player_total = calculate_hand_value(player_hand)
    dealer_upcard = dealer_hand[0]

    # プレイヤーのナチュラルブラックジャック判定（初手A+10/絵札）
    if player_total == 21:
        dealer_total = calculate_hand_value(dealer_hand)
        session["bj_game_over"] = True

        if dealer_total == 21:
            # 引き分け（返金）
            payout = bet
            message = "引き分け！双方ブラックジャック（賭け金返金）"
        else:
            # ブラックジャック勝利（5.0倍配当）
            payout = int(bet * 5.0)
            message = f"🎉 ブラックジャック達成！ 5.0倍（+{payout} コイン）"

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT coins FROM users WHERE id=%s", (current_user.id,))
        current_coins = cur.fetchone()[0]
        current_coins += payout
        cur.execute("UPDATE users SET coins=%s WHERE id=%s", (current_coins, current_user.id))
        conn.commit()
        cur.close()
        put_conn(conn)

        return jsonify({
            "success": True,
            "game_over": True,
            "player_hand": [get_card_display(c) for c in player_hand],
            "dealer_hand": [get_card_display(c) for c in dealer_hand],
            "player_total": 21,
            "dealer_total": dealer_total,
            "payout": payout,
            "coins": current_coins,
            "message": message
        })

    return jsonify({
        "success": True,
        "game_over": False,
        "player_hand": [get_card_display(c) for c in player_hand],
        "dealer_hand": [get_card_display(dealer_upcard), "❓"],
        "player_total": player_total,
        "dealer_total": calculate_hand_value([dealer_upcard]),
        "coins": coins
    })

@blackjack_bp.route("/blackjack/hit", methods=["POST"])
@login_required
def blackjack_hit():
    """ヒット処理（カードを1枚追加）"""
    if session.get("bj_game_over", True):
        return jsonify({"success": False, "error": "ゲームは既に終了しています"}), 400

    deck = session.get("bj_deck", [])
    player_hand = session.get("bj_player_hand", [])
    dealer_hand = session.get("bj_dealer_hand", [])
    bet = session.get("bj_bet", 0)

    if not deck:
        return jsonify({"success": False, "error": "山札がありません"}), 400

    new_card = deck.pop()
    player_hand.append(new_card)

    session["bj_deck"] = deck
    session["bj_player_hand"] = player_hand

    player_total = calculate_hand_value(player_hand)

    # バースト判定
    if player_total > 21:
        session["bj_game_over"] = True
        dealer_total = calculate_hand_value(dealer_hand)

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT coins FROM users WHERE id=%s", (current_user.id,))
        current_coins = cur.fetchone()[0]
        cur.close()
        put_conn(conn)

        return jsonify({
            "success": True,
            "game_over": True,
            "player_hand": [get_card_display(c) for c in player_hand],
            "dealer_hand": [get_card_display(c) for c in dealer_hand],
            "player_total": player_total,
            "dealer_total": dealer_total,
            "payout": 0,
            "coins": current_coins,
            "message": "💥 バースト！ 21を超えたため負けです。"
        })

    dealer_upcard = dealer_hand[0]
    return jsonify({
        "success": True,
        "game_over": False,
        "player_hand": [get_card_display(c) for c in player_hand],
        "dealer_hand": [get_card_display(dealer_upcard), "❓"],
        "player_total": player_total,
        "dealer_total": calculate_hand_value([dealer_upcard])
    })

@blackjack_bp.route("/blackjack/stand", methods=["POST"])
@login_required
def blackjack_stand():
    """スタンド処理（ディーラーの自動引込み・勝敗判定）"""
    if session.get("bj_game_over", True):
        return jsonify({"success": False, "error": "ゲームは既に終了しています"}), 400

    deck = session.get("bj_deck", [])
    player_hand = session.get("bj_player_hand", [])
    dealer_hand = session.get("bj_dealer_hand", [])
    bet = session.get("bj_bet", 0)

    session["bj_game_over"] = True

    # ディーラーは17以上になるまで引き続ける
    while calculate_hand_value(dealer_hand) < 17 and deck:
        dealer_hand.append(deck.pop())

    player_total = calculate_hand_value(player_hand)
    dealer_total = calculate_hand_value(dealer_hand)

    # 勝敗と配当の計算
    if dealer_total > 21:
        payout = bet * 2
        message = f"🎉 ディーラーがバースト！ 勝利！（+{payout} コイン）"
    elif player_total > dealer_total:
        payout = bet * 2
        message = f"🎉 勝利！ 2.0倍（+{payout} コイン）"
    elif player_total == dealer_total:
        payout = bet
        message = "引き分け（Push）！ 賭け金を返金します。"
    else:
        payout = 0
        message = "ディーラーの勝ち。没収されました。"

    # コイン加算（勝利/引き分け時）
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT coins FROM users WHERE id=%s", (current_user.id,))
    current_coins = cur.fetchone()[0]

    if payout > 0:
        current_coins += payout
        cur.execute("UPDATE users SET coins=%s WHERE id=%s", (current_coins, current_user.id))
        conn.commit()

    cur.close()
    put_conn(conn)

    return jsonify({
        "success": True,
        "game_over": True,
        "player_hand": [get_card_display(c) for c in player_hand],
        "dealer_hand": [get_card_display(c) for c in dealer_hand],
        "player_total": player_total,
        "dealer_total": dealer_total,
        "payout": payout,
        "coins": current_coins,
        "message": message
    })
