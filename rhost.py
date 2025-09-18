# server.py
import socket
import threading
import struct
import mss
import numpy as np
import cv2
import pyautogui
import time

HOST = "0.0.0.0"
PORT = 6000
PASSWORD = "836554ccffb4"
JPEG_QUALITY = 60           # 1~95
FPS = 8                     # 초당 프레임

def handle_client(conn, addr):
    print(f"[+] Connected: {addr}")
    try:
        # 1) 간단한 비밀번호 핸드셰이크 (클라이언트가 먼저 보냄)
        pw_len_data = conn.recv(2)
        if not pw_len_data:
            print("[-] no password length")
            conn.close(); return
        pw_len = struct.unpack("!H", pw_len_data)[0]
        pw = conn.recv(pw_len).decode()
        if pw != PASSWORD:
            print("[-] wrong password, closing")
            conn.sendall(b"PWERR")
            conn.close(); return
        conn.sendall(b"OK")

        stop_event = threading.Event()

        # 입력(명령) 리시브 스레드: 클라이언트로부터 마우스/키 이벤트 수신
        def recv_inputs():
            while not stop_event.is_set():
                # protocol: cmd_len(4) + cmd_bytes(json utf-8)
                hdr = conn.recv(4)
                if not hdr:
                    stop_event.set(); break
                msg_len = struct.unpack("!I", hdr)[0]
                data = b""
                while len(data) < msg_len:
                    chunk = conn.recv(msg_len - len(data))
                    if not chunk:
                        stop_event.set(); break
                    data += chunk
                if not data:
                    break
                try:
                    import json
                    msg = json.loads(data.decode())
                    kind = msg.get("kind")
                    if kind == "mouse":
                        x, y = msg["x"], msg["y"]
                        btn = msg.get("button")
                        action = msg.get("action")  # "move","click","down","up","scroll"
                        if action == "move":
                            pyautogui.moveTo(x, y)
                        elif action == "click":
                            pyautogui.click(x, y, button=btn or "left")
                        elif action == "down":
                            pyautogui.mouseDown(x, y, button=btn or "left")
                        elif action == "up":
                            pyautogui.mouseUp(x, y, button=btn or "left")
                        elif action == "scroll":
                            pyautogui.scroll(msg.get("dy", 0))
                    elif kind == "key":
                        k = msg.get("key")
                        action = msg.get("action")  # "press","down","up","write"
                        if action == "press":
                            pyautogui.press(k)
                        elif action == "down":
                            pyautogui.keyDown(k)
                        elif action == "up":
                            pyautogui.keyUp(k)
                        elif action == "write":
                            pyautogui.write(msg.get("text",""))
                except Exception as e:
                    print("[-] input handling error:", e)
            print("[*] input thread exiting")

        t = threading.Thread(target=recv_inputs, daemon=True)
        t.start()

        # 화면 전송 루프
        with mss.mss() as sct:
            monitor = sct.monitors[0]  # 전체 화면
            delay = 1.0 / FPS
            while not stop_event.is_set():
                start = time.time()
                img = np.array(sct.grab(monitor))
                # BGR order for OpenCV (mss gives BGRA)
                if img.shape[2] == 4:
                    img = img[:, :, :3]
                # 인코딩
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
                result, encimg = cv2.imencode('.jpg', img, encode_param)
                if not result:
                    continue
                data = encimg.tobytes()
                # 전송: 8바이트 길이
                conn.sendall(struct.pack("!Q", len(data)))
                conn.sendall(data)
                elapsed = time.time() - start
                to_sleep = delay - elapsed
                if to_sleep > 0:
                    time.sleep(to_sleep)
    except Exception as e:
        print("[-] client handler exception:", e)
    finally:
        try:
            conn.close()
        except:
            pass
        print(f"[-] Disconnected: {addr}")

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(1)
        print(f"[+] Server listening on {HOST}:{PORT}")
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    print("Server starting...")
    main()
