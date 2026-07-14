# -*- coding: utf-8 -*-
"""UPet —— 独立桌面宠物小工具

不依赖 Codex：导入一张 Codex 格式的宠物精灵图（8 列 x 11 行），
就能常驻桌面、始终置顶、可拖动、可互动。

用法:
    python upet.py            # 直接运行
    pyinstaller 打包后双击 UPet.exe

互动:
    单击       -> 挥手
    双击       -> 跳跃
    左右拖动   -> 跟随方向播放走路动画
    鼠标悬停   -> 张望 / 挥手
    右键       -> 菜单（导入精灵图 / 动作 / 大小 / 速度 / 感知键鼠 / 开机自启 / 退出）

感知键鼠（可在右键菜单关闭，仅本机检测“是否有输入”，不记录内容）:
    连续打字       -> 思考工作
    连续点击鼠标   -> 检查
    键鼠长时间没动 -> 失落打瞌睡；回来时跳跃欢迎
"""
import ctypes
import json
import os
import random
import sys
import time
import tkinter as tk
from collections import deque
from ctypes import wintypes
from tkinter import filedialog, messagebox

from PIL import Image, ImageTk

APP_NAME = "UPet"
KEY_COLOR = "#ff00fe"  # 透明色键（画面中不会出现的颜色）
CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

# Codex 宠物精灵图固定为 8 列 x 11 行，每行一个动作
GRID_COLS, GRID_ROWS = 8, 11
ROW_LAYOUT = [
    ("idle",       "待机"),
    ("walk-right", "向右走"),
    ("walk-left",  "向左走"),
    ("wave",       "挥手"),
    ("jump",       "跳跃"),
    ("failed",     "失落"),
    ("waiting",    "等待"),
    ("working",    "思考"),
    ("checking",   "检查"),
    ("observe-a",  "张望 A"),
    ("observe-b",  "张望 B"),
]
# 一次性动作播放的循环次数（播完回到待机）
ONESHOT_LOOPS = {"wave": 2, "jump": 1, "failed": 1, "waiting": 1,
                 "working": 2, "checking": 2, "observe-a": 1, "observe-b": 1}
AMBIENT_POOL = ["wave", "jump", "waiting", "working", "checking",
                "observe-a", "observe-b", "walk", "walk", "observe-a", "observe-b"]

SCALES = [("50%", 0.5), ("75%", 0.75), ("100%", 1.0), ("150%", 1.5), ("200%", 2.0)]
SPEEDS = [("慢", 300), ("正常", 220), ("快", 140)]

# 各动作相对速度：>1 表示这个动作播得更慢（每帧停留更久）
ANIM_SPEED = {"idle": 1.5, "observe-a": 1.6, "observe-b": 1.6,
              "waiting": 1.3, "working": 1.3, "checking": 1.3, "failed": 1.4}

# ---------- 全局键鼠感知（仅检测“是否有输入”，不记录内容） ----------
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

KB_VKS = ([0x08, 0x09, 0x0D, 0x20]                 # 退格/Tab/回车/空格
          + list(range(0x30, 0x3A))                 # 0-9
          + list(range(0x41, 0x5B))                 # A-Z
          + list(range(0x60, 0x70))                 # 小键盘
          + list(range(0xBA, 0xC1))                 # 标点
          + list(range(0xDB, 0xDF)))                # 括号引号

SLEEP_AFTER_MS = 120_000   # 键鼠无输入这么久 -> 打瞌睡
TYPING_WINDOW = 2.0        # 秒内检测到 >=3 次按键 -> 打字中
CLICK_WINDOW = 2.0         # 秒内检测到 >=2 次点击 -> 点击中
HOVER_COOLDOWN = 8.0       # 悬停反应冷却（秒）


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def system_idle_ms():
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if user32.GetLastInputInfo(ctypes.byref(lii)):
        return kernel32.GetTickCount() - lii.dwTime
    return 0


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class SpriteSheet:
    """解析精灵图：切格子、按透明度检测每行实际帧数。"""

    def __init__(self, path):
        self.path = path
        img = Image.open(path).convert("RGBA")
        self.cell_w = img.width // GRID_COLS
        self.cell_h = img.height // GRID_ROWS
        if self.cell_w < 8 or self.cell_h < 8:
            raise ValueError("图片太小，不像是 8x11 的精灵图")
        self.image = img
        alpha = img.getchannel("A")
        self.anims = {}   # name -> (row, frame_count)
        self.labels = {}  # name -> 中文名
        for row, (name, label) in enumerate(ROW_LAYOUT):
            if (row + 1) * self.cell_h > img.height:
                break
            count = 0
            for c in range(GRID_COLS):
                cell = alpha.crop((c * self.cell_w, row * self.cell_h,
                                   (c + 1) * self.cell_w, (row + 1) * self.cell_h))
                opaque = sum(cell.histogram()[17:])
                if opaque > 500:
                    count = c + 1
            if count > 0:
                self.anims[name] = (row, count)
                self.labels[name] = label
        if "idle" not in self.anims:
            raise ValueError("没有检测到有效帧（第一行应为待机动画）")

    def render_frames(self, name, scale):
        """渲染某个动作的所有帧：合成到透明色键背景上（硬边缘避免色边）。"""
        row, count = self.anims[name]
        key_rgb = tuple(int(KEY_COLOR[i:i + 2], 16) for i in (1, 3, 5))
        w = max(1, int(self.cell_w * scale))
        h = max(1, int(self.cell_h * scale))
        frames = []
        for i in range(count):
            cell = self.image.crop((i * self.cell_w, row * self.cell_h,
                                    (i + 1) * self.cell_w, (row + 1) * self.cell_h))
            if scale != 1:
                cell = cell.resize((w, h), Image.Resampling.LANCZOS)
            # 二值化 alpha：>=128 保留原色，否则填充色键
            base = Image.new("RGBA", cell.size, key_rgb + (255,))
            mask = cell.getchannel("A").point(lambda a: 255 if a >= 128 else 0)
            base.paste(cell, (0, 0), mask)
            frames.append(ImageTk.PhotoImage(base.convert("RGB")))
        return frames


class UPet:
    def __init__(self):
        self.cfg = load_config()
        self.scale = float(self.cfg.get("scale", 1.0))
        self.frame_ms = int(self.cfg.get("speed_ms", 220))
        self.wander = bool(self.cfg.get("wander", True))
        self.sense = bool(self.cfg.get("sense", True))

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title(APP_NAME)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", KEY_COLOR)
        self.root.configure(bg=KEY_COLOR)

        self.label = tk.Label(self.root, bg=KEY_COLOR, bd=0, highlightthickness=0)
        self.label.pack()

        self.sheet = None
        self.frame_cache = {}      # anim name -> [PhotoImage]
        self.anim = "idle"
        self.frame_idx = 0
        self.mode = "idle"         # idle | oneshot | walk | drag | react
        self.react_kind = None     # working | checking | sleep
        self.loops_left = 0
        self.walk_dx = 0
        self.walk_ticks = 0
        self.kb_hits = deque(maxlen=64)     # 最近检测到按键的时间戳
        self.click_hits = deque(maxlen=64)  # 最近检测到点击的时间戳
        self.hover_at = 0.0
        self._ambient_job = None
        self._pending_wave = None
        self._drag = None
        self._moved = False

        self.label.bind("<ButtonPress-1>", self.on_press)
        self.label.bind("<B1-Motion>", self.on_drag)
        self.label.bind("<ButtonRelease-1>", self.on_release)
        self.label.bind("<Double-Button-1>", self.on_double)
        self.label.bind("<Button-3>", self.on_menu)
        self.label.bind("<Enter>", self.on_hover)

        if not self.try_load_initial_sheet():
            sys.exit(0)

        x = self.cfg.get("x")
        y = self.cfg.get("y")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = self.pet_size()
        if x is None or y is None or not (0 <= x <= sw - 10 and 0 <= y <= sh - 10):
            x, y = sw - w - 80, sh - h - 120  # 默认右下角
        self.root.geometry(f"+{int(x)}+{int(y)}")
        self.root.deiconify()

        self.set_anim("idle")
        self.schedule_ambient()
        self.tick()
        self.poll_activity()

        if os.environ.get("UPET_SELFTEST"):
            self.root.after(3000, self.quit)

    # ---------- 精灵图加载 ----------
    def try_load_initial_sheet(self):
        candidates = []
        if self.cfg.get("sheet"):
            candidates.append(self.cfg["sheet"])
        candidates.append(os.path.join(app_dir(), "spritesheet.webp"))
        for p in candidates:
            if p and os.path.exists(p) and self.load_sheet(p, quiet=True):
                return True
        # 首次使用：弹出导入对话框
        messagebox.showinfo(APP_NAME, "欢迎使用 UPet！\n请选择一张宠物精灵图（8 列 x 11 行的透明 WebP/PNG）。")
        return self.import_sheet()

    def load_sheet(self, path, quiet=False):
        try:
            sheet = SpriteSheet(path)
        except Exception as e:
            if not quiet:
                messagebox.showerror(APP_NAME, f"无法加载精灵图:\n{path}\n\n{e}")
            return False
        self.sheet = sheet
        self.frame_cache = {}
        self.cfg["sheet"] = path
        save_config(self.cfg)
        return True

    def import_sheet(self):
        path = filedialog.askopenfilename(
            title="选择宠物精灵图",
            filetypes=[("图片", "*.webp;*.png"), ("所有文件", "*.*")])
        if not path:
            return self.sheet is not None
        ok = self.load_sheet(path)
        if ok:
            self.set_anim("idle")
            self.set_anim_size()
        return ok

    def frames(self, name):
        if name not in self.frame_cache:
            self.frame_cache[name] = self.sheet.render_frames(name, self.scale)
        return self.frame_cache[name]

    def pet_size(self):
        return (max(1, int(self.sheet.cell_w * self.scale)),
                max(1, int(self.sheet.cell_h * self.scale)))

    def set_anim_size(self):
        w, h = self.pet_size()
        self.root.geometry(f"{w}x{h}")

    # ---------- 动画状态机 ----------
    def set_anim(self, name, mode="idle", loops=0):
        if name not in self.sheet.anims:
            name, mode, loops = "idle", "idle", 0
        self.anim = name
        self.frame_idx = 0
        self.mode = mode
        self.loops_left = loops
        self.set_anim_size()

    def play_oneshot(self, name):
        if name in ("walk-left", "walk-right"):
            self.start_walk(-1 if name == "walk-left" else 1)
            return
        self.react_kind = None
        self.set_anim(name, "oneshot", ONESHOT_LOOPS.get(name, 1))

    def start_walk(self, direction=None):
        if direction is None:
            direction = random.choice((-1, 1))
        self.walk_dx = direction * max(3, int(5 * self.scale))
        self.walk_ticks = random.randint(20, 45)
        self.set_anim("walk-left" if direction < 0 else "walk-right", "walk")

    def start_react(self, kind):
        """键鼠感知触发的持续反应：working / checking / sleep"""
        anim = {"working": "working", "checking": "checking", "sleep": "failed"}[kind]
        self.react_kind = kind
        self.set_anim(anim, "react")

    def back_to_idle(self):
        self.react_kind = None
        self.set_anim("idle")
        self.schedule_ambient()

    def tick(self):
        frames = self.frames(self.anim)
        if self.frame_idx >= len(frames):
            self.frame_idx = 0
        self.label.configure(image=frames[self.frame_idx])
        self.frame_idx += 1

        if self.mode == "walk":
            x, y = self.root.winfo_x(), self.root.winfo_y()
            w, _ = self.pet_size()
            sw = self.root.winfo_screenwidth()
            nx = x + self.walk_dx
            if nx < 0 or nx > sw - w:
                self.walk_dx = -self.walk_dx
                self.set_anim("walk-left" if self.walk_dx < 0 else "walk-right", "walk")
                nx = max(0, min(nx, sw - w))
            self.root.geometry(f"+{nx}+{y}")
            self.walk_ticks -= 1
            if self.walk_ticks <= 0:
                self.back_to_idle()

        if self.frame_idx >= len(frames):
            self.frame_idx = 0
            if self.mode == "oneshot":
                self.loops_left -= 1
                if self.loops_left <= 0:
                    self.back_to_idle()

        delay = int(self.frame_ms * ANIM_SPEED.get(self.anim, 1.0))
        self.root.after(delay, self.tick)

    def schedule_ambient(self):
        if self._ambient_job:
            self.root.after_cancel(self._ambient_job)
            self._ambient_job = None
        delay = random.randint(7000, 16000)
        self._ambient_job = self.root.after(delay, self.ambient_act)

    def ambient_act(self):
        self._ambient_job = None
        if self.mode != "idle":
            self.schedule_ambient()
            return
        choice = random.choice(AMBIENT_POOL)
        if choice == "walk":
            if self.wander:
                self.start_walk()
            else:
                self.schedule_ambient()
                return
        else:
            self.play_oneshot(choice)

    # ---------- 全局键鼠感知 ----------
    def cursor_over_pet(self):
        try:
            pt = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
            w, h = self.pet_size()
            return x <= pt.x <= x + w and y <= pt.y <= y + h
        except Exception:
            return False

    def poll_activity(self):
        self.root.after(150, self.poll_activity)
        if not self.sense or self.sheet is None:
            return
        now = time.monotonic()

        # 只检测“有没有按键/点击”，不关心具体内容
        if any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in KB_VKS):
            self.kb_hits.append(now)
        if not self.cursor_over_pet():
            for vk in (0x01, 0x02):
                if user32.GetAsyncKeyState(vk) & 0x8000:
                    self.click_hits.append(now)
                    break

        if self.mode in ("drag", "walk", "oneshot"):
            return

        typing = sum(1 for t in self.kb_hits if now - t < TYPING_WINDOW) >= 3
        clicking = sum(1 for t in self.click_hits if now - t < CLICK_WINDOW) >= 2
        idle_ms = system_idle_ms()

        if self.mode == "react":
            if self.react_kind == "sleep":
                if idle_ms < 1500:  # 有输入了：醒来，跳一下欢迎
                    self.react_kind = None
                    self.play_oneshot("jump")
                return
            if self.react_kind == "working":
                last_kb = self.kb_hits[-1] if self.kb_hits else 0
                if now - last_kb > 2.5:
                    self.back_to_idle()
                return
            if self.react_kind == "checking":
                if typing:
                    self.start_react("working")
                    return
                last_click = self.click_hits[-1] if self.click_hits else 0
                if now - last_click > 2.0:
                    self.back_to_idle()
                return
            return

        # mode == idle
        if idle_ms > SLEEP_AFTER_MS:
            self.start_react("sleep")
        elif typing:
            self.start_react("working")
        elif clicking:
            self.start_react("checking")

    # ---------- 交互 ----------
    def on_press(self, e):
        self._drag = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())
        self._moved = False

    def on_drag(self, e):
        if self._drag is None:
            return
        cx = self.root.winfo_x()
        nx, ny = e.x_root - self._drag[0], e.y_root - self._drag[1]
        if abs(nx - cx) + abs(ny - self.root.winfo_y()) > 2:
            self._moved = True
        # 拖动方向 -> 对应走路动画
        dx = nx - cx
        if self._moved:
            if dx > 1 and self.anim != "walk-right":
                self.set_anim("walk-right", "drag")
            elif dx < -1 and self.anim != "walk-left":
                self.set_anim("walk-left", "drag")
            elif self.mode != "drag":
                self.mode = "drag"
        self.root.geometry(f"+{nx}+{ny}")

    def on_release(self, e):
        self._drag = None
        if self._moved:
            if self.mode == "drag":
                self.back_to_idle()
            self.save_pos()
            return
        # 单击：延迟一点，等双击事件先到
        if self._pending_wave:
            self.root.after_cancel(self._pending_wave)
        self._pending_wave = self.root.after(260, self._do_wave)

    def _do_wave(self):
        self._pending_wave = None
        self.play_oneshot("wave")

    def on_double(self, e):
        if self._pending_wave:
            self.root.after_cancel(self._pending_wave)
            self._pending_wave = None
        self.play_oneshot("jump")

    def on_hover(self, e):
        now = time.monotonic()
        if self.mode == "idle" and now - self.hover_at > HOVER_COOLDOWN:
            self.hover_at = now
            self.play_oneshot(random.choice(("observe-a", "observe-b", "wave")))

    def save_pos(self):
        self.cfg["x"], self.cfg["y"] = self.root.winfo_x(), self.root.winfo_y()
        save_config(self.cfg)

    # ---------- 菜单 ----------
    def on_menu(self, e):
        m = tk.Menu(self.root, tearoff=0)

        act = tk.Menu(m, tearoff=0)
        for name in self.sheet.anims:
            act.add_command(label=self.sheet.labels.get(name, name),
                            command=lambda n=name: self.play_oneshot(n))
        m.add_cascade(label="动作", menu=act)

        size = tk.Menu(m, tearoff=0)
        for label, s in SCALES:
            size.add_radiobutton(label=label, value=s,
                                 variable=tk.DoubleVar(value=self.scale),
                                 command=lambda s=s: self.set_scale(s))
        m.add_cascade(label="大小", menu=size)

        speed = tk.Menu(m, tearoff=0)
        for label, ms in SPEEDS:
            speed.add_radiobutton(label=label, value=ms,
                                  variable=tk.IntVar(value=self.frame_ms),
                                  command=lambda ms=ms: self.set_speed(ms))
        m.add_cascade(label="速度", menu=speed)

        m.add_separator()
        m.add_command(label="导入精灵图…", command=self.import_sheet)
        m.add_checkbutton(label="自由走动", onvalue=True, offvalue=False,
                          variable=tk.BooleanVar(value=self.wander),
                          command=self.toggle_wander)
        m.add_checkbutton(label="感知键鼠活动", onvalue=True, offvalue=False,
                          variable=tk.BooleanVar(value=self.sense),
                          command=self.toggle_sense)
        m.add_command(label="移到屏幕顶部", command=self.snap_top)
        m.add_command(label="移到右下角", command=self.snap_corner)
        m.add_checkbutton(label="开机自启", onvalue=True, offvalue=False,
                          variable=tk.BooleanVar(value=self.startup_enabled()),
                          command=self.toggle_startup)
        m.add_separator()
        m.add_command(label="退出", command=self.quit)
        m.tk_popup(e.x_root, e.y_root)

    def set_scale(self, s):
        self.scale = s
        self.frame_cache = {}
        self.frame_idx = 0
        self.set_anim_size()
        self.cfg["scale"] = s
        save_config(self.cfg)

    def set_speed(self, ms):
        self.frame_ms = ms
        self.cfg["speed_ms"] = ms
        save_config(self.cfg)

    def toggle_wander(self):
        self.wander = not self.wander
        self.cfg["wander"] = self.wander
        save_config(self.cfg)

    def toggle_sense(self):
        self.sense = not self.sense
        if not self.sense and self.mode == "react":
            self.back_to_idle()
        self.cfg["sense"] = self.sense
        save_config(self.cfg)

    def snap_top(self):
        x = self.root.winfo_x()
        self.root.geometry(f"+{x}+0")
        self.save_pos()

    def snap_corner(self):
        w, h = self.pet_size()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"+{sw - w - 80}+{sh - h - 120}")
        self.save_pos()

    # ---------- 开机自启 ----------
    def startup_bat(self):
        return os.path.join(os.environ.get("APPDATA", ""),
                            r"Microsoft\Windows\Start Menu\Programs\Startup",
                            "UPet.bat")

    def startup_enabled(self):
        return os.path.exists(self.startup_bat())

    def toggle_startup(self):
        bat = self.startup_bat()
        try:
            if self.startup_enabled():
                os.remove(bat)
            else:
                if getattr(sys, "frozen", False):
                    cmd = f'start "" "{sys.executable}"'
                else:
                    pyw = sys.executable.replace("python.exe", "pythonw.exe")
                    cmd = f'start "" "{pyw}" "{os.path.abspath(__file__)}"'
                with open(bat, "w", encoding="gbk") as f:
                    f.write(f"@echo off\n{cmd}\n")
        except Exception as e:
            messagebox.showerror(APP_NAME, f"设置开机自启失败：{e}")

    def quit(self):
        self.save_pos()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    UPet().run()
