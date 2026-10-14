# Bảng tra sản phẩm bàn giao D1–D9

Ánh xạ từng mục trong **Mục 12** của file hướng dẫn sang file cụ thể trong repo,
kèm trạng thái nghiệm thu theo **Mục 12.1**.

Mở file này trước khi tìm bất cứ output nào.

**Cập nhật:** 14/10/2026 · tiến độ: xong tuần 1–6 theo tab 11 của `NCKH.xlsx`

---

## Tổng quan

| Mã | Sản phẩm | Người | Tuần | Trạng thái |
|---|---|---|---|---|
| **D1** | Dataset audit package | Phát | 2–3 | **NGHIỆM THU** 14/10/2026 |
| **D2** | Energy prediction benchmark | Phát | 4–6 | **NGHIỆM THU** 14/10/2026 |
| D3 | Safety-aware decision engine | Quyền | 7 | Chưa bắt đầu |
| D4 | Scenario benchmark | Quyền | 8–9 | Chưa bắt đầu |
| D5 | Robustness package | Cả nhóm | 10–11 | Chưa bắt đầu |
| D6 | Reproducible mission record | Phát | 11 | Chưa bắt đầu |
| D7 | Prototype (tuỳ chọn) | Phát | 11 | Chưa bắt đầu |
| D8 | Research paper | Cả nhóm | 12 | Chưa bắt đầu |
| D9 | Reproducibility package | Cả nhóm | 12 | Chưa bắt đầu |

---

## D1 — Dataset audit package

> Mục 12: *"data dictionary, quality report, exclusion log, processed flight-level
> table"*

### Thành phần

| Thầy yêu cầu | File | Nội dung |
|---|---|---|
| Data dictionary | `reports/data_dictionary.md` | 23 cột, đơn vị, dải giá trị, nguồn, cột nào dùng được |
| Quality report | `reports/quality_report.md` | Nguồn, giấy phép, 192/209 chuyến, độ phủ lưới, ba lỗi phát hiện |
| Exclusion log | `reports/exclusion_log.csv` | 17 chuyến bị loại, từng chuyến một lý do |
| Processed flight-level table | `data/processed/flight_level.csv` | 192 dòng × 23 cột — **không commit** (sinh lại bằng script) |

### Mã nguồn sinh ra sản phẩm

| File | Vai trò |
|---|---|
| `src/data_ingestion.py` | Đọc và kiểm tra dữ liệu gốc |
| `src/energy_reconstruction.py` | Tích phân `E = Σ V·I·Δt` |
| `src/features.py` | Trích đặc trưng cấp chuyến bay, áp quy tắc loại trừ |
| `tests/test_energy_reconstruction.py` | 20 unit test cho phép tích phân |
| `tests/test_features.py` | 36 unit test cho đặc trưng và giao thức |

### Tái lập

```bash
python3 -m src.features --out data/processed/flight_level.csv
python3 -m src.features --verify reports/flight_level_week3.csv
```

Lệnh thứ hai đối chiếu với bảng tuần 3 — **cả 8 cột khớp tới 10⁻⁸**.

### Nghiệm thu theo Mục 12.1

| Tiêu chí | Trạng thái | Bằng chứng |
|---|---|---|
| Ghi rõ nguồn và giấy phép | Đạt | `quality_report.md` — DOI 10.1184/R1/12683453, CC BY 4.0 |
| Kiểm từ điển biến và đơn vị | Đạt | `data_dictionary.md` |
| Ghi nhật ký loại trừ chuyến bay | Đạt | `exclusion_log.csv`, 17 dòng |
| Test phép tích phân điện áp–dòng điện | Đạt | 20 unit test |
| Mọi dòng giữ định danh chuyến bay | Đạt | cột `flight` xuyên suốt |
| Chia tập theo chuyến bay hoặc cấu hình | Đạt | `configs/d2_protocol.yaml` → `partitioning` |
| Script xử lý chạy lại được (Mục 9) | Đạt | `--verify` khớp 10⁻⁸ |
| Kiểm chéo (Mục 10) | Đạt | Duy xác nhận 14/10/2026 |

**Cổng chặn đã mở:** *"chưa đạt D1 thì không báo điểm mô hình"*.

### Giải thích chi tiết

`docs/san_pham/D1_ra_soat_du_lieu.md` — viết cho người trong nhóm, không phải
sản phẩm bàn giao.

---

## D2 — Energy prediction benchmark

> Mục 12: *"code and results for at least four predictors/baselines, with
> leakage-resistant validation"*

### Mã nguồn

| File | Vai trò |
|---|---|
| `src/models.py` | Định nghĩa 7 biến thể mô hình D0–D3 |
| `src/evaluation_energy.py` | Ba thí nghiệm E2a, E2b, E2c; chống rò rỉ |
| `src/subgroup_analysis.py` | Sai số theo nhóm |
| `src/bootstrap_ci.py` | Khoảng tin cậy ở cấp chuyến bay |
| `src/interpretability.py` | Hệ số hồi quy và độ quan trọng đặc trưng |
| `src/figures.py` | Sinh 5 hình |
| `src/physics_m100.py` | Tham số hoá mô hình vật lý D5 |
| `src/experiment_log.py` | Nhật ký lần chạy |

### Kết quả

| File | Nội dung |
|---|---|
| `reports/d2_e2a_flight_level_cv.csv` | **Bảng chính** — 7 mô hình × MAE, RMSE, bias, WAPE, inference_ms |
| `reports/d2_e2b_configuration_holdout.csv` | Giữ lại cấu hình |
| `reports/d2_e2c_distance_holdout.csv` | Ngoại suy cự ly (thí nghiệm bổ sung) |
| `reports/d2_oof_residuals.csv` | Phần dư từng chuyến bay — nguyên liệu cho D5 |
| `reports/d2_subgroup_errors.csv` | 18 nhóm × 5 chiều |
| `reports/d2_bootstrap_mae_ci.csv` | MAE kèm khoảng tin cậy 95 % |
| `reports/d2_bootstrap_differences.csv` | Chênh lệch giữa các mô hình |
| `reports/d2_ridge_coefficients.csv` | Hệ số Ridge |
| `reports/d3_feature_importance.csv` | Độ quan trọng đặc trưng Random Forest |
| `reports/d5_hover_validation.csv` | Kiểm chứng tham số hoá mô hình vật lý |
| `reports/figures/fig1…fig5.png` | 5 hình, PNG 300 dpi |
| `reports/experiment_log.jsonl` | Lịch sử các lần chạy |

### Báo cáo

| File | Nội dung |
|---|---|
| `reports/model_selection_report.md` | **Báo cáo chốt mô hình** — vì sao chọn Ridge, 4 tiêu chí, bàn giao sang D3 |
| `reports/parameter_table.md` | Tham số cho `E_available` và lớp luật cứng, kèm nguồn |

### Giao thức

`configs/d2_protocol.yaml` — bản đóng băng tuần 2: tập đặc trưng, thước đo, cách
chia tập, danh sách biến cấm, nhật ký thay đổi.

### Tái lập

```bash
python3 -m src.evaluation_energy        # 10–15 phút
python3 -m src.subgroup_analysis
python3 -m src.interpretability
python3 -m src.bootstrap_ci
python3 -m src.figures
python3 -m src.physics_m100
```

### Nghiệm thu theo Mục 12.1

| Tiêu chí | Trạng thái | Bằng chứng |
|---|---|---|
| Ít nhất 4 mô hình: trung bình hằng, chỉ cự ly, ridge, random forest | Đạt | 7 biến thể trong `d2_e2a_flight_level_cv.csv` |
| Cùng mục tiêu và cùng phân vùng | Đạt | Cùng `energy_Wh`, cùng fold, seed 42 |
| Báo MAE, RMSE, sai số có dấu, sai số theo nhóm | Đạt | `d2_e2a_*.csv` + `d2_subgroup_errors.csv` |
| Không rò rỉ sang tập kiểm | Đạt | Chia theo chuyến bay, CV lồng, `assert_no_leakage`, 14 test giao thức |

**Cổng chặn:** *"chỉ chọn mô hình năng lượng sau khi xem kết quả kiểm định"* —
tuân thủ, xem `model_selection_report.md` mục 1.

### Kết quả chính

**Mô hình được chọn: `D2_ridge_preflight`** — MAE 0,657 Wh (3,09 %), khoảng tin
cậy 95 % [0,582 ; 0,729].

Giới hạn sử dụng: **envelope cự ly 420–610 m**. Ngoài dải này mô hình đoán thiếu
có hệ thống.

### Giải thích chi tiết

`docs/san_pham/D2_benchmark_nang_luong.md` và thư mục `docs/cach_lam/`.

---

## D3 — Safety-aware decision engine

> Mục 12: *"available-energy model, mission-energy budget, reserve-margin
> calculation, hard-rule layer, three-level verdict"*

**Chưa bắt đầu.** Người làm: Quyền, tuần 7.

### Đã chuẩn bị sẵn

| Cần gì | Có ở đâu |
|---|---|
| Mô hình ước lượng `E_required` | `D2_ridge_preflight`, xem `model_selection_report.md` |
| Tham số cho `E_available` | `reports/parameter_table.md` mục 1 |
| Tham số lớp luật cứng | `reports/parameter_table.md` mục 3 |
| Giới hạn sử dụng mô hình | `model_selection_report.md` mục 8 |

### Ba điều phải mang theo

1. `E_nominal = 99,9 Wh` là **giá trị bảo thủ đã chốt**, không phải chắc chắn —
   bắt buộc chạy độ nhạy với 129,96 Wh ở D4
2. **Không dùng luật `tải trọng ≤ 1.245 g`** — máy bay trong bộ dữ liệu vượt khối
   lượng cất cánh tối đa, xem `parameter_table.md` mục 3.1. Dải hợp lệ: 0–500 g
3. **Envelope cự ly 420–610 m**

### Module dự kiến (Mục 9)

`src/available_energy.py` · `src/decision_rules.py` · `src/workflow_state.py` ·
`src/safety_invariants.py`

---

## D4 — Scenario benchmark

> Mục 12: *"documented scenario ranges, fixed random seeds, reference-label policy,
> baseline implementations, and result tables"*

**Chưa bắt đầu.** Người làm: Quyền, tuần 8–9.

Module dự kiến: `src/scenario_generator.py`

Ràng buộc đã biết: bảng độ phủ dữ liệu so với giới hạn vận hành ở
`parameter_table.md` mục 5 — cho biết dải nào có dữ liệu đỡ lưng, dải nào là
ngoại suy phải đánh dấu.

---

## D5 — Robustness package

> Mục 12: *"boundary analysis, threshold sweeps, uncertainty/sensitivity plots,
> and failure-case examples"*

**Chưa bắt đầu.** Người làm: cả nhóm, tuần 10–11.

Module dự kiến: `src/uncertainty.py`

Nguyên liệu đã có: `reports/d2_oof_residuals.csv` — phân phối sai số out-of-fold
cho mô phỏng bất định (§5.8).

---

## D6 — Reproducible mission record

> Mục 12: *"versioned schema and deterministic replay tests"*

**Chưa bắt đầu.** Người làm: Phát, tuần 11.

Module dự kiến: `src/mission_record.py`

---

## D7 — Prototype

> Mục 12: *"optional lightweight interface for mission inputs, energy margin,
> verdict, hard-rule status, and explanations"*

**Tuỳ chọn.** Mục 2.4: chỉ làm sau khi D1–D5 nghiệm thu xong.

---

## D8 — Research paper

> Mục 12: *"complete methods, dataset limitations, baseline definitions,
> quantitative results, and a cautious novelty claim"*

**Chưa bắt đầu.** Cả nhóm, tuần 12.

### Nguyên liệu đã có từ D1 và D2

| Phần bài | Lấy từ |
|---|---|
| Mô tả bộ dữ liệu | `quality_report.md`, `data_dictionary.md` |
| Bảng kết quả chính | `d2_e2a_flight_level_cv.csv` |
| Hình 1–5 | `reports/figures/` |
| Lựa chọn mô hình | `model_selection_report.md` |
| Tham số và nguồn | `parameter_table.md` |

### Hạn chế bắt buộc nêu — đã ghi nhận

1. Dữ liệu gần như không có biến thiên cự ly (94 % một tuyến) → D1 chỉ cự ly thoái hoá
2. Cỡ mẫu hiệu dụng gần 60 cấu hình hơn 192 chuyến
3. Cột vị trí ở đơn vị độ; `position_z` bài báo ghi sai đơn vị
4. Hai cách đo cự ly chênh 2,5 %
5. Bài báo tự mâu thuẫn về loại pin
6. Máy bay vượt khối lượng cất cánh tối đa nhà sản xuất
7. κ(T) chỉ hợp lệ 4,5–18,4 °C, phần lớn dải vận hành phải giữ cận bảo thủ
8. Bộ dữ liệu không ghi nhiệt độ môi trường
9. Đa thức hiệu chỉnh gió không bao phủ 33,7 % dữ liệu của chính tác giả
10. Mô hình vật lý D5 chỉ dựng được một phần

---

## D9 — Reproducibility package

> Mục 12: *"scripts, configuration files, environment requirements, seeds, and
> instructions to regenerate tables/figures"*

**Chưa đóng gói chính thức**, nhưng các thành phần đã có:

| Thầy yêu cầu | Có ở đâu |
|---|---|
| Scripts | `src/` — 12 module |
| Configuration files | `configs/d2_protocol.yaml`, `configs/dataset.yaml` |
| Environment requirements | `requirements.txt` |
| Seeds | `d2_protocol.yaml` → `partitioning.cv.random_state: 42` |
| Instructions to regenerate | `README.md` và `docs/README.md` |
| Lịch sử chạy | `reports/experiment_log.jsonl` |

Giấy phép bộ dữ liệu CC BY 4.0 cho phép công bố bảng dữ liệu đã xử lý kèm mã
nguồn, với điều kiện ghi công Rodrigues et al. (2021) và DOI bộ dữ liệu.

---

## Hai thư mục, hai vai trò

Dễ nhầm, nên ghi rõ:

| Thư mục | Là gì | Thầy có yêu cầu không |
|---|---|---|
| `reports/`, `src/`, `configs/`, `data/` | **Sản phẩm bàn giao** theo Mục 12 | Có |
| `docs/` | Bài giải thích cho người trong nhóm | Không — nhóm tự thêm |

`docs/` viết giọng dẫn giải, có ví dụ, giải thích "vì sao" — để Duy và Quyền đọc
hiểu được công việc của nhau. Nó không phải báo cáo nộp thầy.

---

## Việc còn treo

Xem `configs/d2_protocol.yaml` mục `open_items`. Hiện còn:

| Mã | Việc | Người |
|---|---|---|
| OI-4 | Báo thầy về quyết định chạy hai biến thể D2 | Phát |
| OI-5 | `Draft Báo.docx` còn dùng thông số Matrice 210, phải viết lại | Cả nhóm |

Cả hai không chặn công việc nào.
