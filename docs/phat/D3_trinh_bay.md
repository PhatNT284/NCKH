# Sản phẩm D3 — bản trình bày

Phát · nguồn: `docs/san_pham/D3_bo_may_quyet_dinh.md`, `reports/decision_engine_report.md`

---

# PHẦN A — Bản nói

> Thuộc ý, không cần thuộc chữ.

## 1. D3 để làm gì

Sản phẩm D2 trả lời *"chuyến này tốn bao nhiêu Wh"* — một con số riêng cho từng
nhiệm vụ.

Nhưng **không người điều phối nào ra lệnh cất cánh dựa trên một con số Wh.** Họ
cần nghe: **bay được, bay có điều kiện, hay không được bay.**

D3 là cây cầu giữa hai thứ đó.

Và đây là **đóng góp mới của cả đề tài**. Dự báo năng lượng UAV đã có nhiều người
làm. Cái chưa ai làm chuẩn là gắn nó vào một quy trình quyết định có dự trữ an
toàn, luật cứng, và khai báo rõ giới hạn hiệu lực.

## 2. Một ví dụ chạy suốt

> Sáng mai giao hàng: mang 250 g, bay 472 m, cao 50 m, tốc độ 8 m/s.
> Gió 3 m/s, trời 15 °C. Pin đang 30%, sức khoẻ pin còn 95%.

**Bước 1 — pin cho được bao nhiêu**

```
99,9 Wh × 0,30 × 0,95 × 0,995 = 28,3 Wh
   ↑       ↑      ↑      ↑
ghi trên  SoC   SoH   κ(15 °C)
  vỏ
```

**Bước 2 — chuyến cần bao nhiêu**

Mô hình D2 trả về **22,0 Wh** cho chuyến này.

**Bước 3 — có được phép bay không**

Kiểm 6 luật, **không liên quan gì tới pin**: gió 3 ≤ 10 ✓, 15 °C trong −10…40 ✓,
khối lượng ≤ 3.600 g ✓, tốc độ 8 ≤ 17 ✓, cự ly 472 trong 420–610 ✓, tải 250 trong
0–500 ✓.

**Bước 4 — quyết định**

```
Dư = 28,3 − 22,0 = 6,3 Wh = 28,8%

        20%           26,7%
─────────┼──────────────┼────────→
 NO-FLY   CONDITIONAL      FLY
                           ↑ 28,8%
```

**→ FLY.**

## 3. Hai vạch ở đâu ra — chỗ D2 chảy vào D3

**Vạch dưới 20%** là hệ số dự trữ `r` của thầy. Để dành phòng gió đổi hướng, bay
vòng chờ, lệch tuyến.

**Vạch trên 26,7%** = 20% **cộng sai số của chính mô hình D2**.

Vì con số "cần 22,0 Wh" là **mô hình đoán**, không phải đo. Thực tế có thể là
23,5 Wh. Hệ số 20% chống rủi ro ngoài trời — nó **không** chống việc mô hình đoán
sai. Đó là rủi ro riêng, phải cộng riêng.

Cộng bao nhiêu: lấy từ chính kết quả D2 — 95% số chuyến có sai số dưới **1,469
Wh**. Chia cho 22 Wh ra 6,7%.

```
R_fly = r + p95(|phần dư|) / E_required
```

Vì có phép **chia cho E_required**, vạch trên **khác nhau ở mỗi chuyến** — không
phải hằng số 26,7%.

**Đây là lý do thầy bắt làm xong D2 mới được làm D3.** Không có D2 thì con số
6,7% kia là bịa.

## 4. Bốn mức, không phải ba

| Mức | Nghĩa |
|---|---|
| FLY | biết đủ, và đủ pin |
| CONDITIONAL | đủ pin nhưng sát ngưỡng — **phải chọn biện pháp mới bay được** |
| NO-FLY | **biết là không được** |
| INSUFFICIENT-DATA | **không biết** |

§5.7 cho ba mức. §4.6 thêm mức thứ tư.

Phân biệt *"không biết"* với *"biết là không được"* quan trọng về vận hành:
NO-FLY thì huỷ chuyến. INSUFFICIENT-DATA thì **đi lấy thêm dữ liệu** rồi chạy
lại.

**Chế độ hỏng nguy hiểm nhất** là tự điền giá trị mặc định rồi chạy tiếp:

```
thiếu nhiệt độ → coi như 25 °C → dư 40% → FLY (xanh)
```

Người điều phối nhìn chữ FLY màu xanh và tin. Thực tế hệ thống vừa **bịa** một
con số rồi dựa vào đó mà kết luận. Hôm đó trời 2 °C thì pin yếu hơn hẳn giả định.

§4.6 nguyên văn: *"does not fall back to a favourable default"*. Có test riêng
chặn.

## 5. Luật cứng — hai mức độ khác nhau có chủ đích

| Mã | Luật | Nguồn | Vi phạm thì |
|---|---|---|---|
| HR-1…4 | gió ≤ 10 · −10…40 °C · ≤ 3.600 g · ≤ 17 m/s | **DJI** | **NO-FLY** |
| PD-1 | cự ly 420–610 m | **thí nghiệm E2c của nhóm** | không được FLY |
| PD-2 | tải 0–500 g | độ phủ dữ liệu | không được FLY |

**HR-** là giới hạn vật lý và chứng nhận → **chặn tuyệt đối**. Gió 14 m/s là máy
bay không chịu nổi.

**PD-** là **giới hạn hiệu lực của mô hình** → máy bay vẫn bay được, nhưng ở đó
mô hình đoán thiếu 29,6%, nên con số không đáng tin. Hệ thống phải **nói rõ** thay
vì im lặng đưa ra một số sai.

Khi trích dẫn phải tách hai nguồn. **Trộn lại là lỗi học thuật.**

Và thầy ghi rõ: *"no score, no model output and no human approval may convert a
hard-rule violation into FLY."*

## 6. Thứ tự xét — không được đổi

```
1. Vi phạm luật cứng  → NO-FLY ngay
2. Thiếu đầu vào      → INSUFFICIENT-DATA
3. Tính biên dự trữ   → FLY / CONDITIONAL / NO-FLY
4. Đang ngoại suy     → hạ FLY xuống CONDITIONAL
```

Bước 1 phải trước bước 2. Nếu đảo lại: gió 14 m/s **và** thiếu SoC sẽ ra "thiếu
dữ liệu" — che mất một NO-FLY thật, và người ta sẽ đi đo SoC vô ích rồi mới biết
gió quá mạnh.

## 7. Kiểm D3 bằng gì — câu hay bị hỏi nhất

**Không có đáp án thì kiểm kiểu gì?**

Bộ dữ liệu không có nhãn *"chuyến này đáng lẽ có nên bay không"*, nên **không đo
được độ chính xác**. Thay vào đó nhóm em kiểm **bảy tính chất phải luôn đúng**:

| | Nội dung | Trường hợp | Vi phạm |
|---|---|---|---|
| INV-1 | vi phạm luật cứng → không bao giờ FLY | 576 | **0** |
| INV-2 | thiếu đầu vào → không bao giờ FLY | 960 | **0** |
| INV-3 | pin nhiều hơn → phán quyết không xấu đi | 192 | **0** |
| INV-4 | cùng đầu vào → cùng đầu ra | 192 | **0** |
| INV-5 | lưu rồi tính lại → ra đúng phán quyết cũ | 192 | **0** |
| INV-6 | D3 không chứa mô hình học máy nào | 1 | **0** |
| INV-7 | biện pháp đề xuất ra phải có tác dụng | 213 | **0** |

**2.326 trường hợp, 0 vi phạm**, chạy trên cấu hình của 192 chuyến bay có thật.

**INV-6 đáng nói nhất.** Nó **quét mã nguồn** tìm `.fit()`, `.predict()`,
`import sklearn` trong các module D3. Khai "D3 không có mô hình học máy" rồi để
đó thì vô nghĩa — phải kiểm được.

Lần chạy đầu nó báo chính file quét vi phạm, vì trong file có chuỗi regex
`.fit(`. Em sửa: bỏ cả chuỗi ký tự trước khi quét. Rồi **kiểm hai chiều** — thêm
`.fit()` thật vào thì nó bắt được, hoàn nguyên thì sạch.

**Một phép kiểm luôn báo "đạt" thì vô dụng.**

## 8. Kết quả đẹp nhất của cả dự án

> Phải nói trước: đây **không phải phép chấm điểm**. §4.7 ghi việc đánh giá hành
> vi quyết định thuộc sản phẩm **D4**, trên kịch bản tổng hợp. Chạy ở đây để minh
> hoạ và kiểm bất biến.

Từ SoC 0,50 trở lên, bảng **đứng yên mãi mãi**:

```
187 FLY  ·  5 CONDITIONAL  ·  0 NO-FLY
```

Năm chuyến kẹt ở CONDITIONAL **dù pin đầy 100%**. Cự ly của chúng: 830,7 · 837,0 ·
837,5 · 834,6 · 841,4 m.

**Đúng năm chuyến R6 của thí nghiệm E2c** — những chuyến D2 đoán thiếu 29,6%.

Luật PD-1 chặn chúng **không phải vì pin**, mà vì cự ly nằm ngoài envelope. Hệ
thống không nói "không bay được"; nó nói **"tôi không đủ cơ sở để bảo đảm chuyến
này"**.

Đây là kết quả mạch lạc nhất của cả D2 cộng D3: **một phát hiện thống kê ở tuần 5
trở thành hành vi kiểm chứng được của hệ thống ở tuần 7.**

Và một con số dùng được ngay: SoC tối thiểu để bay, với `r = 0,20` — trung vị
**26,5%**, p90 35,1%, lớn nhất 42,0%.

## 9. Ba quyết định đáng báo

**B3 — κ ở nhiệt độ lạnh.** Quy tắc cũ cho κ = 1 với mọi nhiệt độ ngoài dải hiệu
chỉnh. Đúng ở phía nóng, **sai ở phía lạnh**:

| T | Quy tắc cũ |
|---|---|
| 5 °C | 0,920 |
| **4 °C** | **1,000** ← càng lạnh càng khoẻ?! |

Pin LiPo lạnh thì tụt dung lượng. Quy tắc cũ làm `E_available` tính **thừa** →
biên dự trữ ảo → **cho bay chuyến không đủ pin**. Đúng loại lỗi đề tài này sinh
ra để chống. Em sửa thành kẹp ở giá trị biên 0,9203, và có test quét từ 40 °C
xuống −10 °C bắt buộc κ **không bao giờ tăng ngược**.

**B6 — máy bay trong dữ liệu vượt MTOW.** Nó nặng 3.680–4.180 g, vượt giới hạn
3.600 g ở **mọi** cấu hình, vì mang thêm 1.249 g thiết bị đo. Áp thẳng HR-3 thì
192/192 chuyến NO-FLY, benchmark vô nghĩa. Bỏ HR-3 thì mất một ràng buộc an toàn
thật. Giải: **hai hồ sơ máy bay** — `M100_stock` (khung 2.355 g, HR-3 chặn bình
thường) và `CMU_instrumented` (khung 3.680 g, HR-3 báo "đã biết là vượt", không
chặn).

**B7 — cự ly là khứ hồi.** Tra bài gốc: chuyến bay CMU là **vòng kín tam giác,
quay về đúng điểm cất cánh**; tải gắn Velcro, mang suốt chuyến, không thả. Bộ dữ
liệu **không có điểm giao hàng**. Hệ quả: envelope 420–610 m là **tổng quãng
bay**, tương đương cự ly giao hàng một chiều **≈ 210–305 m**. Khi viết bài phải
nói rõ đang dùng cách nào, không thì **sai gấp đôi**.

## 10. Hai thiếu sót nhóm tự tìm ra và đã vá

Ngày 15/10 em rà lại, đối chiếu **từng chữ** bảng Mục 12.1, phát hiện hai tiêu
chí chưa đáp ứng. Cả hai **không phải lỗi code** — code chạy đúng điều đã thiết
kế — mà là **thiếu một phần thiết kế**.

**RS-1** → Mục 12.1 đòi *"one-way versus round-trip distance explicit"*. Trước đó
**không chỗ nào** trong repo nhắc tới. Đã tra bài gốc và chốt thành quyết định B7
ở trên.

**RS-2** → Mục 12.1 đòi *"conditional verdicts require an explicit mitigation"*.
Bản đầu trả CONDITIONAL kèm một dòng lý do rồi hết — **một ngõ cụt**, người điều
phối không biết làm gì tiếp.

Giờ nó là trạng thái **có đường ra**: hệ thống đề xuất các biện pháp **thực sự
đổi được phán quyết**, người duyệt chọn một, rồi đánh giá lại. Bảy biện pháp —
sạc pin, đổi pin, đợi gió, đợi ấm, giảm tải, giảm tốc, rút tuyến.

Và `propose()` **chạy thử từng biện pháp trước khi đề xuất** — đó là INV-7. Trên
192 chuyến: **213 đề xuất, 0 cái vô dụng**.

Một ví dụ cho thấy INV-7 làm việc: giảm tốc 8 → 6 m/s **không xuất hiện** trong
danh sách, vì nó chỉ bớt 0,47 Wh — chưa đủ vượt ngưỡng. Hệ thống **không bày ra
thứ không giải quyết được gì**.

Biện pháp cũng **không lật được NO-FLY**: áp "sạc pin" lên chuyến vi phạm gió vẫn
ra NO-FLY. Có test riêng khoá điều này — nếu không, biện pháp sẽ thành **cửa sau
để lách luật cứng**.

Em giữ lại mục này trong tài liệu để truy vết, và vì nó là ví dụ tốt: **đọc kỹ
yêu cầu rồi đối chiếu từng dòng quan trọng hơn chạy thêm thí nghiệm.**

---

# PHẦN B — Bốn chỗ nói sai là đổ lập luận

| Đừng nói | Nói |
|---|---|
| "D2 trả về 22 Wh" | "D2 trả về số riêng cho **từng chuyến**, dải 13–38 Wh. Chuyến trong ví dụ là 22,0." |
| "ngưỡng trên là 26,7%" | "26,7% là **của chuyến này**. Công thức có chia cho E_required nên mỗi chuyến một ngưỡng." |
| "D3 dùng mô hình Random Forest" | "**Sản phẩm** D3 không chứa mô hình nào. INV-6 quét mã nguồn để chứng minh." |
| "5 chuyến đó không bay được" | "Hệ thống **không đủ cơ sở để bảo đảm** 5 chuyến đó — khác với không bay được." |

**Lưu ý suốt buổi:** luôn nói **"sản phẩm D3"** hoặc **"mô hình D3"**, không nói
"D3" trần. Sản phẩm D3 là bộ máy quyết định; mô hình D3 là Random Forest. Hai
thứ khác nhau.

---

# PHẦN C — Ba câu hỏi chắc chắn bị hỏi

### "Sao biết bộ máy này đúng, nếu không có đáp án để so?"

Không đo được độ chính xác — bộ dữ liệu không có nhãn. Nên nhóm em kiểm **bảy
tính chất phải luôn đúng**, 2.326 trường hợp, 0 vi phạm. Và việc đánh giá hành vi
quyết định thuộc sản phẩm **D4** theo §4.7, chưa làm.

### "20% là ở đâu ra? Sao không 10% hay 30%?"

Nó là **tham số chính sách**, không phải con số tìm ra từ dữ liệu. §5.7 gọi đúng
như vậy. Nên P§4.5 **bắt buộc** báo cả ba mức 10%, 20%, 30% — nguyên văn *"a
finding that holds only at one arbitrary reserve setting is not a finding about
the method."* Hàm `sweep_reserve()` chạy cả ba.

### "Còn thiếu gì ở D3?"

Một việc em cần thầy quyết: hiện hệ thống **chưa có luật về SoC tối thiểu để hạ
cánh**. Em tính thử bằng mô hình vật lý với tốc độ hạ 1,5 m/s: ở độ cao 100 m,
năng lượng hạ cánh là 5,9 Wh — chiếm 24% năng lượng chuyến, tức **vượt dự trữ
20%**. Có **64 trên 192 chuyến** ở tình trạng đó.

Nghĩa là hệ thống hiện tại **có thể trả FLY cho một chuyến không đủ pin để hạ
cánh**.

Em đã kiểm: tiêu chí nghiệm thu D3 ở Mục 12.1 **không** có yêu cầu này, nên D3
vẫn đạt 13/13. Nhưng em muốn báo thầy để quyết có bổ sung hay không. *(OI-D3-1)*

---

# Truy nguồn

| Muốn gì | File |
|---|---|
| Bản nộp thầy | `reports/decision_engine_report.md` |
| Luật chơi đóng băng | `configs/d3_protocol.yaml` v1.2.0 |
| Bảng 7 bất biến | `reports/d3_invariant_check.csv` |
| Bảng 187/5/0 | `reports/d3_verdict_grid.csv` |
| SoC tối thiểu | `reports/d3_min_soc_per_flight.csv` |
| Tham số và nguồn | `reports/parameter_table.md` |
| Hàm quyết định | `src/decision_rules.py` → `assess()` |
| Bảy biện pháp | `src/mitigations.py` → `propose()` |
