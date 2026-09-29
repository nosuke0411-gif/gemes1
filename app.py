import os
from flask import Flask
from flask_login import LoginManager
from db import get_user_by_id

from routes.main import main_bp
from routes.auth import auth_bp
from routes.highlow import highlow_bp
from routes.revive import revive_bp
from routes.ranking import ranking_bp
from routes.transfer import transfer_bp

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "secret_key_here")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"

@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(user_id)

# ブループリントの登録
app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(highlow_bp)
app.register_blueprint(revive_bp)
app.register_blueprint(ranking_bp)
app.register_blueprint(transfer_bp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
