# D5 — Bản báo cáo chia sẻ trên GitHub

Mở [báo cáo tổng hợp](d5_robustness_report.md) trước; xem [bảng đối chiếu 7 tiêu chí](tables/d5_acceptance_checklist.csv) khi kiểm tra yêu cầu.

**Trạng thái: bằng chứng phát triển; chưa kiểm tra chéo/nghiệm thu.** Bản chia sẻ trích từ `summary_20261026_02`, không chạy thêm mô phỏng và không sửa kết quả nghiên cứu.

## Có trong bản chia sẻ

- Báo cáo tổng hợp, ba biểu đồ PNG và các bảng nhỏ được liên kết trong báo cáo.
- Nhật ký khôi phục/xuất hình liên quan, đã bỏ tiền tố đường dẫn riêng của máy.
- `publication_manifest.json`: đường dẫn nguồn tính từ gốc repository, hash file nguồn và hash bản chia sẻ. Các bản văn bản đã chuẩn hóa đường dẫn/mã hóa, vì vậy hash có thể khác file gốc.

Các đường dẫn nguồn trong bảng kiểm và nhật ký là thông tin truy xuất lịch sử. File dữ liệu ở các đường dẫn đó không được đóng gói trong Git. Bảng kiểm ghi có bằng chứng kỹ thuật trong kho gốc; không xác nhận người clone đã nhận toàn bộ bằng chứng hoặc Phát đã kiểm tra chéo.

## Giữ riêng, không commit

Các lần chạy Monte Carlo/OAT nhiều GB, kết quả nén, các bản khôi phục CSV, kho replay có mã/cấu hình sao chép, bản xuất trung gian và nhật ký dọn thư mục được `.gitignore` bỏ qua. Mã nguồn đang dùng, protocol, kiểm thử và hướng dẫn vẫn được chia sẻ.

Để kiểm chứng đúng lần chạy lịch sử, cần nhận kho hiện vật gốc ngoài Git. Clone repository là đủ để đọc bản báo cáo này; chưa đủ để kiểm hash/chạy lại toàn bộ thí nghiệm lịch sử. Tài liệu proposal được nhóm cung cấp riêng; không sao chép tài liệu ngoài repository vào bản chia sẻ.

## Chạy mã D5

Từ thư mục gốc repository, cài `requirements.txt` và chuẩn bị đầu vào D2–D4 theo README chính. Không huấn luyện lại hoặc đổi file đã đóng băng chỉ để bỏ qua lỗi hash; các runner kiểm hash đầu vào và sẽ báo sai khác.

Thử nhỏ trước (không phải bộ kết quả đầy đủ trong báo cáo):

```powershell
python -m src.uncertainty --scenario-ids 1 5 --draws 100 --out reports/d5/my_smoke_run
```

Kiểm thử D5:

```powershell
python -m pytest tests/test_uncertainty.py tests/test_analyze_uncertainty.py tests/test_sensitivity.py tests/test_mission_record.py tests/test_failure_catalogue.py tests/test_reference_world.py tests/test_complete_robustness.py tests/test_d5_report.py tests/test_recover_uncertainty_csv.py -o addopts= -q
```

Hướng dẫn chi tiết:

- [Monte Carlo và phân tích từng yếu tố](../../../docs/cach_lam/D5_uncertainty.md).
- [Lưu và chạy lại quyết định](../../../docs/cach_lam/D5_replay_workflow.md).
- [Danh mục tình huống](../../../docs/cach_lam/D5_failure_catalogue.md).
- [Đối chiếu tham chiếu và đề xuất thay đổi](../../../docs/cach_lam/D5_matched_counterfactual.md).

Lệnh `python -m src.d5_report --out reports/d5/summary_new` dùng các thư mục lịch sử đã khai trong `src/d5_report.py` và tài liệu proposal ở vị trí khai trong protocol; cần kho hiện vật đó trên máy. Nó không tự lấy dữ liệu từ bản chia sẻ này. Chạy thử mới dùng protocol hiện tại không tự tái tạo nguyên byte lần chạy lịch sử dùng protocol cũ.

D5 dùng hồ sơ CMU với ngoại lệ MTOW đã khai; kết quả FLY trong phân tích không phải quyền bay thực tế. Các tỷ lệ Monte Carlo không phải xác suất an toàn thực tế đã được hiệu chuẩn.
