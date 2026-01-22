from flask import Flask, request, jsonify

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

if __name__ == "__main__":
    app.run()
