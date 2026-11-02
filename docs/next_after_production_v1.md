# Quyết định sau Production Run v1

Chỉ là đề xuất để duyệt; không phương án nào tự tạo live run, cron hay domain
mới. Baseline dùng phương án B đã triển khai: offline replay GitHub + HN Algolia.
Đây là kiểm chứng luồng chạy/approval/artifact, không phải evidence live mới.
Kết quả cụ thể và GAP xem artifacts/production-v1/production_run_report.md.

Ước lượng dưới đây là kế hoạch, không phải số liệu chi phí/khả năng thành công
đã đo. Không dùng paid model/API trong baseline này; ngân sách 5 USD không tự
được hiểu là quyền mua dịch vụ hoặc thực hiện giao dịch. Không có tỷ lệ thành
công phần trăm đủ cơ sở để công bố.

| Phương án | Cost | Thời gian dự kiến | Khả năng thành công | Rủi ro / điều kiện |
|---|---|---|---|---|
| A. Duyệt một live run có mục tiêu tìm proof | Có thể dùng public GET, không cần LLM/paid API; công sức adapter và review là chính | Khoảng 2–4 giờ chuẩn bị, test, chạy và review; trend cần các mốc T+7/T+14 riêng | Thu được manh mối buyer/pain: khả thi; payment proof đủ kiểm chứng trên GitHub/HN: thấp, không bảo đảm | Search metadata không đủ. Cần adapter issues/discussions/threads, protocol/quota khóa trước request. Không đổi option B thành live bằng cách nới gate |
| B. Mở rộng nguồn public có kiểm soát | Chưa có phí API được duyệt; không mua chứng từ, không thanh toán | Khoảng 0.5–1 ngày thiết kế allowlist/adapter/proof review, tùy nguồn | Có thể tìm được proof tốt hơn nếu nguồn gắn buyer/sản phẩm/thời điểm; chưa có nguồn cụ thể được xác minh | Phải trình từng hostname/endpoint và xin duyệt trước. Pricing, ARR tự khai hoặc case study không có đối chứng vẫn không đủ payment proof |
| C. Giữ draft, tối ưu pipeline offline | Không network/paid API; chỉ công sức kỹ thuật | Khoảng 2–4 giờ cho một nhóm cải tiến nhỏ có tests | Cao đối với cải thiện độ tin cậy; không tạo thêm payment/trend evidence | Tránh tối ưu thay cho nghiên cứu thị trường; tiếp tục giữ opportunities rỗng nếu thiếu proof |

## A — Nếu được duyệt sau baseline

Chọn một phân khúc/problem hẹp (ví dụ kiểm soát chi phí/quyền của agent), xem
các title cũ chỉ là đầu mối. Khóa query, thời gian, stable cohort, thứ tự chọn,
dedupe và quota trước khi lấy dữ liệu. Giữ 15 raw items, 8 claims, tối đa 5
opportunities; không buộc phải có opportunity. Một issue/comment là một record,
không gộp cả thread để né cap.

Thu thập raw, SHA-256, locator, URL nguồn và phân biệt created_at/updated_at với
retrieved_at. Tìm buyer identity, product mapping, receipt/invoice/contract/public
filing có thể kiểm chứng; không gọi invoice chưa paid là tiền đã thu. T0 phải
là snapshot của protocol/cohort mới, không phải thời điểm replay archive.
T+7/T+14 là các lượt riêng cần duyệt, không được giả lập hay tự lên lịch.

## B — Cần duyệt domain mới

Trình tên miền, endpoint, tài liệu dự kiến, lý do cần nguồn và giới hạn xử lý.
Chưa có URL payment proof nào được xác minh qua baseline. Web search là một
năng lực bổ sung cần adapter/provenance/quota rõ ràng; chưa có trong script
hiện tại và không được tự gọi để coi đủ "nguồn thứ ba". Không đọc secrets,
không liên hệ khách hàng, gửi email hay thu thập tài liệu riêng tư ngoài phạm vi.

## C — Khuyến nghị hiện tại

Giữ draft và review artifact baseline trước. Nhóm cải tiến ưu tiên: verifier
claim-to-raw theo field/locator thay vì chỉ hash; transaction/finalization khi
storage lỗi; kiểm tra canonical IDs; chuẩn bị adapter và protocol live có thể
duyệt riêng. Hard deadline và rate-limit liên process vẫn cần trước unattended
live. Không bật cron chỉ vì một manual replay thành công.

BUYER + PAYMENT + TREND vẫn là ba điều kiện cần; cần reviewer, phản chứng và
nhánh qualification được duyệt trước khi EMERGING/Top 5 được phép. Giữ hai kill
criteria cũ, không đổi stars/points thành proof. Chờ người dùng chọn A/B/C;
không tự thực hiện phương án tiếp theo.
