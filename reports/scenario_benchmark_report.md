# Báo cáo benchmark kịch bản — sản phẩm D4

**Giao thức:** `configs/d4_protocol.yaml` v1.0.11 (đóng băng, Duy ký 2026-10-21)
**Sinh bởi:** `src/scenario_generator.py` → `src/reference_labeller.py` → `src/baselines_decision.py` → `src/evaluation_scenario.py`
**Ngày chạy:** 2026-10-23
**Hash bộ kịch bản:** `fa81622c5d36884f`

---

## 0. Cảnh báo phải đọc trước mọi con số

Mọi số trong báo cáo này là **simulation-derived**. Không có chuyến bay nào
được thực hiện để tạo ra chúng. Chúng **không chứng minh gì về an toàn trong
thực tế** — đây là cổng chặn của Mục 12.1, không phải lời rào đón.

Hai con số trong báo cáo này **không được báo như nó hiện ra**. Giao thức
(`must_state_in_paper`, quyết định C26) bắt buộc phát biểu nguyên văn:

```
(1) Ty le tu choi thua bang 0 doi voi mot so duong co so la he qua dai so
    cua viec nhan tham chieu bao thu hon he thong mot khoan lon hon chinh
    khoan bat dinh cua he thong; khong phai ket qua do duoc.

(2) Phan lon ty le tu choi cua phuong phap de xuat den tu co ngoai suy,
    khong tu quyet dinh nang luong.
```

Mục 5 và Mục 6 dưới đây giải thích cả hai.

---

## 1. Bộ kịch bản

| | |
|---|---|
| Tổng kịch bản sinh | 18 000 |
| Seed | 42 |
| Bảng chính dùng để chấm | **14 700** |
| Bị loại khỏi bảng chính | 3 300 |

Hai tầng bị loại và lý do (khai trong giao thức, không phải quyết định
lúc chấm):

| Tầng | Số | Loại vì |
|---|---|---|
| `hard_rule_probe` | 2 100 | Cố tình vi phạm giới hạn DJI. Giữ lại sẽ làm M-2 của mọi phương pháp có luật cứng tốt lên một cách giả tạo. Dùng riêng cho M-7. |
| `missing_input` | 1 200 | Thiếu đầu vào. Dùng riêng cho M-10 (fail-closed). |

Hai tầng còn lại nằm trong bảng chính: `main` (12 600) và `short_high`
(2 100 — cự ly ngắn + bay cao, vùng mà PH-1 ràng buộc hơn chỉ tiêu cự ly).

Trong 14 700 kịch bản của bảng chính, **0 kịch bản nhận nhãn `unknown`** —
tức mọi kịch bản được chấm, không có ô nào bị bỏ âm thầm.

---

## 2. Hai nhãn tham chiếu

Mục 6/E3 của Proposal đòi **hai** tham chiếu độc lập, cái thứ hai phải bảo
thủ hơn. Cả hai được Duy ký trong giao thức.

### REF-1 — dựa trên mô hình D2

```
E_required = E_d2_prediction + a,  a = 1.2924 Wh
```

`a = |q05|` của phân vị 5 % phía dưới của sai số OOF có dấu
(`residuals = oof_pred − y`, nên âm = đoán thiếu = nguy hiểm). Nói cách
khác: khoản phụ cấp vừa đủ để che 95 % trường hợp mô hình đoán thiếu.

### REF-2 — dựa trên vật lý, độc lập với D2

```
E_required = k × P_ideal(mass) × t_planned / 3600,  k = 7.44
k = p95( E_measured / (P_ideal · t / 3600) )
```

`k` hiệu chuẩn trên 192 chuyến của `data/processed/flight_level.csv`, lấy
phân vị 95 để REF-2 **bảo thủ hơn** REF-1 — yêu cầu của §6/E3. (Công thức
đầu tiên của REF-2 đòi 7,56 Wh so với 20,79 Wh đo được, tức lạc quan
2,7 lần, nên bị thay — quyết định C22.)

### Phân bố nhãn

| Nhãn | REF-1 | REF-2 |
|---|---|---|
| feasible | 11 950 | 7 861 |
| infeasible | 3 763 | 7 670 |
| marginal | 1 087 | 1 569 |
| unknown | 1 200 | 900 |

**Hai nhãn khác nhau trên 32,2 % kịch bản.** Đây là con số đáng báo: nó
cho biết kết luận của benchmark phụ thuộc bao nhiêu vào lựa chọn tham
chiếu. Bảng chính dưới đây chấm theo REF-1; S-2 chấm lại toàn bộ theo
REF-2.

Vùng biên: **1 077 kịch bản** thoả `|R−0| ≤ 0,05` hoặc `|R−r| ≤ 0,05`
(quyết định C14/C21, bề rộng w = 0,05 khai trước, quét trong S-4). Đạt
ngưỡng tối thiểu 1 000 của phép kiểm GEN-4b — đạt được bằng cách nâng
`n_scenarios` 6 000 → 18 000 theo phương án khắc phục đã khai trước, **không**
nới dải lấy mẫu (quyết định C20).

---

## 3. Bảy phương pháp

| Mã | Nội dung |
|---|---|
| B0 | Ngưỡng SoC cố định |
| B1 | Chỉ tiêu cự ly + hệ số dự trữ |
| B1-pure | Chỉ tiêu cự ly thuần, không dự trữ |
| B2 | Mô hình D2 + ngưỡng dự trữ, không luật cứng |
| B3 | B2 + luật cứng |
| **B5** | **Đề xuất: B3 + bậc giữa CONDITIONAL + hạ bậc ngoại suy** |
| B5-noHR | B5 bỏ luật cứng (dùng để bóc tách đóng góp của luật cứng) |

Mọi phương pháp chạy trên **cùng một bộ 14 700 kịch bản** và **cùng chính
sách dự trữ** (`r = 0,20`) — điều kiện công bằng của Mục 12.1.

Quy ước chấm (khai trước, quyết định C4 và C24):
- `marginal` → **không khả thi** (phía bảo thủ)
- `CONDITIONAL` → **không tính là duyệt bay** (§2.3: chưa thực thi được khi
  chưa có biện pháp)
- `INSUFFICIENT_DATA` → **không bao giờ** tính là duyệt bay (§4.6 fail-closed)

---

## 4. Bảng chính

Chấm theo REF-1, trên 14 700 kịch bản.

| Phương pháp | M-1 recall không khả thi | M-2 false-safe | M-4 từ chối thừa | M-5 F1 |
|---|---|---|---|---|
| B0 | 0,3904 | 0,6096 | 0,0003 | 0,8920 |
| B1 | 0,2187 | 0,7813 | 0,0000 | 0,8658 |
| B1-pure | 0,0472 | 0,9528 | 0,0000 | 0,8411 |
| B2 | 0,8345 | 0,1655 | 0,0229 | 0,9567 |
| B3 | 0,9246 | 0,0754 | 0,0000 | 0,9853 |
| **B5** | **0,9990** | **0,0010** | 0,7186 | 0,4391 |
| B5-noHR | 0,9954 | 0,0046 | 0,0000 | 0,9991 |

**M-2 là hướng nguy hiểm**: đáp án nói không khả thi mà hệ thống duyệt bay.
**M-4 là hướng phiền toái**: đáp án nói khả thi mà hệ thống từ chối. Hai cột
này **phải đọc cùng nhau** — một phương pháp từ chối tất cả sẽ có M-2 = 0
hoàn hảo và vô dụng hoàn toàn.

### Những gì bảng này cho thấy

1. **Chỉ tiêu cự ly là đường cơ sở yếu nhất.** B1-pure bỏ sót 95,3 % kịch
   bản không khả thi. Thêm hệ số dự trữ (B1) chỉ kéo lên 78,1 % bỏ sót.
   Lý do có thể kiểm được: chỉ tiêu cự ly không nhìn thấy payload, gió hay
   độ cao, trong khi ba biến này là nguồn biến thiên lớn nhất của năng
   lượng yêu cầu.

2. **Ngưỡng SoC cố định cũng yếu.** B0 bỏ sót 61,0 %. Nó bỏ sót theo cách
   khác B1: B0 không nhìn thấy nhiệm vụ, chỉ nhìn thấy pin.

3. **Mô hình dự báo là bước nhảy lớn nhất.** B1 → B2: 21,9 % → 83,5 %
   recall. Đây là đóng góp của sản phẩm D2.

4. **Luật cứng là bước nhảy lớn thứ hai.** B2 → B3: 83,5 % → 92,5 %, và
   M-4 giảm 0,0229 → 0,0000. Luật cứng chặn đúng những kịch bản mà mô hình
   năng lượng không có cách nào thấy được (gió quá giới hạn, payload quá
   giới hạn).

5. **So sánh đáng tin nhất về bậc giữa là B3 → B5-noHR**, vì hai cái này
   khác nhau đúng một thành phần: M-2 giảm **0,0754 → 0,0046**, tức giảm
   16 lần, với M-4 vẫn bằng 0. Đây là kết quả **thật và báo được**.

> **Hai điều kiện của kết quả này**, đo được ở Mục 8, phải nêu kèm mỗi lần
> trích dẫn bảng trên: nó phụ thuộc vào giả định pin TB47D (S-1 cho thấy
> M-2 của B5-noHR tăng 70 lần với TB48D), và ưu thế của bậc giữa chỉ đo
> được trên vùng `marginal` (S-3 cho thấy ưu thế biến mất khi đổi quy ước).

---

## 5. Cảnh báo (1) — M-4 = 0 là tất yếu đại số

Bảng trên cho thấy B3, B1, B1-pure và B5-noHR đều có M-4 = 0,0000. Nhìn
vào bảng, điều này **trông như** một phát hiện: "bậc giữa cải thiện an toàn
mà không tốn thêm gì". **Phát biểu đó bị cấm** (quyết định C26), vì nó là
hệ quả đại số, không phải kết quả đo.

Chứng minh:

Kịch bản được tham chiếu gọi là **khả thi** nghĩa là
```
E_av ≥ (1 + r)(E_pred + a)
```
Chia hai vế cho `E_pred` và trừ 1:
```
R_sys = E_av/E_pred − 1 ≥ r + (1 + r)·a / E_pred
```
Ngưỡng FLY của hệ thống là
```
R_fly = r + b / E_pred,   b = 1,4687 Wh
```
Nên mọi kịch bản tham chiếu-khả thi tự động vượt `R_fly` khi
```
(1 + r)·a ≥ b
```
Số thật: `(1 + 0,20) × 1,2924 = 1,5509 ≥ 1,4687`. **Biên của bất đẳng thức
chỉ 0,0822 Wh.**

Nghĩa là: nhãn tham chiếu bảo thủ hơn hệ thống một khoản *lớn hơn* chính
khoản bất định của hệ thống. Không kịch bản tham chiếu-khả thi nào có thể
rơi vào bậc giữa, nên bậc giữa **không thể bị tính là từ chối thừa** —
bất kể bậc giữa được thiết kế thế nào.

Phép kiểm này được in tự động ở cuối mỗi lần chạy và khoá bằng test.
Giao thức **cấm** điều chỉnh `a`, `b` hay `r` để "sửa" con số này: sửa đi
sẽ là chọn tham số theo kết quả mong muốn.

---

## 6. Cảnh báo (2) — M-4 của B5 không phải quyết định năng lượng

M-4 của B5 bằng **0,7186**. Đọc nguyên con số thành "B5 từ chối thừa 72 %"
là **sai**.

Bóc tách theo nguyên nhân (`reports/d4_b5_rejection_causes.csv`):
**71,9 %** kịch bản tham chiếu-khả thi bị B5 hạ bậc vì **ngoại suy** —
luật PD-1/PD-2, kích hoạt khi mô hình D2 phải dự báo ngoài dải cự ly có dữ
liệu đo (envelope 420–610 m). Trong 14 700 kịch bản của bảng chính,
10 706 kịch bản (72,8 %) nằm ngoài envelope này — con số này khớp với
71,9 %, nên nguyên nhân đã xác nhận bằng số, không còn là suy đoán.

Phát biểu đúng: **B5 gắn cờ "ngoài vùng hiệu lực" cho 72 % kịch bản**, chứ
không phải B5 cho rằng 72 % kịch bản thiếu năng lượng. Đây là hành vi
đúng theo thiết kế — PD-1/PD-2 tồn tại chính để hệ thống không im lặng
ngoại suy — nhưng nó cũng là phát hiện quan trọng nhất về **giới hạn của
tập dữ liệu**: envelope cự ly 420–610 m quá hẹp so với dải kịch bản giao.

Hệ quả cho D6–D9: muốn giảm con số này thì phải **mở rộng dữ liệu bay**,
không phải nới luật.

---

## 7. Hai thuộc đo trên tầng riêng

| Mã | Nội dung | Tầng | Kết quả |
|---|---|---|---|
| M-7 | Số lần luật cứng bị vi phạm mà vẫn duyệt bay | `hard_rule_probe` (2 100) | xem `d4_hard_rule_audit.csv` |
| M-10 | Thiếu đầu vào mà vẫn duyệt bay (fail-closed) | `missing_input` (1 200) | xem `d4_hard_rule_audit.csv` |

**M-7 = 0 ở cấu hình có luật cứng là THEO THIẾT KẾ, không phải kết quả.**
Giao thức vì vậy bắt báo **cả hai** cấu hình (quyết định C23): có luật cứng
và không luật cứng. Chỉ báo cấu hình có luật cứng thì "0 vi phạm" đọc như
một kết quả trong khi nó là một hằng số.

Ghi chú kỹ thuật (OI-D4-6): đầu vào thiếu trong CSV là `NaN`, không phải
`None`. Tầng luật cứng của D3 kiểm `giá_trị is None`, và `NaN is None` là
False, `NaN > 10.0` cũng là False — nên HR-1 từng báo PASS cho kịch bản
gió không rõ. Đã sửa bằng hàm chuẩn hoá `nan_sang_none()` tại 19 điểm gọi
ở ranh giới D4↔D3. Bản thân D3 để nguyên (đã nghiệm thu, hành vi trên
đường chạy của riêng nó không bị ảnh hưởng), nhưng đây là **bẫy tiềm ẩn
phải xử lý ở D6**.

---

## 8. Bốn phép đo độ nhạy bắt buộc

| Mã | Quét gì | Vì sao bắt buộc |
|---|---|---|
| S-1 | Pin TB48D (129,96 Wh) thay TB47D | P§4.4 — bài Rodrigues tự mâu thuẫn về loại pin, nên không được chọn một loại rồi im |
| S-2 | Chấm lại toàn bộ theo REF-2 | hai nhãn khác nhau 32,2 %, nên kết luận phải chịu được việc đổi tham chiếu |
| S-3 | Đổi chiều `marginal` → khả thi | quy ước C4 là lựa chọn, không phải sự thật |
| S-4 | Quét bề rộng vùng biên w | w = 0,05 là con số khai trước, không phải con số đo |

Dữ liệu đầy đủ: `reports/d4_sensitivity_runs.csv`.

### 8.1 Thứ hạng — giữ nguyên

Xếp theo M-2 (false-safe, thấp là tốt):

| Cấu hình | Thứ hạng |
|---|---|
| gốc | B5 < B5-noHR < B3 < B2 < B0 < B1 < B1-pure |
| S-1 | B5 < B5-noHR < B3 < B2 < B0 < B1 < B1-pure |
| S-2 | B5 < B5-noHR < B3 < B2 < B0 < B1 < B1-pure |
| S-3 | **B3 = B5 = B5-noHR** (hoà ở 0) < B2 < B0 < B1 < B1-pure |
| S-4 (w = 0,025) | giống hệt cấu hình gốc |
| S-4 (w = 0,1) | giống hệt cấu hình gốc |

**Không phép quét nào đảo thứ hạng.** Kết luận chính của D4 — chỉ tiêu cự ly
yếu nhất, mô hình dự báo là bước nhảy lớn nhất, luật cứng là bước nhảy lớn
thứ hai — đứng được qua cả bốn phép quét.

Nhưng ba phép quét cho thêm thông tin mà bảng chính không có, và cả ba đều
phải vào bài.

### 8.2 S-1 — thứ hạng giữ, con số tuyệt đối xấu đi nhiều

| Phương pháp | M-2 gốc | M-2 với TB48D |
|---|---|---|
| B0 | 0,6096 | 0,6096 *(không đổi)* |
| B1 | 0,7813 | 0,8012 |
| B1-pure | 0,9528 | **0,9938** |
| B2 | 0,1655 | **0,4113** |
| B3 | 0,0754 | **0,3811** |
| B5 | 0,0010 | **0,0829** |
| B5-noHR | 0,0046 | **0,3231** |

B5-noHR tăng **70 lần** (0,0046 → 0,3231). Đây là con số xấu nhất của cả D4.

**Cơ chế, xác nhận bằng số:** nhãn tham chiếu được **phê duyệt trước và giữ
nguyên** — chúng không được tính lại theo loại pin. Chỉ `E_available` của hệ
thống đổi. Bằng chứng: B0 **không đổi tới 7 chữ số**, vì B0 là ngưỡng SoC cố
định nên quyết định của nó độc lập với dung lượng pin; nếu nhãn tham chiếu có
thay đổi thì mẫu số của B0 đã đổi theo. Vậy đổi sang pin lớn hơn làm hệ thống
duyệt bay nhiều hơn, trong khi thước đo vẫn là thước cũ.

**Nghĩa là:** mọi con số an toàn của D4 phụ thuộc vào giả định `E_nominal =
99,9 Wh` (TB47D). Bài gốc Rodrigues **tự mâu thuẫn** về loại pin (P§4.4), nên
đây không phải giả định an toàn. Phải nêu trong phần hạn chế của bài.

### 8.3 S-3 — ưu thế của B5 trên M-2 biến mất

Khi `marginal` được tính là **khả thi**:

| Phương pháp | M-1 | M-2 | M-4 |
|---|---|---|---|
| B3 | **1,0000** | **0,0000** | 0,0558 |
| B5 | **1,0000** | **0,0000** | 0,7417 |
| B5-noHR | **1,0000** | **0,0000** | 0,0816 |
| B2 | 0,9463 | 0,0537 | 0,0591 |

Ba phương pháp **hoà nhau ở recall hoàn hảo**, nên M-2 không còn phân biệt được
chúng. Phân biệt phải chuyển sang M-4, và ở đó **B3 tốt hơn B5-noHR**
(0,0558 < 0,0816).

**Lý do:** gộp `marginal` vào khả thi lấy đúng những trường hợp khó nhất ra
khỏi tập "không khả thi". Còn lại là các trường hợp dễ, mà mọi phương pháp có
mô hình dự báo đều bắt được.

**Hệ quả cho bài:** ưu thế của bậc giữa chỉ đo được **trên vùng marginal**. Quy
ước C4 (`marginal` → không khả thi) không phải lựa chọn trung tính — nó là điều
kiện để kết quả chính của D4 có ý nghĩa, và phải nói rõ như vậy.

### 8.4 S-4 — không tác động, và đó là một phát hiện nhỏ

Cả `w = 0,025` và `w = 0,1` cho bảng **giống hệt** cấu hình gốc, tới từng chữ số.

Đúng theo thiết kế: `w` chỉ dùng để **tách** M-3 (false-safe trong/ngoài vùng
biên), không tham gia việc chấm điểm. Nên kết luận chính của D4 **không phụ
thuộc** vào con số 0,05 khai trước — một điều tốt.

**Nhưng phải thừa nhận hạn chế của chính phép quét này:** S-4 vì vậy không kiểm
chứng được gì về vai trò của `w` trong bảng M-3. Muốn kiểm điều đó thì phải quét
lại `d4_boundary_breakdown.csv` theo `w`, chưa làm.

---

## 9. Tám bảng xuất ra

| Tệp | Nội dung |
|---|---|
| `d4_main_comparison.csv` | bảng chính, 7 phương pháp × M-1/M-2/M-4/M-5 |
| `d4_confusion_matrices.csv` | bốn ô nhị phân cho mỗi phương pháp, cộng ba lớp cho B5 và B5-noHR |
| `d4_boundary_breakdown.csv` | M-3 — false-safe tách trong/ngoài vùng biên |
| `d4_hard_rule_audit.csv` | M-7 và M-10 trên hai tầng riêng |
| `d4_b5_rejection_causes.csv` | bóc tách M-4 của B5 theo nguyên nhân (Mục 6) |
| `d4_structural_relation.csv` | quan hệ `(1+r)a` vs `b` (Mục 5) |
| `d4_tradeoff_curve.csv` | đường đánh đổi theo hệ số dự trữ **và** ngưỡng SoC cố định |
| `d4_sensitivity_runs.csv` | S-1 … S-4 |

---

## 10. Đối chiếu Mục 12.1 — tiêu chí nghiệm thu D4

| # | Tiêu chí | Bằng chứng |
|---|---|---|
| 1 | Dải lấy mẫu và seed được lưu, sinh lại được | `d4_protocol.yaml §scenario_generator`, seed 42, hash `fa81622c5d36884f`, `d4_generator_check.csv` 5/5 |
| 2 | Nhãn tham chiếu được phê duyệt trước khi chấm | giao thức đóng băng v1.0.11, Duy ký 2026-10-21, trước lần chạy đầu |
| 3 | Mọi con số dán nhãn `simulation-derived` | Mục 0, in ở đầu và cuối mỗi lần chạy |
| 4 | B0–B5 được cài đặt | `src/baselines_decision.py`, 7 phương pháp |
| 5 | Cùng bộ kịch bản, cùng chính sách dự trữ | 14 700 kịch bản, `r = 0,20` cho mọi phương pháp |
| 6 | Báo cả false-safe và từ chối thừa | Mục 4, cộng hai cảnh báo bắt buộc ở Mục 5 và Mục 6 |

**6/6 đạt.**

---

## 11. Còn mở

| Mã | Nội dung | Chặn D4? |
|---|---|---|
| RS-3 | Lệch cự ly 92,8 km so với ~65 km | không |
| OI-D4-4 | `interpretability.py` dùng `KFold` trần → alpha 1,0, khác alpha 0,1 của giao thức | không — để nguyên, đã ghi |
| OI-D4-6 | `NaN is None` ở tầng luật cứng của D3 | không — đã vá ở ranh giới, **phải xử lý ở D6** |
| OI-5 | `Draft Báo.docx` dùng số của Matrice 210 | không — ảnh hưởng D8 |
