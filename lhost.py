# client.py
import socket
import struct
import threading
import cv2
import numpy as np
import time
import json

SERVER_IP = "192.168.0.20"   # 서버(조작당할 컴퓨터) IP로 바꿔 주세요
PORT = 6000
PASSWORD = "836554ccffb4"       # 서버와 동일하게 맞춰야 함

window_name = "Remote Desktop (press q to quit)"

sock = None
running = True
frame_lock = threading.Lock()
current_frame = None

def send_password(s):
    pw_bytes = PASSWORD.encode()
    s.sendall(struct.pack("!H", len(pw_bytes)))
    s.sendall(pw_bytes)
    resp = s.recv(3)
    if resp != b"OK":
        raise RuntimeError("Password rejected by server")

def recv_frames():
    global sock, current_frame, running
    try:
        while running:
            # read 8-byte length
            hdr = b""
            while len(hdr) < 8:
                more = sock.recv(8 - len(hdr))
                if not more:
                    running = False
                    return
                hdr += more
            size = struct.unpack("!Q", hdr)[0]
            data = b""
            while len(data) < size:
                chunk = sock.recv(min(65536, size - len(data)))
                if not chunk:
                    running = False
                    return
                data += chunk
            arr = np.frombuffer(data, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None:
                with frame_lock:
                    current_frame = img
    except Exception as e:
        print("[-] recv_frames error:", e)
        running = False

# OpenCV 마우스 콜백: 서버로 마우스 이벤트 전송
def on_mouse(event, x, y, flags, param):
    global sock
    if not running:
        return
    try:
        if event == cv2.EVENT_MOUSEMOVE:
            msg = {"kind":"mouse","action":"move","x":x,"y":y}
        elif event == cv2.EVENT_LBUTTONDOWN:
            msg = {"kind":"mouse","action":"down","x":x,"y":y,"button":"left"}
        elif event == cv2.EVENT_LBUTTONUP:
            msg = {"kind":"mouse","action":"up","x":x,"y":y,"button":"left"}
        elif event == cv2.EVENT_RBUTTONDOWN:
            msg = {"kind":"mouse","action":"down","x":x,"y":y,"button":"right"}
        elif event == cv2.EVENT_RBUTTONUP:
            msg = {"kind":"mouse","action":"up","x":x,"y":y,"button":"right"}
        else:
            return
        bs = json.dumps(msg).encode()
        sock.sendall(struct.pack("!I", len(bs)))
        sock.sendall(bs)
    except Exception as e:
        print("[-] mouse send error:", e)

# 키보드 이벤트 전송 (OpenCV의 waitKey 기반 간단 구현)
def handle_keys(key):
    # key는 ASCII 코드 혹은 special
    # ESC 종료
    if key == 27:  # ESC 키의 ASCII 코드
        return "quit"
    # 예: WASD를 화살표로 매핑하거나, 특정 키를 서버로 전달
    # 그냥 눌린 키를 server에 'press'로 보냅니다.
    try:
        ch = chr(key)
        if ch.isprintable():
            msg = {"kind":"key","action":"press","key":ch}
            bs = json.dumps(msg).encode()
            sock.sendall(struct.pack("!I", len(bs)))
            sock.sendall(bs)
    except:
        pass
    return None

def main():
    global sock, running, current_frame
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_IP, PORT))
    try:
        send_password(sock)
    except Exception as e:
        print("[-] password failed:", e)
        sock.close(); return

    threading.Thread(target=recv_frames, daemon=True).start()

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window_name, on_mouse)

    while running:
        with frame_lock:
            frame = None if current_frame is None else current_frame.copy()
        if frame is not None:
            cv2.imshow(window_name, frame)
        key = cv2.waitKey(30) & 0xFF
        if key != 255:
            action = handle_keys(key)
            if action == "quit":
                running = False
                break
    cv2.destroyAllWindows()
    try:
        sock.close()
    except:
        pass

if __name__ == "__main__":
    main()
