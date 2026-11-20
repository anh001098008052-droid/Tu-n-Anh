# Chương trình PLC đo thời gian cắt rơ le – Xinje XD3-16T-E

Chương trình có 9 bậc thang (rung). PLC làm 3 việc:
1. Nhận lệnh bắt đầu (nút X0 hoặc máy tính ghi M100) → đóng Y0 cho contactor bơm dòng.
2. Đếm thời gian bằng bộ định thời gốc 1 ms, **bắt đầu khi có dòng thật (X3)**, dừng khi tiếp điểm cắt của rơ le (X1) đóng.
3. Ghi kết quả vào thanh ghi D để máy tính đọc qua Modbus.

> **Lưu ý trung thực:** chương trình này được viết theo tài liệu tập lệnh dòng XD, **chưa được nạp thử trên PLC thật**.
> Nếu XDPPro báo lỗi ở lệnh nào (hay gặp nhất là cú pháp `TMR` và lệnh so sánh `LD>=`), hãy chụp màn hình gửi lại để sửa.

## Bảng biến

| Địa chỉ | Ý nghĩa | Modbus |
|---|---|---|
| X0 | Nút **Bắt đầu** tại bàn thử (thường hở) | 0x5000 |
| X1 | **Tiếp điểm cắt** của rơ le cần thử (tiếp điểm khô) | 0x5001 |
| X2 | Tiếp điểm khởi động của rơ le (không bắt buộc, chỉ hiển thị) | 0x5002 |
| X3 | **Có dòng**: tiếp điểm phụ thường hở của contactor bơm, hoặc rơ le dòng | 0x5003 |
| X4 | Nút **Dừng** (thường hở) | 0x5004 |
| Y0 | Cuộn rơ le trung gian 24 VDC → đóng contactor bơm dòng | 0x6000 |
| Y1 | Đèn báo đang thử | 0x6001 |
| M0 | Đang thử (giữ) | – |
| M1 | Đang đếm thời gian | – |
| M100 | Lệnh bắt đầu từ máy tính | coil 100 |
| M101 | Lệnh dừng từ máy tính | coil 101 |
| M110 | = 1: bắt đầu đếm khi X3 đóng (khuyên dùng) · = 0: bắt đầu đếm ngay khi xuất Y0 | coil 110 |
| T0 | Bộ định thời gốc 1 ms | – |
| D0 | **Kết quả: thời gian cắt (ms)** | reg 0 |
| D10 | Trạng thái: 0 chờ · 1 đang bơm · 2 đã cắt · 3 quá thời gian | reg 10 |
| D11 | Bộ đếm số lần đo (máy tính dựa vào đây để biết có kết quả mới) | reg 11 |
| D20 | Thời gian chờ tối đa (ms), máy tính ghi trước mỗi lần đo | reg 20 |

## Sơ đồ thang (ladder)

```
Rung 0  Giá trị mặc định
 ──[ = D20 K0 ]──────────────────────────────────[ MOV K20000 D20 ]
 ──[ M8002 ]─────────────────────────────────────( SET M110 )        ; M8002: xung lần quét đầu

Rung 1  Bắt đầu
 ──┬─[↑ X0 ]─┬──[/ M0 ]──[/ X4 ]─────────────────( SET M0 )
   └─[ M100 ]┘                                  ├( RST M1 )
                                                ├[ RST T0 ]
                                                └[ MOV K1 D10 ]
Rung 2  Xoá lệnh của máy tính
 ──[ M100 ]──────────────────────────────────────( RST M100 )

Rung 3  Xuất bơm dòng
 ──[ M0 ]────────────────────────────────────────( Y0 )
                                                └( Y1 )
Rung 4  Mốc bắt đầu đếm
 ──[ M0 ]──┬─[ X3 ]──────────────────────────────( SET M1 )
           └─[/ M110 ]───────────────────────────( SET M1 )

Rung 5  Đếm thời gian, gốc 1 ms
 ──[ M1 ]────────────────────────────────────────[ TMR T0 K32000 K1 ]

Rung 6  Rơ le cắt → ghi kết quả
 ──[ X1 ]──[ M1 ]────────────────────────────────[ MOV T0 D0 ]
                                                ├[ MOV K2 D10 ]
                                                ├[ INC D11 ]
                                                ├( RST M1 )
                                                └( RST M0 )
Rung 7  Quá thời gian chờ → rơ le không cắt
 ──[ >= T0 D20 ]──[ M1 ]─────────────────────────[ MOV T0 D0 ]
                                                ├[ MOV K3 D10 ]
                                                ├[ INC D11 ]
                                                ├( RST M1 )
                                                └( RST M0 )
Rung 8  Dừng
 ──┬─[ X4 ]───┬──────────────────────────────────( RST M0 )
   └─[ M101 ]─┘                                 ├( RST M1 )
                                                ├( RST M101 )
                                                └[ MOV K0 D10 ]
```

## Danh sách lệnh (để gõ nhanh ở chế độ Instruction List)

```
; Rung 0
LD=     D20  K0
MOV     K20000  D20
LD      M8002
SET     M110
; Rung 1
LDP     X0
OR      M100
ANI     M0
ANI     X4
SET     M0
RST     M1
RST     T0
MOV     K1  D10
; Rung 2
LD      M100
RST     M100
; Rung 3
LD      M0
OUT     Y0
OUT     Y1
; Rung 4
LD      M0
AND     X3
SET     M1
LD      M0
ANI     M110
SET     M1
; Rung 5
LD      M1
TMR     T0  K32000  K1
; Rung 6
LD      X1
AND     M1
MOV     T0  D0
MOV     K2  D10
INC     D11
RST     M1
RST     M0
; Rung 7
LD>=    T0  D20
AND     M1
MOV     T0  D0
MOV     K3  D10
INC     D11
RST     M1
RST     M0
; Rung 8
LD      X4
OR      M101
RST     M0
RST     M1
RST     M101
MOV     K0  D10
```

## Vì sao viết như vậy

- **Đếm từ X3 thay vì từ lệnh Y0.** Rơ le trung gian và contactor tự đóng chậm 10–30 ms. Nếu đếm từ lúc xuất Y0, kết quả sẽ dài thêm đúng khoảng đó. Khi đếm từ X3 (tiếp điểm phụ của contactor, hoặc tốt hơn là rơ le dòng), mốc bắt đầu sát với thời điểm có dòng thật.
- **Bộ lọc đầu vào gần như tự triệt tiêu.** Đầu vào PLC có bộ lọc chống dội, mặc định khoảng 10 ms. X3 (mốc đầu) và X1 (mốc cuối) đều qua cùng một bộ lọc nên độ trễ phần lớn bù trừ nhau. Vẫn nên giảm thời gian lọc xuống mức nhỏ nhất (xem README).
- **Sai số còn lại** khoảng 1 vòng quét PLC (thường 1–5 ms) cộng chênh lệch bộ lọc. Như vậy là đủ nhỏ so với dung sai ±30 ms của IEC 60255-151.
- **INC D11** giúp máy tính nhận ra kết quả mới ngay cả khi hai lần đo cho cùng một thời gian.
