from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

messages = []


# --- Optional HTTP endpoints (still work) ---

@app.route("/send", methods=["POST"])
def send():
    data = request.get_json()
    text = data.get("text", "")
    messages.append(text)

    # Push to all WebSocket clients
    socketio.emit("new_message", text)

    return jsonify({"status": "ok"})


@app.route("/receive", methods=["GET"])
def receive():
    return jsonify({"messages": messages})


# --- WebSocket events ---

@socketio.on("connect")
def handle_connect():
    print("Client connected")
    emit("chat_history", messages)


@socketio.on("send_message")
def handle_send_message(text):
    messages.append(text)
    emit("new_message", text, broadcast=True)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
