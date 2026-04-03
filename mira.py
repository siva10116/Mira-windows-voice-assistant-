import speech_recognition as sr
import sounddevice as sd
import pyttsx3
import keyboard
import threading
import time
import queue
import customtkinter as ctk
import tkinter as tk
import pythoncom
import wikipedia
import webbrowser
from ytmusicapi import YTMusic
import random

msg_queue = queue.Queue()
text_command_queue = queue.Queue()

# Siri aesthetic colors
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class MiraApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Mira Assistant")
        # Sleek vertical floating geometry, like Siri macOS
        self.geometry("340x480")
        self.attributes('-topmost', True)
        self.overrideredirect(True) # Completely removes Windows borders to make it float seamlessly!
        
        # Position specifically in the top right
        self.position_top_right()
        
        # Background color to match the canvas blending smoothly
        self.configure(fg_color="#141414")
        
        # --- ORB VISUALS ---
        # Using a raw Tkinter canvas wrapped inside CustomTkinter for custom gradient-like drawing
        self.canvas_bg = "#141414" 
        self.orb_canvas = tk.Canvas(self, width=200, height=200, bg=self.canvas_bg, highlightthickness=0)
        self.orb_canvas.pack(pady=(30, 10))
        
        # Draw the initial glowing shapes to mimic an iridescent orb
        self.orb_shapes = []
        colors = ["#2b8a3e", "#2bc48a", "#2b7fc4", "#b32bc4"]
        for c in colors:
            x1, y1 = random.randint(40, 80), random.randint(40, 80)
            x2, y2 = random.randint(120, 160), random.randint(120, 160)
            orb = self.orb_canvas.create_oval(x1, y1, x2, y2, fill=c, outline="")
            self.orb_shapes.append(orb)

        # --- MINIMALIST TYPOGRAPHY ---
        self.status_label = ctk.CTkLabel(self, text="Waiting for Ctrl+Alt+M...", font=("Helvetica", 14, "bold"), text_color="gray")
        self.status_label.pack(pady=5)
        
        # This replaces the huge 90s chat log. It dynamically updates exactly what you are saying right now.
        self.live_transcript = ctk.CTkLabel(self, text="", font=("Inter", 18), text_color="white", wraplength=280, justify="center")
        self.live_transcript.pack(pady=10)
        
        # Minimalistic input toggle area
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.pack(side="bottom", pady=20, fill="x", padx=10)
        
        self.mode_var = ctk.StringVar(value="Voice Mode")
        self.mode_toggle = ctk.CTkSegmentedButton(self.bottom_frame, values=["Voice Mode", "Search Mode"], 
                                                  variable=self.mode_var, command=self.switch_mode, height=25)
        self.mode_toggle.pack(pady=(0, 10))

        # Hidden sleek text entry structure for 'Search Mode'
        self.input_frame = ctk.CTkFrame(self.bottom_frame, fg_color="transparent")
        self.text_entry = ctk.CTkEntry(self.input_frame, width=220, placeholder_text="Type to Mira...", border_width=1, corner_radius=20)
        self.text_entry.bind("<Return>", self.submit_text)
        self.enter_btn = ctk.CTkButton(self.input_frame, text="↑", width=40, corner_radius=20, command=self.submit_text)
        
        self.check_queue()
        self.withdraw()
        self.session_active = False

    def position_top_right(self):
        self.update_idletasks()
        width = 340
        height = 480
        # Pushed roughly 20px off from perfectly touching the screen edge for a clean floating look
        x = self.winfo_screenwidth() - width - 20
        y = 40
        self.geometry(f'{width}x{height}+{x}+{y}')

    def animate_orb(self, state):
        """Simulates Siri orb reactivity by recoloring active clusters dynamically."""
        if state == "Listening":
            colors = ["#2bc435", "#1eff8e", "#00d0ff", "#2b7fc4"] # Glowing cyan/greens
        elif state == "Processing":
            colors = ["#ff9900", "#ff4400", "#ff0066", "#9900ff"] # Intense orange/pinks for analyzing
        elif state == "Waiting":
            colors = ["#2b8a3e", "#2bc48a", "#2b7fc4", "#b32bc4"] # Subdued
        else:
            colors = ["gray"] * 4

        for orb, color in zip(self.orb_shapes, colors):
            self.orb_canvas.itemconfig(orb, fill=color)
            # Add subtle jitter to represent reactivity
            x_shift = random.randint(-4, 4)
            y_shift = random.randint(-4, 4)
            
            # Ensure it doesn't walk completely off the canvas over time
            coords = self.orb_canvas.coords(orb)
            if coords[0] < 10 or coords[2] > 190 or coords[1] < 10 or coords[3] > 190:
                self.orb_canvas.move(orb, -x_shift*3, -y_shift*3) # Recenter gently
            else:
                self.orb_canvas.move(orb, x_shift, y_shift)

    def submit_text(self, event=None):
        cmd = self.text_entry.get().strip()
        if cmd:
            self.text_entry.delete(0, "end")
            self.live_transcript.configure(text=f'"{cmd}"')
            text_command_queue.put(cmd)

    def switch_mode(self, new_mode):
        if new_mode == "Search Mode":
            self.input_frame.pack(pady=0)
            self.text_entry.pack(side="left", padx=5)
            self.enter_btn.pack(side="left")
            self.status_label.configure(text="", text_color="orange")
            self.live_transcript.configure(text="Awaiting typed command...")
        else:
            self.input_frame.pack_forget()
            self.status_label.configure(text="Listening...", text_color="#00FF00")

    def show_popup(self, title, link):
        """Creates a pop-up window for resulting links."""
        popup = ctk.CTkToplevel(self)
        popup.title("Mira Link Result")
        popup.geometry("380x160")
        popup.attributes('-topmost', True)
        popup.overrideredirect(True) # Apply stripped look to the pop out as well
        popup.configure(fg_color="#1c1c1c")
        
        popup.update_idletasks()
        # Slide out beautifully directly to the left side of the main floating widget
        x = self.winfo_x() - 390 
        y = self.winfo_y() + 50
        popup.geometry(f"+{x}+{y}")
        
        lbl = ctk.CTkLabel(popup, text=f"{title}", font=("Inter", 14, "bold"), wraplength=350)
        lbl.pack(pady=(20, 10))
        
        btn = ctk.CTkButton(popup, text="Open Result in Browser", corner_radius=20, command=lambda: webbrowser.open(link))
        btn.pack(pady=5)
        
        close_btn = ctk.CTkButton(popup, text="Dismiss", width=80, fg_color="transparent", border_width=1, corner_radius=20, command=popup.destroy)
        close_btn.pack(pady=5)

    def check_queue(self):
        try:
            while True:
                msg = msg_queue.get_nowait()
                if msg["type"] == "SHOW":
                    self.deiconify()  
                    self.attributes('-topmost', True) 
                    self.live_transcript.configure(text="")
                    self.animate_orb("Waiting")
                elif msg["type"] == "STATUS":
                    self.status_label.configure(text=msg["text"], text_color=msg.get("color", "white"))
                    # Bind animations implicitly to textual statuses!
                    if "Listening" in msg["text"]:
                        self.animate_orb("Listening")
                    elif "Processing" in msg["text"]:
                        self.animate_orb("Processing")
                    elif "Waiting" in msg["text"]:
                        self.animate_orb("Waiting")
                elif msg["type"] == "LOG":
                    # Clean out prefix text so it looks minimalistic like a live transcription!
                    clean_text = msg["text"].replace("Mira: ", "").replace("You (Voice): ", "").replace("You (Typed): ", "")
                    # Wrap the text so it formats dynamically gracefully
                    self.live_transcript.configure(text=f'"{clean_text}"')
                    if "Mira:" in msg["text"]:
                        self.animate_orb("Listening") # Jitter brightly while talking back
                elif msg["type"] == "POPUP":
                    self.show_popup(msg["title"], msg["link"])
                elif msg["type"] == "HIDE":
                    self.withdraw()
        except queue.Empty:
            pass
        finally:
            self.after(100, self.check_queue)


def process_user_intent(command, app, speak):
    """Central location processing requests originating from either Voice or Typed Input."""
    if "hello" in command:
        speak("Hello there! How can I help you today?")
        
    elif "time" in command:
        current_time = time.strftime("%I:%M %p")
        speak(f"The current time is {current_time}.")
        
    elif "play" in command:
        song_query = command.replace("play", "").strip()
        if song_query:
            msg_queue.put({"type": "STATUS", "text": f"Locating YTM...", "color": "cyan"})
            try:
                yt = YTMusic()
                search_results = yt.search(song_query, filter="songs")
                if search_results:
                    top_song = search_results[0]
                    video_id = top_song.get("videoId")
                    title = top_song.get("title", song_query)
                    artists = ", ".join([artist.get("name", "") for artist in top_song.get("artists", [])])
                    watch_url = f"https://music.youtube.com/watch?v={video_id}"
                    
                    speak(f"Playing {title} by {artists}.")
                    msg_queue.put({"type": "POPUP", "title": f"Now Playing: {title} by {artists}", "link": watch_url})
                    webbrowser.open(watch_url)
                else:
                    speak("I couldn't find that exact song randomly.")
            except Exception as e:
                msg_queue.put({"type": "LOG", "text": f"YTMusic API Error: {e}"})
                speak("I had trouble communicating with the API.")
        else:
            speak("What would you like me to play?")

    elif "goodbye" in command or "stop" in command:
        speak("Goodbye! Call me if you need me.")
        return "EXIT"

    else:
        msg_queue.put({"type": "STATUS", "text": "Searching Web...", "color": "cyan"})
        try:
            results = wikipedia.search(command)
            if not results:
                speak("I couldn't find anything online about that.")
            else:
                best_match = results[0]
                page = wikipedia.page(best_match, auto_suggest=False)
                msg_queue.put({"type": "POPUP", "title": page.title, "link": page.url})
                summary_text = wikipedia.summary(best_match, sentences=2, auto_suggest=False)
                speak(f"From Wikipedia: {summary_text}")
                
        except wikipedia.exceptions.DisambiguationError as e:
            speak(f"That search was too broad. Did you mean {e.options[0]}?")
        except wikipedia.exceptions.PageError:
            speak("I couldn't isolate a direct page for that request.")
        except Exception as e:
            msg_queue.put({"type": "LOG", "text": f"Search Error: {e}"})
            speak("Encountered an error reading the results.")
            
    return "CONTINUE"


def listen_and_process(app):
    pythoncom.CoInitialize()
    engine = pyttsx3.init()
    engine.setProperty('volume', 1.0)
    
    def speak(text):
        msg_queue.put({"type": "LOG", "text": f"Mira: {text}"})
        print(f"Mira: {text}")
        engine.say(text)
        engine.runAndWait()

    msg_queue.put({"type": "SHOW"})
    mode = app.mode_var.get()
    
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 150
    recognizer.dynamic_energy_threshold = True
    
    conversation_started = False
    wake_words = ["mira", "mirror", "mera", "meera", "myra"]
    
    speak("Online.")
    if mode == "Voice Mode":
        msg_queue.put({"type": "STATUS", "text": "Waiting for 'Mira'...", "color": "orange"})
    
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            
            while app.session_active:
                
                try:
                    typed_cmd = text_command_queue.get_nowait()
                    msg_queue.put({"type": "LOG", "text": f"You (Typed): {typed_cmd}"})
                    status = process_user_intent(typed_cmd.lower(), app, speak)
                    if status == "EXIT":
                        app.session_active = False
                        break
                    continue
                except queue.Empty:
                    pass

                if app.mode_var.get() == "Search Mode":
                    time.sleep(0.2)
                    continue

                msg_queue.put({"type": "STATUS", "text": "Listening...", "color": "#00FF00"})
                try:
                    audio = recognizer.listen(source, timeout=1.5, phrase_time_limit=10)
                except sr.WaitTimeoutError:
                    continue 

                msg_queue.put({"type": "STATUS", "text": "Processing...", "color": "orange"})
                
                try:
                    command = recognizer.recognize_google(audio).lower()
                    
                    if not conversation_started:
                        found_wake = False
                        for w in wake_words:
                            if w in command:
                                found_wake = True
                                command = command.replace(w, "").strip()
                                break
                                
                        if found_wake:
                            conversation_started = True
                            if not command:
                                msg_queue.put({"type": "LOG", "text": f"You (Voice): [Woke Up]"})
                                speak("Yes?")
                                continue 
                        else:
                            continue
                            
                    msg_queue.put({"type": "LOG", "text": f"You (Voice): {command}"})
                    status = process_user_intent(command, app, speak)
                    if status == "EXIT":
                        app.session_active = False
                        break
                        
                except sr.UnknownValueError:
                    pass
                except sr.RequestError as e:
                    msg_queue.put({"type": "STATUS", "text": "Service offline.", "color": "red"})
                    speak("Voice service offline.")
                    app.session_active = False
                    break
                    
    except Exception as e:
        msg_queue.put({"type": "STATUS", "text": "Error occurred.", "color": "red"})
        print(f"An error occurred: {e}")
    finally:
        msg_queue.put({"type": "HIDE"})
        app.session_active = False
        pythoncom.CoUninitialize()

def on_hotkey_pressed(app):
    if not app.session_active:
        app.session_active = True
        threading.Thread(target=listen_and_process, args=(app,), daemon=True).start()
    else:
        app.session_active = False

def main():
    print("Mira Background GUI Service Started.")
    print("Press Ctrl+Alt+M from anywhere to activate or deactivate Mira...")
    app = MiraApp()
    keyboard.add_hotkey('ctrl+alt+m', lambda: on_hotkey_pressed(app))
    try:
        app.mainloop()
    except KeyboardInterrupt:
        print("Exiting...")

if __name__ == "__main__":
    main()
