"""Finalize the saved v2 batch offline; never fetch or execute source content."""
import csv
import io
import json
import socket
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from money_trend.core import DataError, utc, write_json
from money_trend.indie_run import load, sha
from money_trend.live_v2_merge import OUT, build_ledger, make_review


def jsonl(path, rows):
    path.write_bytes(''.join(json.dumps(r, ensure_ascii=False, allow_nan=False) + '\n' for r in rows).encode('utf-8'))


def finalize(root=ROOT):
    root = Path(root).resolve()
    out = root / OUT
    if (out / 'run_manifest.json').exists():
        raise FileExistsError('v2 is finalized; no overwrite or new acquisition')
    config_path = root / 'config/production_v1.json'
    config = load(config_path)
    if (config['criteria_sha256'] != sha(root / 'docs/evidence_criteria.md')
            or config['sources']['indiehackers_rss']['enabled'] is not False
            or config['sources']['indiehackers_rss']['reliability'] != 'UNRELIABLE'
            or config['live_evidence_v2']['additional_live_run_authorized'] is not False):
        raise DataError('criteria pin or source policy mismatch')
    review = make_review(root, load(out / 'component_review.json'))
    ledger = build_ledger(root, review)
    if (ledger['raw_count'] != 15 or ledger['claim_count'] != 8 or ledger['opportunity_count'] != 0
            or ledger['request_counts'] != {'ws1': 12, 'ws2': 6}):
        raise DataError('capture differs from reviewed v2 GAP report; update report review before finalizing')
    tests_path = out / 'offline-tests/offline_tests.json'
    tests = load(tests_path)
    if (tests['status'] != 'PASS' or tests['failures'] or tests['errors']
            or tests['log_sha256'] != sha(tests_path.with_name('offline_tests.txt'))):
        raise DataError('current byte-verified passing offline report required')
    for name, digest in {**tests['source_sha256'], **tests['live_v2_bundle_sha256'], **tests['agent_bundle_sha256']}.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or sha(path) != digest:
            raise DataError('current source/test binding mismatch: ' + name)
    ledger['criteria_sha256'] = config['criteria_sha256']
    ledger['gaps'] = ([] if ledger['opportunities'] else ['NO_COMPLETE_T2_5_CURRENT_PRODUCT_INFRASTRUCTURE']) + [
        'NO_VERIFIED_T1_PAYMENT', 'NO_THREE_POINT_T2_REVENUE_HISTORY', 'SDK_AND_STARTER_HEAVY_BOUNDED_SAMPLE',
        'EXTERNAL_PRICING_CHECKOUT_LINKS_NOT_FETCHED', 'HN_LOW_RELEVANCE_AND_UNVERIFIED_IDENTITIES', 'T7_T14_NOT_OBSERVED']
    ledger['limits'] = {'raw_items': 15, 'claims': 8, 'opportunities': 5}
    ledger['verdict_distribution_records'] = dict(Counter(r['verdict'] for r in ledger['evaluations']))
    ledger['qualification_limit'] = 'T3/HYPED is source evidence grade, not a business opportunity, growth claim or ranking.'
    write_json(out / 'reviewed_candidates.json', review)
    write_json(out / 'evidence_ledger.json', ledger)
    jsonl(out / 'merged_evidence.jsonl', ledger['raw_items'])
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=['product', 'tier', 'verdict', 'source_url', 'evidence_ids'], lineterminator='\n')
    writer.writeheader()
    for opp in ledger['opportunities']:
        writer.writerow({k: json.dumps(opp[k]) if k == 'evidence_ids' else opp[k] for k in writer.fieldnames})
    (out / 'opportunities.csv').write_bytes(stream.getvalue().encode('utf-8'))
    now = utc()
    local_final = datetime.fromisoformat(now).astimezone(timezone(timedelta(hours=7))).strftime('%d/%m/%Y')
    retrievals = [r['retrieved_at'] for r in ledger['responses']]
    captures = {'first_response': min(retrievals), 'last_response': max(retrievals)}
    hn_protocol = load(out / 'ws2/protocol.json')
    gh_review = load(out / 'component_review.json')['github_reviews']
    rows = '\n'.join('| [' + r['product'] + '](' + r['repo_url'] + ') | ' + r['product_kind'] + ' | '
                     + ' / '.join('documented' if r['assessments'][k]['present'] else 'GAP' for k in ('integration', 'pricing', 'checkout'))
                     + ' | Chưa đủ |' for r in gh_review)
    report = f'''# Live evidence v2 — GitHub + HN, T2.5

**{ledger['status']}**. Capture duy nhất ngày **02/11/2026**; review/tổng hợp
offline hoàn tất ngày **{local_final}** (Asia/Saigon). Không refresh ngày review.

| Metric | Kết quả |
|---|---:|
| GitHub repos / README capture | {ledger['source_counts']['github']} / 8 |
| HN retained records | {ledger['source_counts']['hn']} |
| Live records merged | {ledger['raw_count']} |
| Claims có raw quote/locator | {ledger['claim_count']} |
| Opportunities | {ledger['opportunity_count']} |
| HTTP attempts / HTTP 200 responses | {sum(ledger['request_counts'].values())} / {len(ledger['responses'])} |
| Historical T0 cohort, riêng biệt | 15 |

## Phương pháp và scope

WS-1 khóa bốn query topic/README, first page hai repos/query, giữ tối đa 8 IDs
duy nhất rồi đọc đúng 8 README bằng GitHub contents API (base64 JSON). 12 GET,
mỗi URL một attempt, interval 7 giây. WS-2 khóa sáu keyword yêu cầu, tags
`(comment,show_hn)` OR, search_by_date page0, hai hits/query; 12 hits trả về,
10 IDs duy nhất thấy được, giữ first7 theo protocol (2 duplicate occurrences).
WS-2 dùng 6 GET, không retry thực tế. Cả hai protocol được lưu trước GET.

Cửa sổ HN khóa từ **{hn_protocol['cutoff_utc']}** đến
**{hn_protocol['anchor_utc']}**; không đổi thành 30 ngày tính từ ngày finalization.
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
{rows}

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

**{tests['tests_run']} offline tests PASS**, failures=0/errors=0, socket creation bị
chặn. [Test report](offline-tests/offline_tests.json). Kiểm SHA-256/body bytes/meta/
request IDs cho cả 18 responses; README decoded hash + Git blob hash, từng line
quote, HN recency/tags/identity. Tier tests gồm positive T2/T2.5 synthetic và
negative missing/cross-product/scaffold/provenance; fixtures không là proof live.
LICENSE và artifact cũ không sửa. Config/criteria pin trong manifest được ghi
khi tổng hợp; sampling pre-request nằm riêng trong workstream protocols.

GAP codes: {', '.join(ledger['gaps'])}.

Đề xuất để người dùng duyệt: một lượt kiểm tra code/docs GitHub có mục tiêu cho
CRM GH07 (pricing và checkout paths) và GH08 (phân biệt paid product với starter),
trong các hostname đã duyệt và không đọc secret; hoặc chỉ giữ draft và chờ T+7.
Nếu cần xác minh app/payment URL ngoài scope, trình từng hostname/URL để duyệt
riêng. Không tự chạy lượt mới, mở domain mới hoặc cron/production.

Không gọi paid API/token/login hay thực hiện giao dịch. Không đo tổng billing
phiên nên không khẳng định chi phí tổng bằng 0 USD. Chưa production-ready.

[Ledger](evidence_ledger.json) · [Opportunities CSV](opportunities.csv) · [Manifest](run_manifest.json).
'''
    (out / 'live_evidence_report.md').write_bytes(report.encode('utf-8'))
    dashboard = f'''# AI Money-Trend — live evidence v2

**{ledger['status']}**. Capture 02/11/2026; offline review {local_final}.

| Metric | Count |
|---|---:|
| GitHub repos + HN records | 8 + 7 |
| Claims / opportunities | {ledger['claim_count']} / {ledger['opportunity_count']} |
| HTTP attempts / 200 responses | 18 / 18 |
| T3/HYPED source records (unqualified) | 15 |
| EMERGING / PROVEN opportunities | 0 / 0 |
| Historical baseline IDs (excluded from discovery) | 15 |

## Top Opportunities

Chưa có. T2.5 cần cùng product có integration + pricing page + checkout flow.
SDK/template hoặc ba keyword mentions không chứng minh active paid product.

## GAP summary

- GH07 có Stripe billing docs, chưa đủ pricing/checkout; phần lớn sample là SDK/starter.
- HN customer/revenue language chưa tạo founder case hoặc complete payment infra.
- Demo revenue/refund và setup-price placeholders không là real payment/revenue proof.
- T0 giữ nguyên; chưa có T+7/T+14. T+7 chờ 09/11, chưa chạy/cài lịch.
- RSS IndieHackers TẮT UNRELIABLE; TAAFT/Reddit/Product Hunt không được dùng.

[Run report](artifacts/live-evidence-v2/live_evidence_report.md) ·
[Ledger](artifacts/live-evidence-v2/evidence_ledger.json) · [CSV](artifacts/live-evidence-v2/opportunities.csv) ·
[Manifest](artifacts/live-evidence-v2/run_manifest.json).

Offline suite: {tests['tests_run']} PASS. Không chạy thêm live. Chờ review; chưa production-ready.
'''
    (root / 'dashboard.md').write_bytes(dashboard.encode('utf-8'))
    manifest = {'run_id': 'live-evidence-v2', 'status': ledger['status'], 'run_kind': 'one_parallel_live_capture_offline_merge',
                'finalized_at': now, 'finalization_local_date': local_final, 'acquisition': captures,
                'raw_count': ledger['raw_count'], 'claim_count': ledger['claim_count'], 'opportunity_count': ledger['opportunity_count'],
                'source_counts': ledger['source_counts'], 'request_counts': ledger['request_counts'],
                'actual_requested_hosts': sorted({r['url'].split('/')[2] for r in ledger['responses']}),
                'baseline_records': 15, 'baseline_merged': False, 't7_executed': False, 't14_executed': False,
                'additional_live_run_authorized': False, 'limits': ledger['limits'],
                'criteria_sha256': config['criteria_sha256'], 'config_sha256': sha(config_path),
                'offline_tests': tests['tests_run'], 'test_report_sha256': sha(tests_path),
                'source_sha256': tests['source_sha256'], 'live_v2_bundle_sha256': tests['live_v2_bundle_sha256'],
                'dashboard_sha256': sha(root / 'dashboard.md'), 'production_ready': False,
                'artifacts_sha256': {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob('*')) if p.is_file()}}
    write_json(out / 'run_manifest.json', manifest)
    write_json(out / 'terminal_checkpoint.json', {'state': 'FINALIZED_NO_ADDITIONAL_RUN', 'status': ledger['status'],
               'finalized_at': now, 'opportunities': ledger['opportunity_count'], 't7_executed': False})
    # The terminal checkpoint is also part of the finalized byte manifest.
    manifest['artifacts_sha256']['terminal_checkpoint.json'] = sha(out / 'terminal_checkpoint.json')
    write_json(out / 'run_manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    if len(sys.argv) != 1:
        raise SystemExit('This offline merger takes no network flags.')
    with patch.object(socket, 'socket', side_effect=AssertionError('offline v2 merge forbids network')):
        value = finalize()
    print(json.dumps({k: value[k] for k in ('status', 'raw_count', 'claim_count', 'opportunity_count', 'offline_tests')}))
