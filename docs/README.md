# Tài liệu giải thích — đọc cái này trước

Thư mục này giải thích **đã làm gì, làm thế nào, và vì sao**. Viết cho người trong
nhóm chưa theo dõi quá trình, nên không giả định bạn đã biết gì về code hay
thống kê.

> **Lưu ý:** thư mục `docs/` là bài giải thích, **không phải sản phẩm bàn giao**.
> Sản phẩm thật ở `reports/`, `src/`, `configs/`, `data/` — bảng tra đầy đủ ở
> `../reports/deliverables.md`.

## Hai thư mục, bám hai mục khác nhau của thầy

Thầy dùng **hai hệ đánh số riêng biệt, trùng ký hiệu D**. Mục 2.4 nói rõ: *"Các mã
sản phẩm bàn giao là cột mốc dự án; các mã mô hình D0–D5 ở Mục 5 và 7 chỉ các
thuật toán dự báo và là một hệ đặt tên riêng biệt."*

Nên tài liệu cũng chia làm hai:

| Thư mục | Bám mục nào của thầy | Nội dung |
|---|---|---|
| **`cach_lam/`** | §5.2, §5.3, §4.3, §8 | Từng **mô hình** dự báo năng lượng |
| **`san_pham/`** | Mục 12, 12.1, 2.4, 10, 11 | Từng **sản phẩm bàn giao** |

### Bảng đối chiếu hai hệ

| Mã | **Sản phẩm bàn giao** (Mục 12) | **Mô hình** (§5.2) |
|---|---|---|
| D0 | *(không có)* | Trung bình hằng |
| D1 | Rà soát bộ dữ liệu | Hồi quy chỉ cự ly |
| D2 | Benchmark dự báo năng lượng | Ridge regression |
| D3 | Bộ máy quyết định | Random Forest |
| D4 | Benchmark kịch bản | Gradient boosting |
| D5 | Gói độ bền vững | Mô hình vật lý Gong |

**Chỗ dễ nhầm nhất:** "sản phẩm D2" là cuộc so sánh các mô hình; "mô hình D2" là
Ridge. Câu *"sản phẩm D2 kết luận mô hình D2 thắng mô hình D3"* là đúng.

Quy ước: luôn viết **"sản phẩm D2"** hoặc **"mô hình D2"**, không viết "D2" trần.
Trong mã nguồn thì mô hình luôn mang tên đầy đủ (`D2_ridge_preflight`,
`D3_rf_preflight`) nên không nhầm được.

## Đọc gì trước

| Bạn muốn | Đọc |
|---|---|
| Hiểu tổng thể đã làm gì | `san_pham/README.md` |
| Hiểu một mô hình cụ thể | `cach_lam/README.md` rồi vào file tương ứng |
| **Duy — kiểm chéo WP1** | `san_pham/D1_ra_soat_du_lieu.md` mục 8 và 9 |
| **Quyền — trước khi làm sản phẩm D3** | `san_pham/D2_benchmark_nang_luong.md` mục 8 |
| Gặp từ lạ | `thuat_ngu.md` |

## Quy ước tham chiếu

- **§x.y** → mục trong `Delivery_UAV_Preflight_Feasibility_Proposal_updated.md`
  (file thầy hướng dẫn gửi sau khi nhận xét)
- **Eq (n)** → công thức đánh số trong `Proposal.docx` (bản nhóm đã sửa)

Mọi quyết định kỹ thuật phải trỏ được về một trong hai nguồn trên. Nếu không có
chỗ dựa, phải khai báo rõ là **bổ sung ngoài giao thức** — hiện có đúng một trường
hợp, là thí nghiệm E2c.

## Chạy lại toàn bộ

```bash
source .venv/bin/activate
pytest                                              # 56 test
python3 -m src.features --verify reports/flight_level_week3.csv
python3 -m src.evaluation_energy                    # 10–15 phút
python3 -m src.subgroup_analysis
python3 -m src.interpretability
python3 -m src.bootstrap_ci
python3 -m src.figures
python3 -m src.experiment_log
```
