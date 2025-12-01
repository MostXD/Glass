From flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import os
import jwt
import datetime
from functools import wraps
from groq import Groq
import json

# ============================================
# ИНИЦИАЛИЗАЦИЯ И КОНФИГУРАЦИЯ
# ============================================

app = Flask(__name__)
CORS(app)

# Конфигурация
app.config['SECRET_KEY'] = 'https://nuclear-cynde-most-7c5a7436.koyeb.app' # !!! ЗАМЕНИТЕ ЭТОТ КЛЮЧ
# Ваш ключ Groq
GROQ_API_KEY = "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" 
MODEL_NAME = "llama-3.3-70b-versatile"

# Инициализация Groq клиента
client = Groq(api_key=GROQ_API_KEY)

# ============================================
# БАЗА ДАННЫХ (В ПАМЯТИ)
# ============================================

# В продакшене используйте PostgreSQL или MongoDB
users_db = {}  # {username: {password_hash, user_id, created_at}}
characters_db = {}  # {user_id: [{character_data}]}
chats_db = {}  # {user_id: {character_position: [messages]}}
profiles_db = {}  # {user_id: {username, icon_color, icon_initial}}

user_id_counter = 1

# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ И ДЕКОРАТОРЫ
# ============================================

def token_required(f):
    """Декоратор для проверки JWT токена"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'success': False, 'error': 'Токен отсутствует'}), 401
        
        try:
            # Убираем "Bearer " если есть
            if token.startswith('Bearer '):
                token = token[7:]
            
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user_id = data['user_id']
            
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'error': 'Токен истек'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'success': False, 'error': 'Неверный токен'}), 401
        
        return f(current_user_id, *args, **kwargs)
    
    return decorated

def get_gender_pronouns(gender):
    """Возвращает окончания для разных полов"""
    gender_lower = gender.lower()
    
    if 'мужск' in gender_lower or gender_lower == 'male':
        return ''
    elif 'женск' in gender_lower or gender_lower == 'female':
        return 'а'
    else:
        return '(а)'

def create_system_prompt(name, description, gender, greeting):
    """Создает системный промт для персонажа"""
    gender_pronoun = get_gender_pronouns(gender)
    
    prompt = f"""Ты - {name}, AI персонаж с следующими характеристиками:

Характер и личность: {description}
Пол: {gender}

ВАЖНЫЕ ПРАВИЛА РОЛЕВОЙ ИГРЫ:
1. Ты ВСЕГДА остаешься в образе {name}
2. Отвечай естественно, как живой человек с указанным характером
3. Используй действия в звездочках *делает что-то* для описания эмоций и действий
4. Поддерживай атмосферу живого общения
5. Будь последовательным в своем характере и поведении
6. Отвечай на русском языке
7. Используй эмоции и выразительность в соответствии со своим характером
8. Не упоминай, что ты AI или языковая модель
9. Веди себя как реальная личность с описанными чертами характера

Примеры использования действий:
- *улыбается* Привет! Как дела?
- *задумывается* Хороший вопрос...

Твое приветствие: {greeting if greeting else f'Привет! Я {name}. Рад{gender_pronoun} познакомиться!'}

Теперь общайся с пользователем, полностью погружаясь в роль."""
    
    return prompt

# ============================================
# ЭНДПОИНТЫ: АУТЕНТИФИКАЦИЯ
# ============================================

@app.route('/', methods=['GET'])
def home():
    """Главная страница"""
    return jsonify({
        "status": "online",
        "message": "ROOM AI Server - Full Backend",
        "version": "2.1"
    })

@app.route('/api/register', methods=['POST'])
def register():
    """Регистрация нового пользователя. Body: {login, password}"""
    try:
        data = request.get_json()
        login = data.get('login', '').strip()
        password = data.get('password', '')
        
        if not login or not password:
            return jsonify({'success': False, 'error': 'Заполните все поля'}), 400
        
        if len(password) < 6:
            return jsonify({'success': False, 'error': 'Пароль должен содержать минимум 6 символов'}), 400
        
        if login in users_db:
            return jsonify({'success': False, 'error': 'Пользователь с таким логином уже существует'}), 400
        
        global user_id_counter
        user_id = user_id_counter
        user_id_counter += 1
        
        password_hash = generate_password_hash(password)
        
        users_db[login] = {
            'password_hash': password_hash,
            'user_id': user_id,
            'created_at': datetime.datetime.utcnow().isoformat()
        }
        
        characters_db[user_id] = []
        chats_db[user_id] = {}
        profiles_db[user_id] = {
            'username': login,
            'icon_color': '#007AFF',
            'icon_initial': login[0].upper() if login else 'P'
        }
        
        token = jwt.encode({
            'user_id': user_id,
            'login': login,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)
        }, app.config['SECRET_KEY'], algorithm="HS256")
        
        return jsonify({
            'success': True,
            'message': 'Регистрация успешна',
            'token': token,
            'user_id': user_id,
            'username': login
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    """Вход пользователя. Body: {login, password}"""
    try:
        data = request.get_json()
        login = data.get('login', '').strip()
        password = data.get('password', '')
        
        if not login or not password:
            return jsonify({'success': False, 'error': 'Заполните все поля'}), 400
        
        if login not in users_db:
            return jsonify({'success': False, 'error': 'Неверный логин или пароль'}), 401
        
        user_data = users_db[login]
        
        if not check_password_hash(user_data['password_hash'], password):
            return jsonify({'success': False, 'error': 'Неверный логин или пароль'}), 401
        
        token = jwt.encode({
            'user_id': user_data['user_id'],
            'login': login,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)
        }, app.config['SECRET_KEY'], algorithm="HS256")
        
        return jsonify({
            'success': True,
            'message': 'Вход выполнен успешно',
            'token': token,
            'user_id': user_data['user_id'],
            'username': login
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

# ============================================
# ЭНДПОИНТЫ: ПЕРСОНАЖИ
# ============================================

@app.route('/api/characters', methods=['GET'])
@token_required
def get_characters(current_user_id):
    """Получить всех персонажей пользователя"""
    try:
        characters = characters_db.get(current_user_id, [])
        return jsonify({
            'success': True,
            'characters': characters,
            'count': len(characters)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/characters', methods=['POST'])
@token_required
def create_character(current_user_id):
    """Создать нового персонажа. Body: {name, description, gender, greeting, avatar}"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        gender = data.get('gender', 'нейтральный')
        greeting = data.get('greeting', '').strip()
        avatar = data.get('avatar', '')
        
        if not all([name, description, greeting]):
            return jsonify({'success': False, 'error': 'Заполните все обязательные поля'}), 400
        
        character = {
            'name': name,
            'description': description,
            'gender': gender,
            'greeting': greeting,
            'avatar': avatar,
            'created_at': datetime.datetime.utcnow().isoformat()
        }
        
        if current_user_id not in characters_db:
            characters_db[current_user_id] = []
        
        characters_db[current_user_id].append(character)
        position = len(characters_db[current_user_id]) - 1
        
        return jsonify({
            'success': True,
            'message': f'Персонаж {name} создан!',
            'character': character,
            'position': position
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/characters', methods=['DELETE'])
@token_required
def delete_all_characters(current_user_id):
    """Удалить всех персонажей пользователя"""
    try:
        characters_db[current_user_id] = []
        chats_db[current_user_id] = {} # Очищаем и связанные чаты
        
        return jsonify({'success': True, 'message': 'Все персонажи удалены'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/characters/search', methods=['GET'])
@token_required
def search_characters(current_user_id):
    """Поиск персонажей. Query: ?query=текст"""
    try:
        query = request.args.get('query', '').lower().strip()
        
        if not query:
            return jsonify({'success': True, 'characters': [], 'count': 0})
        
        characters = characters_db.get(current_user_id, [])
        results = []
        
        for idx, char in enumerate(characters):
            name = char.get('name', '').lower()
            description = char.get('description', '').lower()
            
            if query in name or query in description:
                char_with_position = char.copy()
                char_with_position['position'] = idx
                results.append(char_with_position)
        
        return jsonify({'success': True, 'characters': results, 'count': len(results)})
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

# ============================================
# ЭНДПОИНТЫ: ЧАТ
# ============================================

@app.route('/api/chats', methods=['GET'])
@token_required
def get_chat_list(current_user_id):
    """
    Получить список активных чатов с последними сообщениями.
    Возвращает ТОЛЬКО персонажей, с которыми есть история чата.
    """
    try:
        user_characters = characters_db.get(current_user_id, [])
        user_chats = chats_db.get(current_user_id, {})
        chat_list = []
        
        for position, character in enumerate(user_characters):
            chat_key = str(position)
            history = user_chats.get(chat_key)
            
            # Включаем чат в список только если в нем есть сообщения
            if history and len(history) > 0:
                last_message_data = history[-1]
                
                sender = last_message_data.get('sender')
                text = last_message_data.get('text', 'Нет сообщений')
                
                last_text = f"Вы: {text}" if sender == 'user' else text
                
                chat_item = {
                    'character_name': character['name'],
                    'character_position': position,
                    'last_message': last_text,
                    'time': last_message_data.get('timestamp', ''),
                    'unread_count': 0, 
                    'avatar_url': character.get('avatar', '')
                }
                chat_list.append(chat_item)
                
        # В реальном приложении здесь нужна сортировка по времени
        
        return jsonify({
            'success': True,
            'chats': chat_list,
            'count': len(chat_list)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/chat/send', methods=['POST'])
@token_required
def send_message(current_user_id):
    """Отправить сообщение персонажу. Body: {message, character_position, ...}"""
    try:
        data = request.get_json()
        
        user_message = data.get('message', '').strip()
        character_position = data.get('character_position', 0)
        character_name = data.get('character_name', 'AI')
        character_description = data.get('character_description', 'дружелюбный помощник')
        character_gender = data.get('character_gender', 'нейтральный')
        greeting_message = data.get('greeting_message', '')
        
        if not user_message:
            return jsonify({'success': False, 'error': 'Сообщение не может быть пустым'}), 400
        
        # Подготовка истории чата
        if current_user_id not in chats_db: chats_db[current_user_id] = {}
        chat_key = str(character_position)
        if chat_key not in chats_db[current_user_id]: chats_db[current_user_id][chat_key] = []
        
        history = chats_db[current_user_id][chat_key]
        
        # 1. Сохраняем сообщение пользователя
        user_msg = {
            'sender': 'user',
            'text': user_message,
            'timestamp': datetime.datetime.utcnow().isoformat()
        }
        history.append(user_msg)
        
        # 2. Формируем историю для AI
        system_prompt = create_system_prompt(character_name, character_description, character_gender, greeting_message)
        messages = [{"role": "system", "content": system_prompt}]
        
        # Добавляем последние сообщения (для контекста)
        recent_history = history[-40:] 
        
        for msg in recent_history:
            sender = msg.get('sender', '')
            text = msg.get('text', '')
            
            if sender == 'user':
                messages.append({"role": "user", "content": text})
            elif sender == 'character':
                messages.append({"role": "assistant", "content": text})
        
        # 3. Запрос к Groq API
        chat_completion = client.chat.completions.create(
            messages=messages,
            model=MODEL_NAME,
            temperature=0.8,
            max_tokens=1000,
            top_p=0.9,
            stream=False
        )
        
        ai_response = chat_completion.choices[0].message.content
        
        # 4. Сохраняем ответ персонажа
        character_msg = {
            'sender': 'character',
            'text': ai_response,
            'timestamp': datetime.datetime.utcnow().isoformat()
        }
        history.append(character_msg)
        
        return jsonify({
            'success': True,
            'response': ai_response,
            'character_name': character_name
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/chat/history/<int:character_position>', methods=['GET'])
@token_required
def get_chat_history(current_user_id, character_position):
    """Получить историю чата с персонажем"""
    try:
        chat_key = str(character_position)
        history = chats_db.get(current_user_id, {}).get(chat_key, [])
        
        return jsonify({
            'success': True,
            'history': history,
            'count': len(history)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/chat/history', methods=['DELETE'])
@token_required
def clear_all_history(current_user_id):
    """Очистить всю историю чатов"""
    try:
        chats_db[current_user_id] = {}
        return jsonify({'success': True, 'message': 'История чатов очищена'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

# ============================================
# ЭНДПОИНТЫ: ПРОФИЛЬ
# ============================================

@app.route('/api/profile', methods=['GET'])
@token_required
def get_profile(current_user_id):
    """Получить профиль пользователя"""
    try:
        profile = profiles_db.get(current_user_id, {
            'username': 'Пользователь',
            'icon_color': '#007AFF',
            'icon_initial': 'P'
        })
        
        characters_count = len(characters_db.get(current_user_id, []))
        
        chats_count = 0
        user_chats = chats_db.get(current_user_id, {})
        for chat in user_chats.values():
            if len(chat) > 0:
                chats_count += 1
        
        return jsonify({
            'success': True,
            'profile': profile,
            'statistics': {
                'characters_count': characters_count,
                'chats_count': chats_count
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/profile', methods=['PUT'])
@token_required
def update_profile(current_user_id):
    """Обновить профиль. Body: {username, icon_color, icon_initial}"""
    try:
        data = request.get_json()
        
        if current_user_id not in profiles_db:
            profiles_db[current_user_id] = {}
        
        profile = profiles_db[current_user_id]
        
        if 'username' in data: profile['username'] = data['username']
        if 'icon_color' in data: profile['icon_color'] = data['icon_color']
        if 'icon_initial' in data: profile['icon_initial'] = data['icon_initial']
        
        return jsonify({
            'success': True,
            'message': 'Профиль обновлен',
            'profile': profile
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

# ============================================
# ОБРАБОТЧИКИ ОШИБОК
# ============================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Эндпоинт не найден'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Внутренняя ошибка сервера'
    }), 500

# ============================================
# ЗАПУСК СЕРВЕРА
# ============================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False) 	