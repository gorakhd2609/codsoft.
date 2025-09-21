# app.py
from flask import Flask, render_template, request, jsonify
from chatbot import ChatBot

app = Flask(__name__, static_folder="static", template_folder="templates")
bot = ChatBot()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get', methods=['POST'])
def get_bot_response():
    data = request.get_json() or {}
    message = data.get('message', '')
    user_name = data.get('user_name')  # optional (from client localStorage)
    reply, new_user_name = bot.get_response(message, user_name)
    return jsonify({'reply': reply, 'user_name': new_user_name})

@app.route('/history', methods=['GET'])
def history():
    user_name = request.args.get('user_name')
    hist = bot.get_history(user_name, limit=200)
    return jsonify({'history': hist})

if __name__ == '__main__':
    # debug True for dev only
    app.run(debug=True)
