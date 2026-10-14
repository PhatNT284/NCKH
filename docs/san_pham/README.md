# Sản phẩm bàn giao — theo Mục 12

Thư mục này bám **Mục 12** của file thầy (*Expected deliverables*) và **Mục 12.1**
(bảng tiêu chí nghiệm thu), cộng các mục liên quan: Mục 2.4 (cổng chặn), Mục 10
(phân công WP), Mục 11 (lịch 12 tuần).

| File | Sản phẩm | Người | Trạng thái |
|---|---|---|---|
| `D1_ra_soat_du_lieu.md` | D1 — Dataset audit package | Phát | **Nghiệm thu 14/10/2026** |
| `D2_benchmark_nang_luong.md` | D2 — Energy prediction benchmark | Phát | **Đạt 4/4 — chính thức** |

## Chưa bắt đầu

| Mã | Sản phẩm | Người | Tuần |
|---|---|---|---|
| D3 | Safety-aware decision engine | Quyền | 7 |
| D4 | Scenario benchmark | Quyền | 8–9 |
| D5 | Robustness package | Cả nhóm | 10–11 |
| D6 | Reproducible mission record | Phát | 11 |
| D7 | Prototype (tuỳ chọn) | Phát | 11 |
| D8 | Research paper | Cả nhóm | 12 |
| D9 | Reproducibility package | Cả nhóm | 12 |

Mỗi sản phẩm sẽ có file riêng khi bắt đầu làm.

## Sản phẩm tuần 6

| Việc | Kết quả |
|---|---|
| Kiểm tương thích mô hình vật lý D5 | `docs/cach_lam/D5_mo_hinh_vat_ly.md` |
| Chốt mô hình năng lượng | `reports/model_selection_report.md` |
| Bảng tham số năng lượng khả dụng | `reports/parameter_table.md` |

Cả ba đã xong. Bảng tham số còn một dòng chờ OI-2 (`E_nominal`), nhưng lớp luật
cứng đầy đủ nên Quyền bắt đầu sản phẩm D3 được ngay.

## Cổng chặn đang áp dụng

- ~~Chưa đạt D1 thì không báo điểm mô hình~~ → **đã mở**, Duy xác nhận 14/10/2026
- **Chưa đạt D2 thì không chốt mô hình cho bộ máy quyết định** (tab 11, tuần 6)
- **Chưa đạt D1–D5 thì không làm phần tuỳ chọn** (Mục 2.4) → D4 gradient boosting,
  SHAP, giao diện đẹp đều bị chặn

## Trước khi Quyền bắt đầu sản phẩm D3

Ba việc:

1. **OI-2** — xác nhận pin TB48D (129,96 Wh) hay TB47D (99,9 Wh) từ tài liệu bộ
   dữ liệu, **không được đoán**. Không có con số này thì không tính được
   `E_available = E_nominal × SoC × SoH × κ(T)`
2. Đọc `../../reports/parameter_table.md` — mọi tham số cho `E_available` và lớp
   luật cứng, kèm nguồn
3. Đọc `D2_benchmark_nang_luong.md` **mục 8** — ràng buộc envelope cự ly
   420–610 m, nó quyết định dải cự ly mà bộ sinh kịch bản ở sản phẩm D4 được phép
   lấy mẫu
