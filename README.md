# AI Money-Trend — local research MVP

MVP Python 3.12, chỉ dùng standard library, chạy local và lưu được trong Git.
Đây là công cụ thu thập bằng chứng về chủ đề AI agent; chưa dùng LLM và chưa
đủ khả năng xác nhận cơ hội kinh doanh. **Không production-ready.**

Đã chuẩn bị [Production v1 theo phương án B](docs/production_v1_plan.md),
chưa kích hoạt/chưa chạy. Script `scripts/run_production.py` chỉ replay archive
offline sau approval riêng cho từng run; không tự fetch live hoặc cài cron.
Template dashboard ở `dashboard.md`, config ở `config/production_v1.json`.
Suite cho bản chuẩn bị chạy bằng lệnh sau để giữ report P2 và MVP lịch sử:

```powershell
python -m money_trend.offline_tests --output artifacts/offline-production-prep
```

Đợt sửa P2 offline: [evidence criteria](docs/evidence_criteria.md) và
[phương án tiếp theo](docs/next_run_decision.md). Chưa chạy thêm live.
Chạy suite hiện tại và giữ nguyên báo cáo lịch sử được manifest v1 tham chiếu:

```powershell
python -m money_trend.offline_tests --output artifacts/offline-p2
```

Report mới ở `artifacts/offline-p2/offline_tests.json`. Các số liệu 32 tests và
run bên dưới mô tả phiên MVP v1 đã commit, không phải số tests sau bản sửa P2.
GitHub ingress hiện yêu cầu metadata `errors`, `type`, `result_count` ở route
được chọn: errors rỗng, type repositories, total count >= số rows trên trang;
empty chỉ hợp lệ nếu total count bằng 0. Thiếu/mâu thuẫn metadata là lỗi ingress.
Không đồng nhất total count với số rows một trang. Khi sau này được duyệt live,
phải truyền test report hiện tại bằng `--test-report`; report v1 không khớp source mới.

## Kết quả đã chạy

Ngày 02/11/2026, một lượt MVP thật thu được **10 repo GitHub + 5 HN stories**,
giữ **8 claims quan sát metadata**, và dừng ở **RESEARCH_DRAFT_ONLY** với
**0 opportunities**. Hai nguồn HTTP 200, không có lỗi ingress trong lượt này.
Một snapshot không chứng minh tăng trưởng; stars/points/comments không phải
payment proof. Không có doanh thu hay khả năng trả tiền nào được xác nhận.

- [Evidence ledger](artifacts/mvp-v1/evidence_ledger.json)
- [Opportunities CSV — chỉ có header](artifacts/mvp-v1/opportunities.csv)
- [Brief v1](artifacts/mvp-v1/AI_MONEY_TREND_BRIEF_v1.md)
- [Run manifest và SHA-256](artifacts/mvp-v1/run_manifest.json)
- [Test report](artifacts/offline_tests.json) và [log](artifacts/offline_tests.txt)
- [Bàn giao](HANDOFF.md)

## Chạy offline

Tại thư mục repo, không cần cài package, token, `.env` hay API key:

```powershell
python -m money_trend.offline_tests
```

Suite hiện có 32 tests; runner chặn tạo socket để bảo đảm offline. Có test trích
8 repo từ HTML public thật, test cả JSON/HTML và hai cấu trúc payload, schema
không nhận diện, empty hợp lệ, JSON lỗi, retry, 429, timeout, giới hạn kích thước,
rate-limit, chặn redirect, prompt injection dạng DATA và pipeline fail-closed.
Các payload synthetic chỉ nằm trong test, không được dùng làm bằng chứng run.

## Pipeline local

Entry point là `python -m money_trend.pipeline`. Lệnh mặc định đã chạy đúng một
lần trong phiên triển khai và không ghi đè `artifacts/mvp-v1`. Không cần chạy
lại để review. Sau review, một lượt nghiên cứu mới phải chọn output chưa tồn tại:

```powershell
python -m money_trend.pipeline --output artifacts/new-reviewed-run
```

Pipeline yêu cầu test report PASS có hash source/test hiện tại. Chạy lại test
sẽ cập nhật report; manifest của lượt đã lưu vẫn tham chiếu hash report gốc.
Muốn giữ nguyên chuỗi kiểm chứng của lượt này, review bản Git đã commit.

Nguồn public cố định:

- GitHub repository search: `https://github.com/search?q=ai+agent&type=repositories`
- HN Algolia: `https://hn.algolia.com/api/v1/search?query=ai%20agent&tags=story&hitsPerPage=5`

Giới hạn mỗi lượt: 15 raw records được giữ (10 GitHub, 5 HN), 8 claims, tối đa
5 opportunities. Response envelope nguyên bản được lưu để audit, có thể chứa
metadata phụ của dịch vụ. Không truy cập trang repo, link đích HN hoặc URL do
nội dung nguồn yêu cầu. Không dùng web search, paid API, đăng bài hay gửi tin.

## Ingress và kill criteria

GitHub parser hỗ trợ `payload.blackbirdSearchRoute.results`, fallback
`payload.results`, JSON trực tiếp và script `application/json` trong HTML.
`results: []` là empty hợp lệ; thiếu route/schema hay hàng sai là lỗi, không
được chuyển thành empty. JSON từ chối duplicate keys, NaN/Infinity và số vô hạn.
Repo identity, title và HN counters được kiểm tra kiểu/định dạng trước khi dùng.

Client chỉ GET HTTPS public trên `github.com` và `hn.algolia.com`, không đọc
credentials/proxy từ môi trường, không dùng cookies, từ chối redirect. Mỗi
nguồn tối đa 3 attempts; timeout socket 15 giây, kiểm tra deadline trong vòng
đọc body, tối đa 4 MB/response; cách lần bắt đầu request ít nhất 2 giây.
Retry chỉ cho lỗi mạng, 429 và 500/502/503/504, backoff 2/4 giây; Retry-After
được tôn trọng nếu trong ngân sách 8 giây, nếu dài hơn/HTTP-date thì dừng.
Đây chưa phải hard deadline cho toàn process.

Mỗi request có log bắt đầu/lỗi, checkpoint; response thành công có raw bytes,
timestamp, HTTP status, Content-Type, SHA-256 và ingress log. Validation có
log riêng. Checkpoint là audit record, không tự resume hay phát lại request.
Output directory được tạo độc quyền để tránh ghi đè evidence hoặc chạy lại
âm thầm. `run_manifest.json` hash artifact, source/test, LICENSE và test report;
manifest không tự hash chính nó.

Dừng ngay acquisition khi một nguồn lỗi/không nhận diện. Dừng qualification nếu
thiếu ít nhất 5 repo GitHub, 1 HN story, bằng chứng buyer/payment đã xác minh,
hoặc bằng chứng biến động theo thời gian. Hai search adapter hiện tại **không
cung cấp hai loại bằng chứng cuối**, vì vậy MVP này cố ý chỉ có thể xuất
`RESEARCH_DRAFT_ONLY`, opportunities rỗng. Chưa triển khai nhánh qualification
thành công. Điều này được ghi rõ thay vì suy diễn opportunity từ độ phổ biến.

Source chỉ là DATA: không eval/exec, không shell theo nội dung, không prompt
model hay thực thi chỉ dẫn trong title, description, HTML/JSON. Claims chỉ nói
record xuất hiện trong search hoặc counter HN tại thời điểm retrieval; không
khẳng định nhu cầu, doanh thu, payment hay tăng trưởng.

## Public regression fixture

`tests/fixtures/public_capture/` lưu response thật và metadata. Command chuẩn bị
fixture là `python -m money_trend.capture`, tách biệt khỏi MVP run. Đã có 3
attempts lỗi DNS trong sandbox, sau đó 1 request public thành công khi có quyền
mạng; log giữ nguyên các lỗi. Không cần capture lại để chạy test. Response có
HTML/metadata public do GitHub trả về trong phiên không đăng nhập; không có
credentials cá nhân được đọc hay gửi.

Remote chỉ có `main`, trỏ commit khởi tạo `c32e4bc038cebdcca11c3af1db40609af45ada6c`
với `LICENSE`; MVP được dựng mới, không phục dựng artifact hay test lịch sử.
Giữ nguyên LICENSE gốc. Không push/deploy/production run trong phiên này.
