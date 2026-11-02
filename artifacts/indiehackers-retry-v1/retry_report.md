# IndieHackers retry + T+7 preparation

Ngày 02/11/2026. **RESEARCH_DRAFT_ONLY**, 0 economic records, 0 claims, 0 opportunities.

| Request (one attempt each) | HTTP | RSS entries |
|---|---:|---|
| `/posts.rss?q=AI` | 500 | Not observed |
| `/posts.rss?q=MRR` | 500 | Not observed |
| `/posts.rss` | 500 | Not observed |

Đây là đúng một đợt fallback được duyệt, tổng **3 GET**, không internal retry.
Chỉ request `feed.indiehackers.world`. Không gọi GitHub/HN, không mở article links
hoặc domain ngoài scope. Endpoint lấy từ raw root của lượt trước, không đoán URL.
Protocol được khóa trước request; raw error bodies/meta/log/checkpoint đã lưu.
Feed mirror tự nhận unofficial; không tuyên bố dữ liệu được IndieHackers xác minh.

Config: `reliability=UNRELIABLE`, `enabled=false`, `retry_exhausted=true`,
`automatic_refresh=false`. **Không thử lại**. Cả ba là lỗi nguồn, không phải
feed thực sự rỗng. Chưa quan sát revenue data để trích T2; không kết luận thị
trường không có T2. Không bịa candidate, số MRR, buyer hoặc payment proof.
T2 policy giữ nguyên: ≥3 distinct actual observations cùng product/founder,
metric/currency/cadence và raw field review → EMERGING, không phải T1/PROVEN.

## T+7 baseline

Đã chạy `python scripts/prepare_t7_snapshot.py` offline để đóng băng **15 records**
từ MVP gốc: 10 repos + 5 HN stories. T0 là timestamp thật ngày **02/11/2026**;
thời gian chuẩn bị không phải lần quan sát mới. [Snapshot](../t7-baseline/snapshot_t0.jsonl)
và [manifest](../t7-baseline/run_manifest.json) liên kết raw/hash/locator từng counter.

HN có points/num_comments. GitHub giữ literal followers và hai labeled issue
counters; verified stars, total issues và specific issue comments thiếu → null.
Không đổi followers thành stars, không tạo counter 0 giả hay backfill T0.
Do đó baseline **BASELINE_PREPARED_WITH_GAPS**, chưa đủ delta cho mọi metric.
Comment/star delta nếu có là net change, không tự bằng số events mới.

T+7: **09/11/2026**, T+14: **16/11/2026**, giữ UTC anchors trong từng row và
Asia/Saigon trong [kế hoạch](../../docs/t7_plan.md). Chưa chạy T+7/T+14,
không cron/scheduler. Không truy metrics hiện tại để giả thành số của T0 cũ.
Protocol trend được đăng ký sau T0; follow-up phải nêu giới hạn này.

## Kiểm tra và bước tiếp theo

**140 offline tests PASS**, failures=0/errors=0, socket creation blocked.
Hash test log khớp byte file; đối chiếu ba request/ingress/raw/meta và các hash
baseline. [Test report](offline-tests/offline_tests.json). Giữ nguyên LICENSE
và artifact lịch sử. Không có paid API/model call riêng cho fetch/parse; tổng
billing phiên không được đo nên không khẳng định 0 USD.

GAP: RSS_UNRELIABLE_HTTP_500_ALL_THREE, NO_FEED_DATA_OBSERVED, NO_REVIEWED_T2_REVENUE_HISTORY, NO_VERIFIED_PAYMENT_PROOF_OBSERVED, T7_T14_NOT_OBSERVED, GITHUB_T0_METRICS_MISSING.

Dừng RSS do UNRELIABLE. Chờ người dùng review; phương án tiếp theo là duyệt
endpoint/method cho phép đo cohort ngày 09/11, hoặc duyệt nguồn/URL khác riêng.
Giá trị GitHub còn thiếu cần baseline có timestamp mới, không backdate. Không
tự thêm domain hoặc chạy live khác. Chưa production-ready.
