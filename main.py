from flask import Flask, request, jsonify
from flask_cors import CORS
import hashlib

app = Flask(__name__)
CORS(app)

# Хранилище пользователей
users = {}

def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "ok",
        "message": "GLASS AI Server Running"
    }), 200

@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Некорректные данные"}), 400
        
        login = data.get('login', '').strip()
        password = data.get('password', '').strip()
        
        if not login or len(login) < 3:
            return jsonify({"error": "Логин должен содержать минимум 3 символа"}), 400
        
        if not password or len(password) < 6:
            return jsonify({"error": "Пароль должен содержать минимум 6 символов"}), 400
        
        if login in users:
            return jsonify({"error": "Пользователь уже существует"}), 409
        
        users[login] = {
            'login': login,
            'password_hash': hash_password(password)
        }
        
        return jsonify({
            "success": True,
            "message": "Регистрация успешна",
            "user": {"login": login}
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Некорректные данные"}), 400
        
        login = data.get('login', '').strip()
        password = data.get('password', '').strip()
        
        if login not in users:
            return jsonify({"error": "Неверный логин или пароль"}), 401
        
        password_hash = hash_password(password)
        if users[login]['password_hash'] != password_hash:
            return jsonify({"error": "Неверный логин или пароль"}), 401
        
        return jsonify({
            "success": True,
            "message": "Вход выполнен успешно",
            "user": {"login": login}
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)