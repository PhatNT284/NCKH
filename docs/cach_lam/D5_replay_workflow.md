# Lưu và chạy lại quyết định D5

Mục đích: lưu đúng dữ liệu, cấu hình và kết quả của một lần đánh giá; sau đó tính lại từ bản đã lưu để kiểm tra có tái tạo được quyết định đó không. Đây là nghiên cứu phần mềm, không cấp quyền bay ngoài thực tế.

Bản đã chạy ngày 26/10/2026 nằm tại `reports/d5/replay_workflow_20261026_03/`: 24/24 bản chạy lại khớp toàn bộ đầu ra, chênh lệch số lớn nhất bằng 0; 41/41 kiểm tra quy trình đạt. Bộ kiểm thử `tests/test_mission_record.py` có 80 ca đạt; 388 kiểm thử cũ liên quan cũng đã đạt trong lần kiểm tra hồi quy. Đã đối chiếu 74 hash file đầu ra, 34 file mã nguồn/cấu hình/mô hình lưu kèm và bảy hiện vật D2–D4; đã thử lệnh capture/replay trong một kho tạm riêng.

## Giới hạn MTOW trong các kết quả D5 đã chạy

D4 và các bản Monte Carlo/OAT đang phân tích hồ sơ `CMU_instrumented`: M100 có gắn thiết bị đo. Bảng tham số ghi khối lượng chưa tải 3.680 g, trong khi DJI công bố khối lượng cất cánh tối đa 3.600 g. Nguồn: `reports/parameter_table.md` mục 3.1 và [thông số DJI M100](https://www.dji.com/support/product/matrice100).

Trong chế độ phân tích này, D3 ghi HR-3 là `KNOWN_EXCEEDED / RECORD_ONLY`. Nhãn `FLY` là kết quả của chế độ phân tích có ngoại lệ đó. Nó không xác nhận cấu hình đã đáp ứng mọi giới hạn của DJI. Dải tải 0–500 g chỉ mô tả phạm vi dữ liệu mô hình, không thay thế MTOW. Không dùng các kết quả này làm xác nhận an toàn bay thực tế.

Module D5 mới không cho duyệt các bản ghi CMU để tiến hành nhiệm vụ. Các ví dụ duyệt dùng riêng `M100_stock`, vẫn giữ HR-3 chặn khi quá khối lượng. Chúng kiểm tra logic phần mềm; mô hình năng lượng học từ dữ liệu CMU chưa được xác nhận riêng cho máy bay M100 nguyên bản.

## Những gì được lưu

- `snapshots/`: thông tin chuyến bay/pin, đơn vị, nguồn và thời hạn thời tiết, thời điểm đánh giá, năng lượng dự đoán, năng lượng khả dụng, mức dư, kết quả từng luật, kết luận, bằng chứng biện pháp xử lý nếu có.
- `artifacts/`: bản sao mã nguồn, YAML D2–D5, hệ số và bộ chuẩn hóa D2, phần dư OOF; kèm hash nguồn dữ liệu, phiên bản Python/thư viện, Git commit và các thay đổi chưa commit. Đầu vào của từng kịch bản được lưu đầy đủ; không cần huấn luyện lại mô hình.
- `workflow_events/`: các sự kiện duyệt, bắt đầu, đánh dấu hết hạn và ghi kết cục, gắn với checksum của bản đánh giá. API chỉ thêm file sự kiện mới và không sửa snapshot cũ.

Checksum giúp phát hiện sửa nhầm. Cơ chế này không phải lưu trữ WORM hay chữ ký chống chỉnh sửa ác ý. Môi trường Python và thư viện không được đóng gói thành container; nếu phiên bản đã lưu không có sẵn, chương trình báo không thể chạy lại.

## Chạy bộ ví dụ và kiểm tra

Tại `D:/IdeaProjects/NCKH`, chạy:

```powershell
.\.venv\Scripts\python.exe -m src.replay_validation --out reports/d5/replay_workflow_my_run
```

Thư mục phải mới. Chương trình lưu các ca đại diện cho đủ bốn kết luận, ca biên, vi phạm gió/khối lượng, đầu vào thiếu/NaN/sai, thời tiết hết hạn, CONDITIONAL có/không có biện pháp hợp lệ. Có thêm ba kịch bản D4: ID 1/TB47D, 2681/TB47D và 4757/TB48D. Thời tiết và thời điểm trong bộ kiểm tra đều là giả lập được khai rõ, không phải quan trắc thời tiết thực tế.

Đọc `replay_report.md` trước. `assessment_summary.csv` liệt kê các bản đã lưu; `replay_results.csv` cho biết mỗi bản chạy lại có khớp không; `workflow_checks.csv` ghi từng tình huống và kết quả chặn/cho phép trong quy trình giả lập.

Chỉ chạy lại một số bản đã lưu:

```powershell
.\.venv\Scripts\python.exe -m src.mission_record --store reports/d5/replay_workflow_my_run --replay stock_fly d4_2681_TB47D d4_4757_TB48D
```

Phép chạy lại không sửa bản cũ và không sinh mẫu Monte Carlo. Nó nạp bản mã nguồn đã lưu trong tiến trình Python riêng, không đọc cấu hình mới nhất của project. Thiếu file, khác checksum hoặc không có đúng phiên bản môi trường thì báo lỗi.

## Thời tiết hết hạn và thay đổi dữ liệu

Mỗi bản thời tiết phải có `observed_at`, `valid_until` và `source`; thời điểm phải có múi giờ. Tại thời điểm đánh giá bằng hoặc sau `valid_until`, dữ liệu hết hạn. Thiếu thời hạn hoặc nguồn cũng không cho kết quả FLY. Không tự điền thời hạn kiểu 30 phút, không tự sửa đầu vào thiếu.

Đổi tải hàng, khoảng cách, độ cao, tốc độ, SoC/SoH, loại pin/máy bay, thời tiết, mô hình, quy tắc hoặc mức dự trữ làm đánh giá cũ STALE. `workflow_action()` kiểm tra các điều kiện này khi duyệt hoặc bắt đầu, dùng thời điểm do bên gọi cung cấp. Bản đánh giá đã được thay thế không dùng lại để duyệt; bản mới cần được người xem xét lại, kể cả khi bản cũ từng được duyệt.

Chạy lại lịch sử dùng thời điểm của lần đánh giá cũ để kiểm tra tính tái lập. Duyệt tiếp một nhiệm vụ cần kiểm tra thời tiết ở thời điểm hiện tại. Tái tạo đúng một kết luận cũ không làm dữ liệu thời tiết đó còn hiệu lực hôm nay.

## CONDITIONAL và kết cục

CONDITIONAL không được duyệt chỉ bằng cách điền một chuỗi tên biện pháp. Module kiểm ID M1–M7, vai trò/thời điểm người duyệt, liên kết bản cũ, đúng yếu tố điều chỉnh, tính lại toàn bộ dự đoán và yêu cầu kết quả cải thiện. Ví dụ M1 tăng SoC, sau đó tạo một bản đánh giá mới. Đây là kiểm tra biện pháp được cung cấp; chưa phải đánh giá đầy đủ bộ tìm kiếm đề xuất điều chỉnh của E5.

Kết cục như COMPLETED, ABORTED, NOT_FLOWN được ghi bằng sự kiện độc lập, có ghi chú và nguồn bằng chứng; UNKNOWN là mặc định. Chương trình không suy ra kết cục từ nhãn FLY/NO_FLY.

## Lưu một yêu cầu riêng

Tạo JSON gồm `assessment_id`, `mission_id`, `assessed_at`, `inputs`, `weather`. `inputs` cần đủ tám đầu vào số như trong các bản ví dụ, cộng `battery_type`, `profile`, `reserve_factor`. Không truyền năng lượng dự đoán từ ngoài: mô hình đã chốt sẽ tính lại.

```powershell
.\.venv\Scripts\python.exe -m src.mission_record --store reports/d5/my_record_store --capture request.json
```

Khi tạo đánh giá lại, thêm `previous_assessment_id` trong cùng kho. Nếu áp biện pháp cho CONDITIONAL, thêm `mitigation` chứa `id`, `approved_by_role`, `approved_at`; thay đổi đầu vào theo đúng biện pháp và cấp một `assessment_id` mới. API mới nằm ở `src/mission_record.py`; API D3 cũ trong `src/workflow_state.py` không phải đường kiểm tra E5 này.

## Trạng thái D5

Lần replay ở trên dùng protocol v0.5.0 đã lưu; bản hiện tại là v0.6.1 và vẫn ở trạng thái nháp, kiểm tra chéo PENDING. Các kết quả cũ giữ nguyên phiên bản và hash của lần chạy. Danh mục 31 ví dụ cho 11 nhóm đã có ở `reports/d5/failure_catalogue_20261026_03/`; xem [hướng dẫn đọc bảng](D5_failure_catalogue.md). Nhãn tham chiếu tính lại và kiểm tra đầy đủ đề xuất cũng đã có ở `reports/d5/matched_counterfactual_20261026_01/`; xem [kết quả](D5_matched_counterfactual.md). Chốt quy trình và kiểm tra chéo cuối vẫn cần hoàn tất trước khi xác nhận D5 hoàn thành.
