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

Từ sản phẩm D4 trở đi còn hệ thứ ba: **B0–B5** là các đường cơ sở quyết định ở
Mục 7. Viết đủ là "đường cơ sở B2", không viết "B2" trần, vì `B3…B10` trong
`configs/d3_protocol.yaml` lại là mã **quyết định thiết kế** — trùng chữ cái,
khác hệ. `configs/d4_protocol.yaml` dùng `C1…C26` cho cùng mục đích đó.

## Đọc gì trước

| Bạn muốn | Đọc |
|---|---|
| Hiểu tổng thể đã làm gì | `san_pham/README.md` |
| Hiểu một mô hình cụ thể | `cach_lam/README.md` rồi vào file tương ứng |
| Hiểu bộ máy quyết định đang chạy ra sao | `san_pham/D3_bo_may_quyet_dinh.md` |
| Hiểu benchmark kịch bản kết luận gì | `san_pham/D4_benchmark_kich_ban.md` |
| **Trích số của sản phẩm D4 vào bài** | `../reports/scenario_benchmark_report.md` **mục 5 và 6 trước đã** — có hai con số không được báo như nó hiện ra |
| **Duy — bắt đầu D5** | `san_pham/README.md`, phần cảnh báo về D5 |
| **Duy — kiểm chéo WP1** | `san_pham/D1_ra_soat_du_lieu.md` mục 8 và 9 |
| **Duy — kiểm chéo WP3** *(đã ký 20/10)* | `../reports/parameter_table.md` |
| **Duy — kiểm chéo nhãn tham chiếu D4** *(đã ký 21/10)* | `../configs/d4_protocol.yaml` mục `reference_label` |
| Gặp từ lạ | `thuat_ngu.md` |

## Quy ước tham chiếu

- **§x.y** → mục trong `Delivery_UAV_Preflight_Feasibility_Proposal_updated.md`
  (file thầy hướng dẫn gửi sau khi nhận xét)
- **P§x.y** → mục trong `Proposal.docx` (bản nhóm đã sửa) khi trích phần diễn giải
- **Eq (n)** → công thức đánh số trong `Proposal.docx`

Mọi quyết định kỹ thuật phải trỏ được về một trong hai nguồn trên. Nếu không có
chỗ dựa, phải khai báo rõ là **bổ sung ngoài giao thức** — hiện có đúng một trường
hợp, là thí nghiệm E2c.

Một chú ý riêng về luật cứng của sản phẩm D3: **nguồn gốc và mức độ là hai trục
độc lập**, nên có ba họ mã, không được trộn khi trích dẫn.

| Mã | Nguồn | Mức độ |
|---|---|---|
| `HR-1…HR-4` | DJI công bố | VETO |
| `PH-1` | nguyên tắc P§4.6 + mô hình vật lý của nhóm | VETO |
| `PD-1, PD-2` | thí nghiệm của nhóm | DOWNGRADE |

Tiền tố `HR-` dành riêng cho số nhà sản xuất công bố, và có test canh quy ước đó
(`tests/test_safety_invariants.py::test_moi_luat_hr_co_ghi_nguon`).

## Chạy lại toàn bộ

```bash
source .venv/bin/activate
pytest                     # toàn bộ test — chạy TRƯỚC mọi benchmark
python3 -m src.features --verify reports/flight_level_week3.csv

# sản phẩm D2
python3 -m src.evaluation_energy                    # 10–15 phút
python3 -m src.subgroup_analysis
python3 -m src.interpretability
python3 -m src.bootstrap_ci
python3 -m src.figures
python3 -m src.experiment_log

# sản phẩm D3
python3 -m src.physics_m100
python3 -m src.safety_invariants --demo
python3 -m src.mitigations --demo
python3 -m src.decision_rules --demo
python3 -m src.evaluation_decision                  # ~2 phút

# sản phẩm D4
python3 -m src.scenario_generator            # 18.000 kịch bản
python3 scripts/compute_q95.py               # khoản dự phòng nhãn REF-1
python3 scripts/compute_ref2_calibration.py  # hệ số hiệu chỉnh nhãn REF-2
python3 -m src.reference_labeller            # gán đáp án
python3 -m src.evaluation_scenario           # chấm 7 phương pháp, sinh 8 CSV
```

Lệnh cuối **không được dùng `--nhanh`** cho bản cuối: cờ đó bỏ qua độ nhạy S-1
(pin TB48D 129,96 Wh), mà P§4.4 bắt buộc phải chạy vì bài gốc tự mâu thuẫn về
loại pin. Chương trình in cảnh báo nếu thiếu.

`pytest` đứng đầu không phải vì tiện: Mục 12.1 của sản phẩm D3 ghi *"Do not run
the final decision benchmark until unit and rule tests pass"*.

> **Quy ước:** tài liệu **không ghi số lượng test**. Con số đó lạc hậu sau mỗi
> lần thêm test, và đã sai ba lần. Cùng cách đã dùng để chữa lỗi danh sách bất
> biến: bỏ chỗ viết cứng chứ không sửa từng chỗ.
