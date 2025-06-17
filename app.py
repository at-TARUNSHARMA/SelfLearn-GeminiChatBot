from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import os
import json
from datetime import datetime
import aiofiles
import asyncio
import threading

# Replace this with your actual API key
API_KEY = "AIzaSyBexDHNUDSZwUw1jA_QFK-aDVwl-dNZpVY"
HISTORY_FILE = "conversation_history.json"
CHAT_ENHANCER_FILE = "chat_enhancer_file.json"

genai.configure(api_key=API_KEY)

app = Flask(__name__)

# Start a chat session
model = genai.GenerativeModel('gemini-2.0-flash-lite')
chat = model.start_chat(history=[])


@app.route('/')
def index():
    return render_template('index.html')


async def run_startup_message():
    prepend_line = "Summarize this conversation and provide me with data related to the product or RightWave in short."
    async with aiofiles.open(CHAT_ENHANCER_FILE, 'r', encoding='utf-8') as msg_file:
        original_content = await msg_file.read()
    # Prepare new content with prepend
    startup_message = f"{prepend_line}\n{original_content.strip()}"
    # Replace this with actual call to your model or API
    response = chat.send_message(startup_message)
    entry = {
        "timestamp": "0000-00-00T00:00:00.000000",
        "user_message": "summary for history",
        "bot_response": response.text
    }
    try:
        async with aiofiles.open(CHAT_ENHANCER_FILE, 'w', encoding='utf-8') as f:
            await f.truncate(0)  # Explicitly clear content
            await f.write(json.dumps(entry, indent=2))
        print("Startup response saved.")
    except Exception as e:
        print(f"Error saving startup response: {e}")


# Send two messages silently at startup
# Function to load initial messages from files
def load_initial_messages(folder_path):
    messages = []
    try:
        for filename in sorted(os.listdir(folder_path)):
            file_path = os.path.join(folder_path, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    messages.append(content)
    except Exception as e:
        print(f"Error reading initial messages: {e}")
    return messages


# Send initial messages silently
def prime_model():
    messages = load_initial_messages("initialMessages")
    for msg in messages:
        try:
            chat.send_message(msg)
        except Exception as e:
            print(f"Error sending initial message '{msg}': {e}")


# Save full exchange into JSON file
async def save_to_history(user_message, bot_response):
    history_entry = {
        "timestamp": datetime.now().isoformat(),
        "user_message": user_message,
        "bot_response": bot_response
    }

    async def save_to_file(file_path):
        try:
            existing_data = []
            if os.path.exists(file_path):
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    if content.strip():
                        loaded = json.loads(content)
                        if isinstance(loaded, list):
                            existing_data = loaded
                        elif isinstance(loaded, dict):
                            existing_data = [loaded]

            # Skip if duplicate
            if any(entry.get("user_message") == user_message for entry in existing_data):
                print(f"Duplicate question detected in {file_path}. Skipping save.")
                return

            existing_data.append(history_entry)

            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(existing_data, indent=2))

        except Exception as e:
            print(f"Error saving chat history to {file_path}: {e}")

    # Run both saves concurrently
    await asyncio.gather(
        save_to_file(HISTORY_FILE),
        save_to_file(CHAT_ENHANCER_FILE)
    )


# Call on startup
prime_model()


@app.route('/ask', methods=['POST'])
def ask():
    user_message = request.json.get("message")
    if not user_message:
        return jsonify({"error": "No message provided"}), 400
    try:
        response = chat.send_message(user_message)

        # Save history in a separate thread running async
        def run_async():
            asyncio.run(save_to_history(user_message, response.text))
        threading.Thread(target=run_async).start()
        return jsonify({"response": response.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # Run startup message async
    asyncio.run(run_startup_message())

    app.run(debug=True)
