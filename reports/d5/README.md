# D5 — Bắt đầu đọc từ đây

**Báo cáo để đọc trên GitHub:** [Báo cáo tổng hợp D5](published/d5_robustness_report.md).

**Đối chiếu proposal:** [Bảng 7 tiêu chí](published/tables/d5_acceptance_checklist.csv).

Cả 7 tiêu chí đã có bằng chứng kỹ thuật. D5 còn chờ kiểm tra chéo và nghiệm thu; chưa phải bản chốt cuối cùng.

## Nội dung đưa lên GitHub

Chỉ `README.md` này và `published/` được đưa vào Git trong thư mục D5. Bản chia sẻ có báo cáo, ba hình minh họa, các bảng nhỏ và thông tin nguồn; các liên kết dùng đường dẫn tương đối. Xem [phạm vi bản chia sẻ và cách chạy](published/README.md).

Các lần chạy đầy đủ, CSV/JSON lớn, bản sao mã/cấu hình trong kho replay, bản khôi phục và nhật ký dọn thư mục vẫn giữ trên máy, được `.gitignore` loại khỏi Git. Không xóa chúng chỉ để giảm dung lượng khi push. Chúng cần cho kiểm chứng chi tiết và tổng hợp lại báo cáo lịch sử.

Mã nguồn D5 trong `src/`, kiểm thử trong `tests/`, protocol trong `configs/` và các hướng dẫn trong `docs/cach_lam/` vẫn được chia sẻ. Script rà soát trước triển khai `scripts/check_d5_readiness.py` đã hoàn thành nhiệm vụ và được chuyển vào Thùng rác ngày 26/10/2026; các module D5 hiện tại không phụ thuộc script này.

Bốn bảng đầu vào D2/D4 được dùng bởi protocol D5 cũng được chia sẻ đúng phiên bản
đã đóng băng. `.gitattributes` giữ nguyên byte của các bảng và ba protocol đầu vào;
không dùng `git add --renormalize` để đổi xuống dòng các file này vì sẽ làm sai SHA-256.

## Các thư mục dữ liệu được giữ cục bộ

Các thư mục sau có trên máy đã chạy thí nghiệm, không kèm theo khi clone GitHub. Báo cáo lịch sử đầy đủ nằm ở `summary_20261026_02/robustness_report.md`.

| Thư mục | Dùng để làm gì |
|---|---|
| `summary_20261026_02` | Báo cáo tổng hợp hiện tại, bảng đối chiếu và biểu đồ để đọc trước. |
| `all_scenarios_dev_01` | Kết quả Monte Carlo và thông tin lần chạy gốc. |
| `fly_reserve_review_20261025_01` | Phân tích các ca ban đầu FLY nhưng có mẫu thiếu dự trữ. |
| `oat_all_scenarios_20261025_01` | Kết quả thay đổi từng yếu tố, thay đổi mức dự trữ và kiểm tra gần ranh giới quyết định. |
| `replay_workflow_20261026_03` | Bản kiểm tra lưu, chạy lại quyết định và quy trình hiện tại. |
| `failure_catalogue_20261026_03` | Danh mục các tình huống đại diện hiện tại. |
| `matched_counterfactual_20261026_01` | Tính lại nhãn tham chiếu và kiểm tra các đề xuất thay đổi chuyến bay. |
| `mc_csv_recovery_20261026_01` | CSV Monte Carlo khôi phục đúng hash gốc từ JSON, được báo cáo sử dụng. |
| `oat_csv_recovery_20261026_01` | Bảng giải thích 457 ca khôi phục đúng hash gốc, được báo cáo sử dụng. |
| `figure_rebuild_20261026_01` | Các hình xuất lại và bằng chứng đối chiếu với hình gốc. |

Các thư mục dữ liệu và khôi phục vẫn cần để kiểm chứng báo cáo và tạo lại bản tổng hợp. Đường dẫn trong mã nguồn và hồ sơ lần chạy đang dùng các tên này.

## Dọn thư mục ngày 26/10/2026

Đã chuyển sáu thư mục không còn được bản tổng hợp hiện tại sử dụng vào **Thùng rác Windows**; có thể khôi phục từ đó nếu cần:

- `summary_20261026_01`: đã có bản tổng hợp `summary_20261026_02` thay thế.
- `replay_workflow_20261026_01`: lần chạy bị lỗi.
- `replay_workflow_20261026_02`: đã có bản `replay_workflow_20261026_03` thay thế.
- `failure_catalogue_20261026_01` và `failure_catalogue_20261026_02`: đã có bản `failure_catalogue_20261026_03` thay thế.
- `readiness_20261025_02`: bản rà soát sơ bộ trước khi triển khai D5, sử dụng protocol v0.2.0; các giới hạn còn liên quan đã được trình bày trong báo cáo hiện tại.

Nhật ký cục bộ `summary_20261026_02/cleanup_log_20261026.json` ghi danh sách file đã xóa và hash trước khi xóa. Nhật ký này không chứa bản sao nội dung đã xóa và không đưa lên GitHub.
