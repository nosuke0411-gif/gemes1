from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from flask_login import current_user
import random
import string

chess_bp = Blueprint('chess_bp', __name__)

# Renderインメモリデータ保持用の辞書
rooms = {}

def generate_room_code(length=4):
    """ 4桁のアルファベット+数字コード生成 """
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choices(chars, k=length))
        if code not in rooms:
            return code

def get_current_user_name():
    """ DB / Flask-Login からログインユーザー名を取得 """
    if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
        return current_user.username
    return session.get('user_name') or session.get('username') or 'Guest'

@chess_bp.route('')
@chess_bp.route('/')
def index():
    """ ロビー表示（アクティブな3件のルームをランダムに抽出） """
    waiting_rooms = {code: data for code, data in rooms.items() if data['status'] == 'waiting'}
    active_codes = list(waiting_rooms.keys())
    random.shuffle(active_codes)
    selected_codes = active_codes[:3]
    
    random_rooms = {code: waiting_rooms[code] for code in selected_codes}
    player_name = get_current_user_name()
    
    return render_template('chess.html', rooms=random_rooms, room_code=None, room_data=None, player_name=player_name)

@chess_bp.route('/api/rooms')
def api_active_rooms():
    """ 待機中のルームからランダムに3件取得してJSONで返すAPI """
    waiting_rooms = {code: data for code, data in rooms.items() if data['status'] == 'waiting'}
    active_codes = list(waiting_rooms.keys())
    random.shuffle(active_codes)
    selected_codes = active_codes[:3]
    
    random_rooms = {code: waiting_rooms[code] for code in selected_codes}
    return jsonify(random_rooms)

@chess_bp.route('/create', methods=['POST'])
def create_room():
    """ 新規ルーム作成時にホストの色をランダムに決定 (True=白, False=黒) """
    player_name = get_current_user_name()
    room_code = generate_room_code()
    
    host_is_white = random.choice([True, False])
    
    rooms[room_code] = {
        'host': player_name,
        'guest': None,
        'status': 'waiting',
        'host_is_white': host_is_white,
        'fen': 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        'turn': 'w'
    }
    
    return redirect(url_for('chess_bp.room', room_code=room_code))

@chess_bp.route('/join', methods=['POST'])
def join_room():
    """ コード指定による参加 """
    room_code = request.form.get('room_code', '').strip().upper()
    player_name = get_current_user_name()
    
    if room_code in rooms and rooms[room_code]['status'] == 'waiting':
        if rooms[room_code]['host'] != player_name:
            rooms[room_code]['guest'] = player_name
            rooms[room_code]['status'] = 'playing'
        return redirect(url_for('chess_bp.room', room_code=room_code))
    
    return redirect(url_for('chess_bp.index'))

@chess_bp.route('/room/<room_code>')
def room(room_code):
    """ 対戦画面の表示 """
    if room_code not in rooms:
        return redirect(url_for('chess_bp.index'))
    
    player_name = get_current_user_name()
    room_data = rooms[room_code]
    
    return render_template('chess.html', rooms={}, room_code=room_code, room_data=room_data, player_name=player_name)

@chess_bp.route('/api/status/<room_code>')
def room_status_api(room_code):
    """ ルームの最新ステータスを返すAPI（ポーリング用） """
    if room_code not in rooms:
        return jsonify({'error': 'Room not found'}), 404
    return jsonify(rooms[room_code])

@chess_bp.route('/api/move/<room_code>', methods=['POST'])
def update_room_move(room_code):
    """ 棋譜・局面を同期するAPI """
    if room_code not in rooms:
        return jsonify({'error': 'Room not found'}), 404
    
    data = request.get_json()
    if data and 'fen' in data:
        rooms[room_code]['fen'] = data['fen']
        rooms[room_code]['turn'] = data.get('turn', 'w')
        if data.get('status'):
            rooms[room_code]['status'] = data['status']
            
    return jsonify({'status': 'success', 'room': rooms[room_code]})

@chess_bp.route('/leave/<room_code>', methods=['POST', 'GET'])
def leave_room(room_code):
    """ 退出処理（ホストが待機中に退出した場合はルーム削除） """
    player_name = get_current_user_name()
    
    if room_code in rooms:
        room_data = rooms[room_code]
        if room_data['host'] == player_name and room_data['status'] == 'waiting':
            rooms.pop(room_code, None)
    
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.method == 'POST':
        return jsonify({'status': 'success', 'message': 'Room left/deleted'})
    
    return redirect(url_for('chess_bp.index'))
