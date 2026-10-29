# Bảng tình huống cần chú ý trong D5

Bản đã tạo: `reports/d5/failure_catalogue_20261026_03/`.

Đây là **31 ví dụ đại diện cho 11 nhóm**, chọn từ kết quả đã lưu. Không phải chỉ có 31 kịch bản gặp vấn đề. Bảng 457 ca có mẫu thiếu dự trữ trước đó vẫn là một bảng khác, dùng cho mục đích khác.

Đã kiểm tra: 58 kiểm thử liên quan đạt, gồm 15 kiểm thử mới cho việc chọn/ghi ví dụ. Đối chiếu độc lập 24/24 ví dụ OAT với đúng bản ghi nguồn và năng lượng đã lưu; 7/7 ca quy trình giữ mã ca thử, không gán ID D4. Bảy hash file kết quả, bản mã tạo bảng, bản quy trình và bảy hiện vật nền D2–D4 đã được đối chiếu.

## Mở file nào trước?

1. `failure_cases_explained.csv`: bảng giải thích tiếng Việt, mở bằng Excel và lọc theo ID, loại pin hoặc nhóm.
2. `failure_catalogue.md`: giải thích từng ví dụ, số năng lượng trước/sau và giới hạn cách hiểu.
3. `failure_catalogue.json` hoặc `.csv`: bản đầy đủ để kiểm tra đầu vào, kết quả từng luật và nguồn của mỗi dòng.

`ID_D4` là mã kịch bản gốc. Nếu trống thì đó là ca thử phần mềm có mã ở cột `Ma_ca_thu`, chẳng hạn thiếu SoC hay thời tiết hết hạn; không phải một ID bị mất dữ liệu.

## Đọc các kết luận

- `FLY`: đạt điều kiện của chế độ phân tích đang dùng. Các ca CMU vẫn có giới hạn MTOW đã công bố, nên nhãn này không cấp quyền bay thực tế.
- `CONDITIONAL`: cần xử lý điều kiện còn vướng và đánh giá/duyệt theo quy trình.
- `NO_FLY`: bị chặn theo điều kiện đánh giá.
- `INSUFFICIENT_DATA`: thiếu dữ liệu cần thiết để đánh giá.

Cột `Loai_ket_qua` phân biệt đổi quyết định, cảnh báo phạm vi mô hình, đổi cách chấm và bị chặn trong quy trình. Có dòng FLY→FLY hoặc CONDITIONAL→CONDITIONAL vì một cảnh báo/cách chấm không nhất thiết làm quyết định đổi. Đó không phải lỗi ghi bảng.

`Du_so_voi_du_tru_truoc_Wh` và `Du_so_voi_du_tru_sau_Wh` là năng lượng còn dư sau khi trừ nhu cầu **cộng phần dự trữ**. Số âm nghĩa là thiếu mức dự trữ. Ô trống nghĩa là không đánh giá đại lượng đó ở ca thử này, không thay bằng số 0.

## Các nhóm được kiểm tra

Năng lượng cần cao hơn dự đoán; mức pin bị báo cao hơn thực tế; pin chai hơn; thay giả định loại pin; đổi quyết định gần ngưỡng; đổi cách chấm nhóm sát ngưỡng; quãng đường ngoài phạm vi dữ liệu; gió ngoài phạm vi đã đo; cách xử lý nhiệt độ ngoài dải hiệu chỉnh; luật an toàn chặn dù năng lượng đủ; dữ liệu thiếu/không hợp lệ/hết hạn.

Các ví dụ OAT được chọn bằng ID nhỏ nhất đủ điều kiện trong mỗi nhóm/loại pin/tham chiếu. Nếu cùng ID có nhiều điểm thử, chọn điểm xuất hiện trước trong lưới đã khai. Vì vậy cùng một ID có thể xuất hiện nhiều dòng, và các dòng không nhất thiết là những ca có tỷ lệ thiếu lớn nhất.

REF-1 và REF-2 là hai cách gán nhãn tham chiếu mô phỏng của D4. Các nhãn D4 giữ nguyên giả định TB47D ban đầu, kể cả khi ứng viên chuyển sang TB48D. Tính lại nhãn tham chiếu theo giả định thay đổi là phần còn lại; bảng này không tự nhận đã hoàn tất phần đó.

## Tạo lại bảng

Tại thư mục `D:/IdeaProjects/NCKH`:

```powershell
.\.venv\Scripts\python.exe -m src.failure_catalogue --oat-run reports/d5/oat_all_scenarios_20261025_01 --replay-run reports/d5/replay_workflow_20261026_03 --fly-review reports/d5/fly_reserve_review_20261025_01 --out reports/d5/failure_catalogue_my_run
```

Thư mục output phải mới. Chương trình đối chiếu hash nguồn, đọc lần lượt toàn bộ 7.467.600 dòng OAT, loại 52.734 điểm thử không hợp lệ và ghi điều kiện chọn/số ca đủ điều kiện trong `category_coverage.csv`. Chỉ đối chiếu lại phép tính và luật của các điểm được chọn; không lấy mẫu Monte Carlo hay huấn luyện mô hình mới.

`catalogue_manifest.json` lưu nguồn và hash các kết quả. `catalogue_source.py` và `protocol_snapshot.yaml` giữ bản mã tạo bảng và quy trình tại lúc tạo. Nhãn tham chiếu tính lại và đánh giá đầy đủ bộ đề xuất điều chỉnh hiện đã có ở `reports/d5/matched_counterfactual_20261026_01/`; xem [hướng dẫn](D5_matched_counterfactual.md). Các bằng chứng vẫn là phát triển, kiểm tra chéo và chốt quy trình còn PENDING.
