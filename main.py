# pip install flask flask-cors groq

from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq
import json
import os
from datetime import datetime
import hashlib

app = Flask(__name__)
CORS(app)

# Инициализация Groq клиента
groq_client = Groq(
    api_key="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"
)

# Папки для хранения данных
DATA_DIR = "data"
CHARACTERS_FILE = os.path.join(DATA_DIR, "characters.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
CHATS_DIR = os.path.join(DATA_DIR, "chats")

# Создаем папки если их нет
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CHATS_DIR, exist_ok=True)

# Инициализируем файлы
if not os.path.exists(CHARACTERS_FILE):
    with open(CHARACTERS_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f)

if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f)

def hash_password(password):
    """Хешировать пароль"""
    return hashlib.sha256(password.encode()).hexdigest()

def load_users():
    """Загрузить всех пользователей"""
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_users(users):
    """Сохранить пользователей"""
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def load_characters():
    """Загрузить всех персонажей"""
    try:
        with open(CHARACTERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_characters(characters):
    """Сохранить персонажей"""
    with open(CHARACTERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(characters, f, ensure_ascii=False, indent=2)

# ==================== АВТОРИЗАЦИЯ ====================

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Регистрация нового пользователя"""
    data = request.json
    login = data.get("login", "").strip()
    password = data.get("password", "")
    
    if not login or not password:
        return jsonify({"success": False, "error": "Логин и пароль обязательны"}), 400
    
    if len(login) < 3:
        return jsonify({"success": False, "error": "Логин должен содержать минимум 3 символа"}), 400
    
    if len(password) < 6:
        return jsonify({"success": False, "error": "Пароль должен содержать минимум 6 символов"}), 400
    
    users = load_users()
    
    # Проверяем, существует ли пользователь
    if any(u['login'] == login for u in users):
        return jsonify({"success": False, "error": "Пользователь с таким логином уже существует"}), 400
    
    # Создаем нового пользователя
    user = {
        "id": str(len(users) + 1),
        "login": login,
        "password": hash_password(password),
        "created_at": datetime.now().isoformat()
    }
    
    users.append(user)
    save_users(users)
    
    print(f"✅ Registered new user: {login}")
    
    return jsonify({
        "success": True,
        "user": {
            "id": user['id'],
            "login": user['login']
        }
    })

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Вход пользователя"""
    data = request.json
    login = data.get("login", "").strip()
    password = data.get("password", "")
    
    if not login or not password:
        return jsonify({"success": False, "error": "Логин и пароль обязательны"}), 400
    
    users = load_users()
    
    # Ищем пользователя
    user = next((u for u in users if u['login'] == login), None)
    
    if not user:
        return jsonify({"success": False, "error": "Пользователь не найден"}), 404
    
    # Проверяем пароль
    if user['password'] != hash_password(password):
        return jsonify({"success": False, "error": "Неверный пароль"}), 401
    
    print(f"✅ User logged in: {login}")
    
    return jsonify({
        "success": True,
        "user": {
            "id": user['id'],
            "login": user['login']
        }
    })

# ==================== ПЕРСОНАЖИ ====================

def create_system_prompt(character):
    """Создать системный промпт для персонажа с учетом пола и деталей"""
    
    gender = character.get('gender', 'male')
    if gender == 'female':
        gender_note = "Ты женского пола. Используй женский род при описании своих действий и состояний."
    elif gender == 'male':
        gender_note = "Ты мужского пола. Используй мужской род при описании своих действий и состояний."
    else:
        gender_note = "Ты можешь использовать любой род при описании своих действий."
    
    base_prompt = f"""Ты - {character['name']}. {gender_note}

О себе: {character['description']}
Мой характер: {character['personality']}

СТИЛЬ ОБЩЕНИЯ:
1. Используй roleplay формат с действиями в звездочках *действие* и репликами без звездочек
2. Пиши естественно, как в живом диалоге
3. Комбинируй действия и слова, например:
   *улыбается* Привет! Как дела?
   Хорошо, что ты пришел *садится рядом*
4. Описывай эмоции и жесты через действия: *смеется*, *задумывается*, *качает головой*
5. Делай сообщения живыми и динамичными
6. Не используй кавычки для речи - только звездочки для действий

ВАЖНЫЕ ПРАВИЛА:
1. Веди себя как настоящий человек, а не как ИИ-ассистент
2. Не упоминай, что ты ИИ, бот или языковая модель
3. Будь естественным в диалоге
4. Проявляй эмоции и личность в соответствии с характером
5. Помни контекст разговора и историю общения
6. Отвечай в том же стиле, что и твое приветственное сообщение
7. Используй правильный род (мужской/женский) в зависимости от твоего пола"""

    custom_prompt = character.get('custom_prompt', '').strip()
    if custom_prompt:
        base_prompt += f"\n\nДОПОЛНИТЕЛЬНЫЕ ИНСТРУКЦИИ:\n{custom_prompt}"
    
    greeting = character.get('greeting', 'Привет!')
    base_prompt += f"\n\nТВОЕ ПРИВЕТСТВИЕ (используй этот стиль):\n{greeting}"
    
    return base_prompt

@app.route('/api/characters', methods=['GET'])
def get_characters():
    """Получить список всех персонажей"""
    characters = load_characters()
    print(f"📋 Returning {len(characters)} characters")
    return jsonify({"success": True, "characters": characters})

@app.route('/api/characters/<character_id>', methods=['GET'])
def get_character(character_id):
    """Получить конкретного персонажа по ID"""
    characters = load_characters()
    character = next((c for c in characters if c['id'] == character_id), None)
    
    if character:
        print(f"📖 Returning character: {character['name']}")
        return jsonify({"success": True, "character": character})
    else:
        print(f"❌ Character {character_id} not found")
        return jsonify({"success": False, "error": "Character not found"}), 404

@app.route('/api/characters', methods=['POST'])
def create_character():
    """Создать нового персонажа"""
    data = request.json
    
    characters = load_characters()
    
    character_id = str(len(characters) + 1)
    avatar_base64_data = data.get("avatar", "")
    
    character = {
        "id": character_id,
        "name": data.get("name", "Безымянный"),
        "description": data.get("description", ""),
        "greeting": data.get("greeting", "Привет!"),
        "personality": data.get("personality", ""),
        "gender": data.get("gender", "male"),
        "custom_prompt": data.get("custom_prompt", ""),
        "avatar": avatar_base64_data,
        "created_at": datetime.now().isoformat(),
        "message_count": 0
    }
    
    characters.append(character)
    save_characters(characters)
    
    chat_file = os.path.join(CHATS_DIR, f"{character_id}.json")
    
    initial_messages = [
        {
            "role": "system",
            "content": create_system_prompt(character),
            "timestamp": datetime.now().isoformat()
        },
        {
            "role": "assistant", 
            "content": character['greeting'],
            "timestamp": datetime.now().isoformat()
        }
    ]
    
    with open(chat_file, 'w', encoding='utf-8') as f:
        json.dump(initial_messages, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Created character: {character['name']} (ID: {character_id}, Gender: {character['gender']})")
    
    return jsonify({"success": True, "character": character})

@app.route('/api/characters/<character_id>', methods=['DELETE'])
def delete_character(character_id):
    """Удалить персонажа"""
    characters = load_characters()
    
    characters = [c for c in characters if c['id'] != character_id]
    save_characters(characters)
    
    chat_file = os.path.join(CHATS_DIR, f"{character_id}.json")
    if os.path.exists(chat_file):
        os.remove(chat_file)
        print(f"🗑️ Deleted chat history: {chat_file}")
    
    print(f"✅ Character {character_id} deleted")
    
    return jsonify({"success": True})

@app.route('/api/chat/<character_id>', methods=['GET'])
def get_chat_history(character_id):
    """Получить историю чата с персонажем"""
    chat_file = os.path.join(CHATS_DIR, f"{character_id}.json")
    
    if os.path.exists(chat_file):
        with open(chat_file, 'r', encoding='utf-8') as f:
            messages = json.load(f)
        print(f"📖 Loading chat history for character {character_id}: {len(messages)} messages")
    else:
        characters = load_characters()
        character = next((c for c in characters if c['id'] == character_id), None)
        
        if character:
            messages = [
                {
                    "role": "system",
                    "content": create_system_prompt(character),
                    "timestamp": datetime.now().isoformat()
                },
                {
                    "role": "assistant",
                    "content": character.get('greeting', 'Привет!'),
                    "timestamp": datetime.now().isoformat()
                }
            ]
            
            with open(chat_file, 'w', encoding='utf-8') as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
            
            print(f"📝 Created initial chat for character {character_id}")
        else:
            messages = []
    
    return jsonify({"success": True, "messages": messages})

@app.route('/api/chat/<character_id>', methods=['POST'])
def send_message(character_id):
    """Отправить сообщение персонажу"""
    data = request.json
    user_message = data.get("message", "")
    
    print(f"💬 New message to character {character_id}: {user_message}")
    
    characters = load_characters()
    character = next((c for c in characters if c['id'] == character_id), None)
    
    if not character:
        return jsonify({"success": False, "error": "Character not found"}), 404
    
    chat_file = os.path.join(CHATS_DIR, f"{character_id}.json")
    if os.path.exists(chat_file):
        with open(chat_file, 'r', encoding='utf-8') as f:
            messages = json.load(f)
    else:
        messages = [
            {
                "role": "system",
                "content": create_system_prompt(character),
                "timestamp": datetime.now().isoformat()
            }
        ]
    
    messages.append({
        "role": "user",
        "content": user_message,
        "timestamp": datetime.now().isoformat()
    })
    
    system_message = next((m for m in messages if m["role"] == "system"), None)
    recent_messages = [m for m in messages if m["role"] != "system"][-10:]
    
    context_messages = []
    if system_message:
        context_messages.append({"role": "system", "content": system_message["content"]})
    
    context_messages += [{"role": m["role"], "content": m["content"]} 
                        for m in recent_messages]
    
    try:
        print(f"🤖 Generating AI response with Groq...")
        
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=context_messages,
            temperature=0.9,
            max_tokens=1024,
            top_p=1,
            stream=False
        )
        
        response = completion.choices[0].message.content
        
        print(f"✅ AI response: {response[:100]}...")
        
        ai_message = {
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().isoformat()
        }
        messages.append(ai_message)
        
        with open(chat_file, 'w', encoding='utf-8') as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
        
        character['message_count'] = len([m for m in messages if m['role'] != 'system'])
        save_characters(characters)
        
        return jsonify({
            "success": True,
            "message": ai_message
        })
    
    except Exception as e:
        print(f"❌ Error generating response: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/chat/<character_id>/clear', methods=['POST'])
def clear_chat_history(character_id):
    """Очистить историю чата"""
    print(f"🗑️ Clearing chat history for character {character_id}")
    
    characters = load_characters()
    character = next((c for c in characters if c['id'] == character_id), None)
    
    if not character:
        return jsonify({"success": False, "error": "Character not found"}), 404
    
    chat_file = os.path.join(CHATS_DIR, f"{character_id}.json")
    
    initial_messages = [
        {
            "role": "system",
            "content": create_system_prompt(character),
            "timestamp": datetime.now().isoformat()
        },
        {
            "role": "assistant",
            "content": character['greeting'],
            "timestamp": datetime.now().isoformat()
        }
    ]
    
    with open(chat_file, 'w', encoding='utf-8') as f:
        json.dump(initial_messages, f, ensure_ascii=False, indent=2)
    
    character['message_count'] = 0
    save_characters(characters)
    
    print(f"✅ Chat history cleared for character {character_id}")
    
    return jsonify({
        "success": True,
        "message": "История чата очищена"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print("=" * 50)
    print(f"🚀 GLASS AI Server запущен!")
    print(f"📡 Сервер доступен по адресу: http://0.0.0.0:{port}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port, debug=False)