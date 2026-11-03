# Live evidence v2 — GitHub + HN, T2.5

**RESEARCH_DRAFT_ONLY**. Capture duy nhất ngày **02/11/2026**; review/tổng hợp
offline hoàn tất ngày **03/11/2026** (Asia/Saigon). Không refresh ngày review.

| Metric | Kết quả |
|---|---:|
| GitHub repos / README capture | 8 / 8 |
| HN retained records | 7 |
| Live records merged | 15 |
| Claims có raw quote/locator | 8 |
| Opportunities | 0 |
| HTTP attempts / HTTP 200 responses | 18 / 18 |
| Historical T0 cohort, riêng biệt | 15 |

## Phương pháp và scope

WS-1 khóa bốn query topic/README, first page hai repos/query, giữ tối đa 8 IDs
duy nhất rồi đọc đúng 8 README bằng GitHub contents API (base64 JSON). 12 GET,
mỗi URL một attempt, interval 7 giây. WS-2 khóa sáu keyword yêu cầu, tags
`(comment,show_hn)` OR, search_by_date page0, hai hits/query; 12 hits trả về,
10 IDs duy nhất thấy được, giữ first7 theo protocol (2 duplicate occurrences).
WS-2 dùng 6 GET, không retry thực tế. Cả hai protocol được lưu trước GET.

Cửa sổ HN khóa từ **2026-10-03T10:53:45+00:00** đến
**2026-11-02T10:53:45+00:00**; không đổi thành 30 ngày tính từ ngày finalization.
Các hit trả về khá nhiễu; keyword/query match không là business relevance proof.
Không backfill, không page tiếp, không thêm query sau khi xem kết quả.

Chỉ request **api.github.com và hn.algolia.com**. github.com được duyệt nhưng
không cần request. HN canonical article/comment URL được dựng từ objectID và
ghi rõ derived/not fetched; source request URL thật là API Algolia. Không mở
pricing/checkout/blog/attachment/payment domains, không POST/click Pay hoặc
execute repo code. RSS IndieHackers vẫn TẮT UNRELIABLE/retry exhausted; TAAFT,
Reddit và Product Hunt không được truy cập. Những quyết định domain là policy
của người dùng, không phải kết luận pháp lý/ToS được kiểm tra trong lượt này.

## Review T2.5 từng repo

Ba component bắt buộc gắn cùng current product; provider mention, SDK khả năng
cho merchant khác và template configuration không đủ xác nhận sản phẩm thu phí.

| Repo source | Loại quan sát | Integration / pricing / checkout | T2.5 |
|---|---|---|---|
| [agentscore/python-commerce](https://github.com/agentscore/python-commerce) | PAYMENT_SDK | GAP / GAP / GAP | Chưa đủ |
| [agentscore/node-commerce](https://github.com/agentscore/node-commerce) | PAYMENT_SDK | GAP / GAP / GAP | Chưa đủ |
| [Holojerm/nuxt-cf-template](https://github.com/Holojerm/nuxt-cf-template) | APPLICATION_TEMPLATE | GAP / GAP / GAP | Chưa đủ |
| [PaddleHQ/paddle-go-sdk](https://github.com/PaddleHQ/paddle-go-sdk) | PAYMENT_PROVIDER_SDK | GAP / GAP / GAP | Chưa đủ |
| [YawLabs/lemonsqueezy-mcp](https://github.com/YawLabs/lemonsqueezy-mcp) | STORE_MANAGEMENT_MCP_SERVER | GAP / GAP / GAP | Chưa đủ |
| [capawesome-team/revenue-sdk](https://github.com/capawesome-team/revenue-sdk) | PAYMENT_SDK | GAP / GAP / GAP | Chưa đủ |
| [euron-sde-team/euron-open-crm](https://github.com/euron-sde-team/euron-open-crm) | SELF_HOSTED_CRM | documented / GAP / GAP | Chưa đủ |
| [luckie9/ai-dev-starter](https://github.com/luckie9/ai-dev-starter) | SAAS_STARTER | documented / GAP / GAP | Chưa đủ |

Năm repo là SDK/API tooling (gồm MCP store-management); hai là template/starter.
CRM GH07 có documentation Stripe billing và current product context, nhưng chưa
capture pricing page hoặc flow pricing-to-checkout cụ thể. GH08 có Stripe wiring
và link Pro pricing/live sandbox chưa mở; giá setup là placeholder, chưa chứng
minh paid plan thực. Không gọi README mang nhãn production-ready là đánh giá
production readiness của pipeline này.

Cảnh báo provenance: GH05 README có revenue/subscription/refund numbers trong
**demo conversation**; GH08 có giá ví dụ cấu hình. Không dùng các số đó thành
real revenue, ba data points T2, buyer hoặc payment proof. Xem exact raw lines,
quotes và reasons trong [component review](component_review.json).

## HN và tier evaluation

7 records không có đủ ba component T2.5. HN01 tác giả tự nhận là paying customer
của Proton; chưa xác minh buyer/transaction, không là founder case và không nối
được integration + pricing + checkout. Các hit còn lại không tạo được chuỗi
revenue cùng founder/product hoặc hạ tầng current product đủ chuẩn.

Mọi record và 8 claims đều chỉ được dùng ở mức source-attributed/T3 HYPED,
không là 15 opportunities hay khẳng định thị trường đang hype/growth. Claim
selection là purposive six GitHub documentation statements + two HN statements,
không là frequency estimate. T1 cần chứng từ/xác minh riêng; T2 cần >=3 actual
observations khác kỳ; T2.5 cần đủ same-product components. **0 case đủ điều kiện**.

Không yêu cầu T1 payment hoặc T+7 để bác T2.5: kết quả rỗng vì thiếu component
và current-product linkage, không phải do áp lại gate buyer/payment cũ. Chưa
verify deployed checkout, chưa execute checkout, chưa quan sát transaction.
Không nâng self-report hoặc external link chưa fetch thành PROVEN/EMERGING.

## WS-3: giữ nguyên baseline

[Audit WS-3](ws3/audit.json) xác nhận đúng 15 IDs T0 cũ: 10 repos + 5 HN stories;
hash/raw/counters giữ nguyên. Chúng **không được merge** vào 15 discovery records
hoặc dùng làm follow-up của repo mới. T0 02/11; T+7 chờ **09/11/2026**, T+14
**16/11/2026**; chưa đo. GitHub verified stars/total issues/specific issue comment
baselines vẫn null/GAP; không đổi followers thành stars hoặc bịa delta.

## Kiểm tra, GAP và bước tiếp theo

**181 offline tests PASS**, failures=0/errors=0, socket creation bị
chặn. [Test report](offline-tests/offline_tests.json). Kiểm SHA-256/body bytes/meta/
request IDs cho cả 18 responses; README decoded hash + Git blob hash, từng line
quote, HN recency/tags/identity. Tier tests gồm positive T2/T2.5 synthetic và
negative missing/cross-product/scaffold/provenance; fixtures không là proof live.
LICENSE và artifact cũ không sửa. Config/criteria pin trong manifest được ghi
khi tổng hợp; sampling pre-request nằm riêng trong workstream protocols.

GAP codes: NO_COMPLETE_T2_5_CURRENT_PRODUCT_INFRASTRUCTURE, NO_VERIFIED_T1_PAYMENT, NO_THREE_POINT_T2_REVENUE_HISTORY, SDK_AND_STARTER_HEAVY_BOUNDED_SAMPLE, EXTERNAL_PRICING_CHECKOUT_LINKS_NOT_FETCHED, HN_LOW_RELEVANCE_AND_UNVERIFIED_IDENTITIES, T7_T14_NOT_OBSERVED.

Đề xuất để người dùng duyệt: một lượt kiểm tra code/docs GitHub có mục tiêu cho
CRM GH07 (pricing và checkout paths) và GH08 (phân biệt paid product với starter),
trong các hostname đã duyệt và không đọc secret; hoặc chỉ giữ draft và chờ T+7.
Nếu cần xác minh app/payment URL ngoài scope, trình từng hostname/URL để duyệt
riêng. Không tự chạy lượt mới, mở domain mới hoặc cron/production.

Không gọi paid API/token/login hay thực hiện giao dịch. Không đo tổng billing
phiên nên không khẳng định chi phí tổng bằng 0 USD. Chưa production-ready.

[Ledger](evidence_ledger.json) · [Opportunities CSV](opportunities.csv) · [Manifest](run_manifest.json).
