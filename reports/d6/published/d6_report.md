# D6 — Bản ghi nhiệm vụ có thể tái lập

Căn cứ: proposal §12 (D6), §5.10; phương pháp kiểm thử theo E5. Duy thực hiện, Phát kiểm tra chéo. Trạng thái kiểm tra chéo: PENDING.

## Kết quả kiểm chứng

- Bản ghi: 12; đủ bốn phán quyết, hai pin, ca cận biên, luật chặn, thiếu/NaN/đầu vào sai, thời tiết hết hạn và đánh giá lại trước bay.
- Lược đồ và lưu/đọc: 12/12 đạt.
- Replay phán quyết: 12/12 khớp chính xác.
- Replay toàn bộ đầu ra: 12/12 khớp; chênh lệch tuyệt đối lớn nhất 0.
- Dung sai số: atol=1e-8, rtol=1e-8, lấy từ protocol D5 đã lưu cùng bản ghi.
- Kiểm tra bổ sung: 12/12 đạt; gồm từ chối schema lạ, trường thiếu, kết quả bị sửa và mô hình lịch sử bị thiếu.

## Hai đầu ra D6 theo proposal

1. `schemas/mission_record/1.0.0.json`: lược đồ có phiên bản; `src/mission_schema.py`: kiểm tra, lưu, đọc và replay bản ghi.
2. `tests/test_mission_schema.py`, `tests/test_mission_record.py`: kiểm thử hợp đồng bản ghi, replay và bất biến quy trình; `replay_results.csv`, `checks.json`: bằng chứng của lần chạy này.

## Phạm vi

D6 kế thừa snapshot/replay từ D5; không thay công thức năng lượng hay mô hình D2. Các ca thử là tổng hợp, thời điểm và thời tiết là fixture lịch sử rõ ràng. M100_stock chỉ kiểm logic; CMU_instrumented là cấu hình chẩn đoán không cấp quyền bay.

Hướng gió không có: lưu null và lý do. Đánh giá tất định không lấy mẫu: seed=null. Độ nhạy riêng từng bản ghi chưa chạy: lưu trạng thái NOT_RUN; không tạo kết quả giả. Bản ghi lưu nguồn giả định pin từ cấu hình lịch sử. Kết cục UNKNOWN được giữ độc lập với FLY/NO_FLY. Không có dữ liệu bay thực tế mới.

Replay cần cả bản ghi và thư mục store chứa mô hình/mã/config lịch sử; file JSON xuất riêng không thay thế kho hiện vật. Thiếu phiên bản hoặc sai checksum thì báo lỗi. Bản ghi quy trình phản ánh thời điểm as_of, không phải quyền duyệt hiện tại.

Kết quả này là bằng chứng kỹ thuật, chưa có xác nhận kiểm tra chéo; không tự nghiệm thu D6 hoặc thay trạng thái nghiệm thu D5.
