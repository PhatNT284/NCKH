# Safety-Aware Pre-Flight Energy Feasibility Assessment for Delivery UAV Missions

Mã nguồn cho đề tài NCKH đánh giá khả thi năng lượng trước chuyến bay cho UAV giao hàng.

- **Nền tảng tham chiếu:** DJI Matrice 100
- **Bộ dữ liệu:** CMU *Data Collected with Package Delivery Quadcopter Drone*
  — DOI [10.1184/R1/12683453](https://doi.org/10.1184/R1/12683453)
- **Bài mô tả bộ dữ liệu:** Rodrigues et al., *Scientific Data*, 2021 —
  DOI [10.1038/s41597-021-00930-x](https://doi.org/10.1038/s41597-021-00930-x)

Mọi mục `§x.y` trong mã nguồn và tài liệu trỏ tới
`Delivery_UAV_Preflight_Feasibility_Proposal_updated.md` (file của thầy hướng dẫn).
Mọi `Eq (n)` trỏ tới `Proposal.docx` của nhóm.

---

## Nhóm và phân công

| Gói | Nội dung | Người chính | Người kiểm chéo | Tuần |
|---|---|---|---|---|
| WP1 | Dữ liệu và dựng lại năng lượng | Phát | Duy | 1–3 |
| WP2 | So sánh mô hình năng lượng | Phát | Duy | 4–6 |
| WP3 | Ngân sách pin và luật quyết định | Phát | Duy | 6–7 |
| WP4 | Kịch bản và độ bền vững | Phát → **Duy** (từ 23/10) | Duy → **Phát** | 8–10 |
| WP5 | Bản ghi, tích hợp và bài viết | Phát → **Duy** (từ 23/10) | Duy → **Phát** | 11–12 |

Nguyên tắc bắt buộc của thầy: **người làm một phần không được là người duy nhất
kiểm kết quả phần đó.**

> **Cập nhật 14/10/2026 — thay đổi phân công.** Quyền chuyển sang một project
> khác và không còn tham gia đề tài. Phát nhận WP3, WP4 và WP5; **Duy là người
> kiểm chéo cho toàn bộ phần còn lại**. Thay đổi này giữ nguyên nguyên tắc trên:
> không gói nào có người làm tự kiểm.

> **Cập nhật 20/10/2026.** Duy đã đọc `reports/parameter_table.md` và ký kiểm chéo
> WP3 — sản phẩm D3 nghiệm thu.

> **Cập nhật 21/10/2026.** Duy ký định nghĩa nhãn tham chiếu của sản phẩm D4
> (`configs/d4_protocol.yaml` mục `reference_label`), **trước** khi chạy so sánh.
> Mục 10 bắt buộc việc này phải có hai người xác nhận.

> **Cập nhật 23/10/2026 — bàn giao D5–D7.** Sản phẩm D4 xong, đạt 6/6 tiêu chí.
> Phát bàn giao **D5, D6, D7** cho Duy; phần nửa sau của WP4 (độ bền vững) và
> WP5 đổi người chính sang Duy. **Phát trở thành người kiểm chéo** cho ba sản
> phẩm này. Nguyên tắc Mục 10 được giữ nguyên, chỉ đổi vai.
>
> Lưu ý về D5: tiêu chí Mục 12.1 của D5 **rộng hơn Mục 12** và bao gồm cả
> *replayable immutable assessment snapshots* cùng các test stale/veto/missing/
> mitigation — xem `docs/san_pham/README.md`, phần cảnh báo về D5. Và
> **Definition of done của thầy là D1–D5**, nên D5 là sản phẩm khoá lại phần
> cốt lõi, còn D6/D7 nằm ngoài.

---

## Cài đặt

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Dữ liệu

`flights.csv` (~102 MB) **không** được commit vào repo. Tải từ KiltHub theo DOI ở
trên và đặt vào `data/raw/flights.csv`. `parameters.csv` đặt cùng chỗ.

```
data/
  raw/                  # KHÔNG commit — flights.csv, parameters.csv
  processed/            # KHÔNG commit — sinh lại được bằng script
```

Nguyên tắc: **sinh lại được thì không commit.** Áp dụng cho cả hai bảng kịch bản
lớn của sản phẩm D4 (`reports/d4_scenarios.csv` và
`reports/d4_scenarios_labelled.csv`) — chúng tái lập chính xác từ `seed: 42`
trong `configs/d4_protocol.yaml`, và `reports/d4_generator_check.csv` lưu hash
`fa81622c5d36884f` để đối chiếu. Hash và seed là bằng chứng tái lập, không phải
bản thân file CSV.

## Chạy

```bash
# 0. Xem flights.csv có những cột gì (chạy lần đầu, để đối chiếu configs/dataset.yaml)
python3 -m src.data_ingestion --inspect

# 1. Dựng lại năng lượng và đặc trưng cấp chuyến bay
python3 -m src.features --out data/processed/flight_level.csv

# 2. Đối chiếu với bảng đã có từ tuần 3
python3 -m src.features --verify reports/flight_level_week3.csv

# 3. Unit test — chạy TRƯỚC mọi benchmark (cổng chặn Mục 12.1 của D3)
pytest

# 4. Sản phẩm D2 — benchmark mô hình năng lượng (10–15 phút)
python3 -m src.evaluation_energy

# 5. Sản phẩm D2 — phân tích bổ sung (mỗi lệnh vài giây)
python3 -m src.subgroup_analysis
python3 -m src.interpretability
python3 -m src.bootstrap_ci
python3 -m src.figures

# 6. Sản phẩm D3 — bộ máy quyết định
python3 -m src.physics_m100          # tham số vật lý + reports/d3_landing_energy.csv
python3 -m src.safety_invariants --demo
python3 -m src.mitigations --demo
python3 -m src.decision_rules --demo
python3 -m src.evaluation_decision   # ~2 phút, sinh 4 CSV vào reports/

# 7. Sản phẩm D4 — benchmark kịch bản
python3 -m src.scenario_generator            # sinh 18.000 kịch bản
python3 scripts/compute_q95.py               # khoản dự phòng cho nhãn REF-1
python3 scripts/compute_ref2_calibration.py  # hệ số hiệu chỉnh nhãn REF-2
python3 -m src.reference_labeller            # gán đáp án cho 18.000 kịch bản
python3 -m src.evaluation_scenario           # chấm 7 phương pháp, sinh 8 CSV
```

Lệnh cuối **không được dùng `--nhanh`** cho bản cuối: cờ đó bỏ qua độ nhạy S-1
(pin TB48D), mà P§4.4 bắt buộc phải chạy. Chương trình in cảnh báo nếu thiếu.

Thứ tự mục 3 trước mục 4, 6 và 7 là **bắt buộc**, không phải thói quen: Mục 12.1
ghi *"Do not run the final decision benchmark until unit and rule tests pass"*.

---

## Tìm sản phẩm bàn giao ở đâu

**D5 đang phát triển:** [báo cáo tổng hợp và các bảng nhỏ](reports/d5/published/README.md).
Mã nguồn, protocol và kiểm thử D5 được giữ trong repo; dữ liệu lần chạy đầy đủ
được lưu riêng, không commit. Bản chia sẻ chưa thay xác nhận kiểm tra chéo hoặc nghiệm thu.

**`reports/deliverables.md`** — bảng tra từng mục D1–D9 của Mục 12 ứng với file
nào trong repo, kèm trạng thái nghiệm thu theo Mục 12.1.

Mở file đó trước khi tìm bất cứ output nào.

---

## ĐỌC TRƯỚC: hai hệ đánh số cùng dùng ký hiệu D

Thầy dùng **hai hệ đặt tên riêng biệt, trùng ký hiệu**. Mục 2.4 của file thầy nói
rõ: *"Các mã sản phẩm bàn giao là cột mốc dự án; các mã mô hình D0–D5 ở Mục 5 và 7
chỉ các thuật toán dự báo và là một hệ đặt tên riêng biệt."*

| Mã | **Sản phẩm bàn giao** (Mục 12) | **Mô hình** (Mục 5.2) |
|---|---|---|
| D0 | *(không có)* | Trung bình hằng |
| D1 | Rà soát bộ dữ liệu | Hồi quy chỉ cự ly |
| D2 | Benchmark dự báo năng lượng | Ridge regression |
| D3 | Bộ máy quyết định | Random Forest |
| D4 | Benchmark kịch bản | Gradient boosting (tuỳ chọn) |
| D5 | Gói độ bền vững | Mô hình vật lý Gong (có điều kiện) |

**Chỗ dễ nhầm nhất:** "sản phẩm D2" là cuộc so sánh các mô hình; "mô hình D2" là
Ridge. Câu *"sản phẩm D2 kết luận mô hình D2 thắng mô hình D3"* là đúng ngữ pháp
của dự án này.

Quy ước trong repo: luôn viết **"sản phẩm D2"** hoặc **"mô hình D2"**, không viết
"D2" trần. Trong mã nguồn, mô hình luôn mang tên đầy đủ (`D2_ridge_preflight`,
`D3_rf_preflight`) nên không nhầm được.

Nhóm **không đổi ký hiệu** của thầy, để mọi thứ đối chiếu được với file gốc.

Còn một hệ thứ ba nữa, chỉ dùng trong sản phẩm D4: **B0–B5** là các đường cơ sở
quyết định ở Mục 7. Không liên quan tới hai hệ trên. Và `B3…B10` trong
`configs/d3_protocol.yaml` cùng `C1…C26` trong `configs/d4_protocol.yaml` là mã
**quyết định thiết kế** — trùng chữ cái, khác hệ.

---

## Trạng thái sản phẩm bàn giao

| Mã | Tên | Người | Trạng thái |
|---|---|---|---|
| D1 | Rà soát bộ dữ liệu | Phát | **Nghiệm thu 14/10/2026** — đạt 8/8 tiêu chí |
| D2 | Benchmark dự báo năng lượng | Phát | **Nghiệm thu 14/10/2026** — đạt 4/4 tiêu chí |
| D3 | Bộ máy quyết định | Phát | **Nghiệm thu 20/10/2026** — đạt 13/13 tiêu chí, Duy đã kiểm chéo |
| D4 | Benchmark kịch bản | Phát | **XONG 23/10/2026** — đạt 6/6 tiêu chí, Duy ký nhãn tham chiếu 21/10 |
| D5 | [Gói độ bền vững](reports/d5/README.md) | **Duy** | Đã triển khai và có bằng chứng kỹ thuật; chờ Phát kiểm tra chéo, chưa nghiệm thu |
| D6 | [Bản ghi nhiệm vụ tái lập được](reports/d6/README.md) | **Duy** | Đã triển khai lược đồ và replay; bằng chứng kiểm thử tại báo cáo D6, chờ Phát kiểm tra chéo |
| D7 | Prototype | **Duy** | Tuỳ chọn — chỉ sau khi D5 nghiệm thu |

Tiến độ theo tab 11 của `NCKH.xlsx`: **xong tuần 1–9**.

### Sản phẩm D4 — sáu bước, xong cả sáu

| Bước | Việc | Trạng thái |
|---|---|---|
| 1 | Đóng băng `configs/d4_protocol.yaml` | xong — **v1.0.11**, 26 quyết định C1–C26 |
| 2 | `src/scenario_generator.py` — 18.000 kịch bản | xong — hash `fa81622c5d36884f`, GEN 5/5 |
| 3 | `src/reference_labeller.py` — hai nhãn REF-1 và REF-2 | xong — Duy ký 21/10 |
| 4 | `src/baselines_decision.py` — B0, B1, B2, B3, B5 | xong — 7 phương pháp |
| 5 | `src/evaluation_scenario.py` — chạy benchmark | xong — 8 CSV, 4 độ nhạy |
| 6 | `reports/scenario_benchmark_report.md` | xong |

**Kết quả chính:** duyệt bay kịch bản không khả thi giảm từ **95,3 %** (chỉ tiêu
cự ly) xuống **0,5 %** (phương pháp đề xuất, bỏ luật cứng). Thứ hạng bảy phương
pháp **giữ nguyên qua cả bốn phép quét độ nhạy**.

**Hai con số trong báo cáo D4 không được báo như nó hiện ra** (quyết định C26 —
giao thức bắt phát biểu nguyên văn trong bài). Đọc `reports/scenario_benchmark_report.md`
mục 5 và 6 trước khi trích bất cứ số nào của D4.

**Cổng chặn đã qua:**

- chưa đạt D1 thì không báo điểm mô hình — qua
- chưa đạt D2 thì không chốt mô hình năng lượng cho bộ máy quyết định — qua
- chưa pass unit test và rule test thì không chạy benchmark quyết định — qua
- không khẳng định đã kiểm chứng an toàn thực tế; nhãn dán `simulation-derived`;
  ghi ra rủi ro vòng tròn — qua, cả ba khai trong `configs/d4_protocol.yaml` và
  nêu ở mục 0 của báo cáo D4
- chưa đạt D1–D4 thì không chạy phân tích vùng biên (tuần 10) — **qua 23/10**

**Cổng chặn còn hiệu lực:** chưa đạt D1–D5 thì **không** làm phần tuỳ chọn
(Mục 2.4) — gradient boosting, SHAP, giao diện đẹp đều bị chặn. **Definition of
done của thầy là D1–D5**, nên D5 là sản phẩm khoá lại phần cốt lõi.

---

## Quy ước làm việc

1. Mọi hình trong bài sinh từ script trong `src/` hoặc `scripts/`, không vẽ tay.
2. Mọi bảng truy ngược được về một file trong `reports/`. Số **phụ thuộc phần
   cứng** (`inference_ms`) chỉ sống trong CSV; tài liệu chỉ được nói về tỉ lệ
   giữa các mô hình, không chép con số cụ thể.
3. Tập đặc trưng và thước đo đã **đóng băng** trong `configs/d2_protocol.yaml`;
   ngưỡng và luật cứng của bộ máy quyết định đóng băng trong
   `configs/d3_protocol.yaml`; dải kịch bản, nhãn tham chiếu và thước đo của
   benchmark kịch bản đóng băng trong `configs/d4_protocol.yaml`. Đổi thì phải
   ghi lý do vào mục `change_log` của chính file đó và chạy lại toàn bộ thí
   nghiệm bị ảnh hưởng.
4. Không tinh chỉnh siêu tham số bằng kết quả tập kiểm cuối.
5. **Không viết cứng danh sách bất biến ở bất cứ đâu.** Code và test phải đọc từ
   `configs/d3_protocol.yaml`. Lỗi lệch danh sách đã xảy ra ba lần và lần nào
   cũng im lặng — giao thức khai 8 bất biến, bảng bằng chứng in 7, không ai báo.
6. **Không chỉnh `a`, `b` hay `r` của sản phẩm D4** để thuộc đo đẹp hơn. Giao
   thức cấm (quyết định C26) — làm vậy là chọn tham số theo kết quả mong muốn.
7. **Chuẩn hoá `NaN` thành `None` ở mọi ranh giới dữ liệu mới** trước khi gọi
   lớp luật cứng. `NaN is None` là False và `NaN > 10.0` cũng là False, nên
   HR-1 từng báo PASS cho kịch bản gió không rõ. Xem `nan_sang_none()` trong
   `src/reference_labeller.py` và OI-D4-6.
