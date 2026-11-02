# Kế hoạch T+7 / T+14 — chưa chạy, chưa cài lịch tự động

Ngày lập: 02/11/2026. Múi giờ trình bày: **Asia/Saigon (UTC+7)**.
Chuẩn bị T0 trong phiên được duyệt này chỉ đọc archive offline; không gọi network,
tạo scheduler, sửa archive gốc hoặc tạo trend_t7.jsonl/trend_t14.jsonl. Mỗi lượt tương lai cần người
dùng duyệt. Hiện vẫn **chỉ một snapshot T0; T+7/T+14 null — GAP**.

## Script chuẩn bị T0 được duyệt

`python scripts/prepare_t7_snapshot.py` đóng băng đúng 15 records từ MVP vào
`artifacts/t7-baseline/snapshot_t0.jsonl`, kèm manifest hash và README về GAP.
Script kiểm pin manifest MVP, hash toàn bộ artifact gốc, metadata và mapping
record/counter về raw trước khi xuất. Nếu output đã tồn tại thì từ chối ghi đè.
Nó không fetch counters hiện tại, không đổi timestamp T0 thành thời gian chuẩn
bị và không chạy T+7. Dữ liệu thiếu giữ null, counter thực bằng 0 giữ nguyên 0.
HN có points/num_comments; GitHub giữ followers và hai labeled issue counters
đúng tên nguồn, không thay thế chúng cho stars/total issues/issue comments.
Vì vậy đây là **BASELINE_PREPARED_WITH_GAPS**, không phải baseline đủ cho mọi
metric được yêu cầu. Thu metric GitHub còn thiếu cần một mốc quan sát mới có
timestamp thật; không backfill vào T0 lịch sử.

## Cohort đóng băng: đúng 15 records MVP

Nguồn gốc: `artifacts/mvp-v1/evidence_ledger.json`, `raw_items[0..14]`;
đối chiếu `artifacts/mvp-v1/run_manifest.json` và raw responses bằng SHA-256.
`artifacts/live-evidence-v1/trend_baseline.jsonl` giữ lại cùng 15 records và
tham chiếu 8 claims lịch sử. Không thay bằng 14 GitHub issues/15 HN records của
lượt discovery mới, không dựng lại 12 case cloud đã mất.

| Evidence ID | Định danh cohort cố định |
|---|---|
| E01 | `vercel/ai` |
| E02 | `microsoft/ai-agents-for-beginners` |
| E03 | `activepieces/activepieces` |
| E04 | `FlowiseAI/Flowise` |
| E05 | `reworkd/AgentGPT` |
| E06 | `bojieli/ai-agent-book` |
| E07 | `addyosmani/agent-skills` |
| E08 | `zai-org/Open-AutoGLM` |
| E09 | `ashishpatel26/500-AI-Agents-Projects` |
| E10 | `NirDiamant/GenAI_Agents` |
| E11 | HN `46990729` |
| E12 | HN `48500012` |
| E13 | HN `47460525` |
| E14 | HN `46987559` |
| E15 | HN `46515696` |

Cohort gồm **10 repos và 5 HN stories**, không gồm GitHub issue cụ thể. Giữ
stable ID, source và T0 của từng record; không thay thành viên khi biến mất
khỏi search hoặc kết quả mới “tốt hơn”. Chuyển tên repo phải có evidence nối
identity; không tự coi repo mới là bản thay thế.

## Lịch đề xuất

| Mốc | GitHub retrieval anchor | HN retrieval anchor |
|---|---|---|
| T0 đã có | 02/11/2026 10:01:40.308906 | 02/11/2026 10:01:44.931800 |
| T+7 dự kiến | **09/11/2026 10:01:40.308906** | **09/11/2026 10:01:44.931800** |
| T+14 dự kiến | **16/11/2026 10:01:40.308906** | **16/11/2026 10:01:44.931800** |

Các anchor tương ứng 03:01:40/03:01:44 UTC. Đây là thời điểm mục tiêu tính từ
timestamp thật, không cam kết HTTP hoàn thành đúng microsecond. Đề xuất dung sai
±1 giờ, khóa trước lần đo; ghi actual retrieval time và khoảng cách thực. Nếu
lỡ cửa sổ, đánh dấu LATE/MISSED, không sửa ngày hoặc gọi mốc muộn là đúng T+7.
Không tự chạy sớm hoặc bù số liệu; lịch này không tạo cron/automation.

## Metric: có gì tại T0, có gì chưa thể đo delta

| Metric mong muốn | T0 thực có | Cách dùng hợp lệ ở T+7/T+14 |
|---|---|---|
| Số comment HN / điểm HN cho cùng story | Có `num_comments` và `points` cho 5 IDs | So sánh cùng ID/field sau khi xác nhận semantics tương thích; tính net delta, không tự gọi là số comment mới |
| Số star mới cho cùng GitHub repo | Không có `stargazers_count` được xác minh tại T0 | Không tính delta từ giá trị null. Chỉ thu total được xác minh khi được duyệt; mốc đầu có số thật là baseline của metric mới, không giả thành T0 cũ |
| Số issue mới cho cùng repo | Không có total-issue baseline hoặc danh sách issues tại T0 | Có thể đề xuất đếm event `created_at` trong từng khoảng cố định với coverage đầy đủ; đây là interval event count, không trừ một T0 total giả |
| Số comment mới cho cùng GitHub issue | Cohort cũ không có issue IDs/comment counts | Chưa đủ cơ sở. Muốn theo dõi issues phải duyệt danh sách issue cố định và T0 mới của series đó; không thay cohort cũ bằng issues discovery |

Raw GitHub embedded JSON có các số `followers`, `help_wanted_issues_count`,
`good_first_issue_issues_count`; không được tuyên bố raw hoàn toàn không có số.
Nhưng **không đổi tên `followers` thành stars** khi chưa xác minh semantics;
hai issue-count phụ cũng không phải tổng issue mới. Không truy hồi hay bịa
stargazers_count/total issues/comments của ngày 02/11 để lấp chỗ trống.

Năm HN metric gốc để đối chiếu (không phải kết quả follow-up):

| HN ID | T0 points | T0 num_comments |
|---|---:|---:|
| 46990729 | 2346 | 951 |
| 48500012 | 1467 | 536 |
| 47460525 | 1274 | 618 |
| 46987559 | 953 | 750 |
| 46515696 | 879 | 1353 |

Raw locators: `hits[i].points`, `hits[i].num_comments` trong response HN của
MVP; normalized ledger gọi num_comments là `comments`. T0 GitHub nằm trong
`payload.blackbirdSearchRoute.results[i]`. Luôn giữ mapping rõ ràng, không trộn
điểm HN, comment HN, repo stars và issue counts thành một chỉ số tăng trưởng.

## Query và sampling method

Giữ nguyên query và first-page sampling của MVP khi chạy kiểm tra discovery
song song với cohort audit (chỉ khi được duyệt):

- `https://github.com/search?q=ai+agent&type=repositories`
- `https://hn.algolia.com/api/v1/search?query=ai%20agent&tags=story&hitsPerPage=5`

Query giống nhau **không bảo đảm cùng 15 thành viên**, vì thứ hạng có thể đổi.
Phải đối chiếu với danh sách cohort ở trên. Record cũ không còn trên trang trả
về: để value/delta=null, ghi lý do NOT_RETURNED, không điền bằng record mới.
Không đổi sort, page, filter hoặc lấy best-match mới làm bằng chứng cùng cohort.

Đề xuất đọc trực tiếp stable IDs trên api.github.com/hn.algolia.com là một
phương pháp bổ sung cần trình endpoint và mapping field để duyệt trước lượt
đo. Domain đã được phép không tự xác nhận endpoint/semantics tương thích. Nếu
method thay đổi, ghi method_changed=true; không tự đánh dấu comparable=true
hoặc TREND_EVIDENCE=true. Không mở Product Hunt/IndieHackers/company blog chỉ
vì đang thực hiện lịch T+7.

## Công thức và giới hạn so sánh

- Với cumulative counter đã đo thật và tương thích: delta = value_T7 - value_T0;
  tại T14 lưu thêm value_T14 - value_T7 và value_T14 - value_T0.
- Net comment/star delta có thể âm do xóa/điều chỉnh; không clamp về 0. Nó không
  bằng số event mới. Muốn đếm event mới phải có timestamps và coverage phù hợp.
- Đề xuất issue event windows `(T0,T7]`, `(T7,T14]` cùng repo và query cố định.
  Loại pull requests, dedupe stable issue ID, kiểm tra pagination/index completeness.
  Nếu quota/rate-limit không cho đủ coverage thì để count=null hoặc nêu partial;
  không coi số record đã lấy là tổng issues mới. Không fetch vô hạn để lấp quota.
- Không có T0 hoặc hai đầu khác field/unit/method: delta=null, comparable=false,
  ghi GAP. Nếu đo metric GitHub mới ở T+7, so T+14 với mốc đó chỉ là series mới;
  không đổi ngày baseline thành 02/11 hoặc coi đủ trend từ T0 cũ.

Tiêu chí hiện tại yêu cầu query/sampling/metric khóa trước T0. MVP chưa có
protocol trend đầy đủ cho mọi metric đề xuất, nên các so sánh thu được có thể
chỉ là mô tả hậu kiểm; hai snapshot không tự sửa được thiếu sót pre-registration.
Không bật TREND_EVIDENCE=true hoặc EMERGING chỉ vì tới ngày T+7.

## Output dự kiến, không tạo file ngay

- `artifacts/longitudinal-v1/trend_t7.jsonl`
- `artifacts/longitudinal-v1/trend_t14.jsonl`

Giữ một row cho mỗi thành viên trong 15 IDs, kể cả row thiếu dữ liệu; không
bịa record thay thế. Mỗi row cần: evidence_id, source/stable_id, original_t0,
metric_name/unit, actual_t0_value hoặc null, scheduled/actual_followup_time,
followup_value, delta hoặc null, comparable, method_changed, coverage,
missing_reason và các references raw/hash/locator cho từng mốc. Lưu protocol
hash, source/retrieval times riêng và log mọi request/ingress. File đã xuất phải
gắn đúng lượt, không ghi đè T0 hoặc artifact lịch sử.

Trước mỗi lần: xin duyệt run/endpoint/metric/query/quota, chạy test offline,
kiểm tra hash T0 và method compatibility, rồi mới fetch. Hiện chưa có approval
cho hai lượt, chưa triển khai adapter follow-up và chưa có trend_t7/trend_t14.

Ngay cả khi có longitudinal activity hợp lệ, buyer/payment gate vẫn độc lập:
tăng stars/comments không chứng minh giao dịch, doanh thu hay nhu cầu trả tiền.
Thiếu proof của longitudinal vẫn là GAP. Theo criteria v2 được duyệt riêng,
T2 revenue history có thể EMERGING mà không có T+7/T+14 MVP; tuyệt đối không
gọi T2 là payment proof/T1 hoặc phép đo prospective của cohort này. Mỗi lượt
follow-up dừng sau báo cáo và chờ review, không tự chuyển sang live run khác.
