# Đối chiếu tham chiếu đúng giả định và kiểm tra đề xuất điều chỉnh

Bản đã chạy: `reports/d5/matched_counterfactual_20261026_01/`. Mở `robustness_completion_report.md` để đọc báo cáo. Hai file ví dụ có tên `battery_reference_examples.csv` và `counterfactual_examples_explained.csv` có cột tiếng Việt.

## 1. Tính lại nhãn tham chiếu để làm gì?

Nhãn D4 gốc được tính với giả định pin TB47D. Khi thử TB48D, ngân sách năng lượng đã đổi; nhãn tham chiếu cũng cần được tính cho giả định mới nếu muốn đối chiếu cùng một tình huống. Nhãn D4 gốc vẫn giữ nguyên để làm chuẩn so sánh chính. File mới là phân tích bổ sung.

Đã thực hiện trên toàn bộ **14.700 ID**, hai loại pin và 254 điểm quét mỗi pin: **7.467.600 điểm**, trong đó 7.414.866 hợp lệ. Mỗi điểm có cả REF-1 và REF-2. Có 65.024 dòng thước đo, đủ hai cách gộp marginal và hai cách xác định thành viên nhóm: giữ nhóm D4 gốc hoặc tính lại theo thế giới đã đổi.

Tại đầu vào gốc, TB47D tái tạo đúng nhãn D4. Với TB48D, **2.099 nhãn REF-1** và **3.188 nhãn REF-2** thay đổi. Các số này được đếm riêng theo từng REF, không cộng thành tổng số ID.

Ví dụ ID 5: năng lượng pin khả dụng TB47D khoảng 26,07 Wh, TB48D khoảng 33,91 Wh. Nhãn REF-1 từ `marginal` (sát ngưỡng) chuyển thành `feasible` (khả thi theo tham chiếu năng lượng). Kết luận của hệ thống còn phụ thuộc các quy tắc khác, không nhất thiết phải là FLY chỉ vì nhãn tham chiếu khả thi.

### Các định nghĩa được giữ nhất quán

- REF-1 vẫn là mô hình D2 đã chốt cộng khoản dự phòng D4; REF-2 vẫn dùng công thức vật lý và hệ số 7,44 đã chốt. Không huấn luyện hay hiệu chỉnh lại.
- Khi thay đầu vào nhiệm vụ, nhu cầu và năng lượng khả dụng được tính lại. Sai số phần dư dùng để thử ứng viên không tự đưa sang hai REF; đây là sai số của ứng viên, không phải một số đo nhu cầu chung cho cả ba mô hình.
- Khi quét mức dự trữ của ứng viên, chuẩn dự trữ REF giữ 20%. Như vậy phép so sánh không tự đổi cả yêu cầu dùng để chấm.
- REF-2 chưa có mô hình nhu cầu theo gió đã được kiểm chứng. Nó giữ nguyên công thức, không tự thêm tác động gió. Cấu hình CMU giữ khối lượng theo hồ sơ hiện có, không tự thêm hiệu chỉnh khối lượng pin mới.

## 2. Kiểm tra đề xuất điều chỉnh

Chọn trước toàn bộ **2.245 ID** có nhãn sát ngưỡng theo ít nhất một REF D4, thử cả hai pin thành **4.490 cặp ID–loại pin**. Danh sách và quy tắc nằm trong `selection_manifest.json`, được ghi trước khi thử bất kỳ thay đổi nào.

Thử từng yếu tố một: tăng mức pin theo lưới 1 điểm phần trăm; đổi pin TB48D; chờ gió giảm hoặc nhiệt độ phù hợp khi áp dụng được; giảm tải và tốc độ theo các mức có trong dữ liệu; rút ngắn đường bay theo lưới 10 m trong phạm vi mô hình. Bước chia lưới chỉ là lựa chọn tính toán, không phải độ chính xác cảm biến.

Đã đánh giá **244.596 thay đổi áp dụng được**, giữ cả thử không thành công và không áp dụng trong **259.299 dòng**. Hệ thống đưa ra **2.915 đề xuất** trên **2.383 cặp ID–loại pin**. Một cặp có thể có nhiều đề xuất.

Hệ thống chọn mức thay đổi nhỏ nhất trong từng biện pháp giúp ứng viên đạt FLY, rồi mới kiểm tra bằng hai REF. Kết quả REF không được dùng để lọc trước hoặc chọn mức thay đổi. “Nhỏ nhất” chỉ đúng trong lưới đã khai và từng biện pháp; không khẳng định tối ưu liên tục hoặc so sánh chi phí sạc pin với giảm hàng.

| Pin | Đề xuất ứng viên đưa ra | Qua REF-1 theo nhãn feasible | Qua REF-2 theo nhãn feasible |
|---|---:|---:|---:|
| TB47D | 1.838 | 1.676 | 572 |
| TB48D | 1.077 | 1.077 | 681 |

Đây là đánh giá theo tham chiếu mô phỏng, không phải tỷ lệ chuyến bay thực tế thành công. Có bảng riêng cho cách gộp marginal vào feasible và cho nhóm trong/ngoài phạm vi dữ liệu.

### Ví dụ cần hiểu

- **ID 41/TB47D:** tăng mức pin từ 44,17% lên 47% làm hệ thống đổi NO_FLY → FLY. REF-1 đồng ý, REF-2 vẫn cho rằng chưa đủ năng lượng. Đề xuất này được giữ trong kết quả để báo cáo sự bất đồng.
- **ID 10/TB47D:** nếu nhiệm vụ cho phép giảm quãng đường khoảng 775,59 m xuống 610 m, hệ thống đổi CONDITIONAL → FLY và cả hai REF đều đạt. Đây vẫn là giả định điều chỉnh nhiệm vụ, không khẳng định tuyến thực tế có thể tự động rút ngắn như vậy.
- Giảm tốc độ đã được thử nhưng không tạo đề xuất đạt FLY trong nhóm này. Không mặc định bay chậm hơn luôn tiêu thụ ít năng lượng vì thời lượng dự kiến cũng tăng.
- Không có ca gió vượt HR-1 trong tập marginal chính đã chọn, nên hành động chờ gió M3 không áp dụng; tỷ lệ khi mẫu số bằng 0 được ghi NA.

## 3. Các file dùng để kiểm tra

- `matched_baseline_labels.csv`: từng ID ở đầu vào gốc cho cả hai pin, nhãn trước/sau và năng lượng tham chiếu.
- `matched_reference_labels.csv.gz`: đủ nhãn của 7.467.600 điểm đã lưu. File lớn, dùng Python đọc theo lô.
- `fixed_vs_matched_metrics.csv`: đối chiếu nhãn cũ/mới trên cùng nhóm gốc.
- `matched_reference_metrics.csv`: đủ thước đo cho nhóm gốc và nhóm tính lại.
- `counterfactual_case_summary.csv`: từng cặp ID/pin có bao nhiêu đề xuất và có đề xuất qua REF hay không.
- `counterfactual_proposals.csv`: mọi đề xuất ứng viên đã đưa ra, kể cả bị REF đánh giá không đạt.
- `counterfactual_trials.csv.gz`: cả các thử nghiệm không thành công/không áp dụng.
- `counterfactual_validation_summary.csv`: tử số, mẫu số, phạm vi dữ liệu và hai cách gộp marginal.
- `input_manifest.json`, `selection_manifest.json`, `run_status.json`, `protocol_snapshot.yaml`, `code_snapshot/`: nguồn, kế hoạch và hash để kiểm tra lại.

236 kiểm thử liên quan đã qua, gồm 47 kiểm thử mới. Đã đối chiếu độc lập toàn bộ 2.915 đề xuất bằng D3 và hai công thức tham chiếu, kiểm tra mức thay đổi nhỏ nhất theo lưới và 27 hash file đầu ra. Bộ tính mới tái tạo đúng quyết định/năng lượng hợp lệ của toàn bộ điểm OAT đã lưu.

## 4. Chạy lại phần này

Tại `D:/IdeaProjects/NCKH`:

```powershell
.\.venv\Scripts\python.exe -m src.complete_robustness --oat-run reports/d5/oat_all_scenarios_20261025_01 --out reports/d5/matched_counterfactual_my_run
```

Thư mục output phải mới. Lệnh đọc lại kết quả OAT, tính nhãn tham chiếu mới và thử các thay đổi đã khai; không sinh Monte Carlo mới.

## 5. Trạng thái

Lần chạy sử dụng protocol **v0.6.0**, được lưu nguyên trong thư mục kết quả. Bản hiện tại **v0.6.1** chỉ cập nhật trạng thái đã thực hiện và đường dẫn bằng chứng, không đổi quy tắc/lưới/thước đo. Các phần kỹ thuật D5 đã có bằng chứng phát triển; kiểm tra chéo của Phát, chốt quy trình và nghiệm thu cuối còn PENDING.

Cấu hình CMU vượt MTOW và các kết quả này không cấp quyền bay ngoài thực tế. Những bất đồng giữa REF-1 và REF-2 phải được báo cáo; không chọn cách tham chiếu có kết quả đẹp hơn để thay thế các kết quả còn lại.
