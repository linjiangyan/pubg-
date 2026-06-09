import tkinter as tk
from tkinter import ttk, colorchooser, messagebox, filedialog
import queue
import math
import json
import os
import sys
import time
import threading
import numpy as np
import cv2
from PIL import ImageGrab, Image, ImageDraw
from pynput import mouse, keyboard

# 尝试导入系统托盘库
try:
    import pystray
    from pystray import MenuItem as item
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False
    print("提示：未安装 pystray，无法最小化到系统托盘。如需托盘功能请运行 pip install pystray")

def resource_path(relative_path):
    """获取资源文件的绝对路径，兼容开发环境和打包后的 exe"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

TEMPLATE_DIR = resource_path("img_template")

class ScreenMarker:
    def __init__(self):
        self.lite_window = None
        self.marker_window = None
        self.tray_icon = None
        self.main_window_closed = False

        if not os.path.exists(TEMPLATE_DIR):
            os.makedirs(TEMPLATE_DIR)

        self.config_file = "marker_config.json"
        self.load_config()

        # 点位
        self.point1 = None
        self.point2 = None
        self.point3 = None
        self.point4 = None
        self.point5 = None

        # 比例尺档位
        self.scale_level = self.config.get('scale_level', 0)
        self.scale_pixels = self.config.get('scale_pixels', [100, 120, 150, 180, 220])
        self.max_level = 4

        # 滚轮调档开关
        self.wheel_listen_enable = False

        # 点位样式
        self.point_size = self.config.get('point_size', 5)
        self.p1_color = self.config.get('p1_color', '#FF4D4D')
        self.p2_color = self.config.get('p2_color', '#4D79FF')
        self.p3_color = self.config.get('p3_color', '#4C9A2A')
        self.p4_color = self.config.get('p4_color', '#FFB347')
        self.p5_color = self.config.get('p5_color', '#B266FF')

        # 快捷键
        self.hotkey1 = self.config.get('hotkey1', 'R')
        self.hotkey2 = self.config.get('hotkey2', 'T')
        self.hotkey3 = self.config.get('hotkey3', 'Y')
        self.hotkey4 = self.config.get('hotkey4', 'U')
        self.hotkey5 = self.config.get('hotkey5', 'I')
        self.hotkey_toggle = self.config.get('hotkey_toggle', 'Ctrl+H')
        self.hotkey_center = self.config.get('hotkey_center', 'Ctrl+C')
        self.hotkey_recog = self.config.get('hotkey_recog', 'Ctrl+G')

        # 距离面板
        self.lite_width = self.config.get('lite_width', 280)
        self.lite_height = self.config.get('lite_height', 190)
        self.lite_off_x = self.config.get('lite_off_x', 100)
        self.lite_off_y = self.config.get('lite_off_y', 100)
        self.text_size = self.config.get('text_size', 11)

        # 图像识别配置
        self.recog_switch = False
        self.match_threshold = self.config.get("match_threshold", 0.8)
        self.recognize_interval = self.config.get("recognize_interval", 0.5)
        self.recog_running = False
        self.stop_recog_event = threading.Event()
        self.recog_threads = []

        # 模板分组
        self.group1_tpls = []
        self.group3_tpls = []
        self.group4_tpls = []
        self.group5_tpls = []
        self.load_all_templates()

        self.input_queue = queue.Queue()
        self.ctrl_pressed = False
        self.alt_pressed = False
        self.shift_pressed = False
        self.current_key = None
        self.recording_hotkey = None
        self.txt_ids = []

        # 主窗口
        self.main_window = tk.Tk()
        self.main_window.title("🎯 多点位图像识别测距工具")
        self.main_window.geometry("1000x850")
        self.main_window.attributes('-topmost', True)
        self.main_window.resizable(False, False)
        self.main_window.configure(bg='#F0F2F5')
        self.main_window.protocol("WM_DELETE_WINDOW", self.hide_main_window)

        self.setup_styles()

        self.left_frame = tk.Frame(self.main_window, bg='#F0F2F5', width=480)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=15, pady=15, expand=True)
        self.right_frame = tk.Frame(self.main_window, bg='#F0F2F5', width=480)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=15, pady=15, expand=True)

        self.create_marker_window()
        self.create_lite_window()
        self.create_ui()

        self.start_listeners()
        self.process_queue()

        self.update_scale_display()
        self.init_lite_text()
        self.update_lite_data_only()

        if PYSTRAY_AVAILABLE:
            self.setup_tray_icon()
            self.main_window.withdraw()
        else:
            pass

    def setup_tray_icon(self):
        icon_size = 64
        image = Image.new('RGBA', (icon_size, icon_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((8, 8, icon_size-8, icon_size-8), fill=(255, 80, 80, 255))
        draw.ellipse((icon_size//2-4, icon_size//2-4, icon_size//2+4, icon_size//2+4), fill=(255, 255, 255, 255))
        menu = (
            item('显示设置', self.show_main_window),
            item('退出', self.quit_app)
        )
        self.tray_icon = pystray.Icon("pubg_distance_tool", image, "PUBG测距工具", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_main_window(self):
        if self.main_window and not self.main_window_closed:
            self.main_window.deiconify()
            self.main_window.lift()
            self.main_window.focus_force()

    def hide_main_window(self):
        if PYSTRAY_AVAILABLE:
            self.main_window.withdraw()
        else:
            self.on_close()

    def quit_app(self):
        self.main_window_closed = True
        if self.tray_icon:
            self.tray_icon.stop()
        self.on_close()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Card.TLabelframe', background='#FFFFFF', relief='flat', borderwidth=1)
        style.configure('Card.TLabelframe.Label', background='#FFFFFF', foreground='#2C3E50', font=('微软雅黑', 10, 'bold'))
        style.configure('Primary.TButton', font=('微软雅黑', 9), padding=5)
        style.map('Primary.TButton', background=[('active', '#2980B9'), ('pressed', '#1A5276')])
        style.configure('Highlight.TButton', font=('微软雅黑', 9, 'bold'), foreground='#FFFFFF', background='#E67E22')
        style.map('Highlight.TButton', background=[('active', '#D35400'), ('pressed', '#A04000')])

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = {}

    def save_config(self):
        cfg = {
            'scale_level': self.scale_level,
            'scale_pixels': self.scale_pixels,
            'point_size': self.point_size,
            'p1_color': self.p1_color,
            'p2_color': self.p2_color,
            'p3_color': self.p3_color,
            'p4_color': self.p4_color,
            'p5_color': self.p5_color,
            'hotkey1': self.hotkey1,
            'hotkey2': self.hotkey2,
            'hotkey3': self.hotkey3,
            'hotkey4': self.hotkey4,
            'hotkey5': self.hotkey5,
            'hotkey_toggle': self.hotkey_toggle,
            'hotkey_center': self.hotkey_center,
            'hotkey_recog': self.hotkey_recog,
            'lite_width': self.lite_width,
            'lite_height': self.lite_height,
            'lite_off_x': self.lite_off_x,
            'lite_off_y': self.lite_off_y,
            'text_size': self.text_size,
            'match_threshold': self.match_threshold,
            'recognize_interval': self.recognize_interval
        }
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)

    def load_all_templates(self):
        self.group1_tpls.clear()
        self.group3_tpls.clear()
        self.group4_tpls.clear()
        self.group5_tpls.clear()
        if not os.path.exists(TEMPLATE_DIR):
            return
        for fname in os.listdir(TEMPLATE_DIR):
            path = os.path.join(TEMPLATE_DIR, fname)
            if not os.path.isfile(path):
                continue
            lower = fname.lower()
            if lower.startswith("tpl_1_"):
                tpl = cv2.imread(path)
                if tpl is not None:
                    self.group1_tpls.append(tpl)
            elif lower.startswith("tpl_3_"):
                tpl = cv2.imread(path)
                if tpl is not None:
                    self.group3_tpls.append(tpl)
            elif lower.startswith("tpl_4_"):
                tpl = cv2.imread(path)
                if tpl is not None:
                    self.group4_tpls.append(tpl)
            elif lower.startswith("tpl_5_"):
                tpl = cv2.imread(path)
                if tpl is not None:
                    self.group5_tpls.append(tpl)

    def refresh_template(self):
        """刷新模板，并更新显示数量的标签"""
        self.load_all_templates()
        count_text = f"模板数量 | 点1: {len(self.group1_tpls)} | 点3: {len(self.group3_tpls)} | 点4: {len(self.group4_tpls)} | 点5: {len(self.group5_tpls)}"
        if hasattr(self, 'template_count_label'):
            self.template_count_label.config(text=count_text)

    def toggle_recognize(self):
        total = len(self.group1_tpls) + len(self.group3_tpls) + len(self.group4_tpls) + len(self.group5_tpls)
        if total == 0:
            messagebox.showwarning("提示", "未找到模板图片，请先放入 img_template 文件夹")
            return
        self.recog_switch = not self.recog_switch
        if self.recog_switch:
            self.recog_switch_btn.config(text="🔴 关闭图像识别", fg="white")
            self.stop_recog_event.clear()
            self.recog_threads = []
            for point_type in [1, 3, 4, 5]:
                t = threading.Thread(target=self.recognize_worker, args=(point_type,), daemon=True)
                t.start()
                self.recog_threads.append(t)
        else:
            self.recog_switch_btn.config(text="🟢 开启图像识别", fg="white")
            self.stop_recog_event.set()
            for t in self.recog_threads:
                t.join(timeout=0.5)
            self.recog_threads.clear()
        self.update_lite_data_only()

    def recognize_worker(self, point_type):
        while not self.stop_recog_event.is_set():
            try:
                screen = ImageGrab.grab()
                screen_cv = cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2BGR)
                if point_type == 1:
                    tpls = self.group1_tpls
                elif point_type == 3:
                    tpls = self.group3_tpls
                elif point_type == 4:
                    tpls = self.group4_tpls
                elif point_type == 5:
                    tpls = self.group5_tpls
                else:
                    return
                for tpl in tpls:
                    h, w = tpl.shape[:2]
                    res = cv2.matchTemplate(screen_cv, tpl, cv2.TM_CCOEFF_NORMED)
                    loc = np.where(res >= self.match_threshold)
                    for pt in zip(*loc[::-1]):
                        cx = pt[0] + w // 2
                        cy = pt[1] + h // 2 + 9
                        self.input_queue.put(('add_point', point_type, cx, cy))
                        break
                    else:
                        continue
                    break
            except Exception:
                pass
            time.sleep(self.recognize_interval)

    def update_threshold(self, val):
        self.match_threshold = float(val)
        self.thresh_label.config(text=f"匹配阈值：{self.match_threshold:.2f}")
        self.save_config()

    def create_marker_window(self):
        self.marker_window = tk.Toplevel(self.main_window)
        self.marker_window.title("标注层")
        self.marker_window.attributes('-fullscreen', True)
        self.marker_window.attributes('-topmost', True)
        self.marker_window.attributes('-transparentcolor', '#010101')
        self.marker_window.configure(bg='#010101')
        self.marker_window.overrideredirect(True)
        self.canvas = tk.Canvas(self.marker_window, bg='#010101', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

    def toggle_marker_visibility(self):
        if self.marker_window.state() == 'normal':
            self.marker_window.withdraw()
            self.toggle_btn.config(text="👁️ 显示标注")
        else:
            self.marker_window.deiconify()
            self.toggle_btn.config(text="🙈 隐藏标注")

    def redraw_all_points(self):
        self.canvas.delete("all")
        r = self.point_size
        if self.point1:
            x, y = self.point1
            self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=self.p1_color, outline='')
        if self.point2:
            x, y = self.point2
            self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=self.p2_color, outline='')
        if self.point3:
            x, y = self.point3
            self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=self.p3_color, outline='')
        if self.point4:
            x, y = self.point4
            self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=self.p4_color, outline='')
        if self.point5:
            x, y = self.point5
            self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=self.p5_color, outline='')

    def create_lite_window(self):
        if self.lite_window:
            self.lite_window.destroy()
        self.lite_window = tk.Toplevel(self.main_window)
        self.lite_window.geometry(f"{self.lite_width}x{self.lite_height}+{self.lite_off_x}+{self.lite_off_y}")
        self.lite_window.attributes('-topmost', True)
        self.lite_window.attributes('-transparentcolor', 'black')
        self.lite_window.configure(bg='black')
        self.lite_window.overrideredirect(True)
        self.lite_canvas = tk.Canvas(self.lite_window, bg='black', highlightthickness=0)
        self.lite_canvas.pack(fill=tk.BOTH, expand=True)

    def draw_outline_text(self, x, y, text, font, fill_color='white'):
        out_w = 1
        for dx in range(-out_w, out_w+1):
            for dy in range(-out_w, out_w+1):
                if dx != 0 or dy != 0:
                    self.lite_canvas.create_text(x+dx, y+dy, text=text, font=font, fill="black")
        return self.lite_canvas.create_text(x, y, text=text, font=font, fill=fill_color)

    def init_lite_text(self):
        self.lite_canvas.delete("all")
        self.txt_ids.clear()
        w = self.lite_width
        h = self.lite_height
        font = ("微软雅黑", self.text_size)
        lines = ["状态", "黄标距离", "橙标距离", "蓝标距离", "绿标距离"]
        line_height = self.text_size + 12
        total_height = len(lines) * line_height
        y_start = (h - total_height) // 2
        for i, line in enumerate(lines):
            y = y_start + i * line_height
            text_id = self.draw_outline_text(w//2, y, f"{line}: --", font, fill_color='white')
            self.txt_ids.append(text_id)

    def update_lite_data_only(self):
        if not self.lite_canvas:
            return
        wheel_status = "开启" if self.wheel_listen_enable else "关闭"
        recog_status = "开启" if self.recog_switch else "关闭"
        scale_val = self.scale_pixels[self.scale_level]
        status_text = f"挡位：{self.scale_level} 滚轮：{wheel_status} 图像识别：{recog_status}"
        self.lite_canvas.itemconfig(self.txt_ids[0], text=status_text)

        p2 = self.point2
        points = [self.point1, self.point3, self.point4, self.point5]
        labels = ["黄标距离", "橙标距离", "蓝标距离", "绿标距离"]
        for i, pt in enumerate(points):
            if p2 and pt and scale_val > 0:
                x1, y1 = p2
                x2, y2 = pt
                px = math.hypot(x2 - x1, y2 - y1)
                real = (px / scale_val) * 100.0
                text = f"{labels[i]}: {real:.1f} 米"
            else:
                text = f"{labels[i]}: -- 米"
            self.lite_canvas.itemconfig(self.txt_ids[1+i], text=text)

    def apply_lite_settings(self):
        try:
            w = int(self.lite_width_entry.get())
            h = int(self.lite_height_entry.get())
            ox = int(self.off_x_entry.get())
            oy = int(self.off_y_entry.get())
            if w <= 0 or h <= 0:
                raise ValueError
            self.lite_width = w
            self.lite_height = h
            self.lite_off_x = ox
            self.lite_off_y = oy
            self.create_lite_window()
            self.init_lite_text()
            self.update_lite_data_only()
            self.save_config()
        except:
            messagebox.showerror("错误", "数值必须为正整数")

    def create_ui(self):
        # ========== 左侧区域 ==========
        recog_frame = ttk.LabelFrame(self.left_frame, text="🔍 图像识别", style='Card.TLabelframe', padding=10)
        recog_frame.pack(fill=tk.X, pady=(0, 12))

        # 刷新按钮和模板数量显示
        top_row = tk.Frame(recog_frame, bg='#FFFFFF')
        top_row.pack(fill=tk.X, pady=(0, 5))
        tk.Button(top_row, text="🔄 刷新模板图片", command=self.refresh_template,
                  bg='#3498DB', fg='white', font=('微软雅黑', 9), relief='flat', padx=5, pady=3).pack(side=tk.LEFT)
        # 模板数量标签
        self.template_count_label = tk.Label(top_row, text="模板数量 | 点1:0 | 点3:0 | 点4:0 | 点5:0",
                                             font=('微软雅黑', 8), fg='#2C3E50', bg='#FFFFFF')
        self.template_count_label.pack(side=tk.RIGHT, padx=5)

        self.recog_switch_btn = tk.Button(recog_frame, text="🟢 开启图像识别", command=self.toggle_recognize,
                                          bg='#2ECC71', fg='white', font=('微软雅黑', 9, 'bold'), relief='flat', padx=5, pady=5)
        self.recog_switch_btn.pack(fill=tk.X, pady=(0, 8))

        threshold_frame = tk.Frame(recog_frame, bg='#FFFFFF')
        threshold_frame.pack(fill=tk.X, pady=5)
        tk.Label(threshold_frame, text="匹配阈值", font=('微软雅黑', 9), bg='#FFFFFF').pack(side=tk.LEFT)
        self.thresh_scale = tk.Scale(threshold_frame, from_=0.5, to=1.0, resolution=0.01, orient=tk.HORIZONTAL,
                                     command=self.update_threshold, bg='#FFFFFF', highlightthickness=0)
        self.thresh_scale.set(self.match_threshold)
        self.thresh_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        self.thresh_label = tk.Label(threshold_frame, text=f"{self.match_threshold:.2f}", width=5, font=('微软雅黑', 9), bg='#FFFFFF')
        self.thresh_label.pack(side=tk.RIGHT)

        point_frame = ttk.LabelFrame(self.left_frame, text="🎨 点位样式", style='Card.TLabelframe', padding=10)
        point_frame.pack(fill=tk.X, pady=(0, 12))

        size_frame = tk.Frame(point_frame, bg='#FFFFFF')
        size_frame.pack(fill=tk.X, pady=5)
        tk.Label(size_frame, text="点位大小", font=('微软雅黑', 9), bg='#FFFFFF').pack(side=tk.LEFT)
        self.size_scale = tk.Scale(size_frame, from_=1, to=10, orient=tk.HORIZONTAL, command=self.change_point_size,
                                   bg='#FFFFFF', highlightthickness=0)
        self.size_scale.set(self.point_size)
        self.size_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        color_frame = tk.Frame(point_frame, bg='#FFFFFF')
        color_frame.pack(fill=tk.X, pady=5)
        colors = [(self.p1_color, "点1", self.choose_p1_color),
                  (self.p2_color, "点2", self.choose_p2_color),
                  (self.p3_color, "点3", self.choose_p3_color),
                  (self.p4_color, "点4", self.choose_p4_color),
                  (self.p5_color, "点5", self.choose_p5_color)]
        for i, (col, name, cmd) in enumerate(colors):
            btn = tk.Button(color_frame, text=name, bg=col, fg='white' if col != '#FFB347' else 'black',
                            font=('微软雅黑', 8), width=6, relief='flat', command=cmd)
            btn.grid(row=i//3, column=i%3, padx=5, pady=2, sticky='ew')
        color_frame.columnconfigure(0, weight=1)
        color_frame.columnconfigure(1, weight=1)
        color_frame.columnconfigure(2, weight=1)

        func_frame = ttk.LabelFrame(self.left_frame, text="⚙️ 常用功能", style='Card.TLabelframe', padding=10)
        func_frame.pack(fill=tk.X, pady=(0, 12))

        self.toggle_btn = tk.Button(func_frame, text="🙈 隐藏标注", command=self.toggle_marker_visibility,
                                    bg='#95A5A6', fg='white', font=('微软雅黑', 9), relief='flat', padx=5, pady=3)
        self.toggle_btn.pack(fill=tk.X, pady=2)
        tk.Button(func_frame, text="🗑️ 清空所有点位", command=self.clear_all_points,
                  bg='#E74C3C', fg='white', font=('微软雅黑', 9), relief='flat', padx=5, pady=3).pack(fill=tk.X, pady=2)

        # ========== 右侧区域 ==========
        scale_frame = ttk.LabelFrame(self.right_frame, text="📏 比例尺档位", style='Card.TLabelframe', padding=10)
        scale_frame.pack(fill=tk.X, pady=(0, 12))

        self.scale_entries = []
        scale_labels = ["不缩放", "缩放1次", "缩放2次", "缩放3次", "缩放4次"]
        for i, lab in enumerate(scale_labels):
            row = tk.Frame(scale_frame, bg='#FFFFFF')
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=lab, width=10, anchor='w', font=('微软雅黑', 9), bg='#FFFFFF').pack(side=tk.LEFT)
            ent = tk.Entry(row, width=8, font=('微软雅黑', 9), relief='solid', bd=1)
            ent.insert(0, str(self.scale_pixels[i]))
            ent.pack(side=tk.RIGHT, padx=5)
            ent.bind("<Return>", lambda e, idx=i: self.set_scale_pixel(idx))
            self.scale_entries.append(ent)

        tk.Button(scale_frame, text="✅ 保存所有缩放设置", command=self.apply_all_scale,
                  bg='#3498DB', fg='white', font=('微软雅黑', 9), relief='flat', padx=5, pady=3).pack(fill=tk.X, pady=5)

        level_btn_frame = tk.Frame(scale_frame, bg='#FFFFFF')
        level_btn_frame.pack(fill=tk.X, pady=5)
        for i in range(5):
            tk.Button(level_btn_frame, text=str(i), width=4, command=lambda lv=i: self.set_scale_level(lv),
                      bg='#BDC3C7', fg='black', relief='flat').pack(side=tk.LEFT, padx=2, expand=True)

        self.scale_display = tk.Label(scale_frame, text="当前档位：--", fg='#2980B9', font=('微软雅黑', 9, 'bold'), bg='#FFFFFF')
        self.scale_display.pack(pady=5)

        hotkey_frame = ttk.LabelFrame(self.right_frame, text="⌨️ 快捷键 (点击输入框后按键录制)", style='Card.TLabelframe', padding=10)
        hotkey_frame.pack(fill=tk.X, pady=(0, 12))

        def bind_hk(entry, tag):
            entry.bind("<FocusIn>", lambda e: self.recording_hotkey_set(tag))
            entry.bind("<FocusOut>", lambda e: self.recording_hotkey_clear())

        hk_list = [
            ("点1", "hk1"), ("点2", "hk2"), ("点3", "hk3"),
            ("点4", "hk4"), ("点5", "hk5"), ("显隐标注", "toggle"), ("点2居中", "center"),
            ("图像识别开关", "recog")
        ]
        self.hk_entry_map = {}
        for row, (name, tag) in enumerate(hk_list):
            frame = tk.Frame(hotkey_frame, bg='#FFFFFF')
            frame.pack(fill=tk.X, pady=2)
            tk.Label(frame, text=name, width=10, anchor='w', font=('微软雅黑', 9), bg='#FFFFFF').pack(side=tk.LEFT)
            ent = tk.Entry(frame, width=12, font=('微软雅黑', 9), relief='solid', bd=1)
            if tag == "hk1": ent.insert(0, self.hotkey1)
            elif tag == "hk2": ent.insert(0, self.hotkey2)
            elif tag == "hk3": ent.insert(0, self.hotkey3)
            elif tag == "hk4": ent.insert(0, self.hotkey4)
            elif tag == "hk5": ent.insert(0, self.hotkey5)
            elif tag == "toggle": ent.insert(0, self.hotkey_toggle)
            elif tag == "center": ent.insert(0, self.hotkey_center)
            elif tag == "recog": ent.insert(0, self.hotkey_recog)
            ent.pack(side=tk.RIGHT, padx=5)
            bind_hk(ent, tag)
            self.hk_entry_map[tag] = ent

        lite_frame = ttk.LabelFrame(self.right_frame, text="📊 悬浮距离面板", style='Card.TLabelframe', padding=10)
        lite_frame.pack(fill=tk.X, pady=(0, 12))

        param_frame = tk.Frame(lite_frame, bg='#FFFFFF')
        param_frame.pack(fill=tk.X, pady=5)
        self.lite_width_entry = tk.Entry(param_frame, width=6, font=('微软雅黑', 9), relief='solid', bd=1)
        self.lite_height_entry = tk.Entry(param_frame, width=6, font=('微软雅黑', 9), relief='solid', bd=1)
        self.off_x_entry = tk.Entry(param_frame, width=6, font=('微软雅黑', 9), relief='solid', bd=1)
        self.off_y_entry = tk.Entry(param_frame, width=6, font=('微软雅黑', 9), relief='solid', bd=1)

        self.lite_width_entry.insert(0, str(self.lite_width))
        self.lite_height_entry.insert(0, str(self.lite_height))
        self.off_x_entry.insert(0, str(self.lite_off_x))
        self.off_y_entry.insert(0, str(self.lite_off_y))

        labels_pos = [("宽:", self.lite_width_entry), ("高:", self.lite_height_entry),
                      ("X偏移:", self.off_x_entry), ("Y偏移:", self.off_y_entry)]
        for i, (txt, ent) in enumerate(labels_pos):
            tk.Label(param_frame, text=txt, font=('微软雅黑', 9), bg='#FFFFFF').grid(row=i//2, column=(i%2)*2, sticky='w', padx=5)
            ent.grid(row=i//2, column=(i%2)*2+1, padx=5, pady=2)

        font_frame = tk.Frame(lite_frame, bg='#FFFFFF')
        font_frame.pack(fill=tk.X, pady=5)
        tk.Label(font_frame, text="字体大小", font=('微软雅黑', 9), bg='#FFFFFF').pack(side=tk.LEFT)
        self.text_size_scale = tk.Scale(font_frame, from_=8, to=20, orient=tk.HORIZONTAL, command=self.change_text_size,
                                        bg='#FFFFFF', highlightthickness=0)
        self.text_size_scale.set(self.text_size)
        self.text_size_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        tk.Button(lite_frame, text="📌 应用面板设置", command=self.apply_lite_settings,
                  bg='#9B59B6', fg='white', font=('微软雅黑', 9), relief='flat', padx=5, pady=3).pack(fill=tk.X, pady=5)

        tip_frame = tk.Frame(self.right_frame, bg='#F0F2F5')
        tip_frame.pack(fill=tk.X, pady=5)
        tk.Label(tip_frame, text="作者qq：2891357674",
                 font=('微软雅黑', 8), fg='#7F8C8D', bg='#F0F2F5').pack()

        # 初次刷新模板数量
        self.refresh_template()

    def change_point_size(self, val):
        self.point_size = int(val)
        self.save_config()
        self.redraw_all_points()

    def change_text_size(self, val):
        self.text_size = int(val)
        self.save_config()
        self.create_lite_window()
        self.init_lite_text()
        self.update_lite_data_only()

    def choose_p1_color(self):
        c = colorchooser.askcolor(initialcolor=self.p1_color)[1]
        if c:
            self.p1_color = c
            self.save_config()
            self.redraw_all_points()
    def choose_p2_color(self):
        c = colorchooser.askcolor(initialcolor=self.p2_color)[1]
        if c:
            self.p2_color = c
            self.save_config()
            self.redraw_all_points()
    def choose_p3_color(self):
        c = colorchooser.askcolor(initialcolor=self.p3_color)[1]
        if c:
            self.p3_color = c
            self.save_config()
            self.redraw_all_points()
    def choose_p4_color(self):
        c = colorchooser.askcolor(initialcolor=self.p4_color)[1]
        if c:
            self.p4_color = c
            self.save_config()
            self.redraw_all_points()
    def choose_p5_color(self):
        c = colorchooser.askcolor(initialcolor=self.p5_color)[1]
        if c:
            self.p5_color = c
            self.save_config()
            self.redraw_all_points()

    def add_point(self, p_type, x, y):
        if p_type == 1:
            self.point1 = (x, y)
        elif p_type == 2:
            self.point2 = (x, y)
        elif p_type == 3:
            self.point3 = (x, y)
        elif p_type == 4:
            self.point4 = (x, y)
        elif p_type == 5:
            self.point5 = (x, y)
        self.main_window.after(0, self.redraw_all_points)
        self.main_window.after(0, self.update_lite_data_only)

    def clear_all_points(self):
        self.point1 = self.point2 = self.point3 = self.point4 = self.point5 = None
        self.main_window.after(0, self.redraw_all_points)
        self.main_window.after(0, self.update_lite_data_only)

    def move_point2_to_center(self):
        sw = self.main_window.winfo_screenwidth()
        sh = self.main_window.winfo_screenheight()
        self.point2 = (sw//2, sh//2)
        self.main_window.after(0, self.redraw_all_points)
        self.main_window.after(0, self.update_lite_data_only)

    def set_scale_pixel(self, idx):
        try:
            v = int(self.scale_entries[idx].get())
            if v <= 0: raise ValueError
            self.scale_pixels[idx] = v
            self.save_config()
            self.update_scale_display()
            self.update_lite_data_only()
        except:
            self.scale_entries[idx].delete(0, tk.END)
            self.scale_entries[idx].insert(0, str(self.scale_pixels[idx]))

    def apply_all_scale(self):
        for i in range(5):
            self.set_scale_pixel(i)

    def set_scale_level(self, lv):
        if 0 <= lv <= self.max_level:
            self.scale_level = lv
            self.save_config()
            self.update_scale_display()
            self.update_lite_data_only()

    def update_scale_display(self):
        val = self.scale_pixels[self.scale_level]
        self.scale_display.config(text=f"当前缩放：{self.scale_level}  100米 = {val}像素")

    def toggle_wheel(self):
        self.wheel_listen_enable = not self.wheel_listen_enable
        self.update_lite_data_only()

    def wheel_prev_level(self):
        if self.scale_level > 0:
            self.set_scale_level(self.scale_level - 1)

    def wheel_next_level(self):
        if self.scale_level < self.max_level:
            self.set_scale_level(self.scale_level + 1)

    def recording_hotkey_set(self, tag):
        self.recording_hotkey = tag

    def recording_hotkey_clear(self):
        self.recording_hotkey = None

    def parse_key_name(self, key):
        mods = []
        if self.ctrl_pressed: mods.append("Ctrl")
        if self.alt_pressed: mods.append("Alt")
        if self.shift_pressed: mods.append("Shift")
        if hasattr(key, "vk") and 96 <= key.vk <= 105:
            return "+".join(mods + [f"Numpad{key.vk-96}"])
        try:
            return "+".join(mods + [key.char.upper()])
        except AttributeError:
            if key == keyboard.Key.esc: return "ESC"
            elif key == keyboard.Key.enter: return "+".join(mods+["Enter"])
            else: return "+".join(mods + [str(key).split('.')[-1].upper()])

    def start_listeners(self):
        self.keyboard_listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.mouse_listener = mouse.Listener(on_click=self.on_mouse_click, on_scroll=self.on_mouse_scroll)
        self.keyboard_listener.start()
        self.mouse_listener.start()

    def on_mouse_scroll(self, x, y, dx, dy):
        if not self.wheel_listen_enable:
            return
        if dy > 0:
            self.wheel_next_level()
        else:
            self.wheel_prev_level()

    def on_key_press(self, key):
        if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl_pressed = True
        elif key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
            self.alt_pressed = True
        elif key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
            self.shift_pressed = True

        try:
            if key.char.lower() == 'm' and not (self.ctrl_pressed or self.alt_pressed or self.shift_pressed):
                self.toggle_wheel()
                return
        except AttributeError:
            pass

        if self.recording_hotkey:
            name = self.parse_key_name(key)
            tag = self.recording_hotkey
            ent = self.hk_entry_map[tag]
            ent.delete(0, tk.END)
            ent.insert(0, name)
            if tag == "hk1": self.hotkey1 = name
            elif tag == "hk2": self.hotkey2 = name
            elif tag == "hk3": self.hotkey3 = name
            elif tag == "hk4": self.hotkey4 = name
            elif tag == "hk5": self.hotkey5 = name
            elif tag == "toggle": self.hotkey_toggle = name
            elif tag == "center": self.hotkey_center = name
            elif tag == "recog": self.hotkey_recog = name
            self.save_config()
            return

        try:
            self.current_key = key.char.upper()
        except Exception:
            self.current_key = str(key).split('.')[-1].upper()
        self.check_hotkey_action()

    def on_key_release(self, key):
        if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl_pressed = False
        elif key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
            self.alt_pressed = False
        elif key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
            self.shift_pressed = False
        else:
            self.current_key = None

    def check_hotkey_action(self):
        if not self.current_key:
            return
        mods = []
        if self.ctrl_pressed: mods.append("Ctrl")
        if self.alt_pressed: mods.append("Alt")
        if self.shift_pressed: mods.append("Shift")
        combo = "+".join(mods + [self.current_key])
        if combo == self.hotkey_recog:
            self.toggle_recognize()
        elif combo == self.hotkey_toggle:
            self.toggle_marker_visibility()
        elif combo == self.hotkey_center:
            self.move_point2_to_center()

    def on_mouse_click(self, x, y, button, pressed):
        if not pressed or button != mouse.Button.left:
            return
        if not self.current_key or self.ctrl_pressed or self.alt_pressed or self.shift_pressed:
            return
        key = self.current_key
        if key == self.hotkey1:
            self.input_queue.put(('add_point', 1, x, y))
        elif key == self.hotkey2:
            self.input_queue.put(('add_point', 2, x, y))
        elif key == self.hotkey3:
            self.input_queue.put(('add_point', 3, x, y))
        elif key == self.hotkey4:
            self.input_queue.put(('add_point', 4, x, y))
        elif key == self.hotkey5:
            self.input_queue.put(('add_point', 5, x, y))

    def process_queue(self):
        try:
            while True:
                msg = self.input_queue.get_nowait()
                if msg[0] == "add_point":
                    _, p_t, x, y = msg
                    self.add_point(p_t, x, y)
        except queue.Empty:
            pass
        self.main_window.after(100, self.process_queue)

    def on_close(self):
        self.recog_switch = False
        self.stop_recog_event.set()
        if hasattr(self, "keyboard_listener"): self.keyboard_listener.stop()
        if hasattr(self, "mouse_listener"): self.mouse_listener.stop()
        if self.marker_window: self.marker_window.destroy()
        if self.lite_window: self.lite_window.destroy()
        self.save_config()
        self.main_window.quit()
        self.main_window.destroy()

    def run(self):
        self.main_window.mainloop()


if __name__ == "__main__":
    app = ScreenMarker()
    app.run()