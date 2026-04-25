from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime
import os
print("printing works")
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", transports=["websocket"])

# Track which socket belongs to which username
user_sids = {}      # username -> sid
sid_users = {}      # sid -> username
token_sids = {}
sid_tokens = {}
sid_roles = {}

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
    "enzotokenfjlsbdj",
    "jonahtokendsfieh",
    "theotokenafeeisd"
}

# Track which Socket.IO sessions are authenticated
authenticated = set()

def return_main(sids):
    for sid in sids:
        role = sid_roles.get(sid, "main")
        if role == "main":
            print("return sid")
            return sid
    return sids[0]

def emit_sid(event, data, to=None):
    if to is None:
        return False
    print("returned false (to is none)")
    token = sid_tokens.get(to, None)
    if token is None:
        return False
    print("returned false (token is none)")
    sids = token_sids.get(token, [])
    if not sids:
        return False
    print("returned false (not sids)")
    sid = return_main(sids)
    socketio.emit(event, data, to=sid)
    return True

def require_auth():
    print("AUTH CHECK:", request.sid, request.sid in authenticated, authenticated)
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

file_buffers = {}

UPLOAD_DIR = "UPLOADS"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_completed_uploads():
    return [f for f in os.listdir(UPLOAD_DIR)]

@socketio.event
def files():
    sid = request.sid
    emit_sid("server_uploads", {"files" : get_completed_uploads()}, to=sid)

@socketio.event
def upload_chunk(payload):
    name = payload["file"]
    chunk = payload["chunk"]

    file_buffers.setdefault(name, bytearray()).extend(chunk)

@socketio.event
def request_latest(data):
    view = bool(data.get("on_complete", 0))
    if view:
        files = [os.path.join(UPLOAD_DIR, f) for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f)) and f.lower().endswith((".png", ".jpg", ".jpeg"))] # gets all of the server's files
    else:
        files = [os.path.join(UPLOAD_DIR, f) for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))]
    if len(files) == 0:
        socketio.emit("server_uploads", {"files" : []})
        return None
    file = max(files, key=os.path.getctime) # latest
    filename = os.path.basename(file)
    try: # same as download but assumes on_complete is 1
        with open(file, "rb") as f:
            while chunk := f.read(4096):
                emit_sid("download_chunk", {"file": filename, "chunk": chunk}, to=request.sid)
        
            if view:
                emit_sid("view_download_complete", {"file": filename}, to=request.sid)
            else:
                emit_sid("download_complete", {"file": filename}, to=request.sid)

    except FileNotFoundError:
       socketio.emit_sid("download_error", {"file": file}, to=request.sid)

@socketio.event
def upload_complete(payload):
    sid = request.sid
    try:
        name = payload["file"]
        with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
            f.write(file_buffers[name])
        del file_buffers[name]
        emit_sid("upload_complete", {"file": name}, to=sid)

        if name.lower().endswith((".png", ".jpg", ".jpeg")):
            files = [os.path.join(UPLOAD_DIR, f) for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f)) and f.lower().endswith((".png", ".jpg", ".jpeg"))] # gets all of the server's files
            if len(files) == 0:
                socketio.emit("server_uploads", {"files" : []})
                return None
            file = max(files, key=os.path.getctime) # latest
            filename = os.path.basename(file)
            with open(file, "rb") as f:
                while chunk := f.read(4096):
                    socketio.emit("download_chunk", {"file": filename, "chunk": chunk})
            
                socketio.emit("view_download_complete", {"file": filename})

    except:
        emit_sid("upload_error", {"file": name}, to=sid)

@socketio.event
def download(data):
    file = data.get("file")
    try:
        with open(os.path.join(UPLOAD_DIR, file), "rb") as f:
            while chunk := f.read(4096):
                socketio.emit("download_chunk", {"file": file, "chunk": chunk}, to=request.sid)
        
        if data.get("on_complete", 0) == 1:
            socketio.emit("view_download_complete", {"file": file}, to=request.sid)
        else:
            socketio.emit("download_complete", {"file": file}, to=request.sid)

    except FileNotFoundError:
        socketio.emit("download_error", {"file": file}, to=request.sid)

# ----------------------------------------------------
# Trim history helper
# ----------------------------------------------------
def trim_history(room):
    history = chat_history.get(room, [])
    if len(history) >= 50:
        chat_history[room] = history[-10:]

def broadcast_online(room):
    online_users = list(rooms_online.get(room, []))
    socketio.emit("online_list", {
        "room": room,
        "users": online_users
    }, room=room)

# ----------------------------------------------------
# WebSocket events
# ----------------------------------------------------

@socketio.on("connect")
def handle_connect(auth):
    token = auth.get("token") if auth else None
    if token is None or token not in VALID_DEVICE_TOKENS:
        return False

    sid = request.sid
    authenticated.add(sid)
    token_sids.setdefault(token, set()).add(sid)
    sid_tokens[sid] = token

@socketio.on("ping_dnd")
def handle_ping_dnd(data):
    sender = data["to"]
    emit("ping_dnd", {"to": sender}, room=sender)

@socketio.on("join_room")
def handle_join_main(data):
    if not require_auth():
        return False

    room = data.get("room")
    user = data.get("user", "Unknown")

    # Track username <-> sid
    user_sids[user] = request.sid
    sid_users[request.sid] = user
    sid_roles[request.sid] = "main"

    join_room(room)
    print(f"{user} joined room: {room}")

    rooms_online.setdefault(room, set()).add(user)

    broadcast_online(room)

    system_msg = {
        "room": room,
        "user": "SYSTEM",
        "text": f"{user} has joined the room.",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }

    chat_history.setdefault(room, []).append(system_msg)
    trim_history(room)

    socketio.emit("new_message", system_msg, room=room, skip_sid=request.sid)

@socketio.on("join_bg")
def handle_join_bg(data):
    if not require_auth():
        return False

    room = data.get("room")
    user = data.get("user", "Unknown")

    # Track username <-> sid
    user_sids[user] = request.sid
    sid_users[request.sid] = user
    sid_roles[request.sid] = "bg"

    join_room(room)
    print(f"{user} has connected.")

    rooms_online.setdefault(room, set()).add(user)

    system_msg = {
        "room": room,
        "user": "SYSTEM",
        "text": f"{user} has connected.",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }

    chat_history.setdefault(room, []).append(system_msg)
    trim_history(room)

@socketio.on("leave_room")
def handle_leave_main(data):
    if not require_auth():
        return False

    room = data.get("room")
    user = data.get("user", "Unknown")

    leave_room(room)
    print(f"{user} left room: {room}")

    # Remove user from online list
    if room in rooms_online and user in rooms_online[room]:
        rooms_online[room].remove(user)

    broadcast_online(room)
    
    system_msg = {
        "room": room,
        "user": "SYSTEM",
        "text": f"{user} has left the room.",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }

    chat_history.setdefault(room, []).append(system_msg)
    trim_history(room)

    emit("new_message", system_msg, room=room)

@socketio.on("leave_bg")
def handle_leave_bg(data):
    print("handle_leave_bg triggered")
    if not require_auth():
        return False

    room = data.get("room")
    user = data.get("user", "Unknown")

    leave_room(room)
    print(f"{user} left room: {room}")

    # Remove user from online list
    if room in rooms_online and user in rooms_online[room]:
        rooms_online[room].remove(user)

    broadcast_online(room)
    
    system_msg = {
        "room": room,
        "user": "SYSTEM",
        "text": f"{user} has disconnected.",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }

    chat_history.setdefault(room, []).append(system_msg)
    trim_history(room)

    socketio.emit("new_message", system_msg, room=room)

@socketio.on("disconnect")
def handle_disconnect():
    print("DISCONNECT EVENT:", {
        "disconnecting_sid": sid,
        "disconnecting_user": sid_users.get(sid),
        "authenticated_before": authenticated.copy(),
    })
    sid = request.sid
    if sid in sid_users:
        user = sid_users[sid]
        print(f"{user} disconnected!")
        # Remove from all rooms
        for room, users in rooms_online.items():
            if user in users:
                users.discard(user)
                broadcast_online(room)

        # Remove from maps
        token = sid_tokens.get(sid)
        if token:
            token_sids.get(token, set()).discard(sid)
            if not token_sids.get(token):
                token_sids.pop(token, None)
        user_sids.pop(user, None)
        sid_users.pop(sid, None)
        authenticated.discard(sid)
        print("AUTHENTICATED_AFTER:", authenticated)

@socketio.on("request_history")
def handle_history(data):
    if not require_auth():
        return False

    room = data.get("room") if isinstance(data, dict) else data

    if room not in chat_history:
        chat_history[room] = []

    emit("chat_history", chat_history[room])

@socketio.on("reply")
def handle_reply(data):
    if not require_auth():
        return False

    room = data.get("room", "general")
    timestamp = data.get("timestamp")
    user = sid_users.get(request.sid, "Unknown")

    # Broadcast to everyone in the room
    socketio.emit("highlight_message", {
        "timestamp": timestamp,
        "replied_by": user
    }, room=room)

    print(f"{user} replied to message at {timestamp}")

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
    message = data.get("message", "")
    print(user_sids.keys())
    # If target is not online, send LOCAL ONLY message
    if target not in user_sids:
        emit("ping_failed", {
            "to": target,
            "reason": "offline"
        }, room=request.sid)
        return None
    print("iftargetnotinusersids")

    success = emit_sid("ping_alert", {
        "from": sender,
        "message": message
    }, to=user_sids[target])
    print(success)
    if not success:
        emit("ping_failed", {
            "to": target,
            "reason": "offline"
        }, room=request.sid)

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
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)
