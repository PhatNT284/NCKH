# Cách làm — mô hình theo §5.2

Thư mục này bám **Mục 5.2** của file thầy (*Energy-demand prediction*), cộng các
mục liên quan: §5.3 (thiết kế chống rò rỉ, thước đo), §4.3 (bảng biến khả dụng),
§8 (phân tích thống kê).

Mỗi file mô tả **một mô hình** trong danh sách §5.2, theo cùng một khuôn:

1. Thầy yêu cầu gì — trích nguyên văn
2. Cài đặt thế nào — tham số, nằm ở đâu trong code
3. Kết quả riêng của mô hình đó
4. Trạng thái

| File | Mô hình §5.2 | MAE |
|---|---|---|
| `D0_trung_binh_hang.md` | Constant-mean baseline | 3,975 |
| `D1_chi_cu_ly.md` | Distance-only baseline (OLS + Huber) | 3,974 / 3,968 |
| `D2_ridge.md` | **Multi-factor Ridge — ĐƯỢC CHỌN** | **0,657** |
| `D3_random_forest.md` | Random Forest Regressor | 1,014 |
| `D5_mo_hinh_vat_ly.md` | **Mô hình vật lý Gong — đang làm, tuần 6** | — |

Bảng **so sánh giữa các mô hình** không nằm ở đây mà ở
`../san_pham/D2_benchmark_nang_luong.md` — so sánh chỉ có nghĩa khi đặt các mô
hình cạnh nhau.

---

## Trạng thái §5.2

| Mô hình | Trạng thái |
|---|---|
| D0, D1, D2, D3 | **Xong** — tuần 4–5 |
| D5 Mô hình vật lý | **Đang làm** — bảng kiểm tương thích đã xong, kết luận: khả thi một phần |
| D4 Gradient boosting | **Bị chặn** — xem dưới |
| Mô hình lai | **Bị chặn** — cùng điều kiện với D4 |

### D4 — vì sao chưa làm

**Không phải quên.** Mục 2.4 của thầy đặt cổng chặn cứng:

> *Gradient-boosted trees, SHAP, nghiên cứu người dùng, bộ dữ liệu ngoài và giao
> diện đẹp đều là tuỳ chọn. **Không được bắt đầu cho tới khi sản phẩm D1–D5 đạt
> tiêu chí nghiệm thu.***

Sản phẩm D3, D4, D5 còn chưa bắt đầu, nên D4 bị chặn. Tab 11 của `NCKH.xlsx` cũng
không xếp tuần nào cho D4 — lịch của thầy nhất quán với quy định của chính thầy.

Dự đoán nếu làm: với 192 dòng và quan hệ gần tuyến tính, nhiều khả năng cũng thua
Ridge như Random Forest đã thua. Giá trị kỳ vọng thấp; thiếu thời gian thì bỏ, đúng
như thầy cho phép.

Khi làm thì phải giữ: cùng mục tiêu, cùng phân vùng, cùng seed như D0–D3; CV lồng
để tinh chỉnh; chạy cả hai biến thể đặc trưng; và không được dùng kết quả D4 để
đổi kết luận đã chốt ở sản phẩm D2.
