# D1 — Rà soát bộ dữ liệu và dựng lại năng lượng

**Người làm:** Phát (WP1) · **Người kiểm chéo:** Duy · **Tuần 1–3**

---

## 1. D1 để làm gì

Mục tiêu một câu: **biến dữ liệu bay thô thành một bảng sạch, mỗi chuyến bay một
dòng, trong đó có cột "chuyến này tốn bao nhiêu Wh".**

Vì sao phải làm trước mọi thứ khác: cột năng lượng đó là **mục tiêu dự báo** của
toàn bộ D2, và là đầu vào của công thức quyết định ở D3. Nếu nó sai, mọi thứ phía
sau sai theo mà không ai biết.

Thầy đặt một cổng chặn cứng cho việc này (Mục 12.1):

> *Chưa đạt D1 thì không được báo điểm mô hình.*

---

## 2. Dữ liệu gốc có gì

Bộ dữ liệu CMU, tải từ https://doi.org/10.1184/R1/12683453, giấy phép **CC BY 4.0**
(được dùng lại tự do, chỉ cần ghi công tác giả).

Gồm hai file:

**`parameters.csv`** — 209 dòng, mỗi dòng một chuyến bay. Ghi *ý định* của chuyến
bay: tải trọng bao nhiêu gram, tốc độ ra lệnh bao nhiêu m/s, bay ở độ cao nào,
tuyến nào, ngày giờ nào.

**`flights.csv`** — 107 MB, hơn 240 nghìn dòng. Mỗi dòng là **một khoảnh khắc**
trong một chuyến bay, ghi khoảng 10 lần mỗi giây. Có điện áp, dòng điện, vị trí,
vận tốc, gió, gia tốc...

Nói cách khác: `parameters.csv` là *kế hoạch bay*, `flights.csv` là *nhật ký ghi
âm toàn bộ chuyến bay*.

### Thiết kế thí nghiệm

Nhóm Rodrigues không bay bừa. Họ bay theo **lưới giai thừa đầy đủ**:

- 3 mức tải: 0 g, 250 g, 500 g
- 5 mức tốc độ: 4, 6, 8, 10, 12 m/s
- 4 mức độ cao: 25, 50, 75, 100 m

3 × 5 × 4 = **60 tổ hợp**, và cả 60 đều có mặt, mỗi tổ hợp bay lặp 2–5 lần.

Đây là điểm mạnh lớn. Các yếu tố **trực giao** — tải, tốc độ, độ cao thay đổi độc
lập nhau — nên tách được ảnh hưởng riêng của từng cái. Dữ liệu quan sát ngẫu nhiên
thường không làm được điều này.

---

## 3. Tính năng lượng như thế nào

Đây là phần lõi của D1. Công thức thầy ghi ở §4.2:

```
P_t = V_t × I_t                    (công suất tức thời)
E   = Σ  V_t × I_t × Δt            (năng lượng cả chuyến)
```

### Giải thích bằng lời

Công suất điện = điện áp × dòng điện. Đơn vị watt (W).

Ví dụ: pin đang ở 22 V, động cơ rút 18 A → công suất lúc đó là 22 × 18 = **396 W**.

Năng lượng = công suất × thời gian. Nếu giữ nguyên 396 W trong 180 giây thì tốn
396 × 180 = 71.280 joule.

Nhưng công suất **không** cố định — lúc cất cánh rút rất nhiều, lúc bay bằng ít
hơn, lúc hạ cánh lại khác. Nên phải cộng dồn từng khoảnh khắc nhỏ:

```
mẫu 1: 396 W × 0,1 s = 39,6 J
mẫu 2: 402 W × 0,1 s = 40,2 J
mẫu 3: 388 W × 0,1 s = 38,8 J
...cộng hết hơn 1.800 mẫu
```

Đó chính là ý nghĩa của dấu Σ trong công thức. Trong toán gọi là **tích phân**.

### Hai chi tiết kỹ thuật, đều quan trọng

**Dùng khoảng thời gian thực giữa hai mẫu.** Thầy ghi rõ ở §4.2: nếu mốc thời
gian không đều thì phải dùng hiệu số thực tế, không được giả định tần số lấy mẫu
cố định. Kiểm tra thực tế: tần số lấy mẫu dao động từ 5,3 đến 9,1 Hz giữa các
chuyến bay — **không đều thật**. Nếu giả định đều thì sai.

**Dùng quy tắc hình thang, không dùng tổng Riemann.** Hai cách cộng dồn hơi khác
nhau. Riemann lấy giá trị đầu mỗi đoạn; hình thang lấy trung bình hai đầu, chính
xác hơn khi công suất đang thay đổi. Hai cách lệch nhau **0,040%** — rất nhỏ, và
chính sự nhỏ đó là bằng chứng dữ liệu lấy mẫu đủ dày.

Đổi đơn vị cuối: joule chia 3600 ra watt-giờ (Wh), vì dung lượng pin ghi theo Wh.

### Kết quả

192 chuyến bay, năng lượng trung bình **21,3 Wh**, trải từ **13,0 đến 37,7 Wh**.

---

## 4. Vì sao từ 209 chuyến còn 192

Loại 17 chuyến, mỗi chuyến có lý do ghi rõ trong `reports/exclusion_log.csv`:

| Lý do | Số chuyến | Giải thích |
|---|---|---|
| Không phải bay hành trình | 13 | Tuyến bắt đầu bằng `A` (chạy không tải) hoặc `H` (bay treo tại chỗ). Không phải nhiệm vụ giao hàng |
| Độ cao ngoài lưới | 2 | Không thuộc 25/50/75/100 m |
| Tải ngoài lưới | 1 | Không thuộc 0/250/500 g |
| Cảm biến dòng hỏng | 1 | Dòng trung vị dưới 1,0 A — máy bay không thể bay với dòng nhỏ vậy, chắc chắn cảm biến lỗi |

Thầy bắt buộc ghi nhật ký loại trừ (Mục 12.1). Lý do: người đọc phải kiểm được
nhóm có loại bỏ chuyến bay một cách tuỳ tiện để làm đẹp kết quả hay không.

Lưu ý thêm: mã chuyến bay chạy từ 1 đến 279 nhưng chỉ có 209 dòng — **70 chuyến
đã bị chính tác giả loại từ trước**. Nhóm không biết lý do, phải nêu trong hạn chế.

---

## 5. Ba lỗi tìm thấy trong bộ dữ liệu

Đây là phần có giá trị khoa học nhất của D1. Cả ba đều phải viết vào bài.

### Lỗi 1 — Cột vị trí ở đơn vị độ, không phải mét

`position_x` = **kinh độ**, `position_y` = **vĩ độ**, đều tính bằng **độ**. Giá trị
thực tế khoảng −79,78 và 40,46 — đó là toạ độ Pittsburgh.

Nếu cứ thế trừ hai toạ độ liên tiếp rồi coi kết quả là mét, ta được con số kiểu
0,0015 — **sai khoảng 5 bậc độ lớn**. Mà chương trình vẫn chạy bình thường, không
báo lỗi gì. Đây đúng là loại lỗi nguy hiểm nhất: sai mà im lặng.

Cách đúng: dùng công thức **haversine** với bán kính Trái Đất **R = 6.371.000 m**.
Con số R này không phải chọn bừa — thử nhiều cách quy đổi khác nhau, chỉ haversine
với R = 6.371.000 tái lập đúng bảng tuần 3 (lệch 4,5 × 10⁻⁹ m, tức trùng khít).
Xấp xỉ mặt phẳng với hệ số 111.320 m/độ lệch 0,68 m mỗi chuyến — nhỏ nhưng đủ để
người khác không tái lập được.

**Phải ghi R = 6.371.000 m vào bài**, nếu không không ai lặp lại được kết quả.

### Lỗi 2 — Đơn vị `position_z` trong bài báo ghi sai

Bảng 1 của Rodrigues et al. ghi đơn vị `position_z` là **độ**, nhưng mô tả nó là
**độ cao**. Tác giả thừa nhận đây là lỗi.

Dữ liệu xác nhận z ở đơn vị **mét**: chuyến bay ở độ cao 25 m có biên độ z là
27,4 m; chuyến ở 50 m có biên độ 52,9 m. Khớp.

### Lỗi 3 — Hai cách đo cự ly chênh nhau 2,5%

Cự ly tính bằng haversine từ toạ độ: **510,8 m** (chuyến bay số 1).
Cự ly tính bằng tích phân cột vận tốc: **498,9 m**. Cùng một chuyến bay.

Chênh 2,4%. Không biết cách nào đúng hơn — chỉ biết hai cảm biến độc lập không
đồng ý với nhau.

Vì sao quan trọng: cự ly là đầu vào trung tâm của công thức `E_req = E_out +
E_return + ...` ở D3. Sai số 2,5% này lan thẳng vào mọi phán quyết. Phải nêu
trong mục hạn chế.

---

## 6. Hạn chế lớn nhất: dữ liệu gần như không có biến thiên cự ly

**Đây là điều quan trọng nhất cả nhóm cần biết.**

| | |
|---|---|
| Chuyến trên tuyến R1 | **180 / 192 (94%)** |
| Cự ly của R1 | 456,7 – 487,1 m, **độ lệch chuẩn 5,3 m (~1%)** |
| 12 chuyến còn lại | R2–R6, trong đó 5 chuyến khoảng 835 m |

Nghĩa là: đây là thí nghiệm giai thừa tại **một cự ly cố định**, không phải bộ dữ
liệu đa cự ly.

**Hai hệ quả:**

1. Mô hình D1 "chỉ cự ly" bị thoái hoá — xem `D2_mo_hinh.md`.
2. Việc ngoại suy sang nhiệm vụ dài hơn là **giả định chưa được kiểm**. Thí nghiệm
   E2c trong D2 kiểm nó, và kết quả không tốt.

### Cỡ mẫu hiệu dụng

Mỗi tổ hợp có 2–5 chuyến gần như lặp lại nhau. Nên đơn vị thông tin **độc lập**
thực chất gần với **60 cấu hình** hơn là 192 chuyến.

Khi viết bài: 192 là số chuyến bay, nhưng tính đa dạng điều kiện chỉ ở mức 60.
Nói 192 mà không nói 60 là thổi phồng.

---

## 7. Biến hậu nghiệm — cái bẫy phải tránh

Bảng kết quả có cả hai loại cột trộn lẫn:

**Biết TRƯỚC khi cất cánh** — dùng được để dự báo:
`payload_num`, `speed_num` (tốc độ ra lệnh), `altitude_num`, cự ly tuyến, gió dự báo

**Chỉ có SAU khi bay xong** — không được dùng:

| Cột | Vì sao cấm |
|---|---|
| `duration_s` | thời lượng bay thực tế |
| `speed_realised_ms` | = cự ly ÷ thời lượng, là 1/thời lượng trá hình |
| `climb_m`, `descent_m` | mét leo/hạ đo được |
| `P_mean_W`, `P_max_W` | công suất đo được |
| `energy_per_metre_J` | tính trực tiếp từ cột mục tiêu — rò rỉ trắng trợn |
| `alt_mean_m` | độ cao so với mực nước biển, không phải thông số kế hoạch |

Đề tài tên là đánh giá **trước chuyến bay**. Mô hình cần biết thời lượng bay thực
tế mới chạy được thì vô dụng, vì lúc cần dùng thì chưa có con số đó.

Danh sách cấm này đóng băng trong `configs/d2_protocol.yaml` và **có unit test
chặn** (`TestProtocolIntegrity`) — nếu ai vô tình thêm biến cấm vào mô hình, test
sẽ đỏ.

---

## 8. Kiểm chứng: làm sao biết code đúng

Hai lớp kiểm.

**Lớp 1 — unit test.** 20 test cho riêng phép tích phân, trong
`tests/test_energy_reconstruction.py`. Cách kiểm: đưa vào tín hiệu đã biết đáp số
tính tay, xem code có ra đúng không.

Ví dụ: công suất 100 W giữ nguyên trong 100 giây phải ra đúng 10.000 J. Hoặc:
mốc thời gian không đều `[0, 0,5, 3,0, 3,1, 7,0, 10,0]` với công suất 50 W phải
ra 500 J — test này bắt lỗi giả định tần số lấy mẫu đều.

Thêm 8 test riêng cho phép đổi độ sang mét, trong đó một test chuyên bắt đúng lỗi
đã từng mắc: trừ thẳng theo độ cho ~0,0009 còn kết quả thật phải ~100 m.

**Lớp 2 — kiểm tái lập.** Chạy:

```bash
python3 -m src.features --verify reports/flight_level_week3.csv
```

Code đọc `flights.csv` từ đầu, dựng lại toàn bộ bảng, rồi so với bảng tuần 3.
Kết quả: cả 8 cột khớp tới 10⁻⁸.

Đây là thứ thầy đòi ở Mục 12.1: *"script xử lý chạy lại được"*.

---

## 9. Còn thiếu gì

| Việc | Người |
|---|---|
| Từ điển biến đầy đủ (`reports/data_dictionary.md`) | Phát |
| **Duy kiểm chéo đơn vị năng lượng và cách chia tập** | Duy |
| Xác nhận pin TB48D (129,96 Wh) hay TB47D (99,9 Wh) từ tài liệu bộ dữ liệu — **không được đoán**, lệch 30% ảnh hưởng mọi phán quyết ở D3 | Quyền |
| Tra khối lượng khung M100 để tính tải trọng tối đa | Quyền |

Thầy viết rõ: **người làm một phần không được là người duy nhất kiểm phần đó.**
Nên chữ ký của Duy là bắt buộc, không phải thủ tục.
