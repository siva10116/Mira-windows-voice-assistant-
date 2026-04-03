
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
import pywinstyles

msg_queue = queue.Queue()
text_command_queue = queue.Queue()

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class MiraApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Mira Assistant")
        # Classic Mac Siri dimensions (vertical panel)
        self.width = 320
        self.height = 600
        self.attributes('-topmost', True)
        self.overrideredirect(True) # borderless
        
        # We use a very dark grey to give Windows Acrylic something to blur without making it totally invisible
        self.configure(fg_color="#121212")
        
        # Start completely hidden off-screen (top right, above the screen)
        self.target_y = 40 # The resting Y position (just below menu bar)
        self.current_y = -self.height - 100
        self.x_pos = self.winfo_screenwidth() - self.width - 20 # 20px from right edge
        
        self.geometry(f'{self.width}x{self.height}+{self.x_pos}+{self.current_y}')
        
        # Apply True Glassmorphism
        try:
            pywinstyles.apply_style(self, "acrylic")
        except:
            pass

        # Top Section: "Siri" prompt
        self.status_label = ctk.CTkLabel(self, text="What can I help you with?", font=("Outfit", 20, "bold"), text_color="#ffffff", wraplength=280)
        self.status_label.pack(pady=(40, 5), padx=20)
        
        self.live_transcript = ctk.CTkLabel(self, text="", font=("Inter", 16), text_color="#a1a1aa", wraplength=280, justify="center")
        self.live_transcript.pack(pady=10, padx=20)

        # Mode Toggles & Sleek Entry - Moved higher up to leave bottom strictly for waves
        self.input_container = ctk.CTkFrame(self, fg_color="transparent")
        self.input_container.pack(fill="x", pady=20, padx=20)
        
        self.input_frame = ctk.CTkFrame(self.input_container, fg_color="transparent")
        self.input_frame.pack(pady=0)
        self.text_entry = ctk.CTkEntry(self.input_frame, width=220, height=35, placeholder_text="Ask Mira...", 
                                       border_width=1, corner_radius=15, font=("Inter", 13), fg_color="#1f1f26")
        self.text_entry.pack(side="left", padx=5)
        self.text_entry.bind("<Return>", self.submit_text)
        
        self.enter_btn = ctk.CTkButton(self.input_frame, text="Ask", width=50, height=35, corner_radius=15, 
                                       font=("Inter", 12, "bold"), command=self.submit_text)
        self.enter_btn.pack(side="left")

        # --- WAVEFORM VISUALS AT THE BOTTOM ---
        self.canvas_bg = "#121212" 
        self.wave_canvas = tk.Canvas(self, width=self.width, height=120, bg=self.canvas_bg, highlightthickness=0)
        self.wave_canvas.pack(side="bottom", fill="x", pady=0) # Pinned to the hard bottom edge
        
        # Mac Siri precise colors: Cyan, Magenta, Green, Yellow, White Core
        self.num_points = 60 
        self.x_coords = [int(i * (self.width / (self.num_points - 1))) for i in range(self.num_points)]
        self.wave_lines = []
        
        colors = ["#19AEE3", "#E52C9F", "#44C65D", "#F5AA25", "#ffffff"]
        widths = [4, 4, 4, 3, 2] # Thinner, more intense strings of light
        
        for color, width in zip(colors, widths):
            coords = []
            for x in self.x_coords:
                coords.extend([x, 60])
            # Smooth bezier-like multipoint
            line_id = self.wave_canvas.create_line(*coords, fill=color, width=width, smooth=True, capstyle="round")
            self.wave_lines.append(line_id)

        self.animation_state = "Waiting"
        self.phase = 0.0
        
        self.session_active = False
        self.is_visible = False
        self.animating_slide = False
        
        self.check_queue()
        self.update_wave()
        self.withdraw()

    def slide_animation(self):
        """Smooth ease-out sliding animation loop for the window."""
        if not self.animating_slide:
            return
            
        target = self.target_y if self.is_visible else -self.height - 50
        diff = target - self.current_y
        
        if abs(diff) < 2:
            self.current_y = target
            self.geometry(f'{self.width}x{self.height}+{self.x_pos}+{int(self.current_y)}')
            self.animating_slide = False
            if not self.is_visible:
                self.withdraw() # Hide it fully when off-screen
            return
            
        # Ease out scaling
        self.current_y += diff * 0.25 
        self.geometry(f'{self.width}x{self.height}+{self.x_pos}+{int(self.current_y)}')
        self.after(16, self.slide_animation) # 60fps sliding

    def toggle_visibility(self):
        if not self.is_visible:
            self.deiconify()
            self.attributes('-topmost', True)
            self.is_visible = True
            self.animating_slide = True
            self.slide_animation()
        else:
            self.is_visible = False
            self.animating_slide = True
            self.slide_animation()

    def update_wave(self):
        """Continuous mathematical animation loop for the waveform."""
        if self.session_active and self.is_visible:
            self.phase += 0.12
            amplitude_mult = 1.0
            speed_mult = 1.0
            
            if self.animation_state == "Listening":
                amplitude_mult = 35.0
                speed_mult = 2.2
            elif self.animation_state == "Processing":
                amplitude_mult = 15.0
                speed_mult = 3.5
            elif self.animation_state == "Waiting":
                amplitude_mult = 4.0
                speed_mult = 0.8
            elif self.animation_state == "Quiet":
                amplitude_mult = 0.0 
                
            for idx, line_id in enumerate(self.wave_lines):
                new_coords = []
                for i, x in enumerate(self.x_coords):
                    # Bell Curve
                    envelope = math.sin((i / (self.num_points - 1)) * math.pi)
                    
                    # Offsets to create crossing strands
                    layer_offset = (idx * 1.5) 
                    noise1 = math.sin(self.phase * speed_mult + (i * 0.15) + layer_offset) 
                    noise2 = math.cos(self.phase * speed_mult * 0.7 + (i * 0.25))
                    
                    combined_noise = (noise1 + noise2) * 0.5 
                    
                    y = 60 + (combined_noise * amplitude_mult * envelope) # center at 60px height
                    new_coords.extend([x, y])
                    
                self.wave_canvas.coords(line_id, *new_coords)
                
        self.after(30, self.update_wave)

    def submit_text(self, event=None):
        cmd = self.text_entry.get().strip()
        if cmd:
            self.text_entry.delete(0, "end")
            self.live_transcript.configure(text=f'"{cmd}"')
            text_command_queue.put(cmd)


    def show_popup(self, title, link):
        """Creates an ultra premium 'Toast' style Result pop up sliding from right."""
        popup = ctk.CTkToplevel(self)
        popup.title("Mira Notify")
        popup.geometry("320x130")
        popup.attributes('-topmost', True)
        popup.overrideredirect(True) 
        
        popup.configure(fg_color="#181818")
        
        try:
            pywinstyles.apply_style(popup, "acrylic")
        except:
            pass
            
        popup.update_idletasks()
        
        # Spawn relative to the main Siri window
        x = self.winfo_x() - 340 # Spawn to the left of the assistant panel
        y = self.target_y # align with top
        popup.geometry(f"+{x}+{y}")
        
        lbl = ctk.CTkLabel(popup, text=title, font=("Outfit", 16, "bold"), text_color="#ffffff", wraplength=280)
        lbl.pack(pady=(15, 10), padx=10)
        
        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack()
        
        btn = ctk.CTkButton(btn_frame, text="Open Link", corner_radius=15, width=120, height=30, 
                            font=("Inter", 13, "bold"), command=lambda: webbrowser.open(link))
        btn.pack(side="left", padx=5)
        
        close_btn = ctk.CTkButton(btn_frame, text="Dismiss", width=80, height=30, 
                                  font=("Inter", 13), fg_color="#333333", hover_color="#555555", corner_radius=15, 
                                  command=popup.destroy)
        close_btn.pack(side="left", padx=5)

    def check_queue(self):
        try:
            while True:
                msg = msg_queue.get_nowait()
                if msg["type"] == "SHOW":
                    if not self.is_visible:
                        self.toggle_visibility()
                    self.live_transcript.configure(text="")
                    self.animation_state = "Waiting"
                elif msg["type"] == "STATUS":
                    if "Listening" in msg["text"]:
                        self.animation_state = "Listening"
                    elif "Processing" in msg["text"]:
                        self.animation_state = "Processing"
                    elif "Waiting" in msg["text"]:
                        self.animation_state = "Waiting"
                elif msg["type"] == "LOG":
                    clean_text = msg["text"].replace("Mira: ", "").replace("You (Voice): ", "").replace("You (Typed): ", "")
                    self.live_transcript.configure(text=f'"{clean_text}"')
                    if "Mira:" in msg["text"]:
                        self.animation_state = "Listening" 
                elif msg["type"] == "POPUP":
                    self.show_popup(msg["title"], msg["link"])
                elif msg["type"] == "HIDE":
                    if self.is_visible:
                        self.toggle_visibility()
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
                    msg_queue.put({"type": "POPUP", "title": f"{title} — {artists}", "link": watch_url})
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
    speak("Online.")
    msg_queue.put({"type": "STATUS", "text": "Waiting..."})
    
    try:
        while app.session_active:
            try:
                typed_cmd = text_command_queue.get(timeout=0.2)
                msg_queue.put({"type": "LOG", "text": f"You: {typed_cmd}"})
                msg_queue.put({"type": "STATUS", "text": "Processing..."})
                
                status = process_user_intent(typed_cmd.lower(), app, speak)
                if status == "EXIT":
                    app.session_active = False
                    break
                    
                msg_queue.put({"type": "STATUS", "text": "Waiting..."})
            except queue.Empty:
                pass
                    
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
        msg_queue.put({"type": "HIDE"}) # explicitly queue a hide command immediately

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
