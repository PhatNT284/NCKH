# D6 — Bản ghi nhiệm vụ có thể tái lập

Căn cứ proposal **§12, D6**: “versioned schema and deterministic replay tests”; chi tiết trường dữ liệu tại **§5.10**, phương pháp kiểm chứng và dung sai tại **E5**. Người thực hiện: **Duy**; kiểm tra chéo: **Phát — PENDING**.

## Sản phẩm

**Đọc trên GitHub:** [Báo cáo D6](published/d6_report.md).
Trên máy có kho lần chạy, mở `validation_20261028_excel_01/mission_records.xlsx`.
Lần chạy này có bước xuất bảng tự động, **12/12 replay khớp,
12/12 kiểm tra đạt, sai lệch lớn nhất 0**. Thư mục lần chạy và Excel giữ cục bộ;
người clone repository tạo bản mới bằng các lệnh bên dưới.

Thư mục D6 được giữ gọn như sau:

- `validation_20261028_excel_01/`: kết quả hiện tại, 12 JSON, Excel và kho `store/` để replay.
- `published/`: bộ bằng chứng bàn giao ngày 27/10, giữ nguyên manifest và kết quả pytest lịch sử.
- `README.md`: hướng dẫn này.

Các lần chạy cũ và file xuất thử đã chuyển vào
`../_archive/d6_cleanup_20261028/`, kèm bản nén dự phòng
`../_archive/d6_cleanup_20261028.zip`. Khi cần replay bộ `published/` cũ,
giải nén `reports/d6/validation_20261027_02/` từ file nén về repository.

| Thành phần | File |
|---|---|
| Lược đồ phiên bản 1.0.0 | [schema](../../schemas/mission_record/1.0.0.json) |
| Kiểm tra, lưu, đọc và replay bản ghi D6 | [mission_schema.py](../../src/mission_schema.py) |
| Snapshot, kho phiên bản, replay và các cổng quy trình kế thừa D5 | [mission_record.py](../../src/mission_record.py) |
| Kiểm thử D6 | [test_mission_schema.py](../../tests/test_mission_schema.py) |
| Kiểm thử replay và bất biến quy trình kế thừa | [test_mission_record.py](../../tests/test_mission_record.py) |
| Tạo bằng chứng D6 | [d6_validation.py](../../src/d6_validation.py) |
| Tự xuất Excel | [d6_export.py](../../src/d6_export.py), [d6_excel.mjs](../../src/d6_excel.mjs) |
| Kiểm thử xuất bảng | [test_d6_export.py](../../tests/test_d6_export.py) |
| Kết quả bàn giao | [báo cáo](published/d6_report.md), [replay](published/replay_results.csv), [kiểm tra](published/checks.json) |

Bộ bàn giao lịch sử `validation_20261027_02`: **12/12 bản ghi** khớp khi lưu/đọc và
replay, **12/12 kiểm tra bổ sung** đạt, chênh lệch số lớn nhất **0**. Bộ pytest:
**108/108 đạt**; [kết quả XML](published/test_results.xml),
[bản ghi mẫu](published/example_record.json), [manifest](published/publication_manifest.json).
Đây là bằng chứng kỹ thuật, chưa có xác nhận nghiệm thu.

## Cấu trúc bản ghi

File xuất có `sha256` của toàn bộ `record`. Bên trong:

- `schema_version`: phiên bản lược đồ D6; khác với phiên bản snapshot D5. Phiên bản chưa hỗ trợ bị từ chối, không tự chuyển đổi.
- `snapshot`: bản đánh giá gốc và checksum; giữ đầu vào, đơn vị, thời gian, thời tiết, năng lượng, biên dự trữ, luật cứng và phán quyết.
- `artifact_manifest`: định danh bằng hash của mã nguồn, mô hình/scaler, cấu hình, dữ liệu nền và phiên bản môi trường đã lưu.
- `assumptions`: nguồn đầu vào nếu có và phần cấu hình pin/nhiệt độ lấy từ **kho lịch sử**.
- `metadata`: quy ước tổng đường bay, định danh phiên bản, thông tin pin và giải thích.
- `workflow`: trạng thái tại `as_of`, lịch sử sự kiện, duyệt, lý do stale, liên kết đánh giá lại và kết cục độc lập.

Không điền dữ liệu giả cho trường chưa có: hướng gió là `null` kèm lý do; đánh giá tất định có `sampled=false`, `seed=null`; độ nhạy riêng bản ghi ghi `NOT_RUN_FOR_THIS_DETERMINISTIC_ASSESSMENT`. Input không hợp lệ vẫn có thể được lưu để kiểm thử đóng an toàn; schema kiểm cấu trúc bản ghi, engine lịch sử kiểm tính hợp lệ đầu vào và chặn FLY.

Lược đồ có các trạng thái của proposal. CLI D6 xuất trạng thái từ đánh giá/sự kiện hiện có; không triển khai thêm các thao tác quản trị cho toàn bộ trạng thái `DRAFT` đến `CLOSED`.

## Chạy

Chạy D6 giờ tự tạo thêm `mission_records.xlsx` (4 trang tổng hợp, đầu vào,
luật kiểm tra và quy trình) trong thư mục lần chạy. Không xuất `mission_records.csv`;
`replay_results.csv` vẫn được giữ làm bảng kiểm chứng replay.
Bảng là bản trích xuất tĩnh; JSON và kho `store/` vẫn dùng cho replay.
Excel được ghi vào manifest hash của lần chạy. Các lần chạy cũ có thể còn CSV tổng hợp;
từ nay không tạo thêm file này. Dữ liệu và kết quả replay không thay đổi.

File chẩn đoán Excel (`*.inspect.ndjson`) chỉ được tạo trong thư mục tạm và
tự dọn sau khi xuất; không đưa vào thư mục kết quả hoặc manifest. Khi thành công,
thư mục lần chạy có đúng 9 mục: `records/`, `store/`, `checks.json`,
`d6_report.md`, `mission_record.schema.json`, `mission_records.xlsx`,
`replay_results.csv`, `replay_results.json`, `validation_manifest.json`.
`run_failure.json` chỉ xuất hiện khi lệnh kiểm chứng bị lỗi.

Bước xuất Excel cần Node.js và gói `@oai/artifact-tool`. Trên máy hiện tại,
chương trình tự tìm runtime đi kèm Codex. Máy khác cần đặt `D6_NODE` đến
Node executable và `D6_ARTIFACT_NODE_MODULES` đến thư mục `node_modules`
chứa gói này. Thiếu runtime/gói sẽ báo lỗi, không âm thầm bỏ qua Excel.

Để chỉ xuất bảng từ một lần chạy cũ, không chạy lại mô hình:

```powershell
.venv\Scripts\python.exe -m src.d6_export --records reports/d6/validation_20261028_excel_01/records --out outputs/d6_export/mission_records.xlsx
```

Lệnh `src.mission_schema export` bên dưới cũng tự xuất `.xlsx`
cùng tên cạnh file JSON. Tất cả lệnh xuất đều từ chối ghi đè file đã có.

Từ thư mục gốc repository, sau khi cài `requirements.txt`:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_mission_schema.py tests/test_mission_record.py tests/test_d6_export.py
.venv\Scripts\python.exe -m src.d6_validation --out reports/d6/validation_20261028_excel_02
```

Lệnh trên tạo lần chạy mới `_02`; chọn tên khác nếu thư mục đã tồn tại.
Không ghi đè kết quả lịch sử.

Ví dụ dùng kho vừa tạo:

```powershell
.venv\Scripts\python.exe -m src.mission_schema export --store reports/d6/validation_20261028_excel_02/store --assessment no_fly --at 2026-10-26T01:03:00+00:00 --out reports/d6/mission_example.json
.venv\Scripts\python.exe -m src.mission_schema validate reports/d6/mission_example.json
.venv\Scripts\python.exe -m src.mission_schema replay reports/d6/mission_example.json --store reports/d6/validation_20261028_excel_02/store
```

`--at` là thời điểm mô phỏng có múi giờ, không phải TTL vận hành mặc định. `validate` chỉ kiểm cấu trúc/checksum/nhất quán metadata; `replay` mới đối chiếu kho lịch sử và tính lại kết quả. Phán quyết phải trùng tuyệt đối; số học dùng atol/rtol của protocol đã lưu (lần này đều 1e-8).

Replay cần cả file xuất và kho `store/`, gồm snapshot liên quan, mã nguồn, mô hình, cấu hình và sự kiện. Có thể chuyển cả thư mục lần chạy sang vị trí khác trong cùng môi trường phiên bản. Thiếu hiện vật, checksum sai hoặc môi trường khác thì báo lỗi, không lấy mô hình mới thay thế. Các sự kiện bổ sung sau khi xuất không làm thay đổi bản ghi đã xuất hoặc phép tính lịch sử; trạng thái `as_of` không đại diện quyền duyệt hiện tại.

## Đối chiếu proposal

| Yêu cầu | Vị trí bằng chứng |
|---|---|
| §12 D6: lược đồ có phiên bản | `schemas/mission_record/1.0.0.json`; kiểm thử từ chối phiên bản lạ |
| §5.10: ID, thời gian, máy bay/pin, đầu vào nhiệm vụ và pin | `snapshot.assessment` và `metadata` |
| §5.10: phiên bản dữ liệu/mô hình/cấu hình/phần mềm | `artifact_manifest`, `metadata.versions` |
| §5.10: năng lượng, biên/ngưỡng, luật, phán quyết | `snapshot.assessment.result` |
| §5.10: bất định, seed, giải thích/độ nhạy | `snapshot.assessment.uncertainty`, `metadata.explanation`; trạng thái chưa chạy ghi rõ |
| §5.10: workflow, stale, duyệt, đánh giá lại, kết cục | `workflow`, bộ test D5 kế thừa |
| §12 D6, §5.10, E5: replay | `replay_results.csv`, kiểm thử dữ liệu bị sửa/thiếu mô hình và thay đổi lịch sử |

Snapshot/replay và các kiểm thử stale/veto/missing/mitigation **cũng là yêu cầu D5 theo §12.1**. D6 kế thừa phần đó, không chuyển trách nhiệm ra khỏi D5. D6 không thêm mô hình năng lượng, huấn luyện, Monte Carlo, UI, database hoặc phân quyền doanh nghiệp.

## Phạm vi chia sẻ và trạng thái

`published/` chứa báo cáo, bảng nhỏ, kết quả pytest và manifest hash. Kho replay đầy đủ trong thư mục lần chạy được giữ cục bộ; bản chia sẻ nhỏ không đủ để replay độc lập. Muốn chạy lại cần kho đầy đủ hoặc tạo lần chạy mới bằng lệnh trên.

Đây là kiểm chứng kỹ thuật trên kịch bản tổng hợp, chưa phải nghiệm thu hoặc chứng minh an toàn bay. Trạng thái kiểm tra chéo vẫn PENDING; kết quả D5 giữ trạng thái riêng.
