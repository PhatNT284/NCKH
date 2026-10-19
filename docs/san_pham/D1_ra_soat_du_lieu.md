# Sản phẩm D1 — Rà soát bộ dữ liệu và dựng lại năng lượng

> Tài liệu này về **sản phẩm bàn giao D1**. Đừng nhầm với **mô hình D1** (hồi quy
> chỉ cự ly) ở `../cach_lam/D1_chi_cu_ly.md`. Hai hệ đánh số khác nhau.

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

### Chi tiết 1 — Dùng khoảng thời gian thực giữa hai mẫu

Thầy ghi rõ ở §4.2: nếu mốc thời gian không đều thì phải dùng hiệu số thực tế,
không được giả định tần số lấy mẫu cố định.

Kiểm tra thực tế: tần số lấy mẫu dao động **5,3 đến 9,1 Hz** giữa các chuyến bay
— không đều thật. Giả định đều thì sai.

### Chi tiết 2 — Quy tắc hình thang là gì

Vấn đề: ta chỉ biết công suất **tại các điểm lấy mẫu**, không biết nó biến thiên
thế nào **giữa** hai điểm. Phải giả định.

Giả sử hai mẫu liên tiếp:

```
t = 0,00 s  →  P = 400 W
t = 0,12 s  →  P = 440 W
```

Năng lượng tiêu tốn trong 0,12 giây đó là bao nhiêu?

**Cách 1 — tổng Riemann (lấy giá trị đầu đoạn):**
Giả định công suất giữ nguyên 400 W suốt đoạn.

```
400 W × 0,12 s = 48,0 J
```

**Cách 2 — quy tắc hình thang (lấy trung bình hai đầu):**
Giả định công suất tăng đều từ 400 lên 440 W.

```
(400 + 440) / 2 × 0,12 s  =  420 × 0,12  =  50,4 J
```

Tên "hình thang" đến từ hình học: vẽ công suất theo thời gian, đoạn giữa hai mẫu
tạo thành một **hình thang** (hai cạnh đứng là 400 và 440, đáy là 0,12 giây).
Diện tích hình thang chính là năng lượng. Riemann thì vẽ thành hình chữ nhật, bỏ
sót phần tam giác phía trên.

Hình thang chính xác hơn khi công suất đang thay đổi — mà công suất của UAV thì
thay đổi liên tục. Nên đây là phương pháp công bố.

### Con số 0,040 % đến từ đâu

Code tính năng lượng **hai lần** cho mỗi chuyến bay, một lần bằng hình thang, một
lần bằng Riemann, rồi so chênh lệch:

```
chênh lệch (%) = |E_hình_thang − E_Riemann| / E_hình_thang × 100
```

Làm vậy với cả 192 chuyến, được 192 con số chênh lệch. **Lấy trung vị của 192 con
số đó ra 0,040 %.**

Trong `src/energy_reconstruction.py`, đó là trường `cross_check_pct` mà hàm
`reconstruct_flight_energy()` trả về cho từng chuyến.

**Vì sao con số nhỏ lại là tin tốt.** Tần số lấy mẫu khoảng 8 Hz, tức mỗi mẫu cách
nhau ~0,12 giây. Trong 0,12 giây công suất không kịp đổi nhiều, nên hình thang và
hình chữ nhật gần như trùng nhau.

Nếu chênh lệch mà **lớn** — ví dụ 5 % — thì đó là dấu hiệu dữ liệu lấy mẫu quá
thưa, không bắt kịp biến thiên công suất. Khi đó con số năng lượng sẽ phụ thuộc
vào việc chọn phương pháp nào, tức là **không đáng tin**.

Chênh lệch 0,040 % nghĩa là: chọn cách nào cũng ra gần như cùng một số. Con số
năng lượng **vững**, không phải sản phẩm của một lựa chọn kỹ thuật tuỳ ý.

Đây chính là lý do thầy yêu cầu đối chiếu hai phương pháp chứ không chỉ chạy một
cái rồi thôi.

### Chi tiết 3 — Đổi đơn vị

Tích phân ra **joule (J)**. Dung lượng pin thì ghi theo **watt-giờ (Wh)**.

```
1 Wh = 1 W × 3600 s = 3600 J
→ chia cho 3600
```

Ví dụ: 400 W trong 180 giây = 72.000 J = 72.000 / 3600 = **20 Wh**.

### Kết quả

| | |
|---|---|
| Số chuyến bay | 192 |
| Tổng năng lượng | 4.083,8441 Wh |
| **Trung bình** | 4.083,8441 / 192 = **21,270 Wh** |
| Nhỏ nhất | 12,991 Wh |
| Lớn nhất | 37,747 Wh |

Con số **21,3 Wh** trong các báo cáo là 21,270 làm tròn một chữ số thập phân.

Cách tính đơn giản: cộng cột `energy_Wh` của 192 dòng rồi chia 192. Mỗi dòng là
một chuyến bay đã qua tích phân ở trên. Mở `data/processed/flight_level.csv` bằng
Excel, dùng hàm `AVERAGE` trên cột đó cũng ra đúng số này.

**Con số 21,3 Wh dùng để làm gì:** nó là **mốc so sánh** cho mọi sai số về sau.
Khi nói mô hình sai 0,657 Wh, phải hiểu là sai 0,657 trên nền 21,3 — tức khoảng
3 %. Không có mốc này thì con số sai số không có ý nghĩa.

Nó cũng chính là giá trị mà mô hình D0 trung bình hằng luôn dự báo — xem
`../cach_lam/D0_trung_binh_hang.md`.

---

## 4. Hai phép rút gọn — vì sao bảng cuối chỉ còn 192 dòng

Chỗ này hay gây nhầm, vì **hai phép rút gọn khác nhau xảy ra cùng lúc**:

```
flights.csv       242.019 dòng  ──┐
                                  ├──→  flight_level.csv  192 dòng
parameters.csv        209 dòng  ──┘
```

Hai con số giảm vì hai lý do hoàn toàn khác nhau. Tách ra sẽ rõ.

---

### Rút gọn A — gộp nhiều dòng telemetry thành một dòng

Đây là lý do từ **hàng trăm nghìn dòng** còn **vài trăm dòng**.

Máy bay đo khoảng **5,3 đến 9,1 lần mỗi giây**, suốt chuyến bay dài 106–428 giây.
Nên **một chuyến bay sinh ra rất nhiều dòng**:

| | Số mẫu telemetry |
|---|---|
| Chuyến ít nhất | 708 |
| Trung vị | 1.220 |
| Chuyến nhiều nhất | 2.856 |
| **Tổng 192 chuyến** | **242.019** |

Một chuyến cụ thể trong `flights.csv` trông như sau:

```
flight  time    battery_voltage  battery_current  position_x    ...
  5     0.00        22.41             8.3         -79.78231
  5     0.17        22.40             9.1         -79.78232
  5     0.34        22.38            12.7         -79.78234
  ...                                                           ← 1.220 dòng
  5   205.82        20.95             7.4         -79.78231
```

Cả 1.220 dòng đó **mô tả đúng một chuyến bay**.

Việc của D1 là biến chúng thành **một dòng tóm tắt**:

```
flight  energy_Wh  distance_2d_m  duration_s  payload  speed  altitude
  5       21.4         472.6        205.8       250      8       50
```

Trong đó `21.4 Wh` là **cộng dồn cả 1.220 mẫu** qua phép tích phân ở mục 3, và
`472.6 m` là **cộng dồn từng bước GPS** bằng haversine.

**Không mất thông tin nào** — nó được gộp lại thành đại lượng tổng của cả chuyến.

#### Vì sao phải gộp — hai lý do, lý do thứ hai quan trọng hơn

**Lý do thứ nhất, kỹ thuật.** Câu hỏi của đề tài là *"chuyến bay này tốn bao
nhiêu Wh"*. Đơn vị của câu hỏi là **chuyến bay**. Một mẫu telemetry đơn lẻ không
có "năng lượng của nó" — năng lượng chỉ có nghĩa khi cộng dồn theo thời gian.

**Lý do thứ hai, chống rò rỉ.** §5.3 của thầy bắt chia tập ở cấp chuyến bay:

> *"Keep all samples from one flight in the same data partition. Never split
> time-series rows from one flight between training and testing."*

Nếu giữ nguyên 242.019 dòng rồi chia ngẫu nhiên để huấn luyện và kiểm, thì 1.220
dòng của **cùng một chuyến** sẽ nằm ở **cả hai phía**. Mô hình chỉ cần **nhớ**
chuyến đó chứ không cần học quy luật, và điểm số sẽ đẹp một cách giả tạo.

Gộp thành một dòng mỗi chuyến làm chuyện đó **không thể xảy ra về mặt cấu trúc**
— chứ không phải nhờ một luật mà ai đó phải nhớ tuân thủ.

---

### Rút gọn B — loại chuyến không dùng được

Đây là lý do từ **209 chuyến** còn **192 chuyến**, và nó xảy ra ở cấp **chuyến
bay**, không liên quan gì tới telemetry.

---

### Hai phép này độc lập nhau

```
parameters.csv              flights.csv
  209 chuyến              242.019 dòng telemetry
      │                            │
      │  rút gọn B                 │  rút gọn A
      │  loại 17 chuyến            │  gộp ~1.220 dòng → 1 dòng
      └──────────┬─────────────────┘
                 ▼
         flight_level.csv
          192 dòng × 23 cột
```

Nếu **không loại chuyến nào** thì bảng cuối vẫn là **209 dòng**, không phải 209
nghìn dòng. Phép gộp xảy ra bất kể có loại hay không.

---

### Một con số đáng nhớ khi trình bày

Dữ liệu thô có **242 nghìn mẫu** — nghe rất nhiều. Nhưng sau khi gộp chỉ còn
**192 chuyến**, và theo phân tích ở mục 6, cỡ mẫu hiệu dụng còn gần **60 cấu
hình** hơn.

```
242.019 mẫu  →  192 chuyến  →  ~60 cấu hình độc lập
```

Chênh lệch từ 242 nghìn xuống 60 là lý do đề tài phải chọn Ridge chứ không phải
mạng nơ-ron, và phải dùng CV lặp 25 lần chứ không phải một lần chia.

**Ai nhìn 242 nghìn dòng rồi nói "dữ liệu nhiều" là đã đếm sai đơn vị.**

---

### Chi tiết rút gọn B — 17 chuyến bị loại

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

1. Mô hình D1 "chỉ cự ly" bị thoái hoá — xem `D2_benchmark_nang_luong.md`.
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

### Vì sao phải có mục này

Code sai thường **không báo lỗi**. Nó chạy trơn tru, in ra một bảng đẹp, và con số
trong bảng thì sai.

Dự án này đã gặp đúng chuyện đó một lần: phiên bản đầu của hàm tính cự ly cộng
thẳng hiệu số toạ độ theo **độ** rồi coi kết quả là **mét**. Chương trình chạy
bình thường, không cảnh báo gì. Sai khoảng 100.000 lần. Chỉ phát hiện ra nhờ đối
chiếu với bảng tuần 3.

Nên không thể "nhìn code thấy đúng" rồi tin. Phải có cách kiểm độc lập.

Ba lớp kiểm, mỗi lớp bắt một loại lỗi khác nhau.

---

### Lớp 1 — Unit test: 56 test tự động

**Nguyên tắc:** đưa vào dữ liệu đã biết trước đáp số, xem code có ra đúng không.

Chạy bằng một lệnh:

```bash
pytest
```

Màn hình phải hiện `56 passed`. Nếu hiện số nào khác, hoặc có chữ `FAILED`, thì
có gì đó hỏng — **không được dùng kết quả cho tới khi sửa xong**.

#### Phân bố 56 test

| Nhóm | Số test | Kiểm cái gì |
|---|---|---|
| `TestInstantaneousPower` | 2 | P = V × I |
| `TestIntegration` | 6 | Phép tích phân |
| `TestUnitConversion` | 3 | Đổi J sang Wh |
| `TestReconstructFlightEnergy` | 9 | Toàn bộ quy trình một chuyến bay |
| `TestHaversineSteps` | 6 | Đổi độ sang mét |
| `TestTrajectoryFeatures` | 8 | Cự ly, leo, hạ |
| `TestWindFeatures` | 3 | Gió, trung bình trên vòng tròn |
| `TestExclusions` | 5 | Bốn quy tắc loại trừ chuyến bay |
| `TestProtocolIntegrity` | 14 | **Kiểm chính file cấu hình** |

#### Ví dụ cụ thể từng loại test

**Đáp số tính tay được.** Công suất 100 W giữ nguyên trong 100 giây phải ra đúng
10.000 J. Không cần máy tính cũng biết đáp án, nên nếu code ra số khác là code sai.

**Bẫy mốc thời gian không đều.** Cho mốc `[0 ; 0,5 ; 3,0 ; 3,1 ; 7,0 ; 10,0]` với
công suất 50 W không đổi. Tổng thời gian 10 giây nên phải ra đúng 500 J. Nếu code
giả định tần số lấy mẫu đều thì sẽ ra số khác — test này bắt đúng lỗi đó.

**Phân biệt hai phương pháp tích phân.** Với tín hiệu tăng dần, Riemann **phải**
cho kết quả thấp hơn hình thang. Nếu hai cách ra cùng một số thì code đang nhầm
lẫn hai phương pháp.

**Bắt lỗi đơn vị độ/mét.** Test tính rằng trừ thẳng hai toạ độ theo độ cho ra
~0,0009, còn khoảng cách thật phải ~100 m. Test này tồn tại **chỉ vì lỗi đó đã
từng xảy ra thật** — viết test cho một lỗi đã gặp là cách chắc chắn nó không quay
lại.

**Trung bình hướng gió trên vòng tròn.** Gió hướng 350° và 10° thì trung bình phải
là 0°, không phải 180°. Trung bình số học thông thường cho kết quả sai hoàn toàn.

**Bay đi rồi về.** Đi 100 m rồi quay lại điểm xuất phát thì tổng đường đi là
200 m, không phải 0 m. Test chống lỗi dùng khoảng cách điểm đầu–điểm cuối thay vì
chiều dài đường đi.

**Mọi chuyến bị loại đều phải ghi lý do.** Test đếm: số chuyến giữ lại cộng số
chuyến trong nhật ký loại trừ phải bằng tổng ban đầu. Không chuyến nào được biến
mất lặng lẽ.

#### Nhóm test đặc biệt: TestProtocolIntegrity

14 test này **không kiểm code**, mà kiểm file `configs/d2_protocol.yaml`.

Lý do: lỗi nguy hiểm nhất ở đây không phải code chạy sai, mà là **ai đó vô tình
đưa một biến hậu nghiệm vào tập đặc trưng**. Code sẽ chạy hoàn hảo, MAE sẽ rất
đẹp, và toàn bộ kết quả vô giá trị.

Những gì nhóm test này chặn:

- Không cột nào trong danh sách cấm được lọt vào tập đặc trưng
- `energy_per_metre_J` phải nằm trong danh sách cấm (nó tính trực tiếp từ cột mục
  tiêu — rò rỉ trắng trợn)
- `duration_s` chỉ được có trong biến thể D2-a, `duration_planned_s` chỉ trong D2-b
- Hai biến thể phải khác nhau **đúng một đặc trưng**, không hơn
- Thước đo `bias` phải có mặt
- Cột gió chính phải là gió thô
- Thí nghiệm E2c phải được khai báo là **bổ sung ngoài giao thức**
- 5 chuyến giữ lại cự ly phải là **5 cấu hình khác nhau**, không phải 5 bản sao

Nói cách khác: giao thức đã đóng băng được **máy móc canh gác**, không phụ thuộc
vào việc có ai nhớ ra hay không.

---

### Lớp 2 — Kiểm tái lập

```bash
python3 -m src.features --verify reports/flight_level_week3.csv
```

Code đọc `flights.csv` từ đầu, dựng lại toàn bộ bảng 192 chuyến, rồi so từng cột
với bảng đã có từ tuần 3.

**Kết quả: cả 8 cột khớp tới 10⁻⁸** — tức trùng khít, chênh lệch chỉ ở mức sai số
làm tròn của máy tính.

| Cột | Lệch lớn nhất |
|---|---|
| `energy_Wh` | 7,1 × 10⁻¹⁵ |
| `distance_2d_m` | 2,6 × 10⁻⁸ |
| `distance_3d_m` | 1,5 × 10⁻⁸ |
| `duration_s` | 0 |
| `climb_m`, `descent_m` | 6,8 × 10⁻¹³ |
| `P_mean_W`, `P_max_W` | dưới 10⁻¹² |

**Phép kiểm này chứng minh được gì:** quy trình xử lý là **tất định** — cùng dữ
liệu vào, cùng code, ra cùng kết quả. Người khác tải bộ dữ liệu về, chạy script
của nhóm, sẽ ra đúng những con số trong bài.

Đây là thứ thầy đòi ở Mục 12.1: *"script xử lý chạy lại được"*, và ở Mục 9: *"mọi
hình trong bài phải sinh từ script"*.

**Nó KHÔNG chứng minh được gì:** rằng cách tính là *đúng về vật lý*. Nếu bảng tuần
3 đã sai từ đầu thì code tái lập y hệt cái sai đó. Lớp 1 và lớp 3 mới chặn được
loại lỗi này.

---

### Lớp 3 — Người kiểm chéo

Hai lớp trên đều là máy tự kiểm. Máy không bắt được lỗi **tư duy** — ví dụ chọn
nhầm công thức, hiểu sai đơn vị của bộ dữ liệu, hoặc chia tập theo cách tạo ra rò
rỉ mà không ai nhận ra.

Thầy yêu cầu rõ ở Mục 10:

> *Người làm một phần không được là người duy nhất kiểm kết quả phần đó.*

Và chỉ định cụ thể: **Duy kiểm đơn vị năng lượng và cách chia tập của Phát**
(WP1 ↔ WP2).

#### Duy cần kiểm cụ thể những gì

**Về đơn vị năng lượng:**

1. Công thức `E = Σ V × I × Δt` có đúng là năng lượng điện không
2. Phép đổi J → Wh chia 3600 có đúng không
3. Dải kết quả 13,0 – 37,7 Wh có hợp lý với một chuyến bay M100 khoảng 3 phút
   không — đối chiếu với dung lượng pin nhà sản xuất công bố
4. Công suất trung bình 405 W có hợp lý với một quadrotor cỡ này không

**Về cách chia tập:**

1. Đơn vị phân tích có đúng là **chuyến bay** không, hay đang chia theo mẫu
2. Mọi mẫu của một chuyến có nằm cùng một phân vùng không
3. Thí nghiệm giữ lại cấu hình có thật sự bỏ **cả tổ hợp** ra không
4. Việc chuẩn hoá đặc trưng có chỉ học từ fold huấn luyện không

Mục 2 và 4 là chỗ dễ sai nhất, và cũng là chỗ sai thì kết quả đẹp lên chứ không
xấu đi — nên không tự lộ.

#### Sau khi kiểm xong

Duy xác nhận thì sửa hai chỗ:

1. `configs/d2_protocol.yaml` → `meta.cross_check_status` đổi từ `PENDING` thành
   `CONFIRMED`
2. `reports/quality_report.md` → ô cuối bảng trạng thái nghiệm thu đổi thành
   **Đạt**

Lúc đó sản phẩm D1 mới nghiệm thu, và kết quả của sản phẩm D2 mới chuyển từ **tạm
thời** thành **chính thức**.

---

### Ba lớp bắt ba loại lỗi khác nhau

| Lớp | Bắt được | Không bắt được |
|---|---|---|
| Unit test | Code tính sai so với đáp số đã biết | Chọn nhầm công thức ngay từ đầu |
| Kiểm tái lập | Code chạy không tất định, phụ thuộc môi trường | Sai lặp lại y hệt cái sai cũ |
| Người kiểm chéo | Lỗi tư duy, hiểu sai đơn vị, rò rỉ ẩn | Lỗi tính toán nhỏ |

Thiếu một lớp là hở một mảng. Đó là lý do cả ba đều bắt buộc.
