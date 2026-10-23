# Sản phẩm D4 — Benchmark trên kịch bản mô phỏng

> Mục 12 / Mục 12.1 của Proposal.
> Trạng thái: **xong 6/6 bước, đạt 6/6 tiêu chí nghiệm thu.**
> Báo cáo số: `reports/scenario_benchmark_report.md`

---

## 1. D4 trả lời câu hỏi gì

D3 cho ta một bộ máy quyết định. Nhưng **bộ máy đó có hơn cách làm cũ
không, và hơn ở chỗ nào** thì D3 không trả lời được, vì D3 chỉ chạy trên
192 chuyến bay có thật — quá ít và quá hẹp để so sánh bảy phương pháp.

D4 sinh **18 000 kịch bản giả** có đáp án biết trước, rồi cho bảy phương
pháp cùng chạy trên đó.

**Cái D4 không làm:** nó không chứng minh hệ thống an toàn trong thực tế.
Đáp án là do ta tự đặt ra, không phải do bay thử. Đây là lý do mọi con số
đều phải dán nhãn **simulation-derived** — cổng chặn của Mục 12.1.

---

## 2. Bốn thành phần

```
scenario_generator.py   18 000 kịch bản         (dải + seed khai trước)
        ↓
reference_labeller.py   gắn ĐÁP ÁN cho mỗi cái  (hai tham chiếu độc lập)
        ↓
baselines_decision.py   7 phương pháp cùng chạy (cùng kịch bản, cùng r)
        ↓
evaluation_scenario.py  chấm điểm → 8 bảng CSV
```

### 2.1 Bộ sinh kịch bản

4 tầng, seed 42:

| Tầng | Số | Để làm gì |
|---|---|---|
| `main` | 12 600 | bảng chính |
| `short_high` | 2 100 | cự ly ngắn + bay cao, vùng mà PH-1 ràng buộc hơn chỉ tiêu cự ly |
| `hard_rule_probe` | 2 100 | cố tình vi phạm giới hạn DJI — **chỉ** dùng cho M-7 |
| `missing_input` | 1 200 | thiếu đầu vào — **chỉ** dùng cho M-10 |

Hai tầng cuối **bị loại khỏi bảng chính**, lý do khai trong giao thức
chứ không quyết định lúc chấm. Giữ chúng lại sẽ làm điểm an toàn của mọi
phương pháp có luật cứng tốt lên một cách giả tạo.

Bảng chính còn **14 700** kịch bản.

### 2.2 Đáp án — hai tham chiếu, không phải một

§6/E3 đòi hai tham chiếu độc lập, cái thứ hai bảo thủ hơn:

- **REF-1** = dự báo của mô hình D2 cộng phụ cấp `a = 1,2924 Wh`
  (phụ cấp vừa đủ che 95 % trường hợp D2 đoán thiếu).
- **REF-2** = hoàn toàn từ vật lý, không dùng D2:
  `k × P_ideal(khối lượng) × thời_gian / 3600`, với `k = 7,44` hiệu chuẩn
  trên 192 chuyến thật ở phân vị 95.

**Hai đáp án khác nhau trên 32,2 % kịch bản.** Đây là con số phải báo: nó
cho biết kết luận phụ thuộc bao nhiêu vào việc ta chọn đáp án nào. Bảng
chính chấm theo REF-1; phép đo độ nhạy S-2 chấm lại toàn bộ theo REF-2.

### 2.3 Bảy phương pháp

| Mã | |
|---|---|
| B0 | ngưỡng SoC cố định |
| B1 | chỉ tiêu cự ly + dự trữ |
| B1-pure | chỉ tiêu cự ly thuần |
| B2 | mô hình D2 + dự trữ |
| B3 | B2 + luật cứng |
| **B5** | **đề xuất: B3 + bậc giữa + hạ bậc ngoại suy** |
| B5-noHR | B5 bỏ luật cứng, để bóc tách đóng góp của luật cứng |

Cùng 14 700 kịch bản, cùng `r = 0,20`.

---

## 3. Kết quả

| Phương pháp | bắt được kịch bản xấu | **duyệt bay kịch bản xấu** | từ chối oan |
|---|---|---|---|
| B1-pure | 4,7 % | **95,3 %** | 0 % |
| B1 | 21,9 % | **78,1 %** | 0 % |
| B0 | 39,0 % | **61,0 %** | 0,03 % |
| B2 | 83,5 % | **16,6 %** | 2,3 % |
| B3 | 92,5 % | **7,5 %** | 0 % |
| B5-noHR | 99,5 % | **0,5 %** | 0 % |
| **B5** | **99,9 %** | **0,1 %** | 71,9 % |

Cột giữa là cột nguy hiểm. Cột phải là cột phiền toái. **Phải đọc cả hai** —
một phương pháp từ chối tất cả sẽ có cột giữa bằng 0 hoàn hảo và vô dụng
hoàn toàn.

### Bốn điều rút ra

1. **Chỉ tiêu cự ly là cách làm yếu nhất** — bỏ sót 95 %. Nó không nhìn
   thấy payload, gió, độ cao.
2. **Mô hình dự báo là bước nhảy lớn nhất** (B1 → B2: 22 % → 84 %). Đây là
   đóng góp của D2.
3. **Luật cứng là bước nhảy lớn thứ hai** (B2 → B3: 84 % → 93 %, và từ chối
   oan về 0). Luật cứng chặn đúng cái mô hình năng lượng không thấy được.
4. **So sánh đáng tin nhất về bậc giữa là B3 → B5-noHR**, vì chúng khác
   nhau đúng một thành phần: duyệt bay kịch bản xấu giảm **7,5 % → 0,5 %**,
   tức **16 lần**, mà từ chối oan vẫn bằng 0. Đây là kết quả thật và
   báo được.

> **Kết quả thứ 4 có hai điều kiện**, đo được ở Mục 6, phải nêu kèm mỗi lần
> trích bảng trên: nó phụ thuộc giả định pin TB47D (S-1), và ưu thế của bậc
> giữa chỉ đo được trên vùng `marginal` (S-3).

---

## 4. Hai con số KHÔNG được báo như nó hiện ra

Giao thức bắt phát biểu nguyên văn hai câu này trong bài (quyết định C26).
Đây là phần dễ bị đọc sai nhất của cả D4.

### (1) "Từ chối oan = 0" là tất yếu đại số, không phải kết quả đo

Nhìn bảng, B3 và B5-noHR đều có từ chối oan bằng 0. Trông như một phát
hiện đẹp. Nhưng nó là hệ quả của số học:

- đáp án gọi là khả thi khi `E_av ≥ (1+r)(E_pred + a)`
- hệ thống duyệt FLY khi `E_av ≥ E_pred + b + r·E_pred`
- so hai cái: `(1+r)·a = 1,5509` còn `b = 1,4687`

Vì **1,5509 ≥ 1,4687**, mọi kịch bản mà đáp án gọi là khả thi đều tự động
vượt ngưỡng FLY. Bậc giữa **không thể** bị tính là từ chối oan, dù thiết
kế thế nào. Biên của bất đẳng thức chỉ **0,0822 Wh**.

→ **Cấm viết** "bậc giữa cải thiện an toàn mà không tốn thêm gì".
→ Giao thức **cấm** chỉnh `a`, `b`, `r` để "sửa" con số này — sửa đi là
chọn tham số theo kết quả mong muốn.

### (2) 71,9 % của B5 là cờ ngoại suy, không phải quyết định năng lượng

B5 có từ chối oan 71,9 %. Đọc thành "B5 từ chối thừa 72 %" là **sai**.

Bóc tách: **71,9 %** kịch bản bị B5 hạ bậc vì **ngoại suy** — luật
PD-1/PD-2 kích hoạt khi D2 phải dự báo ngoài dải cự ly có dữ liệu đo
(420–610 m). Trong 14 700 kịch bản, **10 706 (72,8 %)** nằm ngoài dải này.
Hai con số khớp nhau, nên nguyên nhân đã xác nhận bằng số.

Phát biểu đúng: **B5 gắn cờ "ngoài vùng hiệu lực" cho 72 % kịch bản.**

Đây là hành vi đúng theo thiết kế — PD-1/PD-2 tồn tại chính để hệ thống
không im lặng ngoại suy. Nhưng nó cũng là phát hiện quan trọng nhất của
D4 về **giới hạn dữ liệu**: dải cự ly 420–610 m quá hẹp so với dải kịch
bản giao hàng.

→ Hệ quả cho D6–D9: muốn giảm con số này phải **mở rộng dữ liệu bay**,
không phải nới luật.

---

## 5. Hai thứ không chấm ở bảng chính

| | Tầng riêng | Vì sao tách |
|---|---|---|
| **M-7** vi phạm luật cứng mà vẫn duyệt | `hard_rule_probe` | **M-7 = 0 là theo thiết kế, không phải kết quả.** Giao thức bắt báo cả hai cấu hình (có / không luật cứng) — chỉ báo cấu hình có luật cứng thì "0 vi phạm" đọc như kết quả trong khi nó là hằng số. |
| **M-10** thiếu dữ liệu mà vẫn duyệt | `missing_input` | §4.6 fail-closed: `INSUFFICIENT_DATA` không có đường nào thành duyệt bay. |

---

## 6. Bốn phép đo độ nhạy — và vì sao bắt buộc

| | Quét gì | Vì sao |
|---|---|---|
| S-1 | pin TB48D thay TB47D | P§4.4 — bài Rodrigues tự mâu thuẫn về loại pin, nên không được chọn một loại rồi im |
| S-2 | chấm lại theo REF-2 | hai đáp án khác 32,2 %, kết luận phải chịu được việc đổi đáp án |
| S-3 | `marginal` → tính là khả thi | quy ước này là lựa chọn, không phải sự thật |
| S-4 | quét bề rộng vùng biên w | w = 0,05 là số khai trước, không phải số đo |

### Kết quả: thứ hạng giữ nguyên

| Cấu hình | Thứ hạng theo "duyệt bay kịch bản xấu" |
|---|---|
| gốc | B5 < B5-noHR < B3 < B2 < B0 < B1 < B1-pure |
| S-1 | B5 < B5-noHR < B3 < B2 < B0 < B1 < B1-pure |
| S-2 | B5 < B5-noHR < B3 < B2 < B0 < B1 < B1-pure |
| S-3 | **B3 = B5 = B5-noHR** (hoà ở 0) < B2 < B0 < B1 < B1-pure |
| S-4 | giống hệt cấu hình gốc (cả w = 0,025 và w = 0,1) |

**Không phép quét nào đảo thứ hạng.** Kết luận chính của D4 đứng được.

Nhưng ba phép quét cho thêm ba thông tin mà bảng chính không có:

**S-1 — con số tuyệt đối xấu đi rất nhiều.** Đổi sang pin TB48D thì B5-noHR
tăng từ 0,46 % lên **32,3 %**, tức **70 lần**. Lý do: nhãn tham chiếu được
phê duyệt trước nên **giữ nguyên**, chỉ `E_available` của hệ thống đổi — pin
lớn hơn thì hệ thống duyệt bay nhiều hơn trong khi thước đo vẫn là thước cũ.
Bằng chứng: B0 không đổi tới 7 chữ số, vì B0 là ngưỡng SoC cố định nên không
phụ thuộc dung lượng pin.
→ Mọi con số an toàn của D4 phụ thuộc vào giả định pin TB47D, mà **bài gốc tự
mâu thuẫn về loại pin**. Phải nêu ở phần hạn chế.

**S-3 — ưu thế của bậc giữa biến mất.** Khi `marginal` tính là khả thi thì
B3, B5, B5-noHR **hoà nhau** ở recall 1,0 và false-safe 0,0. Phân biệt phải
chuyển sang từ chối oan, và ở đó B3 (0,0558) **tốt hơn** B5-noHR (0,0816).
Lý do: gộp `marginal` vào khả thi lấy đúng các trường hợp khó nhất ra khỏi
tập "không khả thi", còn lại là các ca dễ mà mọi phương pháp có mô hình đều
bắt được.
→ Ưu thế của bậc giữa **chỉ đo được trên vùng marginal**. Quy ước C4 không
phải lựa chọn trung tính — nó là điều kiện để kết quả chính có ý nghĩa.

**S-4 — không tác động.** Cả hai bề rộng cho bảng giống hệt gốc, vì `w` chỉ
dùng để tách bảng M-3 chứ không tham gia chấm điểm. Tốt: kết luận chính không
phụ thuộc con số 0,05 khai trước. Nhưng cũng phải thừa nhận phép quét này
**không kiểm chứng được gì** về vai trò của `w` trong bảng M-3 — muốn kiểm
thì phải quét `d4_boundary_breakdown.csv` theo `w`, chưa làm.

---

## 7. Chạy lại

```bash
python3 -m src.scenario_generator     # 18 000 kịch bản, hash fa81622c5d36884f
python3 -m src.reference_labeller     # gắn hai đáp án
python3 -m src.evaluation_scenario    # 8 bảng CSV  (KHÔNG dùng --nhanh)
pytest -q
```

`--nhanh` bỏ qua S-1 để chạy nhanh khi đang phát triển. **Bản cuối phải
chạy đầy đủ** — chương trình sẽ in cảnh báo nếu thiếu.

Tám bảng xuất ra `reports/`: `d4_main_comparison`, `d4_confusion_matrices`,
`d4_boundary_breakdown`, `d4_hard_rule_audit`, `d4_b5_rejection_causes`,
`d4_structural_relation`, `d4_tradeoff_curve`, `d4_sensitivity_runs`.

---

## 8. Đối chiếu Mục 12.1

| # | Tiêu chí | Đạt |
|---|---|---|
| 1 | dải + seed lưu lại, sinh lại được | ✅ seed 42, hash `fa81622c5d36884f`, 5/5 phép kiểm GEN |
| 2 | đáp án phê duyệt **trước** khi chấm | ✅ giao thức đóng băng v1.0.11, Duy ký 21/10, trước lần chạy đầu |
| 3 | mọi con số dán `simulation-derived` | ✅ in ở đầu và cuối mỗi lần chạy |
| 4 | B0–B5 được cài đặt | ✅ 7 phương pháp |
| 5 | cùng kịch bản, cùng chính sách dự trữ | ✅ 14 700 kịch bản, `r = 0,20` |
| 6 | báo **cả** false-safe **và** từ chối oan | ✅ cộng hai cảnh báo bắt buộc ở Mục 4 |

**6/6.**

---

## 9. Còn mở

| | | Chặn D4? |
|---|---|---|
| RS-3 | lệch cự ly 92,8 km vs ~65 km | không |
| OI-D4-4 | `interpretability.py` dùng `KFold` trần → alpha 1,0 ≠ alpha 0,1 của giao thức | không, đã ghi |
| OI-D4-6 | `NaN is None` ở tầng luật cứng D3 — đã vá ở ranh giới D4↔D3 | không, **phải xử lý ở D6** |
| OI-5 | `Draft Báo.docx` dùng số Matrice 210 | không, ảnh hưởng D8 |
