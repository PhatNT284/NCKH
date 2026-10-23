# Sản phẩm D3 — Bộ máy quyết định có ý thức an toàn

**Báo cáo bàn giao theo Mục 12 · nghiệm thu theo Mục 12.1**

| | |
|---|---|
| Gói công việc | WP3 |
| Người làm | Phát |
| Người kiểm chéo | Duy — **đã xác nhận 20/10/2026** |
| Tuần | 7 |
| Giao thức | `configs/d3_protocol.yaml` v1.4.0 |
| Ngày | 20/10/2026 |

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

## 3. Tám quyết định đã chốt

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

Với chuyến trung bình 21,3 Wh thì vạch trên ≈ 26,9%. Vì khoản cộng thêm là một
lượng Wh **tuyệt đối**, vạch trên **khác nhau ở từng chuyến** — chuyến cần ít Wh
thì phần dự phòng bất định chiếm tỷ lệ cao hơn.

**Điều `r` KHÔNG bao gồm:** năng lượng cất cánh và hạ cánh. Hai khoản đó nằm
trong `E_required`, không nằm trong `r` — xem quyết định B9. Nâng `r` để bù cho
hạ cánh là đếm hai lần.

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

### B9 — Quy ước ngân sách năng lượng, chống đếm hai lần

P§4.5 cho công thức ngân sách:

```
E_required = E_outbound + E_return + E_hover          (4)
```

và kèm một ràng buộc nguyên văn: *"subject to an explicit convention that
prevents double counting. Whether the stated route distance is one-way or
round-trip, **whether take-off and landing energy is already contained in the
estimator's output**, whether the return leg carries the payload, and what
cruise speed and altitude are assumed are all recorded in the mission record
and fixed before evaluation."*

Bốn quy ước. Bản trước chỉ khai một (cự ly khứ hồi, B7).

| | Quy ước | Chốt |
|---|---|---|
| 1 | cự ly một chiều hay khứ hồi | **khứ hồi** (B7) |
| 2 | năng lượng cất/hạ cánh đã trong output chưa | **đã có** |
| 3 | chặng về có mang tải không | **có** |
| 4 | giả định tốc độ và độ cao hành trình | tốc độ ra lệnh, độ cao kế hoạch |
| + | số hạng `E_hover` | **= 0** |

**Quy ước (2) là quy ước quan trọng nhất.** Mục tiêu dự báo của D2 là **tổng
năng lượng cả chuyến bay**, không phân đoạn theo pha — §4.2 bước 4 cho phép:
*"If phase segmentation is unreliable, use total flight energy as the primary
target"*. Chuyến bay CMU là vòng kín đầy đủ: cất cánh, leo, hành trình, hạ, đáp
đất.

Nên `E_required` **đã bao gồm** năng lượng cất cánh và hạ cánh. Hệ quả là
**tuyệt đối không được** cộng thêm một khoản hạ cánh, và không được nâng `r` để
"bù cho hạ cánh" — làm vậy là đếm hai lần.

`E_hover = 0` vì bộ dữ liệu không có điểm giao hàng (tải mang suốt chuyến, không
thả). Không phải nhóm bỏ sót số hạng thứ ba của công thức (4); nó bằng 0 vì
nhiệm vụ không có pha treo giao hàng. Nếu sau này áp cho giao hàng thật thì phải
cộng lại, và phải khai lại quy ước (3) vì lúc đó chặng về không mang tải.

**Phát hiện thế nào:** khi rà câu hỏi *"hệ số dự trữ r = 0,20 bù cho những rủi
ro nào?"*. Tra P§4.5 thì thấy câu trả lời không nằm ở `r` mà nằm ở `E_required`,
và thầy có bắt khai báo rõ — mà repo chưa khai.

Chi tiết: `configs/d3_protocol.yaml` mục `energy_required.budget_conventions`.

### B10 — Sàn năng lượng hạ cánh, luật `PH-1`

P§4.6 đòi một sàn cho SoC, nguyên văn: *"A minimum state of charge is added,
**set so that the aircraft retains the energy required to land from its cruise
altitude**, following the principle of placing a safety limit ahead of the end
of discharge rather than at it [10]."*

Bản trước chưa cài. Nhóm từng tưởng đây là việc cần hỏi thầy — tra lại P§4.6
thì thấy thầy **đã chọn sẵn cách làm**, việc của nhóm chỉ là tính và cài đặt.

**Công thức:**

```
E_landing = P_treo(khối lượng cất cánh) × (độ cao ÷ 1,5 m/s) ÷ 3600
PH-1:  E_available(SoC, SoH, T)  ≥  E_landing
```

Tốc độ hạ 1,5 m/s lấy từ Rodrigues et al. (2021), mục Methods. Công suất khi hạ
lấy **bằng** công suất bay treo — cận bảo thủ, vì thiếu hệ số cản cánh quạt để
tính phần cánh quạt thu lại được. Hướng sai lệch là **ước thừa**, tức thận trọng
hơn.

**Năng lượng hạ cánh** (hồ sơ `CMU_instrumented`, bảng đầy đủ ở
`reports/d3_landing_energy.csv`):

| Độ cao | tải 0 g | tải 500 g |
|---|---|---|
| 25 m | 2,46 Wh | 2,98 Wh |
| 50 m | 4,93 Wh | 5,97 Wh |
| 75 m | 7,39 Wh | 8,95 Wh |
| 100 m | 9,86 Wh | **11,93 Wh** |

**Mức độ: VETO.** Không đủ pin để đáp xuống đất là một thực tế vật lý, không
phải giới hạn hiệu lực của mô hình — nên nó chặn tuyệt đối như `HR-1…HR-4`, và
biện pháp giảm thiểu không lật được (có test khoá).

**Nhưng mã luật là `PH-1`, không phải `HR-5`.** Tiền tố `HR-` trong repo dành
riêng cho luật mà **con số do DJI công bố**. `PH-1` có *nguyên tắc* từ P§4.6 của
thầy nhưng *con số* từ mô hình vật lý của nhóm, với η khớp từ **một điểm** (thời
lượng bay treo không tải DJI công bố). Hai nguồn khác nhau nên phải mang mã
khác nhau.

Repo giờ có **ba họ mã**, trong đó nguồn gốc và mức độ là hai trục độc lập:

| Mã | Nguồn | Mức độ |
|---|---|---|
| `HR-1…HR-4` | DJI công bố | VETO |
| `PH-1` | nguyên tắc P§4.6 + số của nhóm | **VETO** |
| `PD-1, PD-2` | thí nghiệm của nhóm | DOWNGRADE |

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
| **PH-1** | **`E_available` ≥ năng lượng hạ cánh** | **P§4.6 + `src/physics_m100.py`** | **NO-FLY** |
| PD-1 | cự ly 420–610 m | thí nghiệm E2c của nhóm | không được FLY |
| PD-2 | tải 0–500 g | độ phủ dữ liệu | không được FLY |

Hai mức độ khác nhau có chủ đích. `HR-*` và `PH-1` là giới hạn vật lý → chặn
tuyệt đối. `PD-*` là **giới hạn hiệu lực của mô hình** → máy bay vẫn bay được,
nhưng con số dự báo không đáng tin ở đó, nên hệ thống phải nói rõ thay vì im
lặng. §6/E3 yêu cầu *"clearly label any extrapolated ranges"*.

**Khi trích dẫn phải tách ba nguồn**, không được trộn:

| Mã | Trích gì |
|---|---|
| `HR-1…HR-4` | thông số DJI công bố |
| `PH-1` | nguyên tắc P§4.6 của thầy + mô hình vật lý của **nhóm** (η khớp từ một điểm) |
| `PD-1, PD-2` | thí nghiệm E2c và độ phủ dữ liệu của **nhóm** |

Có test canh quy ước này: `test_moi_luat_hr_co_ghi_nguon` bắt buộc mọi luật
`HR-*` phải có `"DJI"` trong trường nguồn. Test đó đã bắt được một lỗi thật —
luật này ban đầu được đặt tên `HR-5`.

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

### Quy ước ngân sách năng lượng đang áp dụng

Theo quyết định B9 và `d3_protocol.yaml` mục `budget_conventions`:

| Quy ước | Giá trị |
|---|---|
| Cự ly | khứ hồi (vòng kín) |
| Năng lượng cất cánh và hạ cánh | **đã nằm trong** `E_required` |
| Chặng về mang tải | có |
| Tốc độ / độ cao hành trình | tốc độ ra lệnh / độ cao kế hoạch |
| `E_hover` | 0 Wh — không có điểm giao hàng |

Lưu ý quan hệ với `PH-1`: năng lượng hạ cánh **bình thường** ở cuối chuyến đã
nằm trong `E_required`. `PH-1` là **sàn riêng** cho tình huống phải huỷ chuyến
giữa đường và đáp gấp. Hai thứ khác nhau — cộng gộp là đếm hai lần.

### Cách chạy lại

```bash
python3 -m src.evaluation_decision        # khoảng 25 giây
```

Sinh bốn file vào `reports/`:
`d3_min_soc_per_flight.csv` · `d3_verdict_grid.csv` ·
`d3_scenario_sensitivity.csv` · `d3_invariant_check.csv`

---

## 6. Kết quả

### 6.1 — Tám bất biến, trên dữ liệu thật

| Bất biến | Nội dung | Số trường hợp | Vi phạm |
|---|---|---|---|
| INV-1 | luật cứng phủ quyết | 576 | **0** |
| INV-2 | fail closed | 960 | **0** |
| INV-3 | đơn điệu theo năng lượng | 192 | **0** |
| INV-4 | tất định | 192 | **0** |
| INV-5 | tính lại từ bản ghi | 192 | **0** |
| INV-6 | không chứa mô hình học máy | 1 | **0** |
| INV-7 | biện pháp giảm thiểu có tác dụng | 213 | **0** |
| **INV-8** | **không đủ pin hạ cánh thì không bao giờ FLY** | **768** | **0** |

**3.094 trường hợp, không vi phạm nào.**

Khác với test đơn vị: test đơn vị kiểm vài chục trường hợp do người chọn; bảng
này lấy cấu hình từ 192 chuyến bay có thật.

INV-3 đáng chú ý nhất — nó quét SoC theo 50 bước cho từng chuyến và bắt buộc
phán quyết **không bao giờ xấu đi khi pin nhiều hơn**. Đó cũng là điều kiện tiên
quyết để thuật toán tìm SoC tối thiểu bằng chia đôi ở mục 6.2 có nghĩa.

INV-8 kiểm **hai chiều**: SoC dưới ngưỡng hạ cánh thì phải NO-FLY, *và* áp biện
pháp giảm thiểu thì **vẫn** NO-FLY. Chiều thứ hai quan trọng không kém — không
có nó thì "sạc thêm pin" thành cửa sau để lách `PH-1`.

**Danh sách bất biến đọc từ giao thức, không viết cứng trong code.**
`run_invariants()` lấy `invariants.tests` từ `d3_protocol.yaml` rồi tra hàm kiểm
tương ứng, và **ném lỗi** nếu giao thức khai một bất biến mà không có hàm kiểm.
Trước đó danh sách viết cứng, nên khi thêm INV-7 rồi INV-8 thì giao thức nói một
đằng và bảng bằng chứng nói một nẻo — lỗi im lặng, và đã xảy ra hai lần.

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

### 6.2b — Luật `PH-1` có ràng buộc hơn luật dự trữ không?

Câu hỏi này phải trả lời bằng số, vì nó quyết định `PH-1` có ý nghĩa gì trên bộ
dữ liệu này.

| Ngưỡng SoC đòi hỏi | Nhỏ nhất | Trung vị | Lớn nhất |
|---|---|---|---|
| Luật `PH-1` (sàn hạ cánh) | 2,5% | 6,0% | **12,0%** |
| Luật dự trữ (`r = 0,20`) | **16,2%** | 26,5% | 42,0% |

**Hai dải không chồng nhau: 12,0 < 16,2.** Số chuyến mà `PH-1` ràng buộc hơn
luật dự trữ: **0 trên 192**.

Nên trên bộ dữ liệu này `PH-1` **không đổi phán quyết nào** — bảng mục 6.3 và
6.4 giữ nguyên so với bản trước khi cài.

**Nhưng `PH-1` không phải code chết.** Ở mức pin 10%, nó chặn **30 trên 192**
chuyến (cột `ph1_violated` trong `d3_verdict_grid.csv`). Phán quyết vẫn là
NO-FLY, nhưng **lý do đổi**: không đủ pin để đáp xuống đất, chứ không phải thiếu
biên dự trữ. Người điều phối đọc hai lý do đó sẽ làm hai việc khác nhau.

**Và `PH-1` cần thiết cho sản phẩm D4.** Luật dự trữ tỷ lệ với `E_required`, còn
`PH-1` là một lượng Wh **tuyệt đối**. Nên `PH-1` chỉ ràng buộc hơn khi
`E_required` nhỏ mà độ cao cao:

```
Chuyến cần 8 Wh, cao 100 m, tải 500 g:
  luật dự trữ  →  cần 10,2 Wh  →  SoC 10,2%
  PH-1         →  cần 11,9 Wh  →  SoC 11,9%   ← PH-1 thắng
```

Bộ dữ liệu CMU không có loại nhiệm vụ đó (cự ly gần như cố định ~472 m), nhưng
bộ sinh kịch bản ở D4 quét **độc lập** cự ly và độ cao nên sẽ sinh ra. Thiếu
`PH-1` thì những kịch bản đó cho FLY sai.

> **Cảnh báo khi đọc bảng ngưỡng `PH-1`:** hàm `min_soc_for_landing()` mặc định
> `κ = 1`, tức cho **ngưỡng lạc quan**. Bảng trên đã dùng κ thật tại 15 °C
> (0,9954). Ở 0 °C thì κ = 0,9203 và ngưỡng thật cao hơn mặc định **8,66%**.
> Bảng `reports/d3_landing_energy.csv` dùng mặc định, nên phải đọc là *"ngưỡng
> tối thiểu ở điều kiện tốt nhất"*, không phải ngưỡng vận hành.

### 6.3 — Phân bố phán quyết theo mức pin

Tại `r = 0,20`, SoH = 1,0, 15 °C:

| SoC | FLY | CONDITIONAL | NO-FLY | `PH-1` chặn |
|---|---|---|---|---|
| 0,10 | 0 | 0 | 192 | **30** |
| 0,15 | 0 | 3 | 189 | 0 |
| 0,20 | 19 | 15 | 158 | 0 |
| 0,25 | 73 | 22 | 97 | 0 |
| 0,30 | 134 | 16 | 42 | 0 |
| 0,35 | 167 | 13 | 12 | 0 |
| 0,40 | 184 | 6 | 2 | 0 |
| 0,45 | 187 | 4 | 1 | 0 |
| 0,50 | **187** | **5** | 0 | 0 |
| 1,00 | **187** | **5** | 0 | 0 |

Từ SoC 0,50 trở lên bảng **đứng yên**: 187 FLY, 5 CONDITIONAL, mãi mãi.

Cột cuối là số chuyến bị `PH-1` chặn. Nó chỉ khác 0 ở mức pin 10% — nơi luật dự
trữ cũng đã chặn cả 192 chuyến. Xem mục 6.2b.

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
| Ngân sách năng lượng nhiệm vụ | Đạt | gọi `D2_ridge_preflight` đã chốt, không huấn luyện lại; quy ước ngân sách khai ở B9 |
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
| Kiểm chéo (Mục 10) | **Đạt** | Duy xác nhận 20/10/2026 |

**Chốt: 13/13 tiêu chí đạt. Sản phẩm D3 NGHIỆM THU.**

Ngoài 13 tiêu chí, hệ thống còn cài thêm **luật `PH-1`** theo P§4.6 (quyết định
B10) và **bốn quy ước ngân sách năng lượng** theo P§4.5 (quyết định B9). Cả hai
là bổ sung theo thiết kế đã cam kết trong Proposal, không phải vá một tiêu chí
thiếu — Mục 12.1 không có tiêu chí nào đòi chúng.

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
   hàng thật sẽ nhẹ dần ở chặng về — mô hình không mô tả được điều đó. Số hạng
   `E_hover` của công thức (4) bằng 0 vì không có pha treo giao hàng; áp cho
   nhiệm vụ thật thì phải cộng lại (B9).

6. **Toàn bộ 192 chuyến vượt MTOW nhà sản xuất** (3.680–4.180 g so với 3.600 g).
   Bài Rodrigues không nhắc tới giới hạn này.

7. **`E_nominal = 99,9 Wh` là giá trị chốt tạm.** Bài báo gốc tự mâu thuẫn về
   loại pin; nhóm chọn hướng bảo thủ. Bắt buộc chạy độ nhạy với 129,96 Wh ở D4.

8. **Sàn năng lượng hạ cánh (`PH-1`) dựa trên mô hình vật lý của nhóm, không
   phải số nhà sản xuất.** Nguyên tắc lấy từ P§4.6, nhưng con số tính từ
   `src/physics_m100.py` với hệ số hiệu suất η khớp từ **một điểm** duy nhất
   (thời lượng bay treo không tải DJI công bố).

   Hai giả định phải nêu: (a) công suất khi hạ cánh lấy **bằng** công suất bay
   treo — cận bảo thủ, vì thiếu hệ số cản cánh quạt; (b) η khớp trên dải khối
   lượng 2.431–3.431 g nhưng máy bay thực tế nặng 3.680–4.180 g, nên **là ngoại
   suy**.

   Cả hai lệch về phía **ước thừa** năng lượng hạ cánh, tức thận trọng hơn. Nhưng
   phải khai báo, và không được trích `PH-1` như giới hạn nhà sản xuất.

9. **`PH-1` chưa được thử thách trên bộ dữ liệu này.** Ngưỡng `PH-1` (2,5–12,0%)
   nằm hoàn toàn dưới ngưỡng luật dự trữ (16,2–42,0%), nên nó không đổi phán
   quyết nào trong 192 chuyến. Nó chỉ chặn 30 chuyến ở mức pin 10%, nơi luật dự
   trữ cũng đã chặn.

   Nghĩa là tác dụng thật của `PH-1` sẽ chỉ thấy ở sản phẩm D4, trên kịch bản
   "chuyến ngắn bay cao" mà bộ dữ liệu CMU không có. Không được trình bày `PH-1`
   như một luật đã được kiểm chứng trên dữ liệu thật.

---

## 9. Bàn giao sang D4

Bốn thứ D4 cần, đã có sẵn:

| Cần gì | Ở đâu |
|---|---|
| Hàm quyết định | `src/decision_rules.py` → `assess()` |
| Quét hệ số dự trữ | `src/decision_rules.py` → `sweep_reserve()` |
| Bản ghi nhiệm vụ | `src/workflow_state.py` → `MissionRecord` |
| Dải tham số có dữ liệu đỡ lưng | `reports/parameter_table.md` mục 5 |

Bốn điều D4 phải mang theo:

1. **Nhãn tham chiếu phải độc lập với mô hình đang đánh giá.** §4.7 cảnh báo nếu
   dùng chính D2 sinh nhãn rồi lại dùng D2 dự báo thì đánh giá là vòng tròn và
   luôn cho kết quả đẹp. Cách chống thầy chỉ: lấy nhãn từ **phân phối phần dư
   đo được** (`reports/d2_oof_residuals.csv`) cộng một khoản dự phòng bất định.

2. **Hai trong tám chiều kịch bản là ngoại suy thuần** — SoH và nhiệt độ không
   có dữ liệu đỡ lưng. Phải dán nhãn rõ (§6/E3).

3. **Chạy độ nhạy `E_nominal = 129,96 Wh`** — bắt buộc, §8 mục 3.

4. **Giữ nguyên quy ước ngân sách năng lượng của B9.** Bộ sinh kịch bản không
   được cộng thêm năng lượng hạ cánh vào `E_required`, và phải khai rõ đang lấy
   mẫu cự ly theo cách đọc nào (tổng quãng bay hay một chiều).

5. **Quét độc lập cự ly và độ cao, và báo riêng số kịch bản mà `PH-1` ràng buộc
   hơn luật dự trữ.** Đó là vùng duy nhất `PH-1` có tác dụng, và bộ dữ liệu CMU
   không có nó. Nếu D4 cũng cho 0 kịch bản như vậy thì bộ sinh chưa quét đủ
   rộng.

---

## 10. Việc còn treo

| Mã | Việc | Chặn gì |
|---|---|---|
| ~~OI-D3-1~~ | ~~Sàn an toàn khi có sự cố~~ | **ĐÓNG 20/10** — cài thành luật `PH-1`, quyết định B10 |
| ~~OI-D3-3~~ | ~~Duy ký kiểm chéo WP3~~ | **ĐÓNG 20/10** |
| RS-3 | Lệch tổng cự ly: 92,8 km (192 chuyến) so với ~65 km bài gốc ghi cho 209 chuyến. Nghi nhiễu GPS lúc treo bị cộng dồn. Chưa kết luận | không chặn; ảnh hưởng cách đọc envelope ở B7 |
| OI-4 | Báo thầy quyết định hai biến thể D2 | không chặn |
| OI-5 | `Draft Báo.docx` còn dùng thông số Matrice 210 | D8 |

---

## 11. Ba lỗi do chính bộ test bắt được

Giữ lại mục này vì nó là bằng chứng cho một tính chất của hệ thống kiểm chứng:
test ở đây không chỉ kiểm con số, mà kiểm **quy ước** và **ràng buộc kiến trúc**.
Ba lỗi dưới đây đều phát sinh khi cài `PH-1`, và đều bị bắt trước khi vào bài.

### (a) Mã luật phá quy ước nguồn gốc

Luật mới ban đầu được đặt tên `HR-5`. Test `test_moi_luat_hr_co_ghi_nguon` bắt
buộc mọi luật `HR-*` phải có `"DJI"` trong trường nguồn, và nó đỏ.

Quy ước đó đáng giữ: thầy sẽ hỏi *"con số này ở đâu ra"*, và một luật tên `HR-5`
nằm cạnh bốn luật DJI mời gọi câu trả lời sai. Đã đổi thành `PH-1` và tách thành
mục riêng `physics_derived` trong giao thức.

### (b) Chữ ký hàm phá ràng buộc §4.6

Bản đầu truyền `e_available_Wh` vào `check_hard_rules()`. Test
`test_lop_nay_khong_nhan_dau_ra_mo_hinh` quét chữ ký hàm và cấm mọi tham số có
tên liên quan năng lượng — nó đỏ.

Lập luận *"`E_available` là công thức §5.4, không phải đầu ra mô hình"* là đúng,
nhưng cách làm không cần thiết. Đã đổi: lớp luật cứng nhận `soc`/`soh` (**đầu
vào thô**) rồi tự gọi `available_energy()`. Chữ ký sạch, §4.6 được tôn trọng
nguyên vẹn, và test tiếp tục canh.

### (c) Ngưỡng hạ cánh mặc định là ngưỡng lạc quan

`min_soc_for_landing()` mặc định `κ = 1`. Test
`test_dung_ngay_tai_nguong_thi_pass` đỏ, vì ở 15 °C thì κ = 0,9954 nên ngưỡng
thật cao hơn.

Đây là lỗi trong test, **nhưng nó phơi ra một cái bẫy thật**: ở 0 °C thì
κ = 0,9203 và ngưỡng thật cao hơn mặc định **8,66%**. Ai dùng hàm đó để quyết
định mà quên truyền κ sẽ **ước thiếu** lượng pin cần. Đã thêm
`test_nguong_mac_dinh_la_nguong_LAC_QUAN` khoá tính chất này, và `run_min_soc()`
giờ truyền κ thật.

### Và một lỗi im lặng lặp lại ba lần

Danh sách bất biến từng được viết cứng ở bốn chỗ. Mỗi lần thêm bất biến là một
lần phải sửa bốn chỗ — và đã sai **ba lần** (thêm INV-7, thêm INV-8, rồi
`test_evaluation_decision.py`). Lỗi này **im lặng**: giao thức khai 8 bất biến,
bảng bằng chứng chỉ in 7, không ai báo gì.

Đã sửa bằng cách bỏ con số viết cứng: `run_invariants()` đọc danh sách từ giao
thức và **ném lỗi** nếu thiếu hàm kiểm; test so bảng kết quả trực tiếp với giao
thức. Không có lần thứ tư.

---

## Tệp liên quan

| Loại | Đường dẫn |
|---|---|
| Giao thức | `configs/d3_protocol.yaml` |
| Mã nguồn | `src/available_energy.py`, `src/safety_invariants.py`, `src/decision_rules.py`, `src/workflow_state.py`, `src/mitigations.py`, `src/physics_m100.py`, `src/evaluation_decision.py` |
| Kết quả | `reports/d3_min_soc_per_flight.csv`, `d3_verdict_grid.csv`, `d3_scenario_sensitivity.csv`, `d3_invariant_check.csv`, `d3_landing_energy.csv` |
| Kiểm thử | `tests/test_available_energy.py`, `test_safety_invariants.py`, `test_decision_rules.py`, `test_workflow_state.py`, `test_mitigations.py`, `test_evaluation_decision.py` |
| Giải thích cho nhóm | `docs/san_pham/D3_bo_may_quyet_dinh.md` |