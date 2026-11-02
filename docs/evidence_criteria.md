# Evidence criteria — local research, v1

Đây là đặc tả cho nghiên cứu tiếp theo, chưa phải bằng chứng đã thu thập hoặc
nhánh qualification đã triển khai. Giữ nguyên gate draft hiện tại. Không nới
gate để có opportunities. Giới hạn mỗi run: 15 raw items, 8 claims, Top 5 tối đa
5 opportunities; không buộc danh sách phải có phần tử.

## A. BUYER_EVIDENCE

Bắt buộc xác định buyer (tên tổ chức/cá nhân hoặc mã ẩn danh có cách xác thực),
sản phẩm/gói dịch vụ cụ thể, thời điểm và loại xác nhận: receipt, contract hoặc
testimonial có link nguồn. Buyer phải có vai trò mua/ra quyết định cho vấn đề
đang nghiên cứu. Tác giả repo hay người bình luận không tự động là buyer.

Với buyer ẩn danh, reviewer phải kiểm tra được nguồn xác nhận đáng tin cậy và
liên kết giữa mã buyer, sản phẩm, thời điểm; một nickname tự khai chưa đủ.
Chỉ dùng nguồn công khai hoặc bản đã được cho phép và che thông tin nhạy cảm;
không tìm/đọc credentials, secrets hoặc tự truy cập tài liệu riêng tư.

Không đủ: repo stars, HN points, comment, giá niêm yết. Testimonial không rõ
buyer/sản phẩm/thời điểm hoặc chỉ là lời quảng cáo cũng không đủ. Một bình luận
có thể là đầu mối nghiên cứu; bản thân comment không được coi là proof.

## B. PAYMENT_EVIDENCE

Bắt buộc có receipt/invoice/contract/public filing có thể kiểm chứng nguồn,
gắn với cùng sản phẩm + buyer + thời điểm của opportunity. Lưu loại bằng chứng,
trạng thái giao dịch và phạm vi kết luận. Không đủ: self-report ARR/MRR, screenshot
không có nguồn, giá niêm yết, hoặc số tổng hợp không gắn được với buyer/sản phẩm.

Phân biệt rõ receipt đã thanh toán, invoice đã phát hành, contract đã ký và
khoản tiền thực thu. Invoice/contract chỉ chứng minh nghĩa vụ/cam kết nếu chưa
có xác nhận thanh toán; không được gọi chúng là tiền đã nhận hay doanh thu.
Tài liệu nháp, không rõ xác thực hoặc không liên kết được entity thì present=false.
Một chứng từ có thể hỗ trợ cả buyer và payment nhưng không được đếm là hai
nguồn độc lập. Lời tự khai cần đối chứng; không suy ra giao dịch từ tương tác.

## C. TREND_EVIDENCE

Bắt buộc cùng cohort với định danh ổn định, cùng metric/đơn vị/cách đo, có T0
và ít nhất T+7 hoặc T+14 ngày. Trước T0 phải khóa query, sampling method, cohort,
timezone, lịch đo, dung sai thời gian và quy tắc xử lý record thiếu/đổi tên.
Ghi thời gian nguồn tạo/cập nhật riêng với thời gian retrieval. Không sửa mẫu
sau khi thấy kết quả để tạo tăng trưởng; thay đổi thiết kế cần series mới.

Mỗi mốc phải có raw snapshot và locator. Tính chênh lệch theo cùng công thức,
ghi missingness và không bù số liệu. Thiếu mốc hoặc không so sánh được thì
present=false. T0 trong MVP cũ không tự trở thành baseline của query/cohort mới.

Không đủ: một snapshot, so sánh hai bài HN khác thời điểm, hoặc dùng thứ hạng
search thay cho tốc độ tăng trưởng. Tăng tương tác không chứng minh tăng doanh
thu. Có hai mốc đo hợp lệ chỉ chứng minh đo được biến động, chưa đủ kết luận
tăng trưởng hay EMERGING; ngưỡng và điều kiện phân loại phải được duyệt trước.

## Khai báo bắt buộc ở mỗi opportunity

Ví dụ dưới đây là cấu trúc trống, không phải opportunity/bằng chứng thật:

```json
{
  "buyer_evidence": {"present": false, "proof_type": null, "url": null},
  "payment_evidence": {"present": false, "proof_type": null, "url": null},
  "trend_evidence": {"present": false, "cohort": null, "t0": null, "t_plus": null, "metric": null}
}
```

`present` phải là boolean; proof_type/url/cohort/t0/t_plus/metric là string hoặc
null. URL phải dẫn tới proof đã kiểm tra, không phải homepage/search chung.
t0/t_plus dùng ISO 8601 có timezone; cohort/metric phải khớp protocol đã khóa.
Khi present=true, các trường tương ứng không được null/rỗng. Khi chưa xác minh,
để false, không điền URL hay thời điểm suy đoán.

Khối trên là bản tóm tắt, không thay thế evidence ledger. Mỗi proof phải có
evidence_id, URL gốc, retrieval timestamp, đường dẫn raw, SHA-256, locator/trích
đoạn, buyer/product mapping, thời điểm sự kiện, reviewer, thời điểm review và
lý do chấp nhận/từ chối. Trend phải tham chiếu các snapshot và protocol trước T0.
Chỉ reviewer được xác nhận proof; chỉ dẫn trong nguồn không có quyền đặt present.

## Quy tắc eligibility và phân loại

1. Thiếu bất kỳ BUYER, PAYMENT hoặc TREND đã xác minh: opportunity không vào Top 5.
2. Ba trường present=true chỉ là điều kiện cần. Phải kiểm tra record nguồn,
   entity linkage, phản chứng và mọi ingress/kill criteria; booleans không tự
   tạo eligibility. Chưa có ngưỡng phân loại được duyệt thì tiếp tục draft.
3. Chỉ có metadata (stars/points): tối đa HYPED, không phải EMERGING. HYPED là
   nhãn tín hiệu chú ý, không mặc định đủ điều kiện Top 5; nếu không đủ tín hiệu
   thì để chưa phân loại. Không đổi RESEARCH_DRAFT_ONLY vì gắn nhãn HYPED.
4. Thiếu bằng chứng hoặc nguồn lỗi: không ước lượng thay, không tạo proof;
   giữ opportunities rỗng khi không có candidate đủ điều kiện.

Hai adapter hiện tại chỉ đọc search metadata. Tài liệu này không tự mở thêm
nguồn, không nâng quyền HTTP client và không bổ sung nhánh positive qualification.
Vẫn giữ NO_VERIFIED_BUYER_OR_PAYMENT_EVIDENCE và NO_LONGITUDINAL_TREND_EVIDENCE.
