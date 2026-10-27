import random
import string
from flask import Flask, render_template, jsonify, request, Blueprint
from flask_login import UserMixin, current_user

chess_bp = Blueprint('chess', __name__, template_folder='.', static_folder='static')

# Renderのメモリ上でルームデータを管理（DB不要）
# 構造: { room_code: { "fen": str, "white_player": str, "black_player": str, "status": str } }
ROOMS = {}

def generate_room_code():
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        if code not in ROOMS:
            return code

@chess_bp.route('/chess')
def chess_page():
    return render_template('chess.html')

@chess_bp.route('/api/chess/get_rooms', methods=['GET'])
def get_rooms():
    """現在存在するルームの一覧を返すAPI"""
    room_list = []
    for code, room in ROOMS.items():
        room_list.append({
            "room_code": code,
            "white_player": room["white_player"],
            "black_player": room["black_player"],
            "status": room["status"]
        })
    return jsonify({"success": True, "rooms": room_list})

@chess_bp.route('/api/chess/create_room', methods=['POST'])
def create_room():
    """新規ルーム作成API"""
    code = generate_room_code()
    initial_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    # current_userからユーザー名を取得（未ログイン時はゲスト名）
    player_id = getattr(current_user, 'username', f"Guest_{code}")
    
    ROOMS[code] = {
        "fen": initial_fen,
        "white_player": player_id,
        "black_player": None,
        "status": "waiting"
    }
    
    return jsonify({
        "success": True,
        "room_code": code,
        "player_id": player_id,
        "color": "w"
    })

@chess_bp.route('/api/chess/join_room', methods=['POST'])
def join_room():
    """ルーム参加API"""
    data = request.get_json() or {}
    code = data.get('room_code', '').upper()
    player_id = getattr(current_user, 'username', f"Guest_{code}")

    if code not in ROOMS:
        return jsonify({"success": False, "error": "指定されたルームが見つかりません"}), 404

    room = ROOMS[code]
    color = 'spectator'

    if room["white_player"] == player_id:
        color = 'w'
    elif room["black_player"] == player_id:
        color = 'b'
    elif not room["white_player"]:
        room["white_player"] = player_id
        color = 'w'
    elif not room["black_player"]:
        room["black_player"] = player_id
        room["status"] = 'active'
        color = 'b'

    return jsonify({
        "success": True,
        "room_code": code,
        "fen": room["fen"],
        "color": color,
        "white_player": room["white_player"],
        "black_player": room["black_player"],
        "status": room["status"]
    })

@chess_bp.route('/api/chess/get_state', methods=['GET'])
def get_state():
    """対局の最新状態取得（ポーリング用API）"""
    code = request.args.get('room_code', '').upper()
    if code not in ROOMS:
        return jsonify({"success": False, "error": "ルームが存在しません"}), 404
    
    room = ROOMS[code]
    return jsonify({
        "success": True,
        "fen": room["fen"],
        "white_player": room["white_player"],
        "black_player": room["black_player"],
        "status": room["status"]
    })

@chess_bp.route('/api/chess/make_move', methods=['POST'])
def make_move():
    """手番の更新API"""
    data = request.get_json() or {}
    code = data.get('room_code', '').upper()
    new_fen = data.get('fen')

    if code not in ROOMS:
        return jsonify({"success": False, "error": "ルームが存在しません"}), 404

    ROOMS[code]["fen"] = new_fen
    return jsonify({"success": True})

@chess_bp.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "message": "Render Memory Chess Server is running"})
