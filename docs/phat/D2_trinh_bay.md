# Sản phẩm D2 — bản trình bày

Phát · nguồn: `docs/san_pham/D2_benchmark_nang_luong.md`, `reports/model_selection_report.md`

---

# PHẦN A — Bản nói

> Thuộc ý, không cần thuộc chữ.

Sản phẩm D2 hỏi một câu: **đưa 6 dữ kiện biết trước khi bay, mô hình nào đoán
đúng nhất năng lượng sẽ tốn?** Đáp án thật đã có từ sản phẩm D1 nên chấm điểm
được.

Sáu dữ kiện: tải trọng, tốc độ, độ cao, cự ly, gió, **và thời lượng kế hoạch**.

**D0** không học gì, trả lời 21,3 Wh mọi lúc — làm **mốc sàn**. MAE 3,975.

**D1** chỉ nhìn cự ly. MAE 3,974 — ngang D0, chênh 0,001 Wh. Nhưng **không**
nghĩa là cự ly không ảnh hưởng tới năng lượng: 180 trên 192 chuyến bay cùng một
tuyến, cự ly dao động chỉ 5,3 m, nên cự ly gần như là **hằng số** và dữ liệu
**không cho phép kiểm** điều đó.

**D2 Ridge** tìm một công thức cộng từ 6 yếu tố. Hai phiên bản:

- **-a** dùng thời lượng **đo được** — chỉ biết sau khi bay xong. MAE 1,073.
- **-b** dùng thời lượng **kế hoạch** = cự ly ÷ tốc độ — tính được trước khi cất
  cánh. MAE **0,657**.

Bất ngờ là **-b thắng -a 39%**. Nên phiên bản chạy được trước chuyến bay **không
phải nhượng bộ** — nó vừa đúng về vận hành vừa chính xác hơn.

**D3 Random Forest** không tìm công thức. Nó dựng 300 cây quyết định kiểu *"nếu
tải > 250 g thì… nếu độ cao > 50 m thì…"* rồi lấy trung bình 300 kết quả. MAE
1,014, kém Ridge.

Nhưng vấn đề nặng hơn MAE: nó **học vẹt** (tụt 37% khi gặp tổ hợp mới) và **đoán
thiếu** ở tải nặng, bay cao, cự ly dài.

**D4** gradient boosting **bị chặn** theo Mục 2.4 — không được bắt đầu cho tới
khi sản phẩm D1 đến D5 đạt nghiệm thu. Không phải nhóm em quên.

**D5** mô hình vật lý — **khả thi một phần**. Dựng được 2 trên 4 thành phần, phần
đó kiểm chứng sai **3,4%**. Hai thành phần còn lại thiếu tham số vì DJI không công
bố độ đặc cánh và diện tích cản thân. §5.2 ghi thiếu tham số thì **không được
bịa**, phải loại khỏi xếp hạng định lượng — nên nó không có trong bảng.

**Chọn D2-b**, thắng cả bốn tiêu chí. Và em xin nhấn: hai tiêu chí đầu là **điều
kiện loại**, không phải điểm cộng — nên kể cả Random Forest có MAE thấp hơn thì
nhóm em vẫn không chọn, vì nó đoán thiếu ở tải nặng và bay cao.

---

# PHẦN B — Bốn tiêu chí

Bốn câu hỏi, hỏi theo thứ tự. **Trượt câu 1 hoặc 2 là loại ngay**, bất kể sai số
đẹp đến đâu.

### 1. Mô hình có chạy được lúc chưa bay không?

Xem nó cần cột nào. Cần cột chỉ biết sau khi bay → loại.

→ **D2-a và D3-a loại ở đây** (cần thời lượng bay thật).

### 2. Mô hình đoán thiếu hay đoán thừa?

Lấy sai số **giữ nguyên dấu**, tách theo từng điều kiện — tải 0/250/500 g, độ cao
25/50/75/100 m, 5 mức tốc độ, 3 chế độ gió.

- Số **dương** = đoán thừa = từ chối oan. Phí nhưng **an toàn**.
- Số **âm** = đoán thiếu = **cho bay chuyến sẽ hết pin giữa đường**.

→ **Random Forest loại ở đây**: tải 500 g là −0,65, cao 100 m là −0,71.

### 3. Mô hình hiểu hay học vẹt?

Bỏ nguyên một tổ hợp điều kiện ra khỏi phần học, rồi bắt nó đoán đúng tổ hợp đó.
Lặp qua cả 60 tổ hợp.

- Ridge tệ đi **2%** → hiểu quy luật.
- Random Forest tệ đi **37%** → chỉ nhớ.

### 4. Cái nào sai ít nhất?

Sai số **bỏ dấu**. Ridge **0,657 Wh**, Random Forest 1,014.

Rồi bootstrap 2.000 lần để xác nhận chênh lệch là thật: khoảng tin cậy của hai mô
hình **không chồng lấn nhau**.

---

## Chỗ phải nhớ

**Câu 2 phải tách theo nhóm, không được tính tổng.**

Random Forest có sai số tổng = **−0,001** — gần như hoàn hảo. Vì nó đoán thừa ở
nhóm này, đoán thiếu ở nhóm kia, cộng lại **triệt tiêu nhau**.

Tách ra mới thấy nó đoán thiếu ở tải nặng và bay cao.

**Nếu chỉ xem số tổng thì đã chọn Random Forest** — và bàn giao sang sản phẩm D3
một mô hình có lỗ hổng an toàn mà không ai biết.

Đó là lý do §5.3 của thầy bắt làm phân tích theo nhóm.

---

# PHẦN C — Bảng chấm

| Mô hình | 1 pre-flight | 2 không đoán thiếu | 3 không học vẹt | 4 MAE | |
|---|---|---|---|---|---|
| D0 trung bình hằng | ✅ | ✅ | ✅ | 3,975 | mốc sàn |
| D1 chỉ cự ly | ✅ | ⚠ −0,33 | ✅ | 3,974 | ngang D0 |
| D2-a Ridge | ❌ | ✅ | ✅ | 1,073 | **loại ở 1** |
| **D2-b Ridge** | ✅ | ✅ | ✅ +2% | **0,657** | **ĐƯỢC CHỌN** |
| D3-a Random Forest | ❌ | ⚠ | ❌ | 1,362 | **loại ở 1** |
| D3-b Random Forest | ✅ | ❌ ba vùng | ❌ +37% | 1,014 | **loại ở 2** |
| D4 gradient boosting | — | — | — | — | bị chặn (Mục 2.4) |
| D5 mô hình vật lý | — | — | — | — | thiếu tham số (§5.2) |

**Mô hình được chọn: `D2_ridge_preflight`**

| | |
|---|---|
| Thuật toán | Ridge, alpha = 1,0 |
| Đặc trưng | `payload_num`, `speed_num`, `altitude_num`, `distance_2d_m`, `wind_raw_mean_ms`, `duration_planned_s` |
| MAE | 0,657 Wh (3,09%) |
| Khoảng tin cậy 95% | [0,582 ; 0,729] Wh |
| bias | +0,010 Wh |
| Mã nguồn | `src/models.py` → `make_d2()` |

---

# Ba chỗ nói sai là đổ lập luận

| Đừng nói | Nói |
|---|---|
| -a là kế hoạch, -b là đo được | **-a đo được, -b kế hoạch** |
| chọn D2-b vì MAE thấp nhất | chọn vì thắng **cả 4** tiêu chí, MAE là tiêu chí **cuối** |
| D5 không tính được | D5 **khả thi một phần**, 2/4 thành phần, sai 3,4% |

Cách nhớ -a: **"as written"** — đúng chữ §5.2 của thầy.

---

# Truy nguồn

| Tiêu chí | File |
|---|---|
| 1 — pre-flight | `configs/d2_protocol.yaml` (9 cột cấm) · `src/evaluation_energy.py` |
| 2 — không đoán thiếu | `reports/d2_subgroup_errors.csv` |
| 3 — không học vẹt | `reports/d2_e2b_configuration_holdout.csv` |
| 4 — MAE | `reports/d2_e2a_flight_level_cv.csv` · `reports/d2_bootstrap_differences.csv` |
| Thứ tự chọn đúng quy trình | `reports/model_selection_report.md` · `reports/experiment_log.jsonl` |
