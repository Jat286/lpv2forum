from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Track which socket belongs to which username
user_sids = {}      # username -> sid
sid_users = {}      # sid -> username

# Store chat history per room
chat_history = {
    "general": []
}

# Track online users per room
rooms_online = {}   # { "general": {"Joh", "Alice"} }

# ----------------------------------------------------
# Per-device token auth
# ----------------------------------------------------

# Replace these with your real per-device tokens
VALID_DEVICE_TOKENS = {
    "tobytokengjbgrjl",
    "johtokenfjbalgja",
    "enzotokenfjlsbdj"
}

# Track which Socket.IO sessions are authenticated
authenticated = set()


def require_auth():
    return request.sid in authenticated


@socketio.on("auth")
def handle_auth(data):
    token = data.get("token")

    if token not in VALID_DEVICE_TOKENS:
        print(f"Unauthorized device with token: {token}")
        return False  # disconnect client

    authenticated.add(request.sid)
    print(f"Device authenticated with token: {token}")
    emit("auth_ok", {"status": "ok"})


# ----------------------------------------------------
# Trim history helper
# ----------------------------------------------------
def trim_history(room):
    history = chat_history.get(room, [])
    if len(history) >= 50:
        chat_history[room] = history[-10:]


# ----------------------------------------------------
# Optional HTTP endpoints (not token-protected here)
# ----------------------------------------------------

@app.route("/send", methods=["POST"])
def send():
    data = request.get_json()
    text = data.get("text", "")
    room = data.get("room", "general")
    user = data.get("user", "API")
    timestamp = datetime.now().strftime("%H:%M:%S")

    msg = {
        "room": room,
        "user": user,
        "text": text,
        "timestamp": timestamp
    }

    chat_history.setdefault(room, []).append(msg)
    trim_history(room)

    socketio.emit("new_message", msg, room=room)
    return jsonify({"status": "ok"})


@app.route("/receive", methods=["GET"])
def receive():
    room = request.args.get("room", "general")
    return jsonify({"messages": chat_history.get(room, [])})


# ----------------------------------------------------
# WebSocket events
# ----------------------------------------------------

@socketio.on("connect")
def handle_connect():
    print("Client connected")

@socketio.on("ping_dnd")
def handle_ping_dnd(data):
    sender = data["to"]
    emit("ping_dnd", {"to": sender}, room=sender)

@socketio.on("join_room")
def handle_join(data):
    if not require_auth():
        return False

    room = data.get("room")
    user = data.get("user", "Unknown")

    # Track username <-> sid
    user_sids[user] = request.sid
    sid_users[request.sid] = user

    join_room(room)
    print(f"{user} joined room: {room}")

    rooms_online.setdefault(room, set()).add(user)

    system_msg = {
        "room": room,
        "user": "SYSTEM",
        "text": f"{user} has joined the room.",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }

    chat_history.setdefault(room, []).append(system_msg)
    trim_history(room)

    emit("new_message", system_msg, room=room)

@socketio.on("join_bg")
def handle_join(data):
    if not require_auth():
        return False

    room = data.get("room")
    user = data.get("user", "Unknown")

    # Track username <-> sid
    user_sids[user] = request.sid
    sid_users[request.sid] = user

    join_room(room)
    print(f"{user} joined room: {room}")

    rooms_online.setdefault(room, set()).add(user)

    system_msg = {
        "room": room,
        "user": "SYSTEM",
        "text": f"{user} has joined the room.",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }

    chat_history.setdefault(room, []).append(system_msg)
    trim_history(room)

@socketio.on("leave_room")
def handle_leave(data):
    if not require_auth():
        return False

    room = data.get("room")
    user = data.get("user", "Unknown")

    leave_room(room)
    print(f"{user} left room: {room}")

    # Remove user from online list
    if room in rooms_online and user in rooms_online[room]:
        rooms_online[room].remove(user)

    system_msg = {
        "room": room,
        "user": "SYSTEM",
        "text": f"{user} has left the room.",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }

    chat_history.setdefault(room, []).append(system_msg)
    trim_history(room)

    emit("new_message", system_msg, room=room)

@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid
    if sid in sid_users:
        user = sid_users[sid]
        print(f"{user} disconnected")

        # Remove from all rooms
        for room, users in rooms_online.items():
            if user in users:
                users.remove(user)

        # Remove from maps
        del user_sids[user]
        del sid_users[sid]

@socketio.on("request_history")
def handle_history(data):
    if not require_auth():
        return False

    room = data.get("room") if isinstance(data, dict) else data

    if room not in chat_history:
        chat_history[room] = []

    emit("chat_history", chat_history[room])


@socketio.on("send_message")
def handle_send_message(data):
    if not require_auth():
        return False

    room = data.get("room", "general")

    if room not in chat_history:
        chat_history[room] = []

    chat_history[room].append(data)
    trim_history(room)

    # If trimming happened, resend trimmed history to everyone in the room
    if len(chat_history[room]) == 10:
        emit("chat_history", chat_history[room], room=room)
        return

    emit("new_message", data, room=room)

@socketio.on("ping_user")
def handle_ping_user(data):
    if not require_auth():
        return False

    sender = data.get("from")
    target = data.get("to")

    # If target is not online, send LOCAL ONLY message
    if target not in user_sids:
        emit("ping_failed", {
            "to": target,
            "reason": "offline"
        }, room=request.sid)
        return

    target_sid = user_sids[target]

    emit("ping_alert", {
        "from": sender
    }, room=target_sid)

    print(f"{sender} pinged {target}")

# ----------------------------------------------------
# /online support
# ----------------------------------------------------

@socketio.on("online_request")
def handle_online_request(data):
    if not require_auth():
        return False

    room = data.get("room", "general")

    online_users = list(rooms_online.get(room, []))

    emit("online_list", {
        "room": room,
        "users": online_users
    }, room=request.sid)


# ----------------------------------------------------

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
