from flask import Flask, request
from db import update_user
from telegram import Bot
from config import TELEGRAM_TOKEN

app = Flask(__name__)
bot = Bot(token=TELEGRAM_TOKEN)

@app.route('/donate_webhook', methods=['POST'])
def donate_webhook():
    data = request.json or request.form
    comment = data.get('comment', '')
    if 'user_id:' in comment:
        try:
            user_id = int(comment.split('user_id:')[1].split()[0])
            update_user(user_id, plan='pro')
            bot.send_message(chat_id=user_id, text="✅ Оплата получена! Вам доступно 500 генераций в месяц.")
            return 'ok', 200
        except Exception as e:
            return f'error: {e}', 400
    return 'no user_id', 400

if __name__ == '__main__':
    app.run(port=8080)