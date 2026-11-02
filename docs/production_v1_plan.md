# Production Run v1 plan — phương án B, chưa kích hoạt

EXECUTION_MODE: **HUMAN_APPROVAL_REQUIRED**. Đây là bản chuẩn bị cho báo cáo
draft local, không tuyên bố production-ready. Không có production run được
thực hiện khi tạo các file này. Không mở nguồn hoặc gỡ gate để có opportunities.

## Trigger và window

- Manual là trigger mặc định. Daily cron chỉ là lựa chọn tương lai, chưa cài
  cron/Task Scheduler hay automation. Mỗi lần vẫn phải có người duyệt; cron
  không được tự tạo approval hoặc tái sử dụng approval của run khác.
- Window: 7 ngày tính theo UTC, `[now - 7 days, now]`, áp dụng lên retrieval
  timestamp của response đã lưu. Response tương lai/quá hạn bị loại và ghi GAP.
  Đây là cửa sổ độ tươi dữ liệu, không phải chứng minh trend hoặc story mới.
- Chuỗi T0/T+7/T+14 vẫn là điều kiện riêng của TREND_EVIDENCE; không giả lập
  dữ liệu lịch sử và không đổi ngày retrieval khi replay.

## Chạy offline-first

Config: `config/production_v1.json`. Script: `scripts/run_production.py`.
Phương án B chỉ đọc raw GitHub/HN Algolia đã lưu cùng manifest/ledger, kiểm tra
SHA-256 trước parse, dùng parsers và gate chung. Không gọi live pipeline và không
có fallback network khi cache thiếu/quá hạn/hỏng. Socket cũng bị chặn trong
khâu đọc archive. Một bản config đặt network_enabled=true hoặc option khác B
bị từ chối. Muốn live cần quyết định và implementation riêng sau review.

Output mỗi run nằm ở `artifacts/production-v1/<run-id>/`, thư mục được tạo độc
quyền để không ghi đè. Không tạo output thật trong đợt chuẩn bị này. Giữ nguyên
`artifacts/mvp-v1/` và report lịch sử. Có thể gặp STALE_OR_FUTURE_ARCHIVE nếu
duyệt sau khi cache cũ quá 7 ngày; khi đó xuất draft có GAP thay vì tự refresh.

## Evidence và kill criteria

Áp dụng [evidence criteria](evidence_criteria.md) qua config được pin SHA-256
của tài liệu. Script không diễn giải Markdown bằng LLM hay thực thi chỉ dẫn;
kiểm tra ba nhóm required_evidence trong code, ghi missing proofs vào GAP.
Nếu tài liệu thay đổi phải review, cập nhật config và approval tương ứng.

Giữ nguyên NO_VERIFIED_BUYER_OR_PAYMENT_EVIDENCE và
NO_LONGITUDINAL_TREND_EVIDENCE; giữ kiểm tra tối thiểu 5 GitHub repos/1 HN story
và lỗi ingress. Thêm MISSING_BUYER_EVIDENCE, MISSING_PAYMENT_EVIDENCE,
MISSING_TREND_EVIDENCE khi thiếu proof. Buyer phải xác thực và gắn sản phẩm,
thời điểm; payment có chứng từ kiểm chứng; trend cùng cohort/metric tại các mốc
được định trước. Metadata không được coi là proof; tối đa HYPED, không EMERGING.

Opportunities tối đa 5, chỉ có thể vào Top 5 nếu đủ mọi criteria và được review.
**Ở phương án B chưa có verifier chứng từ hay nhánh qualification**, vì vậy
script giữ opportunities rỗng kể cả khi có các summary booleans present=true.
Ba booleans không đủ thay thế reviewer, ledger, locator và raw proof. Điều này
cố ý chặt hơn chỉ kiểm tra trường bắt buộc, không phải gate được nới lỏng.

## Human approval trước mỗi run

Không có approval hợp lệ được tạo sẵn. Sau khi người dùng duyệt, reviewer tạo
file JSON mới dưới `config/approvals/`, với các trường bắt buộc:

- `approved`: true; `action`: RUN_OFFLINE_DRAFT; `reviewer`: danh tính người duyệt.
- `approved_at`: ISO 8601 có timezone, không ở tương lai và chưa quá 24 giờ.
- `run_id`: ID duy nhất (chữ/số, underscore/hyphen, tối đa 64 ký tự).
- `output_root`: artifacts/production-v1.
- `config_sha256`, `script_sha256`, `criteria_sha256`, `test_report_sha256`,
  `dashboard_sha256`: hash byte các file thực được người duyệt kiểm tra.

Approval là bản ghi local để ngăn chạy nhầm; chưa là chữ ký số hay xác thực
chống người có quyền sửa workspace. Cần ACL/chữ ký/identity verification riêng
trước triển khai nhiều người hoặc unattended production.

Script yêu cầu report offline PASS khớp source/test hiện tại và hash log file;
report còn phải khớp production_bundle_sha256 của script, config, criteria,
dashboard template để không dùng kết quả test cho bundle đã thay đổi.
Report chuẩn bị lưu ở `artifacts/offline-production-prep/`. Các test chỉ chạy
trong thư mục tạm, mô phỏng approval và socket bị chặn; không phải production run.
Không dùng report 42 tests cũ cho source mới.

Lệnh sau chỉ là hướng dẫn sau khi được duyệt, **không chạy trong phiên chuẩn bị**:

```powershell
python scripts/run_production.py --config config/production_v1.json --approval-file config/approvals/REVIEWED-RUN.json --run-id REVIEWED-RUN
```

## Dashboard và audit

Template `dashboard.md` không có kết quả thật: placeholders chưa được render.
Sau một lượt được duyệt, script tạo dashboard Markdown, opportunities.csv
(header-only nếu draft), evidence_ledger.json, run_manifest.json, checkpoint và
ingress.jsonl. Dashboard có số claims/opportunities, verdict distribution,
Top Opportunities và GAP summary. Các nhãn OBSERVED_METADATA/HYPED/EMERGING
không được đồng nhất với trạng thái toàn run RESEARCH_DRAFT_ONLY.

Manifest ghi rõ offline_archive_replay, hash config/criteria/script/test report,
approval, nguồn archive và artifact output. Records giữ timestamp gốc. Replay
không phải bằng chứng live mới hay snapshot độc lập để chứng minh trend.

## Giới hạn còn lại và điểm dừng

Không API trả phí/LLM, không secrets, email, đăng bài, thanh toán hoặc deploy.
Chưa có live fetch trong production script; chưa có hard deadline tổng,
rate-limit liên process, transaction ghi artifact hoặc recovery khi đĩa lỗi.
Không bảo đảm manifest cuối khi filesystem không ghi được. Input hỏng được
ghi GAP và xuất draft nếu storage còn hoạt động; preflight lỗi thì không tạo run.

Sau khi chuẩn bị và tests PASS: dừng để người dùng review. Chưa duyệt manual
run nào, chưa cài daily cron, chưa bật production hay mở domain mới.
