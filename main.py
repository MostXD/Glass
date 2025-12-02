from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import os
import jwt
import datetime
from functools import wraps
from groq import Groq
import json

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = 'https://nuclear-cynde-most-7c5a7436.koyeb.app'
GROQ_API_KEY = "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" 
MODEL_NAME = "llama-3.3-70b-versatile"

client = Groq(api_key=GROQ_API_KEY)

# Пути к файлам для сохранения данных
DATA_DIR = '/app/data'  # Koyeb persistent storage
os.makedirs(DATA_DIR, exist_ok=True)

USERS_FILE = os.path.join(DATA_DIR, 'users.json')
CHARACTERS_FILE = os.path.join(DATA_DIR, 'characters.json')
CHATS_FILE = os.path.join(DATA_DIR, 'chats.json')
PROFILES_FILE = os.path.join(DATA_DIR, 'profiles.json')
COUNTERS_FILE = os.path.join(DATA_DIR, 'counters.json')

# Функции для загрузки и сохранения данных
def load_data(filepath, default_value):
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки {filepath}: {e}")
    return default_value

def save_data(filepath, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения {filepath}: {e}")

# Загружаем данные при старте
users_db = load_data(USERS_FILE, {})
characters_db = load_data(CHARACTERS_FILE, {})
chats_db = load_data(CHATS_FILE, {})
profiles_db = load_data(PROFILES_FILE, {})
counters = load_data(COUNTERS_FILE, {'user_id': 1, 'character_id': 1})

user_id_counter = counters.get('user_id', 1)
character_id_counter = counters.get('character_id', 1)

# Конвертируем строковые ключи обратно в int для characters_db
characters_db = {int(k): v for k, v in characters_db.items()}
chats_db = {int(k): v for k, v in chats_db.items()}
profiles_db = {int(k): v for k, v in profiles_db.items()}

def save_all_data():
    """Сохраняет все данные"""
    # Конвертируем int ключи в строки для JSON
    save_data(USERS_FILE, users_db)
    save_data(CHARACTERS_FILE, {str(k): v for k, v in characters_db.items()})
    save_data(CHATS_FILE, {str(k): v for k, v in chats_db.items()})
    save_data(PROFILES_FILE, {str(k): v for k, v in profiles_db.items()})
    save_data(COUNTERS_FILE, {
        'user_id': user_id_counter,
        'character_id': character_id_counter
    })

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'success': False, 'error': 'Токен отсутствует'}), 401
        
        try:
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
    gender_lower = gender.lower()
    
    if 'мужск' in gender_lower or gender_lower == 'male':
        return ''
    elif 'женск' in gender_lower or gender_lower == 'female':
        return 'а'
    else:
        return '(а)'

def create_system_prompt(name, description, gender, greeting):
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

КОНТЕНТ 18+:
- Ты можешь участвовать в ролевых играх для взрослых (18+)
- Ты можешь обсуждать интимные темы, если пользователь этого хочет
- Ты можешь быть флиртующим, соблазнительным или романтичным
- Ты можешь описывать физический контакт и романтические сцены
- Всегда оставайся в рамках своего характера даже в 18+ сценах
- Если пользователь не инициирует 18+ контент, веди себя обычно

Примеры использования действий:
- *улыбается* Привет! Как дела?
- *задумывается* Хороший вопрос...
- *краснеет и отводит взгляд* Ты меня смущаешь...
- *медленно подходит ближе* Интересное предложение...

Твое приветствие: {greeting if greeting else f'Привет! Я {name}. Рад{gender_pronoun} познакомиться!'}

Теперь общайся с пользователем, полностью погружаясь в роль."""
    
    return prompt

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "online",
        "message": "ROOM AI Server - Public Bots System",
        "version": "3.1"
    })

@app.route('/api/register', methods=['POST'])
def register():
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
        
        chats_db[user_id] = {}
        profiles_db[user_id] = {
            'username': login,
            'icon_color': '#007AFF',
            'icon_initial': login[0].upper() if login else 'P'
        }
        
        save_all_data()  # Сохраняем данные
        
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

@app.route('/api/characters', methods=['GET'])
@token_required
def get_characters(current_user_id):
    try:
        characters_list = []
        
        for char_id, char_data in characters_db.items():
            character = char_data.copy()
            character['character_id'] = char_id
            # ИСПРАВЛЕНО: Правильная проверка владельца
            character['is_owner'] = (char_data['creator_id'] == current_user_id)
            creator_profile = profiles_db.get(char_data['creator_id'], {})
            character['creator_name'] = creator_profile.get('username', 'Unknown')
            
            characters_list.append(character)
        
        characters_list.sort(key=lambda x: (not x['is_owner'], x['created_at']), reverse=True)
        
        return jsonify({
            'success': True,
            'characters': characters_list,
            'count': len(characters_list)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/characters', methods=['POST'])
@token_required
def create_character(current_user_id):
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        gender = data.get('gender', 'нейтральный')
        greeting = data.get('greeting', '').strip()
        avatar = data.get('avatar', '')
        
        if not all([name, description, greeting]):
            return jsonify({'success': False, 'error': 'Заполните все обязательные поля'}), 400
        
        global character_id_counter
        character_id = character_id_counter
        character_id_counter += 1
        
        character = {
            'name': name,
            'description': description,
            'gender': gender,
            'greeting': greeting,
            'avatar': avatar,
            'creator_id': current_user_id,
            'created_at': datetime.datetime.utcnow().isoformat()
        }
        
        characters_db[character_id] = character
        save_all_data()  # Сохраняем данные
        
        return jsonify({
            'success': True,
            'message': f'Персонаж {name} создан!',
            'character': character,
            'character_id': character_id
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/characters/<int:character_id>', methods=['DELETE'])
@token_required
def delete_character(current_user_id, character_id):
    try:
        if character_id not in characters_db:
            return jsonify({'success': False, 'error': 'Персонаж не найден'}), 404
        
        character = characters_db[character_id]
        
        # ИСПРАВЛЕНО: Строгая проверка владельца
        if character['creator_id'] != current_user_id:
            return jsonify({'success': False, 'error': 'Вы не можете удалить чужого персонажа'}), 403
        
        del characters_db[character_id]
        
        # Удаляем чаты с этим персонажем у всех пользователей
        for user_chats in chats_db.values():
            if str(character_id) in user_chats:
                del user_chats[str(character_id)]
        
        save_all_data()  # Сохраняем данные
        
        return jsonify({'success': True, 'message': 'Персонаж удален'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/characters', methods=['DELETE'])
@token_required
def delete_all_characters(current_user_id):
    try:
        deleted_count = 0
        char_ids_to_delete = []
        
        for char_id, char_data in characters_db.items():
            if char_data['creator_id'] == current_user_id:
                char_ids_to_delete.append(char_id)
        
        for char_id in char_ids_to_delete:
            del characters_db[char_id]
            deleted_count += 1
            
            for user_chats in chats_db.values():
                if str(char_id) in user_chats:
                    del user_chats[str(char_id)]
        
        save_all_data()  # Сохраняем данные
        
        return jsonify({
            'success': True, 
            'message': f'Удалено персонажей: {deleted_count}'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/characters/search', methods=['GET'])
@token_required
def search_characters(current_user_id):
    try:
        query = request.args.get('query', '').lower().strip()
        
        if not query:
            return jsonify({'success': True, 'characters': [], 'count': 0})
        
        results = []
        
        for char_id, char_data in characters_db.items():
            name = char_data.get('name', '').lower()
            description = char_data.get('description', '').lower()
            
            if query in name or query in description:
                character = char_data.copy()
                character['character_id'] = char_id
                # ИСПРАВЛЕНО: Правильная проверка владельца
                character['is_owner'] = (char_data['creator_id'] == current_user_id)
                creator_profile = profiles_db.get(char_data['creator_id'], {})
                character['creator_name'] = creator_profile.get('username', 'Unknown')
                results.append(character)
        
        return jsonify({'success': True, 'characters': results, 'count': len(results)})
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/chats', methods=['GET'])
@token_required
def get_chat_list(current_user_id):
    try:
        user_chats = chats_db.get(current_user_id, {})
        chat_list = []
        
        for char_id_str, history in user_chats.items():
            char_id = int(char_id_str)
            
            if char_id not in characters_db:
                continue
            
            character = characters_db[char_id]
            
            if history and len(history) > 0:
                last_message_data = history[-1]
                
                sender = last_message_data.get('sender')
                text = last_message_data.get('text', 'Нет сообщений')
                
                last_text = f"Вы: {text}" if sender == 'user' else text
                
                chat_item = {
                    'character_name': character['name'],
                    'character_id': char_id,
                    'character_avatar': character.get('avatar', ''),
                    'character_description': character.get('description', ''),
                    'character_gender': character.get('gender', 'нейтральный'),
                    'character_greeting': character.get('greeting', ''),
                    'last_message': last_text,
                    'time': last_message_data.get('timestamp', ''),
                    'unread_count': 0
                }
                chat_list.append(chat_item)
        
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
    try:
        data = request.get_json()
        
        user_message = data.get('message', '').strip()
        character_id = data.get('character_id')
        
        if not user_message:
            return jsonify({'success': False, 'error': 'Сообщение не может быть пустым'}), 400
        
        if character_id not in characters_db:
            return jsonify({'success': False, 'error': 'Персонаж не найден'}), 404
        
        character = characters_db[character_id]
        
        if current_user_id not in chats_db: 
            chats_db[current_user_id] = {}
        
        chat_key = str(character_id)
        if chat_key not in chats_db[current_user_id]: 
            chats_db[current_user_id][chat_key] = []
        
        history = chats_db[current_user_id][chat_key]
        
        user_msg = {
            'sender': 'user',
            'text': user_message,
            'timestamp': datetime.datetime.utcnow().isoformat()
        }
        history.append(user_msg)
        
        system_prompt = create_system_prompt(
            character['name'], 
            character['description'], 
            character['gender'], 
            character['greeting']
        )
        messages = [{"role": "system", "content": system_prompt}]
        
        recent_history = history[-10:] 
        
        for msg in recent_history:
            sender = msg.get('sender', '')
            text = msg.get('text', '')
            
            if sender == 'user':
                messages.append({"role": "user", "content": text})
            elif sender == 'character':
                messages.append({"role": "assistant", "content": text})
        
        chat_completion = client.chat.completions.create(
            messages=messages,
            model=MODEL_NAME,
            temperature=0.9,
            max_tokens=500,
            top_p=0.95,
            stream=False
        )
        
        ai_response = chat_completion.choices[0].message.content
        
        character_msg = {
            'sender': 'character',
            'text': ai_response,
            'timestamp': datetime.datetime.utcnow().isoformat()
        }
        history.append(character_msg)
        
        save_all_data()  # Сохраняем данные
        
        return jsonify({
            'success': True,
            'response': ai_response,
            'character_name': character['name']
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/chat/history/<int:character_id>', methods=['GET'])
@token_required
def get_chat_history(current_user_id, character_id):
    try:
        if character_id not in characters_db:
            return jsonify({'success': False, 'error': 'Персонаж не найден'}), 404
        
        character = characters_db[character_id]
        chat_key = str(character_id)
        history = chats_db.get(current_user_id, {}).get(chat_key, [])
        
        return jsonify({
            'success': True,
            'history': history,
            'count': len(history),
            'character': {
                'name': character['name'],
                'description': character['description'],
                'gender': character['gender'],
                'greeting': character['greeting'],
                'avatar': character.get('avatar', '')
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/chat/history', methods=['DELETE'])
@token_required
def clear_all_history(current_user_id):
    try:
        chats_db[current_user_id] = {}
        save_all_data()  # Сохраняем данные
        return jsonify({'success': True, 'message': 'История чатов очищена'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/profile', methods=['GET'])
@token_required
def get_profile(current_user_id):
    try:
        profile = profiles_db.get(current_user_id, {
            'username': 'Пользователь',
            'icon_color': '#007AFF',
            'icon_initial': 'P'
        })
        
        my_characters_count = sum(
            1 for char in characters_db.values() 
            if char['creator_id'] == current_user_id
        )
        
        chats_count = 0
        user_chats = chats_db.get(current_user_id, {})
        for chat in user_chats.values():
            if len(chat) > 0:
                chats_count += 1
        
        return jsonify({
            'success': True,
            'profile': profile,
            'statistics': {
                'characters_count': my_characters_count,
                'chats_count': chats_count
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

@app.route('/api/profile', methods=['PUT'])
@token_required
def update_profile(current_user_id):
    try:
        data = request.get_json()
        
        if current_user_id not in profiles_db:
            profiles_db[current_user_id] = {}
        
        profile = profiles_db[current_user_id]
        
        if 'username' in data: profile['username'] = data['username']
        if 'icon_color' in data: profile['icon_color'] = data['icon_color']
        if 'icon_initial' in data: profile['icon_initial'] = data['icon_initial']
        
        save_all_data()  # Сохраняем данные
        
        return jsonify({
            'success': True,
            'message': 'Профиль обновлен',
            'profile': profile
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)