# PHẦN 1 — Thầy yêu cầu gì

> ▸ Mở `reports/deliverables.md`, cuộn tới mục D1

Mục 12 trong file hướng dẫn của thầy yêu cầu D1 nộp bốn thứ: từ điển biến, báo
cáo chất lượng, nhật ký loại trừ, và bảng dữ liệu cấp chuyến bay.

Mục 12.1 thì đưa ra sáu tiêu chí nghiệm thu: ghi rõ nguồn và giấy phép, kiểm từ
điển biến và đơn vị, ghi nhật ký loại trừ, test phép tích phân điện áp dòng
điện, mọi dòng giữ định danh chuyến bay, và chia tập theo chuyến bay.

Cộng thêm một điều kiện ở Mục 10: người làm không được là người duy nhất kiểm
kết quả của chính mình.

Và thầy đặt một cổng chặn cứng. Nguyên văn là *"Do not report model scores until
passed"* — chưa đạt D1 thì không được báo bất kỳ điểm số mô hình nào. Nên nhóm
em làm xong D1 và được Duy ký trước, rồi mới công bố kết quả của D2.

> ▸ Chỉ vào bảng nghiệm thu trong `deliverables.md` — tám dòng, tất cả đều Đạt

Tám tiêu chí, hiện đều đạt.

---

# PHẦN 2 — Dữ liệu gốc có gì

Bộ dữ liệu là của Carnegie Mellon, đúng bộ thầy chỉ định ở mục 4.1. Em tải từ
KiltHub theo DOI, giấy phép CC BY 4.0.

Về giấy phép, em không chỉ ghi tên mà đọc kỹ điều khoản, vì nó quyết định sản
phẩm D9 đóng gói được những gì. Kết luận là: nhóm **được phép** công bố bảng dữ
liệu đã xử lý kèm mã nguồn, miễn là ghi công tác giả. Không có điều khoản phi
thương mại nào ràng buộc thêm.

Bộ dữ liệu gồm hai file, và chúng khác nhau hoàn toàn.

File thứ nhất là `parameters.csv`, 209 dòng, mỗi dòng là **một chuyến bay**. Nó
ghi kế hoạch bay: chuyến này mang bao nhiêu gram hàng, tốc độ ra lệnh bao nhiêu,
bay ở độ cao nào.

File thứ hai là `flights.csv`, nặng 107 megabyte. Mỗi dòng ở đây là **một khoảnh
khắc** trong một chuyến bay. Máy bay đo khoảng năm tới chín lần mỗi giây, ghi lại
điện áp, dòng điện, vị trí, vận tốc, gió.

Nói ngắn gọn: file thứ nhất là *kế hoạch bay*, file thứ hai là *nhật ký ghi âm
toàn bộ chuyến bay*.

## Thiết kế thí nghiệm

Có một điểm em muốn nêu, vì nó là điểm mạnh của bộ dữ liệu này.

Nhóm Rodrigues không bay bừa. Họ bay theo lưới giai thừa đầy đủ: ba mức tải, năm
mức tốc độ, bốn mức độ cao. Ba nhân năm nhân bốn là sáu mươi tổ hợp, và cả sáu
mươi đều có mặt, mỗi tổ hợp bay lặp hai tới năm lần.

Nghĩa là các yếu tố **trực giao** — tải, tốc độ, độ cao thay đổi độc lập nhau —
nên tách được ảnh hưởng riêng của từng yếu tố. Dữ liệu quan sát ngẫu nhiên
thường không làm được điều này.

---

# PHẦN 3 — Từ hai file đó ra bảng cuối thế nào

> ▸ Đây là phần hay bị hỏi nhất. Nói chậm.

Đầu ra của D1 là một bảng duy nhất, tên `flight_level.csv`, có **192 dòng**.

Từ hai trăm bốn mươi hai nghìn dòng telemetry xuống còn 192 dòng. Ở đây có **hai
phép rút gọn khác nhau** xảy ra cùng lúc, và em muốn tách rõ ra vì chúng không
liên quan gì tới nhau.

## Phép thứ nhất — gộp nhiều dòng thành một dòng

Đây là lý do từ hàng trăm nghìn dòng xuống còn vài trăm dòng.

Một chuyến bay kéo dài khoảng hai tới bảy phút, máy đo năm tới chín lần mỗi
giây. Nên **một chuyến bay sinh ra từ bảy trăm tới gần ba nghìn dòng**, trung vị
là một nghìn hai trăm hai mươi dòng.

Cộng cả 192 chuyến lại là hai trăm bốn mươi hai nghìn dòng.

Việc của D1 là biến một nghìn hai trăm dòng của mỗi chuyến thành **một dòng tóm
tắt**. Ví dụ chuyến số 5: một nghìn hai trăm hai mươi dòng telemetry, gộp lại
thành một dòng ghi năng lượng hai mươi mốt phẩy bốn watt-giờ, cự ly bốn trăm bảy
mươi hai mét, thời lượng hai trăm lẻ sáu giây.

Con số năng lượng đó là **cộng dồn cả một nghìn hai trăm mẫu**. Cự ly là cộng
dồn từng bước GPS.

Không mất thông tin nào, nó được gộp lại thành đại lượng tổng của cả chuyến.

### Vì sao phải gộp

Có hai lý do, và lý do thứ hai quan trọng hơn.

Lý do thứ nhất là kỹ thuật. Câu hỏi của đề tài là *chuyến bay này tốn bao nhiêu
watt-giờ*. Đơn vị của câu hỏi là chuyến bay. Một mẫu telemetry đơn lẻ không có
"năng lượng của nó" — năng lượng chỉ có nghĩa khi cộng dồn theo thời gian.

Lý do thứ hai là chống rò rỉ dữ liệu. Mục 5.3 của thầy bắt chia tập ở cấp chuyến
bay, nguyên văn là không bao giờ được tách các dòng của cùng một chuyến ra hai
phía huấn luyện và kiểm.

Nếu nhóm em giữ nguyên hai trăm bốn mươi hai nghìn dòng rồi chia ngẫu nhiên, thì
một nghìn hai trăm dòng của cùng một chuyến sẽ nằm ở **cả hai phía**. Mô hình chỉ
cần nhớ chuyến đó chứ không cần học quy luật, và điểm số sẽ đẹp một cách giả tạo.

Gộp thành một dòng mỗi chuyến làm chuyện đó **không thể xảy ra về mặt cấu trúc**,
chứ không phải nhờ một luật mà ai đó phải nhớ tuân thủ.

## Phép thứ hai — loại chuyến không dùng được

> ▸ Mở `reports/exclusion_log.csv`

Đây mới là lý do từ 209 chuyến còn 192 chuyến. Chuyện này xảy ra ở cấp chuyến
bay, không liên quan gì tới telemetry.

Nhóm em loại mười bảy chuyến, theo bốn quy tắc:

Mười ba chuyến **không phải bay hành trình** — mã tuyến bắt đầu bằng chữ A là
chạy không tải, chữ H là bay treo tại chỗ. Đó là chuyến thử nghiệm máy, không
phải nhiệm vụ giao hàng.

Hai chuyến có **độ cao ngoài lưới**, không thuộc hai mươi lăm, năm mươi, bảy mươi
lăm hay một trăm mét.

Một chuyến có **tải ngoài lưới**, không thuộc không, hai trăm năm mươi hay năm
trăm gram.

Một chuyến có **cảm biến dòng hỏng** — dòng trung vị dưới một ampe. Máy bay không
thể bay với dòng nhỏ như vậy, chắc chắn cảm biến lỗi.

> ▸ Cuộn file CSV cho thầy thấy 17 dòng, mỗi dòng một lý do

Bốn quy tắc này **viết trước khi chạy**, không phải loại xong rồi nghĩ lý do.
Mục 4.2 của thầy yêu cầu đúng điều đó — nguyên văn là *pre-defined rules*.

## Hai phép này độc lập

Nếu nhóm em không loại chuyến nào, thì bảng cuối vẫn là 209 dòng — chứ không
phải 209 nghìn dòng. Phép gộp xảy ra bất kể có loại hay không.

---

# PHẦN 4 — Tính năng lượng

> ▸ Phần dài nhất. Nếu thầy gật đầu sớm thì bỏ qua mục 4.3 và 4.4.

Đây là phần lõi của D1, vì cột năng lượng này là mục tiêu dự báo của toàn bộ D2
và là đầu vào công thức quyết định ở D3. Sai ở đây thì mọi thứ phía sau sai theo
mà không ai biết.

## 4.1 — Vấn đề là gì

Bộ dữ liệu **không có** cột "chuyến này tốn bao nhiêu watt-giờ". Nếu có thì D1
đã không tồn tại.

Cái nó có là **điện áp và dòng điện đo liên tục** trong suốt chuyến bay. Nhóm em
phải tự dựng con số năng lượng ra từ hai cột đó.

Công thức thầy ghi ở mục 4.2, và nhóm em không đổi một chữ:

```
P_t = V_t × I_t                 công suất tức thời
E   = Σ  V_t × I_t × Δt         năng lượng cả chuyến
```

## 4.2 — Đi qua một ví dụ bằng số

> ▸ Nếu có bảng hoặc giấy thì viết ba dòng này ra, thầy theo dễ hơn

Em xin lấy một khoảnh khắc thật trong dữ liệu.

Tại thời điểm không giây, pin đang ở **hai mươi hai phẩy bốn vôn**, động cơ rút
**mười tám ampe**.

Công suất lúc đó bằng điện áp nhân dòng điện:

```
22,4 V  ×  18 A  =  403 W
```

Bốn trăm lẻ ba watt. Đó là công suất **tại một khoảnh khắc**.

Nhưng năng lượng thì không phải công suất — năng lượng là **công suất nhân thời
gian**. Giống như xe chạy sáu mươi ki-lô-mét một giờ là *tốc độ*, còn đi được bao
xa thì phải nhân với thời gian chạy.

Nếu công suất giữ nguyên bốn trăm lẻ ba watt trong hai trăm giây thì:

```
403 W  ×  200 s  =  80.600 joule
```

**Nhưng công suất không hề giữ nguyên.** Lúc cất cánh động cơ rút rất mạnh, lúc
bay bằng thì ít hơn, lúc hạ cánh lại khác. Nên không thể nhân một lần là xong.

Cách làm là **cộng dồn từng khoảnh khắc nhỏ**:

```
mẫu thứ 1:   403 W  ×  0,17 s  =  68,5 J
mẫu thứ 2:   412 W  ×  0,17 s  =  70,0 J
mẫu thứ 3:   396 W  ×  0,17 s  =  67,3 J
...
cộng hết 1.220 mẫu
```

Đó chính là ý nghĩa dấu tổng trong công thức của thầy. Trong toán gọi là **tích
phân**.

## 4.3 — Ba chi tiết cài đặt

### Chi tiết một — khoảng thời gian phải lấy thật

Thầy ghi rõ trong mục 4.2: nếu mốc thời gian không đều thì phải dùng hiệu số
thực tế, không được giả định tần số lấy mẫu cố định.

Em kiểm thì tần số dao động từ **năm phẩy ba tới chín phẩy một hertz** giữa các
chuyến bay. Không đều thật.

Nên code của em lấy hiệu hai mốc thời gian liền nhau, không nhân với một hằng số.

### Chi tiết hai — giữa hai mẫu thì giả định thế nào

Đây là chỗ tinh tế. Mình chỉ biết công suất **tại các điểm đo**, không biết nó
biến thiên ra sao **giữa** hai điểm. Bắt buộc phải giả định.

Giả sử hai mẫu liên tiếp:

```
t = 0,00 s   →   P = 400 W
t = 0,12 s   →   P = 440 W
```

Trong một trăm hai mươi phần nghìn giây đó, máy bay tốn bao nhiêu?

**Cách thứ nhất — tổng Riemann.** Giả định công suất giữ nguyên bốn trăm watt
suốt đoạn:

```
400 W  ×  0,12 s  =  48,0 J
```

**Cách thứ hai — quy tắc hình thang.** Giả định công suất tăng đều từ bốn trăm
lên bốn trăm bốn mươi:

```
(400 + 440) / 2  ×  0,12 s  =  420  ×  0,12  =  50,4 J
```

Tên "hình thang" đến từ hình học. Vẽ công suất theo thời gian, đoạn giữa hai mẫu
tạo thành một hình thang — hai cạnh đứng là bốn trăm và bốn trăm bốn mươi, đáy là
không phẩy mười hai giây. Diện tích hình thang chính là năng lượng.

Còn Riemann thì vẽ thành hình chữ nhật, **bỏ sót phần tam giác phía trên**.

Hình thang chính xác hơn khi công suất đang thay đổi — mà công suất của UAV thì
thay đổi liên tục. Nên nhóm em công bố hình thang.

### Chi tiết ba — đổi đơn vị

Tích phân ra **joule**. Nhưng dung lượng pin thì nhà sản xuất ghi theo
**watt-giờ**. Phải đổi.

```
1 Wh  =  1 W  trong  3600 s  =  3600 J
→  chia cho 3600
```

Ví dụ chuyến bay vừa rồi:

```
76.680 J  ÷  3600  =  21,3 Wh
```

Đó là một chuyến bay tốn hai mươi mốt phẩy ba watt-giờ.

## 4.4 — Và đây là điểm em muốn nhấn

Code của em tính năng lượng **hai lần** cho mỗi chuyến bay. Một lần bằng hình
thang, một lần bằng tổng Riemann, rồi so chênh lệch.

Làm vậy với cả 192 chuyến, rồi lấy trung vị của 192 con số chênh lệch đó.

Kết quả: **không phẩy không bốn phần trăm**.

### Vì sao con số nhỏ này lại là tin tốt

Nếu hai phương pháp lệch **nhiều** — ví dụ năm phần trăm — thì nghĩa là dữ liệu
lấy mẫu quá thưa, không bắt kịp biến thiên công suất. Khi đó con số năng lượng
sẽ **phụ thuộc vào việc mình chọn phương pháp nào**. Tức là không đáng tin, và
bất kỳ ai dùng cách khác sẽ ra số khác.

Chênh không phẩy không bốn phần trăm nghĩa là: chọn cách nào cũng ra gần như
cùng một số. Con số năng lượng **vững**, không phải sản phẩm của một lựa chọn kỹ
thuật tuỳ ý.

### Vì sao nó nhỏ đến vậy — nếu thầy hỏi sâu

> ▸ Chỉ nói nếu thầy hỏi. Hơi kỹ.

Có hai lý do cộng lại.

Thứ nhất, tần số lấy mẫu khoảng sáu hertz, tức mỗi mẫu cách nhau khoảng một phần
sáu giây. Trong khoảng đó công suất không kịp đổi nhiều, nên hình thang và hình
chữ nhật gần trùng nhau.

Thứ hai, và cái này thú vị hơn. Chênh lệch giữa hai phương pháp ở **mỗi bước** là
nửa phần chênh công suất nhân delta t. Nhưng khi cộng dồn cả chuyến thì các phần
đó **triệt tiêu lẫn nhau** — chỗ công suất tăng bù cho chỗ công suất giảm. Cuối
cùng chỉ còn lại phần phụ thuộc công suất đầu chuyến và cuối chuyến.

Mà chuyến bay thì bắt đầu và kết thúc đều ở trạng thái công suất thấp, gần giống
nhau. Nên phần dư còn lại rất nhỏ.

Nói cách khác, con số không phẩy không bốn phần trăm không phải may mắn — nó là
hệ quả của việc chuyến bay bắt đầu và kết thúc ở cùng một trạng thái.

## 4.5 — Không phân đoạn theo pha bay

Một quyết định nữa em muốn báo rõ.

Mục 4.2 bước bốn của thầy cho phép dùng tổng năng lượng cả chuyến nếu phân đoạn
pha bay không đáng tin, nguyên văn là *"If phase segmentation is unreliable, use
total flight energy as the primary target"*.

Nhóm em chọn phương án đó, và có lý do cụ thể chứ không phải để cho nhanh.

Để cắt được ranh giới cất cánh, leo, hành trình, hạ, hạ cánh thì cần vị trí và
vận tốc đáng tin. Nhưng cột vị trí ngang ở đơn vị độ và có nhiễu GPS, còn cột
vận tốc thì lệch hai phẩy bốn phần trăm so với vị trí — chính là lỗi thứ ba em sẽ
nói ở phần sau.

Hai cảm biến không đồng ý với nhau thì không cắt pha nhất quán được. Cắt bừa thì
ranh giới sai, và mọi phân tích theo pha sau đó sai theo.

Quyết định này em ghi vào file giao thức, mục `phase_segmentation`, kèm lý do —
để sau này ai đọc cũng biết đây là lựa chọn có cân nhắc, không phải bỏ sót.

## 4.6 — Kết quả

Chạy cho cả 192 chuyến:

| | |
|---|---|
| Trung bình | **21,3 Wh** |
| Nhỏ nhất | 13,0 Wh |
| Lớn nhất | 37,7 Wh |

Con số trung bình tính rất đơn giản: cộng cột `energy_Wh` của 192 dòng rồi chia
192. Thầy mở file bằng Excel dùng hàm `AVERAGE` cũng ra đúng số này.

### Con số 21,3 dùng để làm gì

Nó là **mốc so sánh cho mọi sai số về sau**.

Khi em báo ở D2 rằng mô hình sai không phẩy sáu sáu watt-giờ, thì phải hiểu là
sai trên nền hai mươi mốt phẩy ba — tức khoảng **ba phần trăm**. Không có mốc này
thì con số không phẩy sáu sáu không nói lên điều gì.

Và nó cũng chính là giá trị mà mô hình D0 — mô hình trung bình hằng — luôn dự
báo. D0 là mốc sàn: mô hình nào không hơn được nó thì vô dụng.

# PHẦN 5 — Làm sao biết code đúng

> ▸ Chuyển sang terminal

Em muốn dành một phần cho chuyện này, vì code sai thường **không báo lỗi**. Nó
chạy trơn tru, in ra một bảng đẹp, và con số trong bảng thì sai.

Nhóm em có ba lớp kiểm, mỗi lớp bắt một loại lỗi khác nhau.

## Lớp một — test tự động

> ▸ Gõ `pytest`, chờ kết quả

Năm mươi sáu test cho riêng phần D1. Nguyên tắc là đưa vào dữ liệu đã biết trước
đáp số rồi xem code có ra đúng không.

Ví dụ một ca: công suất một trăm watt giữ nguyên trong một trăm giây thì phải ra
đúng mười nghìn joule. Không cần máy tính cũng biết đáp án.

Một ca khác khó hơn: cho mốc thời gian lệch nhau không đều, nhưng tổng thời gian
đúng mười giây và công suất không đổi năm mươi watt. Kết quả phải ra đúng năm
trăm joule. Nếu code giả định tần số đều thì sẽ ra số khác — test này bắt đúng
lỗi đó.

Trong năm mươi sáu test có mười bốn test đặc biệt. Chúng **không kiểm code**, mà
kiểm chính file giao thức. Lý do là lỗi nguy hiểm nhất ở đây không phải code chạy
sai, mà là ai đó vô tình đưa một biến hậu nghiệm vào tập đặc trưng. Lúc đó code
chạy hoàn hảo, sai số rất đẹp, và toàn bộ kết quả vô giá trị.

Nói cách khác, giao thức đã đóng băng được máy móc canh gác, không phụ thuộc vào
việc có ai nhớ ra hay không.

## Lớp hai — kiểm tái lập

> ▸ Gõ `python3 -m src.features --verify reports/flight_level_week3.csv`

Lệnh này đọc dữ liệu thô từ đầu, dựng lại toàn bộ bảng 192 chuyến, rồi so từng
cột với bảng đã có từ tuần ba.

> ▸ Chờ chạy xong, chỉ vào kết quả

Cả tám cột khớp tới mười mũ trừ tám. Tức là trùng khít, chênh lệch chỉ ở mức sai
số làm tròn của máy tính.

Phép kiểm này chứng minh quy trình là **tất định** — người khác tải bộ dữ liệu
về, chạy script của nhóm em, sẽ ra đúng những con số trong bài.

Nhưng em cũng xin nói rõ nó **không** chứng minh được gì: nó không chứng minh
cách tính đúng về mặt vật lý. Nếu bảng tuần ba đã sai từ đầu thì code tái lập y
hệt cái sai đó. Nên mới cần lớp thứ ba.


### "Làm sao biết 21,3 Wh là hợp lý?"

Hai cách kiểm. Thứ nhất, pin M100 có dung lượng chín mươi chín phẩy chín
watt-giờ, mà chuyến bay dài khoảng ba phút trong khi máy bay treo được hai mươi
hai phút — nên tốn khoảng một phần năm pin là hợp lý. Thứ hai, công suất trung
bình ra bốn trăm lẻ năm watt, hợp lý với một quadrotor cỡ này. Bạn Duy cũng kiểm
chéo hai điểm này.
