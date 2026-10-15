# Bảng tra sản phẩm bàn giao D1–D9

Ánh xạ từng mục trong **Mục 12** của file hướng dẫn sang file cụ thể trong repo,
kèm trạng thái nghiệm thu theo **Mục 12.1**.

Mở file này trước khi tìm bất cứ output nào.

**Cập nhật:** 15/10/2026 (bản 2, sau khi vá RS-1 và RS-2) · tiến độ: xong tuần 1–7

---

## Tổng quan

| Mã | Sản phẩm | Người | Tuần | Trạng thái |
|---|---|---|---|---|
| **D1** | Dataset audit package | Phát | 2–3 | **NGHIỆM THU** 14/10/2026 |
| **D2** | Energy prediction benchmark | Phát | 4–6 | **NGHIỆM THU** 14/10/2026 |
| **D3** | Safety-aware decision engine | Phát | 7 | **Đạt 13/13 tiêu chí — chờ Duy ký kiểm chéo** |
| D4 | Scenario benchmark | Phát | 8–9 | Chưa bắt đầu |
| D5 | Robustness package | Phát | 10–11 | Chưa bắt đầu |
| D6 | Reproducible mission record | Phát | 11 | Chưa bắt đầu |
| D7 | Prototype (tuỳ chọn) | Phát | 11 | Chưa bắt đầu |
| D8 | Research paper | Cả nhóm | 12 | Chưa bắt đầu |
| D9 | Reproducibility package | Cả nhóm | 12 | Chưa bắt đầu |

> **Phân công đổi 14/10/2026:** Quyền chuyển sang project khác. Phát nhận WP3,
> WP4, WP5; Duy kiểm chéo toàn bộ phần còn lại (giữ nguyên tắc Mục 10).

---

## Mục 12 đòi output gì — bảng tra nhanh

Nguyên văn Mục 12, và file nào trong repo đáp ứng:

| Mã | Thầy đòi (nguyên văn) | File trong repo |
|---|---|---|
| **D1** | data dictionary | `reports/data_dictionary.md` |
| | quality report | `reports/quality_report.md` |
| | exclusion log | `reports/exclusion_log.csv` |
| | processed flight-level table | `data/processed/flight_level.csv` |
| **D2** | code … for at least four predictors/baselines | `src/models.py` — 7 biến thể |
| | results … | `reports/d2_*.csv` — 9 bảng |
| | with leakage-resistant validation | `src/evaluation_energy.py` + `configs/d2_protocol.yaml` |
| **D3** | available-energy model | `src/available_energy.py` |
| | mission-energy budget | gọi `D2_ridge_preflight` |
| | reserve-margin calculation | `src/decision_rules.py` |
| | hard-rule layer | `src/safety_invariants.py` |
| | three-level verdict | `src/decision_rules.py` — 4 mức (3 + INSUFFICIENT-DATA) |

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
| `reports/d2_oof_residuals.csv` | Phần dư từng chuyến bay — nguyên liệu cho D3 và D5 |
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

`configs/d2_protocol.yaml` v1.4.0 — bản đóng băng tuần 2: tập đặc trưng, thước đo,
cách chia tập, danh sách biến cấm, nhật ký thay đổi.

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

**Đã làm. Đạt 13/13 tiêu chí Mục 12.1. Chờ chữ ký kiểm chéo của Duy (OI-D3-3).**

### Mã nguồn — năm module, sáu khối

| Khối | File | Nội dung |
|---|---|---|
| a. Năng lượng khả dụng | `src/available_energy.py` | `E_available = E_nominal × SoC × SoH × κ(T)` |
| b. Ngân sách nhiệm vụ | gọi `D2_ridge_preflight` | không huấn luyện lại |
| c. Biên dự trữ | `src/decision_rules.py` | `M` và `R` |
| d. Lớp luật cứng | `src/safety_invariants.py` | 6 luật, có quyền phủ quyết |
| e. Phán quyết | `src/decision_rules.py` | 4 mức |
| f. Dấu còn hạn, bản ghi | `src/workflow_state.py` | `MissionRecord`, stale, replay |
| g. Biện pháp giảm thiểu | `src/mitigations.py` | 7 biện pháp, 2 nhóm — bắt buộc cho CONDITIONAL |
| — | `src/evaluation_decision.py` | bộ chạy trên 192 chuyến |

### Kết quả

| File | Nội dung |
|---|---|
| `reports/d3_invariant_check.csv` | **7 bất biến × 2.326 trường hợp, 0 vi phạm** |
| `reports/d3_min_soc_per_flight.csv` | SoC tối thiểu từng chuyến, 3 mức hệ số dự trữ |
| `reports/d3_verdict_grid.csv` | Phân bố phán quyết trên lưới SoC × r |
| `reports/d3_scenario_sensitivity.csv` | Độ nhạy SoH × nhiệt độ × r |

### Báo cáo

| File | Nội dung |
|---|---|
| `reports/decision_engine_report.md` | **Báo cáo bàn giao** — sáu khối, kết quả, nghiệm thu, bàn giao sang D4 |

### Giao thức

`configs/d3_protocol.yaml` v1.2.0 — ngưỡng, luật, hồ sơ máy bay, quy ước cự ly,
biện pháp giảm thiểu, 7 bất biến, 12 điều cấm, nhật ký với 6 quyết định B3–B8.

### Tái lập

```bash
pytest                                  # 358 test
python3 -m src.mitigations --demo
python3 -m src.evaluation_decision      # ~25 giây, sinh 4 CSV
```

### Nghiệm thu theo Mục 12.1

Nguyên văn tiêu chí D3 của thầy, từng mục một:

| # | Tiêu chí (nguyên văn) | Trạng thái | Bằng chứng |
|---|---|---|---|
| 1 | Available-energy assumptions and sources documented | **Đạt** | `parameter_table.md` mục 1–2, `d3_protocol.yaml` mục 2 |
| 2 | **One-way versus round-trip distance explicit** | **Đạt** | quyết định B7 — đã vá 15/10 |
| 3 | Reserve thresholds fixed | **Đạt** | `d3_protocol.yaml` mục 5, quyết định B4 |
| 4 | Hard constraints tested to veto FLY | **Đạt** | INV-1, 576/576 |
| 5 | Invalid/stale safety-critical inputs fail closed | **Đạt** | INV-2 960/960, `workflow_state.py` |
| 6 | Hard-rule violations cannot be overridden | **Đạt** | luật cứng xét trước biên dự trữ; có test quét mọi mức `r` |
| 7 | Stale assessments are invalidated | **Đạt** | `check_freshness()`, 7 nguồn làm hết hạn |
| 8 | **Conditional verdicts require an explicit mitigation** | **Đạt** | quyết định B8, `src/mitigations.py`, INV-7 213/213 — đã vá 15/10 |
| 9 | Three verdicts have precise operational definitions | **Đạt** | điều kiện số trong giao thức + `actionable` định nghĩa rõ khi nào được tiến hành |

**Cổng chặn:** *"Do not run the final decision benchmark until unit and rule
tests pass"* — tuân thủ: 358 test pass trước khi chạy `evaluation_decision`.

### Kết quả chính

- **7 bất biến, 2.326 trường hợp, 0 vi phạm**
- **SoC tối thiểu để bay**: trung vị 26,5 %, p90 35,1 %, lớn nhất 42,0 % (r = 0,20)
- **187/192 chuyến đạt FLY; 5 chuyến kẹt vĩnh viễn ở CONDITIONAL** dù pin đầy —
  đúng 5 chuyến R6 ~835 m của thí nghiệm E2c, bị luật PD-1 chặn vì ngoài envelope

### Giải thích chi tiết

`docs/san_pham/D3_bo_may_quyet_dinh.md`

---

## RÀ SOÁT 15/10/2026 — hai thiếu sót, đã vá

Đối chiếu từng chữ bảng Mục 12.1 phát hiện hai tiêu chí chưa đáp ứng. Cả hai đều
**không phải lỗi code** — code chạy đúng điều đã thiết kế — mà là **thiếu một
phần thiết kế**. Cả hai đã vá trong cùng ngày; giữ lại mục này để truy vết.

### RS-1 — Chưa khai báo cự ly là một chiều hay khứ hồi · **ĐÃ VÁ (B7)**

Mục 12.1 đòi: *"one-way versus round-trip distance explicit"*. §4.3 cũng cảnh báo:
*"out-and-back mission distance is not the same as one-way distance"*.

Hiện `data_dictionary.md` chỉ ghi `distance_2d_m` là *"tổng đường đi trên mặt
đất"*, không nói rõ gì thêm. Không chỗ nào trong repo nêu vấn đề này.

**Tra bài gốc** — Rodrigues et al., *Scientific Data* 8, 155 (2021), mục Methods:

> *"tracks a triangular wind-neutral path while recording the data"* ·
> *"reaches the launch point again, the UAV stops and descends at approximately
> 1.5 m/s"*

Tức là **chuyến bay là vòng kín tam giác, quay về đúng điểm cất cánh**. Và tải
trọng **gắn bằng dây Velcro, mang suốt chuyến, không thả xuống** — bài không mô
tả cơ cấu thả hàng nào.

Ba hệ quả, theo mức độ nghiêm trọng:

1. **`distance_2d_m` ≈ 472 m là vòng kín, không phải cự ly giao hàng một chiều.**
   Một nhiệm vụ giao hàng thật "472 m tới khách" sẽ bay khoảng 944 m khứ hồi —
   **nằm ngoài envelope 420–610 m**. Nghĩa là envelope hiện tại tương ứng với
   **cự ly giao hàng một chiều khoảng 210–305 m**, không phải 420–610 m. Đây là
   cách diễn giải phải viết rõ, nếu không bài báo sẽ nói sai gấp đôi.

2. **Khối lượng không đổi suốt chuyến.** Giao hàng thật thì chặng về nhẹ hơn, nên
   mô hình sẽ **đoán thừa** năng lượng chặng về — lệch về phía an toàn, nhưng
   vẫn là sai lệch phải khai báo.

3. **Bộ dữ liệu không có khái niệm "điểm giao hàng".** Đây là đường bay thử theo
   vòng, không phải nhiệm vụ giao hàng. Phải nói thẳng trong phần hạn chế.

**Đã vá:** quy ước ghi vào `data_dictionary.md` (mục riêng, có trích nguyên văn),
`d3_protocol.yaml` (`inputs.distance_convention`), `parameter_table.md` mục 5 và
`decision_engine_report.md`. Envelope giờ nêu **cả hai cách đọc**. Không con số
nào trong CSV thay đổi.

### RS-2 — CONDITIONAL chưa đòi biện pháp giảm thiểu · **ĐÃ VÁ (B8)**

Mục 12.1 đòi: *"conditional verdicts require an explicit mitigation"*. Mục 2.3
nói rõ hơn:

> *"CONDITIONAL / DEGRADED is actionable only when an approved mitigation is
> selected and the scenario is re-evaluated where the mitigation changes energy
> demand or constraints."*

Hiện `decision_rules.py` trả về CONDITIONAL kèm một dòng lý do, và hết. Không có
danh sách biện pháp, không bắt chọn, không đánh giá lại.

Đúng chữ của thầy thì CONDITIONAL hiện **chưa dùng được** — nó mới là một nhãn,
chưa phải một trạng thái có đường ra.

**Đã vá:** thêm `src/mitigations.py` với 7 biện pháp chia hai nhóm.

| Nhóm | Biện pháp | Đổi cái gì |
|---|---|---|
| A | M1 sạc thêm pin · M2 đổi pin TB48D · M3 đợi gió giảm · M4 đợi trời ấm | năng lượng khả dụng hoặc ràng buộc |
| B | M5 giảm tải · M6 giảm tốc · M7 rút tuyến | **nhu cầu năng lượng** — bắt buộc dự báo lại |

`actionable = False` khi CONDITIONAL chưa có biện pháp; `may_proceed` của bản ghi
tôn trọng cờ này. Nhóm B nhận hàm dự báo truyền từ ngoài, nên D3 vẫn không import
mô hình (INV-6 còn hiệu lực); không có hàm dự báo thì nhóm B bị bỏ qua và **báo
rõ**, không im lặng.

Thêm **INV-7**: mọi biện pháp đề xuất đều được **chạy thử trước** khi hiện ra.
Trên 192 chuyến: 213 đề xuất, 0 cái vô dụng. Và biện pháp **không lật được
NO-FLY** — có test riêng xác nhận.

### RS-3 — Lệch tổng cự ly so với bài gốc *(cần kiểm, chưa kết luận)*

Bài Rodrigues ghi bộ dữ liệu phủ *"a total distance of approximately 65
kilometres"* cho 209 chuyến. Tổng `distance_2d_m` của 192 chuyến nhóm tính được
là **92,8 km** — cao hơn khoảng 43 %.

Hai khả năng, chưa phân biệt được:

- Bài tính cự ly theo tuyến danh nghĩa, nhóm tính theo quỹ đạo GPS thật
- Phép cộng haversine theo từng mẫu **cộng dồn cả nhiễu GPS lúc treo**, làm
  phồng cự ly

Khả năng thứ hai đáng lo hơn và kiểm được: so tổng quãng đường với khoảng cách
đường thẳng giữa các điểm mốc, hoặc lọc các bước nhỏ hơn ngưỡng nhiễu.

**Chưa kết luận gì.** Ghi lại để kiểm, vì nó ảnh hưởng tới cách đọc envelope ở
RS-1. Việc này **không chặn** D3.

---

## D4 — Scenario benchmark

> Mục 12: *"documented scenario ranges, fixed random seeds, reference-label policy,
> baseline implementations, and result tables"*

**Chưa bắt đầu.** Người làm: Phát, tuần 8–9.

Module dự kiến: `src/scenario_generator.py`

### Đã chuẩn bị sẵn

| Cần gì | Có ở đâu |
|---|---|
| Hàm quyết định | `src/decision_rules.py` → `assess()` |
| Quét hệ số dự trữ | `src/decision_rules.py` → `sweep_reserve()` |
| Bản ghi nhiệm vụ | `src/workflow_state.py` → `MissionRecord` |
| Dải tham số có dữ liệu đỡ lưng | `reports/parameter_table.md` mục 5 |
| Phân phối sai số cho nhãn tham chiếu | `reports/d2_oof_residuals.csv` |

### Ba điều bắt buộc

1. **Nhãn tham chiếu phải độc lập với mô hình đang đánh giá** (§4.7). Dùng chính
   D2 sinh nhãn rồi lại dùng D2 dự báo là vòng tròn. Lấy nhãn từ phân phối phần
   dư đo được cộng một khoản dự phòng bất định.
2. **SoH và nhiệt độ là ngoại suy thuần** — phải dán nhãn rõ (§6/E3).
3. **Chạy độ nhạy `E_nominal = 129,96 Wh`** — bắt buộc, §8 mục 3.

---

## D5 — Robustness package

> Mục 12: *"boundary analysis, threshold sweeps, uncertainty/sensitivity plots,
> and failure-case examples"*

**Chưa bắt đầu.** Người làm: Phát, tuần 10–11.

Module dự kiến: `src/uncertainty.py`

Nguyên liệu đã có: `reports/d2_oof_residuals.csv` — phân phối sai số out-of-fold
cho mô phỏng bất định (§5.8). Và `reports/d3_scenario_sensitivity.csv` đã là một
lát cắt độ nhạy sơ bộ.

---

## D6 — Reproducible mission record

> Mục 12: *"versioned schema and deterministic replay tests"*

**Chưa bắt đầu chính thức**, nhưng nền đã có: `src/workflow_state.py` →
`MissionRecord` với bảy trường phiên bản, và INV-5 (tính lại từ bản ghi) đã đạt
192/192. D6 sẽ mở rộng và kiểm đầy đủ.

Người làm: Phát, tuần 11.

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

### Nguyên liệu đã có

| Phần bài | Lấy từ |
|---|---|
| Mô tả bộ dữ liệu | `quality_report.md`, `data_dictionary.md` |
| Bảng kết quả chính | `d2_e2a_flight_level_cv.csv` |
| Hình 1–5 | `reports/figures/` |
| Lựa chọn mô hình | `model_selection_report.md` |
| Tham số và nguồn | `parameter_table.md` |
| Bộ máy quyết định | `decision_engine_report.md` |
| Bất biến | `d3_invariant_check.csv` |

### Hạn chế bắt buộc nêu — đã ghi nhận

1. Dữ liệu gần như không có biến thiên cự ly (94 % một tuyến) → mô hình D1 chỉ
   cự ly thoái hoá
2. Cỡ mẫu hiệu dụng gần 60 cấu hình hơn 192 chuyến
3. Cột vị trí ở đơn vị độ; `position_z` bài báo ghi sai đơn vị
4. Hai cách đo cự ly chênh 2,5 %
5. Bài báo tự mâu thuẫn về loại pin
6. Máy bay vượt khối lượng cất cánh tối đa nhà sản xuất (3.680–4.180 g vs 3.600 g)
7. κ(T) chỉ hợp lệ 4,5–18,4 °C, phần lớn dải vận hành phải giữ cận bảo thủ
8. Bộ dữ liệu không ghi nhiệt độ môi trường
9. Đa thức hiệu chỉnh gió không bao phủ 33,7 % dữ liệu của chính tác giả
10. Mô hình vật lý D5 chỉ dựng được một phần
11. **Chuyến bay là vòng kín quay về điểm cất cánh, tải mang suốt chuyến, không
    có điểm giao hàng** — bộ dữ liệu là đường bay thử, không phải nhiệm vụ giao
    hàng (RS-1)
12. **Quyết định chưa được chấm điểm** — bộ dữ liệu không có nhãn kết cục; việc
    đó thuộc D4 trên kịch bản tổng hợp, và nhãn phải gọi là *simulation-derived*
13. Gió đo được dùng thay gió dự báo khi chạy D3 trên 192 chuyến

---

## D9 — Reproducibility package

> Mục 12: *"scripts, configuration files, environment requirements, seeds, and
> instructions to regenerate tables/figures"*

**Chưa đóng gói chính thức**, nhưng các thành phần đã có:

| Thầy yêu cầu | Có ở đâu |
|---|---|
| Scripts | `src/` — 18 module |
| Configuration files | `configs/d2_protocol.yaml` v1.4.0, `d3_protocol.yaml` v1.2.0, `dataset.yaml` |
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

`docs/` viết giọng dẫn giải, có ví dụ, giải thích "vì sao" — để Duy đọc hiểu được
công việc. Nó không phải báo cáo nộp thầy.

---

## Việc còn treo

| Mã | Việc | Chặn gì |
|---|---|---|
| ~~RS-1~~ | ~~Khai báo cự ly một chiều / khứ hồi~~ | **đã vá 15/10 — B7** |
| ~~RS-2~~ | ~~CONDITIONAL phải đòi biện pháp giảm thiểu~~ | **đã vá 15/10 — B8** |
| RS-3 | Kiểm lệch tổng cự ly 92,8 km vs 65 km của bài gốc | không chặn, nhưng ảnh hưởng cách đọc envelope |
| OI-D3-1 | Tính SoC tối thiểu để hạ cánh an toàn từ độ cao hành trình | làm trước D4 |
| OI-D3-3 | Duy xác nhận vai kiểm chéo WP3 và ký nghiệm thu | nghiệm thu D3 |
| OI-4 | Báo thầy quyết định hai biến thể D2 | không chặn |
| OI-5 | `Draft Báo.docx` còn dùng thông số Matrice 210 | D8 |

**Thứ tự nên làm:** OI-D3-1 → nhờ Duy ký nghiệm thu D3 → D4. RS-3 làm lúc nào cũng được.
