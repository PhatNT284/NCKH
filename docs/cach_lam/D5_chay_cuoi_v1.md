# Chạy D5 theo protocol đóng băng v1.0.0

Chạy từ thư mục gốc repo sau khi cập nhật GitHub. Mỗi lần dùng run ID và đường
dẫn gate mới; không ghi đè bằng chứng cũ:

```powershell
git status --short --branch
git fetch origin
git log --oneline HEAD..origin/main
# Nếu có cập nhật: tích hợp và kiểm tra thay đổi trước khi tiếp tục.
.\.venv\Scripts\python.exe -u -m src.d5_final --run-id final_v1_NEW_ID --test-gate reports/d5/test_gates/NEW_ID.json --run-tests
```

`--run-tests` chạy toàn bộ pytest trước thí nghiệm, lưu log, số test và hash mã,
cấu hình/schema. Gate không qua hoặc nguồn bị sửa sau gate thì không chạy.
Runner chỉ chấp nhận protocol **v1.0.0 / frozen / APPROVED**; không sửa protocol.

Thứ tự thực thi: baseline → Monte Carlo đầy đủ → phân tích FLY → OAT → hình OAT
→ matched-reference và counterfactual đầy đủ → replay/workflow → xuất/kiểm
schema 1.0.0 → failure catalogue → bảng đối chiếu lịch sử → hình/báo cáo cuối.
Không tái sử dụng draw từ v0.6.1, không khớp lại D2, không đổi seed hoặc lưới.

Toàn bộ bằng chứng được giữ ở `reports/d5/<run_id>/`, gồm mười file bàn giao,
bốn hình, các bảng chi tiết/nén, snapshot, mã nguồn/cấu hình và manifest từng
bước. Bảng vùng biên có điểm số theo từng w và hai REF; hình chuyển verdict
vùng biên dùng membership riêng của từng REF. Nhánh matched tách nhãn/membership
giữ cố định với nhãn/membership tính lại.

24 snapshot D5 được nhúng nguyên checksum vào đúng schema trao đổi
`schemas/mission_record/1.0.0.json` của D6. Không cộng 12 bản D6 vào số replay D5.
CSV MC lịch sử được chọn theo hash gốc, dùng bản khôi phục đã xác minh khi file
gốc bị làm tròn. Các sai khác được báo theo từng cột, không tự sửa số cho khớp.

Sau khi hoàn tất, runner kiểm hash đầu vào/mã lần nữa, tạo và xác minh
`output_hashes.json`, rồi đặt mọi file/thư mục của run ở thuộc tính chỉ đọc.
Đây là bảo vệ khỏi lưu nhầm, không phải WORM hoặc chữ ký chống sửa đổi.
Không mở CSV bằng Excel rồi lưu lại. `runtime.json` ghi thời gian pipeline và
từng bước, tách khỏi thời gian pytest ở `test_gate.json`.

Runner tạo thêm bản nhỏ tại `reports/d5/published/<run_id>/` để đưa vào Git:
báo cáo, bảng tổng hợp MC, bảng OAT/vùng biên/matched/counterfactual, replay,
schema, bốn hình và hash của bộ đầy đủ. CSV/JSON MC lớn và kho replay vẫn giữ
cục bộ theo `.gitignore`; không xóa chúng để giảm dung lượng khi push.

Protocol đã được Phát duyệt; kết quả lần chạy mới vẫn phải được kiểm tra.
Trạng thái module con có thể giữ chữ DEVELOPMENT/PENDING từ giao diện cũ;
xem trạng thái toàn bộ run ở `run_status.json` và `acceptance_checks.json`.
Không thay metadata của lần chạy cũ để biến nó thành lần chạy cuối.
