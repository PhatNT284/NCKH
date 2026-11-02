# D5 — Lần chạy đầy đủ theo protocol v1.0.0

Run ID: `final_v1_20261102_01`. Protocol được Phát duyệt và đóng băng ngày 31/10/2026.
Lần chạy này có đầy đủ bằng chứng kỹ thuật; nghiệm thu kết quả mới vẫn chờ kiểm tra.

## Kết quả và phạm vi

Tất cả tỷ lệ FLY của D4/D5 trong phân tích này dùng cấu hình **CMU_instrumented
vượt MTOW**. HR-3 ghi nhận KNOWN_EXCEEDED ở tầng chẩn đoán; workflow chặn
duyệt/thực thi. Lớp chặn workflow không bị áp vào mẫu số thước đo.
Dải tải 0–500 g là độ phủ dữ liệu, không thay thế giới hạn MTOW.
Không phân tích hiệu năng M100_stock: mô hình D2 hiệu chỉnh trên khung 3.680 g;
áp sang khung 2.355 g là ngoại suy khối lượng chưa có số đo. Fixture M100_stock
chỉ kiểm logic phần mềm. Nhãn tham chiếu là simulation-derived.

- Baseline: đúng hệ số/scaler/intercept D2 của D4; kiểm nhãn, margin và API D3 scalar.
- Monte Carlo: 14.700 kịch bản × 10.000 draw × 3 seed × 2 pin × 5 cấu hình;
  4,410,000,000 lượt lấy mẫu; 0 draw không hợp lệ.
- OAT: 7.467.600 lượt đánh giá; quét reserve và điểm số vùng biên tại từng w.
- Matched-reference: 7,467,600 lượt; hai REF,
  membership gốc/tính lại và nhãn cố định/tính lại được lưu riêng.
- Counterfactual: 2,245 ID,
  4,490 ca pin,
  244,596 phép thử áp dụng được,
  2,915 đề xuất; giữ cả thất bại/không áp dụng.
- Replay **24/24**, workflow **41/41**. Không cộng 12 bản D6 thành 36.
- 24 snapshot D5 được nhúng nguyên checksum vào bản ghi theo schema D6
  `schemas/mission_record/1.0.0.json`; kiểm cấu trúc, metadata và chuỗi sự kiện.

## Đầu ra và đối chiếu

Mười file bắt buộc ở gốc run: input_manifest.json, baseline_consistency.json,
monte_carlo_fractions.csv, one_factor_sensitivity.csv, boundary_breakdown.csv,
verdict_transitions.csv, reference_policy_sensitivity.csv, failure_catalogue.csv,
replay_results.csv, workflow_invariant_results.csv; bốn hình trong figures/.
Các thư mục mc/oat/matched/replay/catalogue/fly_review giữ đầy đủ bằng chứng,
bao gồm snapshot, trial bị loại và manifest từng bước. source_snapshot/ lưu
mã, cấu hình, schema và đầu vào đúng phiên bản của lần chạy.

`old_vs_new_comparison.csv`: 366 cột đối chiếu, tổng
0 ô sai khác. So sánh giá trị đọc từ CSV
chính xác, tách định danh phiên bản/hash và thời gian khỏi số liệu thí nghiệm.
Catalogue đối chiếu 14 cột, gồm các JSON chứa đầu vào, năng lượng, margin và MC.
Nguồn CSV MC cũ dùng bản khôi phục khớp SHA-256 gốc, không dùng file đã làm tròn.
Chi tiết: historical_source_verification.json và table_sources.json.

Các manifest của module con giữ nhãn DEVELOPMENT/PENDING từ giao diện cũ:
chúng là bước thành phần, không tự đại diện toàn bộ D5. Protocol thực dùng
v1.0.0 được kiểm bằng hash và manifest, không sửa metadata của lần chạy cũ.
Trạng thái kỹ thuật của toàn bộ run nằm ở run_status.json và acceptance_checks.json;
không tự ký nghiệm thu thay Phát.

## Giả định và thời gian D9

SoC/SoH/kappa ±0,02 ở nhánh chính là giả định thí nghiệm, có thể lạc quan.
Phải đọc cùng nhánh stress ±0,05 (gió ±2 m/s), adverse residual/dependence;
không diễn giải fraction thành xác suất an toàn thực tế đã hiệu chuẩn.

Pipeline: **1158.638 giây**; chi tiết từng bước trong runtime.json.
Thời gian kiểm thử nằm riêng ở test_gate.json. Thời gian pipeline chưa gồm
bước niêm phong hash cuối. CSV được tạo một lần, kiểm hash và đặt toàn bộ
file/thư mục của run ở thuộc tính chỉ đọc; đây không phải lưu trữ WORM.
Không mở rồi lưu lại CSV bằng Excel. output_hashes.json kiểm chứng nội dung.
