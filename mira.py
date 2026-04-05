import threading
import time
import queue
import math
import re
import webbrowser
import requests
import pythoncom
import pywinstyles

import customtkinter as ctk
import tkinter as tk

from openai import OpenAI
from ytmusicapi import YTMusic

# ─── AI ───────────────────────────────────────────────────────
OPENROUTER_API_KEY = "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"
ai_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
) if OPENROUTER_API_KEY else None

msg_queue          = queue.Queue()
text_command_queue = queue.Queue()
CONVERSATION_HISTORY = []

SYSTEM_PROMPT = (
    "You are Mira, a concise smart assistant. "
    "Reply in 1-3 sentences. Be direct and natural. "
    "Never use markdown, bullets, or symbols."
)

def ai_chat(user_msg):
    if not ai_client:
        return "No API key configured."
    CONVERSATION_HISTORY.append({"role": "user", "content": user_msg})
    hist = CONVERSATION_HISTORY[-20:]
    try:
        resp = ai_client.chat.completions.create(
            model="qwen/qwen-plus",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + hist,
        )
        reply = re.sub(r"[*#`]", "", resp.choices[0].message.content).strip()
        CONVERSATION_HISTORY.append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        return f"AI error: {str(e)[:80]}"


# ─── SIRI ORB ─────────────────────────────────────────────────
ORB_COLORS = [
    "#BF5FFF", "#8B5CF6", "#6366F1",
    "#3B82F6", "#06B6D4", "#A855F7",
    "#EC4899", "#7C3AED",
]

class SiriOrb:
    """Fluid multi-layer orb matching Apple Siri's Mac aesthetic."""

    def __init__(self, canvas, size=110):
        self.cv    = canvas
        self.S     = size
        self.cx    = size / 2
        self.cy    = size / 2
        self.phase = 0.0
        self.amp   = 0.05
        self.spd   = 0.028
        self._layers = []
        self._build()

    def _build(self):
        self.cv.delete("all")
        self._layers = []
        cx, cy = self.cx, self.cy

        specs = [
            # (r_frac, filled, line_width, phase_off, freq, color_idx)
            (0.90, False, 1, 0.00, 0.90, 7),
            (0.78, False, 1, 0.65, 1.05, 1),
            (0.65, False, 2, 1.30, 1.20, 2),
            (0.52, True,  0, 1.95, 1.35, 0),
            (0.38, True,  0, 2.60, 1.55, 5),
        ]
        for r_frac, filled, lw, po, freq, cidx in specs:
            r = self.S / 2 * r_frac
            if filled:
                oid = self.cv.create_oval(
                    cx-r, cy-r, cx+r, cy+r,
                    fill=ORB_COLORS[cidx], outline="",
                )
            else:
                oid = self.cv.create_oval(
                    cx-r, cy-r, cx+r, cy+r,
                    outline=ORB_COLORS[cidx], width=lw, fill="",
                )
            self._layers.append({
                "id": oid, "r_frac": r_frac,
                "filled": filled, "phase_off": po,
                "freq": freq, "color_idx": cidx,
            })

        self._glint = self.cv.create_oval(0,0,1,1, fill="#FFFFFF", outline="")

    def animate(self, state):
        self.phase += self.spd
        tgt_amp, tgt_spd = {
            "Listening":  (0.80, 0.072),
            "Processing": (0.52, 0.090),
            "Speaking":   (0.65, 0.060),
        }.get(state, (0.06, 0.028))

        self.amp += (tgt_amp - self.amp) * 0.07
        self.spd += (tgt_spd - self.spd) * 0.07

        cx, cy = self.cx, self.cy
        t = self.phase

        for l in self._layers:
            base_r = self.S / 2 * l["r_frac"]
            po, fr = l["phase_off"], l["freq"]

            n = (math.sin(t*fr*1.7 + po)*0.55
               + math.sin(t*fr*3.1 + po*1.3)*0.26
               + math.cos(t*fr*1.2 + po*0.8)*0.19)
            rx = base_r * (1 + n * self.amp * 0.55)
            ry = base_r * (1 + n * self.amp * 0.36)

            cidx  = (l["color_idx"] + int(t * 0.22)) % len(ORB_COLORS)
            color = ORB_COLORS[cidx]
            if l["filled"]:
                self.cv.itemconfig(l["id"], fill=color)
            else:
                self.cv.itemconfig(l["id"], outline=color)
            self.cv.coords(l["id"], cx-rx, cy-ry, cx+rx, cy+ry)

        # Glint
        inner_r = self.S / 2 * 0.42
        gr  = 7 + self.amp * 5
        gx  = cx - inner_r * 0.38
        gy  = cy - inner_r * 0.44
        alp = int(55 + self.amp * 115)
        alp = max(0, min(255, alp))
        self.cv.itemconfig(self._glint, fill=f"#{alp:02x}{alp:02x}{alp:02x}")
        self.cv.coords(self._glint, gx-gr, gy-gr, gx+gr, gy+gr)


# ─── MAIN WINDOW ──────────────────────────────────────────────
class MiraApp(ctk.CTk):
    W = 480
    H = 215

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("Mira")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.withdraw()

        self.anim_state = "Waiting"
        self.active     = False
        self.visible    = False
        self.sliding    = False
        self.vel        = 0.0
        self._dragging  = False
        self._dx = self._dy = 0

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.X        = (sw - self.W) // 2
        self.tgt_y    = sh - self.H - 60
        self.hidden_y = self.tgt_y + 40
        self.cur_y    = self.hidden_y

        self.geometry(f"{self.W}x{self.H}+{self.X}+{int(self.cur_y)}")

        try:
            pywinstyles.apply_style(self, "transparent")
        except Exception:
            pass

        self._build()
        self._pump()
        self._tick()

    # ── BUILD ────────────────────────────────────────────
    def _build(self):
        self.configure(fg_color=("gray85", "#0D0D10"))

        # Dark frosted card — matches screenshot exactly
        self.card = ctk.CTkFrame(
            self,
            fg_color=("gray95", "#1C1C1F"),
            corner_radius=20,
            border_width=1,
            border_color=("gray75", "#3A3A3C"),
        )
        self.card.pack(fill="both", expand=True, padx=1, pady=1)

        # Drag handle
        for w in [self.card]:
            w.bind("<ButtonPress-1>",   self._drag_start)
            w.bind("<B1-Motion>",       self._drag_do)
            w.bind("<ButtonRelease-1>", self._drag_end)

        # ── TOP ROW: Orb + State/Response ──
        top = ctk.CTkFrame(self.card, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(14, 0))
        top.bind("<ButtonPress-1>",   self._drag_start)
        top.bind("<B1-Motion>",       self._drag_do)
        top.bind("<ButtonRelease-1>", self._drag_end)

        # Siri orb
        self.orb_cv = tk.Canvas(
            top, width=110, height=110,
            bg="#1C1C1F", highlightthickness=0,
        )
        self.orb_cv.pack(side="left", padx=(0, 4))
        self.orb = SiriOrb(self.orb_cv, 110)

        # Text area right of orb
        txt_box = ctk.CTkFrame(top, fg_color="transparent")
        txt_box.pack(side="left", fill="both", expand=True, padx=(10, 0))
        txt_box.bind("<ButtonPress-1>",   self._drag_start)
        txt_box.bind("<B1-Motion>",       self._drag_do)
        txt_box.bind("<ButtonRelease-1>", self._drag_end)

        # State label — "Waiting…" bold white
        self.lbl_state = ctk.CTkLabel(
            txt_box,
            text="Waiting…",
            font=("SF Pro Display", 22, "bold"),
            text_color=("black", "#F5F5F7"),
            anchor="w",
        )
        self.lbl_state.pack(anchor="w", pady=(16, 0))
        self.lbl_state.bind("<ButtonPress-1>",   self._drag_start)
        self.lbl_state.bind("<B1-Motion>",       self._drag_do)

        # Response / transcript — grey, italic feel
        self.lbl_resp = ctk.CTkLabel(
            txt_box,
            text="",
            font=("SF Pro Display", 14),
            text_color=("gray30", "#AEAEB2"),
            wraplength=270,
            justify="left",
            anchor="w",
        )
        self.lbl_resp.pack(anchor="w", pady=(4, 0))
        self.lbl_resp.bind("<ButtonPress-1>",   self._drag_start)
        self.lbl_resp.bind("<B1-Motion>",       self._drag_do)

        # ── SEPARATOR ──
        ctk.CTkFrame(self.card, height=1, fg_color=("gray75", "#2C2C2E")).pack(
            fill="x", padx=18, pady=(12, 0)
        )

        # ── BOTTOM ROW: entry + cog + search ──
        self.bot = ctk.CTkFrame(self.card, fg_color="transparent")
        self.bot.pack(fill="x", padx=12, pady=(10, 10))

        self.entry = ctk.CTkEntry(
            self.bot,
            height=40,
            placeholder_text="Type or Speak…",
            border_width=1,
            border_color=("gray75", "#3A3A3C"),
            corner_radius=20,
            font=("SF Pro Display", 14),
            fg_color=("gray90", "#2C2C2E"),
            text_color=("black", "#F5F5F7"),
            placeholder_text_color=("gray40", "#636366"),
        )
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", self._on_enter)

        # Cog
        ctk.CTkButton(
            self.bot, text="⚙",
            width=40, height=40, corner_radius=20,
            fg_color=("gray90", "#2C2C2E"), hover_color=("gray75", "#3A3A3C"),
            border_width=1, border_color=("gray75", "#3A3A3C"),
            font=("SF Pro Display", 17),
            text_color=("gray40", "#8E8E93"),
            command=self._settings,
        ).pack(side="left", padx=(8, 0))

        # Search (🔍 → magnifier icon)
        ctk.CTkButton(
            self.bot, text="⌕",
            width=40, height=40, corner_radius=20,
            fg_color=("gray90", "#2C2C2E"), hover_color=("gray75", "#3A3A3C"),
            border_width=1, border_color=("gray75", "#3A3A3C"),
            font=("SF Pro Display", 18),
            text_color=("gray40", "#8E8E93"),
            command=self._search,
        ).pack(side="left", padx=(6, 0))

        # ── MEDIA CONTROLS ROW ──
        self.content_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=18, pady=(0, 10))

        self.media_row = ctk.CTkFrame(self.content_frame, fg_color="#1C1C1F", corner_radius=10)
        
        # Track Slider Frame
        self.slider_frame = ctk.CTkFrame(self.media_row, fg_color="transparent", height=20)
        self.slider_frame.pack(fill="x", padx=8, pady=(8, 0))
        
        self.time_lbl_1 = ctk.CTkLabel(self.slider_frame, text="0:00", font=("SF Pro Display", 10), text_color="#AEAEB2")
        self.time_lbl_1.pack(side="left", padx=(4, 8))
        
        self.track_slider = ctk.CTkSlider(self.slider_frame, height=10, button_length=0, progress_color="#FF0000", fg_color="#3A3A3C")
        self.track_slider.set(0)
        self.track_slider.pack(side="left", fill="x", expand=True)

        self.time_lbl_2 = ctk.CTkLabel(self.slider_frame, text="3:15", font=("SF Pro Display", 10), text_color="#AEAEB2")
        self.time_lbl_2.pack(side="right", padx=(8, 4))

        # Main Control Frame
        mid_controls = ctk.CTkFrame(self.media_row, fg_color="transparent")
        mid_controls.pack(fill="x", padx=8, pady=4)
        
        # Thumbnail and Title
        left_info = ctk.CTkFrame(mid_controls, fg_color="transparent")
        left_info.pack(side="left", fill="x", expand=True)

        self.lbl_thumb = ctk.CTkLabel(left_info, text="", width=36, height=36, corner_radius=4, fg_color="#2C2C2E")
        self.lbl_thumb.pack(side="left", padx=(0, 8), pady=2)
        
        self.lbl_now_playing = ctk.CTkLabel(left_info, text="", font=("SF Pro Display", 12, "bold"), text_color="#F5F5F7", anchor="w")
        self.lbl_now_playing.pack(side="left", fill="x", expand=True)

        # Right Action Buttons
        right_btns = ctk.CTkFrame(mid_controls, fg_color="transparent")
        right_btns.pack(side="right")
        
        opts = {"width": 30, "height": 30, "fg_color": "transparent", "hover_color": "#3A3A3C", "text_color": "#F5F5F7", "font": ("SF Pro Display", 14)}
        ctk.CTkButton(right_btns, text="👎", command=lambda: self._set_status("Disliked", "#FF453A"), **opts).pack(side="left", padx=2)
        ctk.CTkButton(right_btns, text="👍", command=lambda: self._set_status("Liked", "#30D158"), **opts).pack(side="left", padx=2)
        ctk.CTkButton(right_btns, text="⠇", command=lambda: self._set_status("More actions", "#AEAEB2"), **opts).pack(side="left", padx=(2, 6))

        # Bottom Player Buttons
        bot_controls = ctk.CTkFrame(self.media_row, fg_color="transparent")
        bot_controls.pack(fill="x", padx=8, pady=(0, 8))
        
        center_frame = ctk.CTkFrame(bot_controls, fg_color="transparent")
        center_frame.pack(side="left", expand=True)

        ctk.CTkButton(center_frame, text="🔀", command=lambda: self._set_status("Shuffle toggled", "#AEAEB2"), **opts).pack(side="left", padx=6)
        ctk.CTkButton(center_frame, text="⏮", command=lambda: self._media_cmd("previous track"), **opts).pack(side="left", padx=4)
        
        play_opts = opts.copy()
        play_opts["font"] = ("SF Pro Display", 18)
        ctk.CTkButton(center_frame, text="▶", command=lambda: self._media_cmd("play/pause media"), **play_opts).pack(side="left", padx=4)
        
        ctk.CTkButton(center_frame, text="⏭", command=lambda: self._media_cmd("next track"), **opts).pack(side="left", padx=4)
        ctk.CTkButton(center_frame, text="🔂", command=lambda: self._set_status("Repeat toggled", "#AEAEB2"), **opts).pack(side="left", padx=6)

        vol_frame = ctk.CTkFrame(bot_controls, fg_color="transparent")
        vol_frame.pack(side="right")
        ctk.CTkButton(vol_frame, text="🔉", command=lambda: self._media_cmd("volume down"), **opts).pack(side="left", padx=2)
        ctk.CTkButton(vol_frame, text="🔊", command=lambda: self._media_cmd("volume up"), **opts).pack(side="left", padx=2)

        # ── SUGGESTIONS ROW ──
        self.sug_frame = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent", height=130)

        # ── STATUS BAR ──
        self.bar = ctk.CTkFrame(self.card, fg_color="transparent")
        self.bar.pack(fill="x", padx=18, pady=(0, 10))
        self.bar.bind("<ButtonPress-1>",   self._drag_start)
        self.bar.bind("<B1-Motion>",       self._drag_do)
        self.bar.bind("<ButtonRelease-1>", self._drag_end)

        ctk.CTkLabel(
            self.bar, text="Mira Status:  ",
            font=("SF Pro Display", 11),
            text_color="#48484A",
        ).pack(side="left")

        self.lbl_status = ctk.CTkLabel(
            self.bar, text="Idle",
            font=("SF Pro Display", 11),
            text_color="#636366",
        )
        self.lbl_status.pack(side="left")

        # Sparkle ✦ bottom right
        ctk.CTkLabel(
            self.bar, text="✦",
            font=("SF Pro Display", 14),
            text_color="#5E5CE6",
        ).pack(side="right", padx=(0, 15))

        # Sizegrip (resize handle)
        self.sizegrip = ctk.CTkLabel(self.card, text="↘", font=("SF Pro Display", 18), text_color="#3A3A3C", cursor="sizing")
        self.sizegrip.place(relx=1.0, rely=1.0, anchor="se", x=-2, y=-2)
        self.sizegrip.bind("<ButtonPress-1>", self._resize_start)
        self.sizegrip.bind("<B1-Motion>", self._resize_do)
        self.sizegrip.bind("<ButtonRelease-1>", self._resize_end)

    # ── DRAG ────────────────────────────────────────────
    def _drag_start(self, e):
        self._dragging = True
        self._dx, self._dy = e.x, e.y

    def _drag_do(self, e):
        if not self._dragging:
            return
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        nx = max(0, min(self.winfo_x() + e.x - self._dx, sw - self.W))
        ny = max(0, min(self.winfo_y() + e.y - self._dy, sh - self.H))
        self.X = nx
        self.tgt_y = ny
        self.cur_y = ny
        self.geometry(f"+{self.X}+{int(self.cur_y)}")

    def _drag_end(self, e):
        self._dragging = False

    def _resize_start(self, e):
        self._resizing = True
        self._rx = e.x_root
        self._ry = e.y_root
        self._start_W = self.W
        self._start_H = self.H

    def _resize_do(self, e):
        if not getattr(self, '_resizing', False): return
        dx = e.x_root - self._rx
        dy = e.y_root - self._ry
        self.W = max(350, self._start_W + dx)
        self.H = max(200, self._start_H + dy)
        self.geometry(f"{self.W}x{self.H}")

    def _resize_end(self, e):
        self._resizing = False

    def _media_cmd(self, action):
        import keyboard
        keyboard.send(action)

    def show_media(self, msg):
        text = msg.get("text", "")
        self.lbl_now_playing.configure(text=text[:35] + ("…" if len(text) > 35 else ""))
        
        url = msg.get("thumb")
        if url:
             threading.Thread(target=self._load_image_to_label, args=(url, self.lbl_thumb, (36, 36)), daemon=True).start()
             
        if "suggestions" in msg:
            sugs = msg["suggestions"]
            for widget in self.sug_frame.winfo_children():
                widget.destroy()
                
            if sugs:
                ctk.CTkLabel(self.sug_frame, text="Suggested", font=("SF Pro Display", 11, "bold"), text_color="#AEAEB2", anchor="w").pack(fill="x", pady=(0,4))
                for sug in sugs:
                    s_row = ctk.CTkFrame(self.sug_frame, fg_color="#2C2C2E", corner_radius=8, height=44)
                    s_row.pack(fill="x", pady=2)
                    
                    s_thumb = ctk.CTkLabel(s_row, text="", width=32, height=32, corner_radius=4, fg_color="#1C1C1F")
                    s_thumb.pack(side="left", padx=(6, 4), pady=4)
                    
                    s_name = ctk.CTkLabel(s_row, text=sug["title"][:50], font=("SF Pro Display", 12), text_color="#F5F5F7", anchor="w")
                    s_name.pack(side="left", padx=8, expand=True, fill="x")
                    
                    cb = lambda e, s=sug: text_command_queue.put(f"?play_sug:{s['videoId']}|{s['title']}|{s['thumb']}")
                    s_row.bind("<Button-1>", cb)
                    s_thumb.bind("<Button-1>", cb)
                    s_name.bind("<Button-1>", cb)
                    
                    if sug.get("thumb"):
                        threading.Thread(target=self._load_image_to_label, args=(sug["thumb"], s_thumb, (32, 32)), daemon=True).start()

            if not self.sug_frame.winfo_ismapped():
                self.sug_frame.pack(fill="both", expand=True)
        else:
            if self.sug_frame.winfo_ismapped():
                self.sug_frame.pack_forget()

        if not self.media_row.winfo_ismapped():
            self.media_row.pack(fill="x", pady=(0, 10))

        if self.H < 500:
            self.H = 500
            self.geometry(f"{self.W}x{self.H}")
            
        self.track_slider.set(0)
        self._playback_seconds = 0
        if hasattr(self, "_slider_timer"):
            self.after_cancel(self._slider_timer)
        self._animate_slider()
        
    def _animate_slider(self):
        duration_sec = 195
        self._playback_seconds += 1
        if self._playback_seconds <= duration_sec:
            pct = self._playback_seconds / duration_sec
            self.track_slider.set(pct)
            m = self._playback_seconds // 60
            s = self._playback_seconds % 60
            self.time_lbl_1.configure(text=f"{m}:{s:02d}")
            self._slider_timer = self.after(1000, self._animate_slider)
                
    def _load_image_to_label(self, url, lbl, size=(36, 36)):
        try:
            from PIL import Image
            from io import BytesIO
            import requests
            r = requests.get(url, timeout=5)
            img = Image.open(BytesIO(r.content)).resize(size, Image.LANCZOS)
            photo = ctk.CTkImage(light_image=img, dark_image=img, size=size)
            
            def apply_img():
                lbl.configure(image=photo)
                lbl.image = photo  # Keep strong reference to prevent GC
                
            self.after(0, apply_img)
        except Exception:
            pass

    # ── ACTIONS ─────────────────────────────────────────
    def _on_enter(self, _=None):
        cmd = self.entry.get().strip()
        if not cmd:
            return
        self.entry.delete(0, "end")
        self.lbl_resp.configure(text=f'"{cmd}"')
        self.lbl_state.configure(text="Processing…", text_color=("black", "#F5F5F7"))
        self._set_status("Processing…", "#FF9F0A")
        self.anim_state = "Processing"
        text_command_queue.put(cmd)

    def _search(self):
        q = self.entry.get().strip()
        if q:
            self.entry.delete(0, "end")
            webbrowser.open(
                f"https://www.google.com/search?q={requests.utils.quote(q)}"
            )
            self.lbl_state.configure(text="Searching…", text_color=("black", "#F5F5F7"))
            self.lbl_resp.configure(text=f'"{q}"')
            self._set_status(f'Google: {q[:36]}', "#30D158")
        else:
            webbrowser.open("https://www.google.com")
            self._set_status("Opened Google", "#30D158")

    def _settings(self):
        current_mode = ctk.get_appearance_mode()
        new_mode = "Light" if current_mode == "Dark" else "Dark"
        ctk.set_appearance_mode(new_mode)
        
        # update orb cv bg
        bg_col = "#1C1C1F" if new_mode == "Dark" else "gray95"
        self.orb_cv.configure(bg=bg_col)
        self._set_status(f"{new_mode} Mode", "#636366")

    def _set_status(self, text, color="#636366"):
        self.lbl_status.configure(text=text, text_color=color)

    # ── SHOW / HIDE / SLIDE ─────────────────────────────
    def show(self):
        self.hidden_y = self.tgt_y + 40
        self.cur_y = self.hidden_y
        self.deiconify()
        self.attributes("-topmost", True)
        self.visible = True
        self.sliding = True
        self._slide()

    def hide(self):
        self.hidden_y = self.tgt_y + 40
        self.visible = False
        self.sliding = True
        self._slide()

    def toggle(self):
        if self.visible:
            self.hide()
        else:
            self.show()

    def _slide(self):
        if not self.sliding:
            return
        tgt = self.tgt_y if self.visible else self.hidden_y
        self.vel = (self.vel + (tgt - self.cur_y) * 0.18) * 0.68
        self.cur_y += self.vel
        if abs(tgt - self.cur_y) < 0.5 and abs(self.vel) < 0.5:
            self.cur_y = tgt
            self.vel   = 0
            self.sliding = False
            self.geometry(f"{self.W}x{self.H}+{self.X}+{int(self.cur_y)}")
            if not self.visible:
                self.withdraw()
            return
        self.geometry(f"{self.W}x{self.H}+{self.X}+{int(self.cur_y)}")
        self.after(14, self._slide)

    # ── QUEUE PUMP ──────────────────────────────────────
    def _pump(self):
        try:
            while True:
                msg = msg_queue.get_nowait()
                t   = msg["type"]

                if t == "SHOW":
                    if not self.visible:
                        self.show()
                    self.lbl_resp.configure(text="")

                elif t == "STATUS":
                    txt = msg["text"]
                    self.lbl_state.configure(text=txt, text_color=("black", "#F5F5F7"))
                    col_map = {
                        "Listening": "#30D158", "Speaking": "#5E5CE6",
                        "Processing": "#FF9F0A", "Thinking": "#FF9F0A",
                    }
                    col = next((v for k, v in col_map.items() if k in txt), "#636366")
                    self._set_status(txt, col)
                    st_map = {
                        "Listening": "Listening", "Processing": "Processing",
                        "Thinking":  "Processing", "Speaking":  "Speaking",
                    }
                    self.anim_state = next(
                        (v for k, v in st_map.items() if k in txt), "Waiting"
                    )

                elif t == "LOG":
                    raw = msg["text"]
                    if "Error" in raw:
                        clean = raw.replace("Mira: ", "").replace("Error: ", "")
                        self.lbl_state.configure(
                            text="Error Communicating", text_color="#FF453A")
                        self._set_status(
                            f"Error Communicating with AI", "#FF453A")
                        self.anim_state = "Waiting"
                    elif raw.startswith("Mira:"):
                        clean = raw[5:].strip()
                        if clean:
                            self.lbl_state.configure(
                                text="Mira", text_color=("black", "#F5F5F7"))
                            self.lbl_resp.configure(text=f'"{clean}"')
                        self._set_status("Speaking…", "#5E5CE6")
                        self.anim_state = "Speaking"
                    else:
                        clean = raw.replace("You: ", "")
                        self.lbl_resp.configure(text=f'"{clean}"')

                elif t == "DONE":
                    self.lbl_state.configure(text="Waiting…", text_color=("black", "#F5F5F7"))
                    self._set_status("Idle", "#636366")
                    self.anim_state = "Waiting"

                elif t == "HIDE":
                    if self.visible:
                        self.hide()

                elif t == "MEDIA":
                    self.show_media(msg.get("msg", msg))

        except queue.Empty:
            pass
        finally:
            self.after(40, self._pump)

    # ── ANIMATION ───────────────────────────────────────
    def _tick(self):
        if self.visible:
            self.orb.animate(self.anim_state)
        self.after(28, self._tick)


# ─── BACKEND ──────────────────────────────────────────────────
def process_intent(cmd, speak):
    cmd_l = cmd.lower().strip()

    if cmd_l.startswith("?play_sug:"):
        _, details = cmd.split(":", 1)
        parts = details.split("|", 2)
        if len(parts) >= 3:
            vid, ttl, thb = parts[0], parts[1], parts[2]
            url = f"https://music.youtube.com/watch?v={vid}"
            webbrowser.open(url)
            msg_queue.put({"type": "MEDIA", "msg": {"text": ttl, "thumb": thb, "suggestions": []}})
            speak(f"Playing {ttl}.")
        return "CONTINUE"

    if re.search(r'\b(hello|hi|hey)\b', cmd_l):
        speak("Hey! I'm Mira. How can I help you?")

    elif re.search(r'\btime\b', cmd_l):
        speak(f"It's {time.strftime('%I:%M %p')} right now.")

    elif re.search(r'\b(date|today)\b', cmd_l):
        speak(f"Today is {time.strftime('%A, %B %d, %Y')}.")

    elif re.search(r'\b(search|google|look up|find)\b', cmd_l):
        q = re.sub(r'\b(search for|search|google|look up|find)\b', '', cmd_l).strip()
        if q:
            webbrowser.open(
                f"https://www.google.com/search?q={requests.utils.quote(q)}"
            )
            speak(f"Searching Google for {q}.")
        else:
            webbrowser.open("https://www.google.com")
            speak("Opening Google.")

    elif re.search(r'\b(open|go to|visit)\b', cmd_l):
        q   = re.sub(r'\b(open|go to|visit)\b', '', cmd_l).strip()
        url = (q if q.startswith("http")
               else f"https://{q}" if "." in q
               else f"https://www.google.com/search?q={requests.utils.quote(q)}")
        webbrowser.open(url)
        speak(f"Opening {q}.")

    elif re.search(r'\b(play|music)\b', cmd_l):
        q = re.sub(r'\b(play|music|listen to|listen)\b', '', cmd_l).strip()
        if not q:
            speak("What would you like me to play?")
            return "CONTINUE"
        msg_queue.put({"type": "STATUS", "text": "Searching music…"})
        try:
            results = YTMusic().search(q, filter="songs")
            if results:
                s   = results[0]
                ttl = s.get("title", q)
                art = ", ".join(a.get("name", "") for a in s.get("artists", []))
                vid = s.get("videoId")
                if vid:
                    url = f"https://music.youtube.com/watch?v={vid}"
                    webbrowser.open(url)
                    
                    thumb_url = ""
                    thumbs = s.get("thumbnails", [])
                    if thumbs:
                        thumb_url = thumbs[-1].get("url", "")
                        
                    sugs = []
                    for t in results[1:4]:
                        t_vid = t.get("videoId")
                        if not t_vid: continue
                        t_th = t.get("thumbnails", [])
                        t_tu = t_th[-1].get("url") if t_th else ""
                        art_sug = ", ".join(a.get("name", "") for a in t.get("artists", []))
                        s_ttl = f"{t.get('title', '')} • {art_sug}"
                        sugs.append({"videoId": t_vid, "title": s_ttl, "thumb": t_tu})
                        
                    msg_queue.put({"type": "MEDIA", "msg": {"text": f"{ttl} • {art}", "thumb": thumb_url, "suggestions": sugs}})
                    speak(f"Playing {ttl} by {art}.")
                else:
                    speak("Couldn't play that song on YouTube.")
            else:
                speak("Couldn't find that song.")
        except Exception:
            speak("Had trouble reaching the music service.")

    elif re.search(r'\b(clear|reset)\b', cmd_l):
        CONVERSATION_HISTORY.clear()
        speak("Conversation cleared.")

    elif re.search(r'\b(stop|goodbye|bye|exit|quit)\b', cmd_l):
        speak("Goodbye!")
        return "EXIT"

    else:
        msg_queue.put({"type": "STATUS", "text": "Thinking…"})
        reply = ai_chat(cmd)
        speak(reply)

    return "CONTINUE"


def session_loop(app):
    import pyttsx3
    pythoncom.CoInitialize()
    engine = pyttsx3.init()
    engine.setProperty("volume", 1.0)
    for v in engine.getProperty("voices"):
        if "zira" in v.name.lower() or "female" in v.name.lower():
            engine.setProperty("voice", v.id)
            break

    def speak(text):
        msg_queue.put({"type": "LOG",    "text": f"Mira: {text}"})
        msg_queue.put({"type": "STATUS", "text": "Speaking…"})
        engine.say(text)
        engine.runAndWait()
        msg_queue.put({"type": "DONE"})

    msg_queue.put({"type": "SHOW"})
    speak("Online.")

    try:
        while app.active:
            try:
                cmd = text_command_queue.get(timeout=0.25)
                msg_queue.put({"type": "LOG", "text": f"You: {cmd}"})
                result = process_intent(cmd, speak)
                if result == "EXIT":
                    app.active = False
            except queue.Empty:
                pass
    except Exception as e:
        msg_queue.put({"type": "LOG", "text": f"Error: {e}"})
    finally:
        app.active = False
        msg_queue.put({"type": "HIDE"})
        pythoncom.CoUninitialize()


def on_hotkey(app):
    if not app.active:
        app.active = True
        threading.Thread(target=session_loop, args=(app,), daemon=True).start()
    else:
        app.active = False
        msg_queue.put({"type": "HIDE"})


def main():
    import keyboard
    print("Mira  —  Ctrl+Alt+M to toggle")
    app = MiraApp()
    keyboard.add_hotkey("ctrl+alt+m", lambda: on_hotkey(app))
    try:
        app.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()