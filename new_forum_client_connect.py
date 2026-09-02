import socketio
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

clientID = "client1"
connected = False
pendingChallenge = None
with open("private.pem", "rb") as f:
    privateKey = serialization.load_pem_private_key(
        f.read(), password=None)

def verify(challenge):
    signature = privateKey.sign(
        challenge,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256())

    sio.emit("verify", {"signature": signature.hex()})

@sio.event
def connect():
    global connected, pendingChallenge
    connected = True
    if pendingChallenge:
        verify(pendingChallenge)
        pendingChallenge = None

@sio.on("challenge")
def handle_challenge(data):
    global pendingChallenge
    challenge = bytes.fromhex(data["challenge"])
    if connected:
        verify(challenge)
    else:
        pendingChallenge = challenge

@sio.on("auth_ok")
def auth_ok(data):
    # this is your normal auth_ok function hopefully
