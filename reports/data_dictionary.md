# Từ điển biến

**Sản phẩm D1** · tiêu chí nghiệm thu Mục 12.1: *"kiểm từ điển biến và đơn vị"*

Mô tả mọi cột trong `data/processed/flight_level.csv` — bảng 192 chuyến bay, mỗi
chuyến đúng một dòng.

- Nguồn: CMU Package Delivery Quadcopter, DOI 10.1184/R1/12683453
- Giấy phép: CC BY 4.0
- Sinh ra bởi: `python3 -m src.features --out data/processed/flight_level.csv`
- Dải giá trị dưới đây lấy từ chính 192 chuyến đã lọc

---

## Cách đọc cột "Dùng được"

| Ký hiệu | Nghĩa |
|---|---|
| **TRƯỚC** | Biết được trước khi cất cánh. **Dùng làm đặc trưng dự báo.** |
| **SAU** | Chỉ có sau khi bay xong. **Cấm dùng làm đặc trưng** (xem `configs/d2_protocol.yaml`) |
| **MỤC TIÊU** | Cái cần dự báo |
| **ĐỊNH DANH** | Khoá, không phải đại lượng vật lý |

Lý do tách: đề tài là đánh giá **trước** chuyến bay. Mô hình cần biết thời lượng
bay thực tế mới chạy được thì vô dụng vào đúng lúc cần dùng.

---

## 1. Định danh và tham số nhiệm vụ

Nguồn: `parameters.csv`

| Cột | Đơn vị | Dùng được | Nhỏ nhất | Trung vị | Lớn nhất | Ghi chú |
|---|---|---|---|---|---|---|
| `flight` | — | ĐỊNH DANH | 1 | — | 277 | Mã chuyến bay gốc. Chạy tới 277 nhưng chỉ có 209 dòng: 70 chuyến đã bị tác giả loại từ trước, không rõ lý do |
| `payload_num` | g | **TRƯỚC** | 0 | 250 | 500 | Chỉ 3 mức. Không được tuyên bố tổng quát cho tải khác |
| `speed_num` | m/s | **TRƯỚC** | 4 | 8 | 12 | Tốc độ **ra lệnh**, không phải tốc độ thực tế |
| `altitude_num` | m | **TRƯỚC** | 25 | 50 | 100 | Độ cao hành trình kế hoạch, so với mặt đất. 4 mức: 25/50/75/100 |
| `route` | — | **TRƯỚC** | — | — | — | 6 tuyến R1–R6. **R1 chiếm 180/192 chuyến** |
| `date` | — | ĐỊNH DANH | 2019-04-07 | — | 2019-10-24 | 17 ngày bay khác nhau |
| `local_time` | hh:mm | ĐỊNH DANH | — | — | — | Giờ địa phương lúc cất cánh |

**Lưu ý về lưới thí nghiệm:** 3 tải × 5 tốc độ × 4 độ cao = 60 tổ hợp, cả 60 đều
có mặt, mỗi tổ hợp 2–5 chuyến. Các yếu tố trực giao.

---

## 2. Mục tiêu dự báo

| Cột | Đơn vị | Dùng được | Nhỏ nhất | Trung vị | Lớn nhất |
|---|---|---|---|---|---|
| `energy_Wh` | Wh | **MỤC TIÊU** | 12,991 | 20,791 | 37,747 |

**Cách tính** (§4.2):

```
P_t = V_t × I_t
E   = Σ V_t × I_t × Δt        → joule, chia 3600 ra Wh
```

- Phương pháp tích phân: **hình thang**, dùng khoảng thời gian **thực** giữa hai
  mẫu (tần số lấy mẫu không đều: 5,3–9,1 Hz)
- Đối chiếu với tổng Riemann: lệch trung vị **0,040%**
- Nguồn: `battery_voltage` và `battery_current` trong `flights.csv`
- Có unit test: `tests/test_energy_reconstruction.py` (20 test)

---

## 3. Hình học đường bay

| Cột | Đơn vị | Dùng được | Nhỏ nhất | Trung vị | Lớn nhất | Ghi chú |
|---|---|---|---|---|---|---|
| `distance_2d_m` | m | **TRƯỚC** | 427,45 | 472,63 | 841,40 | Tổng đường đi trên mặt đất |
| `distance_3d_m` | m | SAU | 470,98 | 607,36 | 979,55 | Gồm cả thành phần dựng |
| `climb_m` | m | SAU | 28,25 | 62,46 | 118,17 | Tổng mét leo **đo được** |
| `descent_m` | m | SAU | 30,05 | 65,17 | 117,09 | Tổng mét hạ **đo được** |
| `alt_mean_m` | m | SAU | 277,53 | 302,45 | 334,28 | **So với mực nước biển**, không phải mặt đất |

### Cách tính cự ly — phần quan trọng, phải ghi vào bài

Trong `flights.csv`:

- `position_x` = **kinh độ**, đơn vị **độ** (~ −79,78 — Pittsburgh)
- `position_y` = **vĩ độ**, đơn vị **độ** (~ 40,46)
- `position_z` = độ cao, đơn vị **mét**

**Cự ly 2D** dùng công thức **haversine** với bán kính Trái Đất:

```
R = 6 371 000 m
```

Con số R này **không được chọn tuỳ tiện**. Thử nhiều cách quy đổi, chỉ haversine
với R = 6.371.000 tái lập đúng bảng tuần 3, lệch 4,5 × 10⁻⁹ m. Xấp xỉ mặt phẳng
với hệ số 111.320 m/độ lệch 0,68 m mỗi chuyến — đủ để người khác không tái lập
được kết quả.

**Cự ly 3D** ghép bước haversine với chênh lệch độ cao:

```
step_3d = √( step_haversine² + dz² )
```

### Ba cảnh báo về đơn vị

1. **Cộng hiệu số toạ độ theo độ rồi coi là mét sẽ sai ~5 bậc độ lớn** — mà chương
   trình vẫn chạy bình thường, không báo lỗi. Có unit test chặn riêng lỗi này.
2. **Bảng 1 của Rodrigues et al. ghi đơn vị `position_z` là độ**, nhưng mô tả là
   độ cao. Tác giả thừa nhận là lỗi. Dữ liệu xác nhận z ở đơn vị mét: biên độ
   27,4 m ở chuyến bay độ cao 25 m, 52,9 m ở chuyến 50 m.
3. **`alt_mean_m` ≈ 300 m là độ cao so với mực nước biển**, không phải độ cao bay.
   Đừng nhầm với `altitude_num`.

### Hai cách đo cự ly chênh 2,5%

| Chuyến bay 1 | Cự ly |
|---|---|
| Haversine từ toạ độ | 510,8 m |
| Tích phân cột vận tốc | 498,9 m |

Chênh 2,4% trên cùng một chuyến bay. Không xác định được cách nào đúng hơn — chỉ
biết hai cảm biến độc lập không đồng ý với nhau.

**Phải nêu trong hạn chế:** cự ly là đầu vào trung tâm của `E_req = E_out +
E_return + ...`, nên sai số 2,5% này lan vào mọi phán quyết ở D3.

---

## 4. Thời lượng và tốc độ

| Cột | Đơn vị | Dùng được | Nhỏ nhất | Trung vị | Lớn nhất | Ghi chú |
|---|---|---|---|---|---|---|
| `duration_s` | s | SAU | 106,11 | 183,20 | 428,29 | Thời lượng bay **thực tế** |
| `duration_planned_s` | s | **TRƯỚC** | — | — | — | Suy ra: `distance_2d_m / speed_num` (§5.5) |
| `speed_realised_ms` | m/s | SAU | 1,529 | 2,586 | 4,559 | `distance_2d_m / duration_s` |

### Vì sao `speed_realised_ms` thấp hơn `speed_num` nhiều

Tốc độ ra lệnh 4–12 m/s nhưng tốc độ "thực tế" chỉ 1,5–4,6 m/s. Không mâu thuẫn:
`speed_realised_ms` lấy cự ly ngang chia cho **toàn bộ** thời lượng, gồm cả cất
cánh, leo, hạ, hạ cánh và treo. Nó **không phải** tốc độ hành trình.

Tên cột dễ gây hiểu nhầm. Giữ nguyên để khớp bảng tuần 3, nhưng không dùng làm
đặc trưng.

### Vì sao hai loại thời lượng

Thầy liệt kê "duration" trong tập đặc trưng D2 (§5.2) nhưng không nói rõ loại nào.
Nhóm chạy **hai phiên bản** — chi tiết trong `docs/san_pham/D2_benchmark_nang_luong.md` mục 3.

Bằng chứng số: hồi quy `duration_s` theo các biến biết trước khi bay cho
**R² = 0,73**, tức 27% thông tin không suy ra được từ kế hoạch bay. Hai biến thể
thật sự khác nhau.

---

## 5. Gió

| Cột | Đơn vị | Dùng được | Nhỏ nhất | Trung vị | Lớn nhất | Ghi chú |
|---|---|---|---|---|---|---|
| `wind_mean_ms` | m/s | **TRƯỚC** | 2,809 | 4,434 | 6,670 | Gió **thô**, chưa hiệu chỉnh. Giao thức gọi là `wind_raw_mean_ms` |
| `wind_dir_mean_deg` | độ | **TRƯỚC** | 1,31 | 183,36 | 359,79 | Hướng gió trung bình. Lấy trung bình **trên vòng tròn**, không phải trung bình số học |

### Vì sao dùng gió thô, không dùng gió hiệu chỉnh

§13 của thầy cho hai nhánh: dùng độ lớn gió kèm ghi rõ hạn chế, **hoặc** suy ra
thành phần theo hướng **chỉ khi dữ liệu hợp lệ tồn tại**.

`d2_report.md` đã chứng minh dữ liệu hiệu chỉnh **không** hợp lệ:

| Cột | Tương quan với `speed_realised_ms` |
|---|---|
| `wind_raw_mean_ms` | +0,415 |
| `wind_corr_mean_ms` | **+0,506** |

Cột gió đã hiệu chỉnh tương quan với tốc độ UAV **mạnh hơn cả gió thô** — dấu hiệu
nó đang đo tốc độ bay chứ không đo gió.

Thêm nữa, đa thức hiệu chỉnh của Rodrigues chỉ hợp lệ trong [2,218 ; 12,697] m/s,
mà **33,72% số mẫu nằm dưới cận dưới** và 2,64% nằm trên cận trên. Đa thức của
chính tác giả không bao phủ được dữ liệu của chính họ.

### Các cột gió trong `mission_record.csv` (không dùng cho D2)

| Cột | Nhỏ nhất | Trung vị | Lớn nhất |
|---|---|---|---|
| `wind_corr_mean_ms` | 2,397 | 3,992 | 7,932 |
| `wind_corr_max_ms` | 4,846 | 13,530 | 20,218 |
| `wind_corr_std_ms` | 1,212 | 3,882 | 6,473 |
| `wind_tailwind_mean_ms` | 0,045 | 5,858 | 9,120 |
| `wind_coverage` | 0,289 | 0,638 | 0,932 |
| `wind_n_valid` | 306 | 774 | 1899 |

Giữ lại làm phân tích phụ, báo cả hai nhánh trong bảng so sánh.

### Hạn chế bắt buộc nêu

- Cảm biến gió có độ lệch được chính tác giả thừa nhận, rõ nhất ở tốc độ bay thấp
- Bài báo nêu **hai trị số sai số khác nhau** cho cảm biến gió (±0,1 m/s trong
  phần lời, ±0,3 m/s trong Bảng 2) và không giải thích
- Độ lớn gió đơn thuần **không phân biệt được gió ngược và gió xuôi** (§4.3)
- Toàn chiến dịch bay trong dải gió hẹp 2,81–6,67 m/s

---

## 6. Công suất và chất lượng ghi dữ liệu

| Cột | Đơn vị | Dùng được | Nhỏ nhất | Trung vị | Lớn nhất | Ghi chú |
|---|---|---|---|---|---|---|
| `P_mean_W` | W | SAU | 257,94 | 407,51 | 496,03 | Công suất trung bình đo được |
| `P_max_W` | W | SAU | 706,83 | 842,11 | 1004,22 | Đỉnh công suất, thường lúc cất cánh |
| `energy_per_metre_J` | J/m | **CẤM** | 79,17 | 156,68 | 271,03 | Tính trực tiếp từ cột mục tiêu — **rò rỉ trắng trợn** |
| `n_samples` | — | SAU | 708 | 1219 | 2856 | Số mẫu telemetry dùng được |
| `sample_hz` | Hz | SAU | 5,263 | 8,333 | 9,091 | **Không đều** — lý do phải dùng khoảng thời gian thực |
| `quality_notes` | — | — | — | — | — | **Rỗng toàn bộ 192 dòng.** Giữ lại để khớp bảng tuần 3 |

---

## 7. Tóm tắt: tập đặc trưng đã đóng băng

Chốt trong `configs/d2_protocol.yaml`, có unit test chặn (`TestProtocolIntegrity`).

**D2-b — phiên bản chính, đưa vào bộ máy quyết định D3:**

```
payload_num, speed_num, altitude_num, distance_2d_m,
wind_raw_mean_ms, duration_planned_s
```

**D2-a — phiên bản đối chứng, đúng chữ §5.2:**

```
payload_num, speed_num, altitude_num, distance_2d_m,
wind_raw_mean_ms, duration_s
```

**Cấm tuyệt đối:** `speed_realised_ms`, `climb_m`, `descent_m`, `P_mean_W`,
`P_max_W`, `energy_per_metre_J`, `alt_mean_m`, `n_samples`, `sample_hz`

---

## 8. Hạn chế lớn nhất của bảng dữ liệu này

**Gần như không có biến thiên cự ly.**

| | |
|---|---|
| Chuyến trên tuyến R1 | 180 / 192 (94%) |
| Cự ly R1 | 456,7 – 487,1 m, độ lệch chuẩn **5,3 m (~1%)** |
| Tương quan cự ly ↔ năng lượng | chỉ **+0,143** |

Đây là thí nghiệm giai thừa tại **một cự ly cố định**, không phải bộ dữ liệu đa
cự ly.

**Cỡ mẫu hiệu dụng:** mỗi tổ hợp có 2–5 chuyến gần như lặp lại, nên đơn vị thông
tin độc lập gần với **60 cấu hình** hơn là 192 chuyến. Khi viết bài, nói 192 mà
không nói 60 là thổi phồng.
