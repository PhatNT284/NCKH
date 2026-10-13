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
python -m src.data_ingestion --inspect

# 1. Dựng lại năng lượng và đặc trưng cấp chuyến bay
python -m src.features --out data/processed/flight_level.csv

# 2. Đối chiếu với bảng đã có từ tuần 3
python -m src.features --verify reports/flight_level_week3.csv

# 3. Unit test
pytest -q
```

---

## Trạng thái sản phẩm bàn giao

| Mã | Tên | Trạng thái |
|---|---|---|
| D1 | Rà soát bộ dữ liệu | Đang hoàn thiện — còn giấy phép và test tái lập |
| D2 | Benchmark dự báo năng lượng | Chưa bắt đầu |
| D3 | Bộ máy quyết định | Chưa bắt đầu |
| D4 | Benchmark kịch bản | Chưa bắt đầu |
| D5 | Gói độ bền vững | Chưa bắt đầu |

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
