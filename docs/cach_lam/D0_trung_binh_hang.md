# Mô hình D0 — Trung bình hằng

> Mô hình trong **§5.2**, không phải sản phẩm bàn giao. Bảng so sánh giữa các mô
> hình nằm ở `../san_pham/D2_benchmark_nang_luong.md`.

**Trạng thái: XONG** · tuần 4 · Phát

---

## 1. Thầy yêu cầu gì (§5.2)

> *Dự đoán mức năng lượng bay trung bình trong tập huấn luyện. Đây là baseline
> kiểm tra tính hợp lý cơ bản (sanity-check) và không kỳ vọng mang lại giá trị
> sử dụng trong vận hành thực tế.*

## 2. Cài đặt

`src/models.py` → `make_d0()`

```python
Pipeline([("model", DummyRegressor(strategy="mean"))])
```

Không dùng đặc trưng nào. Nó học đúng một con số — trung bình năng lượng của tập
huấn luyện — rồi đoán con số đó cho mọi chuyến bay.

Trong `configs/d2_protocol.yaml`: `models.D0`, `required: true`.

## 3. Kết quả

| Thước đo | Giá trị |
|---|---|
| MAE | **3,975 Wh** |
| RMSE | 4,894 |
| bias | 0,000 |
| WAPE | 18,67 % |
| Thời gian suy luận | 0,031 ms |

Giá trị dự báo cố định: khoảng 21,3 Wh (trung bình của 192 chuyến).

bias bằng 0 là hiển nhiên, không phải thành tích — đoán bằng trung bình thì theo
định nghĩa sai lệch hai phía cân nhau.

## 4. Vai trò

Đây là **mốc bắt buộc**, không phải ứng viên. Mọi mô hình khác phải thắng được nó,
nếu không thì việc phức tạp hoá là vô ích.

Nó cũng cho biết **độ khó của bài toán**: muốn dự báo năng lượng mà không biết gì
cả thì sai khoảng 18,7 %. Mô hình tốt nhất đưa con số đó xuống 3,09 %.

Một kết quả đáng chú ý liên quan tới D0: **mô hình D1 chỉ cự ly không hơn D0 chút
nào** (3,974 so với 3,975). Xem `D1_chi_cu_ly.md`.
