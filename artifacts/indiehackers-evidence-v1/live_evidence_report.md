# IndieHackers live evidence v1 — GAP report

Ngày 02/11/2026. **RESEARCH_DRAFT_ONLY**. Thu thập live đã dừng; phần tổng hợp này hoàn toàn offline.

| Metric | Kết quả |
|---|---:|
| HTTP attempts / raw HTTP responses | 3 / 3 |
| RSS/Atom responses parse hợp lệ | 0 |
| Raw economic records giữ lại | 0 |
| Claims | 0 |
| Opportunities | 0 |

## Nguồn và coverage thực tế

Chỉ request hostname `feed.indiehackers.world`. Root trả HTTP 200 HTML và tự nhận
là **unofficial IndieHackers feed**. `/posts.rss` và tham số `q` được tìm thấy
trong chính raw root; query plan được khóa trước request RSS. Không mở liên kết
bài đích, redirect, stylesheet/CDN, IndieHackers chính, Product Hunt hay blog.

Query **AI agent** trả HTTP 500 cả hai lần thử. Hai error HTML được lưu nguyên
byte cùng hash/meta/log; không parse thành RSS hoặc claim. Những query còn lại
**Claude Code, Codex, AI automation, MRR report: NOT_RUN** sau lỗi nguồn bền vững.
Tổng ba attempts gồm root một lần và query hai lần, không phải ba nguồn hay
ba economic records. Nguồn lỗi khác với feed được nhận diện nhưng rỗng.
Không kết luận thị trường không có T2, chỉ chưa quan sát được ở lượt này.

## T2 evaluation và GAP

Không có feed entry để trích/review product, founder, amount, currency và ba kỳ
report. Vì vậy không có T2, không có EMERGING; không tạo record cho đủ target
10–15. Revenue tự khai đạt T2 trong test synthetic chỉ chứng minh policy hoạt
động, không phải evidence live. Không có T1/verified payment được quan sát.
T3 chỉ HYPED; không được dùng lấp transactional Top 5.

T0 MVP lịch sử giữ nguyên; lượt này không đo T+7/T+14 và không thay đổi cohort.
Thiếu longitudinal tiếp tục là GAP, không ngăn T2 riêng theo policy mới.
Không có cơ sở đặt buyer/payment/trend legacy present flags thành true.

GAP codes: SOURCE_UNAVAILABLE_HTTP_500, NO_REVIEWED_T2_REVENUE_HISTORY, MRR_ITEM_TARGET_NOT_MET, QUERY_COVERAGE_INCOMPLETE, NO_VERIFIED_PAYMENT_PROOF_OBSERVED, MVP_T7_T14_NOT_OBSERVED.

## Kiểm tra và giới hạn

Offline suite: **123 PASS**, failures=0, errors=0, socket creation
bị chặn; log SHA-256 được kiểm trên byte file. [Test report](offline-tests/offline_tests.json).
Kiểm hash của cả ba response, đối chiếu request/ingress/meta và frozen protocol;
evaluator test positive/negative T2, RSS/Atom parser, host scope, lỗi HTTP và
empty/error distinction. Không thực hiện model smoke test mới cho role thứ 14;
TOML được parse offline với đúng năm field đã verify. Sáu hook command giữ nguyên.
T2 field normalization vẫn cần human review; merger không xác thực transaction
documents để nhận T1. Chưa production-ready.

`acquisition_checkpoint.json` là checkpoint seed cũ; `terminal_checkpoint.json`
là trạng thái tổng hợp cuối (3 attempts, source stopped). Các checkpoint/log raw
ban đầu giữ nguyên. Config/criteria hiện tại được pin khi tổng hợp; protocol
trước request nằm riêng, không giả rằng config được ghi trước acquisition.

Không gọi API trả phí/token/login. Không có model API call riêng cho fetch/parse;
không có số liệu billing tổng phiên nên không tuyên bố chi phí phiên bằng 0 USD.

## Bước tiếp theo cần duyệt

1. Duyệt một lần kiểm tra lại đúng RSS host sau khi dịch vụ phục hồi, vẫn bounded
   retry/query order và tối đa 15 records. Không tự retry thêm ở phiên này.
2. Hoặc cung cấp/duyệt URL feed public cụ thể cùng hostname để kiểm tra ở lượt mới.
   Blog/company domain và `indiehackers.com` chưa được duyệt; không tự fallback.
3. Nếu có entries, review ít nhất ba actual revenue observations cùng entity,
   cùng metric/currency/cadence với raw field mapping trước EMERGING; T1 cần
   chứng từ và xác minh riêng. Giữ lịch T+7/T+14 của cohort MVP độc lập.

[Ledger](evidence_ledger.json) · [Manifest](run_manifest.json) · [Opportunities](opportunities.csv).
