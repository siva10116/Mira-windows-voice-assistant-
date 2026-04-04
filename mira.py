# lllll
import pyttsx3
import keyboard
import threading
import time
import queue
import customtkinter as ctk
import tkinter as tk
import pythoncom
import webbrowser
from ytmusicapi import YTMusic
import random
import math
import pywinstyles
import os
from google import genai

# Setup Gemini API (Replace the string or use environment variable)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyCJMo4e87F3-P374JoE23gYiI0o_H97n30")
gemini_client = None
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

msg_queue = queue.Queue()
text_command_queue = queue.Queue()

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class MiraApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Mira Assistant")
        self.width = 560
        self.height = 190
        self.attributes('-topmost', True)
        self.overrideredirect(True)
        self.configure(fg_color="#18181A")
        
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        self.x_pos = (screen_width - self.width) // 2
        self.target_y = screen_height - self.height - 80 
        self.hidden_y = screen_height + 50
        
        self.current_y = self.hidden_y
        self.geometry(f'{self.width}x{self.height}+{self.x_pos}+{self.current_y}')
        
        try:
            import pywinstyles
            pywinstyles.apply_style(self, "transparent")
        except:
            pass

        self.border_frame = ctk.CTkFrame(self, fg_color="transparent", border_width=1, border_color="#333333", corner_radius=15)
        self.border_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        self.main_content = ctk.CTkFrame(self.border_frame, fg_color="transparent", corner_radius=14)
        self.main_content.pack(fill="both", expand=True, padx=1, pady=1)

        self.top_section = ctk.CTkFrame(self.main_content, fg_color="transparent")
        self.top_section.pack(fill="both", expand=True, padx=20, pady=(20, 5))

        self.wave_frame = ctk.CTkFrame(self.top_section, fg_color="transparent", width=220)
        self.wave_frame.pack(side="left", fill="y", padx=(0, 20))
        self.wave_frame.pack_propagate(False)
        
        import tkinter as tk
        self.canvas_bg = "#18181A" 
        self.wave_canvas = tk.Canvas(self.wave_frame, width=220, height=90, bg=self.canvas_bg, highlightthickness=0)
        self.wave_canvas.place(relx=0.5, rely=0.5, anchor="center") 
        
        self.num_points = 50 
        self.wave_width = 200
        self.x_coords = [int(i * (self.wave_width / (self.num_points - 1))) for i in range(self.num_points)]
        self.wave_lines = []
        
        colors = ["#19AEE3", "#E52C9F", "#44C65D", "#F5AA25"]
        self.bloom_layers = [(6, 0.4), (2, 1.0)]
        for color in colors:
            for width, _ in self.bloom_layers:
                coords = []
                for x in self.x_coords:
                    coords.extend([x, 45])
                line_id = self.wave_canvas.create_line(*coords, fill=color, width=width, smooth=True, capstyle="round")
                self.wave_lines.append(line_id)

        self.right_col = ctk.CTkFrame(self.top_section, fg_color="transparent")
        self.right_col.pack(side="left", fill="both", expand=True)

        self.status_label = ctk.CTkLabel(self.right_col, text="Waiting...", font=("Inter", 20, "bold"), text_color="#ffffff")
        self.status_label.pack(anchor="w", pady=(0, 4))
        
        self.live_transcript = ctk.CTkLabel(self.right_col, text='"Online."', font=("Inter", 14), text_color="#A0A0A0", wraplength=280, justify="left")
        self.live_transcript.pack(anchor="w", pady=(0, 10))

        self.input_row = ctk.CTkFrame(self.right_col, fg_color="transparent")
        self.input_row.pack(fill="x", side="bottom")
        
        self.text_entry = ctk.CTkEntry(self.input_row, height=36, placeholder_text="Type or Speak...", 
                                       border_width=1, border_color="#3A3A3D", corner_radius=18, font=("Inter", 13), fg_color="#2A2A2D", text_color="#ffffff")
        self.text_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.text_entry.bind("<Return>", self.submit_text)
        
        self.tools_frame = ctk.CTkFrame(self.input_row, fg_color="#2A2A2D", height=36, corner_radius=18, border_width=1, border_color="#3A3A3D")
        self.tools_frame.pack(side="right")
        
        self.btn_settings = ctk.CTkButton(self.tools_frame, text="⚙️", width=36, height=36, corner_radius=18, fg_color="transparent", hover_color="#3E3E42", font=("Inter", 16))
        self.btn_settings.pack(side="left", padx=(2,0))
        
        self.btn_sep = ctk.CTkFrame(self.tools_frame, width=1, height=18, fg_color="#454549")
        self.btn_sep.pack(side="left", pady=9, padx=2)
        
        self.btn_mic = ctk.CTkButton(self.tools_frame, text="🎤", width=36, height=36, corner_radius=18, fg_color="transparent", hover_color="#3E3E42", font=("Inter", 14), text_color="#A259FF")
        self.btn_mic.pack(side="left", padx=(0,2))

        self.bottom_bar = ctk.CTkFrame(self.main_content, fg_color="transparent", height=30)
        self.bottom_bar.pack(fill="x", side="bottom", padx=20, pady=(0, 10))
        
        self.status_sep = ctk.CTkFrame(self.main_content, height=1, fg_color="#333333")
        self.status_sep.pack(fill="x", side="bottom", padx=20, pady=(0, 5))
        
        self.bottom_status_title = ctk.CTkLabel(self.bottom_bar, text="Mira Status: ", font=("Inter", 12), text_color="#A0A0A0")
        self.bottom_status_title.pack(side="left")
        
        self.bottom_status_text = ctk.CTkLabel(self.bottom_bar, text="Ready", font=("Inter", 12), text_color="#A0A0A0")
        self.bottom_status_text.pack(side="left", padx=(5, 0))

        self.star_icon = ctk.CTkLabel(self.bottom_bar, text="✨", font=("Inter", 14), text_color="#A0A0A0")
        self.star_icon.pack(side="right")

        self.animation_state = "Waiting"
        self.phase = 0.0
        
        self.spring_velocity = 0.0
        self.target_amplitude = 1.0
        self.current_amplitude = 1.0
        
        self.session_active = False
        self.is_visible = False
        self.animating_slide = False
        
        self.check_queue()
        self.update_wave()
        self.withdraw()

    def slide_animation(self):
        if not self.animating_slide:
            return
            
        target = self.target_y if self.is_visible else self.hidden_y
        
        stiffness = 0.15
        damping = 0.75
        
        force = (target - self.current_y) * stiffness
        self.spring_velocity = (self.spring_velocity + force) * damping
        self.current_y += self.spring_velocity
        
        if abs(target - self.current_y) < 0.5 and abs(self.spring_velocity) < 0.5:
            self.current_y = target
            self.geometry(f'{self.width}x{self.height}+{self.x_pos}+{int(self.current_y)}')
            self.animating_slide = False
            if not self.is_visible:
                self.withdraw()
            return
            
        self.geometry(f'{self.width}x{self.height}+{self.x_pos}+{int(self.current_y)}')
        self.after(16, self.slide_animation)

    def toggle_visibility(self):
        if not self.is_visible:
            self.deiconify()
            self.attributes('-topmost', True)
            self.is_visible = True
            self.animating_slide = True
            self.slide_animation()
            
            self.status_label.configure(text="Waiting...")
            self.bottom_status_text.configure(text="Ready", text_color="#A0A0A0")
        else:
            self.is_visible = False
            self.animating_slide = True
            self.slide_animation()

    def update_wave(self):
        import math
        if self.session_active and self.is_visible:
            self.phase += 0.15
            
            target_amp = 1.0
            speed_mult = 1.0
            
            if self.animation_state == "Listening":
                target_amp = 30.0
                speed_mult = 2.5
            elif self.animation_state == "Processing":
                target_amp = 15.0
                speed_mult = 3.5
            elif self.animation_state == "Waiting":
                target_amp = 5.0
                speed_mult = 0.8
            elif self.animation_state == "Quiet":
                target_amp = 0.0 
                
            self.current_amplitude += (target_amp - self.current_amplitude) * 0.1
                
            line_idx = 0
            for color_idx in range(4):
                for bloom_idx in range(2):
                    line_id = self.wave_lines[line_idx]
                    layer_offset = (color_idx * 1.5)
                    
                    new_coords = []
                    for i, x in enumerate(self.x_coords):
                        envelope = math.sin((i / (self.num_points - 1)) * math.pi)
                        noise1 = math.sin(self.phase * speed_mult + (i * 0.15) + layer_offset) 
                        noise2 = math.cos(self.phase * speed_mult * 0.7 + (i * 0.25))
                        
                        combined_noise = (noise1 + noise2) * 0.5 
                        
                        y = 45 + (combined_noise * self.current_amplitude * envelope)
                        new_coords.extend([x, y])
                        
                    self.wave_canvas.coords(line_id, *new_coords)
                    line_idx += 1
                
        self.after(30, self.update_wave)

    def submit_text(self, event=None):
        cmd = self.text_entry.get().strip()
        if cmd:
            self.text_entry.delete(0, "end")
            self.live_transcript.configure(text=f'"{cmd}"')
            self.status_label.configure(text="Processing...")
            import queue
            text_command_queue.put(cmd)

    def show_popup(self, title, link):
        popup = ctk.CTkToplevel(self)
        popup.title("Mira Notify")
        popup.geometry("360x90")
        popup.attributes('-topmost', True)
        popup.overrideredirect(True) 
        
        popup.configure(fg_color="#18181F")
        try:
            import pywinstyles
            pywinstyles.apply_style(popup, "acrylic")
        except:
            pass
            
        popup.update_idletasks()
        
        x = self.x_pos + (self.width // 2) - 180 
        y = self.target_y - 110
        popup.geometry(f"+{x}+{y}")
        
        content = ctk.CTkFrame(popup, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=15, pady=15)
        
        lbl = ctk.CTkLabel(content, text=title, font=("Outfit", 15, "bold"), text_color="#ffffff", wraplength=200, anchor="w", justify="left")
        lbl.pack(side="left", fill="x", expand=True)
        
        import webbrowser
        btn = ctk.CTkButton(content, text="Open", corner_radius=15, width=60, height=30, 
                            font=("Inter", 12, "bold"), fg_color="#ffffff", text_color="#000000", hover_color="#dddddd", 
                            command=lambda: webbrowser.open(link))
        btn.pack(side="right", padx=(5, 0))
        
        popup.after(8000, popup.destroy)

    def check_queue(self):
        import queue
        try:
            while True:
                msg = msg_queue.get_nowait()
                if msg["type"] == "SHOW":
                    if not self.is_visible:
                        self.toggle_visibility()
                    self.live_transcript.configure(text="")
                    self.animation_state = "Waiting"
                elif msg["type"] == "STATUS":
                    self.status_label.configure(text=msg["text"])
                    self.bottom_status_text.configure(text=msg["text"], text_color="#A0A0A0")
                    if "Listening" in msg["text"]:
                        self.animation_state = "Listening"
                    elif "Processing" in msg["text"]:
                        self.animation_state = "Processing"
                    elif "Thinking" in msg["text"]:
                        self.animation_state = "Processing"
                    elif "Waiting" in msg["text"]:
                        self.animation_state = "Waiting"
                elif msg["type"] == "LOG":
                    clean_text = msg["text"].replace("Mira: ", "").replace("You (Voice): ", "").replace("You (Typed): ", "")
                    if "Gemini Error" in msg["text"] or "Error:" in msg["text"]:
                        self.bottom_status_text.configure(text="Error Communicating with Gemini", text_color="#FF9500")
                        self.status_label.configure(text="Error")
                        self.animation_state = "Waiting"
                    elif "Mira:" in msg["text"]:
                        self.status_label.configure(text="Mira")
                        self.live_transcript.configure(text=f'"{clean_text}"')
                        self.animation_state = "Listening" 
                    else:
                        self.live_transcript.configure(text=f'"{clean_text}"')
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
        msg_queue.put({"type": "STATUS", "text": "Thinking..."})
        try:
            if not gemini_client:
                speak("Please set your Gemini API key in the code to enable AI answers.")
            else:
                # Add a system prompt hint so it speaks well on a voice assistant
                prompt = f"Answer concisely in 1 to 3 sentences suitable for a voice assistant to read aloud: {command}"
                response = gemini_client.models.generate_content(
                    model='gemini-1.5-flash',
                    contents=prompt
                )
                
                # Clean up markdown asterisks for the TTS engine
                gemini_response = response.text.replace('*', '').replace('#', '')
                speak(gemini_response)
        except Exception as e:
            msg_queue.put({"type": "LOG", "text": f"Gemini Error: {e}"})
            speak("Encountered an error communicating with Gemini.")
            
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
