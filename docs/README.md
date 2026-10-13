# Tài liệu giải thích — đọc cái này trước

Thư mục này giải thích **đã làm gì, làm thế nào, và vì sao** cho từng sản phẩm
bàn giao D1–D9. Viết cho người trong nhóm chưa theo dõi quá trình, nên không
giả định bạn đã biết gì về code hay thống kê.

## Đọc theo thứ tự

| File | Nội dung | Ai nên đọc |
|---|---|---|
| `D1_du_lieu.md` | Dựng lại năng lượng từ điện áp và dòng điện, lọc chuyến bay, các lỗi tìm thấy trong bộ dữ liệu | Tất cả. Duy bắt buộc đọc (kiểm chéo WP1) |
| `D2_mo_hinh.md` | So sánh mô hình dự báo năng lượng, ý nghĩa từng con số | Tất cả. Quyền cần đọc phần cuối (ràng buộc cho D3) |
| `thuat_ngu.md` | Giải nghĩa MAE, bias, cross-validation, rò rỉ dữ liệu... | Ai thấy mơ hồ ở hai file trên |

D3–D9 sẽ có file riêng khi làm tới.

## Quy ước tham chiếu

Trong toàn bộ tài liệu và mã nguồn:

- **§x.y** → mục trong `Delivery_UAV_Preflight_Feasibility_Proposal_updated.md`
  (file thầy hướng dẫn gửi sau khi nhận xét)
- **Eq (n)** → công thức đánh số trong `Proposal.docx` (bản nhóm đã sửa)

Mọi quyết định kỹ thuật trong dự án đều phải trỏ được về một trong hai nguồn
trên. Nếu một quyết định không có chỗ dựa, nó phải được khai báo rõ là **bổ
sung ngoài giao thức** — hiện có đúng một trường hợp như vậy, là thí nghiệm
E2c, giải thích trong `D2_mo_hinh.md`.

## Trạng thái hiện tại

| Sản phẩm | Người | Trạng thái |
|---|---|---|
| D1 — Rà soát bộ dữ liệu | Phát | Gần xong. Còn từ điển biến và chữ ký kiểm chéo của Duy |
| D2 — Benchmark dự báo năng lượng | Phát | Kết quả đã có. Còn sai số theo nhóm và hình vẽ |
| D3 — Bộ máy quyết định | Quyền | Chưa bắt đầu. Đọc phần cuối `D2_mo_hinh.md` trước khi làm |
| D4 — Benchmark kịch bản | Quyền | Chưa bắt đầu |
| D5 — Gói độ bền vững | Cả nhóm | Chưa bắt đầu |

## Chạy lại toàn bộ

```bash
source .venv/bin/activate
pytest                                              # 56 test
python3 -m src.features --verify reports/flight_level_week3.csv   # D1
python3 -m src.evaluation_energy                    # D2, khoảng 10–15 phút
python3 -m src.subgroup_analysis                    # D2 sai số theo nhóm, vài giây
python3 -m src.interpretability                     # D2/D3 diễn giải mô hình
python3 -m src.bootstrap_ci                         # khoảng tin cậy, vài giây
python3 -m src.figures                              # 5 hình cho bài
python3 -m src.experiment_log                       # xem nhật ký các lần chạy
```
