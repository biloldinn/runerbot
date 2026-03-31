from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({
        "status": "active",
        "message": "Turon Buyurtma Bot is ready for deployment!",
        "recommendation": "For 24/7 reliability, please deploy this bot on Render.com instead of Vercel."
    })

@app.route("/webhook", methods=["POST"])
def webhook():
    # Placeholder for future Vercel-to-Telegram Webhook integration
    return "Webhook received (placeholder).", 200

if __name__ == "__main__":
    app.run()
