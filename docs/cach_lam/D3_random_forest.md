# Mô hình D3 — Random Forest

> Mô hình trong **§5.2**. Đừng nhầm với **sản phẩm D3** (bộ máy quyết định
> FLY/NO-FLY) — việc của Quyền, tuần 7, chưa bắt đầu.

**Trạng thái: XONG** · tuần 5 · Phát
Không được chọn — thua D2 Ridge.

---

## 1. Thầy yêu cầu gì (§5.2)

> *Sử dụng mô hình Random Forest quy mô nhỏ, đã tinh chỉnh để làm baseline phi
> tuyến cho dữ liệu dạng bảng. Giới hạn độ sâu của cây và kích thước lá để giảm
> hiện tượng quá khớp. Mức độ quan trọng của đặc trưng chỉ mang tính mô tả, không
> mang tính quan hệ nhân quả.*

Bốn yêu cầu, đã làm đủ cả bốn.

## 2. Random Forest là gì

Xây 300 cây quyết định, mỗi cây học từ một phần dữ liệu khác nhau, rồi lấy trung
bình kết quả.

Khác Ridge ở chỗ nó bắt được **quan hệ phi tuyến** và **tương tác** giữa các yếu
tố — ví dụ "tăng tải ảnh hưởng mạnh hơn khi bay cao". Ridge không làm được.

Nhưng với 192 dòng và quan hệ khá tuyến tính, khả năng đó không giúp được gì, và
cái giá phải trả là dễ học vẹt hơn.

## 3. Cài đặt

`src/models.py` → `make_d3(max_depth, min_samples_leaf)`

| Tham số | Giá trị thử | Chọn được |
|---|---|---|
| `n_estimators` | 300 cố định | 300 |
| `max_depth` | 3, 5, 8 | **8** |
| `min_samples_leaf` | 2, 4, 8 | **2** |

Hai tham số sau chính là "giới hạn độ sâu cây và kích thước lá" thầy yêu cầu.
Tinh chỉnh bằng CV lồng trong fold huấn luyện.

Cũng chạy hai biến thể đặc trưng như D2: `D3_rf_preflight` và `D3_rf_as_written`.

## 4. Kết quả

| Biến thể | MAE | độ lệch chuẩn | RMSE | bias | WAPE | ms |
|---|---|---|---|---|---|---|
| D3-b (trước chuyến bay) | 1,014 | 0,144 | 1,502 | −0,001 | 4,76 % | **21,7** |
| D3-a (duration đo được) | 1,362 | 0,234 | 1,977 | +0,073 | 6,39 % | 16,4 |

Khoảng tin cậy 95 % của D3-b: [0,822 ; 1,141] — **không chồng lấn** với khoảng của
Ridge [0,582 ; 0,729]. Hai mô hình tách bạch rõ ràng.

Chênh lệch so với Ridge: +0,312 Wh, khoảng tin cậy [0,153 ; 0,490] → **có ý nghĩa
thống kê**.

## 5. Ba điểm yếu phát hiện được

### (a) Học vẹt — tụt 37 % khi giữ lại cấu hình

| | CV thường | Giữ lại cấu hình |
|---|---|---|
| D2 Ridge | 0,657 | 0,672 (+2 %) |
| **D3 RF** | 1,014 | **1,386 (+37 %)** |

Nghĩa là nó bám vào các cấu hình cụ thể đã thấy trong tập huấn luyện. Ridge thì
không.

### (b) Đoán thiếu ở ba vùng nguy hiểm

| Nhóm | MAE | bias |
|---|---|---|
| Tải 500 g | 0,986 | **−0,654** |
| Độ cao 100 m | 1,112 | **−0,710** |
| Cự ly > 700 m | 3,814 | **−3,111** |

Cả ba đều là điều kiện nhiệm vụ giao hàng thực tế hay gặp. Ridge không có vùng nào
như vậy.

Đây là lý do mạnh nhất để loại D3: hai mô hình có MAE tổng thể không chênh quá
nhiều, nhưng **hành vi an toàn khác hẳn nhau**. Bảng tổng giấu kín điều này.

### (c) Chậm hơn 100 lần

21,7 ms so với 0,215 ms. Vẫn là tức thời với người dùng nên **không phải lý do
loại**, chỉ là một bất lợi nhỏ nữa.

## 6. Độ quan trọng đặc trưng

| Đặc trưng | Độ quan trọng | Độ lệch chuẩn giữa các cây |
|---|---|---|
| thời lượng kế hoạch | 0,480 | 0,110 |
| độ cao | 0,341 | 0,046 |
| tải trọng | 0,107 | 0,029 |
| tốc độ ra lệnh | 0,032 | 0,092 |
| gió trung bình | 0,024 | 0,021 |
| cự ly | 0,017 | 0,016 |

**Hai mô hình đồng ý về thứ tự ba đặc trưng đầu** — Ridge cũng xếp thời lượng kế
hoạch > độ cao > tải trọng. Hai thuật toán khác hẳn nhau cùng ra một kết luận là
dấu hiệu quy luật có thật.

**Cảnh báo bắt buộc (§5.2):** độ quan trọng đặc trưng chỉ **mô tả** mô hình dùng
cột nào nhiều khi chia cây. Nó **không** phải quan hệ nhân quả, và không đọc được
thành "tăng biến X thì năng lượng tăng bao nhiêu".

Chú ý dòng tốc độ: độ quan trọng 0,032 nhưng độ lệch chuẩn 0,092 — **gấp ba lần
chính giá trị**. Các cây không thống nhất, không rút kết luận gì từ dòng đó.

## 7. Kết luận

D3 thua D2 và không được đưa vào bộ máy quyết định.

**Đây là kết quả bình thường và đúng**, không phải làm sai. Thầy đã cảnh báo trước
ở §5.2 rằng với dữ liệu nhỏ thì không nên kỳ vọng mô hình phức tạp thắng. Viết
thẳng điều đó vào bài.
