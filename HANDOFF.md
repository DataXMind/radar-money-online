# Bàn giao — AI Money-Trend local MVP

Đã làm trực tiếp tại `D:\Projects\radar-money-online` ngày 02/11/2026.
Giữ nguyên LICENSE và commit ban đầu. Không có source pipeline từ remote để
khôi phục: `git ls-remote --heads origin` chỉ trả về `refs/heads/main` tại
`c32e4bc038cebdcca11c3af1db40609af45ada6c`; `git ls-tree -r origin/main --name-only`
chỉ có LICENSE. Lần kiểm tra remote đầu trong sandbox lỗi mạng, lần kiểm tra
chỉ đọc với quyền mạng thành công.

## Đã xác minh

- Python 3.12.10, không dependency ngoài standard library.
- 32 tests offline PASS, 0 failures, 0 errors; socket creation bị chặn.
- Fixture HTML public thật trích được 8 repo; hash response được test đối chiếu.
  JSON cùng rows được kiểm tra ở cả nested route và fallback route; đây là
  phép chuyển cấu trúc trong test, không phải tuyên bố đã capture JSON live.
- Đúng một lượt MVP live lúc 10:01:39–10:01:45 giờ Việt Nam (UTC+7).
  Hai request data thành công: GitHub HTTP 200, HN Algolia HTTP 200.
- Lượt thật giữ 15 raw records (10 GitHub/5 HN), 8 metadata claims,
  **RESEARCH_DRAFT_ONLY**, **0 opportunities**; CSV chỉ có header.
- Dừng vì chưa có verified buyer/payment evidence và longitudinal trend evidence.
  Không ước lượng doanh thu, không bịa URL/payment proof.

## File cần review

`money_trend/core.py` là HTTP client và parsers; `pipeline.py` là orchestration,
gate và artifact writer. `offline_tests.py` chặn socket và lưu report có source
hash. `capture.py` chỉ chuẩn bị public fixture.

`artifacts/mvp-v1/` chứa evidence_ledger.json, opportunities.csv,
AI_MONEY_TREND_BRIEF_v1.md, run_manifest.json, checkpoint và raw HTTP responses
cùng request logs/metadata. Test report ở `artifacts/offline_tests.*`.
Fixture riêng ở `tests/fixtures/public_capture/`, không trộn vào evidence run.
`.gitattributes` giữ nguyên byte artifact để hash tồn tại qua Git checkout.

`code_base_commit` trong manifest là HEAD tại lúc chạy (commit khởi tạo), không
phải commit bàn giao được tạo sau đó. `source_sha256` xác định chính xác source
và tests đã chạy; không sửa source sau live run. Commit bàn giao xem bằng
`git log -1 --format=%H`.

## Giới hạn và điểm dừng

Đây là MVP thu thập bằng chứng có gate, chưa dùng LLM, chưa có nhánh tạo cơ hội
đủ điều kiện. Metadata public không thể tự chứng minh khả năng trả tiền hoặc
tăng trưởng. Không nên coi 8 metadata claims là 8 business claims.

Timeout hiện theo socket và kiểm tra body deadline giữa các lần đọc; chưa là
hard process deadline. Không có auto-resume, scheduler, UI hay production service.
HTTP error được log với status/error; chỉ response thành công mới lưu nguyên body.
Chưa có payment proof adapter, chuỗi thời gian hay corroboration độc lập cho buyer.
Mọi việc tiếp theo cần được người dùng review trước; chưa chạy production.

Không đọc secrets, không dùng danger-full-access, không cài dependencies,
không dùng API trả phí, không push, không đăng bài/gửi email/thanh toán.
Không có blocker còn tồn tại sau khi request public được cấp quyền mạng.
Giữ lại log DNS lỗi của bước fixture để không che giấu lỗi đã gặp.
