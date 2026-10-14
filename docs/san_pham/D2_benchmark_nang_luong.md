# Sản phẩm D2 — Benchmark dự báo năng lượng

> Tài liệu này về **sản phẩm bàn giao D2** — cuộc so sánh giữa các **mô hình
> D0–D5** của §5.2. Hai hệ đánh số khác nhau, xem `README.md` ở gốc repo.
> Mô tả từng mô hình riêng lẻ: thư mục `../cach_lam/`.

**Người làm:** Phát (WP2) · **Người kiểm chéo:** Duy · **Tuần 4–6**

> **Quyền:** đọc mục 8 trước khi bắt đầu D3. Có một ràng buộc cứng ở đó.

---

## 1. D2 để làm gì

Câu hỏi: **nếu chỉ biết trước tải trọng, tốc độ, độ cao, cự ly và gió — đoán được
chuyến bay sẽ tốn bao nhiêu pin, chính xác tới đâu?**

Đây là RQ1 của thầy. Giả thuyết H1: *mô hình đa yếu tố sẽ thắng mô hình chỉ dựa
vào cự ly.*

Thầy cũng ghi sẵn **điều kiện phủ định** — tức là điều gì xảy ra thì coi như giả
thuyết sai: nếu mô hình đa yếu tố không giảm được sai số so với mô hình chỉ cự ly,
hoặc cải thiện không ổn định qua các lần chia dữ liệu.

Viết sẵn điều kiện phủ định trước khi chạy là cách làm chuẩn của nghiên cứu khoa
học. Nó ngăn việc nhìn kết quả rồi mới nghĩ ra cách diễn giải cho đẹp.

D2 phục vụ ba chỗ khác nhau trong dự án:

1. Trả lời RQ1 — một trong hai kết quả chính của bài.
2. Cung cấp `E_required` cho công thức quyết định ở D3.
3. Cung cấp phân phối sai số cho phân tích bất định ở D5.

---

## 2. Bảy mô hình được so sánh

Danh sách lấy nguyên từ §5.2. **Không thêm mô hình nào ngoài danh sách** — thầy
cấm nhồi thêm thuật toán chỉ để bảng so sánh trông dày.

**Mô tả chi tiết từng mô hình nằm ở `../cach_lam/`**, mỗi mô hình một file: thầy yêu
cầu gì, cài đặt thế nào, kết quả riêng, điểm mạnh yếu.

| Mô hình §5.2 | Tài liệu | Biến thể chạy | Trạng thái |
|---|---|---|---|
| D0 Trung bình hằng | `../cach_lam/D0_trung_binh_hang.md` | 1 | Xong |
| D1 Chỉ cự ly | `../cach_lam/D1_chi_cu_ly.md` | OLS, Huber | Xong |
| D2 Ridge | `../cach_lam/D2_ridge.md` | D2-a, D2-b | Xong — **được chọn** |
| D3 Random Forest | `../cach_lam/D3_random_forest.md` | D3-a, D3-b | Xong |
| D4 Gradient boosting | *(xem `../cach_lam/README.md`)* | — | Chưa — bị chặn |
| D5 Mô hình vật lý | `../cach_lam/D5_mo_hinh_vat_ly.md` | — | **Đang làm** — tuần 6 |

Bảy biến thể, vì D2 và D3 mỗi cái chạy hai phiên bản đặc trưng (mục 3).

Tài liệu này chỉ giữ những gì **chỉ có nghĩa khi đặt các mô hình cạnh nhau**: bảng
xếp hạng, khoảng tin cậy, giữ lại cấu hình, ngoại suy cự ly, và hình vẽ.

---

## 3. Chuyện hai phiên bản D2 và D3

Thầy liệt kê tập đặc trưng D2 gồm: *quãng đường, tải trọng, tốc độ, độ cao,
**thời gian bay**, và đặc trưng liên quan đến gió.*

Vấn đề: **"thời gian bay" có hai nghĩa.**

- **Đo được** (`duration_s`): chuyến bay thực tế kéo dài bao lâu. Chỉ biết sau khi
  bay xong.
- **Kế hoạch** (`duration_planned_s`): cự ly ÷ tốc độ hành trình. Tính được trước
  khi cất cánh.

Đề tài là đánh giá **trước** chuyến bay, nên dùng loại thứ nhất thì mô hình không
chạy được vào đúng lúc cần dùng. Nhưng thầy có viết chữ "duration" nên nhóm không
tự ý bỏ.

**Quyết định: chạy cả hai, báo cả hai.**

- `D2-a` / `D3-a` — dùng `duration_s`, đúng chữ §5.2
- `D2-b` / `D3-b` — dùng `duration_planned_s`, theo §5.5

### Căn cứ câu chữ

Ba điểm, ghi trong `configs/d2_protocol.yaml`:

1. §5.2 dùng cụm **"such as"** — liệt kê minh hoạ, không bắt buộc. Nhóm tự chốt
   tập đặc trưng rồi khai báo.
2. §4.3 là bảng thầy quy định biến nào *dùng được* và *hạn chế gì* — **không có
   `duration`** trong bảng đó.
3. §5.5 bắt khai báo giả định tốc độ hành trình, tức thừa nhận thời lượng là đại
   lượng suy ra khi lập kế hoạch.

### Bằng chứng số

Trước khi quyết định, kiểm xem hai loại có thực sự khác nhau không: hồi quy
`duration_s` theo các biến biết trước khi bay cho **R² = 0,73**.

Nghĩa là 27% thông tin trong thời lượng đo được **không** suy ra được từ kế hoạch
bay. Hai biến thể thật sự khác nhau → phải chạy cả hai.

Nếu R² đã ~0,95 thì hai cái gần như trùng nhau, khỏi cần bàn.

---

## 4. Chống rò rỉ dữ liệu — phần kỹ thuật quan trọng nhất

"Rò rỉ" (leakage) là khi mô hình vô tình nhìn thấy đáp án lúc học. Kết quả trông
rất đẹp nhưng vô giá trị.

Bộ dữ liệu này có **hai đường rò rỉ**, thầy chỉ rõ cả hai ở §5.3.

### Đường 1 — chia theo mẫu thay vì theo chuyến bay

Mỗi chuyến bay có hơn 1.800 dòng telemetry. Nếu chia ngẫu nhiên theo dòng, cùng
một chuyến bay sẽ nằm ở cả hai phía. Mô hình đã thấy chuyến đó khi học rồi bị
kiểm trên chính nó.

**Cách chặn:** gộp mỗi chuyến thành đúng một dòng trước khi làm gì cả. Đơn vị
phân tích là **chuyến bay**, không phải mẫu.

### Đường 2 — các cấu hình lặp lại

60 tổ hợp, mỗi tổ hợp 2–5 chuyến gần giống hệt nhau. Chia ngẫu nhiên sẽ để chuyến
"tải 250 g, tốc độ 8, cao 50 m" ở phần học và một chuyến y hệt ở phần kiểm. Mô
hình chỉ cần nhớ, không cần hiểu.

**Cách chặn:** thí nghiệm E2b, bỏ nguyên cả tổ hợp ra khỏi phần học.

### Đường 3 — biến hậu nghiệm

Đã nói ở `D1_ra_soat_du_lieu.md` mục 7. Hàm `assert_no_leakage` trong
`evaluation_energy.py` chặn tự động, và có unit test kiểm luôn file cấu hình.

### Chuẩn hoá và tinh chỉnh

Hai việc nữa dễ rò rỉ mà ít người để ý:

- **Chuẩn hoá đặc trưng** phải dùng trung bình và độ lệch chuẩn **của riêng phần
  học**. Nếu tính trên toàn bộ dữ liệu thì thông tin từ phần kiểm đã lọt vào.
  Giải pháp: bọc trong `Pipeline` của scikit-learn, nó tự xử lý đúng.
- **Chọn siêu tham số** (alpha của Ridge, độ sâu cây của RF) phải dùng **CV lồng**
  — chia tiếp phần học thành các fold con để thử. Không bao giờ đụng vào phần kiểm.

---

## 5. Cross-validation là gì

Vấn đề: chỉ có 192 chuyến. Nếu để riêng 40 chuyến làm bài kiểm thì chỉ còn 152 để
học, mà kết quả lại phụ thuộc vào việc 40 chuyến đó tình cờ là chuyến nào.

**Cross-validation 5-fold** giải quyết bằng cách luân phiên:

```
Chia 192 chuyến thành 5 phần.
Lần 1: học trên phần 2,3,4,5 → kiểm trên phần 1
Lần 2: học trên phần 1,3,4,5 → kiểm trên phần 2
...
Lần 5: học trên phần 1,2,3,4 → kiểm trên phần 5
```

Mỗi chuyến bay được kiểm đúng một lần, và mô hình chưa từng thấy nó lúc học.

**Lặp 5 lần** nghĩa là làm lại toàn bộ với 5 cách chia ngẫu nhiên khác nhau. Tổng
25 lần huấn luyện cho mỗi mô hình. Mục đích: xem kết quả có ổn định không, hay chỉ
may mắn ở một cách chia.

Con số `MAE_std` trong bảng kết quả chính là độ dao động đó.

---

## 6. Các thước đo

| Cột | Nghĩa | Đọc thế nào |
|---|---|---|
| **MAE** | Sai số tuyệt đối trung bình, Wh | Đoán lệch bao nhiêu Wh. Càng nhỏ càng tốt. So với nền 21,3 Wh |
| **RMSE** | Sai số bình phương trung bình | Cũng là sai số nhưng phạt nặng các lần sai lớn. RMSE ≫ MAE nghĩa là thỉnh thoảng sai rất nặng |
| **bias** | Sai số **có dấu** | **Cột quan trọng nhất về an toàn** — xem bên dưới |
| **WAPE** | MAE quy ra phần trăm | Dễ cảm nhận hơn MAE |
| **MAE_std** | Độ dao động qua 25 lần chạy | Nhỏ = đáng tin, không phải ăn may |

### Vì sao bias quan trọng nhất

MAE cho biết sai **bao nhiêu**, bias cho biết sai **về phía nào**.

- **bias dương** → mô hình đoán **thừa**, tưởng tốn nhiều pin hơn thực tế.
  Hậu quả: từ chối vài chuyến bay lẽ ra bay được. Phí, nhưng an toàn.
- **bias âm** → mô hình đoán **thiếu**, tưởng tốn ít pin hơn thực tế.
  Hậu quả: **cho phép bay những chuyến sẽ hết pin giữa đường.**

Thầy viết ở §5.3: *"dự báo thiếu một cách hệ thống là vấn đề an toàn"*. Đây chính
là lý do.

Hai mô hình cùng MAE = 2,0 Wh nhưng một cái bias = 0 và cái kia bias = −2,0 là hai
chuyện hoàn toàn khác nhau về mức độ nguy hiểm.

---

## 7. Kết quả

### E2a — Cross-validation ở cấp chuyến bay

| Mô hình | Đặc trưng | MAE | std | RMSE | bias | WAPE |
|---|---|---|---|---|---|---|
| **D2-b Ridge (trước chuyến bay)** | 6 | **0,657** | 0,075 | 0,840 | +0,010 | **3,09%** |
| D3-b Random Forest (trước chuyến bay) | 6 | 1,014 | 0,144 | 1,502 | −0,001 | 4,76% |
| D2-a Ridge (có duration đo được) | 6 | 1,073 | 0,152 | 1,339 | +0,013 | 5,05% |
| D3-a Random Forest (có duration đo được) | 6 | 1,362 | 0,234 | 1,977 | +0,073 | 6,39% |
| D1 chỉ cự ly (Huber) | 1 | 3,968 | 0,502 | 4,900 | −0,326 | 18,63% |
| D1 chỉ cự ly (OLS) | 1 | 3,974 | 0,459 | 4,897 | −0,007 | 18,67% |
| D0 trung bình hằng | 0 | 3,975 | 0,468 | 4,894 | 0,000 | 18,67% |

**Bốn điều rút ra:**

**(a) D1 không hơn gì D0.** 3,974 so với 3,975 — chênh 0,001 Wh, tức bằng không.
Biết cự ly chẳng giúp gì hơn so với không biết gì.

Lý do: 94% chuyến bay cùng một tuyến, cự ly gần như là hằng số nên không mang
thông tin. **Đây KHÔNG phải kết luận "cự ly không ảnh hưởng tới năng lượng"** —
chỉ là dữ liệu không cho phép kiểm điều đó. Câu này bắt buộc phải nằm ngay dưới
bảng trong bài, nếu không người đọc sẽ hiểu sai.

**(b) H1 được ủng hộ mạnh.** MAE giảm từ 3,974 xuống 0,657, tức **giảm 83%**. Độ
lệch chuẩn chỉ 0,075 → ổn định qua cả 25 lần chạy. Điều kiện phủ định không xảy ra.

**(c) D2-b thắng D2-a — bất ngờ lớn nhất.** 0,657 so với 1,073, tốt hơn 39%.

Ngược trực giác: dùng thời lượng **kế hoạch** lại chính xác hơn dùng thời lượng
**đo được**. Diễn giải: `cự ly ÷ tốc độ ra lệnh` là đại lượng sạch, phản ánh đúng
ý định bay. Còn thời lượng đo được chứa cả nhiễu vận hành — thời gian treo chờ,
trễ cất cánh, biến động điều khiển — những thứ không tương ứng tuyến tính với
năng lượng.

Kết quả này giải quyết luôn tranh luận ở mục 3: **phiên bản pre-flight không phải
nhượng bộ.** Nó vừa đúng về vận hành vừa chính xác hơn.

**(d) Ridge thắng Random Forest.** 0,657 so với 1,014. Với 192 dòng và quan hệ gần
tuyến tính, mô hình đơn giản thắng — bình thường, viết thẳng ra. Thầy đã cảnh báo
trước ở §5.2 rằng không nên kỳ vọng RF thắng.

### E2b — Giữ lại cấu hình

| Mô hình | E2a | E2b | chênh |
|---|---|---|---|
| D2-b Ridge | 0,657 | 0,672 | +2% |
| D2-a Ridge | 1,073 | 1,116 | +4% |
| D3-b Random Forest | 1,014 | 1,386 | **+37%** |

Ridge gần như không đổi → **hiểu quy luật thật**, tổng quát được ra điều kiện chưa
từng thấy.

Random Forest tụt 37% → **có học vẹt một phần**, bám vào các cấu hình cụ thể trong
tập huấn luyện. Thêm một lý do chọn Ridge làm mô hình chính.

### E2c — Ngoại suy cự ly

> **Lưu ý:** thí nghiệm này **không có trong giao thức của thầy**. Nó là bổ sung
> của nhóm, khai báo rõ ràng. Thầy không cấm bổ sung, chỉ cấm *nới lỏng*. Kết quả
> của nó **không được dùng để chọn mô hình**.

Huấn luyện **chỉ trên tuyến R1** (~472 m), rồi dự báo các chuyến dài hơn:

| Mô hình | 427–609 m (7 chuyến) | ~835 m (5 chuyến) |
|---|---|---|
| | MAE / bias | MAE / bias |
| D2-b Ridge | 0,740 / −0,15 | **7,613 / −7,613** |
| D2-a Ridge | 2,594 / −1,89 | 15,206 / −15,206 |
| D3-b Random Forest | 3,113 / +3,11 | 4,612 / −1,98 |
| D1 chỉ cự ly | 3,573 / −0,79 | **25,477 / −25,477** |

**Đây là phát hiện quan trọng nhất của D2.**

Nhìn dòng D2-b ở cột 835 m: MAE = 7,613 và bias = −7,613. Hai số **bằng nhau** —
điều đó chỉ xảy ra khi mô hình đoán thiếu ở **toàn bộ 5 chuyến, không trừ chuyến
nào**. Sai 29,6% theo một chiều duy nhất, và là chiều nguy hiểm.

Dịch sang nghĩa vận hành: hỏi hệ thống về chuyến giao hàng 835 m, nó trả lời *"cần
18 Wh"* trong khi thực tế cần 26 Wh. Hệ thống sẽ cấp phán quyết **FLY cho chuyến
bay sẽ hết pin giữa đường** — đúng loại lỗi "cho bay nhầm" mà cả đề tài lấy làm
thước đo an toàn chính.

**Hạn chế của chính thí nghiệm này:** cả 5 chuyến dài bay **cùng ngày
19/09/2019**. Sai lệch có thể do cự ly dài, cũng có thể do điều kiện hôm đó hoặc
tình trạng pin lúc đó — không tách được. Viết là *kiểm tra sơ bộ*, tuyệt đối không
viết *đã kiểm chứng*.

### File thứ tư

`d2_oof_residuals.csv` ghi sai số của từng chuyến bay cụ thể với từng mô hình.
Dùng cho phân tích sai số theo nhóm ở mục 7b, và sẽ là nguyên liệu cho mô phỏng
bất định ở D5 (§5.8).

---

## 7b. Sai số theo nhóm

§5.3 bắt buộc: *"Error by payload, speed, altitude, wind condition, and flight
pattern"*.

**Vì sao cần:** MAE = 0,657 là trung bình của 192 chuyến bay rất khác nhau. Con số
trung bình có thể giấu mất một vùng mô hình yếu hẳn. Ví dụ nếu mô hình kém khi
mang tải nặng, đó là thông tin an toàn quan trọng — vì giao hàng thật hay mang tải
nặng.

Chạy bằng `python3 -m src.subgroup_analysis`, đọc từ `d2_oof_residuals.csv` nên rất
nhanh, không phải huấn luyện lại.

### D2-b Ridge — mô hình chính

| Chiều | Nhóm | n | MAE | bias |
|---|---|---|---|---|
| Tải trọng (g) | 0 | 66 | 0,685 | −0,021 |
| | 250 | 61 | 0,547 | +0,092 |
| | 500 | 65 | 0,727 | −0,034 |
| Tốc độ (m/s) | 4 | 40 | 0,884 | +0,017 |
| | 6 | 38 | 0,532 | −0,100 |
| | 8 | 36 | 0,474 | +0,113 |
| | 10 | 41 | 0,585 | +0,188 |
| | 12 | 37 | 0,790 | −0,180 |
| Độ cao (m) | 25 | 53 | 0,705 | +0,097 |
| | 50 | 47 | 0,568 | −0,077 |
| | 75 | 47 | 0,575 | −0,107 |
| | 100 | 45 | 0,772 | +0,122 |
| Chế độ gió | thấp (<4,14) | 64 | 0,639 | −0,074 |
| | vừa (4,14–4,82) | 64 | 0,505 | +0,088 |
| | cao (>4,82) | 64 | 0,821 | +0,018 |
| Dải cự ly | ~472 m (R1) | 183 | 0,642 | −0,006 |
| | 500–700 m | 4 | 0,976 | +0,896 |
| | >700 m | 5 | 0,876 | −0,106 |

**Kết luận: D2-b sai đều, không có vùng yếu nguy hiểm.**

- MAE dao động hẹp, từ 0,474 đến 0,884 Wh — chênh chưa tới 2 lần giữa nhóm tốt
  nhất và kém nhất.
- **Không nhóm nào có bias âm đáng kể.** Giá trị âm nhất là −0,180 Wh ở tốc độ
  12 m/s, quá nhỏ để lo ngại.
- Tải 500 g: MAE 0,727 với bias gần như bằng 0. Đây là điều quan trọng — mô hình
  **không** kém đi khi mang tải nặng.
- Gió mạnh làm sai số nhích lên (0,821 so với 0,505 ở gió vừa) nhưng bias vẫn
  trung tính.

Đây là một kết quả mạnh và nên nêu rõ trong bài: mô hình không chỉ chính xác trung
bình mà còn **ổn định qua mọi điều kiện vận hành có trong dữ liệu**.

### D3-b Random Forest — có vùng nguy hiểm

| Chiều | Nhóm | n | MAE | bias | |
|---|---|---|---|---|---|
| Tải trọng (g) | 0 | 66 | 1,050 | +0,836 | |
| | 250 | 61 | 0,857 | −0,207 | |
| | **500** | 65 | 0,986 | **−0,654** | **đoán thiếu** |
| Tốc độ (m/s) | **4** | 40 | **1,682** | −0,185 | sai nặng hơn hẳn |
| Độ cao (m) | **100** | 45 | 1,112 | **−0,710** | **đoán thiếu** |
| Dải cự ly | **>700 m** | 5 | 3,814 | **−3,111** | **đoán thiếu** |

Random Forest đoán **thiếu** ở ba vùng cùng lúc: tải nặng, bay cao, và cự ly dài.
Ba điều kiện này đều là điều kiện nhiệm vụ giao hàng thực tế hay gặp.

Đây là **lý do thứ ba** để chọn Ridge, bổ sung cho hai lý do đã có (chính xác hơn,
và không tụt khi giữ lại cấu hình). Hai mô hình có MAE tổng thể không chênh quá
nhiều — 0,657 so với 1,014 — nhưng phân tích theo nhóm cho thấy chúng khác hẳn nhau
về **hành vi an toàn**.

### D1 chỉ cự ly — sai lệch có hệ thống khắp nơi

Bias chạy từ −5,86 Wh (tốc độ 4 m/s) tới +4,03 Wh (độ cao 25 m). Mô hình không chỉ
sai nhiều mà còn sai theo những hướng khác nhau tuỳ điều kiện.

Dễ hiểu: nó chỉ có một biến đầu vào gần như không đổi, nên về bản chất nó đang đoán
một hằng số và mọi khác biệt do tải, tốc độ, độ cao đều trở thành sai số có hệ
thống.

### Ghi chú về đọc bảng

Ba nhóm cuối ở chiều "Dải cự ly" có n rất nhỏ (4 và 5 chuyến). **Không rút kết
luận mạnh từ chúng.** Chúng có mặt ở đây để đối chiếu với thí nghiệm E2c, không
phải để kết luận độc lập.

---

## 7c. Diễn giải mô hình

§5.2 ghi về D3: *"Feature importance is descriptive, not causal."* Mục này trích
xuất con số đó, kèm luôn hệ số hồi quy của Ridge.

Chạy bằng `python3 -m src.interpretability`.

### Hệ số hồi quy Ridge (D2-b)

Ridge chọn `alpha = 1.0`, hằng số 21,270 Wh.

| Đặc trưng | Hệ số (chuẩn hoá) | Hệ số (đơn vị gốc) |
|---|---|---|
| thời lượng kế hoạch | **4,122** | +0,1356 Wh mỗi giây |
| độ cao | **3,052** | +0,1085 Wh mỗi mét |
| tải trọng | 1,677 | +0,0081 Wh mỗi gram |
| tốc độ ra lệnh | 0,668 | +0,2353 Wh mỗi m/s |
| gió trung bình | 0,119 | +0,1428 Wh mỗi m/s |
| cự ly | −0,077 | −0,0013 Wh mỗi mét |

**Hai cách đọc, đừng lẫn:**

- **Hệ số chuẩn hoá** so sánh được giữa các đặc trưng — "cái nào ảnh hưởng mạnh
  hơn". Vì mọi đặc trưng đã đưa về cùng thang đo.
- **Hệ số đơn vị gốc** đọc trực tiếp được — "tăng 100 g tải thì tốn thêm 0,81 Wh".
  Nhưng không so sánh giữa các đặc trưng được, vì đơn vị khác nhau.

Con số đơn vị gốc rất đáng đưa vào bài: nó biến mô hình từ hộp đen thành câu phát
biểu kiểm chứng được.

**Cảnh báo bắt buộc:** các hệ số này là **có điều kiện**, không phải ảnh hưởng độc
lập. Cụ thể `duration_planned_s = cự ly ÷ tốc độ` nên nó và `speed_num` liên hệ
cơ học với nhau. Vì vậy hệ số của tốc độ **dương** (+0,668) dù tương quan thô giữa
tốc độ và năng lượng là **âm** (−0,602). Không mâu thuẫn — chỉ là "giữ thời lượng
không đổi, tăng tốc độ" là một tình huống khác với "tăng tốc độ trên cùng tuyến
bay". Phải nói rõ trong bài, nếu không người đọc sẽ thấy nghịch lý.

Hệ số cự ly gần như bằng 0 (−0,077) — lại là hệ quả của việc 94% chuyến cùng một
tuyến. Không đọc thành "cự ly không quan trọng".

### Độ quan trọng đặc trưng (D3-b Random Forest)

Tham số chọn được: `max_depth = 8`, `min_samples_leaf = 2`.

| Đặc trưng | Độ quan trọng | Độ lệch chuẩn giữa các cây |
|---|---|---|
| thời lượng kế hoạch | 0,480 | 0,110 |
| độ cao | 0,341 | 0,046 |
| tải trọng | 0,107 | 0,029 |
| tốc độ ra lệnh | 0,032 | 0,092 |
| gió trung bình | 0,024 | 0,021 |
| cự ly | 0,017 | 0,016 |

**Hai mô hình đồng ý với nhau về thứ tự ba đặc trưng đầu**: thời lượng kế hoạch >
độ cao > tải trọng. Hai thuật toán hoàn toàn khác nhau cùng ra một kết luận là
dấu hiệu quy luật có thật, không phải sản phẩm của một lựa chọn mô hình.

**Cảnh báo bắt buộc (§5.2):** độ quan trọng đặc trưng chỉ **mô tả** mô hình dùng
cột nào nhiều khi chia cây. Nó **không** phải quan hệ nhân quả, và không đọc được
thành "tăng biến X thì năng lượng tăng bao nhiêu".

Chú ý thêm: tốc độ có độ quan trọng 0,032 nhưng độ lệch chuẩn 0,092 — **lớn gấp
ba lần chính giá trị đó**. Nghĩa là các cây rất không thống nhất về việc có dùng
cột này hay không. Không rút kết luận gì từ nó.

---

## 7d. Hình cho bài

Sinh bằng `python3 -m src.figures`, ghi vào `reports/figures/` dạng PNG 300 dpi.
Mục 9 của thầy yêu cầu: *mọi hình trong bài phải sinh từ script* — không vẽ tay,
không chỉnh trong Excel.

| Hình | Nội dung | Dùng ở phần nào |
|---|---|---|
| `fig1_model_comparison` | MAE của 7 mô hình, kèm thanh độ lệch chuẩn | Kết quả |
| `fig2_predicted_vs_measured` | Dự báo out-of-fold so với đo được, D2-b | Kết quả |
| `fig3_residuals_by_condition` | Phần dư theo tải, tốc độ, độ cao, gió | Kết quả |
| `fig4_distance_extrapolation` | bias theo dải cự ly — phát hiện đoán thiếu | Thảo luận / Hạn chế |
| `fig5_interpretation` | Hệ số Ridge và độ quan trọng RF | Thảo luận |

Bảng màu đã qua kiểm định: dải độ sáng, ngưỡng chroma, tách biệt với các dạng mù
màu, và độ tương phản với nền. Hình dùng nền trắng cho bản in.

---

## 7e. Khoảng tin cậy bootstrap

§5.3 cấm: *"Do not claim that a small difference is significant merely because one
split gives a lower error."* §8 mục 2 đòi dùng **khoảng tin cậy bootstrap ở cấp
chuyến bay**, và cảnh báo không được bốc từng dòng telemetry như thể chúng độc lập.

**Vì sao cần:** cột `MAE_std` cho biết kết quả có **ổn định** qua các lần chia.
Nó không trả lời câu khác: chênh lệch giữa hai mô hình có **thật** không.

**Cách làm:** bốc ngẫu nhiên có hoàn lại 192 chuyến bay, tính lại MAE, lặp 2.000
lần. Bốc theo **cặp** — dùng cùng bộ chỉ số cho cả hai mô hình — vì bốc riêng sẽ
làm mất tương quan (hai mô hình cùng sai nặng ở cùng những chuyến khó) và cho
khoảng rộng hơn thực tế.

Chạy bằng `python3 -m src.bootstrap_ci`. Rất nhanh vì đọc phần dư out-of-fold,
không huấn luyện lại.

### MAE kèm khoảng tin cậy 95%

| Mô hình | MAE | Khoảng tin cậy 95% |
|---|---|---|
| D2-b Ridge | 0,655 | [0,582 ; 0,729] |
| D3-b Random Forest | 0,967 | [0,822 ; 1,141] |
| D2-a Ridge | 1,068 | [0,952 ; 1,185] |
| D3-a Random Forest | 1,326 | [1,134 ; 1,531] |
| D1 chỉ cự ly (Huber) | 3,967 | [3,557 ; 4,381] |
| D1 chỉ cự ly (OLS) | 3,971 | [3,562 ; 4,387] |
| D0 trung bình hằng | 3,973 | [3,582 ; 4,387] |

### Chênh lệch so với D2-b

| Mô hình | Chênh lệch MAE | Khoảng tin cậy 95% | Kết luận |
|---|---|---|---|
| D3-b Random Forest | +0,312 | [0,153 ; 0,490] | **có ý nghĩa** |
| D2-a Ridge | +0,413 | [0,294 ; 0,531] | **có ý nghĩa** |
| D3-a Random Forest | +0,671 | [0,469 ; 0,902] | **có ý nghĩa** |
| D1 chỉ cự ly (Huber) | +3,311 | [2,925 ; 3,714] | **có ý nghĩa** |
| D1 chỉ cự ly (OLS) | +3,315 | [2,924 ; 3,722] | **có ý nghĩa** |
| D0 trung bình hằng | +3,318 | [2,925 ; 3,723] | **có ý nghĩa** |

Chênh lệch dương nghĩa là mô hình đó **tệ hơn** D2-b.

**Mọi khoảng đều không chứa 0** → D2-b thắng tất cả các mô hình còn lại, và chênh
lệch là thật chứ không phải nhiễu của việc chia dữ liệu.

Đáng chú ý: khoảng tin cậy của D2-b [0,582 ; 0,729] và của D3-b [0,822 ; 1,141]
**không chồng lấn nhau**. Hai mô hình tách bạch rõ ràng.

Đây là câu trả lời cho câu hỏi hội đồng chắc chắn sẽ hỏi: *"chênh 0,36 Wh thì có
đáng kể không?"* Giờ trả lời được bằng số, không phải bằng cảm nhận.

---

## 7f. Thời gian suy luận

§5.3 liệt kê *"Inference time, as a secondary metric"*. Đo thời gian `predict`
cho một chuyến bay, không đo thời gian huấn luyện — khi vận hành, mô hình đã
huấn luyện sẵn, người điều phối chỉ chờ một lần dự báo.

| Mô hình | Thời gian (ms) |
|---|---|
| D0 trung bình hằng | 0,031 |
| D1 chỉ cự ly (OLS) | 0,202 |
| D2-b Ridge | 0,215 |
| D2-a Ridge | 0,213 |
| D3-a Random Forest | 16,4 |
| D3-b Random Forest | **21,7** |

Random Forest chậm hơn Ridge khoảng **100 lần**, vì nó phải chạy qua 300 cây.

Về vận hành thì 21,7 ms vẫn là tức thời với người dùng, nên **đây không phải lý
do loại D3**. Nhưng nó là một lợi thế nhỏ nữa của Ridge, đáng ghi một dòng trong
bài: mô hình được chọn vừa chính xác hơn, vừa ổn định hơn, vừa nhẹ hơn.

---

## 7g. Nhật ký thí nghiệm

§8 mục 6 đòi lưu: phiên bản bộ dữ liệu, seed, cấu hình mô hình, danh sách đặc
trưng, đường dẫn đầu ra.

`configs/d2_protocol.yaml` ghi **kế hoạch**. `reports/experiment_log.jsonl` ghi
**lịch sử chạy** — mỗi lần chạy nối thêm một dòng, kèm thời điểm, mã commit git
và sha256 của bảng dữ liệu.

Xem bằng `python3 -m src.experiment_log`.

Mục đích: ba tháng nữa, lúc viết bài, nhìn một file kết quả và tra ngay được nó
sinh ra từ phiên bản dữ liệu nào, tập đặc trưng nào. Nó cũng bắt được lỗi thầm
lặng — nếu ai đó sửa tập đặc trưng rồi chạy lại mà quên ghi, nhật ký sẽ cho thấy
hai lần chạy có cấu hình khác nhau.

---

## 8. Ràng buộc cho D3 — Quyền đọc kỹ phần này

Ba điều từ D2 ràng buộc công việc của D3 và D4:

### (a) Dùng mô hình nào

**`D2_ridge_preflight`** — Ridge với tập đặc trưng pre-flight. Đây là mô hình duy
nhất vừa chính xác nhất vừa chạy được ở thời điểm trước chuyến bay.

Không dùng `D2_ridge_as_written`: nó cần thời lượng bay thực tế, mà lúc đánh giá
trước chuyến bay thì chưa có con số đó.

### (b) Envelope cự ly hợp lệ

**Bộ máy quyết định chỉ được chạy trong dải khoảng 420–610 m.**

Trong dải đó, D2-b giữ MAE 0,740 Wh và bias gần như bằng không. Ngoài dải đó, mô
hình lạc quan có hệ thống — bias −7,6 Wh ở 835 m.

Hệ quả cho bộ sinh kịch bản ở D4: lấy mẫu cự ly ngoài dải này là lấy mẫu ngoài
vùng mô hình còn giá trị. Nếu vẫn muốn lấy, phải đánh dấu rõ là ngoại suy — §6/E3
của thầy có yêu cầu *"clearly label any extrapolated ranges"*.

### (c) Sai số đưa vào tính dự trữ

MAE 0,657 Wh, hay 3,09%. Đây là con số lan vào phân tích bất định ở D5.

Tin tốt từ mục 7b: trong dải cự ly hợp lệ, sai số **ổn định qua mọi điều kiện** —
tải, tốc độ, độ cao, gió đều cho MAE trong khoảng 0,47–0,88 Wh và bias trung tính.
Nên dùng một con số sai số chung cho mọi tải trọng và độ cao là chấp nhận được,
không cần chia nhỏ theo điều kiện.

Nhưng **theo cự ly thì không**: trong dải hợp lệ 0,74 Wh, ra ngoài 7,6 Wh. Dùng
một con số duy nhất cho mọi cự ly là quá lạc quan.

---

## 9. Còn thiếu gì ở D2

| Việc | Ghi chú |
|---|---|
| ~~Sai số theo nhóm~~ | **Xong** — mục 7b |
| ~~Hình vẽ~~ | **Xong** — mục 7d, 5 hình |
| Kiểm tương thích D5 Gong | §3.2, việc của tuần 6 |
| Báo thầy về hai phiên bản D2 | Báo cáo, không phải xin phép. Kèm số 0,657 và 1,073 |

Và nhớ: D2 chỉ được coi là chính thức sau khi **D1 nghiệm thu xong** — hiện còn
chờ từ điển biến và chữ ký kiểm chéo của Duy.
