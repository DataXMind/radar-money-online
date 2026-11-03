# Live evidence v4 — HN Show HN pricing scan

**RESEARCH_DRAFT_ONLY — 0 opportunities.** Capture 03/11/2026 10:33 Asia/Saigon;
offline review completed after the usage-limit/user pause. Không chạy lại scan.

| Metric | Count |
|---|---:|
| Scan HTTP attempts / HTTP 200 | 3 / 3 |
| Returned hits / distinct posts | 30 / 26 |
| Duplicate hits | 4 |
| Posts with syntactically public URL strings in post text | 11 |
| Reviewed homepage/demo discovery leads | 9 |
| Leads scoring ≥70 / required | 1 / 5 |
| Source-attributed claims | 8 |
| Provider mentions / verified integration | 0 / 0 |
| Verified pricing pages / T2.5a / T2.5b | 0 / 0 / 0 |
| EMERGING / PROVEN opportunities | 0 / 0 |
| Product, pricing or checkout GETs | 0 |

## Protocol and provenance

Frozen window: `2026-10-04T03:33:03+00:00` → `2026-11-03T03:33:03+00:00` (30 days).
Ba query `AI agent`, `AI tool`, `launched`, `tags=show_hn`, page 0, 10 hits/query,
newest first. Deduplicate first observed objectID; không backfill hoặc thêm nguồn.
HN author handle/name là attribution của nguồn, chưa verify danh tính founder.
Submission URL riêng lẻ không thay PRODUCT URL trong post text.

[Frozen protocol](scan/protocol.json) · [Capture manifest](scan/manifest.json) ·
[Raw request journal](scan/requests/requests.jsonl) · [Captured normalized records](hn_evidence.jsonl) ·
[Corrected offline ledger](evidence_ledger.json) · [Component review](component_review.json).
Mỗi lead/claim trong ledger có exact source request URL, raw path, SHA-256,
row/field locator và quote đã đối chiếu. HN post URL được dựng từ objectID
thật để người dùng review; không GET website HN hoặc trang sản phẩm.

## Discovery leads — chỉ shortlist ≥70 được giữ

I/P/L = Integration 30 / Pricing 30 / Linkage 40. Pending nhận 0, không cộng
potential points. Provider mention chỉ là discovery signal, chưa verify integration.
Các lead dưới 70 chỉ giữ trong audit, không vào shortlist hay Top Opportunities.

| Product / HN post | Exact product/demo URL in post text | Founder attribution | Provider mention | I/P/L → total | Pricing status |
|---|---|---|---|---|---|
| [ArchDocs](https://news.ycombinator.com/item?id=50340570) | [https://archdocs.io/templates/design-doc-example](https://archdocs.io/templates/design-doc-example) | Aylon / HN AylonArmstrong | None | 0/0/40 = **40** | pending verification |
| [Hanging Context](https://news.ycombinator.com/item?id=50340083) | [https://hangingcontext.com/stories/2026-11-02/agent-stack-rebuilt-from-below/](https://hangingcontext.com/stories/2026-11-02/agent-stack-rebuilt-from-below/) | HN bshivarthy | None | 0/0/40 = **40** | pending verification |
| [Mind Made Many](https://news.ycombinator.com/item?id=50339212) | [https://mindmademany.com/mmm](https://mindmademany.com/mmm) | HN esamust | None | 0/0/40 = **40** | pending verification |
| [Garrul](https://news.ycombinator.com/item?id=50340303) | [https://garrul.com/#comments](https://garrul.com/#comments) | HN KingPinX | None | 0/0/40 = **40** | pending verification |
| [Subvocal](https://news.ycombinator.com/item?id=50340088) | [https://subvocal.company/](https://subvocal.company/) | Aarush and Arnav / HN aarushyadav | None | 0/0/40 = **40** | pending verification |
| [Prelay](https://news.ycombinator.com/item?id=50341158) | [https://prelay.lwnn.news](https://prelay.lwnn.news) | HN MPSimmons | None | 0/0/40 = **40** | pending verification |
| [mxRaven](https://news.ycombinator.com/item?id=50338055) | [https://mxraven.com](https://mxraven.com) | Kush / HN ku5h | None | 0/0/40 = **40** | pending verification |
| [Better Together](https://news.ycombinator.com/item?id=50331415) | [https://better-together.fun](https://better-together.fun) | HN adamontherun | None | 0/0/40 = **40** | pending verification |
| [Maintainers Coffee](https://news.ycombinator.com/item?id=50330154) | [https://maintainers.coffee/github/theorderingmachine](https://maintainers.coffee/github/theorderingmachine) | HN egz | None | 0/30/40 = **70** | USD 8 / gift (post only) |

Shortlist duy nhất: **Maintainers Coffee, 70/100**. Source quote:
“Someone can send coffee for USD $8 to either Canada or the US.” Giá này là
giá quà tặng cà phê tự mô tả trong post, chưa verify trang pricing, integration
hoặc giao dịch. Đây là dịch vụ **quà tặng vật lý, không phải sản phẩm AI**;
vẫn ghi điểm discovery theo rubric nguyên văn để không thêm gate ngầm.

### Context and exclusions

- **ArchDocs**: AI engineering context product; identity and deployment unverified. No provider mention or concrete price.
- **Hanging Context**: Free news experiment; Synorb is a separate paid product. Do not transfer Synorb monetization to Hanging Context. No provider mention or concrete price.
- **Mind Made Many**: Agent organization platform; source-attributed maker only. Subscription mentioned without concrete price. No provider mention.
- **Garrul**: Self-hosted Apache-licensed comments software; AI-assisted development does not establish an AI product. No commercial paid-plan/provider evidence.
- **Subvocal**: Prototype/preorder hardware; future shipping is not a current deployed software product. A $200 discount is not a product price. Preorder URL is not checkout proof. No provider mention.
- **Prelay**: Weather work planning; AI-product relevance not established in the post. No concrete price/provider mention.
- **mxRaven**: Email infrastructure supporting agent mailboxes; do not confuse first-party SDKs with the product. No concrete price/provider mention.
- **Better Together**: AI agent collaboration; source-attributed launch claim only. No concrete price/provider mention.
- **Maintainers Coffee**: Physical coffee gifting service, not an AI product; retain literal discovery score transparently. No provider mention. Post price is not a captured pricing page. Non-AI physical service; no AI market conclusion.

- V4-HN08 Slop Node: chỉ URL API version của node và bài Google bên thứ ba;
  không có trang chủ/demo sản phẩm phù hợp trong text. Không điều tra crypto.
- V4-HN25 PicoPlayer: chỉ technical documentation trong text; homepage chỉ
  xuất hiện ở submission URL, không đáp ứng điều kiện URL trong post text.
- 15 posts còn lại không có eligible product homepage/demo URL trong text;
  không dùng submission URL để bù.

## URL cần người dùng duyệt — chưa fetch

**Homepage: [https://maintainers.coffee/](https://maintainers.coffee/)**.
Đây là URL nguyên văn từ `url` của chính raw row V4-HN22, không đoán từ domain.
Lead đủ điều kiện discovery nhờ demo URL trong post text:
[https://maintainers.coffee/github/theorderingmachine](https://maintainers.coffee/github/theorderingmachine).
Scope warning: non-AI physical gifting. Trình URL để review, chưa duyệt cả domain.

[URL approval register](url_approvals.json): approved URLs rỗng, homepage đang
PENDING_USER_APPROVAL. Chưa có homepage capture để tìm link pricing, nên chưa
có pricing URL để trình duyệt và không tự đoán `/pricing`. Không verify checkout;
Sign up/preorder URL không là checkout proof. G4 đã dừng acquisition; muốn
fetch sau review cần chỉ dẫn tiếp tục với budget còn hiệu lực, ngoài duyệt URL.

## Gates

| Gate | Result | Evidence / effect |
|---|---|---|
| G1 | PASS | Prior retry HTTP 200, hash/HTTP metadata rechecked; user explicitly authorized continuation |
| G2 | PASS for scan | 3/3 HTTP 200, 0 HTTP 4xx/5xx, 0 DNS errors; no retry needed |
| G3 | FAIL / GAP | 9 leads but only 1 scores ≥70; requires at least 5 → no opportunities |
| G4 | ACQUISITION_STOP | Frozen start 03:31:24 UTC, guard 1,260 s. Capture finished after 104.6 s; wall clock later exceeded guard during the long pause; no budget reset recorded |
| G5 | Source provenance PASS; product verification pending | Captured public HN URLs/hash/quotes checked; zero approved/fetched product or pricing pages, so no T2.5 qualification |

Không coi thời gian pause là bốn giờ active research. Báo cáo vẫn áp dụng
wall-clock guard nguyên văn; sau capture 10:33 không phát sinh GET acquisition
mới. Script không gọi LLM hoặc đọc credentials; không quan sát được tổng token
hay chi phí model của phiên để tuyên bố số USD/token thực dùng.

## Merge and evaluation

Mapping: T1 → PROVEN; T2/T2.5a/T2.5b → EMERGING; T3 → HYPED.
26 source records chỉ có T3; 8 claims là câu nguồn đã phát biểu, chưa chứng minh
buyer/payment/revenue. Không có T1 proof hay chuỗi ≥3 revenue periods cho T2.
Giữ trần 8 claims: chọn theo điểm discovery giảm dần, rồi evidence ID; vẫn
review đủ 9 leads. Selection này có chủ đích, không phải tỷ lệ thị trường.
Không có current-product integration và captured pricing page cho T2.5a.
Điểm discovery 70 không là tier và không bypass G3/G4/G5.

**Top Opportunities: chưa có.** [CSV](opportunities.csv) chỉ có header;
không đưa lead 40 điểm hoặc non-AI gift service vào Top Opportunities.

T2.5a/b đã được cập nhật trong [criteria](../../docs/evidence_criteria.md) và
pure evaluator v4 riêng; giữ nguyên evaluator/artifact v2. T2.5b chỉ thêm static
checkout flow được duyệt, không bắt buộc cho T2.5a. Legacy buyer/payment/trend
flags luôn false ở discovery này. Không click, POST, execute hoặc thanh toán.

## Integrity, tests and stop state

- URL normalization được sửa offline: parser cũ lấy nhãn anchor bị HN rút gọn
  `...` thành URL ngắn sai. Ledger mới chỉ lấy href thật và plain text ngoài
  anchor. Corrected IDs: V4-HN05, V4-HN08, V4-HN15, V4-HN19. Raw captures và JSONL ban đầu giữ nguyên;
  không tái quét và không dùng URL rút gọn để xin duyệt.
- Offline suite: **221 PASS**, sockets blocked.
  [Report](offline/offline_tests.json) · [Log](offline/offline_tests.txt).
- Baseline: **15 IDs intact**, toàn bộ historical hashes
  đối chiếu PASS. [Audit before capture](scan/baseline_audit.json) ·
  [Audit after capture](scan/baseline_audit_after.json). T+7 chờ **09/11/2026**;
  không chạy sớm, không sửa T0 hoặc ghép cohort mới.
- GH07/GH08 không deep-dive; không quét GitHub, thêm nguồn hay truy cập domains cấm.
- Mẫu keyword/newest-first có selection bias; không phải khảo sát đầy đủ hoặc
  bằng chứng thị trường không có sản phẩm thu phí.

[Pre-flight history](preflight_history_report.md) ·
[DNS retry diagnostics](retry-preflight-20261103/retry_preflight_report.md) ·
[Run manifest](run_manifest.json).

Final state: **STOPPED_FOR_REVIEW — G3 GAP, G4 acquisition stop, exact homepage
approval pending**. Report/dashboard sẵn sàng commit; kết quả commit/push cần
xác nhận bằng Git riêng. Không tự chạy batch mới.
