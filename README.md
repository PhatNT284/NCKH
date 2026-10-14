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
| WP3 | Ngân sách pin và luật quyết định | Quyền | Phát | 6–7 |
| WP4 | Kịch bản và độ bền vững | Quyền | Duy | 8–10 |
| WP5 | Bản ghi, tích hợp và bài viết | Phát | Quyền | 11–12 |

Nguyên tắc bắt buộc của thầy: **người làm một phần không được là người duy nhất
kiểm kết quả phần đó.**

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

## Chạy

```bash
# 0. Xem flights.csv có những cột gì (chạy lần đầu, để đối chiếu configs/dataset.yaml)
python3 -m src.data_ingestion --inspect

# 1. Dựng lại năng lượng và đặc trưng cấp chuyến bay
python3 -m src.features --out data/processed/flight_level.csv

# 2. Đối chiếu với bảng đã có từ tuần 3
python3 -m src.features --verify reports/flight_level_week3.csv

# 3. Benchmark mô hình năng lượng (10–15 phút)
python3 -m src.evaluation_energy

# 4. Phân tích bổ sung (mỗi lệnh vài giây)
python3 -m src.subgroup_analysis
python3 -m src.interpretability
python3 -m src.bootstrap_ci
python3 -m src.figures

# 5. Unit test
pytest
```

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

---

## Trạng thái sản phẩm bàn giao

| Mã | Tên | Người | Trạng thái |
|---|---|---|---|
| D1 | Rà soát bộ dữ liệu | Phát | **Nghiệm thu 14/10/2026** |
| D2 | Benchmark dự báo năng lượng | Phát | **Nghiệm thu — đạt 4/4 tiêu chí** |
| D3 | Bộ máy quyết định | Quyền | Chưa bắt đầu — đọc `docs/san_pham/D2_benchmark_nang_luong.md` mục 8 trước |
| D4 | Benchmark kịch bản | Quyền | Chưa bắt đầu |
| D5 | Gói độ bền vững | Cả nhóm | Chưa bắt đầu |

Tiến độ theo tab 11 của `NCKH.xlsx`: **xong tuần 1–6**. Sản phẩm tuần 6:
`docs/cach_lam/D5_mo_hinh_vat_ly.md`, `reports/model_selection_report.md`,
`reports/parameter_table.md`.

**Cổng chặn:** chưa đạt D1 thì không báo điểm mô hình. Chưa đạt D2 thì không chốt
mô hình năng lượng cho bộ máy quyết định.

---

## Quy ước làm việc

1. Mọi hình trong bài sinh từ script trong `src/` hoặc `scripts/`, không vẽ tay.
2. Mọi bảng truy ngược được về một file trong `reports/`.
3. Tập đặc trưng và thước đo đã **đóng băng** trong `configs/d2_protocol.yaml`.
   Đổi thì phải ghi lý do vào mục `change_log` của chính file đó và chạy lại
   toàn bộ thí nghiệm bị ảnh hưởng.
4. Không tinh chỉnh siêu tham số bằng kết quả tập kiểm cuối.
