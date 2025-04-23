# utils.py
def log_message(message, socketio=None):
    print(message)
    if socketio:
        socketio.emit('log', {'message': message})
