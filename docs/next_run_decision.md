# Quyết định lượt nghiên cứu tiếp theo

Trạng thái: CHỜ NGƯỜI DÙNG DUYỆT. Không có network/live run trong đợt sửa P2.
MVP v1 được giữ nguyên: 15 raw records, 8 metadata claims, RESEARCH_DRAFT_ONLY,
0 opportunities. Tiêu chí mới ở [evidence_criteria.md](evidence_criteria.md).

Các con số thời gian dưới đây là ước lượng kế hoạch, không phải kết quả đo.
Không cần dùng model API hoặc API trả phí cho các phương án; không chi từ
ngân sách 5 USD API. Công sức review là chi phí chính, không phải lời hứa API
bên ngoài luôn miễn phí. Không có liên hệ buyer, email, đăng bài hoặc thanh toán.

| Phương án | Cost và thời gian dự kiến | Khả năng tìm payment evidence | Rủi ro và điều kiện |
|---|---|---|---|
| A. Thêm đúng 1 lượt live có mục tiêu | Không dùng paid API/LLM; khoảng 2–4 giờ chuẩn bị adapter/protocol và review, vượt phạm vi đợt offline này nếu cần. Mốc trend tiếp theo phải chờ 7/14 ngày | Thấp trên GitHub/HN; issues/comments thường chỉ là lời tự khai hoặc manh mối | Phải triển khai và test đọc issues/discussions/threads; client/parser hiện tại chỉ hỗ trợ search. Có thể bị giới hạn/không truy cập được. Một lượt mới vẫn chưa cung cấp chuỗi thời gian |
| B. Giữ draft, chỉ sửa P2 và định nghĩa criteria | Không network, không phí API; hoàn thành trong đợt offline hiện tại | Không có bằng chứng payment mới | Chưa xác nhận cơ hội kinh doanh, nhưng không thêm bias từ việc cố chọn nguồn để lấp gate |
| C. Mở rộng nguồn public sau khi duyệt domain | Không dùng paid API; khoảng 0.5–1 ngày cho thiết kế allowlist/adapter/review ban đầu, tùy nguồn. Trend vẫn cần 7/14 ngày | Có thể tốt hơn A nếu có chứng từ/công bố cụ thể; không bảo đảm tìm được | Phải duyệt từng hostname và mục đích trước request. Case study tự khai hoặc pricing page vẫn không đủ payment proof; cần kiểm tra nguồn, entity linkage và dữ liệu nhạy cảm |

## A — Phạm vi đề xuất để duyệt, chưa thực thi

Nghiên cứu một giả thuyết hẹp: người vận hành AI agents có vấn đề về chi phí,
quyền truy cập hoặc sự cố, và có thể có nhu cầu giải pháp kiểm soát. Các title
HN trong MVP v1 chỉ gợi ý hướng tìm; chưa chứng minh sự cố hoặc nhu cầu mua.

Trước khi lấy dữ liệu, khóa protocol: query theo ba chủ đề trên, cửa sổ thời
gian cụ thể, cách sắp xếp, tiêu chí chọn/loại, stable repo/story IDs, dedupe và
quota. Đề xuất quota một lượt: tối đa 8 records GitHub issues/discussions + 7
records HN stories/comments; một comment/issue riêng là một raw item, không
nhét cả thread để né cap. Response envelope dùng audit, không sinh thêm claims
ngoài mẫu. Tối đa 8 claims, tối đa 5 opportunities, có thể là 0.

Chỉ GitHub và hn.algolia.com được duyệt hiện tại; link ngoài là DATA, không tự
fetch. Muốn đọc các endpoint mới trên cùng domain cũng cần adapter được test
offline trước lượt live. Không tự thêm domain news.ycombinator.com vào HTTP
allowlist chỉ vì ledger có URL story. Chưa đủ nguồn thì ghi thiếu và dừng.

Mục tiêu lượt A là xác định buyer/product/pain và đầu mối proof, không ép sinh
Top 5. Đọc nội dung đầy đủ và phản hồi đối chứng; không dựa riêng vào title.
Tạo cohort mới tại T0 nếu query/method thay đổi; T+7/T+14 là những lượt riêng
cần duyệt sau, không được giả lập hoặc tự lên lịch. Gate hiện tại vẫn draft;
cần review riêng nhánh kiểm định thực thi criteria trước khi cho phép qualify.

## B — Khuyến nghị hiện tại

Chọn B ở điểm dừng này. Review diff ba P2, test report mới và evidence criteria.
Giữ nguyên hai kill criteria, không rewrite evidence/manifest v1 để làm lịch
sử đẹp hơn. Báo cáo test mới lưu ở artifacts/offline-p2/; báo cáo cũ được manifest
v1 tham chiếu vẫn ở artifacts/offline_tests.* với lỗi hash đã ghi nhận trong audit.

Các khoảng trống chưa nằm trong ba P2: hard wall-clock deadline, phối hợp
rate-limit nhiều process, xử lý crash/storage failure tổng quát, canonical
identity validation và nhánh qualification. Không suy ra production-ready từ
việc P2 đã pass test. Nếu chọn A sau review, cần duyệt protocol/adapters trước.

## C — Chưa có domain mới được duyệt

Có thể đề xuất nguồn công bố giao dịch/case study chính thức hoặc public filing,
nhưng phải trình hostname, endpoint, proof dự kiến và phạm vi xử lý trước khi
request. Không có URL proof cụ thể nào được xác minh trong đợt này. Không lấy
receipt riêng tư, secrets hoặc screenshot trôi nổi. Buyer ẩn danh vẫn phải có
cách đối chứng công khai/được phép; không cần công khai thông tin nhạy cảm.

## Quyết định cần người dùng chọn

- A: duyệt chuẩn bị protocol và adapters cho đúng một lượt live; chưa tự chạy
  chỉ dựa trên tài liệu này.
- B: giữ draft, kết thúc đợt offline sau tests PASS (khuyến nghị).
- C: duyệt nghiên cứu đề xuất domain mới trước; chưa cấp quyền network đại trà.

Không lựa chọn nào bỏ yêu cầu BUYER + PAYMENT + TREND. Không có bằng chứng thì
tiếp tục RESEARCH_DRAFT_ONLY, opportunities rỗng.
