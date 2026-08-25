import socketio
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

clientID = "client1"
with open("private.pem", "rb") as f:
    privateKey = serialization.load_pem_private_key(
        f.read(), password=None)
    
@sio.event
def connect():
    sio.emit("auth", {"id": clientID})

@sio.on("challenge")
def handle_challenge(data):
    challenge = bytes.fromhex(data["challenge"])
    signature = privateKey.sign(
        challenge,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256())

    sio.emit("verify", {"signature": signature.hex()})

@sio.event
def auth_ok(data):
    # this is your normal auth_ok function hopefully