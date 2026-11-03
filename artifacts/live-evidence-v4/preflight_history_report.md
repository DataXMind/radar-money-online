# Live evidence v4 — pre-flight retry PASS / RESEARCH_DRAFT_ONLY

**Cập nhật mới nhất — 03/11/2026, 10:23:47 Asia/Saigon:** retry G1 nhận
**HTTP 200**, 1/2 lần tối đa, khi thực thi GET HN ngoài sandbox được duyệt.
DNS trong sandbox timeout; DNS ngoài sandbox resolve được. Dừng chờ review
theo chỉ dẫn cuối prompt retry, dù PASS hay FAIL; chưa chạy full scan hay commit.
Xem [báo cáo retry và chẩn đoán](retry-preflight-20261103/retry_preflight_report.md).

Phần bên dưới giữ kết quả lần chạy ban đầu để bảo toàn lịch sử.

## Lần chạy ban đầu — STOP_G1

Ngày chạy: 03/11/2026, Asia/Saigon. Phạm vi được yêu cầu: HN Show HN trong
30 ngày gần nhất; chỉ hn.algolia.com được phép fetch trước khi duyệt từng
URL sản phẩm. Không chạy full scan vì pre-flight không đạt.

## Kết quả pre-flight

- Thời điểm bắt đầu request: 2026-11-03 10:07:14.867188 +07:00
  (2026-11-03T03:07:14.867188+00:00).
- GET: `https://hn.algolia.com/api/v1/search?tags=show_hn&hitsPerPage=1`.
- Một lần thử, không retry, không theo redirect.
- HTTP status: **không có response** (`null`), không phải HTTP 4xx/5xx.
- Lỗi transport/DNS: `<urlopen error [Errno 11001] getaddrinfo failed>`.
- Request ID: `001_g1_preflight_1_2cf72d2b`.
- Log: [hn/requests.jsonl](hn/requests.jsonl).
- Checkpoint: [hn/checkpoint.json](hn/checkpoint.json).
- Không có response body hay SHA-256 nguồn vì chưa nhận dữ liệu.

Đây là lỗi phân giải DNS trong môi trường thực thi; chưa đủ bằng chứng kết
luận hn.algolia.com ngừng hoạt động. Không đổi công cụ, endpoint hoặc nguồn
để vượt điều kiện dừng G1.

## Gates

| Gate | Trạng thái | Căn cứ |
|---|---|---|
| G1 — Pre-flight HTTP 200 | FAIL / STOP | Không nhận HTTP response; dừng toàn bộ nghiên cứu |
| G2 — >30% HTTP 4xx/5xx | NOT EVALUATED | Không có HTTP response; không tính lỗi DNS thành 4xx/5xx |
| G3 — Ít nhất 5 candidates và ít nhất 5 đạt 70/100 | NOT EVALUATED / GAP | Full scan chưa chạy; không tạo opportunity |
| G4 — >70% budget mà chưa đủ | NOT REACHED | G1 kết thúc lượt trước full scan |
| G5 — Public evidence URL | NOT EVALUATED | Chưa thu được candidate hay source body |

## Output và GAP

- Posts được scan/đánh giá: 0. Candidates: 0. Claims mới: 0.
- Opportunities: 0. Verdict: **RESEARCH_DRAFT_ONLY**.
- Không xuất Top Opportunities; không suy diễn thiếu nhu cầu từ việc chưa
  truy cập được nguồn.
- GAP: cần một lượt pre-flight mới được người dùng cho phép sau khi xử lý
  kết nối/DNS, rồi mới quét, chấm điểm và trình duyệt từng URL sản phẩm.
- Không có URL sản phẩm/pricing/checkout nào được fetch hoặc cần duyệt ở lượt này.

## Trạng thái bàn giao

Theo yêu cầu G1 “Nếu không HTTP 200 → DỪNG toàn bộ, báo cáo”, chỉ lưu log,
checkpoint và báo cáo dừng này. Đã dừng subagent khám phá pipeline.

Chưa sửa `docs/evidence_criteria.md`, chưa triển khai T2.5a/T2.5b, chưa cập
nhật `dashboard.md`, chưa merge/evaluate full scan, chưa commit hoặc push.
Quyết định T2.5a/T2.5b của người dùng vẫn là yêu cầu cho lượt tiếp tục;
không có evidence nào được đánh giá theo tiêu chí mới trong lượt dừng này.

Baseline T0 15 IDs, artifact lịch sử và lịch T+7 ngày 09/11/2026 giữ nguyên.
Không điều tra GH07/GH08, không quét GitHub hay thêm nguồn, không đọc secrets,
không tương tác checkout. Dừng và chờ người dùng review.
