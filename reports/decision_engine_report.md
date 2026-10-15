# Sản phẩm D3 — Bộ máy quyết định có ý thức an toàn

**Báo cáo bàn giao theo Mục 12 · nghiệm thu theo Mục 12.1**

| | |
|---|---|
| Gói công việc | WP3 |
| Người làm | Phát |
| Người kiểm chéo | Duy |
| Tuần | 7 |
| Giao thức | `configs/d3_protocol.yaml` v1.2.0 |
| Ngày | 15/10/2026 |

Mục 12 yêu cầu: *"available-energy model, mission-energy budget, reserve-margin
calculation, hard-rule layer, three-level verdict"*.

---

## 1. Bộ máy làm gì

D2 trả lời *"chuyến này tốn bao nhiêu Wh"*. Đó là một con số, chưa phải quyết
định. D3 biến con số đó thành câu trả lời mà người điều phối dùng được:
**bay được, bay có điều kiện, hay không được bay**.

```
Kế hoạch bay + trạng thái pin + môi trường
                    │
   ┌────────────────┼────────────────┐
   │                │                │
(a) pin cho     (b) chuyến cần   (d) luật cứng
   bao nhiêu       bao nhiêu        (gió, tải, nhiệt độ…)
   │                │                │
   └────────┬───────┘                │
            │                        │
     (c) biên dự trữ R               │
            │                        │
            └────────┬───────────────┘
                     │
          (e) PHÁN QUYẾT BỐN MỨC
     FLY · CONDITIONAL · NO-FLY · INSUFFICIENT-DATA
                     │
            (f) dấu còn hạn, bản ghi nhiệm vụ
```

Công thức, §5.4 và §5.6:

```
E_available = E_nominal × SoC × SoH × κ(T)
M = E_available − E_required
R = (E_available − E_required) / E_required
```

**D3 không chứa mô hình học máy nào.** Toàn bộ là công thức và luật. Điều này
được khai trong giao thức (`foundation.d3_contains_no_learned_model`) và kiểm
bằng phép quét mã nguồn (INV-6), không phải chỉ nói suông.

---

## 2. Sáu khối, sáu file

| Khối | File | Nguồn |
|---|---|---|
| a. Năng lượng khả dụng | `src/available_energy.py` | §5.4, Eq (2) |
| b. Ngân sách nhiệm vụ | gọi `D2_ridge_preflight` | `reports/model_selection_report.md` |
| c. Biên dự trữ | `src/decision_rules.py` | §5.6 |
| d. Lớp luật cứng | `src/safety_invariants.py` | §4.6, §5.7 |
| e. Phán quyết bốn mức | `src/decision_rules.py` | §5.7 + §4.6 |
| f. Dấu còn hạn, bản ghi | `src/workflow_state.py` | P§4.2 |
| g. Biện pháp giảm thiểu | `src/mitigations.py` | Mục 12.1, §2.3 |

Luật chơi đóng băng ở `configs/d3_protocol.yaml`. Mã nguồn **không chứa con số
viết cứng** — mọi ngưỡng đọc từ giao thức, nên đổi tham số là sửa giao thức và
ghi `change_log`, không sửa code.

---

## 3. Ba quyết định đã chốt

### B3 — κ(T) ngoài dải hiệu chỉnh

Quy tắc cũ cho κ = 1 với mọi nhiệt độ ngoài dải 4,5–18,4 °C của Kim et al. Đúng
ở phía nóng, **sai ở phía lạnh**: tại 4,4 °C nó nhảy từ 0,920 lên 1,000, tức
càng lạnh càng giả định pin càng khoẻ. Pin LiPo lạnh thì tụt dung lượng, nên
quy tắc cũ làm `E_available` tính thừa → biên dự trữ ảo → **cho bay chuyến không
đủ pin**.

Sửa thành kẹp một phía: dưới 4,5 °C giữ ở giá trị biên 0,9203. Vẫn không ngoại
suy (§5.4 cấm), liên tục, và bảo thủ.

### B4 — Hai ngưỡng cho ba mức

§5.7 cho một con số `r = 0,20`, nhưng ba mức cần hai vạch.

```
R_min = r
R_fly = r + p95(|phần dư|) / E_required  =  r + 1,4687 / E_required
```

Hệ số dự trữ `r` chống **rủi ro vận hành** — gió, vòng chờ, lệch tuyến. Nó không
chống **sai số dự báo** của chính mô hình; đó là rủi ro riêng, phải cộng riêng.
Khoản cộng thêm lấy từ phân vị 95 của phần dư out-of-fold của D2-b, đúng cách
§4.7 chỉ: *"a documented uncertainty allowance"* rút từ phần dư **đo được**,
không phải từ chính mô hình.

Với chuyến trung bình 21,3 Wh thì vạch trên ≈ 26,9%.

**Đây là chỗ kết quả D2 thực sự chảy vào D3.** Không có D2 thì con số này là bịa.

### B5 — Thiếu đầu vào

§4.6 nguyên văn: *"a missing, invalid, out-of-range or stale safety-critical input
does not fall back to a favourable default; it produces NO-FLY or an explicit
insufficient-data outcome."*

```
thiếu            → INSUFFICIENT-DATA
sai / ngoài dải  → NO-FLY
hết hạn          → INSUFFICIENT-DATA
```

Đề xuất ban đầu của nhóm (thiếu → cao nhất CONDITIONAL) **không đạt**, vì
CONDITIONAL vẫn là một dạng cho bay, tức vẫn là "favourable default".

### B7 — Cự ly là khứ hồi, không phải một chiều

Mục 12.1 đòi *"one-way versus round-trip distance explicit"*. Bản đầu của báo
cáo này **không nêu**, phát hiện khi rà soát ngày 15/10/2026.

Rodrigues et al. 2021, mục Methods: chuyến bay là **vòng kín tam giác, quay về
đúng điểm cất cánh**; tải gắn Velcro, **mang suốt chuyến, không thả**. Bộ dữ
liệu không có khái niệm điểm giao hàng.

Nên envelope hiệu lực đọc được hai cách:

| Cách đọc | Dải |
|---|---|
| Tổng quãng bay (như dữ liệu) | 420–610 m |
| Cự ly giao hàng một chiều | **≈ 210–305 m** |

Một nhiệm vụ giao hàng thật "472 m tới khách" sẽ bay ~944 m khứ hồi, **nằm ngoài
envelope**. Mọi bảng và câu văn phải nói rõ đang dùng cách đọc nào.

### B8 — CONDITIONAL phải có biện pháp giảm thiểu

Mục 12.1 đòi *"conditional verdicts require an explicit mitigation"*; §2.3 nói
rõ CONDITIONAL chỉ thực thi được khi **đã chọn một biện pháp được duyệt và đánh
giá lại**.

Bản đầu trả CONDITIONAL kèm một dòng lý do rồi hết — một nhãn, chưa phải trạng
thái có đường ra. Đã bổ sung `src/mitigations.py` với 7 biện pháp:

| Nhóm | Biện pháp | Đổi cái gì |
|---|---|---|
| A | M1 sạc thêm pin · M2 đổi pin TB48D · M3 đợi gió giảm · M4 đợi trời ấm | năng lượng khả dụng hoặc ràng buộc |
| B | M5 giảm tải · M6 giảm tốc · M7 rút tuyến | **nhu cầu năng lượng** — bắt buộc dự báo lại |

Nhóm B đổi `E_required` nên phải dự báo lại; hàm dự báo truyền từ ngoài vào, D3
không được tự import mô hình (INV-6). Không có hàm dự báo thì nhóm B bị bỏ qua
và **báo rõ**, không im lặng.

`actionable = False` khi CONDITIONAL chưa có biện pháp. Bản ghi nhiệm vụ
(`may_proceed`) tôn trọng cờ này.

### B6 — Hai hồ sơ máy bay

Máy bay trong bộ dữ liệu nặng 3.680–4.180 g, **vượt MTOW 3.600 g ở mọi cấu
hình**, vì mang thêm 1.249 g thiết bị đo. Áp thẳng luật HR-3 thì 192/192 chuyến
thành NO-FLY và benchmark vô nghĩa; bỏ HR-3 đi thì mất một ràng buộc an toàn thật.

| Hồ sơ | Khung | HR-3 |
|---|---|---|
| `M100_stock` | 2.355 g | VETO — hồ sơ vận hành |
| `CMU_instrumented` | 3.680 g | KNOWN_EXCEEDED — ghi nhận, không chặn |

Nguồn khối lượng: Rodrigues et al., *Scientific Data* 8, 155 (2021), mục Methods.

---

## 4. Lớp luật cứng — hai mức độ

§4.6: *"no score, no model output and no human approval may convert a hard-rule
violation into FLY."*

| Mã | Luật | Nguồn | Vi phạm thì |
|---|---|---|---|
| HR-1 | gió ≤ 10 m/s | DJI | **NO-FLY** |
| HR-2 | −10 ≤ T ≤ 40 °C | DJI | **NO-FLY** |
| HR-3 | khối lượng cất cánh ≤ 3.600 g | DJI | **NO-FLY** (hồ sơ stock) |
| HR-4 | tốc độ ≤ 17 m/s | DJI | **NO-FLY** |
| PD-1 | cự ly 420–610 m | thí nghiệm E2c của nhóm | không được FLY |
| PD-2 | tải 0–500 g | độ phủ dữ liệu | không được FLY |

Hai mức độ khác nhau có chủ đích. HR-* là giới hạn vật lý và chứng nhận của nhà
sản xuất → chặn tuyệt đối. PD-* là **giới hạn hiệu lực của mô hình** → máy bay
vẫn bay được, nhưng con số dự báo không đáng tin ở đó, nên hệ thống phải nói rõ
thay vì im lặng. §6/E3 yêu cầu *"clearly label any extrapolated ranges"*.

Khi trích dẫn phải tách hai nguồn: HR-* trích DJI, PD-* trích thí nghiệm của
chính nhóm.

---

## 5. Chạy trên 192 chuyến bay

### Phải đọc trước khi diễn giải

**Đây không phải phép chấm điểm D3.** Bộ dữ liệu CMU không có nhãn *"chuyến này
đáng lẽ có nên bay không"*, nên không có đáp án để so. §4.7 ghi rõ việc đánh giá
hành vi quyết định thuộc **sản phẩm D4**, trên tập kịch bản tổng hợp ≥ 5.000.

Chạy ở đây để minh hoạ, kiểm bất biến trên dữ liệu thật, và sinh bảng cho bài.

### Nguồn số liệu, và ba điều phải khai báo

| Đại lượng | Lấy từ | Ghi chú |
|---|---|---|
| `E_required` | dự báo **out-of-fold** của D2-b | mỗi dự báo đến từ mô hình chưa từng thấy chuyến đó — không rò rỉ |
| Gió | `wind_mean_ms` (gió **thô đo được**) | **xấp xỉ**: bộ dữ liệu không có dự báo gió |
| SoC, SoH, nhiệt độ | **tham số kịch bản** (§4.3) | không có trong bộ dữ liệu |
| Hồ sơ máy bay | `CMU_instrumented` | quyết định B6 |

Ảnh hưởng của việc dùng gió đo được thay gió dự báo là nhỏ: toàn bộ chiến dịch
bay trong dải 2,81–6,67 m/s, **chưa bao giờ chạm giới hạn 10 m/s**, nên HR-1
không bao giờ kích hoạt trên bộ dữ liệu này.

### Cách chạy lại

```bash
python3 -m src.evaluation_decision        # khoảng 25 giây
```

Sinh bốn file vào `reports/`:
`d3_min_soc_per_flight.csv` · `d3_verdict_grid.csv` ·
`d3_scenario_sensitivity.csv` · `d3_invariant_check.csv`

---

## 6. Kết quả

### 6.1 — Sáu bất biến, trên dữ liệu thật

| Bất biến | Nội dung | Số trường hợp | Vi phạm |
|---|---|---|---|
| INV-1 | luật cứng phủ quyết | 576 | **0** |
| INV-2 | fail closed | 960 | **0** |
| INV-3 | đơn điệu theo năng lượng | 192 | **0** |
| INV-4 | tất định | 192 | **0** |
| INV-5 | tính lại từ bản ghi | 192 | **0** |
| INV-6 | không chứa mô hình học máy | 1 | **0** |
| INV-7 | biện pháp giảm thiểu có tác dụng | 213 | **0** |

**2.326 trường hợp, không vi phạm nào.**

Khác với test đơn vị: test đơn vị kiểm vài chục trường hợp do người chọn; bảng
này lấy cấu hình từ 192 chuyến bay có thật.

INV-3 đáng chú ý nhất — nó quét SoC theo 50 bước cho từng chuyến và bắt buộc
phán quyết **không bao giờ xấu đi khi pin nhiều hơn**. Đó cũng là điều kiện tiên
quyết để thuật toán tìm SoC tối thiểu bằng chia đôi ở mục 6.2 có nghĩa.

### 6.2 — SoC tối thiểu để bay

Con số có nghĩa với người vận hành: *pin phải còn ít nhất bao nhiêu phần trăm?*

Với SoH = 1,0 và 15 °C:

| `r` | trung vị | p90 | lớn nhất | khả thi |
|---|---|---|---|---|
| 0,10 | 24,4% | 32,3% | 38,6% | 187/192 |
| **0,20** | **26,5%** | **35,1%** | **42,0%** | **187/192** |
| 0,30 | 28,6% | 37,9% | 45,4% | 187/192 |

Nửa số chuyến cần pin trên ~27%; chuyến nặng nhất cần 42%.

§5.7 gọi `r` là **tham số chính sách**, không phải yêu cầu của cơ quan quản lý
hay nhà sản xuất. P§4.5 bắt báo cả ba mức: *"a finding that holds only at one
arbitrary reserve setting is not a finding about the method."*

### 6.3 — Phân bố phán quyết theo mức pin

Tại `r = 0,20`, SoH = 1,0, 15 °C:

| SoC | FLY | CONDITIONAL | NO-FLY |
|---|---|---|---|
| 0,10 | 0 | 0 | 192 |
| 0,20 | 19 | 15 | 158 |
| 0,25 | 73 | 22 | 97 |
| 0,30 | 134 | 16 | 42 |
| 0,35 | 167 | 13 | 12 |
| 0,40 | 184 | 6 | 2 |
| 0,50 | **187** | **5** | 0 |
| 1,00 | **187** | **5** | 0 |

Từ SoC 0,50 trở lên bảng **đứng yên**: 187 FLY, 5 CONDITIONAL, mãi mãi.

### 6.4 — Năm chuyến không bao giờ đạt FLY

Năm chuyến kẹt ở CONDITIONAL **dù pin đầy 100%**:

| Chuyến | Tuyến | Cự ly | Tải | `E_required` | SoC tối thiểu để CONDITIONAL |
|---|---|---|---|---|---|
| 268 | R6 | 830,7 m | 500 g | 27,61 Wh | 33,3% |
| 269 | R6 | 837,0 m | 500 g | 20,11 Wh | 24,3% |
| 270 | R6 | 837,5 m | 250 g | 24,99 Wh | 30,2% |
| 271 | R6 | 834,6 m | 0 g | 16,95 Wh | 20,5% |
| 272 | R6 | 841,4 m | 250 g | 38,52 Wh | 46,5% |

Đúng **năm chuyến R6 của thí nghiệm E2c** — những chuyến mà D2 đoán thiếu
29,6%, bias −7,613 Wh.

Luật PD-1 chặn chúng không phải vì pin, mà vì **cự ly 835 m nằm ngoài envelope
420–610 m** nơi mô hình còn hiệu lực. Hệ thống không nói "không bay được"; nó
nói "tôi không đủ cơ sở để bảo đảm chuyến này", và yêu cầu người duyệt.

Đây là kết quả mạch lạc nhất của D3: một phát hiện từ D2 được mang thẳng vào
hành vi của hệ thống, kiểm chứng được trên dữ liệu, chứ không chỉ là một dòng
cảnh báo trong tài liệu.

### 6.5 — Độ nhạy theo kịch bản

SoC tối thiểu để FLY (trung vị), `r = 0,20`:

| SoH \ Nhiệt độ | 5 °C | 15 °C | 25 °C |
|---|---|---|---|
| 1,00 | 28,5% | 26,5% | 26,4% |
| 0,90 | 31,7% | 29,5% | 29,3% |
| 0,80 | 35,7% | 33,1% | 33,0% |

Đọc hai chiều:

**SoH quan trọng hơn nhiệt độ.** Pin tụt từ 100% xuống 80% sức khoẻ làm yêu cầu
SoC tăng ~6,6 điểm phần trăm. Nhiệt độ từ 25 °C xuống 5 °C chỉ tăng ~2,1 điểm.

**Nhưng con số nhiệt độ bị chặn bởi thiết kế.** Chênh lệch 15 °C và 25 °C gần
như bằng 0, vì trên 18,4 °C thì κ = 1 — mô hình không mô tả được gì thêm. Và
dưới 4,5 °C thì κ giữ ở 0,9203, nên lạnh hơn nữa cũng không đổi. Bảng này mô tả
**hành vi của mô hình**, không phải vật lý của pin.

Cả bảng là **phân tích độ nhạy**, không phải dự báo. SoH và nhiệt độ là tham số
kịch bản (§4.3), không có trong bộ dữ liệu, và không được trình bày như hiệu ứng
học được từ dữ liệu.

---

## 7. Nghiệm thu theo Mục 12.1

| Tiêu chí | Trạng thái | Bằng chứng |
|---|---|---|
| Mô hình năng lượng khả dụng | Đạt | `src/available_energy.py`, §5.4 Eq (2) |
| Ngân sách năng lượng nhiệm vụ | Đạt | gọi `D2_ridge_preflight` đã chốt, không huấn luyện lại |
| Tính biên dự trữ | Đạt | `M` và `R`, §5.6 |
| Lớp luật cứng | Đạt | 6 luật, có quyền phủ quyết, INV-1 đạt 576/576 |
| Phán quyết ba mức | Đạt | bốn mức — ba của §5.7 cộng INSUFFICIENT-DATA của §4.6 |
| **Cự ly một chiều / khứ hồi rõ ràng** | **Đạt** | quyết định B7; `data_dictionary.md`, `d3_protocol.yaml` mục `distance_convention` |
| **CONDITIONAL đòi biện pháp giảm thiểu** | **Đạt** | quyết định B8; `src/mitigations.py`, INV-7 đạt 213/213 |
| Fail closed | Đạt | INV-2 đạt 960/960 |
| Không gộp điểm số | Đạt | không có trường điểm số nào; có test chặn |
| Không gọi đầu ra là xác suất | Đạt | §5.6, §5.8 — có test chặn |
| Báo cả ba mức hệ số dự trữ | Đạt | mục 6.2, 6.5 |
| Bản ghi tái lập được | Đạt | INV-5 đạt 192/192 |
| Kiểm chéo (Mục 10) | **Chờ Duy** | OI-D3-3 |

**Chốt: 13/13 tiêu chí đạt. Còn chữ ký kiểm chéo của Duy (OI-D3-3).**

Kiểm thử: **358 test**, trong đó 173 test cho riêng D3.

---

## 8. Hạn chế phải nêu trong bài

1. **D3 chưa được chấm điểm.** Bộ dữ liệu không có nhãn kết cục, nên không đo
   được độ chính xác của quyết định. Việc đó thuộc D4, trên kịch bản tổng hợp,
   và kết quả phải gọi là *simulation-derived*, không phải *ground truth*.

2. **SoH và nhiệt độ là giả định**, không có trong dữ liệu. Mọi kết quả liên
   quan là phân tích độ nhạy.

3. **κ(T) chỉ hợp lệ trên 4,5–18,4 °C**, trong khi dải vận hành M100 là
   −10…40 °C. Phần lớn vùng vận hành nằm ngoài dải hợp lệ. Mô hình hiện **không
   mô tả được ảnh hưởng nhiệt độ** trên phần lớn dải đó.

4. **Gió đo được dùng thay gió dự báo.** Ảnh hưởng nhỏ vì chưa bao giờ chạm
   giới hạn, nhưng phải khai báo.

5. **Chuyến bay là vòng kín, tải mang suốt chuyến, không có điểm giao hàng.**
   Bộ dữ liệu là đường bay thử. Cự ly phải đọc theo đúng quy ước (B7), và giao
   hàng thật sẽ nhẹ dần ở chặng về — mô hình không mô tả được điều đó.

6. **Toàn bộ 192 chuyến vượt MTOW nhà sản xuất** (3.680–4.180 g so với 3.600 g).
   Bài Rodrigues không nhắc tới giới hạn này.

7. **`E_nominal = 99,9 Wh` là giá trị chốt tạm.** Bài báo gốc tự mâu thuẫn về
   loại pin; nhóm chọn hướng bảo thủ. Bắt buộc chạy độ nhạy với 129,96 Wh ở D4.

8. **Luật SoC tối thiểu chưa có** (OI-D3-1). §4.6 đòi một giới hạn SoC đặt
   trước điểm hết phóng điện, dựa trên năng lượng hạ cánh từ độ cao hành trình.
   Hiện chưa tính. Không chặn D3 nghiệm thu nhưng phải làm trước D4.

---

## 9. Bàn giao sang D4

Bốn thứ D4 cần, đã có sẵn:

| Cần gì | Ở đâu |
|---|---|
| Hàm quyết định | `src/decision_rules.py` → `assess()` |
| Quét hệ số dự trữ | `src/decision_rules.py` → `sweep_reserve()` |
| Bản ghi nhiệm vụ | `src/workflow_state.py` → `MissionRecord` |
| Dải tham số có dữ liệu đỡ lưng | `reports/parameter_table.md` mục 5 |

Ba điều D4 phải mang theo:

1. **Nhãn tham chiếu phải độc lập với mô hình đang đánh giá.** §4.7 cảnh báo nếu
   dùng chính D2 sinh nhãn rồi lại dùng D2 dự báo thì đánh giá là vòng tròn và
   luôn cho kết quả đẹp. Cách chống thầy chỉ: lấy nhãn từ **phân phối phần dư
   đo được** (`reports/d2_oof_residuals.csv`) cộng một khoản dự phòng bất định.

2. **Hai trong tám chiều kịch bản là ngoại suy thuần** — SoH và nhiệt độ không
   có dữ liệu đỡ lưng. Phải dán nhãn rõ (§6/E3).

3. **Chạy độ nhạy `E_nominal = 129,96 Wh`** — bắt buộc, §8 mục 3.

---

## 10. Việc còn treo

| Mã | Việc | Chặn gì |
|---|---|---|
| OI-D3-1 | Tính SoC tối thiểu để hạ cánh an toàn từ độ cao hành trình | luật cứng còn thiếu một mục; làm trước D4 |
| RS-3 | Lệch tổng cự ly: 92,8 km (192 chuyến) so với ~65 km bài gốc ghi cho 209 chuyến. Nghi nhiễu GPS lúc treo bị cộng dồn. Chưa kết luận | không chặn; ảnh hưởng cách đọc envelope ở B7 |
| OI-D3-3 | Duy xác nhận vai kiểm chéo WP3 và ký nghiệm thu | nghiệm thu D3 theo Mục 12.1 |
| OI-4 | Báo thầy quyết định hai biến thể D2 | không chặn |
| OI-5 | `Draft Báo.docx` còn dùng thông số Matrice 210 | D8 |

---

## Tệp liên quan

| Loại | Đường dẫn |
|---|---|
| Giao thức | `configs/d3_protocol.yaml` |
| Mã nguồn | `src/available_energy.py`, `src/safety_invariants.py`, `src/decision_rules.py`, `src/workflow_state.py`, `src/evaluation_decision.py` |
| Kết quả | `reports/d3_min_soc_per_flight.csv`, `d3_verdict_grid.csv`, `d3_scenario_sensitivity.csv`, `d3_invariant_check.csv` |
| Kiểm thử | `tests/test_available_energy.py`, `test_safety_invariants.py`, `test_decision_rules.py`, `test_workflow_state.py` |
| Giải thích cho nhóm | `docs/san_pham/D3_bo_may_quyet_dinh.md` — **chưa viết** |
