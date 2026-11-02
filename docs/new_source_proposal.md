# Đề xuất nguồn bổ sung — chờ duyệt domain

Ngày lập: 02/11/2026. Trạng thái: **PROPOSAL ONLY — CHƯA ĐƯỢC DUYỆT / CHƯA FETCH**.
Phiên này chỉ tạo tài liệu; không sửa allowlist, viết adapter, gọi nguồn mới,
đọc credentials hay chạy live. Commit/push Git là thao tác phân phối được yêu cầu.

Ba nhóm dưới đây là nguồn tìm **manh mối có thể dẫn tới proof**, không phải
nguồn transactional đã được xác minh. Mức Trung bình/Cao trong đề bài là giả
thuyết ưu tiên nghiên cứu, chưa phải xác suất đo được. Không có đủ dữ liệu để
gán tỷ lệ phần trăm hoặc kết luận đổi nguồn sẽ giải quyết payment gate.

## Quy tắc bằng chứng giữ nguyên

Theo [evidence criteria](evidence_criteria.md):

- BUYER: danh tính hoặc mã ẩn danh có cách xác thực, sản phẩm cụ thể, thời điểm,
  và xác nhận có nguồn. Maker không tự động là buyer; reviewer không tự động là
  khách đã trả tiền. Testimonial chỉ đủ khi thỏa các trường và được kiểm chứng.
- PAYMENT: receipt/invoice/contract/public filing gắn được buyer + sản phẩm +
  thời điểm, có provenance và review. Invoice phát hành hoặc hợp đồng ký chưa
  tự chứng minh tiền thực thu. ARR/MRR tự khai, milestone, screenshot không nguồn,
  pricing page, lượt vote và bình luận không phải verified payment proof.
- TREND: cùng cohort, metric, phương pháp và các mốc thực T0/T+7 hoặc T+14.
  Chuỗi revenue milestone khác định nghĩa/kỳ đo không thay thế series tương thích.

Một bài viết được đăng trên nền tảng khác vẫn có thể là cùng lời tự khai của
maker; không đếm thành đối chứng độc lập. Thiếu một trong ba loại thì không
vào Top 5. Chỉ có metadata thì tối đa HYPED, không EMERGING; có thể tiếp tục
RESEARCH_DRAFT_ONLY và 0 opportunities sau khi đã duyệt nguồn.

## So sánh đề xuất

Các mức cost dưới đây là **ước lượng cho một pilot tương lai tối đa 15 raw
records, 8 claims**, không phải lượt chạy đã thực hiện. Token là dự trù phần
snippet chuẩn hóa + đầu ra nếu dùng LLM; chưa tính system/context overhead,
reasoning hay retry. Fetch/parse bằng Python có thể không cần model call. Không
cam kết quy đổi các mức token này thành USD hoặc bảo đảm nằm trong 3 USD khi
chưa có giá/usage thực; không mua API/token/credit trong phiên này.

| Nguồn | Evidence dự kiến / khả năng tìm | Cost token + thời gian dự trù | Rủi ro chính | Đề xuất xin duyệt |
|---|---|---|---|---|
| Product Hunt — `producthunt.com` | Launch, review, maker comment, revenue report nếu có. Buyer: có thể có lead; payment: chưa biết; trend: có thể có metadata tại nhiều mốc nhưng cần cohort cố định | Khoảng 3K–8K token cho snippet/output; 1–2 giờ kiểm tra đường thu thập, adapter/tests/review | API/RSS chưa kiểm chứng; có thể cần quyền truy cập hoặc gặp giới hạn; vote/review dễ bị diễn giải quá mức | **DUYỆT pilot có điều kiện** để tìm lead, không duyệt coi dữ liệu đó tự động là transaction proof |
| IndieHackers — `indiehackers.com` | Revenue report, milestone, interview nếu tìm được. Buyer: thường cần bằng chứng bổ sung; payment: chưa biết; trend: milestone cần kiểm tra cùng entity/metric/kỳ đo | Khoảng 4K–10K token; 1–3 giờ kiểm tra public page/RSS, extraction và đối chứng | Nội dung có thể động, yêu cầu đăng nhập, giới hạn truy cập; self-report, survivorship bias, screenshot khó xác thực | **DUYỆT pilot có điều kiện**, ưu tiên tìm đầu mối proof; không công nhận ARR/MRR tự khai là payment evidence |
| Company blog / case study — chưa có hostname cụ thể | Customer story, revenue report, testimonial; khả năng buyer/product mapping có thể tốt hơn nếu có xác nhận phía khách. Payment/trend vẫn cần chứng từ và đo tương thích | Khoảng 4K–10K token; 1–3 giờ cho mỗi domain, tùy cấu trúc và quyền truy cập | Marketing bias, tài liệu không độc lập, điều khoản/robots khác nhau; redirect/CDN/attachment có thể vượt scope | **KHÔNG DUYỆT nhóm domain đại trà**. Đề xuất DUYỆT từng hostname/URL sau khi trình scope cụ thể |

### 1. Product Hunt

Mức yêu cầu trong đề bài: **Trung bình**. Diễn giải thận trọng: giả thuyết có
thể tìm được câu chuyện monetization; **khả năng có payment proof đủ chuẩn chưa
được xác minh**. Launch/review/maker comment là discovery data, không phải chứng
từ giao dịch. Liên kết đến công ty khác chỉ là DATA cho tới khi domain đích được duyệt.

Thu thập đề xuất: search API hoặc RSS **nếu sau khi duyệt mới xác minh được
endpoint công khai phù hợp**. Tài liệu này không khẳng định có search API/RSS
anonymous đang hoạt động, không bịa endpoint, không dùng private/internal API.
Nếu cần credential, subscription hoặc trả phí thì dừng để xin quyết định riêng;
không tìm secrets hoặc tự lấy token từ máy.

Phạm vi xin duyệt đầu tiên chỉ là hostname `producthunt.com`. `www`, API host,
redirect hoặc CDN là các hostname cần khai báo/duyệt riêng, không được mở wildcard.
Ưu tiên tìm một record có buyer/product/time linkage và nguồn chứng từ cụ thể;
nếu chỉ có launch/votes/pricing, ghi GAP và dừng trong quota.

### 2. IndieHackers

Mức yêu cầu trong đề bài: **Cao**. Đây chỉ là giả thuyết về khả năng gặp revenue
report/milestone, **không phải kết luận xác suất verified payment proof cao**.
Một founder tự khai doanh thu không xác nhận buyer hoặc từng giao dịch. Số
doanh thu tổng hợp không gắn được buyer/product/time chưa đạt gate hiện tại.

Thu thập đề xuất: RSS hoặc public page, sau khi duyệt và kiểm tra khả năng truy
cập thực. Chưa xác minh RSS/feed URL nào; không dựng URL theo phỏng đoán. Không
vượt login, captcha, paywall hoặc chống bot. Nếu public page chỉ dẫn sang nguồn
ngoài allowlist, giữ link làm lead và chờ duyệt, không tự follow.

Xin duyệt hostname `indiehackers.com` trước; không suy ra quyền cho mọi subdomain.
Pilot cần phân biệt lời founder, lời khách hàng và tài liệu xác nhận độc lập.
Thiếu buyer/payment linkage sau pilot thì tiếp tục draft, không tìm vô hạn để
đạt số lượng opportunity.

### 3. Company blog / case study

Mức yêu cầu trong đề bài: **Trung bình–Cao**, là giả thuyết ưu tiên, chưa được đo.
Customer story có thể giúp xác định khách hàng/sản phẩm, nhưng không tự xác nhận
khách đã thanh toán. Customer logo hoặc testimonial không nói giá trị/thời điểm
giao dịch thì không được diễn giải thành revenue/payment proof.

Thu thập đề xuất: RSS hoặc direct URL được người dùng duyệt. Hiện **không có
company hostname, bài case study hay URL chứng từ cụ thể nào được xác minh**
trong phiên này. Không dùng một tên gọi “company blog” để mở toàn Internet.
Mỗi đề nghị tiếp theo phải ghi exact hostname, URL/endpoint, mục đích, loại proof
mong đợi, quota và redirect/attachment host. Review cả phía vendor và khách nếu
có nguồn được duyệt; hai bài sao chép cùng thông cáo không là đối chứng độc lập.

## Rủi ro và điều kiện pilot chung

1. Chỉ sau duyệt domain mới kiểm tra tài liệu API/feed, robots và điều khoản
   truy cập/sử dụng hiện hành trên domain đó. Chưa kiểm tra thì để UNKNOWN;
   tài liệu này không đưa kết luận pháp lý rằng scraping hay tái xuất bản được phép.
2. Chỉ public read; không bypass access control, không đọc secrets. 401/403,
   captcha, yêu cầu phí hoặc điều khoản chưa rõ: dừng nguồn, báo GAP. Robots
   không thay thế quyền truy cập hoặc đánh giá điều khoản.
3. Trình phương án timeout/retry/rate-limit cụ thể trước pilot; đề xuất khởi đầu
   tối đa 2 attempts, khoảng cách ít nhất 2 giây/host, tôn trọng cooldown dài
   bằng cách dừng thay vì retry sớm. Không dùng scraping nhiều worker để né giới hạn.
4. Lưu URL thật, raw bytes, SHA-256, retrieval/event times và locator. Chỉ trích
   phần cần thiết, phân biệt source allegation với fact được kiểm chứng; không
   đưa dữ liệu nhạy cảm hoặc nguồn ngoài phạm vi vào dashboard.
5. Chạy một pilot cho một nguồn được duyệt; quota và wall-clock phải khóa trước
   fetch. Đo usage nếu dùng model; không có metering thì không tự tuyên bố đạt
   ngân sách. Không phát sinh run tự động, email, bài đăng hay thanh toán.

## Quyết định đang chờ

Đề xuất duyệt thăm dò có điều kiện Product Hunt/IndieHackers, từng nguồn một;
company case study cần một đề nghị hostname cụ thể trước. **Cả ba hiện vẫn chưa
được người dùng duyệt**, chưa có adapter hay allowlist mới. Duyệt domain chỉ
cho phép chuẩn bị/kiểm tra phạm vi được chỉ định; không có nghĩa nguồn đã đủ
payment proof hoặc được phép chạy nhiều lượt. Chờ quyết định trước mọi live fetch.
