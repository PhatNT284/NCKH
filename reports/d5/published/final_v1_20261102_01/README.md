# D5 v1.0.0 — final_v1_20261102_01

Xem [báo cáo](robustness_report.md), [kiểm tra](acceptance_checks.json), [đối chiếu](old_vs_new_comparison.csv) và [thời gian D9](runtime.json).

Đây là bản nhỏ để đưa lên Git: có bảng MC tổng hợp, OAT, vùng biên, matched-reference, counterfactual, replay/workflow, bốn hình và bằng chứng hash. Bộ đầy đủ ở `reports/d5/final_v1_20261102_01/` trên máy chạy, gồm MC CSV/JSON, các bảng nén lớn và kho snapshot/mã nguồn lịch sử. Các file lớn vẫn giữ nguyên, không bị xóa hoặc ép thành bảng tổng hợp. `full_run_hashes.json` liệt kê checksum để kiểm chứng bộ đầy đủ. Không dùng git add -f cho CSV Monte Carlo vượt giới hạn kích thước GitHub.

Có thêm manifest của từng bước, log pytest và 24 JSON trong `mission_records/` đã kiểm schema 1.0.0. Replay vẫn cần kho artifact/mã lịch sử trong bộ đầy đủ, không chỉ các JSON xuất riêng.
