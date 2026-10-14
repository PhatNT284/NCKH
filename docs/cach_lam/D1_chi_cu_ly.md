# Mô hình D1 — Chỉ cự ly

> Mô hình trong **§5.2**. Đừng nhầm với **sản phẩm D1** (rà soát bộ dữ liệu) ở
> `../san_pham/D1_ra_soat_du_lieu.md`. Hai hệ đánh số khác nhau — xem `README.md` ở gốc repo.

**Trạng thái: XONG** · tuần 4 · Phát

---

## 1. Thầy yêu cầu gì (§5.2)

> *Khớp một mối quan hệ đơn giản giữa quãng đường bay và năng lượng bay đo được.
> Khi hữu ích, báo cáo cả mô hình tuyến tính và biến thể hồi quy bền vững. Mục
> đích nhằm kiểm tra xem quy tắc chỉ dựa trên khoảng cách có thể giải thích được
> bao nhiêu phần trăm biến thiên.*

Ba việc: mô hình tuyến tính, biến thể bền vững, và trả lời câu hỏi "giải thích
được bao nhiêu". Đã làm đủ ba.

## 2. Cài đặt

`src/models.py` → `make_d1(robust=False/True)`

```python
Pipeline([("scaler", StandardScaler()), ("model", LinearRegression())])   # OLS
Pipeline([("scaler", StandardScaler()), ("model", HuberRegressor())])     # bền vững
```

Một đặc trưng duy nhất: `distance_2d_m`.

Huber là hồi quy **bền vững** — ít bị các điểm bất thường kéo lệch hơn OLS.

## 3. Kết quả

| Biến thể | MAE | RMSE | bias | WAPE |
|---|---|---|---|---|
| OLS | 3,974 | 4,897 | −0,007 | 18,67 % |
| Huber | 3,968 | 4,900 | −0,326 | 18,63 % |

**So với D0 trung bình hằng (3,975): chênh 0,001 Wh — tức bằng không.**

## 4. Đây là kết quả quan trọng, không phải thất bại

Trả lời thẳng câu hỏi thầy đặt ra: quy tắc chỉ dựa trên cự ly giải thích được
**gần như 0 %** biến thiên trong bộ dữ liệu này.

**Nhưng phải nói rõ lý do, nếu không người đọc sẽ hiểu sai.**

Nguyên nhân nằm ở thiết kế thí nghiệm, không nằm ở vật lý:

| | |
|---|---|
| Chuyến trên tuyến R1 | 180/192 (94 %) |
| Độ lệch chuẩn cự ly của R1 | **5,3 m (~1 %)** |
| Tương quan cự ly ↔ năng lượng | +0,143 |

Cự ly gần như là **hằng số** trong bộ dữ liệu, nên nó không mang thông tin. Đây
**không** phải kết luận "cự ly không ảnh hưởng tới năng lượng bay" — dữ liệu
không cho phép kiểm điều đó.

Câu cảnh báo này bắt buộc phải nằm ngay dưới bảng so sánh trong bài. Thiếu nó,
bảng sẽ trông như mô hình đa yếu tố thắng áp đảo một cách gian lận.

## 5. Hành vi khi ngoại suy cự ly

Thí nghiệm E2c cho thấy D1 hỏng nặng nhất khi gặp cự ly ngoài vùng huấn luyện:

| Dải cự ly | MAE | bias |
|---|---|---|
| 427–609 m | 3,573 | −0,790 |
| ~835 m | **25,477** | **−25,477** |

Ở 835 m nó đoán thiếu **toàn bộ** 5 chuyến, sai gần 99 %. Chi tiết ở
`../san_pham/D2_benchmark_nang_luong.md` mục 7.
