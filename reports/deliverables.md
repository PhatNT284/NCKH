# Bảng tra sản phẩm bàn giao D1–D9

Ánh xạ từng mục trong **Mục 12** của file hướng dẫn sang file cụ thể trong repo,
kèm trạng thái nghiệm thu theo **Mục 12.1**.

Mở file này trước khi tìm bất cứ output nào.

**Cập nhật:** 23/10/2026 (bản 4, sau khi hoàn thành D4) · tiến độ: xong tuần 1–9

---

## Tổng quan

| Mã | Sản phẩm | Người | Tuần | Trạng thái |
|---|---|---|---|---|
| **D1** | Dataset audit package | Phát | 2–3 | **NGHIỆM THU** 14/10/2026 |
| **D2** | Energy prediction benchmark | Phát | 4–6 | **NGHIỆM THU** 14/10/2026 |
| **D3** | Safety-aware decision engine | Phát | 7 | **NGHIỆM THU** 20/10/2026 — 13/13 tiêu chí, Duy đã kiểm chéo |
| **D4** | Scenario benchmark | Phát | 8–9 | **XONG 23/10/2026** — 6/6 tiêu chí, Duy ký nhãn tham chiếu 21/10 |
| D5 | Robustness package | Phát | 10–11 | Chưa bắt đầu — **cổng chặn đã mở** |
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
| **D4** | documented scenario ranges | `configs/d4_protocol.yaml` §`scenario_generator` |
| | fixed random seeds | seed 42, hash bộ kịch bản `fa81622c5d36884f` |
| | reference-label policy | `configs/d4_protocol.yaml` §`reference_label` — Duy ký 21/10 |
| | baseline implementations | `src/baselines_decision.py` — 7 phương pháp |
| | result tables | `reports/d4_*.csv` — 8 bảng |

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
| `src/physics_m100.py` | Tham số hoá mô hình vật lý D5; từ 20/10 cũng cung cấp `landing_energy_Wh()` cho luật `PH-1` của D3 |
| `src/experiment_log.py` | Nhật ký lần chạy |

### Kết quả

| File | Nội dung |
|---|---|
| `reports/d2_e2a_flight_level_cv.csv` | **Bảng chính** — 7 mô hình × MAE, RMSE, bias, WAPE, inference_ms |
| `reports/d2_e2b_configuration_holdout.csv` | Giữ lại cấu hình |
| `reports/d2_e2c_distance_holdout.csv` | Ngoại suy cự ly (thí nghiệm bổ sung) |
| `reports/d2_oof_residuals.csv` | Phần dư từng chuyến bay — nguyên liệu cho D3, D4 và D5 |
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
| `reports/parameter_table.md` | Tham số cho `E_available`, lớp luật cứng và sàn hạ cánh `PH-1`, kèm nguồn |

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

**NGHIỆM THU 20/10/2026. Đạt 13/13 tiêu chí Mục 12.1. Duy đã kiểm chéo.**

### Mã nguồn — bảy module, bảy khối

| Khối | File | Nội dung |
|---|---|---|
| a. Năng lượng khả dụng | `src/available_energy.py` | `E_available = E_nominal × SoC × SoH × κ(T)` |
| b. Ngân sách nhiệm vụ | gọi `D2_ridge_preflight` | không huấn luyện lại; 4 quy ước §4.5 khai ở giao thức |
| c. Biên dự trữ | `src/decision_rules.py` | `M` và `R` |
| d. Lớp luật cứng | `src/safety_invariants.py` | **7 luật, 3 họ mã** — xem dưới |
| e. Phán quyết | `src/decision_rules.py` | 4 mức |
| f. Dấu còn hạn, bản ghi | `src/workflow_state.py` | `MissionRecord`, stale, replay |
| g. Biện pháp giảm thiểu | `src/mitigations.py` | 7 biện pháp, 2 nhóm — bắt buộc cho CONDITIONAL |
| — | `src/physics_m100.py` | `landing_energy_Wh()` cho luật `PH-1` |
| — | `src/evaluation_decision.py` | bộ chạy trên 192 chuyến |

### Ba họ mã luật cứng — không được trộn khi trích dẫn

| Mã | Nguồn | Mức độ |
|---|---|---|
| `HR-1…HR-4` | DJI công bố | VETO |
| `PH-1` | nguyên tắc P§4.6 + mô hình vật lý của **nhóm** | **VETO** |
| `PD-1, PD-2` | thí nghiệm E2c và độ phủ dữ liệu của **nhóm** | DOWNGRADE |

Nguồn gốc và mức độ là **hai trục độc lập**. `PH-1` nghiêm như luật DJI nhưng con
số là của nhóm, nên mang mã riêng — không phải `HR-5`. Có test canh quy ước đó.

### Kết quả

| File | Nội dung |
|---|---|
| `reports/d3_invariant_check.csv` | **8 bất biến × 3.094 trường hợp, 0 vi phạm** |
| `reports/d3_min_soc_per_flight.csv` | SoC tối thiểu từng chuyến, 3 mức hệ số dự trữ, kèm ngưỡng `PH-1` |
| `reports/d3_verdict_grid.csv` | Phân bố phán quyết trên lưới SoC × r, kèm cột `ph1_violated` |
| `reports/d3_scenario_sensitivity.csv` | Độ nhạy SoH × nhiệt độ × r |
| `reports/d3_landing_energy.csv` | Năng lượng hạ cánh — bảng tham số của `PH-1`, 24 dòng |

### Báo cáo

| File | Nội dung |
|---|---|
| `reports/decision_engine_report.md` | **Báo cáo bàn giao** — bảy khối, kết quả, nghiệm thu, bàn giao sang D4 |

### Giao thức

`configs/d3_protocol.yaml` v1.4.0 — ngưỡng, 7 luật cứng (3 họ mã), hồ sơ máy bay,
quy ước cự ly, 4 quy ước ngân sách năng lượng, biện pháp giảm thiểu, 8 bất biến,
13 điều cấm, nhật ký với 10 quyết định B3–B10.

### Tái lập

```bash
pytest                                  # ~403 test
python3 -m src.physics_m100             # sinh d3_landing_energy.csv
python3 -m src.mitigations --demo
python3 -m src.safety_invariants --demo
python3 -m src.decision_rules --demo
python3 -m src.evaluation_decision      # ~2 phut, sinh 4 CSV
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
| 6 | Hard-rule violations cannot be overridden | **Đạt** | luật cứng xét trước biên dự trữ; INV-8 kiểm cả chiều biện pháp |
| 7 | Stale assessments are invalidated | **Đạt** | `check_freshness()`, 7 nguồn làm hết hạn |
| 8 | **Conditional verdicts require an explicit mitigation** | **Đạt** | quyết định B8, `src/mitigations.py`, INV-7 213/213 — đã vá 15/10 |
| 9 | Three verdicts have precise operational definitions | **Đạt** | điều kiện số trong giao thức + `actionable` định nghĩa rõ khi nào được tiến hành |

**Cổng chặn:** *"Do not run the final decision benchmark until unit and rule
tests pass"* — tuân thủ: toàn bộ test pass trước khi chạy `evaluation_decision`.

**Ngoài 13 tiêu chí**, hệ thống còn cài thêm hai thứ theo thiết kế đã cam kết
trong Proposal, không phải vá tiêu chí thiếu:

- **4 quy ước ngân sách năng lượng** theo P§4.5 (quyết định B9) — chống đếm hai lần
- **Luật `PH-1`** theo P§4.6 (quyết định B10) — sàn năng lượng hạ cánh

### Kết quả chính

- **8 bất biến, 3.094 trường hợp, 0 vi phạm**
- **SoC tối thiểu để bay**: trung vị 26,5 %, p90 35,1 %, lớn nhất 42,0 % (r = 0,20)
- **187/192 chuyến đạt FLY; 5 chuyến kẹt vĩnh viễn ở CONDITIONAL** dù pin đầy —
  đúng 5 chuyến R6 ~835 m của thí nghiệm E2c, bị luật PD-1 chặn vì ngoài envelope
- **Luật `PH-1` không đổi phán quyết nào** trên bộ dữ liệu này: nó đòi SoC
  2,5–12,0 % còn luật dự trữ đòi 16,2–42,0 %, hai dải không chồng nhau. Nhưng ở
  mức pin 10 % nó chặn 30/192 chuyến — không phải code chết. Tác dụng thật sẽ
  thấy ở D4, trên kịch bản "chuyến ngắn bay cao" mà bộ dữ liệu CMU không có.

> **D4 đã kiểm điều này:** tầng `short_high` (2 100 kịch bản) được sinh riêng để
> quét vùng đó. Xem `reports/d4_main_comparison.csv` và thuộc đo M-9.

### Giải thích chi tiết

`docs/san_pham/D3_bo_may_quyet_dinh.md`

---

## RÀ SOÁT — bốn thiếu sót, đã vá

Đối chiếu từng chữ bảng Mục 12.1, P§4.5 và P§4.6 phát hiện bốn chỗ chưa đáp ứng.
Giữ lại mục này để truy vết.

| Mã | Nội dung | Trạng thái |
|---|---|---|
| RS-1 | Chưa khai báo cự ly một chiều / khứ hồi | **ĐÃ VÁ 15/10** — quyết định B7 |
| RS-2 | CONDITIONAL chưa đòi biện pháp giảm thiểu | **ĐÃ VÁ 15/10** — quyết định B8 |
| RS-4 | Chưa khai đủ 4 quy ước ngân sách năng lượng (P§4.5) | **ĐÃ VÁ 19/10** — quyết định B9 |
| RS-5 | Chưa cài sàn năng lượng hạ cánh (P§4.6) | **ĐÃ VÁ 20/10** — quyết định B10, luật `PH-1` |
| RS-3 | Lệch tổng cự ly 92,8 km vs ~65 km bài gốc | **chưa kết luận**, không chặn |

### RS-1 — Cự ly là khứ hồi · **ĐÃ VÁ (B7)**

Mục 12.1 đòi: *"one-way versus round-trip distance explicit"*. §4.3 cũng cảnh báo:
*"out-and-back mission distance is not the same as one-way distance"*.

Trước bản vá, không chỗ nào trong repo nêu vấn đề này.

**Tra bài gốc** — Rodrigues et al., *Scientific Data* 8, 155 (2021), mục Methods:

> *"tracks a triangular wind-neutral path while recording the data"* ·
> *"reaches the launch point again, the UAV stops and descends at approximately
> 1.5 m/s"*

Chuyến bay là **vòng kín tam giác, quay về đúng điểm cất cánh**. Tải trọng gắn
bằng dây Velcro, **mang suốt chuyến, không thả**.

Ba hệ quả, theo mức độ nghiêm trọng:

1. **`distance_2d_m` ≈ 472 m là vòng kín, không phải cự ly giao hàng một chiều.**
   Một nhiệm vụ giao hàng thật "472 m tới khách" sẽ bay khoảng 944 m khứ hồi —
   **nằm ngoài envelope 420–610 m**. Nghĩa là envelope hiện tại tương ứng với
   **cự ly giao hàng một chiều khoảng 210–305 m**.
2. **Khối lượng không đổi suốt chuyến.** Giao hàng thật thì chặng về nhẹ hơn, nên
   mô hình sẽ **đoán thừa** năng lượng chặng về — lệch về phía an toàn, nhưng
   vẫn là sai lệch phải khai báo.
3. **Bộ dữ liệu không có khái niệm "điểm giao hàng".** Đây là đường bay thử theo
   vòng, không phải nhiệm vụ giao hàng.

**Đã vá:** quy ước ghi vào `data_dictionary.md`, `d3_protocol.yaml`,
`parameter_table.md` và `decision_engine_report.md`. Không con số nào trong CSV
thay đổi.

### RS-2 — CONDITIONAL phải có biện pháp · **ĐÃ VÁ (B8)**

Mục 12.1 đòi: *"conditional verdicts require an explicit mitigation"*. Mục 2.3
nói rõ hơn: *"CONDITIONAL / DEGRADED is actionable only when an approved
mitigation is selected and the scenario is re-evaluated."*

Bản trước trả CONDITIONAL kèm một dòng lý do rồi hết — một nhãn, chưa phải một
trạng thái có đường ra.

**Đã vá:** thêm `src/mitigations.py` với 7 biện pháp chia hai nhóm.

| Nhóm | Biện pháp | Đổi cái gì |
|---|---|---|
| A | M1 sạc thêm pin · M2 đổi pin TB48D · M3 đợi gió giảm · M4 đợi trời ấm | năng lượng khả dụng hoặc ràng buộc |
| B | M5 giảm tải · M6 giảm tốc · M7 rút tuyến | **nhu cầu năng lượng** — bắt buộc dự báo lại |

`actionable = False` khi CONDITIONAL chưa có biện pháp. Thêm **INV-7**: mọi biện
pháp đề xuất đều được **chạy thử trước** khi hiện ra. Trên 192 chuyến: 213 đề
xuất, 0 cái vô dụng. Và biện pháp **không lật được NO-FLY** — có test riêng.

### RS-4 — Bốn quy ước ngân sách năng lượng · **ĐÃ VÁ (B9)**

P§4.5 cho công thức `E_required = E_outbound + E_return + E_hover` kèm ràng buộc
*"subject to an explicit convention that prevents double counting"* và liệt kê
**bốn** quy ước phải khai. Repo chỉ khai một (cự ly khứ hồi, B7).

| | Quy ước | Chốt |
|---|---|---|
| 1 | cự ly một chiều hay khứ hồi | **khứ hồi** (B7) |
| 2 | năng lượng cất/hạ cánh đã trong output chưa | **đã có** |
| 3 | chặng về có mang tải không | **có** |
| 4 | giả định tốc độ và độ cao hành trình | tốc độ ra lệnh, độ cao kế hoạch |
| + | số hạng `E_hover` | **= 0** — không có điểm giao hàng |

Quy ước (2) là quan trọng nhất: mục tiêu dự báo của D2 là **tổng năng lượng cả
chuyến bay** (§4.2 bước 4, không phân đoạn pha), nên `E_required` **đã bao gồm**
năng lượng cất cánh và hạ cánh. Hệ quả: **tuyệt đối không** cộng thêm một khoản
hạ cánh, và không nâng `r` để "bù cho hạ cánh".

**Không đổi hành vi hệ thống** — đây là khai báo điều hệ thống đang làm. Nhưng nó
chặn một lỗi thật: trước bản vá, người đọc giao thức có thể kết luận rằng năng
lượng hạ cánh chưa được tính rồi cộng thêm vào.

### RS-5 — Sàn năng lượng hạ cánh · **ĐÃ VÁ (B10)**

P§4.6 đòi: *"A minimum state of charge is added, **set so that the aircraft
retains the energy required to land from its cruise altitude**, following the
principle of placing a safety limit ahead of the end of discharge rather than at
it [10]."*

Repo chưa cài. Nhóm **từng tưởng đây là việc cần hỏi thầy** — tra lại P§4.6 thì
thấy thầy đã chọn sẵn cách làm, việc của nhóm chỉ là tính và cài đặt.

**Đã vá:** luật `PH-1`, mức độ VETO.

```
E_hạ = P_treo(khối lượng cất cánh) × (độ cao ÷ 1,5 m/s) ÷ 3600
PH-1:  E_available(SoC, SoH, T)  ≥  E_hạ
```

Năng lượng hạ cánh, hồ sơ `CMU_instrumented` (bảng đầy đủ ở
`reports/d3_landing_energy.csv`):

| Độ cao | tải 0 g | tải 500 g |
|---|---|---|
| 25 m | 2,46 Wh | 2,98 Wh |
| 50 m | 4,93 Wh | 5,97 Wh |
| 75 m | 7,39 Wh | 8,95 Wh |
| 100 m | 9,86 Wh | **11,93 Wh** |

Thêm **INV-8**, kiểm hai chiều: SoC dưới ngưỡng thì phải NO-FLY, *và* áp biện pháp
giảm thiểu thì vẫn NO-FLY.

**Đổi hành vi hệ thống**, nên đã chạy lại `evaluation_decision` và cập nhật bốn
CSV. Bảng phán quyết **không đổi** (187/5/0) — đã xác nhận bằng số, không giả định.

#### Ba lỗi phát sinh khi cài, do chính bộ test bắt

| | Lỗi | Test bắt |
|---|---|---|
| (a) | đặt tên `HR-5` trong khi nguồn không phải DJI | `test_moi_luat_hr_co_ghi_nguon` |
| (b) | chữ ký hàm nhận `e_available_Wh`, phá §4.6 | `test_lop_nay_khong_nhan_dau_ra_mo_hinh` |
| (c) | ngưỡng hạ cánh mặc định κ = 1, tức **lạc quan** | `test_dung_ngay_tai_nguong_thi_pass` |

Lỗi (c) phơi ra một cái bẫy thật: ở 0 °C thì κ = 0,9203 và ngưỡng thật cao hơn
mặc định **8,66 %**. Đã thêm test khoá tính chất đó.

#### Và một lỗi im lặng lặp lại ba lần

Danh sách bất biến từng được viết cứng ở bốn chỗ. Mỗi lần thêm bất biến là một
lần phải sửa bốn chỗ — và đã sai **ba lần** (thêm INV-7, thêm INV-8, rồi
`test_evaluation_decision.py`). Lỗi này **im lặng**: giao thức khai 8 bất biến,
bảng bằng chứng chỉ in 7, không ai báo gì.

Đã sửa bằng cách bỏ con số viết cứng: `run_invariants()` đọc danh sách từ giao
thức và **ném lỗi** nếu thiếu hàm kiểm; test so bảng kết quả trực tiếp với giao
thức.

### RS-3 — Lệch tổng cự ly so với bài gốc *(chưa kết luận)*

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
RS-1. Việc này **không chặn** D3 hay D4.

---

## D4 — Scenario benchmark

> Mục 12: *"documented scenario ranges, fixed random seeds, reference-label policy,
> baseline implementations, and result tables"*

**XONG 23/10/2026. Đạt 6/6 tiêu chí Mục 12.1. Duy ký định nghĩa nhãn tham chiếu
21/10, trước lần chạy đầu.**

### Mã nguồn — bốn module, một chuỗi

| Bước | File | Nội dung |
|---|---|---|
| 1 | `configs/d4_protocol.yaml` | v1.0.11 đóng băng — 26 quyết định C1–C26, 22 điều cấm |
| 2 | `src/scenario_generator.py` | 18 000 kịch bản, 4 tầng, seed 42 |
| 3 | `src/reference_labeller.py` | gắn **hai** nhãn tham chiếu độc lập |
| 4 | `src/baselines_decision.py` | 7 phương pháp B0…B5-noHR |
| 5 | `src/evaluation_scenario.py` | chấm điểm, sinh 8 bảng CSV |
| — | `scripts/compute_q95.py` | tính khoản phụ cấp `a` của REF-1 |
| — | `scripts/compute_ref2_calibration.py` | hiệu chuẩn `k` của REF-2 |

Test: `tests/test_scenario_generator.py`, `tests/test_reference_labeller.py`,
`tests/test_baselines_decision.py`, `tests/test_evaluation_scenario.py`.

### Bộ kịch bản — 4 tầng, 18 000 kịch bản, seed 42

| Tầng | Số | Vào bảng chính? |
|---|---|---|
| `main` | 12 600 | có |
| `short_high` | 2 100 | có — vùng `PH-1` ràng buộc hơn chỉ tiêu cự ly |
| `hard_rule_probe` | 2 100 | **không** — chỉ dùng cho M-7 |
| `missing_input` | 1 200 | **không** — chỉ dùng cho M-10 |

Bảng chính: **14 700** kịch bản, **0 kịch bản `unknown`**.
Hash bộ kịch bản: `fa81622c5d36884f`. Năm phép kiểm GEN: **5/5 đạt.**

Lý do loại hai tầng được **khai trong giao thức**, không phải quyết định lúc
chấm — giữ chúng lại sẽ làm M-2 của mọi phương pháp có luật cứng tốt lên giả tạo.

### Hai nhãn tham chiếu — §6/E3 đòi hai cái, cái sau bảo thủ hơn

| | Công thức | Nguồn |
|---|---|---|
| **REF-1** | `E_d2_prediction + a`, `a = 1,2924 Wh` | `a = |q05|` của sai số OOF có dấu |
| **REF-2** | `k × P_ideal(mass) × t/3600`, `k = 7,44` | `k = p95(E_đo / (P_ideal·t/3600))` trên 192 chuyến |

| Nhãn | REF-1 | REF-2 |
|---|---|---|
| feasible | 11 950 | 7 861 |
| infeasible | 3 763 | 7 670 |
| marginal | 1 087 | 1 569 |
| unknown | 1 200 | 900 |

**Hai nhãn khác nhau trên 32,2 % kịch bản** — con số này phải báo, nó cho biết
kết luận phụ thuộc bao nhiêu vào lựa chọn tham chiếu. Độ nhạy S-2 chấm lại toàn
bộ theo REF-2.

Vùng biên: **1 077 kịch bản** (w = 0,05, khai trước). Đạt ngưỡng GEN-4b ≥ 1 000
bằng cách nâng `n_scenarios` 6 000 → 18 000 theo phương án khắc phục đã khai
trước, **không** nới dải lấy mẫu (quyết định C20).

### Kết quả

| File | Nội dung |
|---|---|
| `reports/d4_scenarios.csv` | 18 000 kịch bản |
| `reports/d4_scenarios_labelled.csv` | kèm hai nhãn tham chiếu |
| `reports/d4_generator_check.csv` | 5 phép kiểm GEN |
| `reports/d4_labeller_check.csv` | phép kiểm GEN-4b, GEN-6 |
| `reports/d4_d2_frozen_coefficients.csv` | hệ số D2 đóng băng dùng cho REF-1 |
| `reports/d4_main_comparison.csv` | **bảng chính** — 7 phương pháp × M-1/M-2/M-4/M-5 |
| `reports/d4_confusion_matrices.csv` | bốn ô nhị phân mỗi phương pháp, cộng ba lớp cho B5 |
| `reports/d4_boundary_breakdown.csv` | M-3 — false-safe trong/ngoài vùng biên |
| `reports/d4_hard_rule_audit.csv` | M-7 và M-10 trên hai tầng riêng |
| `reports/d4_b5_rejection_causes.csv` | bóc tách M-4 của B5 theo nguyên nhân |
| `reports/d4_structural_relation.csv` | quan hệ `(1+r)a` vs `b` |
| `reports/d4_tradeoff_curve.csv` | đường đánh đổi theo hệ số dự trữ **và** ngưỡng SoC |
| `reports/d4_sensitivity_runs.csv` | S-1 … S-4 |

### Báo cáo

| File | Nội dung |
|---|---|
| `reports/scenario_benchmark_report.md` | **Báo cáo bàn giao** — bộ kịch bản, hai nhãn, bảy phương pháp, hai cảnh báo bắt buộc |

### Tái lập

```bash
python3 -m src.scenario_generator     # 18 000 kịch ban, hash fa81622c5d36884f
python3 -m src.reference_labeller     # gan hai nhan tham chieu
python3 -m src.evaluation_scenario    # 8 bang CSV — KHONG dung --nhanh
pytest -q
```

`--nhanh` bỏ qua độ nhạy S-1 để chạy nhanh khi phát triển. **Bản cuối phải chạy
đầy đủ** — chương trình in cảnh báo nếu thiếu.

### Nghiệm thu theo Mục 12.1

Nguyên văn tiêu chí D4 của thầy:

> *Scenario ranges and random seeds saved; reference-label protocol approved;
> labels explicitly marked simulation-derived; B0/B1/B2/B3/B5 implemented where
> applicable; identical scenarios and reserve policy used for comparisons;
> false-safe and unnecessary-rejection metrics reported*

| # | Tiêu chí | Trạng thái | Bằng chứng |
|---|---|---|---|
| 1 | Dải lấy mẫu và seed được lưu | **Đạt** | `d4_protocol.yaml §scenario_generator`, seed 42, hash `fa81622c5d36884f`, `d4_generator_check.csv` 5/5 |
| 2 | Giao thức nhãn tham chiếu được phê duyệt | **Đạt** | v1.0.11 đóng băng, **Duy ký 21/10**, trước lần chạy đầu |
| 3 | Nhãn dán rõ `simulation-derived` | **Đạt** | in ở đầu và cuối mỗi lần chạy, mục 0 của báo cáo |
| 4 | B0/B1/B2/B3/B5 được cài đặt | **Đạt** | `src/baselines_decision.py` — 7 phương pháp |
| 5 | Cùng kịch bản, cùng chính sách dự trữ | **Đạt** | 14 700 kịch bản, `r = 0,20` cho mọi phương pháp |
| 6 | Báo **cả** false-safe **và** từ chối thừa | **Đạt** | bảng chính, cộng hai cảnh báo bắt buộc |

**Cổng chặn:** *"No claims of real-world safety validation; document any
circularity risk"* — tuân thủ: mọi con số dán `simulation-derived`; rủi ro vòng
tròn được xử lý bằng **hai** tham chiếu, cái thứ hai (REF-2) không dùng D2.

### Kết quả chính

| Phương pháp | M-1 recall | M-2 false-safe | M-4 từ chối thừa | M-5 F1 |
|---|---|---|---|---|
| B0 | 0,3904 | 0,6096 | 0,0003 | 0,8920 |
| B1 | 0,2187 | 0,7813 | 0,0000 | 0,8658 |
| B1-pure | 0,0472 | 0,9528 | 0,0000 | 0,8411 |
| B2 | 0,8345 | 0,1655 | 0,0229 | 0,9567 |
| B3 | 0,9246 | 0,0754 | 0,0000 | 0,9853 |
| **B5** | **0,9990** | **0,0010** | 0,7186 | 0,4391 |
| B5-noHR | 0,9954 | 0,0046 | 0,0000 | 0,9991 |

- **Chỉ tiêu cự ly là đường cơ sở yếu nhất** — B1-pure bỏ sót 95,3 %
- **Mô hình dự báo là bước nhảy lớn nhất** — B1 → B2: 21,9 % → 83,5 % (đóng góp D2)
- **Luật cứng là bước nhảy lớn thứ hai** — B2 → B3: 83,5 % → 92,5 %
- **So sánh đáng tin nhất về bậc giữa là B3 → B5-noHR** (khác nhau đúng một thành
  phần): M-2 giảm **0,0754 → 0,0046**, tức **16 lần**, M-4 vẫn bằng 0

### HAI CON SỐ KHÔNG ĐƯỢC BÁO NHƯ NÓ HIỆN RA

Giao thức (`must_state_in_paper`, quyết định C26) bắt phát biểu nguyên văn:

```
(1) Ty le tu choi thua bang 0 doi voi mot so duong co so la he qua dai so
    cua viec nhan tham chieu bao thu hon he thong mot khoan lon hon chinh
    khoan bat dinh cua he thong; khong phai ket qua do duoc.

(2) Phan lon ty le tu choi cua phuong phap de xuat den tu co ngoai suy,
    khong tu quyet dinh nang luong.
```

**(1) M-4 = 0 là tất yếu đại số.** Đáp án gọi là khả thi khi
`E_av ≥ (1+r)(E_pred + a)`, tức `R_sys ≥ r + (1+r)a/E_pred`; ngưỡng hệ thống là
`R_fly = r + b/E_pred`. Vì `(1+r)·a = 1,5509 ≥ b = 1,4687`, mọi kịch bản
tham chiếu-khả thi **tự động** vượt ngưỡng FLY. Bậc giữa không thể bị tính là từ
chối thừa, dù thiết kế thế nào. Biên của bất đẳng thức chỉ **0,0822 Wh**.
→ **Cấm viết** *"bậc giữa cải thiện an toàn mà không tốn thêm"*.
→ Giao thức **cấm** chỉnh `a`, `b`, `r` để "sửa" con số này.

**(2) M-4 = 0,7186 của B5 phần lớn không phải quyết định năng lượng.**
**71,9 %** kịch bản tham chiếu-khả thi bị B5 hạ bậc vì **ngoại suy** (PD-1/PD-2,
ngoài envelope 420–610 m). Trong 14 700 kịch bản, 10 706 (72,8 %) nằm ngoài
envelope — hai con số khớp nhau, nguyên nhân đã xác nhận bằng số.
Phát biểu đúng: **B5 gắn cờ "ngoài vùng hiệu lực" cho 72 % kịch bản.**
→ Hệ quả cho D5–D9: muốn giảm con số này phải **mở rộng dữ liệu bay**, không
phải nới luật.

### Bốn phép đo độ nhạy bắt buộc

| | Quét gì | Vì sao bắt buộc |
|---|---|---|
| S-1 | pin TB48D (129,96 Wh) | P§4.4 — bài gốc tự mâu thuẫn về loại pin |
| S-2 | chấm lại theo REF-2 | hai nhãn khác 32,2 % |
| S-3 | `marginal` → tính là khả thi | quy ước C4 là lựa chọn, không phải sự thật |
| S-4 | quét bề rộng vùng biên w | w = 0,05 là số khai trước |

**Kết quả: không phép quét nào đảo thứ hạng.** Thứ hạng theo M-2 giữ nguyên
`B5 < B5-noHR < B3 < B2 < B0 < B1 < B1-pure` ở cấu hình gốc, S-1, S-2 và cả hai
bề rộng của S-4. Kết luận chính của D4 đứng được.

Ba phép quét cho thêm thông tin mà bảng chính không có, **cả ba phải vào bài**:

| | Phát hiện |
|---|---|
| **S-1** | Thứ hạng giữ nhưng **con số tuyệt đối xấu đi nhiều**: M-2 của B5-noHR tăng 0,0046 → **0,3231**, tức **70 lần**. Cơ chế xác nhận bằng số: nhãn tham chiếu được phê duyệt trước nên **giữ nguyên**, chỉ `E_available` đổi (bằng chứng: B0 không đổi tới 7 chữ số vì là ngưỡng SoC cố định). → **Mọi con số an toàn của D4 phụ thuộc giả định pin TB47D**, mà bài gốc tự mâu thuẫn về loại pin. |
| **S-3** | Khi `marginal` tính là khả thi thì B3, B5, B5-noHR **hoà nhau** ở M-1 = 1,0 và M-2 = 0,0; phân biệt chuyển sang M-4, và ở đó **B3 (0,0558) tốt hơn B5-noHR (0,0816)**. → **Ưu thế của bậc giữa chỉ đo được trên vùng `marginal`**; quy ước C4 là điều kiện để kết quả chính có ý nghĩa, không phải lựa chọn trung tính. |
| **S-4** | Cả `w = 0,025` và `w = 0,1` cho bảng **giống hệt** gốc, vì `w` chỉ tách bảng M-3 chứ không tham gia chấm điểm. Tốt: kết luận chính không phụ thuộc con số 0,05. Nhưng phép quét này **không kiểm chứng gì** về vai trò của `w` trong bảng M-3 (OI-D4-7). |

### Yêu cầu kiểm chéo riêng của D4 — đã xong

Mục 10: *"Student 3 and Student 4 must **jointly verify the definition of the
reference scenario labels**"*.

Duy ký `configs/d4_protocol.yaml §reference_label` ngày **21/10/2026**, trước
lần chạy so sánh đầu tiên. Ba lỗi trong bản ký đầu (`approved_on: "20206-10-21"`,
`status` rỗng, `meta.status` cũ) đã vá trên chính file đã ký, giữ nguyên chữ ký.
Sau khi đổi công thức REF-2 (quyết định C22), chữ ký được **reset và ký lại**.

### Giải thích chi tiết

`docs/san_pham/D4_benchmark_kich_ban.md`

---

## D5 — Robustness package

> Mục 12: *"boundary analysis, threshold sweeps, uncertainty/sensitivity plots,
> and failure-case examples"*

**Chưa bắt đầu. Cổng chặn đã mở** — D1 đến D4 đều xong. Người làm: Phát, tuần 10–11.

Module dự kiến: `src/uncertainty.py`

Nguyên liệu đã có:

| Cần gì | Có ở đâu |
|---|---|
| Phân phối sai số out-of-fold (§5.8) | `reports/d2_oof_residuals.csv` |
| Lát cắt độ nhạy sơ bộ | `reports/d3_scenario_sensitivity.csv` |
| Phân tích vùng biên — 1 077 kịch bản | `reports/d4_boundary_breakdown.csv` |
| Quét ngưỡng hai trục | `reports/d4_tradeoff_curve.csv` |
| Bốn phép quét độ nhạy đã chạy | `reports/d4_sensitivity_runs.csv` |
| Ví dụ trường hợp thất bại | `reports/d4_b5_rejection_causes.csv` — 71,9 % ngoại suy |

---

## D6 — Reproducible mission record

> Mục 12: *"versioned schema and deterministic replay tests"*

**Chưa bắt đầu chính thức**, nhưng nền đã có: `src/workflow_state.py` →
`MissionRecord` với bảy trường phiên bản, và INV-5 (tính lại từ bản ghi) đã đạt
192/192. D6 sẽ mở rộng và kiểm đầy đủ.

Người làm: Phát, tuần 11.

**Phải xử lý ở D6 (OI-D4-6):** đầu vào thiếu trong CSV là `NaN`, không phải
`None`. Tầng luật cứng của D3 kiểm `giá_trị is None`, và `NaN is None` là False,
`NaN > 10.0` cũng là False — nên HR-1 từng báo PASS cho kịch bản gió không rõ,
và B0 duyệt bay. D4 đã vá bằng `nan_sang_none()` tại 19 điểm gọi ở ranh giới
D4↔D3; bản thân D3 để nguyên (đã nghiệm thu, hành vi trên đường chạy riêng của
nó không bị ảnh hưởng). Đây là **bẫy tiềm ẩn** cho mọi đường dữ liệu mới.

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
| Năng lượng hạ cánh | `d3_landing_energy.csv` |
| **Định nghĩa đường cơ sở** | `d4_protocol.yaml §baselines` — 7 phương pháp |
| **Bảng so sánh định lượng** | `d4_main_comparison.csv` |
| **Benchmark kịch bản** | `scenario_benchmark_report.md` |

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
    hàng (RS-1). Số hạng `E_hover` của công thức (4) bằng 0 vì không có pha treo
    giao hàng (RS-4)
12. **Quyết định chưa được chấm điểm trên dữ liệu thật** — bộ dữ liệu không có
    nhãn kết cục. D4 chấm trên kịch bản tổng hợp, và mọi nhãn phải gọi là
    *simulation-derived*
13. Gió đo được dùng thay gió dự báo khi chạy D3 trên 192 chuyến
14. **Luật `PH-1` dựa trên mô hình vật lý của nhóm**, không phải số nhà sản xuất.
    η khớp từ một điểm, và áp lên máy bay CMU là ngoại suy. Công suất khi hạ cánh
    lấy bằng công suất bay treo — cận bảo thủ (RS-5)
15. **`PH-1` chưa được thử thách trên bộ dữ liệu này** — ngưỡng của nó nằm hoàn
    toàn dưới ngưỡng luật dự trữ, nên không đổi phán quyết nào. Không được trình
    bày như một luật đã kiểm chứng trên dữ liệu thật
16. **Hai nhãn tham chiếu của D4 khác nhau trên 32,2 % kịch bản** — kết luận của
    benchmark phụ thuộc vào lựa chọn tham chiếu, phải báo cả hai (S-2)
17. **"Từ chối thừa = 0" là tất yếu đại số, không phải kết quả đo** — xem cảnh
    báo (1) của D4. Cấm viết *"bậc giữa cải thiện an toàn mà không tốn thêm"*
18. **71,9 % từ chối của B5 là cờ ngoại suy, không phải quyết định năng lượng** —
    envelope cự ly 420–610 m quá hẹp so với dải kịch bản giao hàng. Xem cảnh
    báo (2) của D4
19. **Mọi con số an toàn của D4 phụ thuộc giả định pin TB47D (99,9 Wh)** — độ
    nhạy S-1 cho thấy đổi sang TB48D làm M-2 của B5-noHR tăng **70 lần**
    (0,0046 → 0,3231). Thứ hạng giữ nguyên, nhưng khoảng cách so với các đường
    cơ sở hẹp lại rất nhiều. Bài gốc **tự mâu thuẫn** về loại pin (hạn chế 5),
    nên đây không phải giả định an toàn
20. **Ưu thế của bậc giữa chỉ đo được trên vùng `marginal`** — độ nhạy S-3 cho
    thấy khi `marginal` được tính là khả thi thì B3, B5 và B5-noHR hoà nhau ở
    recall hoàn hảo, và trên M-4 thì B3 còn tốt hơn B5-noHR. Quy ước C4
    (`marginal` → không khả thi) là **điều kiện** để kết quả chính có ý nghĩa,
    không phải một lựa chọn trung tính

---

## D9 — Reproducibility package

> Mục 12: *"scripts, configuration files, environment requirements, seeds, and
> instructions to regenerate tables/figures"*

**Chưa đóng gói chính thức**, nhưng các thành phần đã có:

| Thầy yêu cầu | Có ở đâu |
|---|---|
| Scripts | `src/` — 22 module |
| Configuration files | `configs/d2_protocol.yaml` v1.4.0, `d3_protocol.yaml` v1.4.0, `d4_protocol.yaml` v1.0.11, `dataset.yaml` |
| Environment requirements | `requirements.txt` |
| Seeds | `d2_protocol.yaml → partitioning.cv.random_state: 42`; `d4_protocol.yaml → scenario_generator.seed: 42` |
| Instructions to regenerate | `README.md` và `docs/README.md` |
| Lịch sử chạy | `reports/experiment_log.jsonl` |
| Hash bộ kịch bản | `fa81622c5d36884f` |

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
| ~~RS-4~~ | ~~Khai đủ 4 quy ước ngân sách năng lượng~~ | **đã vá 19/10 — B9** |
| ~~RS-5 / OI-D3-1~~ | ~~Sàn năng lượng hạ cánh~~ | **đã vá 20/10 — B10, luật `PH-1`** |
| ~~OI-D3-3~~ | ~~Duy ký kiểm chéo WP3~~ | **đã xong 20/10** |
| ~~OI-D4-1~~ | ~~Duy ký định nghĩa nhãn tham chiếu~~ | **đã xong 21/10** |
| RS-3 | Kiểm lệch tổng cự ly 92,8 km vs 65 km của bài gốc | không chặn, nhưng ảnh hưởng cách đọc envelope |
| OI-4 | Báo thầy quyết định hai biến thể D2 | không chặn |
| OI-D4-4 | `interpretability.py` dùng `KFold` trần → alpha 1,0, khác alpha 0,1 của `d2_protocol.yaml` | không chặn — để nguyên, đã ghi |
| OI-D4-6 | `NaN is None` ở tầng luật cứng D3 — đã vá ở ranh giới D4↔D3 | **D6** |
| OI-D4-7 | S-4 không kiểm được vai trò của `w` trong bảng M-3 — cần quét `d4_boundary_breakdown.csv` theo `w` | không chặn — D5 |
| OI-5 | `Draft Báo.docx` còn dùng thông số Matrice 210 | D8 |

**Thứ tự nên làm:** D5 (`src/uncertainty.py`, tuần 10–11) → D6, kèm xử lý
OI-D4-6 ngay từ đầu. RS-3 làm lúc nào cũng được.
