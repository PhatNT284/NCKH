# Mô hình D5 — Mô hình vật lý (Gong et al., 2023)

> Mô hình trong **§5.2**. Đừng nhầm với **sản phẩm D5** (gói độ bền vững) — việc
> của cả nhóm, tuần 10–11.

**Trạng thái: ĐANG LÀM — bảng kiểm tương thích đã xong** · tuần 6 · Phát + Duy

**Kết luận sơ bộ: KHẢ THI MỘT PHẦN.** Dựng được mô hình bay treo và bay thẳng
đứng. **Không** dựng được mô hình Gong đầy đủ vì thiếu tham số khí động của cánh
quạt.

---

## 1. Thầy yêu cầu gì (§5.2)

> *Chỉ triển khai mô hình công suất cho máy bay nhiều cánh quạt đã công bố (ví dụ:
> Gong et al., 2023) **sau khi** đã ghi nhận đầy đủ mọi tham số yêu cầu và xác
> nhận rằng việc tham số hóa là phù hợp với dòng M100. Nếu không thể thu thập một
> tham số bắt buộc một cách đáng tin cậy, **không được tự ý bịa đặt tham số đó**.
> Thay vào đó, hãy báo cáo mô hình như một đối tượng so sánh từ tài liệu tham khảo
> và không đưa vào bảng xếp hạng định lượng.*

## 2. Khác mọi mô hình trước ở điểm nào

D0–D4 đều **học từ dữ liệu**. D5 thì không — nó là **công thức vật lý**, thay tham
số máy bay vào là ra kết quả.

Ưu điểm: giải thích được bằng vật lý, không phụ thuộc dữ liệu huấn luyện, nên về
lý thuyết ngoại suy cự ly tốt hơn — đúng chỗ các mô hình học máy đang yếu nhất
(xem `D2_ridge.md` mục 8).

Nhược điểm: cần biết thông số động cơ và cánh quạt, mà nhà sản xuất thường không
công bố.

Công thức Gong, theo Proposal mục 4.2:

```
P_hover  = P_bl + P_in                        (4)   bay treo
P_level  = P_bl(V) + P_in(V) + P_par(V)       (5)   bay ngang
P_3D     = P_hover + ΔP_ngang + ΔP_dọc        (6)   bay ba chiều
```

- `P_in` — công suất **cảm ứng**, phần tạo lực nâng
- `P_bl` — công suất **hình dạng**, mất vì ma sát cánh quạt
- `P_par` — công suất **ký sinh**, lực cản của thân máy bay

---

## 3. Bảng kiểm tương thích (§3.2)

Tám mục thầy quy định. Nguồn tham số: [trang hỗ trợ chính thức DJI cho Matrice
100](https://www.dji.com/global/downloads/products/matrice100).

| # | Mục | Trạng thái | Giá trị / ghi chú |
|---|---|---|---|
| 1 | Cấu hình động lực và khung máy bay | **Có** | Quadrotor, 4 cánh quạt DJI 1345s, động cơ DJI 3510 |
| 2 | Khối lượng khung, pin, tải | **Có** | 2.355 g (TB47D) hoặc 2.431 g (TB48D); tải 0/250/500 g |
| 3 | **Thông số cánh quạt và động cơ** | **MỘT PHẦN** | Có đường kính 13″ → bán kính 0,1651 m. **Thiếu** chiều rộng cánh, tỉ số đặc, hệ số cản, KV động cơ |
| 4 | Phân biệt tốc độ so với không khí và mặt đất | **Có** | Định nghĩa được; bộ dữ liệu có cả gió lẫn vận tốc |
| 5 | Các pha bay mô hình bao phủ | **Có** | Gong phủ bay treo, bay tiến, lên và xuống thẳng |
| 6 | Cách xử lý gió | **Có** | Gió vào qua vận tốc tương đối khối khí, Eq (5) |
| 7 | Đơn vị mọi đại lượng | **Có** | SI xuyên suốt; mật độ không khí 1,225 kg/m³ |
| 8 | Điều kiện bài gốc đã kiểm chứng | **Có — và đây là vấn đề** | Gong hiệu chỉnh trên **M210**, địa điểm khuất gió, **khối lượng cố định** |

### Mục 3 — chỗ tắc

DJI công bố **mã** cánh quạt (1345s) và động cơ (3510), nhưng không công bố các
tham số khí động mà mô hình Gong cần:

| Tham số thiếu | Dùng để tính | Vì sao không có |
|---|---|---|
| Chiều rộng cánh quạt | `P_bl` công suất hình dạng | DJI không công bố |
| Tỉ số đặc (solidity) | `P_bl` | Cần chiều rộng cánh và số cánh |
| Hệ số cản cánh quạt | `P_bl` | Phải đo trong hầm gió |
| Diện tích cản thân máy bay | `P_par` công suất ký sinh | Phải đo trong hầm gió |
| KV động cơ | hiệu suất truyền động | DJI không công bố |

Từ mã **1345s** chỉ suy ra được đường kính 13 inch và bước 4,5 inch — đủ cho
**bán kính**, không đủ cho phần còn lại.

**Thầy cấm bịa.** Nên `P_bl` và `P_par` không dựng được từ nguồn tài liệu.

### Mục 8 — vấn đề cốt lõi

Gong et al. hiệu chỉnh mô hình trên **DJI M210**, không phải M100. Proposal mục
2.2 còn ghi thêm: thí nghiệm của họ tiến hành ở **địa điểm khuất gió**, và **khối
lượng máy bay giữ không đổi nên biến thiên tải trọng chưa bao giờ được thử**.

Mà tải trọng lại là một trong ba đặc trưng quan trọng nhất của bộ dữ liệu này.

---

## 4. Phần LÀM ĐƯỢC: công suất cảm ứng và hệ số hiệu suất

Dù thiếu tham số cho mô hình Gong đầy đủ, phần **công suất cảm ứng** vẫn dựng được
từ lý thuyết động lượng, vì nó chỉ cần **diện tích đĩa quay** — tính từ bán kính
cánh quạt, mà bán kính thì có.

```
P_lý_tưởng = T^1.5 / √(2 · ρ · A)        với T = m · g
```

| Đại lượng | Giá trị | Nguồn |
|---|---|---|
| Bán kính cánh quạt | 0,1651 m | từ mã 1345s (13″) |
| Số cánh quạt | 4 | DJI |
| **Tổng diện tích đĩa A** | **0,34253 m²** | tính ra |
| Mật độ không khí ρ | 1,225 kg/m³ | khí quyển chuẩn |

### Khớp hệ số hiệu suất η

`P_lý_tưởng` là công suất **khí động** lý tưởng. Công suất **điện** rút từ pin cao
hơn nhiều vì tổn hao cánh quạt, động cơ, bộ điều tốc và mạch điện. Hệ số η gộp
toàn bộ phần đó.

Khớp η từ **đúng một điểm**: thời lượng bay treo không tải DJI công bố. Để các trị
số còn lại vẫn là kiểm chứng độc lập.

### Kết quả kiểm chéo

Chạy bằng `python3 -m src.physics_m100`:

| Pin | Tải (g) | η | Dự báo (phút) | DJI công bố | Lệch | |
|---|---|---|---|---|---|---|
| TB47D | 0 | 0,4449 | 22,00 | 22 | — | dùng để khớp |
| TB47D | 500 | 0,4449 | 16,48 | 17 | 3,0 % | **kiểm chéo** |
| TB47D | 1000 | 0,4449 | 12,94 | 13 | 0,5 % | **kiểm chéo** |
| TB48D | 0 | 0,4565 | 28,00 | 28 | — | dùng để khớp |
| TB48D | 500 | 0,4565 | 21,15 | 20 | 5,8 % | **kiểm chéo** |
| TB48D | 1000 | 0,4565 | 16,70 | 16 | 4,4 % | **kiểm chéo** |

**Sai lệch trên 4 trị số không dùng để khớp: trung bình 3,4 %, lớn nhất 5,8 %.**

Hai điều đáng chú ý:

1. **Mô hình nắm đúng ảnh hưởng của tải trọng.** Chỉ khớp một hằng số duy nhất ở
   điểm không tải, mà dự báo được cả quan hệ tải–thời lượng trong vòng 6 %.
2. **η của hai cấu hình pin chênh nhau chỉ 2,6 %** (0,4449 so với 0,4565) — hai
   phép khớp độc lập cho gần như cùng một giá trị, củng cố rằng con số có ý nghĩa
   vật lý chứ không phải tham số tuỳ chỉnh.

η ≈ 0,45 cũng hợp lý với một quadrotor cỡ này: khoảng 45 % năng lượng điện thành
công suất khí động hữu ích.

---

## 5. Kết luận — khả thi một phần

| Thành phần | Dựng được? | Lý do |
|---|---|---|
| `P_in` công suất cảm ứng | **Được** | Chỉ cần diện tích đĩa quay |
| Hệ số hiệu suất η | **Được** | Khớp từ dữ liệu DJI công bố, kiểm chéo 4 điểm |
| `P_bl` công suất hình dạng | **Không** | Thiếu tỉ số đặc và hệ số cản |
| `P_par` công suất ký sinh | **Không** | Thiếu diện tích cản thân máy bay |
| Mô hình bay treo / thẳng đứng | **Được** | Chủ yếu là công suất cảm ứng |
| Mô hình Gong 3D đầy đủ, Eq (6) | **Không** | Thiếu hai thành phần trên |

### Hệ quả theo đúng quy định §5.2

Vì không dựng được mô hình Gong đầy đủ, **D5 không vào bảng xếp hạng định lượng**
cùng D0–D3. Thầy ghi rõ: báo cáo như đối chứng tài liệu.

**Đây không phải thất bại.** Nó trả lời một câu hỏi thật và có giá trị cho bài:

> *Mô hình công suất vật lý đã công bố có áp dụng được sang một nền tảng UAV khác
> chỉ bằng thông tin nhà sản xuất công khai hay không?*

Trả lời: **một phần**. Thành phần cảm ứng chuyển được và kiểm chứng được trong
vòng 6 %. Thành phần hình dạng và ký sinh thì không, vì cần tham số khí động chỉ
đo được trong hầm gió.

Đây là một đóng góp cho phần hạn chế, và là lý do có cơ sở để đề tài dùng mô hình
thực nghiệm thay vì mô hình vật lý.

### Nếu muốn đưa vào so sánh định lượng

Hai cách, đều phải khai báo rõ:

1. **Mô hình rút gọn** — chỉ công suất cảm ứng cộng η, bỏ `P_bl` và `P_par`. Dán
   nhãn **"adapted"**, không được gọi là tái lập Gong. Sẽ dự báo **thiếu** vì bỏ
   hai thành phần tổn hao.
2. **Lấy tham số từ cánh quạt tương đương** đã có số liệu công bố. Rủi ro cao,
   phải nêu rõ là thay thế và kiểm độ nhạy.

Khuyến nghị: chọn cách 1, và chỉ sau khi sản phẩm D1–D5 xong.

---

## 6. Hai việc tồn đọng được giải quyết nhờ mục này

**OI-3 — khối lượng khung M100: XONG.**

| Cấu hình | Khối lượng máy bay | Tải trọng tối đa |
|---|---|---|
| Với TB47D | 2.355 g | 3.600 − 2.355 = **1.245 g** |
| Với TB48D | 2.431 g | 3.600 − 2.431 = **1.169 g** |

Bộ dữ liệu CMU chỉ bay tới 500 g — nằm gọn trong giới hạn, cả hai cấu hình.

Con số này đi thẳng vào lớp luật cứng của sản phẩm D3: *tải trọng vượt giới hạn
tài liệu → NO-FLY*.

**OI-2 — pin nào: VẪN TREO.**

| | TB47D | TB48D |
|---|---|---|
| Năng lượng danh định | 99,9 Wh | 129,96 Wh |
| Khối lượng máy bay | 2.355 g | 2.431 g |

Lệch **30 %** về năng lượng. Ảnh hưởng thẳng tới `E_available = E_nominal × SoC ×
SoH × κ(T)`, tức mọi phán quyết ở sản phẩm D3.

Proposal mục 4.4 yêu cầu **xác nhận từ tài liệu bộ dữ liệu, không được đoán**.
Việc của Quyền.

Gợi ý chỗ tra: bài Rodrigues et al. (2021) phần mô tả thiết bị, hoặc tệp README đi
kèm bộ dữ liệu trên KiltHub.

---

## 7. Cảnh báo về Draft Báo.docx

`Draft Báo.docx` đã có một đoạn triển khai Gong, nhưng dựa trên **M210**:

- `E_nominal = 349,2 Wh` — đó là hai pin TB55 của Matrice 210
- Hệ số η khớp theo thời lượng bay treo **33 phút** của M210
- Kiểm chéo bằng tải tối đa **1,23 kg** của M210

Toàn bộ phần đó **không dùng được cho M100** và phải viết lại bằng các con số ở
mục 4 trên. Đã ghi vào `configs/d2_protocol.yaml`, mã **OI-5**.

Điểm tích cực: **phương pháp thì đúng** — khớp η từ thời lượng bay treo công bố
rồi kiểm chéo bằng một trị số không dùng để khớp. Mục 4 ở trên làm đúng cách đó,
chỉ thay số M100, và còn chặt hơn vì kiểm chéo được **4** trị số thay vì 1.

---

## 8. Nguồn

- [DJI — trang hỗ trợ chính thức Matrice 100](https://www.dji.com/global/downloads/products/matrice100)
  — khối lượng, dung lượng pin, thời lượng bay treo, mã cánh quạt và động cơ
- Gong, H., Huang, B., Jia, B., Dai, H. "Modeling Power Consumptions for Multirotor
  UAVs." *IEEE TAES*, 59(6), 2023. [DOI 10.1109/TAES.2023.3288846](https://doi.org/10.1109/TAES.2023.3288846)
- Mã tái lập: `src/physics_m100.py` · kết quả: `reports/d5_hover_validation.csv`
