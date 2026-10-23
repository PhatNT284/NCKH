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
| `D5_mo_hinh_vat_ly.md` | Mô hình vật lý Gong — **xong, khả thi một phần** | — *(không xếp hạng)* |

Bảng **so sánh giữa các mô hình** không nằm ở đây mà ở
`../san_pham/D2_benchmark_nang_luong.md` — so sánh chỉ có nghĩa khi đặt các mô
hình cạnh nhau.

---

## Trạng thái §5.2

| Mô hình | Trạng thái |
|---|---|
| D0, D1, D2, D3 | **Xong** — tuần 4–5 |
| D5 Mô hình vật lý | **Xong** — tuần 6. Bảng kiểm tương thích đã làm, kết luận **khả thi một phần**: dùng được công suất cảm ứng và hệ số hiệu suất η, không dùng được `P_bl` và `P_par`. Nên **không vào xếp hạng định lượng**, báo cáo như đối chứng tài liệu |
| D4 Gradient boosting | **Bị chặn** — xem dưới |
| Mô hình lai | **Bị chặn** — cùng điều kiện với D4 |

Chi tiết D5: `D5_mo_hinh_vat_ly.md` · mã: `src/physics_m100.py` · bảng kiểm:
`../../reports/d5_hover_validation.csv`

Từ 20/10/2026, `src/physics_m100.py` còn một vai thứ hai: nó cung cấp
`landing_energy_Wh()` cho luật `PH-1` của sản phẩm D3 — tức phần **dùng được**
của mô hình vật lý đã đi vào hệ thống thật, dù mô hình không vào xếp hạng dự báo.
Hai vai đó độc lập: `PH-1` chỉ cần công suất bay treo, không cần `P_bl`/`P_par`.

### D4 — vì sao chưa làm

**Không phải quên.** Mục 2.4 của thầy đặt cổng chặn cứng:

> *Gradient-boosted trees, SHAP, nghiên cứu người dùng, bộ dữ liệu ngoài và giao
> diện đẹp đều là tuỳ chọn. **Không được bắt đầu cho tới khi sản phẩm D1–D5 đạt
> tiêu chí nghiệm thu.***

Tính tới 20/10/2026: **sản phẩm D1, D2, D3 đã nghiệm thu; D4 và D5 chưa bắt đầu.**
Nên mô hình D4 vẫn bị chặn — thiếu hai sản phẩm cuối. Tab 11 của `NCKH.xlsx` cũng
không xếp tuần nào cho mô hình D4, lịch của thầy nhất quán với quy định của chính
thầy.

> Đừng đọc lẫn: **"sản phẩm D4"** (benchmark kịch bản, tuần 8–9, cổng chặn đã mở
> và sắp làm) khác **"mô hình D4"** (gradient boosting, tuỳ chọn, còn bị chặn tới
> khi sản phẩm D5 xong).

Dự đoán nếu làm: với 192 dòng và quan hệ gần tuyến tính, nhiều khả năng cũng thua
Ridge như Random Forest đã thua. Giá trị kỳ vọng thấp; thiếu thời gian thì bỏ, đúng
như thầy cho phép.

Khi làm thì phải giữ: cùng mục tiêu, cùng phân vùng, cùng seed như D0–D3; CV lồng
để tinh chỉnh; chạy cả hai biến thể đặc trưng; và không được dùng kết quả mô hình
D4 để đổi kết luận đã chốt ở sản phẩm D2 — càng không được đổi mô hình mà sản phẩm
D3 đang gọi, vì D3 đã nghiệm thu với `D2_ridge_preflight`.
