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
import math

msg_queue = queue.Queue()
text_command_queue = queue.Queue()

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class MiraApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Mira Assistant")
        # Sleek wide, short geometry for Bottom-Center
        self.width = 600
        self.height = 220
        self.attributes('-topmost', True)
        self.overrideredirect(True) # borderless to float seamlessly!
        
        self.position_bottom_center()
        self.configure(fg_color="#141414")
        
        # --- MINIMALIST TYPOGRAPHY ---
        self.status_label = ctk.CTkLabel(self, text="What can I help you with?", font=("Inter", 24, "bold"), text_color="white")
        self.status_label.pack(pady=(15, 5))
        
        # Replaces the chat log with dynamic phrase
        self.live_transcript = ctk.CTkLabel(self, text="", font=("Inter", 16), text_color="gray80", wraplength=500, justify="center")
        self.live_transcript.pack(pady=0)

        # --- WAVEFORM VISUALS ---
        self.canvas_bg = "#141414" 
        self.wave_canvas = tk.Canvas(self, width=500, height=80, bg=self.canvas_bg, highlightthickness=0)
        self.wave_canvas.pack(pady=(10, 0))
        
        # Draw 3 overlapping smooth multipoint lines to mimic a neon glowing wave
        self.num_points = 50
        self.x_coords = [int(i * (500 / (self.num_points - 1))) for i in range(self.num_points)]
        self.wave_lines = []
        colors = ["#b32bc4", "#2b7fc4", "#ffffff"] # Purple, Blue, White Core
        widths = [6, 4, 3] # Outer glow -> Inner hot core
        
        for color, width in zip(colors, widths):
            coords = []
            for x in self.x_coords:
                coords.extend([x, 40]) # initially flat at y=40
            line_id = self.wave_canvas.create_line(*coords, fill=color, width=width, smooth=True, capstyle="round")
            self.wave_lines.append(line_id)

        # Mode Toggles & Sleek Entry
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.pack(side="bottom", pady=5, fill="x")
        
        self.mode_var = ctk.StringVar(value="Voice Mode")
        # Keep toggle very small
        self.mode_toggle = ctk.CTkSegmentedButton(self.bottom_frame, values=["Voice Mode", "Search Mode"], 
                                                  variable=self.mode_var, command=self.switch_mode, height=20, font=("Inter", 10))
        self.mode_toggle.pack(side="bottom")

        # Hidden text entry structure for 'Search Mode'
        self.input_frame = ctk.CTkFrame(self.bottom_frame, fg_color="transparent")
        self.text_entry = ctk.CTkEntry(self.input_frame, width=300, placeholder_text="Type your command...", border_width=1, corner_radius=20)
        self.text_entry.bind("<Return>", self.submit_text)
        self.enter_btn = ctk.CTkButton(self.input_frame, text="↑", width=40, height=25, corner_radius=20, command=self.submit_text)

        self.animation_state = "Waiting"
        self.phase = 0.0
        
        self.session_active = False
        
        self.check_queue()
        self.update_wave() # Starts looping animation mathematically
        self.withdraw()

    def position_bottom_center(self):
        self.update_idletasks()
        # Bottom center, floating heavily over taskbar like the Dribbble GIF
        x = (self.winfo_screenwidth() // 2) - (self.width // 2)
        y = self.winfo_screenheight() - self.height - 60 
        self.geometry(f'{self.width}x{self.height}+{x}+{y}')

    def update_wave(self):
        """Continuous mathematical animation loop for the waveform."""
        if self.session_active:
            self.phase += 0.2
            amplitude_mult = 1.0
            speed_mult = 1.0
            
            if self.animation_state == "Listening":
                amplitude_mult = 28.0 # High spiky waves dynamically jumping
                speed_mult = 2.0
            elif self.animation_state == "Processing":
                amplitude_mult = 16.0 # Medium jittery processing lines
                speed_mult = 3.0
            elif self.animation_state == "Waiting":
                amplitude_mult = 2.0 # Flat breathing line
                speed_mult = 0.5
            elif self.animation_state == "Quiet":
                amplitude_mult = 0.0 # Pure dead flat line
                
            for idx, line_id in enumerate(self.wave_lines):
                new_coords = []
                for i, x in enumerate(self.x_coords):
                    # Bell curve envelope so center jumps highest, edges stay pinned to the canvas walls
                    envelope = math.sin((i / (self.num_points - 1)) * math.pi)
                    
                    # Generate sine wave turbulence across the line segments
                    noise = math.sin(self.phase * speed_mult + (i * 0.5) + (idx * 0.3)) * random.uniform(0.8, 1.2)
                    y = 40 + (noise * amplitude_mult * envelope)
                    new_coords.extend([x, y])
                    
                self.wave_canvas.coords(line_id, *new_coords)
                
        # Loop at ultra-fast 40ms intervals (~25FPS) to keep animation liquid smooth
        self.after(40, self.update_wave)

    def submit_text(self, event=None):
        cmd = self.text_entry.get().strip()
        if cmd:
            self.text_entry.delete(0, "end")
            self.live_transcript.configure(text=f'"{cmd}"')
            text_command_queue.put(cmd)

    def switch_mode(self, new_mode):
        if new_mode == "Search Mode":
            self.mode_toggle.pack_forget() # hide mode toggle cleanly to make room
            self.input_frame.pack(pady=0)
            self.text_entry.pack(side="left", padx=5)
            self.enter_btn.pack(side="left")
            self.mode_toggle.pack(side="bottom", pady=5)
            self.animation_state = "Quiet"
            self.status_label.configure(text="Manual Search Mode")
        else:
            self.input_frame.pack_forget()
            self.status_label.configure(text="What can I help you with?")
            self.animation_state = "Waiting"

    def show_popup(self, title, link):
        """Creates the iTunes style 'Now Playing' / Results pop up."""
        popup = ctk.CTkToplevel(self)
        popup.title("Mira Link Result")
        popup.geometry("450x120")
        popup.attributes('-topmost', True)
        popup.overrideredirect(True) # Frosted glass card style!
        
        # Very dark gray, resembling glassy transparent dark cards
        popup.configure(fg_color="#1a1a1a")
        
        popup.update_idletasks()
        # Spawn EXACTLY ABOVE the main window center!
        x = self.winfo_x() + (self.width // 2) - 225
        y = self.winfo_y() - 130 # Spawn it perfectly floating above 10px in empty space
        popup.geometry(f"+{x}+{y}")
        
        # Layout inside the pop-up panel
        lbl = ctk.CTkLabel(popup, text=title, font=("Inter", 16, "bold"), wraplength=400)
        lbl.pack(pady=(15, 5))
        
        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack()
        
        btn = ctk.CTkButton(btn_frame, text="Open Result/Play", corner_radius=20, width=150, command=lambda: webbrowser.open(link))
        btn.pack(side="left", padx=10)
        
        # We need a custom dismiss button since the normal application top-bar logic was purged
        close_btn = ctk.CTkButton(btn_frame, text="Dismiss Card", width=100, fg_color="#333333", hover_color="#555555", corner_radius=20, command=popup.destroy)
        close_btn.pack(side="left", padx=10)

    def check_queue(self):
        try:
            while True:
                msg = msg_queue.get_nowait()
                if msg["type"] == "SHOW":
                    self.deiconify()  
                    self.attributes('-topmost', True) 
                    self.live_transcript.configure(text="")
                    self.animation_state = "Waiting"
                elif msg["type"] == "STATUS":
                    # We hook animation states dynamically!
                    if "Listening" in msg["text"]:
                        self.animation_state = "Listening"
                    elif "Processing" in msg["text"]:
                        self.animation_state = "Processing"
                    elif "Waiting" in msg["text"]:
                        self.animation_state = "Waiting"
                elif msg["type"] == "LOG":
                    clean_text = msg["text"].replace("Mira: ", "").replace("You (Voice): ", "").replace("You (Typed): ", "")
                    # Wrap text and enclose in quotes Siri Dribbble-style
                    self.live_transcript.configure(text=f'"{clean_text}"')
                    if "Mira:" in msg["text"]:
                        self.animation_state = "Listening" # Oscillate dynamically while talking
                elif msg["type"] == "POPUP":
                    self.show_popup(msg["title"], msg["link"])
                elif msg["type"] == "HIDE":
                    self.withdraw()
        except queue.Empty:
            pass
        finally:
            self.after(50, self.check_queue)


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
            msg_queue.put({"type": "STATUS", "text": "Locating YTM..."})
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
                    msg_queue.put({"type": "POPUP", "title": f"iTunes/YTM: {title} by {artists}", "link": watch_url})
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
        msg_queue.put({"type": "STATUS", "text": "Searching..."})
        try:
            results = wikipedia.search(command)
            if not results:
                speak("I couldn't find anything online about that.")
            else:
                best_match = results[0]
                page = wikipedia.page(best_match, auto_suggest=False)
                # Spawn information window 
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
        msg_queue.put({"type": "STATUS", "text": "Waiting..."})
    
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

                msg_queue.put({"type": "STATUS", "text": "Listening..."})
                try:
                    audio = recognizer.listen(source, timeout=1.5, phrase_time_limit=10)
                except sr.WaitTimeoutError:
                    continue 

                msg_queue.put({"type": "STATUS", "text": "Processing..."})
                
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
                    msg_queue.put({"type": "STATUS", "text": "Service offline."})
                    speak("Voice service offline.")
                    app.session_active = False
                    break
                    
    except Exception as e:
        msg_queue.put({"type": "STATUS", "text": "Error."})
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
