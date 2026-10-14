# Báo cáo chốt mô hình năng lượng

**Sản phẩm tuần 6** · Phát (WP2) · người kiểm chéo: Duy

**Quyết định: chọn `D2_ridge_preflight`** — Ridge regression trên tập đặc trưng
biết trước khi cất cánh.

---

## 1. Vì sao cần báo cáo này

Thầy đặt cổng chặn ở Mục 12.1, bảng tiêu chí nghiệm thu sản phẩm D2:

> *Chỉ chọn mô hình năng lượng **sau khi** xem kết quả kiểm định.*

Báo cáo này là bằng chứng nhóm làm đúng thứ tự: chạy toàn bộ so sánh trước, xem
kết quả, rồi mới chọn. Không chọn trước rồi chạy lấy lệ.

Nó cũng là bàn giao sang sản phẩm D3 — Quyền cần biết dùng mô hình nào và dùng
trong giới hạn nào.

**Thứ tự thực tế đã diễn ra:**

| Thời điểm | Việc |
|---|---|
| Tuần 2 | Đóng băng giao thức: tập đặc trưng, thước đo, cách chia tập |
| Tuần 4 | Chạy D0, D1, D2 |
| Tuần 5 | Chạy D3, phân tích sai số theo nhóm |
| Tuần 6 | Kiểm tương thích D5, **rồi mới chốt** |

Giao thức đóng băng trong `configs/d2_protocol.yaml` từ trước khi có kết quả nào.

---

## 2. Các ứng viên đã xét

Danh sách lấy nguyên từ §5.2, không thêm mô hình nào ngoài.

| Mô hình | Biến thể | Có vào vòng chọn? |
|---|---|---|
| D0 Trung bình hằng | 1 | Không — chỉ là mốc kiểm tra |
| D1 Chỉ cự ly | OLS, Huber | Có |
| D2 Ridge | D2-a, D2-b | Có |
| D3 Random Forest | D3-a, D3-b | Có |
| D4 Gradient boosting | — | Không — bị chặn bởi Mục 2.4 |
| D5 Mô hình vật lý | — | Không — thiếu tham số, xem mục 6 |

Hai biến thể của D2 và D3 khác nhau đúng một đặc trưng:

- **-a** dùng `duration_s` — thời lượng bay **đo được**, chỉ có sau khi bay xong
- **-b** dùng `duration_planned_s` — thời lượng **kế hoạch** = cự ly ÷ tốc độ

---

## 3. Tiêu chí chọn

Bốn tiêu chí, xếp theo mức quan trọng. Ba tiêu chí đầu lấy từ §5.3, tiêu chí thứ
tư là ràng buộc của chính đề tài.

| # | Tiêu chí | Căn cứ |
|---|---|---|
| 1 | **Chạy được trước khi cất cánh** | Đề tài là đánh giá *pre-flight* |
| 2 | **Không đoán thiếu có hệ thống** | §5.3: *"dự báo thiếu một cách hệ thống là vấn đề an toàn"* |
| 3 | **Tổng quát ra ngoài điều kiện đã thấy** | §5.3: thí nghiệm giữ lại cấu hình |
| 4 | **Sai số nhỏ nhất** | §5.3: MAE, RMSE |

Tiêu chí 1 và 2 là **điều kiện loại**, không phải điểm cộng. Mô hình không thoả
thì loại bất kể sai số đẹp đến đâu.

---

## 4. Bằng chứng theo từng tiêu chí

### Tiêu chí 1 — Chạy được trước khi cất cánh

Loại ngay hai biến thể **-a**. Chúng cần `duration_s`, mà lúc đứng ở bãi phóng
chưa bay thì chưa có con số đó.

Còn lại: D1 (OLS, Huber), D2-b, D3-b.

**Phát hiện đáng chú ý:** biến thể pre-flight không hề là nhượng bộ. D2-b
(MAE 0,657) **chính xác hơn 39 %** so với D2-a (1,073).

Diễn giải: `cự ly ÷ tốc độ ra lệnh` là đại lượng sạch, phản ánh đúng ý định bay.
Thời lượng đo được chứa cả nhiễu vận hành — treo chờ, trễ cất cánh, biến động
điều khiển — những thứ không tương ứng tuyến tính với năng lượng.

### Tiêu chí 2 — Không đoán thiếu có hệ thống

Kiểm bằng cột `bias` tách theo từng điều kiện vận hành
(`reports/d2_subgroup_errors.csv`).

| Nhóm | D2-b Ridge | D3-b Random Forest |
|---|---|---|
| Tải 0 g | −0,021 | +0,836 |
| Tải 250 g | +0,092 | −0,207 |
| **Tải 500 g** | **−0,034** | **−0,654** |
| Độ cao 25 m | +0,097 | +0,571 |
| Độ cao 50 m | −0,077 | −0,276 |
| Độ cao 75 m | −0,107 | +0,311 |
| **Độ cao 100 m** | **+0,122** | **−0,710** |
| **Cự ly > 700 m** | −0,106 | **−3,111** |

**D2-b: không nhóm nào có bias âm đáng kể.** Giá trị âm nhất là −0,180 ở tốc độ
12 m/s, quá nhỏ để lo ngại.

**D3-b đoán thiếu ở ba vùng cùng lúc:** tải nặng, bay cao, cự ly dài — cả ba đều
là điều kiện nhiệm vụ giao hàng thực tế hay gặp.

Đây là tiêu chí quan trọng nhất về an toàn. Hai mô hình có MAE tổng thể không
chênh quá nhiều (0,657 so với 1,014), nhưng **hành vi an toàn khác hẳn nhau**.
Bảng xếp hạng tổng giấu kín điều này.

### Tiêu chí 3 — Tổng quát ra ngoài điều kiện đã thấy

Thí nghiệm E2b: bỏ nguyên một tổ hợp (tải × tốc độ × độ cao) ra khỏi tập huấn
luyện, lặp qua cả 60 tổ hợp.

| Mô hình | CV thường | Giữ lại cấu hình | Chênh |
|---|---|---|---|
| **D2-b Ridge** | 0,657 | 0,672 | **+2 %** |
| D2-a Ridge | 1,073 | 1,116 | +4 % |
| D3-b Random Forest | 1,014 | 1,386 | **+37 %** |

Ridge gần như không đổi → hiểu quy luật thật. Random Forest tụt 37 % → bám vào
các cấu hình cụ thể trong tập huấn luyện, tức có học vẹt một phần.

### Tiêu chí 4 — Sai số

CV 5-fold lặp 5 lần ở cấp chuyến bay, 192 chuyến.

| Mô hình | MAE | Khoảng tin cậy 95 % | RMSE | WAPE | ms |
|---|---|---|---|---|---|
| **D2-b Ridge** | **0,657** | **[0,582 ; 0,729]** | 0,840 | **3,09 %** | 0,215 |
| D3-b Random Forest | 1,014 | [0,822 ; 1,141] | 1,502 | 4,76 % | 21,7 |
| D1 chỉ cự ly (Huber) | 3,968 | [3,557 ; 4,381] | 4,900 | 18,63 % | 0,212 |
| D0 trung bình hằng | 3,975 | [3,582 ; 4,387] | 4,894 | 18,67 % | 0,031 |

**Chênh lệch có ý nghĩa thống kê.** Bootstrap 2.000 lần ở cấp chuyến bay
(`reports/d2_bootstrap_differences.csv`):

| So với D2-b | Chênh lệch | Khoảng tin cậy 95 % | |
|---|---|---|---|
| D3-b Random Forest | +0,312 | [0,153 ; 0,490] | **không chứa 0** |
| D1 chỉ cự ly | +3,315 | [2,924 ; 3,722] | **không chứa 0** |

Mọi khoảng đều không chứa 0 → D2-b thắng thật, không phải may rủi của việc chia
dữ liệu. Khoảng tin cậy của D2-b và D3-b cũng **không chồng lấn nhau**.

---

## 5. Lưu ý bắt buộc về D1 chỉ cự ly

D1 cho MAE 3,974, **ngang bằng D0 trung bình hằng** (3,975). Chênh 0,001 Wh, tức
bằng không.

**Không được đọc thành "cự ly không ảnh hưởng tới năng lượng bay".**

Nguyên nhân nằm ở thiết kế thí nghiệm: 180/192 chuyến (94 %) bay trên cùng tuyến
R1, độ lệch chuẩn cự ly chỉ 5,3 m (~1 %). Cự ly gần như là **hằng số** trong bộ
dữ liệu nên không mang thông tin. Dữ liệu **không cho phép kiểm** ảnh hưởng của
cự ly.

Câu này bắt buộc nằm ngay dưới bảng so sánh trong bài. Thiếu nó, bảng sẽ trông như
mô hình đa yếu tố thắng áp đảo một cách gian lận.

---

## 6. Vì sao D5 mô hình vật lý không vào vòng chọn

Đã làm bảng kiểm tương thích §3.2. Kết quả: **khả thi một phần**.

| Thành phần | Dựng được? | Lý do |
|---|---|---|
| `P_in` công suất cảm ứng | Được | Chỉ cần diện tích đĩa quay, suy từ bán kính cánh quạt |
| Hệ số hiệu suất η | Được | Khớp từ thời lượng bay treo DJI công bố |
| `P_bl` công suất hình dạng | **Không** | DJI không công bố tỉ số đặc, hệ số cản cánh |
| `P_par` công suất ký sinh | **Không** | DJI không công bố diện tích cản thân |

§5.2 ghi rõ: thiếu tham số thì **không được bịa**, phải báo cáo như đối chứng tài
liệu và loại khỏi xếp hạng định lượng.

Phần dựng được có kiểm chứng tốt: khớp η từ **đúng một điểm** rồi dự báo 4 trị số
thời lượng bay treo không dùng để khớp, sai lệch trung bình **3,4 %**.

Chi tiết: `docs/cach_lam/D5_mo_hinh_vat_ly.md`

---

## 7. Quyết định

**Mô hình được chọn: `D2_ridge_preflight`**

| | |
|---|---|
| Thuật toán | Ridge regression, alpha = 1,0 |
| Đặc trưng | `payload_num`, `speed_num`, `altitude_num`, `distance_2d_m`, `wind_raw_mean_ms`, `duration_planned_s` |
| MAE | 0,657 Wh (3,09 %) |
| Khoảng tin cậy 95 % | [0,582 ; 0,729] Wh |
| bias | +0,010 Wh |
| Thời gian suy luận | 0,215 ms |
| Mã nguồn | `src/models.py` → `make_d2()` |

Thắng cả bốn tiêu chí: chạy được trước chuyến bay, không có vùng đoán thiếu, tổng
quát tốt, và sai số nhỏ nhất.

### Hệ số hồi quy

Hằng số 21,270 Wh.

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

**Cảnh báo:** hệ số tốc độ **dương** dù tương quan thô giữa tốc độ và năng lượng
là **âm** (−0,602). Không mâu thuẫn — vì `thời lượng kế hoạch = cự ly ÷ tốc độ`,
hai biến liên hệ cơ học. "Giữ thời lượng không đổi mà tăng tốc độ" là tình huống
khác hẳn "tăng tốc độ trên cùng tuyến bay". Phải giải thích trong bài.

---

## 8. Giới hạn sử dụng — bàn giao sang sản phẩm D3

### Envelope cự ly hợp lệ: khoảng 420 – 610 m

Thí nghiệm E2c (bổ sung ngoài giao thức): huấn luyện chỉ trên tuyến R1 ~472 m,
rồi dự báo các chuyến dài hơn.

| Dải cự ly | MAE | bias |
|---|---|---|
| 427 – 609 m | 0,740 | −0,15 |
| **~835 m** | **7,613** | **−7,613** |

Ở 835 m, `MAE = |bias|` — nghĩa là mô hình đoán thiếu ở **toàn bộ 5 chuyến, không
trừ chuyến nào**. Sai 29,6 % theo một chiều duy nhất, và là chiều nguy hiểm.

**Nghĩa vận hành:** hỏi hệ thống về chuyến giao hàng 835 m, nó trả lời *"cần
18 Wh"* trong khi thực tế cần 26 Wh → cấp phán quyết **FLY cho chuyến bay sẽ hết
pin giữa đường**. Đúng loại lỗi cho-bay-nhầm mà cả đề tài lấy làm thước đo chính.

**Hạn chế của chính thí nghiệm này:** cả 5 chuyến dài bay cùng ngày 19/09/2019.
Sai lệch có thể do cự ly dài, cũng có thể do điều kiện hôm đó — không tách được.
Viết là *kiểm tra sơ bộ*, không viết *đã kiểm chứng*.

### Sai số đưa vào tính dự trữ

| Dải | MAE dùng |
|---|---|
| Trong envelope 420 – 610 m | 0,74 Wh |
| Ngoài envelope | 7,6 Wh — **không khuyến nghị dùng** |

Trong envelope, sai số **ổn định qua mọi điều kiện** — tải, tốc độ, độ cao, gió
đều cho MAE 0,47–0,88 Wh và bias trung tính. Nên dùng một con số chung cho mọi
tải trọng và độ cao là chấp nhận được.

Theo cự ly thì **không** — phải phân biệt trong và ngoài envelope.

### Ràng buộc cho bộ sinh kịch bản ở sản phẩm D4

Lấy mẫu cự ly ngoài dải 420 – 610 m phải **đánh dấu rõ là ngoại suy** — §6/E3 yêu
cầu *"clearly label any extrapolated ranges"*.

---

## 9. Truy nguồn

| Khẳng định | File kết quả |
|---|---|
| Bảng MAE, RMSE, bias, WAPE | `reports/d2_e2a_flight_level_cv.csv` |
| Giữ lại cấu hình | `reports/d2_e2b_configuration_holdout.csv` |
| Ngoại suy cự ly | `reports/d2_e2c_distance_holdout.csv` |
| Sai số theo nhóm | `reports/d2_subgroup_errors.csv` |
| Khoảng tin cậy bootstrap | `reports/d2_bootstrap_differences.csv` |
| Hệ số hồi quy | `reports/d2_ridge_coefficients.csv` |
| Kiểm tương thích D5 | `reports/d5_hover_validation.csv` |
| Giao thức đã đóng băng | `configs/d2_protocol.yaml` |
| Lịch sử chạy | `reports/experiment_log.jsonl` |

Chạy lại toàn bộ: xem `docs/README.md`.
