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
from openai import OpenAI
from typing import List, Tuple
import tkinter.font as tkfont
import vlc
import yt_dlp
import requests
from io import BytesIO
from PIL import Image

# Setup OpenRouter AI (Qwen)
OPENROUTER_API_KEY = "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"
ai_client = None
if OPENROUTER_API_KEY:
    ai_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )

msg_queue = queue.Queue()
text_command_queue = queue.Queue()

# Theme Configuration
class ThemeManager:
    def __init__(self):
        self.current_theme = "dark"  # "dark" or "light"
        self.themes = {
            "dark": {
                "bg_primary": "#0D0D0F",
                "bg_secondary": "#1A1A1E",
                "bg_tertiary": "#2D2D31",
                "bg_hover": "#3E3E42",
                "text_primary": "#FFFFFF",
                "text_secondary": "#8E8E93",
                "text_muted": "#636366",
                "accent": "#4361EE",
                "accent_hover": "#5A75FF",
                "error": "#FF9F0A",
                "success": "#34C759",
                "border": "#2D2D31",
                "separator": "#38383A",
                "wave_colors": ["#9D4EDD", "#5A189A", "#3A0CA3", "#4361EE", "#4895EF", "#4CC9F0", "#F72585", "#B5179E", "#7209B7", "#560BAD"]
            },
            "light": {
                "bg_primary": "#F5F5F7",
                "bg_secondary": "#FFFFFF",
                "bg_tertiary": "#E8E8ED",
                "bg_hover": "#D2D2D7",
                "text_primary": "#1D1D1F",
                "text_secondary": "#6E6E73",
                "text_muted": "#86868B",
                "accent": "#007AFF",
                "accent_hover": "#0051D5",
                "error": "#FF3B30",
                "success": "#34C759",
                "border": "#D2D2D7",
                "separator": "#C6C6C8",
                "wave_colors": ["#007AFF", "#5856D6", "#AF52DE", "#FF2D55", "#FF9500", "#FFCC00", "#4CD964", "#5AC8FA", "#007AFF", "#5856D6"]
            }
        }
    
    def get_colors(self):
        return self.themes[self.current_theme]
    
    def toggle_theme(self):
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        return self.current_theme

theme_manager = ThemeManager()

class WaveformAnimation:
    """Advanced Siri-like waveform animation with theme support"""
    def __init__(self, canvas, width=220, height=90):
        self.canvas = canvas
        self.width = width
        self.height = height
        self.num_points = 60
        self.phase = 0.0
        self.amplitude = 5.0
        self.frequency = 1.0
        self.speed = 0.15
        self.wave_lines = []
        self.x_coords = [int(i * (width / (self.num_points - 1))) for i in range(self.num_points)]
        self.setup_waves()
    
    def setup_waves(self):
        """Create multiple wave layers"""
        colors = theme_manager.get_colors()["wave_colors"]
        for i, color in enumerate(colors):
            width = 3 if i < 5 else 2
            coords = []
            for x in self.x_coords:
                coords.extend([x, self.height // 2])
            line_id = self.canvas.create_line(
                *coords, fill=color, width=width, smooth=True, capstyle="round"
            )
            self.wave_lines.append({
                'id': line_id, 'color': color, 'width': width,
                'offset': i * 0.3, 'frequency': 1.0 + (i * 0.1)
            })
    
    def update_colors(self):
        """Update wave colors when theme changes"""
        colors = theme_manager.get_colors()["wave_colors"]
        for i, layer in enumerate(self.wave_lines):
            if i < len(colors):
                self.canvas.itemconfig(layer['id'], fill=colors[i])
    
    def update(self, state: str):
        """Update waveform based on state"""
        self.phase += self.speed
        
        if state == "Listening":
            target_amplitude, target_speed = 35.0, 0.3
        elif state == "Processing":
            target_amplitude, target_speed = 20.0, 0.25
        elif state == "Speaking":
            target_amplitude, target_speed = 25.0, 0.2
        else:
            target_amplitude, target_speed = 3.0, 0.1
        
        self.amplitude += (target_amplitude - self.amplitude) * 0.1
        self.speed += (target_speed - self.speed) * 0.1
        
        for layer in self.wave_lines:
            new_coords = []
            for i, x in enumerate(self.x_coords):
                t = i / (self.num_points - 1)
                wave1 = math.sin(self.phase * layer['frequency'] * 2 + t * math.pi * 2 + layer['offset'])
                wave2 = math.sin(self.phase * 1.5 + t * math.pi * 4 + layer['offset'] * 2) * 0.5
                wave3 = math.cos(self.phase * 0.8 + t * math.pi * 3) * 0.3
                envelope = math.sin(t * math.pi)
                y_offset = (wave1 + wave2 + wave3) * self.amplitude * envelope
                y = self.height // 2 + y_offset
                new_coords.extend([x, y])
            self.canvas.coords(layer['id'], *new_coords)

class MusicPlayerFrame(ctk.CTkFrame):
    """Integrated native music player using VLC"""
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.current_song = None
        self.is_playing = False
        self.vlc_instance = vlc.Instance()
        self.player = self.vlc_instance.media_player_new()
        self.duration = 0
        self.playlist_queue = []
        self.current_idx = 0
        self.setup_ui()
    
    def setup_ui(self):
        colors = theme_manager.get_colors()
        self.player_container = ctk.CTkFrame(self, fg_color=colors["bg_tertiary"], corner_radius=12)
        self.player_container.pack(fill="x", padx=12, pady=(0, 12))
        self.info_frame = ctk.CTkFrame(self.player_container, fg_color="transparent")
        self.info_frame.pack(fill="x", padx=15, pady=15)
        
        self.album_art = ctk.CTkLabel(
            self.info_frame, text="🎵", font=("SF Pro Display", 24),
            width=60, height=60, corner_radius=8, fg_color=colors["bg_hover"],
            text_color=colors["text_muted"]
        )
        self.album_art.pack(side="left", padx=(0, 15))
        
        self.song_info_frame = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        self.song_info_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.full_title = "Loading..."
        self.full_artist = "—"
        self.title_offset = 0
        self.artist_offset = 0
        
        self.song_title = ctk.CTkLabel(
            self.song_info_frame, text="Loading...",
            font=("SF Pro Display", 15, "bold"), text_color=colors["text_primary"],
            anchor="w", justify="left", width=340
        )
        self.song_title.pack(anchor="w", pady=(0, 4))
        self.song_artist = ctk.CTkLabel(
            self.song_info_frame, text="—", font=("SF Pro Display", 13),
            text_color=colors["text_secondary"], anchor="w", justify="left", width=340
        )
        self.song_artist.pack(anchor="w")
        
        self.close_btn = ctk.CTkButton(
            self.info_frame, text="✕", width=28, height=28, corner_radius=14,
            fg_color="transparent", hover_color=colors["bg_hover"],
            font=("SF Pro Display", 14), text_color=colors["text_muted"], command=self.hide_player
        )
        self.close_btn.pack(side="right")
        
        self.progress_slider = ctk.CTkSlider(
            self.player_container, width=300, height=14,
            fg_color=colors["bg_hover"], progress_color=colors["accent"],
            button_color=colors["text_primary"], button_hover_color=colors["text_muted"],
            command=self.seek_song
        )
        self.progress_slider.pack(fill="x", padx=15, pady=(0, 12))
        self.progress_slider.set(0)
        
        self.controls_frame = ctk.CTkFrame(self.player_container, fg_color="transparent")
        self.controls_frame.pack(fill="x", padx=15, pady=(0, 15))
        self.current_time = ctk.CTkLabel(self.controls_frame, text="0:00", font=("SF Pro Display", 11), text_color=colors["text_muted"])
        self.current_time.pack(side="left")
        self.total_time = ctk.CTkLabel(self.controls_frame, text="0:00", font=("SF Pro Display", 11), text_color=colors["text_muted"])
        self.total_time.pack(side="right")
        
        self.btn_frame = ctk.CTkFrame(self.controls_frame, fg_color="transparent")
        self.btn_frame.pack(fill="x", pady=(8, 0))
        self.btn_prev = ctk.CTkButton(
            self.btn_frame, text="⏪", width=36, height=36, corner_radius=18,
            fg_color="transparent", hover_color=colors["bg_hover"],
            font=("SF Pro Display", 16), text_color=colors["text_primary"], command=self.prev_song
        )
        self.btn_prev.pack(side="left", padx=(0, 20))
        self.btn_play = ctk.CTkButton(
            self.btn_frame, text="▶", width=48, height=48, corner_radius=24,
            fg_color=colors["accent"], hover_color=colors["accent_hover"],
            font=("SF Pro Display", 18), text_color="#FFFFFF", command=self.toggle_play
        )
        self.btn_play.pack(side="left", padx=20)
        self.btn_next = ctk.CTkButton(
            self.btn_frame, text="⏩", width=36, height=36, corner_radius=18,
            fg_color="transparent", hover_color=colors["bg_hover"],
            font=("SF Pro Display", 16), text_color=colors["text_primary"], command=self.next_song
        )
        self.btn_next.pack(side="left", padx=(20, 0))
        
        self.vol_slider = ctk.CTkSlider(
            self.btn_frame, width=80, height=8,
            fg_color=colors["bg_hover"], progress_color=colors["text_muted"],
            button_color=colors["text_muted"], button_hover_color=colors["text_primary"],
            command=self.set_volume
        )
        self.vol_slider.pack(side="right", padx=(20, 0), pady=(14, 0))
        self.vol_slider.set(1.0)
        
        self.pack_forget()
        self.update_progress_loop()

    def set_volume(self, value):
        if hasattr(self, 'player'):
            self.player.audio_set_volume(int(value * 100))

    def seek_song(self, value):
        length = self.player.get_length()
        if length > 0:
            self.player.set_time(int(length * value))

    def update_progress_loop(self):
        if self.is_playing and self.player.get_state() == vlc.State.Playing:
            time_ms = self.player.get_time()
            if time_ms > 0:
                length = self.player.get_length()
                if length > 0:
                    self.total_time.configure(text=f"{length//60000}:{(length//1000)%60:02d}")
                    self.current_time.configure(text=f"{time_ms//60000}:{(time_ms//1000)%60:02d}")
                    self.progress_slider.set(time_ms / length)
                    
                    if time_ms > length - 1500:
                        self.next_song()
                        
        # Marquee text logic
        if len(self.full_title) > 38:
            self.title_offset = (self.title_offset + 1) % (len(self.full_title) + 5)
            display = (self.full_title + "     " + self.full_title)[self.title_offset:self.title_offset+38]
            self.song_title.configure(text=display)
            
        if len(self.full_artist) > 42:
            self.artist_offset = (self.artist_offset + 1) % (len(self.full_artist) + 5)
            display = (self.full_artist + "     " + self.full_artist)[self.artist_offset:self.artist_offset+42]
            self.song_artist.configure(text=display)

        self.after(500, self.update_progress_loop)
    
    def show_player(self, title, artist, url, video_id=None):
        colors = theme_manager.get_colors()
        self.current_song = {"title": title, "artist": artist, "url": url}
        self.full_title = title
        self.full_artist = artist
        self.title_offset = 0
        self.artist_offset = 0
        self.song_title.configure(text=title if len(title) <= 38 else title[:38], text_color=colors["text_primary"])
        self.song_artist.configure(text="Loading stream...", text_color=colors["text_secondary"])
        self.album_art.configure(image=None, text="🎵")
        self.btn_play.configure(text="⏸")
        self.is_playing = True
        self.pack(fill="x", before=self.master.input_row if hasattr(self.master, 'input_row') else None)
        
        # Load stream in background
        threading.Thread(target=self._load_stream, args=(url, artist, video_id), daemon=True).start()
        
    def _load_stream(self, url, artist, video_id):
        if video_id:
            try:
                from ytmusicapi import YTMusic
                yt = YTMusic()
                data = yt.get_watch_playlist(videoId=video_id)
                self.playlist_queue = data.get("tracks", [])
                self.current_idx = 0
            except:
                pass

        try:
            ydl_opts = {'format': 'bestaudio/best', 'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                audio_url = info['url']
                thumbnail_url = info.get('thumbnail')
                
                if thumbnail_url:
                    response = requests.get(thumbnail_url)
                    img = Image.open(BytesIO(response.content))
                    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(60, 60))
                    self.album_art.configure(image=ctk_img, text="")
                
                media = self.vlc_instance.media_new(audio_url)
                self.player.set_media(media)
                self.player.play()
                self.full_artist = artist
                self.artist_offset = 0
                self.song_artist.configure(text=artist if len(artist) <= 42 else artist[:42])
        except Exception as e:
            self.full_artist = f"Error loading: {e}"
            self.song_artist.configure(text=self.full_artist)
    
    def hide_player(self):
        self.pack_forget()
        self.is_playing = False
        self.current_song = None
        self.player.stop()
        self.playlist_queue = []
    
    def toggle_play(self):
        if self.is_playing:
            self.btn_play.configure(text="▶")
            self.player.pause()
            self.is_playing = False
        else:
            self.btn_play.configure(text="⏸")
            self.player.play()
            self.is_playing = True
    
    def prev_song(self):
        if self.playlist_queue and self.current_idx > 0:
            self.current_idx -= 1
            self._play_queue_track()
        else:
            time_ms = self.player.get_time()
            self.player.set_time(max(0, time_ms - 10000))
    
    def next_song(self):
        if self.playlist_queue and self.current_idx + 1 < len(self.playlist_queue):
            self.current_idx += 1
            self._play_queue_track()
        else:
            time_ms = self.player.get_time()
            self.player.set_time(time_ms + 10000)

    def _play_queue_track(self):
        self.player.stop()
        track = self.playlist_queue[self.current_idx]
        title = track.get("title", 'Unknown')
        artist = ", ".join([a.get("name", "") for a in track.get("artists", [])])
        video_id = track.get("videoId")
        self.full_title = title
        self.title_offset = 0
        self.full_artist = artist
        self.artist_offset = 0
        
        self.song_title.configure(text=title if len(title) <= 38 else title[:38])
        self.song_artist.configure(text="Loading stream...")
        threading.Thread(target=self._load_stream, args=(url, artist, None), daemon=True).start()
    
    def update_theme(self):
        colors = theme_manager.get_colors()
        self.player_container.configure(fg_color=colors["bg_tertiary"])
        self.album_art.configure(fg_color=colors["bg_hover"], text_color=colors["text_muted"])
        self.song_title.configure(text_color=colors["text_primary"])
        self.song_artist.configure(text_color=colors["text_secondary"])
        self.current_time.configure(text_color=colors["text_muted"])
        self.total_time.configure(text_color=colors["text_muted"])
        self.btn_play.configure(fg_color=colors["accent"], hover_color=colors["accent_hover"])
        self.btn_prev.configure(text_color=colors["text_primary"])
        self.btn_next.configure(text_color=colors["text_primary"])
        self.progress_slider.configure(fg_color=colors["bg_hover"], progress_color=colors["accent"])
        self.vol_slider.configure(fg_color=colors["bg_hover"], progress_color=colors["text_muted"], button_color=colors["text_muted"], button_hover_color=colors["text_primary"])

class MiraApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Mira Assistant")
        self.width = 580
        self.height = 200
        self.attributes('-topmost', True)
        self.overrideredirect(True)
        
        self.apply_theme()
        
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        self.x_pos = (screen_width - self.width) // 2
        self.target_y = screen_height - self.height - 100
        self.hidden_y = screen_height + 50

        self.current_y = self.hidden_y
        self.geometry(f'{self.width}x{self.height}+{self.x_pos}+{self.current_y}')

        try:
            pywinstyles.apply_style(self, "transparent")
        except:
            pass

        # Main container
        self.border_frame = ctk.CTkFrame(
            self, fg_color=theme_manager.get_colors()["bg_secondary"],
            border_width=0, corner_radius=20
        )
        self.border_frame.pack(fill="both", expand=True, padx=2, pady=2)

        # Top section
        self.top_section = ctk.CTkFrame(self.border_frame, fg_color="transparent")
        self.top_section.pack(fill="both", expand=True, padx=25, pady=(20, 10))

        # Waveform
        self.wave_frame = ctk.CTkFrame(self.top_section, fg_color="transparent", width=240)
        self.wave_frame.pack(side="left", fill="y", padx=(0, 25))
        self.wave_frame.pack_propagate(False)

        self.wave_canvas = tk.Canvas(
            self.wave_frame, width=240, height=90,
            bg=theme_manager.get_colors()["bg_secondary"], highlightthickness=0
        )
        self.wave_canvas.place(relx=0.5, rely=0.5, anchor="center")
        self.waveform = WaveformAnimation(self.wave_canvas)

        # Right column
        self.right_col = ctk.CTkFrame(self.top_section, fg_color="transparent")
        self.right_col.pack(side="left", fill="both", expand=True)

        # Status label
        self.status_label = ctk.CTkLabel(
            self.right_col, text="Waiting...",
            font=("SF Pro Display", 22, "bold"),
            text_color=theme_manager.get_colors()["text_primary"]
        )
        self.status_label.pack(anchor="w", pady=(0, 6))

        # Live transcript
        self.live_transcript = ctk.CTkLabel(
            self.right_col, text='"Online."',
            font=("SF Pro Display", 14),
            text_color=theme_manager.get_colors()["text_secondary"],
            wraplength=300, justify="left"
        )
        self.live_transcript.pack(anchor="w", pady=(0, 15))

        # Input row
        self.input_row = ctk.CTkFrame(self.right_col, fg_color="transparent")
        self.input_row.pack(fill="x", side="bottom")

        # Text entry
        self.text_entry = ctk.CTkEntry(
            self.input_row, height=42, placeholder_text="Type or Speak...",
            border_width=0, corner_radius=21,
            font=("SF Pro Display", 14),
            fg_color=theme_manager.get_colors()["bg_tertiary"],
            text_color=theme_manager.get_colors()["text_primary"],
            placeholder_text_color=theme_manager.get_colors()["text_muted"]
        )
        self.text_entry.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.text_entry.bind("<Return>", self.submit_text)

        # Tools frame
        self.tools_frame = ctk.CTkFrame(
            self.input_row, fg_color=theme_manager.get_colors()["bg_tertiary"],
            height=42, corner_radius=21, border_width=0
        )
        self.tools_frame.pack(side="right")

        # Theme toggle button
        self.btn_theme = ctk.CTkButton(
            self.tools_frame, text="", width=36, height=42,
            corner_radius=21, fg_color="transparent",
            hover_color=theme_manager.get_colors()["bg_hover"],
            font=("SF Pro Display", 16),
            text_color=theme_manager.get_colors()["text_primary"],
            command=self.toggle_theme
        )
        self.btn_theme.pack(side="left", padx=(2, 0))

        # Separator
        ctk.CTkFrame(self.tools_frame, width=1, height=20, fg_color=theme_manager.get_colors()["separator"]).pack(side="left", pady=11, padx=4)

        # Settings button
        self.btn_settings = ctk.CTkButton(
            self.tools_frame, text="⚙️", width=36, height=42,
            corner_radius=21, fg_color="transparent",
            hover_color=theme_manager.get_colors()["bg_hover"],
            font=("SF Pro Display", 16),
            text_color=theme_manager.get_colors()["text_primary"],
            command=self.open_settings
        )
        self.btn_settings.pack(side="left", padx=(0, 4))

        # Separator
        ctk.CTkFrame(self.tools_frame, width=1, height=20, fg_color=theme_manager.get_colors()["separator"]).pack(side="left", pady=11, padx=4)

        # Microphone button
        self.btn_mic = ctk.CTkButton(
            self.tools_frame, text="🎤", width=36, height=42,
            corner_radius=21, fg_color="transparent",
            hover_color=theme_manager.get_colors()["bg_hover"],
            font=("SF Pro Display", 16),
            text_color=theme_manager.get_colors()["text_primary"],
            command=self.toggle_mic
        )
        self.btn_mic.pack(side="left", padx=(0, 2))

        # Music Player (Integrated)
        self.music_player = MusicPlayerFrame(self.border_frame, fg_color="transparent")
        
        # Bottom separator
        self.status_sep = ctk.CTkFrame(
            self.border_frame, height=1,
            fg_color=theme_manager.get_colors()["separator"]
        )
        self.status_sep.pack(fill="x", side="bottom", padx=25, pady=(0, 8))

        # Bottom status bar
        self.bottom_bar = ctk.CTkFrame(self.border_frame, fg_color="transparent", height=25)
        self.bottom_bar.pack(fill="x", side="bottom", padx=25, pady=(0, 12))

        self.bottom_status_title = ctk.CTkLabel(
            self.bottom_bar, text="Mira Status:  ",
            font=("SF Pro Display", 12),
            text_color=theme_manager.get_colors()["text_muted"]
        )
        self.bottom_status_title.pack(side="left")

        self.bottom_status_text = ctk.CTkLabel(
            self.bottom_bar, text="Ready",
            font=("SF Pro Display", 12),
            text_color=theme_manager.get_colors()["text_muted"]
        )
        self.bottom_status_text.pack(side="left")

        self.star_icon = ctk.CTkLabel(
            self.bottom_bar, text="✨",
            font=("SF Pro Display", 14),
            text_color=theme_manager.get_colors()["text_muted"]
        )
        self.star_icon.pack(side="right")

        # Animation state
        self.animation_state = "Waiting"
        self.session_active = False
        self.is_visible = False
        self.animating_slide = False
        self.spring_velocity = 0.0

        # Enable Dragging
        self.drag_start_x = 0
        self.drag_start_y = 0
        for widget in [self, self.border_frame, self.top_section, self.right_col]:
            widget.bind("<Button-1>", self.start_move)
            widget.bind("<B1-Motion>", self.do_move)

        self.check_queue()
        self.update_waveform()
        self.withdraw()

    def start_move(self, event):
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def do_move(self, event):
        delta_x = event.x - self.drag_start_x
        delta_y = event.y - self.drag_start_y
        self.x_pos = self.winfo_x() + delta_x
        self.current_y = self.winfo_y() + delta_y
        self.target_y = self.current_y
        self.geometry(f"+{self.x_pos}+{self.current_y}")

    def apply_theme(self):
        """Apply current theme colors"""
        colors = theme_manager.get_colors()
        self.configure(fg_color=colors["bg_primary"])
    
    def toggle_theme(self):
        """Toggle between dark and light theme"""
        theme_manager.toggle_theme()
        self.apply_theme()
        self.update_all_colors()
        
        # Update theme button icon
        if theme_manager.current_theme == "dark":
            self.btn_theme.configure(text="🌙")
        else:
            self.btn_theme.configure(text="☀️")
    
    def update_all_colors(self):
        """Update all UI element colors"""
        colors = theme_manager.get_colors()
        
        # Update main frames
        self.border_frame.configure(fg_color=colors["bg_secondary"])
        self.wave_canvas.configure(bg=colors["bg_secondary"])
        
        # Update labels
        self.status_label.configure(text_color=colors["text_primary"])
        self.live_transcript.configure(text_color=colors["text_secondary"])
        
        # Update entry
        self.text_entry.configure(
            fg_color=colors["bg_tertiary"],
            text_color=colors["text_primary"],
            placeholder_text_color=colors["text_muted"]
        )
        
        # Update tools
        self.tools_frame.configure(fg_color=colors["bg_tertiary"])
        
        # Update separators
        for widget in self.tools_frame.winfo_children():
            if isinstance(widget, ctk.CTkFrame) and widget.cget("width") == 1:
                widget.configure(fg_color=colors["separator"])
        
        # Update bottom bar
        self.status_sep.configure(fg_color=colors["separator"])
        self.bottom_status_title.configure(text_color=colors["text_muted"])
        self.bottom_status_text.configure(text_color=colors["text_muted"])
        self.star_icon.configure(text_color=colors["text_muted"])
        
        # Update music player
        if hasattr(self, 'music_player'):
            self.music_player.update_theme()
        
        # Update waveform colors
        if hasattr(self, 'waveform'):
            self.waveform.update_colors()

    def open_settings(self):
        msg_queue.put({"type": "STATUS", "text": "Opening settings..."})
    
    def toggle_mic(self):
        if self.animation_state == "Listening":
            self.animation_state = "Waiting"
        else:
            self.animation_state = "Listening"
            msg_queue.put({"type": "STATUS", "text": "Listening..."})

    def slide_animation(self):
        if not self.animating_slide:
            return

        target = self.target_y if self.is_visible else self.hidden_y
        stiffness, damping = 0.15, 0.75

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
            self.bottom_status_text.configure(text="Ready", text_color=theme_manager.get_colors()["text_muted"])
        else:
            self.is_visible = False
            self.animating_slide = True
            self.slide_animation()

    def update_waveform(self):
        if self.is_visible:
            self.waveform.update(self.animation_state)
        self.after(30, self.update_waveform)

    def submit_text(self, event=None):
        cmd = self.text_entry.get().strip()
        if cmd:
            self.text_entry.delete(0, "end")
            self.live_transcript.configure(text=f'"{cmd}"')
            self.status_label.configure(text="Processing...")
            self.animation_state = "Processing"
            text_command_queue.put(cmd)

    def show_music_player(self, title, artist, url, video_id=None):
        """Show integrated music player"""
        if hasattr(self, 'music_player'):
            self.music_player.show_player(title, artist, url, video_id)
            # Adjust window height to accommodate player
            self.height = 420  # Increased height for music player
            self.target_y = self.winfo_screenheight() - self.height - 100
            if self.is_visible:
                self.geometry(f'{self.width}x{self.height}+{self.x_pos}+{self.current_y}')

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
                    self.status_label.configure(text=msg["text"])
                    self.bottom_status_text.configure(text=msg["text"], text_color=theme_manager.get_colors()["text_secondary"])
                    if "Listening" in msg["text"]:
                        self.animation_state = "Listening"
                    elif "Processing" in msg["text"] or "Thinking" in msg["text"]:
                        self.animation_state = "Processing"
                    elif "Speaking" in msg["text"]:
                        self.animation_state = "Speaking"
                    elif "Waiting" in msg["text"]:
                        self.animation_state = "Waiting"
                    elif "Error" in msg["text"]:
                        self.bottom_status_text.configure(
                            text="Error Communicating with Gemini",
                            text_color=theme_manager.get_colors()["error"]
                        )
                elif msg["type"] == "LOG":
                    clean_text = msg["text"].replace("Mira: ", "").replace("You (Voice): ", "").replace("You (Typed): ", "")
                    if "Gemini Error" in msg["text"] or "Error:" in msg["text"]:
                        self.bottom_status_text.configure(
                            text="Error Communicating with Gemini",
                            text_color=theme_manager.get_colors()["error"]
                        )
                        self.status_label.configure(text="Error")
                        self.animation_state = "Waiting"
                    elif "Mira:" in msg["text"]:
                        self.status_label.configure(text="Mira")
                        self.live_transcript.configure(text=f'"{clean_text}"')
                        self.animation_state = "Speaking"
                    else:
                        self.live_transcript.configure(text=f'"{clean_text}"')
                elif msg["type"] == "MUSIC":
                    self.show_music_player(msg["title"], msg["artist"], msg["url"], msg.get("video_id"))
                elif msg["type"] == "HIDE":
                    if self.is_visible:
                        self.toggle_visibility()
        except queue.Empty:
            pass
        finally:
            self.after(50, self.check_queue)

def process_user_intent(command, app, speak):
    if "hello" in command:
        speak("Hello there! How can I help you today?")
    elif "time" in command:
        current_time = time.strftime("%I:%M %p")
        speak(f"The current time is {current_time}.")
    elif "play" in command:
        song_query = command.replace("play", "").strip()
        if song_query:
            msg_queue.put({"type": "STATUS", "text": "Searching..."})
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
                    msg_queue.put({
                        "type": "MUSIC",
                        "title": title,
                        "artist": artists,
                        "url": watch_url,
                        "video_id": video_id
                    })
                    # Removed webbrowser.open(watch_url) to keep playback entirely native
                else:
                    speak("I couldn't find that song.")
            except Exception as e:
                msg_queue.put({"type": "LOG", "text": f"YTMusic API Error: {e}"})
                speak("I had trouble with the music API.")
        else:
            speak("What would you like me to play?")
    elif "goodbye" in command or "stop" in command:
        speak("Goodbye! Call me if you need me.")
        return "EXIT"
    else:
        msg_queue.put({"type": "STATUS", "text": "Thinking..."})
        try:
            if not ai_client:
                speak("Please check your OpenRouter API key.")
            else:
                response = ai_client.chat.completions.create(
                    model="qwen/qwen-plus",
                    messages=[
                        {"role": "system", "content": "You are Mira, a helpful AI voice assistant. Answer concisely in 1 to 3 sentences."},
                        {"role": "user", "content": command}
                    ]
                )
                ai_response = response.choices[0].message.content.replace('*', '').replace('#', '')
                speak(ai_response)
        except Exception as e:
            msg_queue.put({"type": "LOG", "text": f"AI Error: {e}"})
            speak("I encountered an error communicating with the AI.")
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
        msg_queue.put({"type": "HIDE"})

def main():
    print("Mira Assistant Started")
    print("Press Ctrl+Alt+M to activate/deactivate")
    app = MiraApp()
    keyboard.add_hotkey('ctrl+alt+m', lambda: on_hotkey_pressed(app))
    try:
        app.mainloop()
    except KeyboardInterrupt:
        print("Exiting...")

if __name__ == "__main__":
    main()
