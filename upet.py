# -*- coding: utf-8 -*-
"""UPet —— 独立桌面宠物小工具

不依赖 Codex：导入一张 Codex 格式的宠物精灵图（8 列 x 11 行），
就能常驻桌面、始终置顶、可拖动、可互动。

用法:
    python upet.py            # 直接运行
    pyinstaller 打包后双击 UPet.exe

互动:
    单击        -> 挥手
    双击        -> 跳跃
    左右拖动    -> 跟随方向播放走路动画
    Ctrl+上下拖 -> 连续放大缩小（脚底位置不动）
    鼠标滚轮    -> 逐级放大缩小
    鼠标悬停    -> 张望 / 挥手
    右键        -> 菜单（选择宠物 / 获取宠物 / 动作 / 设置 / 使用说明 / 退出）

获取宠物（「获取宠物」菜单按上手难度排序）:
    codexpets.net    -> 下载 zip，用「导入下载的宠物」选中即可，不需要命令行（首选）
    petdex.dev / awesome-codex-pet -> 库更大，但要复制页面上的 npx / PowerShell 命令执行
    装到 ~/.codex/pets 的宠物（含 Codex 生成的）会自动出现在画廊里一键切换。
    精灵图兼容 8x9 / 8x11 网格。

感知键鼠（可在右键菜单关闭，仅本机检测“是否有输入”，不记录内容）:
    连续打字       -> 思考工作
    连续点击鼠标   -> 检查
    键鼠长时间没动 -> 失落打瞌睡；回来时跳跃欢迎
"""
import ctypes
import hashlib
import json
import os
import random
import sys
import time
import tkinter as tk
import webbrowser
import zipfile
from collections import deque
from ctypes import wintypes
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

try:  # 界面主题（Windows 11 风格），缺了也能跑
    import darkdetect
    import sv_ttk
except ImportError:
    sv_ttk = darkdetect = None

APP_NAME = "UPet"
KEY_COLOR = "#ff00fe"  # 透明色键（画面中不会出现的颜色）
CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
CODEX_PETS_DIR = os.path.join(os.path.expanduser("~"), ".codex", "pets")   # Codex / petdex 等安装位置
MY_PETS_DIR = os.path.join(CONFIG_DIR, "pets")                             # 从 zip 导入的宠物存这里

# 宠物获取站点（右键菜单「获取宠物」）——按上手难度排，能直接下 zip 的排最前
PET_SITES = [
    ("CodexPets.net - 842+，下载 zip 导入（最简单）", "https://codexpets.net/"),
    ("Petdex - 3600+，页面复制命令安装（需要命令行）", "https://petdex.dev/"),
    ("Awesome Codex Pet - 中文社区精选（需要命令行）", "https://awesome-codex-pet.pages.dev/"),
]
DOCS_URL = "https://github.com/FANzR-arch/UPet/blob/main/docs/使用说明.md"

# 首次运行的气泡提示：把「右键是一切入口」这件事说清楚
TIP_TEXT = "单击我挥手，双击我跳跃\n按住拖动带我走，滚轮调大小\n右键打开菜单（换宠物 / 设置 / 退出）"
TIP_MS = 9000  # 气泡自动消失时间；用户一动手就提前收起

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
MIN_SCALE, MAX_SCALE = 0.25, 3.0
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


def resource_path(rel):
    """打包进 exe 的资源路径（PyInstaller 解压到 _MEIPASS）。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def file_md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def enable_dpi_awareness():
    """高分屏下保持画面清晰（125%/150% 缩放不再发虚）。"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def apply_theme(root):
    """应用 Sun Valley（Windows 11 风格）主题，跟随系统深浅色。"""
    if sv_ttk is None:
        return
    try:
        dark = bool(darkdetect and darkdetect.isDark())
        sv_ttk.set_theme("dark" if dark else "light")
    except Exception:
        pass


# 内置默认宠物：Phil仔（仓库自带的示例宠物）
BUNDLED_PET = resource_path("spritesheet.webp")


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


def extract_sheet_from_zip(zip_path):
    """从宠物 zip 包（如 codexpets.net 的下载包）提取精灵图，
    存到 %APPDATA%/UPet/pets/<包名>/，返回精灵图路径。"""
    with zipfile.ZipFile(zip_path) as z:
        imgs = [n for n in z.namelist()
                if n.lower().endswith((".webp", ".png")) and not n.endswith("/")]
        if not imgs:
            raise ValueError("zip 里没有找到 webp/png 图片")

        def score(n):
            base = os.path.basename(n).lower()
            s = z.getinfo(n).file_size
            if "spritesheet" in base:
                s += 10 ** 9
            elif "sprite" in base:
                s += 10 ** 8
            if "preview" in base or "thumb" in base or "source" in base:
                s -= 10 ** 8
            return s

        best = max(imgs, key=score)
        name = os.path.splitext(os.path.basename(zip_path))[0] or "pet"
        dest_dir = os.path.join(MY_PETS_DIR, name)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, "spritesheet" + os.path.splitext(best)[1].lower())
        with z.open(best) as src, open(dest, "wb") as out:
            out.write(src.read())
    return dest


class SpriteSheet:
    """解析精灵图：切格子、按透明度检测每行实际帧数。

    兼容 8x11（含张望行）和 8x9（仅动作行）等网格：
    列数固定为 8，行数按官方格子 192x208 的高宽比自动推算。
    """

    def __init__(self, path):
        self.path = path
        img = Image.open(path).convert("RGBA")
        self.cell_w = img.width // GRID_COLS
        if self.cell_w < 8:
            raise ValueError("图片太小，不像是 8 列的精灵图")
        est_ch = self.cell_w * 13.0 / 12.0   # 192:208 = 12:13
        rows = max(1, min(GRID_ROWS, round(img.height / est_ch)))
        self.rows = rows
        self.cell_h = img.height // rows
        self.image = img
        alpha = img.getchannel("A")
        self.anims = {}   # name -> (row, frame_count)
        self.labels = {}  # name -> 中文名
        for row, (name, label) in enumerate(ROW_LAYOUT[:rows]):
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

        enable_dpi_awareness()
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title(APP_NAME)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", KEY_COLOR)
        self.root.configure(bg=KEY_COLOR)
        try:  # 让对话框控件按系统缩放比例显示
            self.root.tk.call("tk", "scaling",
                              ctypes.windll.shcore.GetScaleFactorForDevice(0) / 75.0)
        except Exception:
            pass
        apply_theme(self.root)

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
        self._resize = None        # (起始 y_root, 起始 scale)，Ctrl 拖动缩放中
        self._resize_at = 0.0      # 上次应用缩放的时间（节流）
        self._tip = None           # 首次运行的提示气泡
        self._tip_job = None
        self._tips_pending = False # 画廊关掉后补一个演示

        self.label.bind("<ButtonPress-1>", self.on_press)
        self.label.bind("<B1-Motion>", self.on_drag)
        self.label.bind("<ButtonRelease-1>", self.on_release)
        self.label.bind("<Double-Button-1>", self.on_double)
        self.label.bind("<Button-3>", self.on_menu)
        self.label.bind("<Enter>", self.on_hover)
        self.label.bind("<MouseWheel>", self.on_wheel)

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
        elif not self.cfg.get("chooser_shown"):
            # 首次使用：宠物先出现，再弹出选择窗（不阻塞启动）；
            # 选完宠物关掉画廊后，宠物挥手 + 冒气泡把互动方式演示一遍
            self.cfg["chooser_shown"] = True
            save_config(self.cfg)
            self._tips_pending = True
            self.root.after(800, self.open_chooser)

    # ---------- 精灵图加载 ----------
    def try_load_initial_sheet(self):
        candidates = []
        if self.cfg.get("sheet"):
            candidates.append(self.cfg["sheet"])
        candidates.append(os.path.join(app_dir(), "spritesheet.webp"))
        candidates.append(BUNDLED_PET)   # 兜底：内置的 Codex 默认宠物
        for p in candidates:
            if p and os.path.exists(p) and self.load_sheet(p, quiet=True):
                return True
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
        # 内置宠物的临时解压路径不写入配置（每次启动位置都会变）
        if os.path.normpath(path) != os.path.normpath(BUNDLED_PET):
            self.cfg["sheet"] = path
        else:
            self.cfg.pop("sheet", None)
        save_config(self.cfg)
        return True

    def import_sheet(self):
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        path = filedialog.askopenfilename(
            title="选择宠物精灵图或宠物 zip 包",
            initialdir=downloads if os.path.isdir(downloads) else None,
            filetypes=[("宠物文件", "*.webp;*.png;*.zip"), ("所有文件", "*.*")])
        if not path:
            return self.sheet is not None
        return self.load_pet_file(path)

    def load_pet_file(self, path):
        """加载宠物文件：图片直接加载，zip 先提取精灵图。"""
        if path.lower().endswith(".zip"):
            try:
                path = extract_sheet_from_zip(path)
            except Exception as e:
                messagebox.showerror(APP_NAME, f"无法从 zip 导入宠物：\n{e}")
                return self.sheet is not None
        ok = self.load_sheet(path)
        if ok:
            self.set_anim("idle")
            self.set_anim_size()
        return ok

    def open_chooser(self):
        """宠物选择弹窗：内置/已安装列表 + 预览 + 导入 + 宠物站入口。"""
        if getattr(self, "_chooser", None) and self._chooser.winfo_exists():
            self._chooser.lift()
            return
        win = tk.Toplevel(self.root)
        self._chooser = win
        win.title("选择宠物 - UPet")
        win.attributes("-topmost", True)
        win.resizable(False, False)

        def on_closed(e):
            # 首次运行选完宠物 -> 演示一遍互动（子控件的 Destroy 不算）
            if e.widget is win and self._tips_pending:
                self._tips_pending = False
                self.root.after(500, self.show_tips)
        win.bind("<Destroy>", on_closed)

        try:
            win.iconbitmap(resource_path("icon.ico"))
        except Exception:
            pass

        items = self.pet_choices()

        body = ttk.Frame(win, padding=16)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text="选一只宠物放到桌面上",
                  font=("Microsoft YaHei UI", 13, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 12))

        # ---- 动图卡片画廊 ----
        style = ttk.Style()
        bg = style.lookup("TFrame", "background") or "#fafafa"
        dark = bool(darkdetect and darkdetect.isDark()) if darkdetect else False
        accent = "#4cc2ff" if dark else "#0067c0"
        COLS, THUMB = 3, (132, 143)
        CARD_H = 196
        n_rows = (len(items) + COLS - 1) // COLS

        gallery = ttk.Frame(body)
        gallery.grid(row=1, column=0, sticky="nsew")
        canvas = tk.Canvas(gallery, width=COLS * 172 + 4,
                           height=min(2, n_rows) * CARD_H,
                           bg=bg, highlightthickness=0, bd=0)
        canvas.grid(row=0, column=0)
        if n_rows > 2:
            vsb = ttk.Scrollbar(gallery, orient="vertical", command=canvas.yview)
            vsb.grid(row=0, column=1, sticky="ns", padx=(6, 0))
            canvas.configure(yscrollcommand=vsb.set)
        grid_frame = tk.Frame(canvas, bg=bg)
        canvas.create_window((0, 0), window=grid_frame, anchor="nw")
        grid_frame.bind("<Configure>",
                        lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win.bind("<MouseWheel>",
                 lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

        win._anims = []                       # 卡片动画帧
        selected = {"path": None, "card": None}

        def use_selected(_e=None):
            if selected["path"]:
                self.load_pet_file(selected["path"])
            win.destroy()

        def make_card(name, path):
            card = tk.Frame(grid_frame, bg=bg, highlightthickness=2,
                            highlightbackground=bg, cursor="hand2")
            img_lbl = tk.Label(card, bg=bg)
            img_lbl.pack(padx=10, pady=(10, 2))
            txt = tk.Label(card, text=name, bg=bg,
                           font=("Microsoft YaHei UI", 9), wraplength=140)
            txt.pack(pady=(0, 8))
            frames = []
            try:
                sh_ = SpriteSheet(path)
                row, count = sh_.anims["idle"]
                for i in range(count):
                    cell = sh_.image.crop((i * sh_.cell_w, row * sh_.cell_h,
                                           (i + 1) * sh_.cell_w, (row + 1) * sh_.cell_h))
                    cell.thumbnail(THUMB, Image.Resampling.LANCZOS)
                    frames.append(ImageTk.PhotoImage(cell))
            except Exception:
                txt.configure(text=f"{name}\n（无法加载）")
            if frames:
                img_lbl.configure(image=frames[0])
                win._anims.append({"lbl": img_lbl, "frames": frames, "i": 0})

            def select(_e=None):
                if selected["card"] is not None and selected["card"].winfo_exists():
                    selected["card"].configure(highlightbackground=bg)
                selected["path"], selected["card"] = path, card
                card.configure(highlightbackground=accent)

            for w in (card, img_lbl, txt):
                w.bind("<Button-1>", select)
                w.bind("<Double-Button-1>", lambda e: (select(), use_selected()))
            return card, select

        first_select = None
        for i, (name, path) in enumerate(items):
            card, sel_fn = make_card(name, path)
            card.grid(row=i // COLS, column=i % COLS, padx=5, pady=5, sticky="n")
            if first_select is None:
                first_select = sel_fn
        if first_select:
            first_select()

        def tick_gallery():
            if not win.winfo_exists():
                return
            for a in win._anims:
                a["i"] = (a["i"] + 1) % len(a["frames"])
                a["lbl"].configure(image=a["frames"][a["i"]])
            win.after(200, tick_gallery)

        win.after(200, tick_gallery)

        bar = ttk.Frame(body)
        bar.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        ttk.Button(bar, text="使用这只", style="Accent.TButton",
                   command=use_selected).pack(side="left")
        ttk.Button(bar, text="导入文件…",
                   command=lambda: (win.destroy(), self.import_sheet())).pack(
            side="left", padx=(10, 0))
        more = ttk.Menubutton(bar, text="更多宠物")
        mm = tk.Menu(more, tearoff=0)
        for label, url in PET_SITES:
            mm.add_command(label=label, command=lambda u=url: webbrowser.open(u))
        more.configure(menu=mm)
        more.pack(side="right")

        # 居中显示
        win.update_idletasks()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"+{max(20, (sw - w) // 2)}+{max(20, (sh - h) // 2)}")

    def pet_choices(self):
        """内置默认 + 已安装宠物，按文件内容去重（同一只宠物只出现一次）。"""
        choices, seen = [], set()
        for name, path in [("Phil仔（内置默认）", BUNDLED_PET)] + self.installed_pets():
            try:
                digest = file_md5(path)
            except OSError:
                continue
            if digest in seen:
                continue
            seen.add(digest)
            choices.append((name, path))
        return choices

    def installed_pets(self):
        """扫描本机已有的宠物：~/.codex/pets（Codex/petdex 等安装）+ UPet 自己导入的。"""
        pets = []
        for base in (CODEX_PETS_DIR, MY_PETS_DIR):
            if not os.path.isdir(base):
                continue
            try:
                names = sorted(os.listdir(base))
            except OSError:
                continue
            for d in names:
                for fn in ("spritesheet.webp", "spritesheet.png"):
                    p = os.path.join(base, d, fn)
                    if os.path.exists(p):
                        pets.append((d, p))
                        break
        return pets

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
        # 气泡还亮着时别乱跑，否则宠物走了、提示留在原地
        if self.mode != "idle" or self._tip is not None:
            self.schedule_ambient()
            return
        pool = [a for a in AMBIENT_POOL if a == "walk" or a in self.sheet.anims]
        choice = random.choice(pool)
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
    def apply_scale(self, s):
        """缩放并保持脚底位置不动。"""
        s = max(MIN_SCALE, min(MAX_SCALE, s))
        if abs(s - self.scale) < 0.01:
            return
        ow, oh = self.pet_size()
        x, y = self.root.winfo_x(), self.root.winfo_y()
        self.scale = s
        self.frame_cache = {}
        nw, nh = self.pet_size()
        nx, ny = x + (ow - nw) // 2, y + (oh - nh)
        self.root.geometry(f"{nw}x{nh}+{nx}+{ny}")
        frames = self.frames(self.anim)
        self.frame_idx %= len(frames)
        self.label.configure(image=frames[self.frame_idx])

    def save_scale(self):
        self.cfg["scale"] = self.scale
        save_config(self.cfg)
        self.save_pos()

    def on_wheel(self, e):
        factor = 1.08 if e.delta > 0 else 1 / 1.08
        self.apply_scale(self.scale * factor)
        self.save_scale()

    def on_press(self, e):
        self.hide_tips()      # 上手了就不用再看提示
        if e.state & 0x0004:  # 按住 Ctrl：进入拖动缩放
            self._resize = (e.y_root, self.scale)
            self._drag = None
            return
        self._drag = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())
        self._moved = False

    def on_drag(self, e):
        if self._resize is not None:
            now = time.monotonic()
            if now - self._resize_at < 0.04:  # 节流，避免高频重渲染
                return
            self._resize_at = now
            y0, s0 = self._resize
            self.apply_scale(s0 * (1 + (y0 - e.y_root) / 200.0))
            return
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
        if self._resize is not None:
            self._resize = None
            self.save_scale()
            return
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

    # ---------- 首次运行提示 ----------
    def show_tips(self):
        """宠物挥个手，旁边冒气泡说明怎么玩。点一下 / 动一下就收起。"""
        if self._tip is not None:
            return
        self.play_oneshot("wave")

        dark = bool(darkdetect and darkdetect.isDark()) if darkdetect else False
        bg = "#2b2b2b" if dark else "#ffffff"
        fg = "#f0f0f0" if dark else "#1a1a1a"
        edge = "#4cc2ff" if dark else "#0067c0"

        tip = tk.Toplevel(self.root)
        self._tip = tip
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tip.configure(bg=edge)          # 1px 描边靠外层背景色实现
        inner = tk.Frame(tip, bg=bg)
        inner.pack(padx=1, pady=1)
        lbl = tk.Label(inner, text=TIP_TEXT, bg=bg, fg=fg, justify="left",
                       font=("Microsoft YaHei UI", 9), padx=12, pady=9)
        lbl.pack()
        for w in (tip, inner, lbl):
            w.bind("<Button-1>", lambda e: self.hide_tips())

        # 贴在宠物上方；顶部放不下就翻到下方，再夹到屏幕内
        tip.update_idletasks()
        tw, th = tip.winfo_reqwidth(), tip.winfo_reqheight()
        pw, ph = self.pet_size()
        px, py = self.root.winfo_x(), self.root.winfo_y()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x, y = px + pw // 2 - tw // 2, py - th - 8
        if y < 8:
            y = py + ph + 8
        x = max(8, min(x, sw - tw - 8))
        y = max(8, min(y, sh - th - 8))
        tip.geometry(f"+{int(x)}+{int(y)}")

        self._tip_job = self.root.after(TIP_MS, self.hide_tips)

    def hide_tips(self):
        if self._tip_job is not None:
            self.root.after_cancel(self._tip_job)
            self._tip_job = None
        if self._tip is not None:
            if self._tip.winfo_exists():
                self._tip.destroy()
            self._tip = None

    # ---------- 菜单 ----------
    def on_menu(self, e):
        self.hide_tips()
        m = tk.Menu(self.root, tearoff=0)

        m.add_command(label="选择宠物…", command=self.open_chooser)

        get_menu = tk.Menu(m, tearoff=0)
        for label, url in PET_SITES:
            get_menu.add_command(label=label, command=lambda u=url: webbrowser.open(u))
        get_menu.add_separator()
        get_menu.add_command(label="导入下载的宠物（zip/图片）…", command=self.import_sheet)
        m.add_cascade(label="获取宠物", menu=get_menu)

        act = tk.Menu(m, tearoff=0)
        for name in self.sheet.anims:
            act.add_command(label=self.sheet.labels.get(name, name),
                            command=lambda n=name: self.play_oneshot(n))
        m.add_cascade(label="动作", menu=act)

        m.add_separator()

        settings = tk.Menu(m, tearoff=0)
        size = tk.Menu(settings, tearoff=0)
        for label, s in SCALES:
            size.add_radiobutton(label=label, value=s,
                                 variable=tk.DoubleVar(value=self.scale),
                                 command=lambda s=s: self.set_scale(s))
        settings.add_cascade(label="大小", menu=size)
        speed = tk.Menu(settings, tearoff=0)
        for label, ms in SPEEDS:
            speed.add_radiobutton(label=label, value=ms,
                                  variable=tk.IntVar(value=self.frame_ms),
                                  command=lambda ms=ms: self.set_speed(ms))
        settings.add_cascade(label="速度", menu=speed)
        settings.add_separator()
        settings.add_checkbutton(label="自由走动", onvalue=True, offvalue=False,
                                 variable=tk.BooleanVar(value=self.wander),
                                 command=self.toggle_wander)
        settings.add_checkbutton(label="感知键鼠活动", onvalue=True, offvalue=False,
                                 variable=tk.BooleanVar(value=self.sense),
                                 command=self.toggle_sense)
        settings.add_checkbutton(label="开机自启", onvalue=True, offvalue=False,
                                 variable=tk.BooleanVar(value=self.startup_enabled()),
                                 command=self.toggle_startup)
        settings.add_separator()
        settings.add_command(label="移到屏幕顶部", command=self.snap_top)
        settings.add_command(label="移到右下角", command=self.snap_corner)
        m.add_cascade(label="设置", menu=settings)

        m.add_command(label="使用说明", command=lambda: webbrowser.open(DOCS_URL))
        m.add_separator()
        m.add_command(label="退出", command=self.quit)
        m.tk_popup(e.x_root, e.y_root)

    def set_scale(self, s):
        self.apply_scale(s)
        self.save_scale()

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
