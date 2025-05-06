# UUID: 11991ba7054f4e41b75350f969b272e3
import numpy as np
import time
import threading
import keyboard
import sys
import ctypes
import argparse
import socket
import json
from datetime import datetime
import uuid, os, sys
import mss
import mss.tools
from PyQt5 import QtWidgets, QtCore, QtGui

TARGET_COLOR_RGB = (170, 0, 0)

BASE_REGION = {"left": 918, "top": 6, "width": 79, "height": 68}
BASE_RESOLUTION = (1920, 1080)

COLOR_THRESHOLD = 30

COUNTDOWN_DURATION = 45

AUTO_DEFUSE_TIMING = 7.3  
AUTO_DEFUSE_KEY = '4'     
DEFUSE_TIME = 7.0         
NO_TIME_THRESHOLD = 6.9   

UDP_PORT = 25555          
UDP_BUFFER_SIZE = 1024    

countdown_active = False
countdown_thread = None
stop_event = threading.Event()
auto_defuse_active = False
defuse_thread = None
remaining_time = 0
auto_defuse_enabled = False
stop_hotkey = "home"      

SendInput = ctypes.windll.user32.SendInput
PUL = ctypes.POINTER(ctypes.c_ulong)

def spoof_signature():
    this_file = os.path.abspath(__file__)
    new_id = uuid.uuid4().hex

    with open(this_file, 'r+', encoding='utf-8') as f:
        lines = f.readlines()

        if lines and lines[0].startswith('# UUID:'):
            lines[0] = f'# UUID: {new_id}\n'
        else:
            lines.insert(0, f'# UUID: {new_id}\n')

        f.seek(0)
        f.writelines(lines)
        f.truncate()

spoof_signature()

class KeyBdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL)
    ]

class HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort)
    ]

class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL)
    ]

class InputI(ctypes.Union):
    _fields_ = [
        ("ki", KeyBdInput),
        ("mi", MouseInput),
        ("hi", HardwareInput)
    ]

class Input(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("ii", InputI)
    ]

def press_key(key):
    hex_key = ord(key)
    extra = ctypes.c_ulong(0)
    ii_ = InputI()
    ii_.ki = KeyBdInput(0, hex_key, 0x0008, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(1), ii_)
    SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

def release_key(key):
    hex_key = ord(key)
    extra = ctypes.c_ulong(0)
    ii_ = InputI()
    ii_.ki = KeyBdInput(0, hex_key, 0x0008 | 0x0002, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(1), ii_)
    SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

class MinimalTimerOverlay(QtWidgets.QWidget):
    update_signal = QtCore.pyqtSignal(float)
    reset_signal = QtCore.pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("System Helper") 
        self.setWindowFlags(
            QtCore.Qt.WindowStaysOnTopHint | 
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        
        screen = QtWidgets.QApplication.primaryScreen()
        self.screen_size = screen.size()
        
        self.setGeometry(
            self.screen_size.width() - 120, 
            self.screen_size.height() - 80,
            100, 60  
        )
        
        self.update_signal.connect(self.update_timer)
        self.reset_signal.connect(self.reset_display)
        
        self.timer_active = False
        self.time_value = 0
        
        self.setWindowOpacity(0.80)
        
        self.dragging = False
        self.offset = None
    
    def update_timer(self, time_value):
        self.timer_active = True
        self.time_value = time_value
        self.update()
    
    def reset_display(self):
        self.timer_active = False
        self.update()
    
    def paintEvent(self, event):
        if not self.timer_active:
            return
            
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        rect = self.rect()
        radius = 25  
        
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(rect), radius, radius)
        
        if self.time_value <= NO_TIME_THRESHOLD:
            bg_color = QtGui.QColor(60, 20, 20, 160)  
            text_color = QtGui.QColor(255, 100, 100)  
        else:
            bg_color = QtGui.QColor(20, 40, 20, 160)  
            text_color = QtGui.QColor(120, 255, 120)  
        
        painter.fillPath(path, bg_color)
        
        pen = QtGui.QPen(text_color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawPath(path)
        
        time_str = f"{self.time_value:.1f}"
        
        painter.setPen(text_color)
        font = QtGui.QFont("Arial", 16, QtGui.QFont.Bold)
        painter.setFont(font)
        
        painter.drawText(rect, QtCore.Qt.AlignCenter, time_str)
    
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.dragging = True
            self.offset = event.pos()

    def mouseMoveEvent(self, event):
        if self.dragging and self.offset:
            self.move(self.pos() + event.pos() - self.offset)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.dragging = False

def udp_server(overlay):
    global auto_defuse_enabled, stop_hotkey
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(('127.0.0.1', UDP_PORT))
    server_socket.settimeout(0.5)  
    
    print(f"Bomb timer sometimes detects bomb wrong so press home if it starts to stop it")
    
    while True:
        try:
            data, addr = server_socket.recvfrom(UDP_BUFFER_SIZE)
            
            try:
                command = json.loads(data.decode('utf-8'))
                
                if command.get("command") == "status":
                    status = {
                        "auto_defuse": auto_defuse_enabled,
                        "countdown_active": countdown_active,
                        "remaining_time": remaining_time if countdown_active else None,
                        "stop_hotkey": stop_hotkey
                    }
                    response = json.dumps(status)
                    server_socket.sendto(response.encode('utf-8'), addr)
                
                elif command.get("command") == "auto_defuse":
                    if "value" in command:
                        auto_defuse_enabled = bool(command["value"])
                        response = json.dumps({"success": True, "auto_defuse": auto_defuse_enabled})
                        server_socket.sendto(response.encode('utf-8'), addr)
                
                elif command.get("command") == "set_hotkey":
                    if "value" in command:
                        old_hotkey = stop_hotkey
                        new_hotkey = command["value"]
                        
                        try:
                            keyboard.unhook_key(old_hotkey)
                        except:
                            pass
                        
                        stop_hotkey = new_hotkey
                        keyboard.on_press_key(stop_hotkey, lambda _: reset_timer(overlay))
                        
                        response = json.dumps({"success": True, "hotkey": stop_hotkey})
                        server_socket.sendto(response.encode('utf-8'), addr)
                
                elif command.get("command") == "reset":
                    reset_timer(overlay)
                    response = json.dumps({"success": True})
                    server_socket.sendto(response.encode('utf-8'), addr)
                
                else:
                    response = json.dumps({"error": "Unknown command"})
                    server_socket.sendto(response.encode('utf-8'), addr)
            
            except json.JSONDecodeError:
                response = json.dumps({"error": "Invalid JSON format"})
                server_socket.sendto(response.encode('utf-8'), addr)
        
        except socket.timeout:
            pass
        
        except Exception as e:
            print(f"UDP server error: {e}")
            
        if not any(thread.name == "MainThread" and thread.is_alive() for thread in threading.enumerate()):
            break
            
        time.sleep(0.1)

def auto_defuse():
    global auto_defuse_active
    
    press_key(AUTO_DEFUSE_KEY)
    
    while not stop_event.is_set() and auto_defuse_active:
        time.sleep(0.01)
    
    release_key(AUTO_DEFUSE_KEY)

def countdown_timer(overlay):
    global countdown_active, auto_defuse_active, defuse_thread, remaining_time
    
    start_time = time.time()
    remaining = COUNTDOWN_DURATION
    auto_defuse_triggered = False
    
    while remaining > 0:
        if stop_event.is_set():
            break
            
        elapsed = time.time() - start_time
        remaining = COUNTDOWN_DURATION - elapsed
        remaining_time = remaining
        
        overlay.update_signal.emit(remaining)
        
        if auto_defuse_enabled and remaining <= AUTO_DEFUSE_TIMING and not auto_defuse_triggered:
            auto_defuse_active = True
            auto_defuse_triggered = True
            defuse_thread = threading.Thread(target=auto_defuse)
            defuse_thread.daemon = True
            defuse_thread.start()
        
        time.sleep(0.01)  
    
    countdown_active = False
    auto_defuse_active = False
    stop_event.clear()
    overlay.reset_signal.emit()
    
    if defuse_thread and defuse_thread.is_alive():
        defuse_thread.join(timeout=1)

def reset_timer(overlay):
    global countdown_active, countdown_thread, auto_defuse_active
    
    if countdown_active:
        stop_event.set()
        auto_defuse_active = False
        if countdown_thread:
            countdown_thread.join(timeout=1)
        countdown_active = False
        overlay.reset_signal.emit()

def get_scaled_region():
    with mss.mss() as sct:
        monitor = sct.monitors[1]  
        current_width = monitor["width"]
        current_height = monitor["height"]
    
    width_scale = current_width / BASE_RESOLUTION[0]
    height_scale = current_height / BASE_RESOLUTION[1]
    
    scaled_region = {
        "left": int(BASE_REGION["left"] * width_scale),
        "top": int(BASE_REGION["top"] * height_scale),
        "width": int(BASE_REGION["width"] * width_scale),
        "height": int(BASE_REGION["height"] * height_scale)
    }
    
    return scaled_region

def detect_color(overlay):
    global countdown_active, countdown_thread
    
    region = get_scaled_region()
    
    keyboard.on_press_key(stop_hotkey, lambda _: reset_timer(overlay))
    
    try:
        with mss.mss() as sct:
            while True:
                if not countdown_active:
                    screenshot = sct.grab(region)
                    
                    img = np.array(screenshot)
                    
                    target_bgr = (TARGET_COLOR_RGB[2], TARGET_COLOR_RGB[1], TARGET_COLOR_RGB[0])
                    
                    b_mask = np.abs(img[:,:,0].astype(np.int16) - target_bgr[0]) <= COLOR_THRESHOLD
                    g_mask = np.abs(img[:,:,1].astype(np.int16) - target_bgr[1]) <= COLOR_THRESHOLD
                    r_mask = np.abs(img[:,:,2].astype(np.int16) - target_bgr[2]) <= COLOR_THRESHOLD
                    
                    combined_mask = r_mask & g_mask & b_mask
                    
                    if np.any(combined_mask):
                        countdown_active = True
                        stop_event.clear()
                        countdown_thread = threading.Thread(target=countdown_timer, args=(overlay,))
                        countdown_thread.daemon = True
                        countdown_thread.start()
                
                time.sleep(0.01)
            
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        if countdown_active:
            stop_event.set()
            auto_defuse_active = False
            if countdown_thread:
                countdown_thread.join(timeout=1)

def main():
    parser = argparse.ArgumentParser(description="f ")
    parser.add_argument("--auto-defuse", action="store_true", help="Enable auto-defuse feature")
    args = parser.parse_args()
    
    global auto_defuse_enabled
    auto_defuse_enabled = args.auto_defuse
    
    app = QtWidgets.QApplication(sys.argv)
    
    overlay = MinimalTimerOverlay()
    overlay.show()
    
    udp_thread = threading.Thread(
        target=udp_server,
        args=(overlay,),
        daemon=True
    )
    udp_thread.start()
    
    detection_thread = threading.Thread(
        target=detect_color, 
        args=(overlay,),
        daemon=True
    )
    detection_thread.start()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
