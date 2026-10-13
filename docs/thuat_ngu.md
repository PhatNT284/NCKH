# Thuật ngữ

Tra nhanh khi gặp từ lạ trong `D1_du_lieu.md` hoặc `D2_mo_hinh.md`.

---

## Về dữ liệu

**Telemetry** — dữ liệu cảm biến ghi liên tục trong lúc bay. Ở đây khoảng 10 lần
mỗi giây: điện áp, dòng điện, vị trí, vận tốc, gió.

**Cấp chuyến bay (flight-level)** — mỗi chuyến bay gộp thành đúng một dòng. Ngược
với cấp mẫu, nơi mỗi khoảnh khắc là một dòng. Đơn vị phân tích của đề tài là cấp
chuyến bay.

**Thiết kế giai thừa đầy đủ (full factorial)** — thí nghiệm thử mọi tổ hợp của
các yếu tố. Ở đây 3 tải × 5 tốc độ × 4 độ cao = 60 tổ hợp, tất cả đều có.

**Trực giao (orthogonal)** — các yếu tố thay đổi độc lập nhau. Nhờ vậy tách được
ảnh hưởng riêng của tải, của tốc độ, của độ cao. Dữ liệu quan sát ngẫu nhiên
thường không trực giao.

**Cỡ mẫu hiệu dụng** — số đơn vị thông tin thực sự độc lập. Ở đây 192 chuyến bay
nhưng chỉ 60 cấu hình khác nhau, nên cỡ mẫu hiệu dụng gần 60 hơn.

**Đặc trưng (feature)** — biến đầu vào của mô hình. Ví dụ tải trọng, tốc độ.

**Mục tiêu (target)** — cái cần dự báo. Ở đây là `energy_Wh`.

**Biến hậu nghiệm** — đại lượng chỉ biết được sau khi sự việc xảy ra. Ví dụ thời
lượng bay thực tế. Không được dùng làm đặc trưng cho mô hình dự báo trước.

---

## Về mô hình

**Hồi quy (regression)** — dự báo một con số liên tục. Khác phân loại, vốn dự báo
một nhãn.

**Hồi quy tuyến tính** — vẽ đường thẳng (hoặc mặt phẳng nhiều chiều) khớp nhất với
dữ liệu.

**Ridge** — hồi quy tuyến tính có thêm hình phạt cho hệ số quá lớn. Ngăn mô hình
phản ứng thái quá với nhiễu. Hợp với dữ liệu nhỏ.

**Alpha** — độ mạnh của hình phạt trong Ridge. Alpha lớn = phạt nặng = mô hình
"thận trọng" hơn. Phải thử nhiều giá trị để chọn.

**Hồi quy bền vững (robust regression)** — ít bị các điểm bất thường kéo lệch.
Huber là một loại.

**Random Forest** — xây nhiều cây quyết định rồi lấy trung bình. Bắt được quan hệ
phi tuyến và tương tác giữa các yếu tố.

**Siêu tham số (hyperparameter)** — tham số do người đặt trước khi huấn luyện, như
alpha của Ridge hay độ sâu cây của Random Forest. Khác với tham số mà mô hình tự
học từ dữ liệu.

**Baseline** — mô hình mốc để so sánh. Không nhằm dùng thật, chỉ để biết các mô
hình khác có hơn được gì không.

---

## Về đánh giá

**Tập huấn luyện / tập kiểm** — phần dữ liệu để mô hình học, và phần để kiểm. Mô
hình không được thấy tập kiểm lúc học.

**Cross-validation (CV)** — chia dữ liệu thành k phần, luân phiên lấy từng phần
làm tập kiểm. Mỗi điểm dữ liệu được kiểm đúng một lần. Dùng khi dữ liệu ít.

**Fold** — một phần trong cách chia đó.

**CV lồng (nested CV)** — CV bên trong CV. Vòng ngoài để đánh giá, vòng trong để
chọn siêu tham số. Cần thiết để việc chọn siêu tham số không chạm vào tập kiểm.

**Holdout** — giữ riêng một phần dữ liệu, không cho mô hình thấy.

**Holdout cấu hình** — giữ riêng cả một tổ hợp (tải × tốc độ × độ cao). Khó hơn
chia ngẫu nhiên vì mô hình phải đoán điều kiện chưa từng gặp.

**Rò rỉ dữ liệu (leakage)** — mô hình vô tình thấy đáp án lúc học. Kết quả trông
đẹp nhưng vô giá trị.

**Out-of-fold (OOF)** — dự báo cho một điểm dữ liệu, bởi mô hình chưa từng thấy
điểm đó. Phần dư OOF là nguyên liệu cho phân tích bất định.

**Phần dư (residual)** — hiệu giữa giá trị dự báo và giá trị thực.

**Quá khớp (overfitting)** — mô hình học thuộc nhiễu trong tập huấn luyện thay vì
học quy luật. Chạy tốt trên dữ liệu đã thấy, dở trên dữ liệu mới.

**Ngoại suy (extrapolation)** — dùng mô hình ngoài vùng dữ liệu nó được học. Rủi
ro cao, phải kiểm chứ không được giả định.

---

## Thước đo

**MAE** — sai số tuyệt đối trung bình. Trung bình của |dự báo − thực tế|. Cùng đơn
vị với mục tiêu (Wh).

**RMSE** — căn bậc hai của trung bình bình phương sai số. Phạt nặng các lần sai
lớn. Luôn ≥ MAE.

**Bias** — sai số **có dấu**, trung bình của (dự báo − thực tế).
Dương = đoán thừa (an toàn). Âm = đoán thiếu (nguy hiểm).
Nếu |bias| ≈ MAE thì mô hình sai lệch về **một phía duy nhất**.

**WAPE** — MAE quy ra phần trăm so với tổng giá trị thực. Dễ cảm nhận hơn MAE.

**MAPE** — sai số phần trăm trung bình. Không dùng ở đây vì nó bùng nổ khi giá trị
thực gần 0. Thầy khuyên dùng WAPE thay thế.

**R²** — tỉ lệ biến thiên được giải thích. Từ 0 đến 1. Dùng ở mục 3 của
`D2_mo_hinh.md` để kiểm xem thời lượng đo được có suy ra được từ kế hoạch không.

**Độ lệch chuẩn qua các fold** — kết quả dao động bao nhiêu giữa các lần chia. Nhỏ
= ổn định, đáng tin.

---

## Về quy trình nghiên cứu

**Tiền đăng ký (pre-registration)** — chốt giả thuyết, đặc trưng, thước đo trước
khi nhìn kết quả. Ngăn việc nhìn kết quả rồi mới nghĩ ra cách diễn giải cho đẹp.

**Điều kiện phủ định (falsification condition)** — viết sẵn "điều gì xảy ra thì
coi như giả thuyết sai". Thầy ghi sẵn cho cả bốn RQ.

**Đóng băng (freeze)** — chốt giao thức bằng văn bản, sau đó muốn đổi phải ghi lý
do và chạy lại. File `configs/d2_protocol.yaml`.

**Cổng chặn (gate)** — chưa xong việc A thì không được làm việc B. Ví dụ chưa đạt
D1 thì không báo điểm mô hình.

**Tái lập (reproducibility)** — chạy lại script phải ra đúng con số cũ. Kiểm bằng
`python3 -m src.features --verify`.

**Kiểm chéo (cross-check)** — người khác soát kết quả của mình. Thầy bắt buộc:
người làm một phần không được là người duy nhất kiểm phần đó.

**Unit test** — đoạn code kiểm tra code khác có đúng không, bằng cách đưa vào dữ
liệu đã biết đáp số.

---

## Về đề tài

**SoC (State of Charge)** — trạng thái sạc. Pin hiện còn bao nhiêu phần trăm so
với dung lượng đầy **hiện tại**.

**SoH (State of Health)** — trạng thái sức khoẻ. Dung lượng đầy hiện tại so với
dung lượng lúc pin còn mới. Pin càng cũ càng thấp.

**Biên dự trữ (reserve margin)** — phần năng lượng dư ra sau khi trừ nhu cầu
nhiệm vụ. Ký hiệu R (tỉ lệ) và M (Wh).

**Luật cứng (hard rule)** — ràng buộc an toàn không được phép vi phạm, bất kể mô
hình nói gì. Ví dụ gió vượt giới hạn nhà sản xuất → NO-FLY.

**Fail closed** — khi thiếu thông tin thì nghiêng về phía an toàn, tức từ chối bay,
chứ không mặc định cho bay.

**Cho bay nhầm (false-safe)** — hệ thống cấp phán quyết FLY cho nhiệm vụ thực chất
không khả thi. **Đây là lỗi nguy hiểm nhất và là thước đo an toàn chính của đề tài.**

**Từ chối không cần thiết** — hệ thống từ chối nhiệm vụ thực chất bay được. Gây
lãng phí nhưng không nguy hiểm.

**Nhãn sinh từ mô phỏng** — nhãn khả thi/không khả thi do mô hình tạo ra, không
phải kết quả bay thật. Trong bài **không bao giờ** được gọi là ground truth hay
kết quả thực tế.
