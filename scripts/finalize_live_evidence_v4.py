"""Finalize the reviewed v4 GAP report offline; never capture or approve URLs."""
import hashlib
import json
from pathlib import Path

from money_trend.core import DataError, strict_json, utc, write_json
from money_trend.live_v4_hn import baseline_audit

ROOT = Path(__file__).resolve().parents[1]
OUT = Path('artifacts/live-evidence-v4')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize(root=ROOT):
    root = Path(root).resolve()
    out = root / OUT
    ledger = strict_json((out / 'evidence_ledger.json').read_text(encoding='utf-8'))
    tests_path = out / 'offline/offline_tests.json'
    tests = strict_json(tests_path.read_text(encoding='utf-8'))
    if tests.get('status') != 'PASS' or tests.get('failures') != 0 or tests.get('errors') != 0:
        raise DataError('CRITICAL: current offline test suite has not passed')
    for name, digest in tests['source_sha256'].items():
        if sha(root / name) != digest:
            raise DataError('CRITICAL: source changed after offline tests')
    if sha(tests_path.with_name('offline_tests.txt')) != tests['log_sha256']:
        raise DataError('CRITICAL: offline test log hash mismatch')
    baseline = baseline_audit(root)
    if ledger['opportunities'] or ledger['status'] != 'RESEARCH_DRAFT_ONLY':
        raise DataError('this finalizer is scoped to the current v4 GAP run')
    protocol = strict_json((out / 'scan/protocol.json').read_text(encoding='utf-8'))
    counts, gates = ledger['request_counts'], ledger['gates']
    table = []
    for item in ledger['candidates']:
        s = item['score_components']
        price = 'USD 8 / gift (post only)' if item['pricing_quote'] else 'pending verification'
        table.append(f"| [{item['product']}]({item['post_url']}) | [{item['product_url']}]({item['product_url']}) | {item['founder']} | None | {s['integration']}/{s['pricing']}/{s['linkage']} = **{item['score']}** | {price} |")
    rows = '\n'.join(table)
    warnings = '\n'.join(f"- **{c['product']}**: {c['scope_warning']} {' '.join(c['gaps'])}" for c in ledger['candidates'])
    corrected = ', '.join(ledger['normalization_notes']['corrected_records'])
    report = f'''# Live evidence v4 — HN Show HN pricing scan

**RESEARCH_DRAFT_ONLY — 0 opportunities.** Capture 03/11/2026 10:33 Asia/Saigon;
offline review completed after the usage-limit/user pause. Không chạy lại scan.

| Metric | Count |
|---|---:|
| Scan HTTP attempts / HTTP 200 | {counts['scan_attempts']} / {counts['scan_http_200']} |
| Returned hits / distinct posts | {ledger['returned_hits']} / {ledger['raw_count']} |
| Duplicate hits | 4 |
| Posts with syntactically public URL strings in post text | 11 |
| Reviewed homepage/demo discovery leads | {ledger['candidate_count']} |
| Leads scoring ≥70 / required | {ledger['shortlist_count']} / 5 |
| Source-attributed claims | {ledger['claim_count']} |
| Provider mentions / verified integration | 0 / 0 |
| Verified pricing pages / T2.5a / T2.5b | 0 / 0 / 0 |
| EMERGING / PROVEN opportunities | 0 / 0 |
| Product, pricing or checkout GETs | 0 |

## Protocol and provenance

Frozen window: `{protocol['cutoff_utc']}` → `{protocol['anchor_utc']}` (30 days).
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
{rows}

Shortlist duy nhất: **Maintainers Coffee, 70/100**. Source quote:
“Someone can send coffee for USD $8 to either Canada or the US.” Giá này là
giá quà tặng cà phê tự mô tả trong post, chưa verify trang pricing, integration
hoặc giao dịch. Đây là dịch vụ **quà tặng vật lý, không phải sản phẩm AI**;
vẫn ghi điểm discovery theo rubric nguyên văn để không thêm gate ngầm.

### Context and exclusions

{warnings}

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
| G4 | ACQUISITION_STOP | Frozen start 03:31:24 UTC, guard 1,260 s. Capture finished after {gates['G4']['capture_finished_elapsed_seconds']:.1f} s; wall clock later exceeded guard during the long pause; no budget reset recorded |
| G5 | Source provenance PASS; product verification pending | Captured public HN URLs/hash/quotes checked; zero approved/fetched product or pricing pages, so no T2.5 qualification |

Không coi thời gian pause là bốn giờ active research. Báo cáo vẫn áp dụng
wall-clock guard nguyên văn; sau capture 10:33 không phát sinh GET acquisition
mới. Script không gọi LLM hoặc đọc credentials; không quan sát được tổng token
hay chi phí model của phiên để tuyên bố số USD/token thực dùng.

## Merge and evaluation

Mapping: T1 → PROVEN; T2/T2.5a/T2.5b → EMERGING; T3 → HYPED.
26 source records chỉ có T3; {ledger['claim_count']} claims là câu nguồn đã phát biểu, chưa chứng minh
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
  anchor. Corrected IDs: {corrected}. Raw captures và JSONL ban đầu giữ nguyên;
  không tái quét và không dùng URL rút gọn để xin duyệt.
- Offline suite: **{tests['tests_run']} PASS**, sockets blocked.
  [Report](offline/offline_tests.json) · [Log](offline/offline_tests.txt).
- Baseline: **{baseline['baseline_records']} IDs intact**, toàn bộ historical hashes
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
'''
    (out / 'live_evidence_report.md').write_bytes(report.encode('utf-8'))
    dashboard = f'''# AI Money-Trend — live evidence v4

**RESEARCH_DRAFT_ONLY — 0 opportunities.** Capture 03/11/2026, 10:33 Asia/Saigon.

| Metric | Count |
|---|---:|
| HN scan HTTP attempts / HTTP 200 | 3 / 3 |
| Hits / distinct Show HN posts | 30 / 26 |
| Product/demo discovery leads | 9 |
| Leads scoring ≥70 / required | 1 / 5 |
| Source claims / opportunities | {ledger['claim_count']} / 0 |
| Verified T2.5a / T2.5b | 0 / 0 |
| Product/pricing/checkout GETs | 0 |
| Historical baseline IDs (separate) | 15 |

## Top Opportunities

Chưa có. G3 thiếu 5 candidates ≥70; chưa có integration + captured pricing
page. T2.5a đủ EMERGING khi verified; T2.5b thêm checkout tĩnh, không bắt buộc.

## GAP và URL chờ review

- Không post nào nhắc Stripe/Paddle/LemonSqueezy; pricing pages pending verification.
- Maintainers Coffee đạt literal 70 (0/30/40), nhưng là quà tặng cà phê vật lý,
  không phải sản phẩm AI. URL homepage nguyên văn chờ duyệt:
  [https://maintainers.coffee/](https://maintainers.coffee/). Chưa fetch.
- G1/G2 PASS. G4 dừng acquisition do wall-clock vượt 70% qua quãng pause;
  chưa có budget reset. G5 mới verify HN provenance, chưa verify trang sản phẩm.
- T0 giữ nguyên, T+7 chờ **09/11/2026**; GH07/GH08 không điều tra thêm.

[Report](artifacts/live-evidence-v4/live_evidence_report.md) ·
[Candidates + scores](artifacts/live-evidence-v4/candidates.json) ·
[Ledger](artifacts/live-evidence-v4/evidence_ledger.json) ·
[CSV](artifacts/live-evidence-v4/opportunities.csv) ·
[Manifest](artifacts/live-evidence-v4/run_manifest.json).

Offline suite: **{tests['tests_run']} PASS**. Dừng chờ review; chưa production-ready.
'''
    (root / 'dashboard.md').write_bytes(dashboard.encode('utf-8'))
    artifact_hashes = {p.relative_to(root).as_posix(): sha(p) for p in sorted(out.rglob('*'))
                       if p.is_file() and p.name != 'run_manifest.json'}
    bundle = ('config/production_v1.json', 'config/live_evidence_v4.json', 'docs/evidence_criteria.md',
              'dashboard.md', 'scripts/finalize_live_evidence_v4.py')
    manifest = {'run_id': 'live-evidence-v4', 'generated_at': utc(), 'status': ledger['status'],
        'capture_completed_at': strict_json((out / 'scan/manifest.json').read_text())['finished_at'],
        'raw_count': ledger['raw_count'], 'claim_count': ledger['claim_count'],
        'candidate_count': ledger['candidate_count'], 'shortlist_count': ledger['shortlist_count'],
        'opportunity_count': 0, 'gates': gates, 'approved_product_urls': [],
        'source_files_sha256': tests['source_sha256'], 'bundle_sha256': {n: sha(root / n) for n in bundle},
        'artifacts_sha256': artifact_hashes, 'baseline': baseline,
        'new_acquisition_authorized': False, 't7_executed': False,
        'commit_message_requested': 'Pivot to HN Show HN pricing scan + T2.5a/b + gates + live v4',
        'git_commit_or_push_success_claimed': False}
    write_json(out / 'run_manifest.json', manifest)
    return {k: manifest[k] for k in ('status', 'raw_count', 'candidate_count', 'shortlist_count', 'opportunity_count')}


if __name__ == '__main__':
    print(json.dumps(finalize()))
