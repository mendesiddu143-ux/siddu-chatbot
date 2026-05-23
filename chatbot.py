import os
from flask import Flask, render_template, request, jsonify
from groq import Groq

app = Flask(__name__)


client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        user_message = request.form["message"]
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a helpful assistant named Siddu."},
                {"role": "user", "content": user_message}
            ]
        )
        reply = response.choices[0].message.content
        return jsonify({"reply": reply})
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)