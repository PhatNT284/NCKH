# Mô hình D2 — Ridge regression

> Mô hình trong **§5.2**. Đừng nhầm với **sản phẩm D2** (benchmark so sánh) ở
> `../san_pham/D2_benchmark_nang_luong.md`. Hai hệ đánh số khác nhau.

**Trạng thái: XONG** · tuần 4 · Phát
**ĐÂY LÀ MÔ HÌNH ĐƯỢC CHỌN** đưa vào bộ máy quyết định.

---

## 1. Thầy yêu cầu gì (§5.2)

> *Sử dụng một tập đặc trưng nhỏ đã xác định trước như quãng đường, tải trọng,
> tốc độ, độ cao, thời gian bay và các đặc trưng liên quan đến gió. Chỉ chuẩn hóa
> các đặc trưng dựa trên số liệu thống kê của tập huấn luyện. Hồi quy Ridge được
> ưu tiên hơn các đa thức bậc cao không ràng buộc vì tập dữ liệu tương đối nhỏ.*

## 2. Ridge là gì

Hồi quy tuyến tính có thêm **hình phạt** cho các hệ số quá lớn. Hình phạt ngăn mô
hình phản ứng thái quá với nhiễu trong dữ liệu.

Với 192 dòng, nếu dùng đa thức bậc cao thì mô hình sẽ học thuộc nhiễu thay vì học
quy luật — đó là lý do thầy ưu tiên Ridge.

Độ mạnh của hình phạt là tham số `alpha`, chọn bằng CV lồng từ [0,01 ; 0,1 ; 1 ;
10 ; 100]. **Giá trị chọn được: alpha = 1,0.**

## 3. Hai biến thể

Thầy liệt kê "thời gian bay" trong tập đặc trưng nhưng không nói rõ loại nào.

| | Đặc trưng thứ 6 | Dùng được lúc nào |
|---|---|---|
| **D2-b** `D2_ridge_preflight` | `duration_planned_s` = cự ly ÷ tốc độ | **trước khi cất cánh** |
| D2-a `D2_ridge_as_written` | `duration_s` đo được | chỉ sau khi bay xong |

Năm đặc trưng chung: `payload_num`, `speed_num`, `altitude_num`, `distance_2d_m`,
`wind_raw_mean_ms`.

Căn cứ chọn D2-b làm chính và lý lẽ đầy đủ: `../san_pham/D2_benchmark_nang_luong.md` mục 3.

## 4. Cài đặt

`src/models.py` → `make_d2(alpha)`

```python
Pipeline([("scaler", StandardScaler()), ("model", Ridge(alpha=alpha))])
```

`StandardScaler` nằm **trong** Pipeline, nên việc chuẩn hoá chỉ học từ fold huấn
luyện — đúng yêu cầu của thầy, và không thể làm sai được.

## 5. Kết quả

| Biến thể | MAE | độ lệch chuẩn | RMSE | bias | WAPE | ms |
|---|---|---|---|---|---|---|
| **D2-b** | **0,657** | 0,075 | 0,840 | +0,010 | **3,09 %** | 0,215 |
| D2-a | 1,073 | 0,152 | 1,339 | +0,013 | 5,05 % | 0,213 |

Khoảng tin cậy 95 % của D2-b: **[0,582 ; 0,729]**.

Giữ lại cấu hình: MAE 0,672 — **chỉ tăng 2 %**, tức mô hình hiểu quy luật thật
chứ không học vẹt.

## 6. Hệ số hồi quy

alpha = 1,0, hằng số 21,270 Wh.

| Đặc trưng | Hệ số chuẩn hoá | Đơn vị gốc |
|---|---|---|
| thời lượng kế hoạch | 4,122 | +0,1356 Wh/giây |
| độ cao | 3,052 | +0,1085 Wh/mét |
| tải trọng | 1,677 | +0,0081 Wh/gram |
| tốc độ ra lệnh | 0,668 | +0,2353 Wh/(m/s) |
| gió trung bình | 0,119 | +0,1428 Wh/(m/s) |
| cự ly | −0,077 | −0,0013 Wh/mét |

Đọc được thành câu: *mang thêm 250 g tốn thêm ~2,0 Wh; bay cao thêm 25 m tốn thêm
~2,7 Wh.*

**Cảnh báo phải nêu trong bài:** hệ số tốc độ **dương** dù tương quan thô giữa tốc
độ và năng lượng là **âm** (−0,602). Không mâu thuẫn — vì `thời lượng kế hoạch =
cự ly ÷ tốc độ`, hai biến liên hệ cơ học. "Giữ thời lượng không đổi mà tăng tốc
độ" là tình huống khác hẳn "tăng tốc độ trên cùng tuyến bay".

Hệ số cự ly gần 0 là hệ quả của việc 94 % chuyến cùng một tuyến — xem
`D1_chi_cu_ly.md`.

## 7. Vì sao mô hình này được chọn

Bốn lý do, không chỉ một:

1. **Chính xác nhất** — 0,657 so với 1,014 của Random Forest
2. **Tổng quát tốt** — giữ lại cấu hình chỉ tụt 2 %, trong khi RF tụt 37 %
3. **Không có vùng đoán thiếu** — qua mọi mức tải, tốc độ, độ cao, gió
4. **Nhẹ** — 0,215 ms, nhanh hơn RF 100 lần

Lý do 3 là quan trọng nhất về an toàn. Random Forest đoán thiếu ở tải 500 g, độ
cao 100 m và cự ly dài — xem `D3_random_forest.md`.

## 8. Giới hạn sử dụng

**Chỉ dùng trong dải cự ly khoảng 420–610 m.** Ngoài dải đó mô hình đoán thiếu có
hệ thống: ở 835 m, bias = −7,613 Wh trên cả 5 chuyến.

Ràng buộc này áp cho sản phẩm D3 và D4 — chi tiết ở `../san_pham/D2_benchmark_nang_luong.md` mục 8.
