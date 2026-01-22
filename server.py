from flask import Flask, request, jsonify
import time

app = Flask(__name__)
messages = []  # store all messages

@app.route("/send", methods=["POST"])
def send():
    data = request.get_json()
    text = data.get("text", "")
    messages.append(text)
    return jsonify({"status": "ok"})

@app.route("/receive", methods=["GET"])
def receive():
    return jsonify({"messages": messages})

@app.route("/wait", methods=["GET"])
def wait_for_message():
    last = int(request.args.get("last", 0))

    # Long-poll for up to 30 seconds
    for _ in range(30):
        if len(messages) > last:
            return jsonify({"messages": messages})
        time.sleep(1)

    # Timeout: return current messages anyway
    return jsonify({"messages": messages})

if __name__ == "__main__":
    app.run()
