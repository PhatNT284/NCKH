# Chạy phần mô phỏng bất định D5

Phần lưu/chạy lại quyết định và kiểm tra thời tiết/workflow đã có module D5 riêng. Xem [hướng dẫn lưu và chạy lại](D5_replay_workflow.md) cho lệnh chạy và giải thích giới hạn MTOW của cấu hình CMU. Các tỷ lệ Monte Carlo trong file này không phải quyền cho bay.

Danh mục 31 ví dụ đại diện cho 11 nhóm đã có tại `reports/d5/failure_catalogue_20261026_03/`. Xem [cách đọc bảng tình huống D5](D5_failure_catalogue.md); bảng này phân biệt đổi quyết định, thiếu dự trữ, cảnh báo và ca thử quy trình.

Đối chiếu tham chiếu theo giả định thay đổi và kiểm tra đầy đủ tập đề xuất đã có tại `reports/d5/matched_counterfactual_20261026_01/`. Xem [hướng dẫn và kết quả dễ đọc](D5_matched_counterfactual.md).

`src/uncertainty.py` lấy các đầu vào đã khai trong `configs/d5_protocol.yaml`, sinh sai lệch và tính lại năng lượng qua nhiều lượt lấy mẫu. Kết quả cho biết tỷ lệ lượt thỏa điều kiện năng lượng/dự trữ trong mô hình, dưới các giả định đã khai.

## Phạm vi đã triển khai

- Nạp đúng hệ số, scaler và intercept D2 đã lưu; đối chiếu hash và phiên bản đầu vào D2–D4 trước khi lấy mẫu.
- Lấy mẫu có hoàn lại từ phần dư OOF cấp chuyến, theo thứ tự flight tăng. Quy ước phần dư là dự đoán trừ thực tế: `E_demand = D2(latent_wind) - residual`.
- Năm nhánh: `RESIDUAL_ONLY`, `PRIMARY_INDEPENDENT`, `WIDER_RANGES`, `ADVERSE_RESIDUAL_POOL`, `ADVERSE_DEPENDENCE`.
- Đọc mức sai lệch đã chốt từ protocol. SoC/SoH/κ được lấy mẫu trên khoảng đã cắt theo [0,1]; gió có cận dưới 0. Lưu cận hiệu dụng và độ lệch trung bình khi khoảng bất đối xứng.
- PCG64 với `SeedSequence([seed, scenario_id, stream_id])`: việc đổi thứ tự xử lý, pin hoặc reserve không thay đổi chuỗi mẫu. Mức chính và khoảng rộng dùng cùng các quantile.
- Tính riêng tỷ lệ đủ năng lượng dự trữ và tỷ lệ đồng thời qua các VETO vật lý của D3. PH-1 dùng đúng năng lượng đã chịu sai lệch κ/SoC/SoH.
- Giữ verdict ban đầu; không tự đổi tỷ lệ Monte Carlo thành quyền cho bay.
- Dữ liệu gốc thiếu/NaN/không hợp lệ không được sửa bằng cách lấy mẫu hoặc kẹp về biên. Các tầng audit được ghi riêng, không đưa vào mẫu số Monte Carlo.
- Demand không dương được đếm là draw không hợp lệ, không lấy mẫu lại. Draw có gió vượt giới hạn hoặc thiếu năng lượng hạ cánh vẫn thuộc mẫu số hợp lệ và được đếm là thất bại ràng buộc.

## Chạy thử trên dữ liệu D4

Từ thư mục repository `D:/IdeaProjects/NCKH`:

```powershell
.\.venv\Scripts\python.exe -m src.uncertainty --limit 3 --out reports/d5/my_development_run
```

Mặc định dùng 3 kịch bản đầu tiên trong các tầng chính, 10.000 mẫu, ba seed trong protocol, cả hai loại pin và năm nhánh. Có thể chỉ định ID để xem ca sát biên hoặc dữ liệu thiếu:

```powershell
.\.venv\Scripts\python.exe -m src.uncertainty --scenario-ids 1 5 12601 16801 --out reports/d5/my_selected_cases
```

Kịch bản 5 là ca biên REF-1; 12601 thuộc tầng hard-rule probe; 16801 thuộc tầng missing-input. Các ID này được lấy từ bộ D4 hiện tại đã đối chiếu hash.

`--draws 100` chỉ dùng khi cần thử code nhanh; giá trị ghi đè được lưu rõ trong manifest. Mỗi lần chạy phải có thư mục mới; chương trình từ chối ghi đè thư mục đã có.

## Tóm tắt trong terminal

Từ module v0.1.1 / protocol v0.3.1, lúc chạy sẽ hiện cấu hình đầu vào và tiến độ `Completed scenario ... (đã xử lý/tổng; phần trăm)`. Khi hoàn tất, terminal in số kịch bản được chọn/có lấy mẫu/bị bỏ qua, tổng số draw hợp lệ/không hợp lệ và bảng tỷ lệ theo từng cấu hình, pin, seed. Hồ sơ máy bay và reserve được tách thành các bảng riêng.

Tỷ lệ trong bảng tổng hợp được tính bằng **tổng số lượt đạt / tổng số lượt hợp lệ của nhóm**, không lấy trung bình các fraction có mẫu số khác nhau. Không gộp các seed, pin hoặc cấu hình sai số thành một tỷ lệ chung. Trường hợp không có mẫu hợp lệ được in `NA`.

Xem tóm tắt kết quả đã chạy mà không cần chạy lại Monte Carlo:

```powershell
.\.venv\Scripts\python.exe -m src.uncertainty --summary-only reports/d5/my_first_run
```

Chế độ này đối chiếu hash manifest và kết quả JSON đã lưu rồi chỉ in tóm tắt; không sửa file trong thư mục lần chạy cũ. Khi chạy mới, tóm tắt còn được lưu vào `terminal_summary.txt` và `terminal_summary.csv`.

Phần cập nhật tóm tắt đã được kiểm tra cùng bộ uncertainty: 51 kiểm thử qua, gồm cách cộng tử số/mẫu số, tách seed/pin/cấu hình, loại dòng audit khỏi mẫu số, hiển thị NA, đọc lại lần chạy cũ và từ chối file sai hash.

## Các file đầu ra

| File | Nội dung |
|---|---|
| `input_manifest.json` | Cấu hình lần chạy, ID kịch bản, seed, số draw, hash đầu vào/code, phiên bản thư viện và trạng thái Git; nội dung giữ nguyên trong lần chạy |
| `run_status.json` | Trạng thái chạy/thất bại và hash các file kết quả |
| `monte_carlo_fractions.json` | Kết quả có cấu trúc, khoảng hiệu dụng, số draw hợp lệ/không hợp lệ, số vi phạm từng VETO và cờ ngoài miền |
| `monte_carlo_fractions.csv` | Cùng dữ liệu để lập bảng; các trường phức tạp được ghi dạng chuỗi JSON |
| `terminal_summary.txt` | Bản tóm tắt giống phần in trong terminal |
| `terminal_summary.csv` | Tử số, mẫu số và fraction theo từng hồ sơ/reserve/cấu hình/pin/seed |

Mỗi dòng kết quả có scenario_id, seed, loại pin, cấu hình bất định, reserve ratio, run_id và hash manifest. Hai nhãn tham chiếu D4 được giữ nguyên dưới `fixed_label_ref1/ref2`; đổi pin trong mô phỏng không ghi lại nhãn D4.

Mẫu số của mỗi fraction là `valid_draws`. Khi mẫu số bằng 0, fraction là null. `draws_total`, `invalid_draws` và các số đếm thành công được lưu cùng fraction.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_uncertainty.py -o addopts= -q
```

Bao phủ công thức/dấu phần dư; không cộng trùng allowance; tái lập seed và pairing; khoảng sát biên; pool âm và ghép hạng bất lợi; dữ liệu thiếu/không hợp lệ; demand không dương; VETO gió; PH-1 với năng lượng đã nhiễu; hash đầu vào; manifest và chống ghi đè output.

## Phần còn lại của D5

### Phân tích từng yếu tố trên toàn bộ 14.700 kịch bản

```powershell
.\.venv\Scripts\python.exe -m src.sensitivity --source-run reports/d5/all_scenarios_dev_01 --fly-review reports/d5/fly_reserve_review_20261025_01 --out reports/d5/oat_new_run
.\.venv\Scripts\python.exe -m src.sensitivity_report --run reports/d5/oat_new_run
```

Đã thực hiện đầy đủ tại `reports/d5/oat_all_scenarios_20261025_01/`: 254 điểm quét cho mỗi loại pin, 7.467.600 lượt đánh giá xác định. Mỗi điểm chỉ thay một yếu tố. Có đủ các offset sai số đã khai, toàn bộ 192 phần dư OOF, các dải SoH/gió/nhiệt độ, mức reserve và giả định loại pin.

Mở `sensitivity_report.md` để xem kết quả và sáu biểu đồ. `fly_cases_explained.csv` giải thích đủ 457 ca FLY đã lọc bằng các cột tiếng Việt. Hai file `.csv.gz` chứa chi tiết toàn bộ phép quét và tổng hợp từng kịch bản–yếu tố; nên đọc bằng Python theo lô vì số dòng chi tiết vượt giới hạn một sheet Excel.

Tần suất đổi verdict trên lưới không phải xác suất Monte Carlo. REF-1/REF-2 và boundary gốc được giữ cố định; các bảng chấm riêng từng REF, cách gộp marginal và các độ rộng w. Việc chưa thấy một yếu tố đơn lẻ gây thiếu dự trữ ở khoảng chính không có nghĩa yếu tố đó không ảnh hưởng khi kết hợp với yếu tố khác.

### Lọc các ca FLY có mẫu thiếu dự trữ từ lần chạy đã lưu

```powershell
.\.venv\Scripts\python.exe -m src.analyze_uncertainty --run reports/d5/all_scenarios_dev_01 --out reports/d5/fly_review_new
```

Lệnh chỉ đọc kết quả cũ, đối chiếu hash và ghép lại đầu vào D4 đã dùng trong lần chạy; không sinh mẫu Monte Carlo mới. Thư mục output phải mới.

- `fly_priority_cases.csv`: 20 ca cấu hình chính có tỷ lệ thiếu cao nhất qua các seed, để xem trước.
- `fly_reserve_failures.csv`: toàn bộ ca FLY có mẫu thiếu, giữ riêng từng cấu hình và loại pin.
- `fly_reserve_failures_by_seed.csv`: số lượt thiếu và tỷ lệ riêng theo từng seed.
- `fly_case_summary.csv`: số ca FLY ban đầu, số ca có mẫu thiếu và số ca có mẫu thiếu ở mọi seed.
- `fly_reserve_review.md`: giải thích điều kiện lọc, bảng ngắn và giới hạn diễn giải.
- `analysis_manifest.json`: nguồn, hash và quy tắc phân tích để truy lại kết quả.

Khoảng tỷ lệ thấp/cao của một ca được tính trên mọi seed, kể cả seed không có mẫu thiếu. Thiếu mức dự trữ và vi phạm VETO được phân biệt. Việc lọc này chưa tự xác định nguyên nhân từ từng yếu tố sai số, chưa là bằng chứng verdict đổi và chưa thay thế danh mục ca thất bại đầy đủ.

Runner Monte Carlo vẫn ghi `DEVELOPMENT_PARTIAL` và `final_d5_complete: false`. OAT đã quét boundary/reserve và xuất biểu đồ trên toàn bộ tập chính. Snapshot lịch sử, replay và kiểm tra thời tiết/workflow hiện có ở `src/mission_record.py`, với runner `src/replay_validation.py`; đây là phần phát triển riêng, không thay đổi ý nghĩa các mẫu MC cũ. Danh mục 11 nhóm hiện có ở `src/failure_catalogue.py`. Matched-reference secondary và kiểm tra đầy đủ đề xuất đã có ở `src/complete_robustness.py`; các bằng chứng vẫn là phát triển, kiểm chéo/chốt quy trình và nghiệm thu cuối còn PENDING. Tỷ lệ đồng thời qua VETO của MC chỉ xét lớp ràng buộc vật lý D3, chưa gộp hiệu lực thời tiết/workflow.

Protocol hiện là v0.6.1, vẫn ở trạng thái nháp và chưa có xác nhận kiểm chéo của Phát. Các khoảng sai số, seed và số draw kế thừa từ v0.2.0 được giữ nguyên. Các output MC/OAT và đối chiếu tham chiếu trước đó vẫn gắn với phiên bản protocol đã dùng khi chạy.

## Kết quả kiểm tra ngày 25/10/2026

- 40 kiểm thử của module mới đã qua; tổng cộng 279 kiểm thử của uncertainty, available_energy, safety_invariants và decision_rules đã qua. Ba cảnh báo deprecation đến từ fixture hiện có của các bộ kiểm thử D3.
- Bản chạy `reports/d5/uncertainty_dev_20261025_01/` chọn ID 1, 5, 12601 và 16801, giữ đủ 10.000 draw, ba seed, hai pin, năm nhánh.
- ID 1 và 5 tạo 60 dòng kết quả Monte Carlo, tổng cộng 600.000 lượt lấy mẫu. ID 12601 tạo 30 dòng audit; ID 16801 tạo 30 dòng dữ liệu gốc không hợp lệ. Hai nhóm sau không có draw và không được điền feasibility fraction.
- Có 120 dòng kết quả tổng cộng. Trạng thái lần chạy là `COMPLETED_DEVELOPMENT_PARTIAL`; input manifest và hash output đã lưu.
- Ví dụ để đọc output, với TB47D/seed 42, kịch bản 1 có fraction 1,0000 ở nhánh chính và 0,9925 ở nhánh khoảng rộng; kịch bản 5 có 0,0083 và 0,0783 tương ứng. Khoảng rộng hoặc ghép phụ thuộc có thể làm fraction tăng ở kịch bản vốn thiếu dự trữ; không suy rằng nhánh được đặt tên stress luôn phải làm mọi fraction giảm. Đây là ví dụ chạy thử để kiểm tra phần mềm, chưa đủ để kết luận cho toàn bộ bộ kịch bản.
