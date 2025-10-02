import os
import socket
from datetime import datetime

class SocketServer:
    def __init__(self, ip="127.0.0.1", port=8000, bufsize=4096, timeout=5):
        self.ip = ip
        self.port = port
        self.bufsize = bufsize
        self.timeout = timeout
        self.req_dir = "./request"
        self.img_dir = "./images"
        os.makedirs(self.req_dir, exist_ok=True)
        os.makedirs(self.img_dir, exist_ok=True)

    def _nowstamp() -> str:
        return datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

    def _split_headers_body(raw: bytes):
        sep = b"\r\n\r\n"
        i = raw.find(sep)
        if i == -1:
            return raw, b""
        return raw[:i], raw[i + 4:]

    def _parse_headers(header_bytes: bytes):
        lines = header_bytes.decode("iso-8859-1", errors="replace").split("\r\n")
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        return lines[0] if lines else "", headers

    def _extract_boundary(content_type: str):
        # 'multipart/form-data; boundary=----WebKitFormBoundary...'
        if "boundary=" not in content_type:
            return None
        b = content_type.split("boundary=", 1)[1].strip()
        if b.startswith('"') and b.endswith('"'):
            b = b[1:-1]
        return b.encode("iso-8859-1")

    def _save_request_bin(self, header_bytes: bytes, body: bytes) -> str:
        ts = self._nowstamp()
        path = os.path.join(self.req_dir, f"{ts}.bin")
        with open(path, "wb") as f:
            f.write(header_bytes + b"\r\n\r\n" + body)
        return ts, path

    def _save_multipart_images(self, body: bytes, boundary: bytes, prefix: str):
        saved = []
        dash = b"--" + boundary
        parts = body.split(dash)
        for seg in parts:
            seg = seg.lstrip(b"\r\n")
            if not seg or seg.startswith(b"--"):
                continue
            if b"\r\n\r\n" not in seg:
                continue
            hdr, data = seg.split(b"\r\n\r\n", 1)
            if data.endswith(b"\r\n"):
                data = data[:-2]

            disp = b""
            ctype = b""
            for line in hdr.split(b"\r\n"):
                low = line.lower()
                if low.startswith(b"content-disposition:"):
                    disp = line.split(b":", 1)[1].strip()
                elif low.startswith(b"content-type:"):
                    ctype = line.split(b":", 1)[1].strip()

            # filename 추출
            filename = None
            if b"filename=" in disp:
                after = disp.split(b"filename=", 1)[1].strip()
                if after.startswith(b'"') and b'"' in after[1:]:
                    filename = after.split(b'"')[1].decode("iso-8859-1", "ignore")
                else:
                    filename = after.decode("iso-8859-1", "ignore")
                filename = os.path.basename(filename)  # 경로 탈출 방지

            # 이미지 파트만 저장
            if filename and ctype.lower().startswith(b"image/"):
                save_name = f"{prefix}_{filename}"
                path = os.path.join(self.img_dir, save_name)
                with open(path, "wb") as f:
                    f.write(data)
                saved.append(path)
        return saved

    # ---------- server loop ----------
    def run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((self.ip, self.port))
            srv.listen(10)
            print(f"Server is running on {self.ip}:{self.port}  (Ctrl+C to stop)")

            try:
                while True:
                    clnt, addr = srv.accept()
                    with clnt:
                        clnt.settimeout(self.timeout)
                        try:
                            # 1) 헤더 수신
                            data = b""
                            while b"\r\n\r\n" not in data:
                                chunk = clnt.recv(self.bufsize)
                                if not chunk:
                                    break
                                data += chunk

                            header_bytes, body = self._split_headers_body(data)
                            _, headers = self._parse_headers(header_bytes)

                            # 2) Content-Length만큼 바디 추가 수신
                            clen = 0
                            if "content-length" in headers:
                                try:
                                    clen = int(headers["content-length"])
                                except ValueError:
                                    clen = 0
                            need = max(0, clen - len(body))
                            while need > 0:
                                chunk = clnt.recv(min(self.bufsize, need))
                                if not chunk:
                                    break
                                body += chunk
                                need -= len(chunk)

                            # 3) 실습 1: 원문 요청 저장
                            ts, bin_path = self._save_request_bin(header_bytes, body)
                            print(f"[Saved] {bin_path}")

                            # 4) 실습 2: 멀티파트 이미지 저장
                            saved_images = []
                            ctype = headers.get("content-type", "")
                            if ctype.lower().startswith("multipart/form-data"):
                                boundary = self._extract_boundary(ctype)
                                if boundary:
                                    saved_images = self._save_multipart_images(body, boundary, ts)
                                    for p in saved_images:
                                        print(f"[Image] {p}")

                            # 5) 간단 응답
                            body_txt = "OK" if not saved_images else "OK\n" + "\n".join(saved_images)
                            resp = (
                                "HTTP/1.1 200 OK\r\n"
                                "Content-Type: text/plain; charset=utf-8\r\n"
                                f"Content-Length: {len(body_txt.encode('utf-8'))}\r\n"
                                "Connection: close\r\n\r\n"
                                f"{body_txt}"
                            ).encode("utf-8")
                            clnt.sendall(resp)

                        except socket.timeout:
                            clnt.sendall(b"HTTP/1.1 408 Request Timeout\r\nConnection: close\r\n\r\n")
                        except Exception as e:
                            msg = f"server error: {e}".encode("utf-8", "ignore")
                            clnt.sendall(
                                b"HTTP/1.1 500 Internal Server Error\r\n"
                                b"Content-Type: text/plain; charset=utf-8\r\n"
                                b"Connection: close\r\n"
                                b"Content-Length: " + str(len(msg)).encode("ascii") + b"\r\n\r\n" + msg
                            )
            except KeyboardInterrupt:
                print("\nServer is shutting down...")

if __name__ == "__main__":
    SocketServer().run()
