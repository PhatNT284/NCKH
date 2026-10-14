# Bảng tham số năng lượng khả dụng và luật cứng

**Sản phẩm tuần 6** · Phát + Duy · phục vụ sản phẩm D3 (bộ máy quyết định)

Thầy yêu cầu ở Mục 12.1 (tiêu chí nghiệm thu D3): *"giả định năng lượng khả dụng
có nguồn"*. Mỗi dòng dưới đây đều ghi nguồn; dòng nào chưa có nguồn thì đánh dấu
**CHỜ**, không được đoán.

Nền tảng tham chiếu: **DJI Matrice 100**.
Nguồn thông số nhà sản xuất: [trang hỗ trợ chính thức DJI](https://www.dji.com/global/support/product/matrice100).

---

## 1. Năng lượng khả dụng

Công thức, §5.4 và Proposal Eq (2):

```
E_available = E_nominal × SoC × SoH × κ(T)
```

| Tham số | Giá trị | Đơn vị | Nguồn | Trạng thái |
|---|---|---|---|---|
| `E_nominal` | **99,9** (TB47D) — xem mục 1.1 | Wh | DJI + Rodrigues et al. | **Chốt tạm, kèm độ nhạy** |
| `SoC` | `Q(t) / Q_tot,t` | — | Shibl et al.; Proposal Eq (3) | Xong — biến đầu vào |
| `SoH` | `Q_tot,t / Q_tot,i` | — | Shibl et al.; Proposal Eq (3) | Xong — tham số kịch bản |
| `κ(T)` | `min(1; 0,8814 + 0,0091·T − 0,0001·T²)` | — | Kim et al. | Xong — xem mục 2 |

### 1.1 — OI-2: bài báo tự mâu thuẫn

Đã tra bài Rodrigues et al. (2021). **Bài báo nói hai điều khác nhau:**

| Chỗ ghi trong bài | Nội dung | Ứng với pin nào |
|---|---|---|
| Methods > Airframe | *"Its standard battery has a capacity of **4500 mAh** that gives it a flight time of **22 minutes** without any additional payload"* | **TB47D** |
| Methods > Airframe | khối lượng pin **600 g** | **TB47D** |
| Methods > Regulation and Safety | *"Care is taken in the usage of LiPo **DJI TB48D** batteries"* | **TB48D** |

Đối chiếu thông số DJI:

| | TB47D | TB48D |
|---|---|---|
| Dung lượng | **4500 mAh** | 5700 mAh |
| Năng lượng | **99,9 Wh** | 129,96 Wh |
| Bay treo không tải | **22 phút** | 28 phút |
| Khối lượng pin | **~600 g** | ~676 g |

**Ba con số trong bài đều khớp TB47D; chỉ cái tên nói TB48D.**

### Quyết định: dùng 99,9 Wh làm giá trị chính, có phân tích độ nhạy

Hai lý do:

1. **Đa số bằng chứng.** Dung lượng, thời lượng bay và khối lượng — ba đại lượng
   độc lập — đều chỉ về TB47D. Cái tên xuất hiện một lần, trong mục an toàn, nói
   về cách bảo quản pin LiPo nói chung.
2. **Hướng an toàn.** 99,9 Wh là giá trị **nhỏ hơn**. Giả định ít năng lượng hơn
   thực tế thì hệ thống thận trọng hơn — ra NO-FLY nhiều hơn, tức giảm lỗi
   **cho bay nhầm**. Nếu chọn nhầm theo hướng này thì hậu quả là từ chối thừa,
   không phải cho bay chuyến không đủ pin.

**Bắt buộc kèm phân tích độ nhạy ở sản phẩm D4:** chạy lại toàn bộ với
`E_nominal = 129,96 Wh` và báo cáo kết luận thay đổi thế nào. §8 mục 3 yêu cầu
báo mọi giá trị đã thử, không chỉ giá trị cho kết quả đẹp.

**Phải viết vào phần hạn chế của bài:** bộ dữ liệu không xác định rõ loại pin,
bài báo gốc tự mâu thuẫn, và nhóm chọn giá trị bảo thủ.

### Quy ước SoC × SoH — phải ghi rõ, dễ sai

Viết theo dạng Shibl thì hai đại lượng **dùng chung một số hạng**:

```
SoC × SoH  =  Q(t)/Q_tot,t  ×  Q_tot,t/Q_tot,i  =  Q(t) / Q_tot,i
```

Tức là **điện tích hiện có so với dung lượng lúc pin còn mới**.

Proposal mục 4.4 cảnh báo: hai đại lượng này được định nghĩa khác nhau trong tài
liệu, và **ghép nhầm cặp sẽ đếm dung lượng hiện tại hai lần**. Phải viết quy ước
ra trong bài, không để ngầm hiểu.

### SoH không phải biến đo được

§5.4: SoH là **giả định kịch bản**, không có trong bộ dữ liệu CMU. Không được
trình bày như thể học được từ dữ liệu, và không được huấn luyện mô hình dự báo
SoH trên bộ dữ liệu này.

---

## 2. Hệ số nhiệt độ κ(T) — giới hạn sử dụng

Hồi quy bậc hai của Kim et al. **chỉ hiệu chỉnh trên dải 4,5 – 18,4 °C** (một
tình huống mùa đông).

§5.4 cấm ngoại suy ngoài dải hiệu chỉnh. Ngoài dải phải dùng **cận bảo thủ**.

| Dải nhiệt độ | Dùng gì | Căn cứ |
|---|---|---|
| 4,5 – 18,4 °C | `0,8814 + 0,0091·T − 0,0001·T²` | trong dải hiệu chỉnh |
| Ngoài dải đó | **κ = 1** | cận bảo thủ, §5.4 |

**Vì sao phải chặn trên bằng 1:** đa thức gốc trả về giá trị **lớn hơn 1** trong
khoảng xấp xỉ 15,8 – 75,2 °C, đạt 1,089 tại 45,5 °C — tức khẳng định pin chứa
nhiều năng lượng hơn mức danh định của chính nó. Vô lý về vật lý.

**Hệ quả thực tế, phải nêu trong bài:** dải nhiệt độ vận hành M100 là −10 đến
40 °C, trong khi dải hiệu chỉnh của Kim chỉ 4,5 – 18,4 °C. Nghĩa là **phần lớn
vùng vận hành nằm ngoài dải hợp lệ**, và ở đó κ bị giữ ở 1.

Nói cách khác: mô hình hiện **không mô tả được ảnh hưởng của nhiệt độ** trên phần
lớn dải vận hành. §5.4 ghi rõ nhiệt độ chỉ là **phân tích độ nhạy**, không phải
hiệu ứng học được từ dữ liệu.

---

## 3. Luật cứng cho lớp an toàn (§5.7)

Lớp này chạy **trước** mô hình và chỉ được giữ nguyên hoặc hạ cấp phán quyết,
không bao giờ nâng NO-FLY lên FLY.

| Tham số | Giá trị | Đơn vị | Nguồn | Trạng thái |
|---|---|---|---|---|
| Khối lượng cất cánh tối đa | 3.600 | g | DJI | Xong |
| Khối lượng máy bay (TB47D) | 2.355 | g | DJI | Xong |
| Khối lượng máy bay (TB48D) | 2.431 | g | DJI | Xong |
| Tải trọng tối đa, **máy bay nguyên bản** | 1.245 (TB47D) / 1.169 (TB48D) | g | tính: 3.600 − khối lượng máy bay | Xong — **nhưng xem mục 3.1** |
| **Giới hạn gió** | **10** | m/s | DJI | Xong |
| **Dải nhiệt độ vận hành** | **−10 … 40** | °C | DJI | Xong |
| Nhiệt độ sạc pin | 0 … 40 | °C | DJI | Xong — ngoài phạm vi quyết định bay |
| Tốc độ lên tối đa | 5 | m/s | DJI | Xong |
| Tốc độ xuống tối đa | 4 | m/s | DJI | Xong |
| Tốc độ tối đa (chế độ GPS) | 17 | m/s | DJI | Xong |

DJI công bố tải trọng tối đa **gián tiếp** qua khối lượng cất cánh tối đa, nên con
số đó là **tính ra**, không phải nhà sản xuất ghi thẳng. Phải nói rõ khi trích dẫn.

---

### 3.1 — Máy bay trong bộ dữ liệu VƯỢT khối lượng cất cánh tối đa

**Đây là phát hiện quan trọng, ảnh hưởng trực tiếp tới lớp luật cứng.**

Máy bay trong bộ dữ liệu CMU **không phải M100 nguyên bản**. Bài Rodrigues et al.
liệt kê khối lượng từng thành phần:

| Thành phần | Khối lượng |
|---|---|
| Khung máy bay | 1.831 g |
| Pin | 600 g |
| Cảm biến gió và cột | 136 g |
| Máy tính trên khoang, cảm biến nhỏ, dây | 1.113 g |
| **Tổng, chưa tải** | **3.680 g** |

Đối chiếu với giới hạn DJI:

| Cấu hình | Khối lượng cất cánh | So với MTOW 3.600 g |
|---|---|---|
| Không tải | 3.680 g | **vượt 80 g (+2,2 %)** |
| Tải 250 g | 3.930 g | **vượt 330 g (+9,2 %)** |
| Tải 500 g | 4.180 g | **vượt 580 g (+16,1 %)** |

**Toàn bộ 192 chuyến bay đều vượt khối lượng cất cánh tối đa nhà sản xuất công bố.**
Bài báo không nhắc tới giới hạn này.

#### Hệ quả cho luật cứng ở sản phẩm D3

Không được dùng luật `tải trọng ≤ 1.245 g` cho máy bay này. Con số đó tính cho M100
nguyên bản, còn máy bay thực tế đã mang thêm **1.249 g thiết bị đo** (cảm biến gió +
máy tính trên khoang).

Áp thẳng luật `khối lượng cất cánh ≤ 3.600 g` thì **mọi chuyến trong bộ dữ liệu đều
thành NO-FLY**, kể cả chuyến không tải — benchmark vô nghĩa.

**Cách xử lý đề xuất:**

1. Luật cứng về tải trọng dựa trên **dải bộ dữ liệu phủ**: 0 – 500 g. Ngoài dải này
   là ngoại suy, phải đánh dấu.
2. Giới hạn MTOW của nhà sản xuất ghi vào bảng tham số như **ràng buộc đã biết bị
   vượt**, nêu trong phần hạn chế của bài — không dùng làm luật chặn trong benchmark.
3. Nếu sau này áp dụng hệ thống cho máy bay thật ở cấu hình nguyên bản, lúc đó luật
   `tải trọng ≤ 1.245 g` mới đúng.

#### Hệ quả cho mô hình vật lý D5

Hệ số η trong `src/physics_m100.py` khớp trên dải khối lượng **2.431 – 3.431 g**
(dải DJI công bố thời lượng bay treo). Máy bay trong bộ dữ liệu nặng
**3.680 – 4.180 g** — **nằm ngoài dải đã hiệu chỉnh**.

Nên nếu áp mô hình vật lý lên các chuyến bay thực tế thì đó là **ngoại suy**, phải
khai báo rõ. Phép kiểm chứng η ở `docs/cach_lam/D5_mo_hinh_vat_ly.md` vẫn hợp lệ vì
nó chỉ đối chiếu nội bộ với số liệu DJI cho cấu hình DJI.

---

## 4. Tham số chính sách

| Tham số | Giá trị | Nguồn | Ghi chú |
|---|---|---|---|
| Hệ số dự trữ `r` | **0,20** chính; quét thêm 0,10 và 0,30 | Proposal mục 4.5, theo Zhang et al. | **Tham số chính sách** |

§5.7 ghi rõ: *"hệ số dự trữ 1,20 có thể được thử như một **giả định kịch bản**,
nhưng không được trình bày như yêu cầu của cơ quan quản lý hay nhà sản xuất."*

Và bắt buộc báo kết quả trên cả ba mức, không chỉ mức cho kết quả đẹp nhất.

---

## 5. Độ phủ của bộ dữ liệu so với giới hạn vận hành

Bảng này **không phải tham số**, nhưng sản phẩm D4 cần nó: nó cho biết dải nào có
dữ liệu đỡ lưng, dải nào là ngoại suy.

| Biến | Bộ dữ liệu CMU phủ | Giới hạn vận hành | Nhận xét |
|---|---|---|---|
| Tải trọng | 0 – 500 g | tối đa 1.245 g | Phủ **40 %** dải; trên 500 g là ngoại suy |
| Gió | 2,81 – 6,67 m/s | tối đa 10 m/s | Chưa bao giờ chạm gần giới hạn |
| Độ cao | 25 – 100 m | — | Bốn mức rời rạc |
| Tốc độ ra lệnh | 4 – 12 m/s | tối đa 17 m/s | Phủ phần lớn dải hữu dụng |
| Cự ly | **~472 m (94 % số chuyến)** | — | Xem cảnh báo dưới |
| Nhiệt độ | **không ghi nhận** | −10 … 40 °C | Hoàn toàn không có dữ liệu |

### Hai cảnh báo cho bộ sinh kịch bản ở sản phẩm D4

**Cự ly** — bộ dữ liệu gần như chỉ có một cự ly. Mô hình năng lượng được chọn chỉ
đáng tin trong dải khoảng **420 – 610 m**; ngoài dải đó nó **đoán thiếu có hệ
thống** (bias −7,6 Wh ở 835 m). Lấy mẫu ngoài dải này phải đánh dấu rõ là ngoại
suy — §6/E3 của thầy yêu cầu *"clearly label any extrapolated ranges"*.

Chi tiết: `docs/san_pham/D2_benchmark_nang_luong.md` mục 8.

**Nhiệt độ** — bộ dữ liệu **không ghi nhiệt độ môi trường**. Mọi kịch bản nhiệt độ
là giả định thuần tuý, và κ(T) chỉ hợp lệ trên một phần nhỏ dải vận hành (mục 2).
Kết quả liên quan tới nhiệt độ phải trình bày như **phân tích độ nhạy**, không
phải dự báo.

---

## 6. Tóm tắt trạng thái

| Nhóm | Trạng thái |
|---|---|
| Năng lượng khả dụng | **Xong** — `E_nominal` = 99,9 Wh, kèm phân tích độ nhạy bắt buộc |
| Hệ số nhiệt độ | Xong, kèm giới hạn sử dụng đã ghi rõ |
| Luật cứng | **Xong toàn bộ** |
| Tham số chính sách | Xong |

**Bảng tham số đã đủ — Quyền bắt đầu sản phẩm D3 được ngay.**

Ba điều phải mang theo sang D3:

1. `E_nominal = 99,9 Wh` là **giá trị bảo thủ đã chốt**, không phải giá trị chắc
   chắn. Phải chạy độ nhạy với 129,96 Wh ở sản phẩm D4.
2. **Không dùng luật `tải trọng ≤ 1.245 g`** — xem mục 3.1. Dải hợp lệ là 0 – 500 g.
3. **Envelope cự ly 420 – 610 m** — xem mục 5.

---

## Nguồn

- [DJI — trang hỗ trợ chính thức Matrice 100](https://www.dji.com/global/support/product/matrice100)
- Shibl, M. M., Ismail, L. S., Massoud, A. M. "A machine learning-based battery
  management system for state-of-charge prediction and state-of-health estimation
  for unmanned aerial vehicles." *Journal of Energy Storage*, 66, 2023.
  [DOI 10.1016/j.est.2023.107380](https://doi.org/10.1016/j.est.2023.107380)
- Kim, H., et al. "Drone flight scheduling under uncertainty on battery duration
  and air temperature." *Computers & Industrial Engineering*, 2018.
  [DOI 10.1016/j.cie.2018.02.005](https://doi.org/10.1016/j.cie.2018.02.005)
  — **thầy yêu cầu kiểm lại metadata đầy đủ và dải nhiệt độ hợp lệ trước khi dùng
  định lượng**
- Zhang, J., et al. "Energy consumption models for delivery drones." *Transportation
  Research Part D*, 90, 2021. [DOI 10.1016/j.trd.2020.102668](https://doi.org/10.1016/j.trd.2020.102668)
- Khối lượng và tải trọng tối đa: `src/physics_m100.py`
