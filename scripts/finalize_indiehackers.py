"""Finalize saved RSS requests offline. This command cannot start a live run."""
import argparse
import csv
import io
import json
import socket
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from money_trend.core import DataError, utc, write_json
from money_trend.indie_run import audit_capture, evaluate_reviewed, load, sha, validate_source_config


def finalize(root=ROOT):
    out = root / 'artifacts/indiehackers-evidence-v1'
    if (out / 'run_manifest.json').exists():
        raise FileExistsError('finalized run is immutable; no overwrite')
    config_path = root / 'config/production_v1.json'
    config = load(config_path)
    validate_source_config(config, root)
    audit = audit_capture(root, out)
    # This report template describes the captured v1 failure, not a future run.
    if (audit['request_attempts'] != 3 or [m['status'] for m in audit['responses']] != [200, 500, 500]
            or audit['records'] or audit['parsed_feed_responses'] != 0):
        raise DataError('v1 capture differs from reviewed failure; new report review required')
    summary = load(out / 'acquisition_summary.json')
    if summary['total_attempts'] != audit['request_attempts']:
        raise DataError('acquisition summary/log attempt mismatch')
    reviewed = load(out / 'reviewed_candidates.json')
    result = evaluate_reviewed(reviewed['candidates'], audit['records'])
    tests_path = out / 'offline-tests/offline_tests.json'
    tests = load(tests_path)
    if (tests['status'] != 'PASS' or tests['failures'] != 0 or tests['errors'] != 0
            or sha(tests_path.with_name('offline_tests.txt')) != tests['log_sha256']):
        raise DataError('passing, byte-verified offline tests required')
    for name, digest in {**tests['source_sha256'], **tests.get('indiehackers_bundle_sha256', {})}.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or sha(path) != digest:
            raise DataError('test report source binding mismatch: ' + name)
    gaps = list(audit['gaps'])
    if not result['opportunities']:
        gaps.append('NO_REVIEWED_T2_REVENUE_HISTORY')
    if len(audit['records']) < 10:
        gaps.append('MRR_ITEM_TARGET_NOT_MET')
    if any(q['state'] == 'NOT_RUN' for q in audit['query_status']):
        gaps.append('QUERY_COVERAGE_INCOMPLETE')
    gaps += ['NO_VERIFIED_PAYMENT_PROOF_OBSERVED', 'MVP_T7_T14_NOT_OBSERVED']
    # A partial/broken source cannot silently yield a complete positive run.
    opportunities = result['opportunities'] if audit['source_status'] == 'AVAILABLE' else []
    status = 'RESEARCH_WITH_EMERGING_CANDIDATES' if opportunities else 'RESEARCH_DRAFT_ONLY'
    now = utc()
    counts = {'raw_items': len(audit['records']), 'claims': len(result['claims']),
              'opportunities': len(opportunities), 'request_attempts': audit['request_attempts'],
              'raw_http_responses': audit['response_count'], 'parsed_feed_responses': audit['parsed_feed_responses']}
    ledger = {'run_id': 'indiehackers-evidence-v1', 'status': status, 'source_status': audit['source_status'],
              'criteria': config['criteria_file'], 'criteria_sha256': config['criteria_sha256'],
              'counts': counts, 'capture_audit': {k: v for k, v in audit.items() if k != 'records'},
              'raw_items': audit['records'], 'claims': result['claims'], 'evaluations': result['evaluations'],
              'opportunities': opportunities, 'gaps': list(dict.fromkeys(gaps)),
              'provenance_limit': 'Unofficial mirror; not independently verified IndieHackers primary content or paid revenue.'}
    write_json(out / 'evidence_ledger.json', ledger)
    (out / 'indiehackers_evidence.jsonl').write_bytes(''.join(
        json.dumps(r, ensure_ascii=False, allow_nan=False) + '\n' for r in audit['records']).encode('utf-8'))
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=['product', 'founder', 'tier', 'verdict', 'evidence_ids'], lineterminator='\n')
    writer.writeheader()
    for opp in opportunities:
        writer.writerow({k: json.dumps(opp[k]) if k == 'evidence_ids' else opp[k] for k in writer.fieldnames})
    (out / 'opportunities.csv').write_bytes(stream.getvalue().encode('utf-8'))
    write_json(out / 'terminal_checkpoint.json', {'state': 'FINALIZED_OFFLINE_SOURCE_STOPPED', 'finalized_at': now,
               'status': status, 'source_status': audit['source_status'], **counts,
               'note': 'acquisition_checkpoint.json is the original seed-stage checkpoint; requests/checkpoint.json is the final per-request failure. No further fetch.'})
    report = f'''# IndieHackers live evidence v1 — GAP report

Ngày 02/11/2026. **{status}**. Thu thập live đã dừng; phần tổng hợp này hoàn toàn offline.

| Metric | Kết quả |
|---|---:|
| HTTP attempts / raw HTTP responses | {audit['request_attempts']} / {audit['response_count']} |
| RSS/Atom responses parse hợp lệ | {audit['parsed_feed_responses']} |
| Raw economic records giữ lại | {counts['raw_items']} |
| Claims | {counts['claims']} |
| Opportunities | {counts['opportunities']} |

## Nguồn và coverage thực tế

Chỉ request hostname `feed.indiehackers.world`. Root trả HTTP 200 HTML và tự nhận
là **unofficial IndieHackers feed**. `/posts.rss` và tham số `q` được tìm thấy
trong chính raw root; query plan được khóa trước request RSS. Không mở liên kết
bài đích, redirect, stylesheet/CDN, IndieHackers chính, Product Hunt hay blog.

Query **AI agent** trả HTTP 500 cả hai lần thử. Hai error HTML được lưu nguyên
byte cùng hash/meta/log; không parse thành RSS hoặc claim. Những query còn lại
**Claude Code, Codex, AI automation, MRR report: NOT_RUN** sau lỗi nguồn bền vững.
Tổng ba attempts gồm root một lần và query hai lần, không phải ba nguồn hay
ba economic records. Nguồn lỗi khác với feed được nhận diện nhưng rỗng.
Không kết luận thị trường không có T2, chỉ chưa quan sát được ở lượt này.

## T2 evaluation và GAP

Không có feed entry để trích/review product, founder, amount, currency và ba kỳ
report. Vì vậy không có T2, không có EMERGING; không tạo record cho đủ target
10–15. Revenue tự khai đạt T2 trong test synthetic chỉ chứng minh policy hoạt
động, không phải evidence live. Không có T1/verified payment được quan sát.
T3 chỉ HYPED; không được dùng lấp transactional Top 5.

T0 MVP lịch sử giữ nguyên; lượt này không đo T+7/T+14 và không thay đổi cohort.
Thiếu longitudinal tiếp tục là GAP, không ngăn T2 riêng theo policy mới.
Không có cơ sở đặt buyer/payment/trend legacy present flags thành true.

GAP codes: {', '.join(ledger['gaps'])}.

## Kiểm tra và giới hạn

Offline suite: **{tests['tests_run']} PASS**, failures=0, errors=0, socket creation
bị chặn; log SHA-256 được kiểm trên byte file. [Test report](offline-tests/offline_tests.json).
Kiểm hash của cả ba response, đối chiếu request/ingress/meta và frozen protocol;
evaluator test positive/negative T2, RSS/Atom parser, host scope, lỗi HTTP và
empty/error distinction. Không thực hiện model smoke test mới cho role thứ 14;
TOML được parse offline với đúng năm field đã verify. Sáu hook command giữ nguyên.
T2 field normalization vẫn cần human review; merger không xác thực transaction
documents để nhận T1. Chưa production-ready.

`acquisition_checkpoint.json` là checkpoint seed cũ; `terminal_checkpoint.json`
là trạng thái tổng hợp cuối (3 attempts, source stopped). Các checkpoint/log raw
ban đầu giữ nguyên. Config/criteria hiện tại được pin khi tổng hợp; protocol
trước request nằm riêng, không giả rằng config được ghi trước acquisition.

Không gọi API trả phí/token/login. Không có model API call riêng cho fetch/parse;
không có số liệu billing tổng phiên nên không tuyên bố chi phí phiên bằng 0 USD.

## Bước tiếp theo cần duyệt

1. Duyệt một lần kiểm tra lại đúng RSS host sau khi dịch vụ phục hồi, vẫn bounded
   retry/query order và tối đa 15 records. Không tự retry thêm ở phiên này.
2. Hoặc cung cấp/duyệt URL feed public cụ thể cùng hostname để kiểm tra ở lượt mới.
   Blog/company domain và `indiehackers.com` chưa được duyệt; không tự fallback.
3. Nếu có entries, review ít nhất ba actual revenue observations cùng entity,
   cùng metric/currency/cadence với raw field mapping trước EMERGING; T1 cần
   chứng từ và xác minh riêng. Giữ lịch T+7/T+14 của cohort MVP độc lập.

[Ledger](evidence_ledger.json) · [Manifest](run_manifest.json) · [Opportunities](opportunities.csv).
'''
    (out / 'live_evidence_report.md').write_bytes(report.encode('utf-8'))
    dashboard = f'''# AI Money-Trend — IndieHackers evidence v1

**{status}** — source unavailable, 02/11/2026.

| Metric | Count |
|---|---:|
| Retained raw economic records | {counts['raw_items']} |
| Claims | {counts['claims']} |
| Opportunities | {counts['opportunities']} |
| HTTP attempts / saved responses | {audit['request_attempts']} / {audit['response_count']} |
| Valid RSS/Atom responses | {audit['parsed_feed_responses']} |

## Verdict distribution (business candidates)

| Verdict | Count |
|---|---:|
| PROVEN | 0 |
| EMERGING | {len(opportunities)} |
| HYPED | 0 |

## Top Opportunities

Không có. Chưa nhận được RSS hợp lệ để review T2. HTTP 500 không phải feed rỗng.

## GAP summary

- Root 200 HTML; query AI agent 500 hai lần. Chỉ feed.indiehackers.world được request.
- Bốn keyword còn lại NOT_RUN; target 10–15 MRR records chưa đạt.
- Không có reviewed T2 hoặc T1 quan sát được. Không kết luận thị trường không có proof.
- T0 lịch sử giữ nguyên; chưa có T+7/T+14. T2 có thể EMERGING theo criteria v2,
  không được gọi self-report là verified payment hoặc growth đã kiểm chứng.

[Run report](artifacts/indiehackers-evidence-v1/live_evidence_report.md) ·
[Ledger](artifacts/indiehackers-evidence-v1/evidence_ledger.json) ·
[Manifest](artifacts/indiehackers-evidence-v1/run_manifest.json) ·
[CSV](artifacts/indiehackers-evidence-v1/opportunities.csv).

[Previous GitHub/HN run: 29 records, 8 claims, 0 opportunities](artifacts/live-evidence-v1/live_evidence_report.md).
[Previous offline baseline](artifacts/production-v1/production_run_report.md).
Không chạy thêm, không production-ready. Chờ human review.
'''
    (root / 'dashboard.md').write_bytes(dashboard.encode('utf-8'))
    files = [p for p in out.rglob('*') if p.is_file() and p.name != 'run_manifest.json']
    manifest = {'run_id': 'indiehackers-evidence-v1', 'run_kind': 'live_capture_then_offline_finalize',
                'status': status, 'source_status': audit['source_status'], 'finalized_at': now,
                'acquisition_finished_at': summary['finished_at'], 'allowed_source_hosts': ['feed.indiehackers.world'],
                'additional_live_run': False, **counts, 'opportunity_verdicts': [o['verdict'] for o in opportunities],
                'query_status': audit['query_status'], 'gaps': ledger['gaps'],
                'criteria_sha256': config['criteria_sha256'], 'config_sha256': sha(config_path),
                'test_report': tests_path.relative_to(root).as_posix(), 'test_count': tests['tests_run'],
                'test_report_sha256': sha(tests_path), 'source_sha256': tests['source_sha256'],
                'finalizer_sha256': sha(Path(__file__)), 'dashboard_sha256': sha(root / 'dashboard.md'),
                'artifacts_sha256': {p.relative_to(out).as_posix(): sha(p) for p in sorted(files)},
                'production_ready': False}
    write_json(out / 'run_manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    with patch.object(socket, 'socket', side_effect=AssertionError('offline finalizer forbids network')):
        result = finalize()
    print(json.dumps({k: result[k] for k in ('status', 'source_status', 'raw_items', 'claims', 'opportunities', 'test_count')}))
