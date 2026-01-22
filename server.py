from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Store chat history per room
chat_history = {
    "general": []
}

# -------------------------
# Optional HTTP endpoints
# -------------------------

@app.route("/send", methods=["POST"])
def send():
    data = request.get_json()
    text = data.get("text", "")
    room = data.get("room", "general")

    if room not in chat_history:
        chat_history[room] = []

    chat_history[room].append(text)
    socketio.emit("new_message", text, room=room)

    return jsonify({"status": "ok"})


@app.route("/receive", methods=["GET"])
def receive():
    room = request.args.get("room", "general")
    return jsonify({"messages": chat_history.get(room, [])})


# -------------------------
# WebSocket events
# -------------------------

@socketio.on("connect")
def handle_connect():
    print("Client connected")


@socketio.on("join_room")
def handle_join(room):
    join_room(room)
    print(f"Client joined room: {room}")


@socketio.on("leave_room")
def handle_leave(room):
    leave_room(room)
    print(f"Client left room: {room}")


@socketio.on("request_history")
def handle_history(room):
    if room not in chat_history:
        chat_history[room] = []
    emit("chat_history", chat_history[room])


@socketio.on("send_message")
def handle_send_message(data):
    room = data.get("room", "general")

    if room not in chat_history:
        chat_history[room] = []

    chat_history[room].append(data)

    # Send only to users in that room
    emit("new_message", data, room=room)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
