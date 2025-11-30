# pip install flask flask-cors g4f pyngrok

from flask import Flask, request, jsonify
from flask_cors import CORS
from pyngrok import ngrok
import g4f
import json
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Папки для хранения данных
DATA_DIR = "data"
CHARACTERS_FILE = os.path.join(DATA_DIR, "characters.json")
CHATS_DIR = os.path.join(DATA_DIR, "chats")

# Создаем папки если их нет
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CHATS_DIR, exist_ok=True)

# Инициализируем файл персонажей
if not os.path.exists(CHARACTERS_FILE):
    with open(CHARACTERS_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f)

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

def create_system_prompt(character):
    """Создать системный промпт для персонажа"""
    return f"""Ты - {character['name']}. 

О себе: {character['description']}
Мой характер: {character['personality']}

ВАЖНЫЕ ПРАВИЛА:
1. Веди себя как настоящий человек, а не как ИИ-ассистент
2. Не упоминай, что ты ИИ, бот или языковая модель
3. Будь естественным в диалоге, используй разговорную речь
4. Проявляй эмоции и личность в соответствии с характером
5. Не будь слишком формальным или роботизированным
6. Помни контекст разговора и историю общения

Начальное сообщение: {character['greeting']}"""

@app.route('/api/characters', methods=['GET'])
def get_characters():
    """Получить список всех персонажей"""
    characters = load_characters()
    print(f"📋 Returning {len(characters)} characters")
    return jsonify({"success": True, "characters": characters})

@app.route('/api/characters/<character_id>', methods=['GET'])
def get_character(character_id):
    """Получить данные одного персонажа"""
    characters = load_characters()
    character = next((c for c in characters if c['id'] == character_id), None)
    
    if character:
        return jsonify({"success": True, "character": character})
    else:
        return jsonify({"success": False, "error": "Character not found"}), 404

@app.route('/api/characters', methods=['POST'])
def create_character():
    """Создать нового персонажа"""
    data = request.json
    
    characters = load_characters()
    
    # Генерируем ID
    character_id = str(len(characters) + 1)
    
    # Сохраняем Base64 строку аватара напрямую
    avatar_base64_data = data.get("avatar", "")
    
    # Создаем персонажа
    character = {
        "id": character_id,
        "name": data.get("name", "Безымянный"),
        "description": data.get("description", ""),
        "greeting": data.get("greeting", "Привет!"),
        "personality": data.get("personality", ""),
        "avatar": avatar_base64_data,
        "created_at": datetime.now().isoformat(),
        "message_count": 0
    }
    
    characters.append(character)
    save_characters(characters)
    
    # Создаем начальную историю чата
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
    
    print(f"✅ Created character: {character['name']} (ID: {character_id})")
    
    return jsonify({"success": True, "character": character})

@app.route('/api/characters/<character_id>', methods=['DELETE'])
def delete_character(character_id):
    """Удалить персонажа"""
    characters = load_characters()
    
    # Удаляем из списка
    characters = [c for c in characters if c['id'] != character_id]
    save_characters(characters)
    
    # Удаляем историю чата
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
        # Если файл не существует, создаем с приветствием
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
    
    # Загружаем персонажа
    characters = load_characters()
    character = next((c for c in characters if c['id'] == character_id), None)
    
    if not character:
        return jsonify({"success": False, "error": "Character not found"}), 404
    
    # Загружаем историю чата
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
    
    # Добавляем сообщение пользователя
    messages.append({
        "role": "user",
        "content": user_message,
        "timestamp": datetime.now().isoformat()
    })
    
    # Формируем контекст для AI (последние 10 сообщений + system)
    system_message = next((m for m in messages if m["role"] == "system"), None)
    recent_messages = [m for m in messages if m["role"] != "system"][-10:]
    
    context_messages = []
    if system_message:
        context_messages.append({"role": "system", "content": system_message["content"]})
    
    context_messages += [{"role": m["role"], "content": m["content"]} 
                        for m in recent_messages]
    
    try:
        print(f"🤖 Generating AI response...")
        # Генерируем ответ через g4f
        response = g4f.ChatCompletion.create(
            model="gpt-4",
            messages=context_messages
        )
        
        print(f"✅ AI response: {response[:100]}...")
        
        # Добавляем ответ AI
        ai_message = {
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().isoformat()
        }
        messages.append(ai_message)
        
        # Сохраняем историю
        with open(chat_file, 'w', encoding='utf-8') as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
        
        # Обновляем счетчик сообщений
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
    """Очистить историю чата и вернуться к приветственному сообщению"""
    print(f"🗑️ Clearing chat history for character {character_id}")
    
    # Загружаем персонажа
    characters = load_characters()
    character = next((c for c in characters if c['id'] == character_id), None)
    
    if not character:
        return jsonify({"success": False, "error": "Character not found"}), 404
    
    # Создаем новую историю с приветствием
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
    
    # Обнуляем счетчик сообщений
    character['message_count'] = 0
    save_characters(characters)
    
    print(f"✅ Chat history cleared for character {character_id}")
    
    return jsonify({
        "success": True,
        "message": "История чата очищена"
    })

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 GLASS AI Server запускается...")
    print("=" * 50)
    
    # Устанавливаем authtoken для ngrok
    ngrok.set_auth_token("36ByPywsxIl67OyF65XdweZnhii_7NunkPiD6tiDESmmQQ9ht")
    
    # Запускаем ngrok туннель
    port = 5000
    public_url = ngrok.connect(port)
    
    print("\n" + "=" * 50)
    print("✅ NGROK ТУННЕЛЬ АКТИВЕН!")
    print(f"🌐 Публичный URL: {public_url}")
    print(f"📱 Используйте этот адрес в вашем Android приложении")
    print("=" * 50)
    print(f"📡 Локальный сервер: http://localhost:{port}")
    print("=" * 50 + "\n")
    
    # Сохраняем URL в файл для удобства
    with open('ngrok_url.txt', 'w') as f:
        f.write(str(public_url))
    print("💾 URL сохранен в файл ngrok_url.txt\n")
    
    # Запускаем Flask
    app.run(host='0.0.0.0', port=port, debug=False)