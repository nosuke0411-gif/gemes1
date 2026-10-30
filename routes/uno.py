import random
import string
import os
from flask import Flask, render_template, request, session, Blueprint
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from flask_login import current_user

uno_bp = Blueprint('uno',__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'uno_secret_key_12345')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

def get_current_user_name():
    """ DB / Flask-Login からログインユーザー名を取得 """
    if current_user and hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
        return getattr(current_user, 'username', 'User')
    return session.get('user_name') or session.get('username') or 'Guest'

# In-memory storage for active rooms and game states
rooms = {}

COLORS = ['Red', 'Yellow', 'Green', 'Blue']
NUMBERS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
ACTIONS = ['Skip', 'Reverse', 'DrawTwo']
WILDS = ['Wild', 'WildDrawFour']

def generate_room_code():
    """ 4桁のランダムなアルファベット・数字のルームコードを作成 """
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        if code not in rooms:
            return code

def create_deck():
    """Generates a standard 108-card UNO deck."""
    deck = []
    for color in COLORS:
        deck.append({'color': color, 'type': 'number', 'value': 0, 'id': f"{color}_0_0"})
        for num in NUMBERS[1:]:
            deck.append({'color': color, 'type': 'number', 'value': num, 'id': f"{color}_{num}_1"})
            deck.append({'color': color, 'type': 'number', 'value': num, 'id': f"{color}_{num}_2"})
        for action in ACTIONS:
            deck.append({'color': color, 'type': 'action', 'value': action, 'id': f"{color}_{action}_1"})
            deck.append({'color': color, 'type': 'action', 'value': action, 'id': f"{color}_{action}_2"})
    for i in range(4):
        deck.append({'color': 'Wild', 'type': 'wild', 'value': 'Wild', 'id': f"Wild_Wild_{i}"})
        deck.append({'color': 'Wild', 'type': 'wild', 'value': 'WildDrawFour', 'id': f"Wild_WildDrawFour_{i}"})
    
    random.shuffle(deck)
    return deck

class UnoGame:
    def __init__(self, room_code):
        self.room_code = room_code
        self.players = []
        self.deck = create_deck()
        self.discard_pile = []
        self.current_turn = 0
        self.direction = 1
        self.current_color = None
        self.status = 'waiting'
        self.winner = None
        self.logs = []

    def log(self, text):
        self.logs.append(text)
        if len(self.logs) > 30:
            self.logs.pop(0)

    def add_player(self, sid, name):
        if len(self.players) >= 6 or self.status != 'waiting':
            return False
        existing_names = [p['name'] for p in self.players]
        final_name = name
        counter = 1
        while final_name in existing_names:
            final_name = f"{name}_{counter}"
            counter += 1

        self.players.append({
            'id': sid,
            'name': final_name,
            'hand': [],
            'uno_called': False,
            'has_drawn': False
        })
        self.log(f"【参加】{final_name} さんが参加しました。")
        return True

    def remove_player(self, sid):
        player = next((p for p in self.players if p['id'] == sid), None)
        if player:
            self.players.remove(player)
            self.log(f"【退出】{player['name']} さんが退出しました。")
            if len(self.players) < 3 and self.status == 'playing':
                self.status = 'finished'
                self.log("プレイヤー数が3人未満になったため、ゲームを終了しました。")
            elif self.status == 'playing':
                if self.current_turn >= len(self.players):
                    self.current_turn = 0

    def draw_card(self, count=1):
        drawn = []
        for _ in range(count):
            if not self.deck:
                if len(self.discard_pile) > 1:
                    top_card = self.discard_pile.pop()
                    self.deck = self.discard_pile
                    random.shuffle(self.deck)
                    self.discard_pile = [top_card]
                    self.log("山札が切れたため、捨て札をシャッフルして山札に補充しました。")
                else:
                    break
            if self.deck:
                drawn.append(self.deck.pop())
        return drawn

    def start_game(self):
        if not (3 <= len(self.players) <= 6):
            return False, "プレイヤー人数は3〜6人である必要があります。"

        self.deck = create_deck()
        self.discard_pile = []
        self.status = 'playing'
        self.direction = 1
        self.current_turn = 0
        self.winner = None

        for player in self.players:
            player['hand'] = self.draw_card(7)
            player['uno_called'] = False
            player['has_drawn'] = False

        top_card = self.deck.pop()
        while top_card['value'] == 'WildDrawFour':
            self.deck.append(top_card)
            random.shuffle(self.deck)
            top_card = self.deck.pop()

        self.discard_pile.append(top_card)

        if top_card['color'] == 'Wild':
            self.current_color = random.choice(COLORS)
        else:
            self.current_color = top_card['color']

        self.log("=== ゲームがスタートしました！ ===")
        self.log(f"最初のカード: [{self.get_card_display(top_card)}]")

        self.apply_initial_card_effect(top_card)
        return True, "成功"

    def get_card_display(self, card):
        return f"{card['color']} {card['value']}"

    def apply_initial_card_effect(self, card):
        if card['value'] == 'Skip':
            self.log(f"最初のカードがSkipのため、{self.players[self.current_turn]['name']} さんのターンがスキップされました。")
            self.advance_turn()
        elif card['value'] == 'Reverse':
            self.direction *= -1
            self.log("最初のカードがReverseのため、順番が逆回りになりました。")
        elif card['value'] == 'DrawTwo':
            curr_player = self.players[self.current_turn]
            drawn = self.draw_card(2)
            curr_player['hand'].extend(drawn)
            self.log(f"最初のカードがDrawTwoのため、{curr_player['name']} さんが2枚引いてターンがスキップされました。")
            self.advance_turn()

    def advance_turn(self):
        if 0 <= self.current_turn < len(self.players):
            self.players[self.current_turn]['has_drawn'] = False
        self.current_turn = (self.current_turn + self.direction) % len(self.players)

    def is_valid_play(self, card):
        top_card = self.discard_pile[-1]
        if card['type'] == 'wild' or card['color'] == self.current_color or card['value'] == top_card['value']:
            return True
        return False

    def play_card(self, sid, card_id, chosen_color=None):
        curr_player = self.players[self.current_turn]
        if curr_player['id'] != sid:
            return False, "あなたのターンではありません。"

        card = next((c for c in curr_player['hand'] if c['id'] == card_id), None)
        if not card or not self.is_valid_play(card):
            return False, "そのカードは出せません。"

        if card['type'] == 'wild' and not chosen_color:
            return False, "色の選択が必要です。"

        curr_player['hand'].remove(card)
        self.discard_pile.append(card)

        if card['type'] == 'wild':
            self.current_color = chosen_color
            self.log(f"{curr_player['name']} が [{card['value']}] を出し、色を 【{chosen_color}】 に変更しました。")
        else:
            self.current_color = card['color']
            self.log(f"{curr_player['name']} が [{self.get_card_display(card)}] を出しました。")

        if len(curr_player['hand']) != 1:
            curr_player['uno_called'] = False

        if len(curr_player['hand']) == 0:
            self.status = 'finished'
            self.winner = curr_player['name']
            self.log(f"🎉 {curr_player['name']} さんが勝利しました！")
            return True, "勝利"

        next_player = self.players[(self.current_turn + self.direction) % len(self.players)]

        if card['value'] == 'Skip':
            self.log(f"{next_player['name']} さんのターンがスキップされました。")
            self.advance_turn()
            self.advance_turn()
        elif card['value'] == 'Reverse':
            self.direction *= -1
            self.log("順番が逆回りになりました！")
            self.advance_turn()
        elif card['value'] == 'DrawTwo':
            next_player['hand'].extend(self.draw_card(2))
            self.log(f"{next_player['name']} さんは2枚引かされ、ターンがスキップされました。")
            self.advance_turn()
            self.advance_turn()
        elif card['value'] == 'WildDrawFour':
            next_player['hand'].extend(self.draw_card(4))
            self.log(f"{next_player['name']} さんは4枚引かされ、ターンがスキップされました。")
            self.advance_turn()
            self.advance_turn()
        else:
            self.advance_turn()

        return True, "成功"

    def player_draw_card(self, sid):
        curr_player = self.players[self.current_turn]
        if curr_player['id'] != sid or curr_player['has_drawn']:
            return False, "カードを引けません。"

        drawn = self.draw_card(1)
        if drawn:
            curr_player['hand'].extend(drawn)
            curr_player['has_drawn'] = True
            self.log(f"{curr_player['name']} さんが山札から1枚引きました。")
            return True, drawn[0]
        return False, "山札からカードを引けませんでした。"

    def player_pass(self, sid):
        curr_player = self.players[self.current_turn]
        if curr_player['id'] != sid or not curr_player['has_drawn']:
            return False, "パスできません。"

        self.log(f"{curr_player['name']} さんがパスしました。")
        self.advance_turn()
        return True, "パスしました。"

    def call_uno(self, sid):
        player = next((p for p in self.players if p['id'] == sid), None)
        if not player:
            return False, "プレイヤーが見つかりません。"

        if len(player['hand']) == 1:
            player['uno_called'] = True
            self.log(f"🔥 {player['name']} さんが 「UNO!」 を宣言しました！")
            return True, "UNO宣言成功！"
        else:
            player['hand'].extend(self.draw_card(2))
            self.log(f"⚠️ {player['name']} さんの誤認UNO宣言！ペナルティで2枚引きました。")
            return False, "ペナルティ"

    def catch_uno_penalty(self, target_name):
        target = next((p for p in self.players if p['name'] == target_name), None)
        if target and len(target['hand']) == 1 and not target['uno_called']:
            target['hand'].extend(self.draw_card(2))
            self.log(f"🚨 {target['name']} さんのUNOの言い忘れが指摘されました！ペナルティで2枚引きました。")
            return True, "指摘成功"
        return False, "指摘の対象外です。"

    def get_state(self, sid):
        my_player = next((p for p in self.players if p['id'] == sid), None)
        players_info = [{
            'name': p['name'],
            'card_count': len(p['hand']),
            'uno_called': p['uno_called'],
            'is_current': self.players[self.current_turn]['id'] == p['id'] if self.players else False
        } for p in self.players]

        return {
            'room_code': self.room_code,
            'status': self.status,
            'players': players_info,
            'current_turn_name': self.players[self.current_turn]['name'] if self.players and self.status == 'playing' else None,
            'is_my_turn': (self.players[self.current_turn]['id'] == sid) if (self.players and self.status == 'playing') else False,
            'my_hand': my_player['hand'] if my_player else [],
            'top_card': self.discard_pile[-1] if self.discard_pile else None,
            'current_color': self.current_color,
            'direction': '時計回り' if self.direction == 1 else '反時計回り',
            'deck_count': len(self.deck),
            'winner': self.winner,
            'has_drawn': my_player['has_drawn'] if my_player else False,
            'logs': self.logs
        }

def init_game_state(room_code):
    if room_code not in rooms:
        rooms[room_code] = UnoGame(room_code)
    return rooms[room_code]

def broadcast_state(room_code):
    if room_code in rooms:
        game = rooms[room_code]
        for p in game.players:
            state = game.get_state(p['id'])
            socketio.emit('game_state', state, room=p['id'])

@app.route('/uno')
def index():
    return render_template('uno.html')

# WebSocket Handlers
@socketio.on('get_user_info')
def handle_get_user_info():
    user_name = get_current_user_name()
    emit('user_info', {'user_name': user_name})

@socketio.on('create_room')
def handle_create_room():
    room_code = generate_room_code()
    emit('room_created', {'room_code': room_code})

@socketio.on('join_game')
def handle_join(data):
    room_code = data.get('room', '').upper()
    player_name = data.get('name') or get_current_user_name()
    sid = request.sid

    if not room_code or room_code not in rooms and len(rooms) > 100:
        emit('error_message', {'message': '無効なルームコードです。'})
        return

    join_room(sid)
    game = init_game_state(room_code)

    success = game.add_player(sid, player_name)
    if not success:
        emit('error_message', {'message': 'ルームに参加できませんでした（満員または対戦中）。'})
        return

    broadcast_state(room_code)

@socketio.on('start_game')
def handle_start(data):
    room_code = data.get('room', '').upper()
    if room_code in rooms:
        game = rooms[room_code]
        success, msg = game.start_game()
        if success:
            broadcast_state(room_code)
        else:
            emit('error_message', {'message': msg})

@socketio.on('play_card')
def handle_play_card(data):
    room_code = data.get('room', '').upper()
    card_id = data.get('card_id')
    chosen_color = data.get('chosen_color')
    sid = request.sid

    if room_code in rooms:
        game = rooms[room_code]
        success, msg = game.play_card(sid, card_id, chosen_color)
        if success:
            broadcast_state(room_code)
        else:
            emit('error_message', {'message': msg})

@socketio.on('draw_card')
def handle_draw(data):
    room_code = data.get('room', '').upper()
    sid = request.sid

    if room_code in rooms:
        game = rooms[room_code]
        success, msg = game.player_draw_card(sid)
        if success:
            broadcast_state(room_code)
        else:
            emit('error_message', {'message': msg})

@socketio.on('pass_turn')
def handle_pass(data):
    room_code = data.get('room', '').upper()
    sid = request.sid

    if room_code in rooms:
        game = rooms[room_code]
        success, msg = game.player_pass(sid)
        if success:
            broadcast_state(room_code)
        else:
            emit('error_message', {'message': msg})

@socketio.on('call_uno')
def handle_uno(data):
    room_code = data.get('room', '').upper()
    sid = request.sid

    if room_code in rooms:
        game = rooms[room_code]
        game.call_uno(sid)
        broadcast_state(room_code)

@socketio.on('catch_uno')
def handle_catch_uno(data):
    room_code = data.get('room', '').upper()
    target_name = data.get('target_name')

    if room_code in rooms:
        game = rooms[room_code]
        game.catch_uno_penalty(target_name)
        broadcast_state(room_code)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    for room_code, game in list(rooms.items()):
        player = next((p for p in game.players if p['id'] == sid), None)
        if player:
            game.remove_player(sid)
            if len(game.players) == 0:
                del rooms[room_code]
            else:
                broadcast_state(room_code)
            break
