# Đo thời gian cắt rơ le thật bằng PLC Xinje XD3 + Bàn bơm dòng rơ le

```
 Nguồn bơm dòng ──► Contactor ──► Rơ le cần thử ──► Tiếp điểm cắt
 (variac + BA hạ áp)   ▲   │ tiếp điểm phụ                  │
                       │   ▼                                ▼
               Y0 ── PLC XD3 ── X3 (có dòng)          X1 (cắt)
                       │ RS485 (Modbus RTU)
                       ▼
     Máy tính: cau_noi_plc.py  ──►  trình duyệt: bom-dong-thu-role.html (tab "Thiết bị thật")
```

Trong thư mục này:
- `chuong-trinh-plc.md`: chương trình PLC (sơ đồ thang + danh sách lệnh) và bảng địa chỉ.
- `cau_noi_plc.py`: chương trình cầu nối chạy trên máy tính.

---

## 1. Đấu dây

> ⚠️ **An toàn**
> - Nút dừng khẩn phải **cắt trực tiếp cuộn contactor bơm dòng** bằng dây cứng, không đi qua PLC.
> - Mạch bơm dòng có dòng lớn: dùng dây và cầu đấu đúng tiết diện, chỉ thao tác khi đã cắt nguồn.
> - **Không đưa điện áp nguồn thao tác 110/220 VDC của tủ vào đầu vào PLC.** Tách dây tiếp điểm cắt ra khỏi mạch tủ, chỉ dùng tiếp điểm khô.

**Nguồn PLC.** Model **-E** dùng nguồn xoay chiều: L, N = 220 VAC. Hãy kiểm tra nhãn trên vỏ, vì model -C dùng 24 VDC.

**Đầu vào.** Mỗi tiếp điểm khô đấu giữa chân **Xn** và chân **COM** của khối đầu vào. Đây là kiểu NPN thường gặp ở Xinje, nhưng vẫn nên đối chiếu sơ đồ in trên vỏ.

| Chân | Nối với |
|---|---|
| X0 – COM | Nút Bắt đầu (thường hở) |
| X1 – COM | **Tiếp điểm cắt của rơ le** (tiếp điểm khô, hoặc qua opto cách ly) |
| X2 – COM | Tiếp điểm khởi động của rơ le (không bắt buộc) |
| X3 – COM | Tiếp điểm phụ thường hở của contactor bơm, hoặc tiếp điểm rơ le dòng |
| X4 – COM | Nút Dừng (thường hở) |

**Đầu ra transistor.** Y0 **không** đóng trực tiếp contactor 220 VAC được. Hãy đấu như sau:

```
 +24V ──► cuộn rơ le trung gian 24 VDC ──► Y0      (Y COM0 ──► 0V)
          (đấu song song diode 1N4007 ngược chiều để dập xung)
 Tiếp điểm rơ le trung gian ──► cuộn contactor bơm dòng (nối tiếp với nút dừng khẩn)
```

**Truyền thông.** Dùng bộ chuyển USB–RS485 nối vào cổng RS485 (COM2) của PLC: **A–A, B–B**. Nếu không có tín hiệu, hãy thử đảo A và B. Cũng có thể dùng cáp lập trình RS232 ở COM1.

## 2. Nạp chương trình bằng XDPPro

Tên mục menu có thể khác đôi chút giữa các phiên bản XDPPro.

1. Mở **XDPPro** → menu **File** → **New** (Tạo mới) → chọn model **XD3-16T-E** → **OK**.
2. Gõ chương trình:
   - Bấm nút chuyển sang chế độ **Instruction List** (danh sách lệnh) trên thanh công cụ, rồi gõ phần “Danh sách lệnh” trong `chuong-trinh-plc.md`.
   - Hoặc vẽ thang theo sơ đồ ở cùng file.
3. Bấm **Compile / Check** (Kiểm tra) để kiểm tra lỗi. Nếu báo lỗi ở `TMR` hoặc `LD>=`, mở **Help** → **Instruction** để xem cú pháp đúng cho phiên bản của bạn, hoặc gửi ảnh lỗi để sửa.
4. **Cài cổng truyền thông** (cây **Project** bên trái → **PLC Config** / **Cấu hình PLC** → **Serial Port**):
   chọn **COM2** → giao thức **Modbus RTU**, **Slave**, **trạm 1**, **19200**, **8 bit dữ liệu**, **Even**, **1 stop bit**.
   Nếu đặt khác, nhập đúng các thông số đó khi chạy cầu nối.
5. **Giảm bộ lọc đầu vào** (cùng mục **PLC Config** → **Input / Filter**): đặt X1 và X3 ở mức thời gian lọc nhỏ nhất cho phép.
6. Nối cáp lập trình → menu **PLC** → **Download** (Tải chương trình xuống) → chuyển PLC sang **RUN**.
7. **Kiểm tra nhanh** (menu **PLC** → **Free Monitor** / **Giám sát**):
   - Bấm X0: Y0 và Y1 phải sáng, D10 = 1.
   - Chập X3, rồi chập X1: D10 chuyển thành 2, D0 hiện số ms, D11 tăng thêm 1.

## 3. Chạy cầu nối trên máy tính

Cần **Python 3.8 trở lên** (lúc cài trên Windows nhớ tích **Add Python to PATH**).

```bash
pip install pyserial
cd đường-dẫn-tới/Tu-n-Anh/plc-do-thoi-gian
python cau_noi_plc.py --port COM3
```

- Tìm số cổng COM: **Device Manager** → mục **Ports (COM & LPT)** → dòng bộ chuyển USB–RS485.
- Nếu PLC đặt thông số khác: `--baud 9600 --parity N --unit 2`.
- **Chưa có PLC?** Chạy thử bằng PLC giả lập: `python cau_noi_plc.py --demo`.

Cầu nối tự mở trình duyệt tại `http://localhost:8765/bom-dong-thu-role.html`.

## 4. Đo trên giao diện

1. Ở cột trái, nhập **chỉnh định thật của rơ le** (ngưỡng, đặc tính, TMS).
2. Mở tab **Thiết bị thật (PLC)**. Thẻ “Kết nối” phải hiện **Đã kết nối**.
3. Chọn **Kiểu sự cố**, rồi nhập **Dòng bơm thực tế** đọc trên ampe kế (A thứ cấp). Phần mềm tự tính **thời gian kỳ vọng**.
4. Bấm **▶ Bắt đầu đo**, hoặc bấm nút X0 tại bàn thử. Khi rơ le cắt, kết quả tự ghi vào **Biên bản kết quả** với đánh giá Đạt/Không đạt.
5. Lặp lại cho các mức dòng khác, rồi bấm **Sao chép CSV** → dán vào Excel.

> Trang đăng trên claude.ai **không** kết nối được PLC, vì trình duyệt chặn truy cập cổng COM và máy tính cục bộ.
> Phải mở trang qua địa chỉ `localhost` mà cầu nối in ra.
