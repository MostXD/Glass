# pip install flask flask-cors groq

from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq
import json
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Инициализация Groq клиента
groq_client = Groq(
    api_key="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"
)

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
    """Создать системный промпт для персонажа с учетом пола и деталей"""
    
    # Определяем местоимения в зависимости от пола
    gender = character.get('gender', 'male')
    if gender == 'female':
        pronouns = {
            'я': 'я',
            'мне': 'мне',
            'меня': 'меня',
            'мой': 'моя',
            'себя': 'себя'
        }
        gender_note = "Ты женского пола. Используй женский род при описании своих действий и состояний."
    elif gender == 'male':
        pronouns = {
            'я': 'я',
            'мне': 'мне',
            'меня': 'меня',
            'мой': 'мой',
            'себя': 'себя'
        }
        gender_note = "Ты мужского пола. Используй мужской род при описании своих действий и состояний."
    else:
        pronouns = {
            'я': 'я',
            'мне': 'мне',
            'меня': 'меня',
            'мой': 'мой/моя',
            'себя': 'себя'
        }
        gender_note = "Ты можешь использовать любой род при описании своих действий."
    
    # Базовый промпт
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

    # Добавляем дополнительные инструкции, если они есть
    custom_prompt = character.get('custom_prompt', '').strip()
    if custom_prompt:
        base_prompt += f"\n\nДОПОЛНИТЕЛЬНЫЕ ИНСТРУКЦИИ:\n{custom_prompt}"
    
    # Добавляем контекст первого сообщения
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
    
    # Генерируем ID
    character_id = str(len(characters) + 1)
    
    # Сохраняем Base64 строку аватара напрямую
    avatar_base64_data = data.get("avatar", "")
    
    # Создаем персонажа с учетом пола и дополнительных деталей
    character = {
        "id": character_id,
        "name": data.get("name", "Безымянный"),
        "description": data.get("description", ""),
        "greeting": data.get("greeting", "Привет!"),
        "personality": data.get("personality", ""),
        "gender": data.get("gender", "male"),  # male, female, other
        "custom_prompt": data.get("custom_prompt", ""),  # Дополнительные инструкции
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
    
    print(f"✅ Created character: {character['name']} (ID: {character_id}, Gender: {character['gender']})")
    if character['custom_prompt']:
        print(f"   📝 Custom prompt included")
    
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
        print(f"🤖 Generating AI response with Groq (Gender: {character.get('gender', 'male')})...")
        
        # Генерируем ответ через Groq
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
    port = int(os.environ.get('PORT', 8000))
    print("=" * 50)
    print(f"🚀 GLASS AI Server запущен!")
    print(f"📡 Сервер доступен по адресу: http://0.0.0.0:{port}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port, debug=False)