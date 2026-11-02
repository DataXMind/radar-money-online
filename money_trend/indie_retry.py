"""One approved retry batch, exactly one GET per fallback URL; no link following."""
import json
import re
from pathlib import Path

from .core import DataError, strict_json, utc, write_json
from .indie_rss import FEED_HOST, parse_feed
from .indie_run import evaluate_reviewed, load, sha, validate_source_config
from .live_shared import LiveClient

RUN = 'indiehackers-retry-v1'
PLAN = [
    {'keyword': 'AI', 'url': f'https://{FEED_HOST}/posts.rss?q=AI'},
    {'keyword': 'MRR', 'url': f'https://{FEED_HOST}/posts.rss?q=MRR'},
    {'keyword': None, 'url': f'https://{FEED_HOST}/posts.rss'},
]
ACCEPT = 'application/rss+xml, application/atom+xml, application/xml, text/xml, text/html'


def capture(root, client_factory=LiveClient):
    """Consumes the one-batch authorization before network, refusing any replay."""
    root = Path(root).resolve()
    config_path = root / 'config/production_v1.json'
    config = load(config_path)
    validate_source_config(config, root)
    source = config['sources']['indiehackers_rss']
    if source.get('retry_exhausted') or source.get('reliability') == 'UNRELIABLE':
        raise DataError('RSS retry exhausted or source UNRELIABLE; no further request authorized')
    out = root / 'artifacts' / RUN
    out.mkdir(exist_ok=False)
    discovery = root / 'artifacts/indiehackers-evidence-v1/requests/001_seed_1_e6198699.body'
    protocol = {'run_id': RUN, 'recorded_at': utc(), 'authorization': 'User approved one simplified three-URL fallback batch in this chat.',
                'allowed_hosts': [FEED_HOST], 'queries': PLAN, 'max_http_attempts': 3,
                'attempts_per_url': 1, 'interval_seconds': 3, 'timeout_seconds': 15,
                'stop': 'First 200 recognized nonempty RSS/Atom; otherwise after third URL. Never retry a URL.',
                'discovery_path': discovery.relative_to(root).as_posix(), 'discovery_sha256': sha(discovery),
                'limits': {'raw_items': 15, 'claims': 8, 'opportunities': 5},
                'criteria_sha256': config['criteria_sha256'], 'config_before_sha256': sha(config_path),
                'state': 'FROZEN_BEFORE_REQUESTS'}
    write_json(out / 'protocol.json', protocol)
    # Persist consumed authorization before GET so an interrupted batch is not restarted.
    source.update(retry_exhausted=True, automatic_refresh=False, enabled=False,
                  retry_batch={'run_id': RUN, 'state': 'STARTED', 'max_http_attempts': 3,
                               'attempts_per_url': 1, 'restart_authorized': False})
    write_json(config_path, config)
    outcomes, records = [], []
    try:
        client = client_factory(out / 'requests', allowed_hosts=(FEED_HOST,), timeout=15,
                                attempts=1, interval=3, max_requests=3, deadline_seconds=120, accept=ACCEPT)
        for index, query in enumerate(PLAN):
            label = f'fallback_{index + 1}'
            result = {**query, 'state': 'REQUEST_FAILED', 'http_status': None, 'feed_entries': None}
            try:
                body, meta = client.get(query['url'], label)
                result.update(http_status=meta['status'], raw_response_path=(out / 'requests' / meta['body_file']).relative_to(root).as_posix(),
                              raw_response_sha256=meta['sha256'])
                entries = parse_feed(body)
                result.update(state='RECOGNIZED_NONEMPTY' if entries else 'RECOGNIZED_EMPTY', feed_entries=len(entries))
                client.log('rss_parse', url=query['url'], state=result['state'], entries=len(entries))
                # These are source-attributed leads; numbers alone never establish T2.
                relevant = [r for r in entries if re.search(r'\bmrr\b|\brevenue\b', r['title'] + '\n' + r['content'], re.I)]
                for entry in relevant[:15]:
                    records.append({**entry, 'source_url': query['url'], 'raw_response_path': result['raw_response_path'],
                                    'raw_response_sha256': meta['sha256']})
                outcomes.append(result)
                write_json(out / 'checkpoint.json', {'state': result['state'], 'outcomes': outcomes, 'request_attempts': client.count})
                if entries:
                    break
            except DataError as exc:
                saved = sorted((out / 'requests').glob(f'*_{label}_*.meta.json'))
                if saved:
                    meta = load(saved[-1])
                    result.update(http_status=meta['status'], raw_response_path=(saved[-1].parent / meta['body_file']).relative_to(root).as_posix(),
                                  raw_response_sha256=meta['sha256'])
                result.update(state='HTTP_ERROR' if result['http_status'] not in (None, 200) else 'INGRESS_OR_REQUEST_ERROR', error=str(exc))
                client.log('rss_ingress_error', url=query['url'], error=str(exc), status=result['http_status'])
                outcomes.append(result)
                write_json(out / 'checkpoint.json', {'state': 'FALLBACK_FAILED', 'outcomes': outcomes, 'request_attempts': client.count})
        all_500 = len(outcomes) == 3 and all(r['http_status'] == 500 for r in outcomes)
        success = any(r['state'] == 'RECOGNIZED_NONEMPTY' for r in outcomes)
        reliability = 'UNRELIABLE' if all_500 else 'SINGLE_NONEMPTY_CAPTURE' if success else 'UNAVAILABLE_OR_EMPTY'
        source.update(reliability=reliability, enabled=success, retry_exhausted=True, automatic_refresh=False)
        source['retry_batch'].update(state='FINISHED', outcomes=[{'url': r['url'], 'state': r['state'], 'http_status': r['http_status']} for r in outcomes],
                                     finished_at=utc())
        for query in PLAN[len(outcomes):]:
            outcomes.append({**query, 'state': 'NOT_RUN_AFTER_SUCCESS', 'http_status': None, 'feed_entries': None})
        summary = {'run_id': RUN, 'finished_at': utc(), 'source_reliability': reliability,
                   'request_attempts': client.count, 'outcomes': outcomes, 'records': records,
                   'additional_retry_authorized': False, 'automatic_refresh': False}
        write_json(out / 'acquisition_summary.json', summary)
        write_json(out / 'checkpoint.json', {'state': 'ACQUISITION_FINISHED', 'source_reliability': reliability,
                                           'request_attempts': client.count, 'additional_retry_authorized': False})
        return summary
    finally:
        # Even an unexpected failure consumes the authorization and stays disabled.
        if source['retry_batch']['state'] == 'STARTED':
            source.update(enabled=False, reliability='INTERRUPTED_REVIEW_REQUIRED')
        write_json(config_path, config)


def report(root):
    """Audit and publish the captured all-500 batch offline, without refetching."""
    root = Path(root).resolve()
    out = root / 'artifacts' / RUN
    if (out / 'run_manifest.json').exists():
        raise FileExistsError('retry report already finalized; no overwrite')
    summary = load(out / 'acquisition_summary.json')
    if (summary['source_reliability'] != 'UNRELIABLE' or summary['request_attempts'] != 3
            or [r['http_status'] for r in summary['outcomes']] != [500, 500, 500] or summary['records']):
        raise DataError('capture differs from all-500 GAP report; evidence review required')
    protocol = load(out / 'protocol.json')
    discovery = (root / protocol['discovery_path']).resolve()
    if (protocol.get('queries') != PLAN or protocol.get('attempts_per_url') != 1
            or protocol.get('max_http_attempts') != 3
            or not discovery.is_relative_to(root / 'artifacts/indiehackers-evidence-v1/requests')
            or sha(discovery) != protocol['discovery_sha256']
            or [r['url'] for r in summary['outcomes']] != [q['url'] for q in PLAN]):
        raise DataError('retry protocol/discovery mismatch')
    config = load(root / 'config/production_v1.json')
    source = config['sources']['indiehackers_rss']
    if source.get('reliability') != 'UNRELIABLE' or source.get('enabled') is not False or source.get('retry_exhausted') is not True:
        raise DataError('failed RSS source must remain disabled and exhausted')
    events = [strict_json(line) for line in (out / 'requests/requests.jsonl').read_text(encoding='utf-8').splitlines()]
    starts = [r for r in events if r.get('event') == 'request_start']
    ingress = [r for r in events if r.get('event') == 'data_ingress']
    if (len(starts) != 3 or [r['url'] for r in starts] != [q['url'] for q in PLAN]
            or any(r['attempt'] != 1 for r in starts) or len(ingress) != 3
            or len({r['request_id'] for r in starts}) != 3
            or {r['request_id'] for r in starts} != {r['request_id'] for r in ingress}):
        raise DataError('retry request/ingress count or plan mismatch')
    for response in ingress:
        body = out / 'requests' / response['body_file']
        meta_path = body.with_suffix('.meta.json')
        meta = load(meta_path)
        if (not body.resolve().is_relative_to((out / 'requests').resolve()) or sha(body) != response['sha256']
                or body.stat().st_size != response['bytes'] or response['status'] != 500
                or response['error_response'] is not True or any(response.get(k) != v for k, v in meta.items())):
            raise DataError('retry raw hash/metadata mismatch')
        if (sum(r['request_id'] == response['request_id'] and r['url'] == response['url'] for r in starts) != 1
                or sum(r['url'] == response['url'] and r['raw_response_path'] == body.relative_to(root).as_posix()
                       and r['raw_response_sha256'] == response['sha256'] for r in summary['outcomes']) != 1):
            raise DataError('retry response does not map to one request/outcome')
    tests_path = out / 'offline-tests/offline_tests.json'
    tests = load(tests_path)
    if (tests['status'] != 'PASS' or tests['failures'] or tests['errors']
            or sha(tests_path.with_name('offline_tests.txt')) != tests['log_sha256']):
        raise DataError('passing byte-verified offline test report required')
    for name, digest in {**tests['source_sha256'], **tests['retry_t7_bundle_sha256']}.items():
        path = (root / name).resolve()
        if (not path.is_relative_to(root) or not (name.startswith(('money_trend/', 'tests/')) and name.endswith('.py')
                or name in ('scripts/retry_indiehackers.py', 'scripts/prepare_t7_snapshot.py',
                            'docs/t7_plan.md', 'config/production_v1.json')) or sha(path) != digest):
            raise DataError('test/source binding mismatch: ' + name)
    baseline = root / 'artifacts/t7-baseline/run_manifest.json'
    t0 = load(baseline)
    rows = [json.loads(line) for line in baseline.with_name('snapshot_t0.jsonl').read_text(encoding='utf-8').splitlines()]
    if t0['raw_count'] != 15 or len(rows) != 15 or t0['network_requests'] != 0 or t0['t7_executed']:
        raise DataError('T0 preparation count/mode mismatch')
    for name, digest in t0['artifacts_sha256'].items():
        if sha(baseline.parent / name) != digest:
            raise DataError('T0 output hash mismatch')
    result = evaluate_reviewed([], [])
    gaps = ['RSS_UNRELIABLE_HTTP_500_ALL_THREE', 'NO_FEED_DATA_OBSERVED', 'NO_REVIEWED_T2_REVENUE_HISTORY',
            'NO_VERIFIED_PAYMENT_PROOF_OBSERVED', 'T7_T14_NOT_OBSERVED', 'GITHUB_T0_METRICS_MISSING']
    ledger = {'status': 'RESEARCH_DRAFT_ONLY', 'source_reliability': 'UNRELIABLE',
              'raw_http_responses': 3, 'raw_items': [], **result, 'gaps': gaps,
              'request_evidence': ingress, 'criteria_sha256': config['criteria_sha256']}
    write_json(out / 'evidence_ledger.json', ledger)
    (out / 'indiehackers_evidence.jsonl').write_bytes(b'')
    (out / 'opportunities.csv').write_bytes(b'product,founder,tier,verdict,evidence_ids\n')
    text = f'''# IndieHackers retry + T+7 preparation

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

**{tests['tests_run']} offline tests PASS**, failures=0/errors=0, socket creation blocked.
Hash test log khớp byte file; đối chiếu ba request/ingress/raw/meta và các hash
baseline. [Test report](offline-tests/offline_tests.json). Giữ nguyên LICENSE
và artifact lịch sử. Không có paid API/model call riêng cho fetch/parse; tổng
billing phiên không được đo nên không khẳng định 0 USD.

GAP: {', '.join(gaps)}.

Dừng RSS do UNRELIABLE. Chờ người dùng review; phương án tiếp theo là duyệt
endpoint/method cho phép đo cohort ngày 09/11, hoặc duyệt nguồn/URL khác riêng.
Giá trị GitHub còn thiếu cần baseline có timestamp mới, không backdate. Không
tự thêm domain hoặc chạy live khác. Chưa production-ready.
'''
    (out / 'retry_report.md').write_bytes(text.encode('utf-8'))
    dashboard = f'''# AI Money-Trend — RSS retry and T+7 preparation

**RESEARCH_DRAFT_ONLY** — 02/11/2026.

| Metric | Result |
|---|---:|
| RSS GET attempts / HTTP 500 responses | 3 / 3 |
| Retained economic records / claims / opportunities | 0 / 0 / 0 |
| PROVEN / EMERGING / HYPED candidates | 0 / 0 / 0 |
| Archived T0 records frozen offline | 15 |
| T+7/T+14 measurements | 0 |

## Top Opportunities

Không có T2/T1 quan sát được: cả AI, MRR và latest feed đều 500.
RSS **UNRELIABLE**, disabled, retry exhausted; không thử lại.

## GAP summary

T0 có HN counters nhưng thiếu verified GitHub stars/total issues/issue comments.
Missing giữ null; không backfill. T+7 chờ **09/11/2026**, chưa chạy hoặc cài lịch.
Không coi lỗi nguồn là feed rỗng hoặc absence of market evidence.

[Retry report](artifacts/{RUN}/retry_report.md) ·
[Ledger](artifacts/{RUN}/evidence_ledger.json) ·
[Baseline](artifacts/t7-baseline/run_manifest.json) · [T+7 plan](docs/t7_plan.md).

[Previous RSS run](artifacts/indiehackers-evidence-v1/live_evidence_report.md).
Offline suite: {tests['tests_run']} PASS. Chờ human review; chưa production-ready.
'''
    (root / 'dashboard.md').write_bytes(dashboard.encode('utf-8'))
    manifest = {'status': 'RESEARCH_DRAFT_ONLY', 'run_kind': 'single_simplified_rss_retry_and_offline_t0_preparation',
                'source_reliability': 'UNRELIABLE', 'finalized_at': utc(), 'acquisition_finished_at': summary['finished_at'],
                'request_attempts': 3, 'raw_http_responses': 3, 'raw_items': 0, 'claims': 0, 'opportunities': 0,
                'allowed_hosts': [FEED_HOST], 'additional_retry_authorized': False,
                'baseline_records': 15, 'baseline_sha256': sha(baseline), 't7_executed': False,
                'criteria_sha256': config['criteria_sha256'], 'config_sha256': sha(root / 'config/production_v1.json'),
                'offline_tests': tests['tests_run'], 'test_report_sha256': sha(tests_path),
                'source_sha256': tests['source_sha256'], 'retry_t7_bundle_sha256': tests['retry_t7_bundle_sha256'],
                'dashboard_sha256': sha(root / 'dashboard.md'), 'gaps': gaps,
                'artifacts_sha256': {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob('*')) if p.is_file()}}
    write_json(out / 'run_manifest.json', manifest)
    return manifest
