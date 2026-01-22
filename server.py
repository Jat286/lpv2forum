from flask import Flask, request, jsonify

app = Flask(__name__)
latest_message = ""

@app.route("/send", methods=["POST"])
def send():
    global latest_message
    data = request.get_json()
    latest_message = data.get("text", "")
    return jsonify({"status": "ok"})

@app.route("/receive", methods=["GET"])
def receive():
    return jsonify({"text": latest_message})

if __name__ == "__main__":
    app.run()
