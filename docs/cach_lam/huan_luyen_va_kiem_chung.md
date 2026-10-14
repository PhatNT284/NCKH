# Huấn luyện mô hình và kiểm chứng — giải thích từ đầu

File này trả lời bốn câu mà thầy hoặc thành viên trong nhóm chắc chắn sẽ hỏi:

1. Huấn luyện là gì, và cụ thể nhóm đã huấn luyện như thế nào
2. Huấn luyện xong thì mô hình cho ra cái gì
3. Làm sao biết kết quả đó đúng
4. Muốn tự kiểm lại thì làm thế nào

Viết cho người chưa học máy học. Không cần đọc file nào trước.

> Phạm vi: đây là tài liệu giải thích cho người trong nhóm, **không phải sản phẩm
> bàn giao**. Sản phẩm thật nằm ở `reports/` — xem `../../reports/deliverables.md`.

---

## 1. Huấn luyện là gì

Bỏ chữ "AI" sang một bên một lát. Vấn đề thực ra rất cụ thể:

> Có 192 chuyến bay đã bay rồi. Mỗi chuyến biết: mang bao nhiêu gam hàng, bay
> nhanh bao nhiêu, cao bao nhiêu, xa bao nhiêu, gió thế nào — và tốn bao nhiêu Wh.
> Giờ có một chuyến **chưa bay**, chỉ biết năm thứ đầu. Đoán xem nó tốn bao nhiêu.

**Huấn luyện** là quá trình để máy tính tự tìm ra quy luật nối năm thứ đầu với
con số cuối. Không ai viết sẵn công thức cho nó. Nó dò trong 192 ví dụ.

### Một ví dụ bằng tay

Giả sử chỉ có một yếu tố là tải trọng, và ta tin quan hệ là đường thẳng:

```
năng_lượng = a × tải_trọng + b
```

`a` và `b` chưa biết. Máy tính thử các cặp `(a, b)` và chọn cặp làm **tổng sai
số trên 192 chuyến nhỏ nhất**. Đó là toàn bộ việc huấn luyện. Kết quả là hai con
số, gọi là **tham số** của mô hình.

Thực tế có 6 yếu tố chứ không phải 1, nên có 7 tham số thay vì 2. Nguyên lý
giống hệt.

### Vì sao gọi là "máy học"

Vì ta không nói cho nó biết tải trọng nặng thì tốn điện hơn. Nó tự rút ra điều
đó từ dữ liệu. Nếu đưa dữ liệu khác, nó sẽ rút ra quy luật khác.

Nói với thầy thì nên dùng chữ **"học máy"** (machine learning), không nói "AI" —
chữ AI hiện gắn với mô hình ngôn ngữ và dễ gây hiểu nhầm. Đây là hồi quy thống
kê và học máy cổ điển.

---

## 2. Hai mô hình đã huấn luyện

### Ridge regression (mô hình D2 của §5.2)

Là đường thẳng nhiều chiều như ví dụ trên, cộng thêm một luật phụ:
**phạt các hệ số quá lớn**.

Vì sao cần luật phạt đó: với 192 dòng dữ liệu, hồi quy thường rất dễ vớ phải
một tổ hợp hệ số to đùng, ngược dấu nhau, triệt tiêu lẫn nhau — khớp dữ liệu cũ
hoàn hảo nhưng vô nghĩa và sai bét khi gặp dữ liệu mới. Luật phạt kéo các hệ số
về gần 0, buộc mô hình chọn lời giải đơn giản nhất còn giải thích được dữ liệu.

Mức phạt là một con số, gọi là **alpha**. Phạt quá nhẹ thì không có tác dụng,
quá nặng thì mô hình thành một đường gần như phẳng. Cách chọn alpha nằm ở mục 3.

§5.2 nói rõ ưu tiên Ridge hơn đa thức bậc cao *vì dữ liệu nhỏ*.

### Random Forest (mô hình D3 của §5.2)

Hoàn toàn khác. Không có công thức nào cả. Nó xây **300 cây quyết định**, mỗi
cây là một chuỗi câu hỏi kiểu:

```
Tải > 250 g?
├── có  → Độ cao > 75 m?
│         ├── có  → đoán 26,1 Wh
│         └── không → đoán 22,4 Wh
└── không → Tốc độ > 8 m/s?
            ├── ...
```

Mỗi cây được xây từ một phần dữ liệu lấy ngẫu nhiên và một phần yếu tố lấy ngẫu
nhiên, nên 300 cây khác nhau. Dự báo cuối là **trung bình của 300 cây**.

Điểm mạnh: bắt được quan hệ phi tuyến và tương tác, thứ đường thẳng không làm
được. Điểm yếu: nó chỉ biết **nội suy trong vùng đã thấy** — ra ngoài vùng đó
nó trả về giá trị của lá gần nhất, tức là đứng yên.

### Vì sao chạy cả hai

Vì §5.2 bắt so sánh, và vì **không ai biết trước cái nào hợp dữ liệu này**. Chạy
cả hai rồi để số liệu quyết định là cách làm khoa học; chọn sẵn một cái rồi đi
tìm lý do biện minh thì không.

---

## 3. Huấn luyện cụ thể như thế nào

Đây là phần nên nắm chắc nhất, vì thầy sẽ hỏi vào đây.

### Bước 1 — Chuẩn bị đầu vào

Mỗi chuyến bay thành **một dòng**, 6 cột đầu vào và 1 cột đáp án:

| Vai trò | Cột |
|---|---|
| Đầu vào | `payload_num`, `speed_num`, `altitude_num`, `distance_2d_m`, `wind_raw_mean_ms`, `duration_planned_s` |
| Đáp án | `energy_Wh` |

Cả 6 cột đầu vào đều là thứ **biết được trước khi cất cánh**. Đây là ràng buộc
cứng, không phải lựa chọn thẩm mỹ: hệ thống này chạy *trước* chuyến bay, nên bất
cứ thứ gì chỉ biết sau khi hạ cánh đều vô dụng, và tệ hơn là làm kết quả đẹp giả
tạo.

Mã nguồn chặn điều đó bằng một hàng rào chạy trước mỗi lần huấn luyện:

```python
def assert_no_leakage(cols, protocol):
    forbidden = {e["column"] for e in protocol["features"]["forbidden"]}
    leaked = forbidden & set(cols)
    if leaked:
        raise ValueError(f"RO RI: bien hau nghiem trong tap dac trung: {leaked}")
```

9 cột nằm trong danh sách cấm, ví dụ `speed_realised_ms` (tốc độ thực tế = cự ly
÷ thời lượng đo được — biết nó tức là đã bay xong) và `energy_per_metre_J` (tính
thẳng từ chính cột đáp án). Nếu ai đó lỡ tay đưa vào, chương trình **dừng ngay**,
không chạy ra kết quả sai.

### Bước 2 — Chuẩn hoá

Tải tính bằng gam (0–500), cự ly bằng mét (~472), gió bằng m/s (~2,8). Ba thang
đo chênh nhau hàng trăm lần. Ridge phạt theo độ lớn hệ số, nên nếu không xử lý,
cột nào có đơn vị nhỏ sẽ bị phạt oan.

Cách xử lý: đổi mọi cột về cùng thang — trừ trung bình, chia độ lệch chuẩn.

**Chi tiết quan trọng nhất ở đây:** trung bình và độ lệch chuẩn chỉ được tính từ
**phần dữ liệu dùng để huấn luyện**, không được tính từ toàn bộ. Nếu tính từ
toàn bộ thì thông tin của phần dữ liệu kiểm đã rò sang phần huấn luyện, và điểm
số sẽ đẹp hơn thực tế.

Trong code, việc này được đảm bảo bằng `Pipeline` của scikit-learn — nó buộc
bước chuẩn hoá đi liền với mô hình và chỉ "học" thống kê từ dữ liệu huấn luyện:

```python
Pipeline([("scaler", StandardScaler()), ("model", Ridge(alpha=alpha))])
```

Random Forest không cần chuẩn hoá (nó chỉ so sánh lớn/nhỏ), nên pipeline của D3
không có bước này.

### Bước 3 — Chọn siêu tham số bằng CV lồng

Ridge cần biết alpha. Random Forest cần biết độ sâu tối đa và số mẫu tối thiểu
mỗi lá. Những con số này **không học được từ dữ liệu** như hệ số — phải thử.

Sai lầm kinh điển: thử nhiều giá trị, chọn giá trị cho điểm tốt nhất **trên tập
kiểm**. Làm vậy là đã dùng tập kiểm để ra quyết định, nên nó không còn là tập
kiểm nữa, và điểm báo cáo sẽ lạc quan hơn thực tế. §5.3 cấm việc này.

Cách làm đúng — **cross-validation lồng**: chia tập huấn luyện ra làm 3 phần nữa,
thử các giá trị *bên trong* đó, chọn giá trị tốt nhất, rồi mới huấn luyện lại
trên toàn bộ tập huấn luyện. Tập kiểm không hề bị đụng tới.

```python
search = GridSearchCV(
    model, spec["param_grid"],
    cv=KFold(n_splits=3, shuffle=True, random_state=seed),
    scoring="neg_mean_absolute_error", n_jobs=-1,
)
```

Lưới đã thử:

| Mô hình | Thử những giá trị nào |
|---|---|
| Ridge | alpha ∈ {0,01 · 0,1 · 1 · 10 · 100} |
| Random Forest | độ sâu ∈ {3, 5, 8} × số mẫu tối thiểu mỗi lá ∈ {2, 4, 8} |

### Bước 4 — Cross-validation ngoài

Giờ mới đến phần chấm điểm thật.

Không thể huấn luyện trên cả 192 chuyến rồi kiểm trên chính 192 chuyến đó — như
đưa đề thi đúng bằng đề ôn, điểm cao không nói lên gì.

Cách làm: chia 192 chuyến thành **5 phần**. Huấn luyện trên 4 phần, dự báo phần
còn lại. Xoay vòng 5 lượt để mỗi chuyến đều có lúc nằm ở phần bị dự báo. Sau 5
lượt, mọi chuyến đều có một dự báo **được tạo ra bởi mô hình chưa từng thấy nó**.

Chưa đủ. Một cách chia có thể may hoặc xui. Nên lặp lại toàn bộ **5 lần với 5
cách chia khác nhau** → tổng **25 lần huấn luyện cho mỗi mô hình**. Báo cả trung
bình lẫn độ lệch chuẩn.

```python
cv = RepeatedKFold(n_splits=5, n_repeats=5, random_state=42)
```

Đơn vị chia là **chuyến bay**, không phải dòng telemetry. Mỗi chuyến có hàng
nghìn dòng; nếu cắt theo dòng thì cùng một chuyến nằm cả hai phía, mô hình chỉ
cần nhớ chứ không cần học. §5.3 nói thẳng điều này.

`random_state=42` là hạt giống ngẫu nhiên — cố định nó thì ai chạy cũng ra đúng
cách chia đó, đúng kết quả đó.

### Toàn bộ quy trình trong một hình

```
192 chuyến bay
   │
   ├─ chia 5 phần (lặp 5 lần, seed 42)
   │
   └─ mỗi lượt:
        4 phần huấn luyện ──┬─ chuẩn hoá (chỉ dùng thống kê 4 phần này)
                            ├─ CV lồng 3 phần → chọn alpha / độ sâu
                            └─ huấn luyện lại trên cả 4 phần
                                      │
        1 phần kiểm   ──────────────► dự báo ──► so với đáp án ──► sai số
```

Thời gian chạy toàn bộ: 10–15 phút.

---

## 4. Huấn luyện xong thì được cái gì

Hai thứ, đừng lẫn lộn.

### (a) Một mô hình đã học xong — dùng để dự báo

Đưa vào 6 con số, trả ra 1 con số:

```
tải 250 g · tốc độ 8 m/s · độ cao 50 m · cự ly 472 m
   · gió 2,8 m/s · thời lượng kế hoạch 59 s
        ↓
     22,4 Wh
```

Chỉ vậy. **Một con số, không kèm xác suất, không kèm độ tin cậy.** §5.6 và §5.8
cấm gọi bất cứ đầu ra nào của D2 là "xác suất" hay "độ tin cậy".

Đây chính là khối tính `E_required` trong sản phẩm D3.

### (b) Các tham số đã học — dùng để diễn giải

Với Ridge, tham số là 6 hệ số, đọc được bằng mắt (`reports/d2_ridge_coefficients.csv`):

| Đặc trưng | Hệ số (đã chuẩn hoá) | Hệ số (đơn vị gốc) |
|---|---|---|
| `duration_planned_s` | 4,122 | 0,136 |
| `altitude_num` | 3,052 | 0,108 |
| `payload_num` | 1,677 | 0,0081 |
| `speed_num` | 0,668 | 0,235 |
| `wind_raw_mean_ms` | 0,119 | 0,143 |
| `distance_2d_m` | −0,077 | −0,0013 |

Cột đã chuẩn hoá cho biết **yếu tố nào quan trọng hơn** (so sánh được với nhau vì
cùng thang). Cột đơn vị gốc cho biết **thêm một đơn vị thì tốn thêm bao nhiêu Wh**
— ví dụ cao thêm 1 m thì tốn thêm 0,108 Wh.

Hai điều phải nói kèm, nếu không sẽ bị hỏi vặn:

1. Hệ số của cự ly **âm**, nghe vô lý. Thực ra không phải — 180/192 chuyến cùng
   một tuyến, cự ly gần như không đổi, nên hệ số này chỉ là nhiễu. Không được
   diễn giải nó.
2. Đây là **quan hệ thống kê, không phải nhân quả**. §5.2 nói rõ với feature
   importance. Nguyên tắc đó áp dụng cho cả hệ số hồi quy.

Với Random Forest thì không có hệ số — 300 cây không đọc bằng mắt được. Chỉ có
"độ quan trọng đặc trưng", là thước đo mô tả, càng không phải nhân quả.

---

## 5. Làm sao biết kết quả đó đúng

Đây là câu quan trọng nhất, và câu trả lời **không phải một con số** mà là một
chuỗi phép kiểm độc lập.

### Lớp 1 — Có hơn đoán bừa không

Mô hình D0 luôn trả về 21,3 Wh bất kể đầu vào. Nó tồn tại để làm **sàn**.

| | MAE (Wh) |
|---|---|
| D0 đoán bừa | 3,975 |
| **Ridge** | **0,657** |

Hơn 6 lần. Nếu không hơn thì mô hình vô dụng, dù điểm số trông thế nào.

### Lớp 2 — Có ổn định không

25 lần chạy, độ lệch chuẩn của MAE = **0,075**. So với MAE 0,657 thì dao động
khoảng 11%. Tức là kết quả không phụ thuộc vào may rủi khi chia dữ liệu.

### Lớp 3 — Chênh lệch với Random Forest có thật không

Ridge 0,657 và RF 1,014. Chênh 0,357 Wh. Có đáng kể không, hay chỉ là nhiễu?

Cách trả lời: **bootstrap**. Bốc ngẫu nhiên có hoàn lại 192 chuyến, tính lại MAE,
lặp 2.000 lần. Bốc theo **cặp** — cùng bộ chỉ số cho cả hai mô hình — vì bốc
riêng sẽ làm mất tương quan và cho khoảng rộng hơn thực tế.

| | MAE | Khoảng tin cậy 95% |
|---|---|---|
| Ridge | 0,655 | [0,582 ; 0,729] |
| Random Forest | 0,967 | [0,822 ; 1,141] |

**Hai khoảng không chồng lấn.** Chênh lệch là thật.

§5.3 cấm: *"không được mô tả một chênh lệch nhỏ là có ý nghĩa chỉ vì một lần chia
cho kết quả thấp hơn"*. Đây là cách tuân thủ điều đó.

### Lớp 4 — Gặp cấu hình chưa từng thấy thì sao

Lớp 1–3 vẫn là chia ngẫu nhiên, nên tập kiểm luôn có những chuyến gần giống
chuyến trong tập huấn luyện. Thực tế vận hành không như vậy.

Thí nghiệm E2b: bỏ **nguyên một tổ hợp** (tải × tốc độ × độ cao) ra khỏi tập
huấn luyện, rồi dự báo nó. Lặp qua cả 60 tổ hợp.

| | Trên dữ liệu quen | Cấu hình mới | Tụt |
|---|---|---|---|
| Ridge | 0,657 | 0,67 | **2%** |
| Random Forest | 1,014 | 1,39 | **37%** |

Đây là chỗ phân thắng bại. Random Forest học thuộc vùng dữ liệu; ra khỏi vùng đó
nó sụp. Ridge giữ được vì nó học một quan hệ trơn, ngoại suy được.

### Lớp 5 — Có vùng nào nguy hiểm không

Bốn lớp trên đều là **một con số cho cả bộ dữ liệu**. Một con số có thể che giấu
rất nhiều thứ: sai ít ở hầu hết điều kiện nhưng sai nặng ở một vài điều kiện —
mà đúng những điều kiện đó mới là lúc giao hàng thật.

Nên chia sai số theo nhóm: tải, tốc độ, độ cao, gió, cự ly — 18 nhóm, xem **bias
có dấu** của từng nhóm (`reports/d2_subgroup_errors.csv`).

Phát hiện: Random Forest **đoán thiếu** ở tải 500 g (−0,654), độ cao 100 m
(−0,710), cự ly >700 m (−3,111). Ridge không có nhóm nào như vậy.

Vì sao đây là lớp quan trọng nhất về an toàn: **đoán thừa và đoán thiếu không
ngang nhau**. Đoán thừa → chuyến bay bị từ chối oan, phiền. Đoán thiếu → UAV cất
cánh với năng lượng không đủ, rơi. Nên `bias` có dấu quan trọng hơn MAE, và một
vùng đoán thiếu có hệ thống là lý do loại mô hình, kể cả khi MAE tổng đẹp.

Bảng MAE tổng giấu kín chuyện này hoàn toàn.

### Lớp 6 — Mô hình đúng tới đâu thì hết đúng

Thí nghiệm E2c: huấn luyện **chỉ** trên 180 chuyến tuyến R1 (~472 m), rồi dự báo
5 chuyến ~835 m.

Kết quả: bias = **−7,613 Wh**, đúng bằng −MAE. Nghĩa là nó đoán thiếu **cả 5
chuyến**, trung bình 29,6%, toàn bộ về phía nguy hiểm.

Từ đó xác định **envelope cự ly hợp lệ 420–610 m**. Ngoài dải này mô hình không
dùng được, và sản phẩm D3 bắt buộc phải tự phát hiện và đánh dấu.

E2c là **thí nghiệm bổ sung ngoài giao thức của thầy**, đã khai báo rõ trong
`d2_protocol.yaml`. Cách viết bắt buộc: *"kiểm tra sơ bộ trên một tập giữ lại
nhỏ"*, tuyệt đối không viết *"đã kiểm chứng"*.

### Tổng kết — trả lời thầy trong một câu

> Mô hình sai trung bình 0,66 Wh, tức khoảng 3%, với khoảng tin cậy 95% là
> [0,58 ; 0,73]. Con số này đến từ 25 lần huấn luyện độc lập trên dữ liệu mô
> hình chưa từng thấy, được kiểm thêm bằng giữ lại cấu hình, bootstrap 2.000 lần
> và phân tích sai số theo 18 nhóm. Nó chỉ có hiệu lực trong cự ly 420–610 m;
> ngoài dải đó mô hình đoán thiếu có hệ thống 29,6%.

Câu cuối mới là câu làm người nghe tin ba câu đầu.

---

## 6. Muốn tự kiểm lại thì làm thế nào

### Kiểm mức 1 — chạy lại toàn bộ

```bash
source .venv/bin/activate
python3 -m src.features --out data/processed/flight_level.csv
python3 -m src.evaluation_energy          # 10–15 phút
python3 -m src.bootstrap_ci
python3 -m src.subgroup_analysis
```

Vì seed cố định ở 42, **phải ra đúng những con số trong `reports/`**. Lệch là có
chuyện — hoặc dữ liệu khác, hoặc code đã bị sửa, hoặc phiên bản thư viện khác.

Ngoại lệ duy nhất: cột `inference_ms` phụ thuộc phần cứng, mỗi máy một khác. Đó
là lý do con số đó chỉ sống trong CSV, không chép vào tài liệu.

### Kiểm mức 2 — chạy test tự động

```bash
pytest
```

56 test. Đáng chú ý là 14 test trong `TestProtocolIntegrity` — chúng kiểm chính
file `d2_protocol.yaml`: đủ 9 biến cấm chưa, seed có đúng 42 không, hai tập đặc
trưng có đúng 6 cột không, tập `preflight` có lọt biến hậu nghiệm nào không.

Tức là nếu ai đó sửa giao thức một cách không hợp lệ, test sẽ đỏ trước khi kịp
chạy ra kết quả sai.

### Kiểm mức 3 — thử phá cho hỏng

Cách tốt nhất để tin một hàng rào là xem nó có chặn thật không.

**Thử 1 — cố tình đưa biến cấm vào.** Mở `configs/d2_protocol.yaml`, thêm
`speed_realised_ms` vào `features.preflight`, chạy `python3 -m src.evaluation_energy`.

Phải thấy:
```
ValueError: RO RI: bien hau nghiem trong tap dac trung: {'speed_realised_ms'}
```
Nếu nó chạy bình thường thì hàng rào hỏng. **Nhớ hoàn nguyên file sau khi thử.**

**Thử 2 — xem rò rỉ làm điểm đẹp thế nào.** Tạm thời bỏ `speed_realised_ms` khỏi
danh sách `forbidden` rồi thêm vào `preflight`, chạy lại. MAE sẽ tụt xuống rất
thấp — và đó chính là lý do phải cấm. Nó "biết trước đáp án" qua đường vòng.

Đây là thí nghiệm đáng làm một lần, vì nó cho cảm giác cụ thể về rò rỉ dữ liệu,
thứ mà đọc lý thuyết rất khó hình dung. **Hoàn nguyên file sau khi thử.**

**Thử 3 — đổi seed.** Sửa `partitioning.cv.random_state` từ 42 sang 7, chạy lại
E2a. MAE sẽ đổi chút ít, nhưng **thứ hạng các mô hình phải giữ nguyên** và chênh
lệch phải nằm trong khoảng độ lệch chuẩn đã báo (0,075). Nếu thứ hạng đảo lộn
thì kết luận không vững.

**Thử 4 — kiểm bằng tay một chuyến.** Lấy một dòng trong
`reports/d2_oof_residuals.csv`, nhân 6 giá trị đầu vào với 6 hệ số trong
`d2_ridge_coefficients.csv` (cột đơn vị gốc), cộng hệ số chặn. Ra gần đúng giá
trị dự báo trong file. Đây là cách chứng minh mô hình không phải hộp đen.

### Kiểm mức 4 — người khác kiểm

Theo Mục 10 của thầy: **người làm không được là người duy nhất kiểm**. Duy là
người kiểm chéo. Ba việc cụ thể nên nhờ:

1. Chạy `pytest` và `src.evaluation_energy` trên máy của mình, đối chiếu số
2. Đọc danh sách 9 biến cấm, tự hỏi còn biến nào đáng cấm mà chưa cấm không
3. Làm Thử 1 ở trên, xác nhận hàng rào hoạt động

---

## 7. Những câu dễ bị hỏi

**"Có 192 dòng mà train được gì?"**
Ít thật, và nhóm đã nói rõ trong bài. Cỡ mẫu hiệu dụng còn gần 60 cấu hình hơn
là 192 chuyến, vì lưới giai thừa 3 tải × 5 tốc độ × 4 độ cao có 2–5 chuyến mỗi
ô. Chính vì ít nên mới chọn Ridge chứ không phải mạng nơ-ron, chọn CV lặp 25 lần
chứ không phải một lần chia, và chọn bootstrap để kiểm chênh lệch. Toàn bộ thiết
kế là để phù hợp với dữ liệu nhỏ.

**"Sao không dùng deep learning cho hiện đại?"**
Mạng nơ-ron cần hàng nghìn tới hàng chục nghìn ví dụ. Với 192 dòng nó sẽ học
thuộc rồi sụp khi gặp cấu hình mới — chính là thứ E2b đã bắt được ở Random
Forest, và mạng nơ-ron còn tệ hơn. §5.2 ưu tiên mô hình đơn giản vì dữ liệu nhỏ.
Chọn mô hình phù hợp cỡ dữ liệu là quyết định kỹ thuật đúng, không phải thiếu
tham vọng.

**"Random Forest mạnh hơn Ridge mà, sao lại thua?"**
Mạnh hơn khi có nhiều dữ liệu và quan hệ phức tạp. Ở đây quan hệ khá tuyến tính
và dữ liệu ít, nên sức mạnh đó thành điểm yếu — nó khớp cả nhiễu. Giao thức đã
ghi trước điều này từ tuần 2, trước khi chạy: *"với 192 dòng và quan hệ khá
tuyến tính, KHÔNG kỳ vọng D3 thắng D2 nhiều. Nếu D3 không thắng D2 thì đó là kết
quả bình thường và đúng — viết thẳng ra."*

**"Mô hình có chắc chắn đúng không?"**
Không. Nó sai trung bình 0,66 Wh, và sai nhiều hơn hẳn ngoài cự ly 420–610 m.
Đó là lý do sản phẩm D3 không dùng thẳng con số dự báo mà cộng thêm **biên dự
trữ** tính từ chính sai số đã đo này.

**"Đây có phải AI không?"**
Là học máy. Mô hình tự rút quy luật từ dữ liệu thay vì được lập trình sẵn công
thức. Không phải mạng nơ-ron, không phải mô hình ngôn ngữ — và với bài toán an
toàn thì đó là ưu điểm: mỗi hệ số đọc được, mỗi quyết định truy ngược được.

---

## Đọc tiếp

| Muốn gì | Đọc |
|---|---|
| Chi tiết từng mô hình | `D0_trung_binh_hang.md` … `D5_mo_hinh_vat_ly.md` |
| Kết quả so sánh đầy đủ | `../san_pham/D2_benchmark_nang_luong.md` |
| Vì sao chọn Ridge | `../../reports/model_selection_report.md` |
| Luật chơi đã đóng băng | `../../configs/d2_protocol.yaml` |
| Gặp từ lạ | `../thuat_ngu.md` |
