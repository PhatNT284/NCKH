# Sản phẩm D3 — Bộ máy quyết định

> **Đây không phải sản phẩm bàn giao.** Bản nộp thầy là
> `../../reports/decision_engine_report.md`. File này là bài giải thích cho
> người trong nhóm: đã làm gì, vì sao làm vậy, và chỗ nào còn thiếu.

Bám **Mục 12** và **Mục 12.1** của file thầy, cộng §5.4, §5.6, §5.7, §4.6, P§4.2.

---

## 1. Vì sao cần D3

Sản phẩm D2 trả lời được *"chuyến này tốn bao nhiêu Wh"* — một con số riêng cho
từng nhiệm vụ, trong dải khoảng 13–38 Wh, sai trung bình 0,66 Wh.

Không người điều phối nào ra lệnh cất cánh dựa trên con số đó. Họ cần nghe:
**bay được, bay có điều kiện, hay không được bay**.

D3 là cây cầu giữa hai thứ đó.

Và đây cũng là **đóng góp mới của cả đề tài**. Dự báo năng lượng UAV đã có nhiều
người làm. Cái chưa ai làm chuẩn là gắn nó vào một quy trình quyết định có dự
trữ an toàn, luật cứng, và khai báo rõ giới hạn hiệu lực.

---

## 2. Một ví dụ chạy suốt

Mọi con số dưới đây là của **riêng chuyến này** — chuyến khác thì ra số khác.

Sáng mai có chuyến giao hàng:

> Mang 250 g, bay 472 m, cao 50 m, tốc độ 8 m/s.
> Dự báo gió 3 m/s, trời 15 °C. Pin đang 30 %, sức khoẻ pin còn 95 %.

### Bước 1 — Pin cho được bao nhiêu

```
99,9 Wh  ×  0,30  ×  0,95  ×  0,995  =  28,3 Wh
   ↑         ↑        ↑        ↑
 ghi trên   SoC      SoH    κ(15 °C)
   vỏ
```

### Bước 2 — Chuyến cần bao nhiêu

Mô hình `D2_ridge_preflight` trả về **22,0 Wh** cho chuyến này. Sai số trung
bình 0,66 Wh.

Con số đó **đã bao gồm** năng lượng cất cánh và hạ cánh — xem mục 3b.

### Bước 3 — Có được phép bay không

Kiểm sáu luật, không liên quan gì tới pin:

```
gió 3 m/s        ≤ 10           ✓
15 °C            trong −10…40   ✓
khối lượng       ≤ 3.600 g      ✓
tốc độ 8 m/s     ≤ 17           ✓
cự ly 472 m      trong 420–610  ✓
tải 250 g        trong 0–500    ✓
```

### Bước 4 — Quyết định

```
Dư  =  28,3 − 22,0  =  6,3 Wh  =  28,8 %

        20 %            26,7 %
─────────┼────────────────┼─────────→
 NO-FLY    CONDITIONAL       FLY
                              ↑
                           28,8 %
```

**→ FLY**, và `actionable = True` nên được phép tiến hành.

Nếu rơi vào CONDITIONAL thì `actionable = False` cho tới khi chọn một biện pháp
giảm thiểu — xem mục 11.

---

## 3. Hai vạch ở đâu ra — chỗ D2 chảy vào D3

**Vạch dưới 20 %** là hệ số dự trữ `r` của thầy. Để dành phòng gió đổi hướng,
bay vòng chờ, lệch tuyến.

**Vạch trên 26,7 %** = 20 % **cộng sai số của chính mô hình D2**.

Vì con số "cần 22,0 Wh" là **mô hình đoán**, không phải đo. Thực tế có thể là
23,5 Wh. Hệ số 20 % chống rủi ro ngoài trời — nó **không** chống việc mô hình
đoán sai. Đó là rủi ro riêng, phải cộng riêng.

Cộng bao nhiêu? Lấy từ chính kết quả D2: 95 % số chuyến có sai số dưới
**1,469 Wh**. Chia cho 22 Wh ra 6,7 %.

```
R_fly = r + p95(|phần dư|) / E_required
```

Vì có phép **chia cho `E_required`**, vạch trên **khác nhau ở mỗi chuyến**.
Con số 26,7 % là của riêng ví dụ này. Chuyến cần ít Wh thì phần dự phòng bất
định chiếm tỷ lệ cao hơn.

Cách này đúng chỉ dẫn §4.7 của thầy: *"a documented uncertainty allowance"* rút
từ phần dư **đo được**, không phải từ chính mô hình. Lấy từ chính mô hình thì
đánh giá thành vòng tròn và luôn cho kết quả đẹp.

**Đây là lý do thầy bắt làm xong D2 mới được làm D3.** Không có D2 thì con số
6,7 % kia là bịa.

---

## 3b. Điều `r` KHÔNG bao gồm — quyết định B9

Đây là chỗ dễ hiểu sai nhất, nên ghi riêng một mục.

Câu hỏi hay gặp: *"20 % đó có bao gồm năng lượng để hạ cánh không?"*

**Không. Và không cần.** Năng lượng hạ cánh nằm ở chỗ khác.

P§4.5 cho công thức ngân sách:

```
E_required = E_outbound + E_return + E_hover          (4)
```

và kèm một ràng buộc: *"subject to an explicit convention that prevents double
counting. Whether the stated route distance is one-way or round-trip, **whether
take-off and landing energy is already contained in the estimator's output**,
whether the return leg carries the payload, and what cruise speed and altitude
are assumed are all recorded in the mission record and fixed before
evaluation."*

Bốn quy ước phải khai. Nhóm chốt như sau:

| | Quy ước | Chốt |
|---|---|---|
| 1 | cự ly một chiều hay khứ hồi | **khứ hồi** (B7) |
| 2 | năng lượng cất/hạ cánh đã trong output chưa | **đã có** |
| 3 | chặng về có mang tải không | **có** |
| 4 | giả định tốc độ và độ cao hành trình | tốc độ ra lệnh, độ cao kế hoạch |
| + | số hạng `E_hover` | **= 0** |

### Vì sao quy ước (2) là "đã có"

Mục tiêu dự báo của D2 là **tổng năng lượng cả chuyến bay**, không phân đoạn
theo pha.

Nhớ lại D1: §4.2 bước 4 cho phép *"If phase segmentation is unreliable, use
total flight energy as the primary target"*, và nhóm chọn phương án đó vì cột
vị trí ở đơn vị độ kèm nhiễu GPS, còn cột vận tốc lệch 2,4 % so với vị trí —
không cắt được ranh giới pha một cách nhất quán.

Mà chuyến bay CMU là vòng kín **đầy đủ**: cất cánh, leo, hành trình, hạ, đáp
đất. Rodrigues et al., mục Methods: *"reaches the launch point again, the UAV
stops and descends at approximately 1.5 m/s"*.

Nên `E_required` **đã bao gồm** năng lượng cất cánh và hạ cánh.

### Hệ quả — hai điều tuyệt đối không được làm

1. **Không cộng thêm** một khoản năng lượng hạ cánh vào `E_required`.
2. **Không nâng `r`** để "bù cho hạ cánh".

Làm một trong hai là **đếm hai lần** — đúng lỗi mà §4.5 sinh ra để chống.

### `E_hover` bằng 0, và vì sao không phải bỏ sót

Công thức (4) có số hạng `E_hover` cho thời gian treo **tại điểm giao hàng**.

Bộ dữ liệu CMU không có điểm giao hàng — tải gắn Velcro, mang suốt chuyến, không
thả. Nên số hạng này bằng 0.

Không phải nhóm bỏ sót. Nó bằng 0 vì nhiệm vụ không có pha treo giao hàng. Nếu
sau này áp cho giao hàng thật thì phải cộng lại, **và phải khai lại quy ước (3)**
vì lúc đó chặng về không mang tải.

### Phát hiện quy ước này thiếu như thế nào

Khi rà câu hỏi *"hệ số dự trữ r = 0,20 bù cho những rủi ro nào?"*. Tra P§4.5 thì
thấy câu trả lời không nằm ở `r` mà nằm ở `E_required`, và thầy có bắt khai báo
rõ — mà repo chưa khai.

Trước bản vá này, một người đọc giao thức có thể kết luận rằng năng lượng hạ
cánh chưa được tính, rồi cộng thêm vào. Đó là lỗi thật, và nó im lặng.

Chi tiết: `../../configs/d3_protocol.yaml` mục
`energy_required.budget_conventions`.

---

## 4. Bốn mức, không phải ba

§5.7 cho ba mức. §4.6 thêm mức thứ tư.

| Mức | Nghĩa |
|---|---|
| FLY | biết đủ, và đủ pin |
| CONDITIONAL | biết đủ, đủ pin nhưng sát ngưỡng — **phải chọn biện pháp mới bay được** |
| NO-FLY | **biết là không được** |
| INSUFFICIENT-DATA | **không biết** |

Phân biệt "không biết" với "biết là không được" quan trọng về vận hành: NO-FLY
thì huỷ chuyến. INSUFFICIENT-DATA thì đi **lấy thêm dữ liệu** rồi chạy lại.

### Chế độ hỏng nguy hiểm nhất

Cách sai là tự điền giá trị mặc định rồi chạy tiếp:

```
thiếu nhiệt độ → coi như 25 °C → dư 40 % → FLY (xanh)
```

Người điều phối nhìn chữ FLY màu xanh và tin. Thực tế hệ thống vừa bịa một con
số rồi dựa vào đó mà kết luận. Hôm đó trời 2 °C thì pin yếu hơn hẳn giả định.

§4.6 nguyên văn: *"does not fall back to a favourable default"*.

Có test riêng chặn:

```python
assert _v(ambient_temp_c=None) == INSUFFICIENT_DATA
assert _v(ambient_temp_c=25.0) == FLY
```

Hai dòng đó phải cho kết quả khác nhau.

---

## 5. Lớp luật cứng — hai mức độ

Thầy viết: *"no score, no model output and no human approval may convert a
hard-rule violation into FLY."*

| Mã | Luật | Nguồn | Vi phạm thì |
|---|---|---|---|
| HR-1 | gió ≤ 10 m/s | DJI | **NO-FLY** |
| HR-2 | −10 ≤ T ≤ 40 °C | DJI | **NO-FLY** |
| HR-3 | khối lượng cất cánh ≤ 3.600 g | DJI | **NO-FLY** |
| HR-4 | tốc độ ≤ 17 m/s | DJI | **NO-FLY** |
| **PH-1** | **pin đủ để hạ cánh** | **P§4.6 + mô hình vật lý nhóm** | **NO-FLY** |
| PD-1 | cự ly 420–610 m | thí nghiệm E2c | không được FLY |
| PD-2 | tải 0–500 g | độ phủ dữ liệu | không được FLY |

**Hai mức khác nhau có chủ đích.**

HR-* và PH-1 là giới hạn vật lý → **chặn tuyệt đối**. Gió 14 m/s là máy bay
không chịu nổi; không đủ pin đáp xuống đất cũng vậy.

PD-* là **giới hạn hiệu lực của mô hình** → máy bay vẫn bay được, nhưng ở đó
mô hình đoán thiếu 29,6 %, nên con số không đáng tin. Hệ thống phải **nói rõ**
thay vì im lặng đưa ra một số sai.

**Ba họ mã, ba nguồn — không được trộn khi trích dẫn:**

| Mã | Trích gì | Mức độ |
|---|---|---|
| HR-1…HR-4 | thông số DJI công bố | VETO |
| **PH-1** | nguyên tắc P§4.6 của thầy + mô hình vật lý của **nhóm** | **VETO** |
| PD-1, PD-2 | thí nghiệm E2c và độ phủ dữ liệu của **nhóm** | DOWNGRADE |

Nguồn gốc và mức độ là **hai trục độc lập**. PH-1 nghiêm như luật DJI nhưng con
số là của nhóm — nên nó mang mã riêng, không phải `HR-5`. Có test canh:
`test_moi_luat_hr_co_ghi_nguon` bắt buộc mọi luật `HR-*` phải có `"DJI"` trong
nguồn, và test đó đã bắt được lỗi này khi luật còn tên `HR-5`.

### PH-1 — sàn năng lượng hạ cánh

P§4.6: *"A minimum state of charge is added, set so that the aircraft retains the
energy required to land from its cruise altitude."*

```
E_hạ = P_treo(khối lượng cất cánh) × (độ cao ÷ 1,5 m/s) ÷ 3600
PH-1:  E_available(SoC, SoH, T)  ≥  E_hạ
```

Năng lượng hạ cánh, hồ sơ CMU (bảng đầy đủ ở `../../reports/d3_landing_energy.csv`):

| Độ cao | tải 0 g | tải 500 g |
|---|---|---|
| 25 m | 2,46 Wh | 2,98 Wh |
| 50 m | 4,93 Wh | 5,97 Wh |
| 75 m | 7,39 Wh | 8,95 Wh |
| 100 m | 9,86 Wh | **11,93 Wh** |

**Đây KHÔNG phải năng lượng hạ cánh bình thường** ở cuối chuyến — cái đó đã nằm
trong `E_required` (mục 3b). PH-1 là sàn cho tình huống **huỷ chuyến giữa đường
và đáp gấp**.

Trên 192 chuyến, PH-1 đòi SoC 2,5–12,0% còn luật dự trữ đòi 16,2–42,0%. Hai dải
**không chồng nhau**, nên PH-1 không đổi phán quyết nào — nhưng ở mức pin 10% nó
chặn 30 chuyến, tức không phải code chết. Tác dụng thật sẽ thấy ở D4, trên kịch
bản "chuyến ngắn bay cao" mà bộ dữ liệu CMU không có.

---

## 6. Thứ tự xét — không được đổi

```
1. Vi phạm luật cứng VETO  → NO-FLY ngay
2. Thiếu đầu vào           → INSUFFICIENT-DATA
3. Tính biên dự trữ        → FLY / CONDITIONAL / NO-FLY
4. Đang ngoại suy PD-*     → hạ FLY xuống CONDITIONAL
```

Bước 1 phải trước bước 2. Nếu đảo lại: gió 14 m/s **và** thiếu SoC sẽ ra "thiếu
dữ liệu" — che mất một NO-FLY thật, và người ta sẽ đi đo SoC vô ích rồi mới biết
gió quá mạnh.

---

## 7. Khối thứ sáu — dấu còn hạn

Năm khối trên tính ra một phán quyết **tại một thời điểm**. Khối này hỏi: còn
hiệu lực không?

```
08:00  đánh giá            → FLY
08:30  gió cập nhật 3 → 12 m/s
09:00  điều phối thấy FLY, cho bay
```

Không ai làm gì sai. Chỉ là không ai bảo hệ thống rằng dữ liệu đã đổi.

Bảy thứ làm hết hạn: gió, nhiệt độ, SoC, SoH, kế hoạch bay, ngưỡng, và **mô hình
D2**. Cái cuối hay bị quên — D2 huấn luyện lại thì mọi đánh giá cũ đều hết hạn.

Khi hết hạn, ô `verdict` **vẫn ghi FLY** (sự kiện lịch sử, phải giữ), nhưng
`may_proceed` thành `False`.

Kèm theo là **bản ghi nhiệm vụ** — JSON chứa đầu vào, đầu ra, và phiên bản của
mọi thứ, để ba tháng sau mở ra tính lại được y hệt.

Và một ô ghi **kết cục thật**, mặc định "không biết". Vì nếu hệ thống bảo FLY rồi
tự ghi "thành công" thì nó tự chấm điểm chính nó và luôn được 100 %.

---

## 8. Kiểm D3 bằng gì

Đây là câu hay bị hỏi: **không có đáp án thì kiểm kiểu gì?**

Không đo được độ chính xác — bộ dữ liệu không có nhãn *"chuyến này đáng lẽ có nên
bay không"*. Thay vào đó kiểm **bảy tính chất phải luôn đúng**:

| | Nội dung | Trường hợp | Vi phạm |
|---|---|---|---|
| INV-1 | vi phạm luật cứng → không bao giờ FLY | 576 | **0** |
| INV-2 | thiếu đầu vào → không bao giờ FLY | 960 | **0** |
| INV-3 | pin nhiều hơn → phán quyết không xấu đi | 192 | **0** |
| INV-4 | cùng đầu vào → cùng đầu ra | 192 | **0** |
| INV-5 | lưu rồi tính lại → ra đúng phán quyết cũ | 192 | **0** |
| INV-6 | D3 không chứa mô hình học máy nào | 1 | **0** |
| INV-7 | biện pháp giảm thiểu đề xuất ra phải có tác dụng | 213 | **0** |
| **INV-8** | **không đủ pin hạ cánh → không bao giờ FLY** | **768** | **0** |

**3.094 trường hợp, 0 vi phạm**, chạy trên cấu hình của 192 chuyến bay có thật.

INV-8 kiểm **hai chiều**: SoC dưới ngưỡng hạ cánh thì phải NO-FLY, *và* áp biện
pháp giảm thiểu thì **vẫn** NO-FLY. Chiều thứ hai quan trọng không kém — không
có nó thì "sạc thêm pin" thành cửa sau để lách PH-1.

Danh sách bất biến **đọc từ giao thức**, không viết cứng. `run_invariants()` lấy
`invariants.tests` rồi tra hàm kiểm, và ném lỗi nếu giao thức khai một bất biến
mà không có hàm. Trước đó viết cứng ở bốn chỗ, nên đã sai **ba lần** — giao thức
khai 8 mà bảng chỉ in 7, im lặng.

INV-6 đáng nói: nó **quét mã nguồn** tìm `.fit()`, `.predict()` và `import
sklearn` trong bốn module D3. Khai "D3 không có mô hình học máy" rồi để đó thì
vô nghĩa — phải kiểm được.

Lần chạy đầu nó báo chính file quét vi phạm, vì trong file có chuỗi regex
`r"\.fit\s*\("`. Sửa: bỏ cả chuỗi ký tự trước khi quét. Rồi kiểm hai chiều —
thêm `.fit()` thật vào thì nó bắt được, hoàn nguyên thì sạch. **Một phép kiểm
luôn báo "đạt" thì vô dụng.**

---

## 9. Chạy trên 192 chuyến — và kết quả đẹp nhất

### Phải đọc trước

Đây **không phải phép chấm điểm**. §4.7 ghi rõ việc đánh giá hành vi quyết định
thuộc sản phẩm **D4**, trên kịch bản tổng hợp. Chạy ở đây để minh hoạ và kiểm
bất biến.

Ba thứ phải khai báo: `E_required` lấy từ dự báo out-of-fold của D2; gió đo được
dùng thay gió dự báo; SoC/SoH/nhiệt độ là tham số kịch bản.

### Kết quả

Từ SoC 0,50 trở lên, bảng **đứng yên mãi mãi**:

```
187 FLY  ·  5 CONDITIONAL  ·  0 NO-FLY
```

Năm chuyến kẹt ở CONDITIONAL **dù pin đầy 100 %**:

| Chuyến | Cự ly | Tải |
|---|---|---|
| 268 | 830,7 m | 500 g |
| 269 | 837,0 m | 500 g |
| 270 | 837,5 m | 250 g |
| 271 | 834,6 m | 0 g |
| 272 | 841,4 m | 250 g |

Đúng **năm chuyến R6 của thí nghiệm E2c** — những chuyến D2 đoán thiếu 29,6 %.

Luật PD-1 chặn chúng không phải vì pin, mà vì cự ly nằm ngoài envelope. Hệ thống
không nói "không bay được"; nó nói **"tôi không đủ cơ sở để bảo đảm chuyến này"**.

Đây là kết quả mạch lạc nhất của cả D2 + D3: một phát hiện thống kê ở tuần 5 trở
thành hành vi kiểm chứng được của hệ thống ở tuần 7.

### Một con số dùng được

SoC tối thiểu để bay, `r = 0,20`: **trung vị 26,5 %, p90 35,1 %, lớn nhất 42,0 %**.

---

## 10. Tám quyết định đã chốt

| Mã | Câu hỏi | Chốt |
|---|---|---|
| B3 | κ(T) ngoài dải hiệu chỉnh dùng gì? | kẹp một phía: dưới 4,5 °C giữ 0,9203 |
| B4 | ba mức cần hai vạch, thầy cho một số | vạch trên = `r` + p95(phần dư)/E |
| B5 | thiếu đầu vào xử sao? | fail closed, thêm mức thứ tư |
| B6 | HR-3 áp sao khi máy bay vượt MTOW? | tách hai hồ sơ máy bay |
| **B7** | cự ly là một chiều hay khứ hồi? | **khứ hồi** — envelope đọc hai cách |
| **B8** | CONDITIONAL cần gì để thực thi được? | **phải chọn biện pháp và đánh giá lại** |
| **B9** | ngân sách năng lượng gồm những gì? | **bốn quy ước §4.5 — xem mục 3b** |
| **B10** | P§4.6 đòi sàn SoC, cài thế nào? | **luật `PH-1`, mức VETO — xem mục 5** |

### B3 đáng kể nhất

Quy tắc cũ cho κ = 1 với mọi nhiệt độ ngoài dải 4,5–18,4 °C. Đúng ở phía nóng,
**sai ở phía lạnh**:

| T | Quy tắc cũ |
|---|---|
| 5 °C | 0,920 |
| **4 °C** | **1,000** ← càng lạnh càng khoẻ?! |
| −5 °C | 1,000 |

Pin LiPo lạnh thì tụt dung lượng. Quy tắc cũ làm `E_available` tính **thừa** →
biên dự trữ ảo → **cho bay chuyến không đủ pin**. Đúng loại lỗi đề tài này sinh
ra để chống.

Sửa thành giữ ở giá trị biên 0,9203. Có test quét từ 40 °C xuống −10 °C bắt buộc
κ **không bao giờ tăng ngược**.

### B6 — vấn đề thật

Máy bay trong bộ dữ liệu nặng 3.680–4.180 g, **vượt MTOW 3.600 g ở mọi cấu
hình**, vì mang thêm 1.249 g thiết bị đo (cảm biến gió + máy tính trên khoang).

Áp thẳng HR-3 thì 192/192 chuyến NO-FLY, benchmark vô nghĩa. Bỏ HR-3 thì mất
một ràng buộc an toàn thật.

Giải: hai hồ sơ. `M100_stock` (khung 2.355 g, HR-3 chặn bình thường) và
`CMU_instrumented` (khung 3.680 g, HR-3 báo "đã biết là vượt", không chặn).

Nguồn: Rodrigues et al. 2021, mục Methods — *"The mass of the airframe is 1831 g…
the battery 600 g… the anemometer and pole 136 g… the onboard computer with small
sensors and wiring 1113 g… totaling 3680 g"*.

---

## 11. Bốn thiếu sót phát hiện khi rà soát — đã vá

Ngày 15/10, 19/10 và 20/10/2026 rà lại, đối chiếu **từng chữ** bảng Mục 12.1,
P§4.5 và P§4.6, phát hiện bốn chỗ chưa đáp ứng. Cả ba **không phải lỗi code** — code
chạy đúng điều đã thiết kế — mà là **thiếu một phần thiết kế hoặc một phần khai
báo**. Đã vá.

Giữ lại mục này để truy vết, và vì nó là ví dụ tốt: đọc kỹ yêu cầu rồi đối chiếu
từng dòng quan trọng hơn chạy thêm thí nghiệm.

### RS-1 → quyết định B7 — cự ly là khứ hồi

Mục 12.1 đòi *"one-way versus round-trip distance explicit"*. Trước đó **không
chỗ nào** trong repo nhắc tới.

Tra bài gốc, mục Methods:

> *"tracks a triangular wind-neutral path"* ·
> *"reaches the launch point again, the UAV stops and descends"*

Chuyến bay CMU là **vòng kín tam giác, quay về đúng điểm cất cánh**; tải gắn
Velcro, **mang suốt chuyến, không thả**. Bộ dữ liệu **không có điểm giao hàng** —
đây là đường bay thử.

Hệ quả nặng nhất: `distance_2d_m` ≈ 472 m là vòng kín. Một nhiệm vụ giao hàng
thật "472 m tới khách" bay ~944 m khứ hồi, **ngoài envelope**.

| Cách đọc envelope | Dải |
|---|---|
| Tổng quãng bay (như dữ liệu) | 420–610 m |
| Cự ly giao hàng một chiều | **≈ 210–305 m** |

Khi viết bài phải nói rõ đang dùng cách nào, không thì sai gấp đôi.

Và một chuyện chưa giải thích được (**RS-3**): tổng `distance_2d_m` của 192
chuyến là 92,8 km, trong khi bài gốc ghi bộ dữ liệu phủ *"approximately 65
kilometres"* cho 209 chuyến. Lệch ~43 %. Nghi phép cộng haversine theo từng mẫu
**cộng dồn cả nhiễu GPS lúc treo**. Chưa kết luận, ghi lại để kiểm.

### RS-2 → quyết định B8 — CONDITIONAL phải có biện pháp

Mục 12.1 đòi *"conditional verdicts require an explicit mitigation"*; §2.3 nói
rõ CONDITIONAL chỉ thực thi được khi **đã chọn một biện pháp được duyệt và đánh
giá lại**.

Bản đầu trả CONDITIONAL kèm một dòng lý do rồi hết — **một ngõ cụt**. Người điều
phối không biết làm gì tiếp.

Giờ nó là trạng thái **có đường ra**:

```
CONDITIONAL, thực thi được = False
    ↓  hệ thống đề xuất các biện pháp THỰC SỰ đổi được phán quyết
  M1  Sạc thêm pin         CONDITIONAL -> FLY
  M2  Đổi sang pin TB48D   CONDITIONAL -> FLY
    ↓  người duyệt chọn một
  đánh giá lại → FLY, thực thi được = True
```

Bảy biện pháp, hai nhóm:

| Nhóm | Biện pháp | Đổi cái gì |
|---|---|---|
| A | M1 sạc pin · M2 đổi pin · M3 đợi gió · M4 đợi ấm | năng lượng khả dụng hoặc ràng buộc |
| B | M5 giảm tải · M6 giảm tốc · M7 rút tuyến | **nhu cầu năng lượng** |

Nhóm B đổi `E_required` nên **bắt buộc dự báo lại**. Hàm dự báo truyền từ ngoài
vào, D3 không được tự import mô hình — INV-6 vẫn còn hiệu lực. Không có hàm dự
báo thì nhóm B bị bỏ qua và **báo rõ**, không im lặng.

Hai điều kiện để một biện pháp là hợp lệ (§2.3):

1. Phải đổi **nhu cầu năng lượng hoặc ràng buộc**. "Cẩn thận hơn khi bay" không
   phải biện pháp.
2. Phải **thực sự cải thiện** phán quyết khi áp dụng → đó là **INV-7**.

`propose()` **chạy thử từng biện pháp** trước khi đề xuất. Nhiệm vụ đã FLY sẵn
thì đề xuất 0 biện pháp. Trên 192 chuyến: 213 đề xuất, 0 cái vô dụng.

Một ví dụ nhỏ cho thấy INV-7 làm việc: M6 (giảm tốc 8 → 6 m/s) **không xuất
hiện** trong danh sách, vì nó chỉ bớt 0,47 Wh — chưa đủ vượt ngưỡng. Hệ thống
không bày ra thứ không giải quyết được gì.

Và biện pháp **không lật được NO-FLY**: áp M1 lên một chuyến vi phạm HR-1 vẫn ra
NO-FLY, `actionable = False`. Có test riêng khoá điều này — nếu không, biện pháp
sẽ thành cửa sau để lách lớp luật cứng.

### RS-4 → quyết định B9 — quy ước ngân sách năng lượng

P§4.5 đòi khai **bốn** quy ước ngân sách năng lượng vào mission record, để chống
đếm hai lần. Repo chỉ khai **một** (cự ly khứ hồi, B7).

Phát hiện khi rà câu hỏi *"hệ số dự trữ r = 0,20 bù cho những rủi ro nào?"*. Tra
P§4.5 thì thấy câu trả lời không nằm ở `r` mà nằm ở `E_required`.

Chi tiết đầy đủ ở **mục 3b** phía trên. Tóm lại:

| Quy ước | Chốt |
|---|---|
| cự ly | khứ hồi (đã có, B7) |
| năng lượng cất/hạ cánh | **đã nằm trong output mô hình** |
| chặng về mang tải | có |
| giả định hành trình | tốc độ ra lệnh, độ cao kế hoạch |
| `E_hover` | 0 Wh |

**Không đổi hành vi hệ thống.** Đây là khai báo điều hệ thống **đang** làm.

Nhưng nó chặn một lỗi thật: trước bản vá, một người đọc giao thức có thể kết
luận rằng năng lượng hạ cánh chưa được tính, rồi cộng thêm vào `E_required` hoặc
nâng `r` lên — tức đếm hai lần, và không ai phát hiện ra vì cả hai hướng đều
"trông có vẻ an toàn hơn".

### RS-5 → quyết định B10 — sàn năng lượng hạ cánh

P§4.6 đòi *"a minimum state of charge… set so that the aircraft retains the
energy required to land from its cruise altitude"*. Repo chưa cài.

Phát hiện khi rà câu hỏi *"hệ số dự trữ 20% bù cho những gì"*. Nhóm **từng tưởng
đây là việc cần hỏi thầy** — tra lại P§4.6 thì thấy thầy đã chọn sẵn cách làm,
việc của nhóm chỉ là tính và cài đặt. Bài học: tra file trước khi kết luận là
thiếu.

Chi tiết ở **mục 5** phía trên. **Đổi hành vi hệ thống** nên đã chạy lại
`evaluation_decision` và cập nhật bốn CSV — bảng phán quyết không đổi (187/5/0),
đã xác nhận bằng số.

#### Ba lỗi phát sinh khi cài, do chính bộ test bắt

| | Lỗi | Test bắt |
|---|---|---|
| (a) | đặt tên `HR-5` trong khi nguồn không phải DJI | `test_moi_luat_hr_co_ghi_nguon` |
| (b) | chữ ký hàm nhận `e_available_Wh`, phá §4.6 | `test_lop_nay_khong_nhan_dau_ra_mo_hinh` |
| (c) | ngưỡng hạ cánh mặc định κ = 1, tức **lạc quan** | `test_dung_ngay_tai_nguong_thi_pass` |

Lỗi (c) là lỗi trong test, nhưng nó phơi ra một cái bẫy thật: ở 0 °C thì
κ = 0,9203 và ngưỡng thật cao hơn mặc định **8,66%**. Ai dùng
`min_soc_for_landing()` mà quên truyền κ sẽ **ước thiếu** lượng pin cần. Đã thêm
test khoá tính chất đó.

Hai test (a) và (b) là loại đáng giá nhất trong repo: chúng không kiểm một con
số, mà kiểm một **quy ước** (`HR-*` ⇒ nguồn DJI) và một **ràng buộc kiến trúc**
(§4.6: lớp luật cứng không nhận đầu ra mô hình). Giữ lại, đừng xoá.

---

## 12. Bàn giao sang D4

| Cần gì | Ở đâu |
|---|---|
| Hàm quyết định | `src/decision_rules.py` → `assess()` |
| Quét hệ số dự trữ | `src/decision_rules.py` → `sweep_reserve()` |
| Bản ghi nhiệm vụ | `src/workflow_state.py` → `MissionRecord` |
| Dải tham số có dữ liệu đỡ lưng | `../../reports/parameter_table.md` mục 5 |

Bốn điều bắt buộc mang theo:

1. **Nhãn tham chiếu phải độc lập với D2.** Dùng D2 sinh nhãn rồi lại dùng D2 dự
   báo là vòng tròn, luôn cho kết quả đẹp. Lấy nhãn từ phân phối phần dư đo được.
2. **SoH và nhiệt độ là ngoại suy thuần** — dán nhãn rõ (§6/E3).
3. **Chạy độ nhạy `E_nominal = 129,96 Wh`** — bắt buộc, §8 mục 3.
4. **Giữ nguyên quy ước ngân sách của B9.** Bộ sinh kịch bản không được cộng
   thêm năng lượng hạ cánh, và phải khai rõ lấy mẫu cự ly theo cách đọc nào.

---

## 13. Việc còn treo

| Mã | Việc | Trạng thái |
|---|---|---|
| ~~OI-D3-1~~ | ~~Sàn an toàn khi có sự cố~~ | **ĐÓNG 20/10** — luật `PH-1`, quyết định B10 |
| ~~OI-D3-3~~ | ~~Duy ký kiểm chéo WP3~~ | **ĐÓNG 20/10** |
| RS-3 | Tổng cự ly 92,8 km vs ~65 km bài gốc | chưa kết luận, không chặn |
| OI-4 | Hai phiên bản thời lượng D2 | chờ thầy, không chặn |

**Sản phẩm D3 nghiệm thu 20/10/2026** — 13/13 tiêu chí Mục 12.1, Duy đã kiểm
chéo. Cổng chặn sang D4 đã mở.

---

## 14. Đọc tiếp

| Muốn gì | Đọc |
|---|---|
| Bản nộp thầy | `../../reports/decision_engine_report.md` |
| Luật chơi đóng băng | `../../configs/d3_protocol.yaml` v1.4.0 |
| Tham số và nguồn | `../../reports/parameter_table.md` |
| Vì sao chọn Ridge | `../../reports/model_selection_report.md` |
| Trạng thái mọi sản phẩm | `../../reports/deliverables.md` |
| Chưa biết gì về học máy | `../cach_lam/huan_luyen_va_kiem_chung.md` |
| Gặp từ lạ | `../thuat_ngu.md` |