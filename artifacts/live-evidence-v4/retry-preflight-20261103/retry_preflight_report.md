# Retry pre-flight — G1 PASS, dừng chờ review

Kết quả lúc **10:23:47 ngày 03/11/2026 (Asia/Saigon)**: GET
`https://hn.algolia.com/api/v1/search?tags=show_hn&hitsPerPage=1` nhận **HTTP 200**.
JSON hợp lệ, trả về 1 hit phục vụ pre-flight; chưa đánh giá hit thành candidate.

Lượt retry dùng **1/2 lần pre-flight tối đa**. Không cần lần 2 hoặc chờ 60 giây
vì lần 1 đã PASS. Không retry tự động, không theo redirect.

## Chẩn đoán mạng

| Kiểm tra | Môi trường | Kết quả |
|---|---|---|
| `nslookup hn.algolia.com` | Sandbox | Resolver `127.0.0.1`, timeout, không resolve được; exit code 0 không đồng nghĩa DNS thành công |
| `ping -n 1 -w 2000 hn.algolia.com` | Sandbox | Không tìm thấy host, exit 1; chưa gửi ICMP được tới đích |
| GET `https://api.github.com` để đối chứng | Sandbox | DNS `Errno 11001`, không HTTP response; không quét GitHub |
| `nslookup hn.algolia.com` | Thực thi ngoài sandbox được duyệt | Resolver `8.8.8.8`, trả IP `34.160.168.181` |
| GET pre-flight HN | Thực thi ngoài sandbox được duyệt | HTTP 200, JSON hợp lệ |

Kết quả cho thấy khả năng resolve DNS khác nhau giữa hai môi trường thực thi.
HN truy cập được bằng HTTPS trong môi trường được duyệt tại thời điểm test;
không có căn cứ gọi nguồn chết. Không đổi DNS, VPN, cấu hình mạng hoặc nguồn.

Bộ kiểm duyệt tự động đã từ chối một lệnh gộp GET đối chứng GitHub và HN trước
khi thực thi, do áp dụng lệnh cấm GitHub trước đó. Đã bỏ phần GitHub và chạy
riêng HN được duyệt. GET đối chứng GitHub ngoài sandbox **chưa thực hiện**;
không tính lệnh bị từ chối là lần pre-flight hay HTTP request đã chạy.

## Provenance

- [Kết quả pre-flight](preflight_results.json).
- [Chẩn đoán DNS/ping và trạng thái kiểm duyệt](network_diagnostics.json).
- [Request log HN](hn/requests.jsonl).
- [Raw HTTP response HN](hn/001_preflight_1_1_d237473a.body).
- [HTTP metadata HN](hn/001_preflight_1_1_d237473a.meta.json).
- SHA-256 raw HN: `7e4322f9c67ebde894fcac17ab65e70ece64e3daedf454fd889c5c3a9ca23566`.
- Retrieval UTC: `2026-11-03T03:23:47.881548+00:00`.
- [Log GET đối chứng trong sandbox](control/requests.jsonl).

## Gates và bàn giao

- G1: **PASS**, 1 HTTP response / 1 HN pre-flight trong lượt retry.
- G2: 0 HTTP 4xx/5xx trong 1 HN request; lỗi DNS đối chứng có status null,
  không đếm là 4xx/5xx. Chưa chạy full-scan error-rate gate.
- G3/G5: chưa đánh giá vì chưa scan candidates.
- G4: lượt retry kết thúc trước ngưỡng thời gian 70% của 15 phút; không có
  dữ liệu billing model để xác nhận mức dùng ngân sách USD/token.

Prompt vừa yêu cầu tiếp tục khi PASS, vừa kết thúc bằng “DỪNG và chờ tôi review
sau khi có kết quả pre-flight (dù PASS hay FAIL)”. Áp dụng chỉ dẫn dừng cuối
prompt: **không chạy full scan sau khi PASS trong lượt này**.

Posts được scan/đánh giá: 0; candidates: 0; claims mới: 0; opportunities: 0.
Discovery verdict vẫn **RESEARCH_DRAFT_ONLY** vì chưa chạy nghiên cứu, không
phải vì đã tìm mà không có sản phẩm đạt tiêu chí.

Chưa fetch URL sản phẩm/pricing/checkout, chưa sửa criteria/dashboard, chưa
commit/push. Giữ nguyên T0 15 IDs, artifact cũ, lịch T+7 ngày 09/11/2026.
Không deep-dive GH07/GH08, không thêm nguồn và không đọc secrets.
