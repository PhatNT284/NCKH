# Giải thích các sản phẩm bàn giao

> **Đây KHÔNG phải sản phẩm bàn giao.** Sản phẩm thật nằm ở `reports/`, `src/`,
> `configs/` và `data/` — xem bảng tra **`reports/deliverables.md`**.
>
> Thư mục này là bài giải thích cho người trong nhóm: đã làm gì, làm thế nào, vì
> sao. Thầy không yêu cầu nó.

Thư mục này bám **Mục 12** của file thầy (*Expected deliverables*) và **Mục 12.1**
(bảng tiêu chí nghiệm thu), cộng các mục liên quan: Mục 2.4 (cổng chặn), Mục 10
(phân công WP), Mục 11 (lịch 12 tuần).

**Cập nhật 23/10/2026.**

## Đã xong

| File | Sản phẩm | Người | Trạng thái |
|---|---|---|---|
| `D1_ra_soat_du_lieu.md` | D1 — Dataset audit package | Phát | **Nghiệm thu 14/10/2026** — 8/8 |
| `D2_benchmark_nang_luong.md` | D2 — Energy prediction benchmark | Phát | **Nghiệm thu 14/10/2026** — 4/4 |
| `D3_bo_may_quyet_dinh.md` | D3 — Safety-aware decision engine | Phát | **Nghiệm thu 20/10/2026** — 13/13, Duy ký kiểm chéo |
| `D4_benchmark_kich_ban.md` | D4 — Scenario benchmark | Phát | **Xong 23/10/2026** — 6/6, Duy ký nhãn tham chiếu 21/10 |

## Chưa bắt đầu

| Mã | Sản phẩm | Người | Tuần | Ghi chú |
|---|---|---|---|---|
| **D5** | Gói độ bền vững | **Duy** | 10–11 | **sản phẩm CỐT LÕI thứ năm** — xem cảnh báo dưới |
| D6 | Bản ghi nhiệm vụ tái lập được | Duy | 11 | ngoài năm sản phẩm cốt lõi |
| D7 | Prototype | Duy | 11 | **tuỳ chọn** — Mục 12.1 ghi rõ không bắt buộc |
| D8 | Research paper | Cả nhóm | 12 | |
| D9 | Reproducibility package | Cả nhóm | 12 | |

> **Bàn giao 23/10/2026.** Phát bàn giao D5–D7 cho Duy. Theo Mục 10, **Phát trở
> thành người kiểm chéo** cho ba sản phẩm này — nguyên tắc *"người làm một phần
> không được là người duy nhất kiểm kết quả phần đó"* vẫn được giữ, chỉ đổi vai.

## CẢNH BÁO về D5 — tiêu chí Mục 12.1 lớn hơn Mục 12 rất nhiều

Đây là chỗ dễ làm thiếu nhất của cả đề tài, nên đọc kỹ.

**Mục 12** chỉ ghi một dòng: *"boundary analysis, threshold sweeps,
uncertainty/sensitivity plots, and failure-case examples"*.

**Mục 12.1** đòi **bảy** thứ:

> *Reserve-threshold sweep; boundary-case analysis; uncertainty/sensitivity tests;
> at least one failure-case catalogue; **replayable immutable assessment
> snapshots**; **tests for stale inputs, hard-rule veto, missing data, and
> conditional-mitigation requirements**; repeatable plots and result tables*

Hai thứ in đậm **vốn bị tưởng là của D6**. Chúng thuộc D5.

Và **Definition of done** của thầy: *"the core study is complete when **D1–D5**
are reproducible from saved scripts/configurations"*. Nghĩa là **D5 là sản phẩm
cuối cùng khoá lại phần cốt lõi** — D6 và D7 nằm ngoài. Thầy còn ghi thẳng:
*"A user interface, SHAP analysis, gradient-boosted model, and human study are
**not required** for this definition of done."*

### Tin tốt: phần lớn D5 đã có sẵn

| Mục 12.1 đòi | Đã có ở đâu | Còn phải làm |
|---|---|---|
| Reserve-threshold sweep | `reports/d4_tradeoff_curve.csv` — quét hai trục | gói lại + vẽ hình |
| Boundary-case analysis | `reports/d4_boundary_breakdown.csv` — 1 077 kịch bản | phân tích, chưa chỉ liệt kê |
| Uncertainty/sensitivity tests | `reports/d4_sensitivity_runs.csv` — S-1…S-4 | **thiếu truyền bất định từ phần dư** |
| ≥ 1 failure-case catalogue | `reports/d4_b5_rejection_causes.csv` | gom thành danh mục có mô tả |
| Replayable immutable snapshots | `src/workflow_state.py` → `MissionRecord`, INV-5 đạt 192/192 | mở rộng + test bất biến hoá |
| Tests: stale, veto, missing, mitigation | INV-1…INV-8, `tests/test_safety_invariants.py` | **đã có đủ** — chỉ cần đối chiếu từng chữ |
| Repeatable plots and tables | `src/figures.py` | thêm hình cho D5 |

Việc **mới** thật sự chỉ còn ba cái:

1. **`src/uncertainty.py`** — Mục 9 của thầy gọi tên file này, repo chưa có.
   Nội dung: truyền bất định dựa trên phần dư (`reports/d2_oof_residuals.csv`,
   §5.8) và kiểm độ nhạy.
2. **Danh mục trường hợp thất bại** — có mô tả, không chỉ là bảng số.
3. **Snapshot bất biến hoá + test replay** đầy đủ.

### Ba việc D4 để lại cho D5

| Mã | Việc |
|---|---|
| **S-1** | Độ nhạy S-1 cho thấy đổi pin TB47D → TB48D làm M-2 của B5-noHR tăng **70 lần**. `E_nominal` phải được quét **như một biến bất định**, không phải chọn một giá trị rồi im. Đây là việc trung tâm của D5. |
| **OI-D4-7** | S-4 chưa kiểm được vai trò của bề rộng vùng biên `w` trong bảng M-3. Phải quét `d4_boundary_breakdown.csv` theo `w`. |
| **S-3** | Ưu thế của bậc giữa chỉ đo được trên vùng `marginal`. D5 nên phân tích riêng vùng này. |

## Cổng chặn đang áp dụng

- ~~Chưa đạt D1 thì không báo điểm mô hình~~ → **đã mở** 14/10
- ~~Chưa đạt D2 thì không chốt mô hình cho bộ máy quyết định~~ → **đã mở** 14/10
- ~~Chưa pass unit test và rule test thì không chạy benchmark quyết định~~ → **đã mở**
- ~~Chưa đạt D1–D4 thì không chạy phân tích vùng biên~~ (tuần 10) → **đã mở** 23/10
- **Chưa đạt D1–D5 thì không làm phần tuỳ chọn** (Mục 2.4) → gradient boosting,
  SHAP, giao diện đẹp vẫn **bị chặn**. D7 chỉ làm sau khi D5 nghiệm thu.
- **Cổng chặn riêng của D5:** *"Only after D1–D4 pass may optional features be
  considered"* — đã qua.

## Trước khi Duy bắt đầu D5

Bốn việc, theo thứ tự:

1. Đọc `reports/deliverables.md` — mục **D5**, bảng nguyên liệu đã có
2. Đọc `D4_benchmark_kich_ban.md` **mục 4 và mục 6** — hai cảnh báo bắt buộc và
   kết quả bốn phép quét độ nhạy. Đây là nền của D5
3. Đọc `D3_bo_may_quyet_dinh.md` **mục 7** — dấu còn hạn và `MissionRecord`, vì
   Mục 12.1 của D5 đòi snapshot bất biến hoá
4. Đọc `D2_benchmark_nang_luong.md` **mục 8** — envelope cự ly 420–610 m, và
   `reports/d2_oof_residuals.csv`, nguyên liệu cho truyền bất định

**Không cần làm gì với OI-2 nữa** — câu hỏi pin TB47D/TB48D đã đóng: lấy TB47D
99,9 Wh làm mặc định và TB48D 129,96 Wh làm độ nhạy bắt buộc S-1 (P§4.4). Nhưng
S-1 cho thấy lựa chọn này **ảnh hưởng lớn**, nên D5 phải quét nó như biến.
