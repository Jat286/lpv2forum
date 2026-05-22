from flask_socketio import Namespace, emit, join_room, leave_room

class T3Namespace(Namespace):
  def on_connect(self):
        print("Client connected to /tictactoe")

  def on_disconnect(self):
      print("Client disconnected from /tictactoe")

  def on_join(self, data):
      room = data["room"]
      join_room(room)
      emit("joined", {"room": room})

  def on_move(self, data):
      emit("move", data, room=data["room"])

  def on_reset(self, data):
      emit("reset", data, room=data["room"])
