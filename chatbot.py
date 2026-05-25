import os
import json
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from groq import Groq

app = Flask(__name__)
client = Groq(api_key="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")

HISTORY_FILE = "chat_history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.form.get("message", "")
    is_design = request.form.get("is_design", "false")
    chat_id = request.form.get("chat_id", "")

    if is_design == "true":
        system_prompt = "You are ManDot AI, an expert web designer. Always generate complete single-file HTML with embedded CSS in <style> tags and JS in <script> tags. Never separate HTML and CSS into different files. Always return ONE complete HTML file only."
    else:
        system_prompt = "You are ManDot AI, a friendly and helpful AI assistant. Give clear, helpful answers in plain text. Never return HTML code unless specifically asked."

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=2000,
            temperature=0.7
        )
        reply = response.choices[0].message.content

        # Save to history
        if chat_id:
            history = load_history()
            if chat_id not in history:
                history[chat_id] = {
                    "id": chat_id,
                    "title": user_message[:40] + "..." if len(user_message) > 40 else user_message,
                    "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "messages": []
                }
            history[chat_id]["messages"].append({
                "role": "user",
                "text": user_message,
                "time": datetime.now().strftime("%H:%M")
            })
            history[chat_id]["messages"].append({
                "role": "ai",
                "text": reply,
                "time": datetime.now().strftime("%H:%M")
            })
            save_history(history)

        return jsonify({"reply": reply, "chat_id": chat_id})
    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"reply": str(e)})

@app.route("/history", methods=["GET"])
def get_history():
    history = load_history()
    chats = list(history.values())
    chats.sort(key=lambda x: x["created"], reverse=True)
    return jsonify(chats)

@app.route("/history/<chat_id>", methods=["GET"])
def get_chat(chat_id):
    history = load_history()
    return jsonify(history.get(chat_id, {}))

@app.route("/history/<chat_id>/rename", methods=["POST"])
def rename_chat(chat_id):
    new_title = request.form.get("title", "")
    history = load_history()
    if chat_id in history:
        history[chat_id]["title"] = new_title
        save_history(history)
    return jsonify({"success": True})

@app.route("/history/<chat_id>/delete", methods=["POST"])
def delete_chat(chat_id):
    history = load_history()
    if chat_id in history:
        del history[chat_id]
        save_history(history)
    return jsonify({"success": True})

@app.route("/history/new", methods=["POST"])
def new_chat():
    chat_id = str(uuid.uuid4())[:8]
    return jsonify({"chat_id": chat_id})

if __name__ == "__main__":
    app.run(debug=True)