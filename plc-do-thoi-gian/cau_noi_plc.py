#!/usr/bin/env python3
"""
Cầu nối PLC Xinje XD  <->  Bàn bơm dòng rơ le (bom-dong-thu-role.html)

- Đọc / ghi PLC qua Modbus RTU (RS485 hoặc RS232), không cần thư viện Modbus,
  chỉ cần pyserial:  pip install pyserial
- Mở một máy chủ web cục bộ (chỉ máy này truy cập được) để phục vụ trang
  bom-dong-thu-role.html và cung cấp API /api/status, /api/start, /api/stop.

Chạy với PLC thật:
    python cau_noi_plc.py --port COM3
Chạy thử không có PLC (PLC giả lập):
    python cau_noi_plc.py --demo
Sau đó mở trình duyệt:  http://localhost:8765/bom-dong-thu-role.html
"""
import argparse
import json
import os
import random
import struct
import sys
import threading
import time
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# ---------------- Bản đồ địa chỉ (khớp với chuong-trinh-plc.md) ----------------
# Địa chỉ Modbus của dòng Xinje XD: D0 = 0, M0 = 0, X0 = 0x5000, Y0 = 0x6000.
# Nếu PLC của bạn khác, sửa ở đây hoặc dùng tham số dòng lệnh --x-base / --y-base.
REG_RESULT = 0      # D0  : thời gian đo (ms)
REG_STATE = 10      # D10 : 0 chờ · 1 đang bơm · 2 đã cắt · 3 quá thời gian
REG_COUNT = 11      # D11 : bộ đếm số lần đo (tăng 1 sau mỗi kết quả)
REG_TIMEOUT = 20    # D20 : thời gian chờ tối đa (ms)
COIL_START = 100    # M100: lệnh bắt đầu từ máy tính
COIL_STOP = 101     # M101: lệnh dừng từ máy tính


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


class ModbusRTU:
    """Modbus RTU master tối giản: FC01, FC03, FC05, FC06."""

    def __init__(self, port, baud, parity, unit, timeout=0.3):
        import serial  # pyserial
        par = {'N': serial.PARITY_NONE, 'E': serial.PARITY_EVEN, 'O': serial.PARITY_ODD}[parity]
        self.s = serial.Serial(port, baud, bytesize=8, parity=par, stopbits=1, timeout=timeout)
        self.unit = unit
        self.lock = threading.Lock()

    def _tx(self, pdu: bytes, rlen: int) -> bytes:
        frame = bytes([self.unit]) + pdu
        frame += struct.pack('<H', crc16(frame))
        with self.lock:
            self.s.reset_input_buffer()
            self.s.write(frame)
            resp = self.s.read(rlen)
        if len(resp) < 5:
            raise IOError('PLC không trả lời. Kiểm tra dây A/B, tốc độ baud, parity và số trạm.')
        if resp[1] & 0x80:
            raise IOError(f'PLC báo lỗi Modbus mã {resp[2]} (địa chỉ không hợp lệ?).')
        if len(resp) < rlen or crc16(resp[:-2]) != struct.unpack('<H', resp[-2:])[0]:
            raise IOError('Sai CRC hoặc thiếu dữ liệu. Có thể nhiễu đường truyền.')
        return resp

    def read_regs(self, addr, n):
        r = self._tx(struct.pack('>BHH', 3, addr, n), 5 + 2 * n)
        return list(struct.unpack('>' + 'H' * n, r[3:3 + 2 * n]))

    def read_bits(self, addr, n):
        nb = (n + 7) // 8
        r = self._tx(struct.pack('>BHH', 1, addr, n), 5 + nb)
        return [bool(r[3 + i // 8] >> (i % 8) & 1) for i in range(n)]

    def write_coil(self, addr, on):
        self._tx(struct.pack('>BHH', 5, addr, 0xFF00 if on else 0), 8)

    def write_reg(self, addr, val):
        self._tx(struct.pack('>BHH', 6, addr, int(val) & 0xFFFF), 8)


class DemoPLC:
    """PLC giả lập chạy đúng logic của chương trình mẫu, để thử khi chưa có phần cứng."""

    def __init__(self, trip_ms):
        self.D = [0] * 32
        self.D[REG_TIMEOUT] = 20000
        self.trip_ms = trip_ms
        self.t0 = None
        self.target = None
        self.lock = threading.Lock()

    def _run(self):
        if self.D[REG_STATE] == 1 and self.t0 is not None:
            el = (time.monotonic() - self.t0) * 1000
            if el >= self.target:
                self._finish(2, round(self.target))
            elif el >= self.D[REG_TIMEOUT]:
                self._finish(3, self.D[REG_TIMEOUT])

    def _finish(self, state, ms):
        self.D[REG_RESULT] = ms
        self.D[REG_STATE] = state
        self.D[REG_COUNT] = (self.D[REG_COUNT] + 1) & 0xFFFF
        self.t0 = None

    def read_regs(self, addr, n):
        with self.lock:
            self._run()
            return self.D[addr:addr + n]

    def read_bits(self, addr, n):
        with self.lock:
            self._run()
            on = self.D[REG_STATE] == 1
            if addr == 0x5000:  # X: X3 = có dòng khi đang bơm, X1 = vừa cắt
                return [False, self.D[REG_STATE] == 2, False, on] + [False] * (n - 4)
            return [on, on] + [False] * (n - 2)  # Y0, Y1

    def write_coil(self, addr, on):
        with self.lock:
            if addr == COIL_START and on and self.D[REG_STATE] != 1:
                self.D[REG_STATE] = 1
                self.t0 = time.monotonic()
                self.target = max(5, random.gauss(self.trip_ms, self.trip_ms * 0.01 + 3))
            elif addr == COIL_STOP and on:
                self.D[REG_STATE] = 0
                self.t0 = None

    def write_reg(self, addr, val):
        with self.lock:
            self.D[addr] = int(val) & 0xFFFF


class Bridge:
    def __init__(self, plc, mode, x_base, y_base, info):
        self.plc, self.mode, self.x_base, self.y_base, self.info = plc, mode, x_base, y_base, info
        self.status = {'bridge': 'bomdong', 'mode': mode, 'connected': False, 'error': 'Đang kết nối…',
                       'state': 0, 'count': 0, 'last_ms': 0, 'x': [False] * 8, 'y': [False] * 8, 'info': info}
        self.lock = threading.Lock()
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            try:
                d = self.plc.read_regs(0, 12)
                x = self.plc.read_bits(self.x_base, 8)
                y = self.plc.read_bits(self.y_base, 8)
                with self.lock:
                    self.status.update(connected=True, error='', last_ms=d[REG_RESULT], state=d[REG_STATE],
                                       count=d[REG_COUNT], x=x, y=y)
                time.sleep(0.1)
            except Exception as e:  # giữ cầu nối chạy, thử lại sau 1 s
                with self.lock:
                    self.status.update(connected=False, error=str(e))
                time.sleep(1.0)

    def get(self):
        with self.lock:
            return dict(self.status)

    def start(self, timeout_ms):
        self.plc.write_reg(REG_TIMEOUT, max(100, min(30000, int(timeout_ms))))
        self.plc.write_coil(COIL_START, True)

    def stop(self):
        self.plc.write_coil(COIL_STOP, True)


class Handler(SimpleHTTPRequestHandler):
    bridge = None
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      '.html': 'text/html; charset=utf-8', '.md': 'text/plain; charset=utf-8',
                      '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8'}

    def log_message(self, fmt, *args):
        if not self.path.startswith('/api/'):
            sys.stderr.write('  web: ' + (fmt % args) + '\n')

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split('?')[0] == '/api/status':
            return self._json(200, self.bridge.get())
        if self.path in ('/', '/index.html'):
            self.send_response(302)
            self.send_header('Location', '/bom-dong-thu-role.html')
            self.end_headers()
            return
        return super().do_GET()

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        try:
            body = json.loads(self.rfile.read(n) or b'{}')
        except ValueError:
            body = {}
        try:
            if self.path == '/api/start':
                self.bridge.start(body.get('timeout_ms', 20000))
                print('  PLC: lệnh BẮT ĐẦU đo')
                return self._json(200, {'ok': True})
            if self.path == '/api/stop':
                self.bridge.stop()
                print('  PLC: lệnh DỪNG')
                return self._json(200, {'ok': True})
            return self._json(404, {'ok': False, 'error': 'Không có API này'})
        except Exception as e:
            return self._json(503, {'ok': False, 'error': str(e)})


def main():
    ap = argparse.ArgumentParser(description='Cầu nối PLC Xinje XD cho Bàn bơm dòng rơ le')
    ap.add_argument('--port', help='Cổng COM nối PLC, ví dụ COM3 (Windows) hoặc /dev/ttyUSB0 (Linux)')
    ap.add_argument('--baud', type=int, default=19200)
    ap.add_argument('--parity', choices=['N', 'E', 'O'], default='E')
    ap.add_argument('--unit', type=int, default=1, help='Số trạm Modbus của PLC')
    ap.add_argument('--x-base', type=lambda v: int(v, 0), default=0x5000)
    ap.add_argument('--y-base', type=lambda v: int(v, 0), default=0x6000)
    ap.add_argument('--http', type=int, default=8765, help='Cổng web cục bộ')
    ap.add_argument('--demo', action='store_true', help='Dùng PLC giả lập, không cần phần cứng')
    ap.add_argument('--demo-ms', type=float, default=1018, help='Thời gian cắt giả lập (ms)')
    ap.add_argument('--no-browser', action='store_true')
    a = ap.parse_args()

    if a.demo:
        plc, mode, info = DemoPLC(a.demo_ms), 'demo', f'PLC giả lập, cắt sau ~{a.demo_ms:.0f} ms'
    else:
        if not a.port:
            ap.error('cần --port (ví dụ --port COM3), hoặc dùng --demo để chạy thử')
        try:
            plc = ModbusRTU(a.port, a.baud, a.parity, a.unit)
        except ImportError:
            sys.exit('Thiếu thư viện pyserial. Cài bằng lệnh:  pip install pyserial')
        except Exception as e:
            sys.exit(f'Không mở được cổng {a.port}: {e}')
        mode, info = 'plc', f'{a.port} · {a.baud} 8{a.parity}1 · trạm {a.unit}'

    Handler.bridge = Bridge(plc, mode, a.x_base, a.y_base, info)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    srv = ThreadingHTTPServer(('127.0.0.1', a.http), partial(Handler, directory=root))
    url = f'http://localhost:{a.http}/bom-dong-thu-role.html'
    print(f'Cầu nối PLC đang chạy ({info}).')
    print(f'Mở trình duyệt tại: {url}')
    print('Nhấn Ctrl+C để thoát.')
    if not a.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\nĐã dừng cầu nối.')


if __name__ == '__main__':
    main()
