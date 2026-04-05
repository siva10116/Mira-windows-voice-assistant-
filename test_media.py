import time
import keyboard
import threading
from mira import MiraApp, msg_queue, text_command_queue

def run_app():
    app = MiraApp()
    app.active = True
    app.show()
    app.mainloop()

threading.Thread(target=run_app, daemon=True).start()

time.sleep(2)
msg_queue.put({"type": "MEDIA", "msg": {
    "text": "Song Title", 
    "thumb": "https://i.ytimg.com/vi/1/default.jpg",
    "suggestions": [
        {"title": "Song 1", "videoId": "123", "thumb": ""},
        {"title": "Song 2", "videoId": "456", "thumb": ""}
    ]
}})

time.sleep(5)
