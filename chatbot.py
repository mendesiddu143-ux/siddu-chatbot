import os
import json
import uuid
import base64
import hashlib
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from groq import Groq
import fitz
from duckduckgo_search import DDGS
from docx import Document
from PIL import Image
import io

app = Flask(__name__)
app.secret_key = "mandot_ai_secret_key_2024"

client = Groq(api_key="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")

USERS_FILE = "users.json"
HISTORY_FILE = "chat_history.json"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def extract_text_from_pdf(file):
    text = ""
    pdf = fitz.open(stream=file.read(), filetype="pdf")
    for page in pdf:
        text += page.get_text()
    return text[:3000]

def extract_text_from_docx(file):
    doc = Document(file)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text[:3000]

def image_to_base64(file):
    img = Image.open(file)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=85)
    return base64.b64encode(buffer.getvalue()).decode()

@app.route("/")
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", user=session["user"])

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        users = load_users()
        hashed = hash_password(password)
        if email in users and users[email]["password"] == hashed:
            session["user"] = {"email": email, "name": users[email]["name"]}
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Invalid email or password!"})
    return render_template("login.html")

@app.route("/signup", methods=["POST"])
def signup():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    if not name or not email or not password:
        return jsonify({"success": False, "error": "All fields are required!"})
    users = load_users()
    if email in users:
        return jsonify({"success": False, "error": "Email already exists!"})
    if len(password) < 6:
        return jsonify({"success": False, "error": "Password must be at least 6 characters!"})
    users[email] = {
        "name": name, "email": email,
        "password": hash_password(password),
        "created": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    save_users(users)
    session["user"] = {"email": email, "name": name}
    return jsonify({"success": True})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/chat", methods=["POST"])
def chat():
    if "user" not in session:
        return jsonify({"reply": "Please login first!"})

    user_message = request.form.get("message", "")
    is_design = request.form.get("is_design", "false")
    chat_id = request.form.get("chat_id", "")
    mode = request.form.get("mode", "default")
    user_email = session["user"]["email"]
    file = request.files.get("file")

    mode_prompts = {
        "default": "You are ManDot AI, created by Siddu (Mende Sidardha). You are a friendly and helpful AI assistant. If anyone asks who made you or who created you, always say 'I am ManDot AI, created by Siddu'. Never mention Meta, Groq, or Llama. Give clear helpful answers in plain text.",
       "developer": "You are ManDot AI in Developer Mode, created by Siddu. Expert software engineer. Give technical answers with code examples. Never mention Meta, Groq, or Llama.",
        "creative": "You are ManDot AI in Creative Mode. Highly imaginative assistant. Give creative, expressive responses.",
        "study": "You are ManDot AI in Study Mode. Patient teacher. Break down topics into simple steps with examples.",
        "business": "You are ManDot AI in Business Mode. Expert business consultant. Give professional strategic advice.",
        "motivator": "You are ManDot AI in Motivator Mode. Energetic life coach. Give powerful uplifting motivational responses."
    }

    if file and file.filename:
        filename = file.filename.lower()
        try:
            if filename.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                img_base64 = image_to_base64(file)
                response = client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[{"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}},
                        {"type": "text", "text": user_message if user_message else "Analyze this image in detail."}
                    ]}],
                    max_tokens=1000
                )
                reply = response.choices[0].message.content
                return jsonify({"reply": reply, "chat_id": chat_id})
            elif filename.endswith('.pdf'):
                file_info = extract_text_from_pdf(file)
                user_message = f"{user_message if user_message else 'Analyze this PDF.'}\n\nContent:\n{file_info}"
            elif filename.endswith(('.docx', '.doc')):
                file_info = extract_text_from_docx(file)
                user_message = f"{user_message if user_message else 'Analyze this document.'}\n\nContent:\n{file_info}"
            elif filename.endswith('.txt'):
                file_info = file.read().decode('utf-8')[:3000]
                user_message = f"{user_message if user_message else 'Analyze this file.'}\n\nContent:\n{file_info}"
        except Exception as e:
            return jsonify({"reply": f"Error reading file: {str(e)}"})

    # Web search
    search_context = ""
    search_results_text = ""
    if is_design != "true":
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(user_message, max_results=2))
                if results:
                    search_context = "\n\nLatest web search results:\n"
                    for i, r in enumerate(results, 1):
                       search_context += f"{i}. {r['title']}: {r['body'][:100]}\n\n"
                    search_results_text = "\n\n**Sources:**\n" + "\n".join([f"- [{r['title']}]({r['href']})" for r in results])
        except:
            pass

    if is_design == "true":
        system_prompt = "You are ManDot AI, an expert web designer. Always generate complete single-file HTML with embedded CSS and JS. Return ONE complete HTML file only."
    else:
        base_prompt = mode_prompts.get(mode, mode_prompts["default"])
        system_prompt = base_prompt + "\n\nYou have access to real-time web search results. Use them to give accurate, up-to-date answers. Always mention sources when using web search data."

    try:
        response = client.chat.completions.create(
           model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message + search_context}
            ],
            max_tokens=2000,
            temperature=0.7
        )
        reply = response.choices[0].message.content
        if search_results_text and is_design != "true":
            reply = reply + search_results_text

        if chat_id:
            history = load_history()
            user_key = f"{user_email}_{chat_id}"
            if user_key not in history:
                history[user_key] = {
                    "id": chat_id, "user": user_email,
                    "title": user_message[:40] + "..." if len(user_message) > 40 else user_message,
                    "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "messages": []
                }
            history[user_key]["messages"].append({"role": "user", "text": user_message[:200], "time": datetime.now().strftime("%H:%M")})
            history[user_key]["messages"].append({"role": "ai", "text": reply, "time": datetime.now().strftime("%H:%M")})
            save_history(history)

        return jsonify({"reply": reply, "chat_id": chat_id})
    except Exception as e:
        return jsonify({"reply": str(e)})

@app.route("/history", methods=["GET"])
def get_history():
    if "user" not in session:
        return jsonify([])
    user_email = session["user"]["email"]
    history = load_history()
    chats = [v for k, v in history.items() if v.get("user") == user_email]
    chats.sort(key=lambda x: x["created"], reverse=True)
    return jsonify(chats)

@app.route("/history/<chat_id>", methods=["GET"])
def get_chat(chat_id):
    if "user" not in session:
        return jsonify({})
    user_email = session["user"]["email"]
    history = load_history()
    user_key = f"{user_email}_{chat_id}"
    return jsonify(history.get(user_key, {}))

@app.route("/history/<chat_id>/rename", methods=["POST"])
def rename_chat(chat_id):
    if "user" not in session:
        return jsonify({"success": False})
    user_email = session["user"]["email"]
    new_title = request.form.get("title", "")
    history = load_history()
    user_key = f"{user_email}_{chat_id}"
    if user_key in history:
        history[user_key]["title"] = new_title
        save_history(history)
    return jsonify({"success": True})

@app.route("/history/<chat_id>/delete", methods=["POST"])
def delete_chat(chat_id):
    if "user" not in session:
        return jsonify({"success": False})
    user_email = session["user"]["email"]
    history = load_history()
    user_key = f"{user_email}_{chat_id}"
    if user_key in history:
        del history[user_key]
        save_history(history)
    return jsonify({"success": True})

@app.route("/history/new", methods=["POST"])
def new_chat():
    chat_id = str(uuid.uuid4())[:8]
    return jsonify({"chat_id": chat_id})

if __name__ == "__main__":
    app.run(debug=True)