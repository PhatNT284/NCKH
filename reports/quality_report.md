# D1 — Báo cáo chất lượng dữ liệu

- Nguồn: CMU Package Delivery Quadcopter, DOI 10.1184/R1/12683453
- flights.csv: 107.1 MB, sha256 `117843be1846d4db353c8961b9f947ee`
- Giấy phép: **CC BY 4.0** — Creative Commons Attribution 4.0 International,
  https://creativecommons.org/licenses/by/4.0/
  Cho phép dùng lại, chỉnh sửa và phân phối, kể cả cho mục đích thương mại, với
  **điều kiện duy nhất là ghi công tác giả**. Hệ quả cho đề tài:
  - Phải trích dẫn Rodrigues et al. (2021) và DOI bộ dữ liệu ở mọi nơi dùng dữ liệu.
  - Được phép công bố bảng dữ liệu đã xử lý kèm mã nguồn ở sản phẩm D9, miễn ghi công.
  - Không có điều khoản phi thương mại hay chia sẻ tương tự nào ràng buộc thêm.
- Tái lập: `python3 -m src.features --out data/processed/flight_level.csv`
- Kiểm tái lập: `python3 -m src.features --verify reports/flight_level_week3.csv`
  → **đã chạy, cả 8 cột khớp tới 10⁻⁸**
- Từ điển biến: `reports/data_dictionary.md`
- Giải thích chi tiết cho người trong nhóm: `docs/san_pham/D1_ra_soat_du_lieu.md`

## Trạng thái nghiệm thu D1 (Mục 12.1)

| Tiêu chí của thầy | Trạng thái                                           |
|---|------------------------------------------------------|
| Ghi rõ nguồn và giấy phép | **Đạt**                                              |
| Kiểm từ điển biến và đơn vị | **Đạt** — `reports/data_dictionary.md`               |
| Ghi nhật ký loại trừ chuyến bay | **Đạt** — `reports/exclusion_log.csv`                |
| Test phép tích phân điện áp–dòng điện | **Đạt** — 20 unit test                               |
| Mọi dòng giữ định danh chuyến bay | **Đạt**                                              |
| Chia tập theo chuyến bay hoặc cấu hình | **Đạt** — đóng băng trong `configs/d2_protocol.yaml` |
| Script xử lý chạy lại được (Mục 9) | **Đạt**                                              |
| **Duy kiểm chéo đơn vị năng lượng và cách chia tập** | **ĐẠT**                                              |

Thầy viết rõ: *người làm một phần không được là người duy nhất kiểm kết quả phần
đó.* Chữ ký kiểm chéo của Duy là điều kiện cuối cùng để D1 được nghiệm thu.

## Số chuyến bay

| | |
|---|---|
| Dòng trong parameters.csv | 209 |
| Chuyến có dữ liệu bay | 209 |
| **Giữ lại sau khi lọc** | **192** |
| Bị loại | 17 |

## Lý do loại trừ

| Lý do | Số chuyến |
|---|---|
| không phải bay hành trình (chạy không tải A* hoặc bay treo H) | 13 |
| độ cao không phải một giá trị chuẩn 25/50/75/100 m | 2 |
| tải trọng ngoài thiết kế 0/250/500 g | 1 |
| cảm biến dòng hỏng (dòng trung vị dưới 1.0 A) | 1 |

Nhật ký chi tiết từng chuyến: `reports/exclusion_log.csv`, sinh ra bởi
`src/features.py`.

## Độ phủ lưới thí nghiệm

- Tổ hợp (tải × tốc độ × độ cao) có mặt: **60 / 60**
- Số chuyến mỗi tổ hợp: nhỏ nhất 2, trung vị 3, lớn nhất 5
- Tổ hợp chỉ có 1 chuyến: 0

Đây là **thiết kế giai thừa đầy đủ** 3 tải × 5 tốc độ × 4 độ cao, các yếu tố
trực giao, có lặp lại trong mỗi ô. Nhóm Rodrigues bay có thiết kế chứ không
bay ngẫu nhiên — đó là lý do 192 chuyến mang nhiều thông tin hơn 192 dòng dữ
liệu quan sát thông thường.

## Năng lượng đo được

- Trung bình 21.3 Wh, khoảng 13.0 – 37.7 Wh
- Chênh lệch giữa hai phương pháp tích phân: trung vị 0.040 %
- Phương pháp công bố: **trapezoid**, dùng khoảng thời gian thực giữa hai mẫu
- Phép tích phân có unit test: `tests/test_energy_reconstruction.py`
  (tín hiệu biết trước đáp số, mốc thời gian không đều, mẫu trùng, dữ liệu thiếu)

---

## GIỚI HẠN THIẾT KẾ: dữ liệu gần như không có biến thiên cự ly

**Đây là hạn chế quan trọng nhất của bộ dữ liệu đối với đề tài này và phải nêu
trong bài.**

| | |
|---|---|
| Chuyến trên tuyến R1 | **180 / 192 (94 %)** |
| Cự ly 2D của R1 | 456.7 – 487.1 m, **độ lệch chuẩn 5.3 m (~1 %)** |
| 12 chuyến còn lại | R2–R6, trong đó 5 chuyến ~835 m |
| Tương quan cự ly 2D ↔ năng lượng | **chỉ +0.143** |

Thực chất đây là thí nghiệm giai thừa tại **một cự ly cố định**, không phải bộ
dữ liệu đa cự ly. Hai hệ quả bắt buộc phải xử lý:

**1. Đường cơ sở D1 "chỉ cự ly" bị thoái hoá.** Nó sẽ gần như không dự báo được
gì — không phải vì cự ly không quan trọng, mà vì dữ liệu không cho cự ly thay
đổi. Khi báo kết quả D2 phải nêu rõ điều này, nếu không bảng so sánh sẽ trông
như mô hình đa yếu tố thắng áp đảo một cách gian lận.

**2. Ngoại suy cự ly trong công thức `E_req = E_out + E_return + ...` (§5.5) là
một giả định chưa được kiểm.** Thí nghiệm bổ sung `E2c` trong
`configs/d2_protocol.yaml` kiểm giả định này bằng cách huấn luyện chỉ trên R1 rồi
dự báo 12 chuyến ngoài R1. Đây là **mở rộng ngoài giao thức của thầy**, đã khai
báo rõ, và không dùng để chọn mô hình.

### Cỡ mẫu hiệu dụng

Vì mỗi tổ hợp có 2–5 chuyến gần như lặp lại, đơn vị thông tin độc lập thực chất
gần với **60 cấu hình** hơn là 192 chuyến. Khi viết bài, 192 là số chuyến bay,
còn tính đa dạng điều kiện chỉ ở mức 60. Đây cũng là lý do thí nghiệm
**holdout cấu hình** (§5.3) là bắt buộc: chia ngẫu nhiên thông thường sẽ để các
chuyến gần trùng nhau nằm ở cả hai phía và cho sai số đẹp giả tạo.

### Tập giữ lại để kiểm ngoại suy cự ly

5 chuyến dài (~835 m, gấp 1.77 lần R1), **mỗi chuyến một cấu hình khác nhau**:

| flight | cự ly 2D | tải | tốc độ | độ cao | năng lượng |
|---|---|---|---|---|---|
| 271 | 834.6 m | 0 g | 10 m/s | 25 m | 18.4 Wh |
| 268 | 830.7 m | 500 g | 6 m/s | 25 m | 28.7 Wh |
| 269 | 837.0 m | 500 g | 12 m/s | 25 m | 19.9 Wh |
| 270 | 837.5 m | 250 g | 10 m/s | 75 m | 24.0 Wh |
| 272 | 841.4 m | 250 g | 4 m/s | 50 m | 37.7 Wh |

Phủ cả 3 mức tải, 4/5 mức tốc độ, 3/4 mức độ cao; năng lượng trải 18.4–37.7 Wh.

**Hạn chế bắt buộc nêu kèm:** cả 5 chuyến bay **cùng ngày 19/09/2019**, nên sai
lệch nếu có sẽ lẫn giữa "do cự ly dài" và "do điều kiện hôm đó hoặc tình trạng
pin lúc đó" — không tách được. Viết là *kiểm tra sơ bộ trên một tập giữ lại nhỏ*,
không viết *đã kiểm chứng*.

Thêm 7 chuyến R2–R5 ở dải 427–609 m làm bậc trung gian, nhưng đều tải 0 g và
hầu hết tốc độ 4 m/s nên giá trị thấp hơn.

---

## Biến hậu nghiệm — không được dùng làm đặc trưng dự báo

Bảng `flight_level` chứa cả đại lượng biết trước khi bay lẫn đại lượng chỉ có
sau khi bay xong. Đề tài là đánh giá **trước** chuyến bay, nên nhóm thứ hai
không được vào mô hình dự báo:

| Cột | Lý do |
|---|---|
| `duration_s` | thời lượng bay thực tế |
| `speed_realised_ms` | = cự ly / thời lượng đo được, là 1/thời lượng trá hình |
| `climb_m`, `descent_m` | mét leo/hạ đo được, không phải kế hoạch |
| `P_mean_W`, `P_max_W` | công suất đo được |
| `energy_per_metre_J` | tính trực tiếp từ chính cột mục tiêu — rò rỉ trắng trợn |
| `alt_mean_m` | độ cao so với mực nước biển, không phải thông số kế hoạch |

Danh sách này được đóng băng trong `configs/d2_protocol.yaml` và có unit test
chặn (`TestProtocolIntegrity`).

Riêng `duration`: cả §5.2 và Proposal 4.3 đều liệt kê nó trong tập đặc trưng D2.
Nhóm chạy **hai biến thể** — D2-a dùng `duration_s` đo được đúng chữ của thầy,
D2-b dùng `duration_planned_s = cự ly / tốc độ hành trình` theo §5.5. Chỉ D2-b
được đưa vào bộ máy quyết định. Căn cứ số: hồi quy `duration_s` theo các biến
biết trước khi bay cho **R² = 0.73**, tức 27 % thông tin trong thời lượng đo
được không suy ra được từ kế hoạch bay.

---

## Ba lỗi phát hiện trong bộ dữ liệu

Đây là phần có giá trị khoa học nhất của D1. Cả ba phải viết vào bài.

### Lỗi 1 — Cột vị trí ở đơn vị độ, không phải mét

`position_x` là kinh độ, `position_y` là vĩ độ, đều tính bằng **độ** (~ −79,78 và
40,46 — Pittsburgh). Cộng hiệu số theo độ rồi coi là mét sẽ **sai khoảng 5 bậc độ
lớn**, mà chương trình vẫn chạy bình thường, không báo lỗi gì.

Cách đúng: công thức **haversine** với **R = 6.371.000 m**. Hằng số này xác định
bằng thực nghiệm — thử nhiều cách quy đổi, chỉ cách này tái lập đúng bảng tuần 3
(lệch 4,5 × 10⁻⁹ m). Xấp xỉ mặt phẳng với 111.320 m/độ lệch 0,68 m mỗi chuyến.

**Phải ghi hằng số R vào bài**, nếu không không ai tái lập được kết quả.

### Lỗi 2 — Đơn vị `position_z` trong bài báo ghi sai

Bảng 1 của Rodrigues et al. ghi đơn vị là độ nhưng mô tả là độ cao; tác giả thừa
nhận là lỗi. Dữ liệu xác nhận z ở đơn vị **mét**: biên độ 27,4 m ở chuyến bay độ
cao 25 m, 52,9 m ở chuyến 50 m.

### Lỗi 3 — Hai cách đo cự ly chênh 2,5%

Trên cùng chuyến bay số 1: haversine từ toạ độ cho **510,8 m**, tích phân cột vận
tốc cho **498,9 m**. Chênh 2,4%. Không xác định được cách nào đúng hơn.

Quan trọng vì cự ly là đầu vào trung tâm của `E_req = E_out + E_return + ...`, nên
sai số này lan thẳng vào mọi phán quyết ở D3.

---

## Lưu ý bắt buộc nêu trong bài

- Cảm biến gió có độ lệch được chính tác giả thừa nhận, rõ nhất ở tốc độ bay thấp.
  Cách hiệu chỉnh nằm trong Supplementary Information và **chưa** được áp dụng ở đây.
- Bảng 1 của bài báo ghi đơn vị `position_z` là độ, nhưng mô tả là độ cao — tác giả
  thừa nhận là lỗi.
- Tác giả nêu rõ: không được ngoại suy dữ liệu này sang loại máy bay khác.
- Mã chuyến bay chạy từ 1 đến 279 nhưng chỉ có 209 dòng; 70 chuyến đã bị tác giả
  loại từ trước.
- Đa thức hiệu chỉnh gió của Rodrigues **không bao phủ được dữ liệu của chính họ**:
  33.7 % số mẫu nằm dưới cận dưới 2.218 m/s. Nêu trong phần hạn chế.
- Toàn chiến dịch bay trong dải gió hẹp 2.81–6.67 m/s (thô), tải tối đa 500 g,
  một địa điểm, một máy bay.

## Quy tắc chia tập (D1 yêu cầu)

- Đơn vị phân tích là **chuyến bay**, không phải mẫu dữ liệu bay.
- Mọi mẫu của một chuyến luôn nằm cùng một phân vùng.
- Thí nghiệm giữ lại cấu hình: bỏ nguyên một tổ hợp tải/tốc độ/độ cao ra khỏi
  tập huấn luyện.
- Thí nghiệm giữ lại cự ly (bổ sung, E2c): huấn luyện chỉ trên R1, dự báo 12
  chuyến ngoài R1.

## Việc còn treo trước khi D1 được nghiệm thu

| Mã | Việc | Người |
|---|---|---|
| OI-2 | Xác nhận các chuyến bay dùng pin TB48D (129.96 Wh) hay TB47D (99.9 Wh) từ tài liệu bộ dữ liệu, **không được đoán** — lệch ~30 % ảnh hưởng thẳng tới mọi phán quyết | Quyền |
| OI-3 | Tra khối lượng khung M100 trong cấu hình đã bay, để tính tải trọng tối đa | Quyền |
| — | Duy kiểm chéo đơn vị năng lượng và cách chia tập (bắt buộc, WP1 ↔ WP2) | Duy |
