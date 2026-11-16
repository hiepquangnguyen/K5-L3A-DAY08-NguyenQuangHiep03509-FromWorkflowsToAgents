# Decision record

Điền sau dấu `:` trên cùng dòng, không xóa nhãn. Giảng viên và `python -m lab8.check_submission` (chạy trong `src/`) đọc các dòng này bằng máy. Không đổi tên hay dời file này khỏi `report/team/`.
`Shape chọn` phải là đúng một trong: `workflow`, `single`, `orchestrator`, `swarm`. Đây là shape được chấm cổng hidden.

- Shape chọn: workflow
- Commit hash: 906eb33
- Run id dẫn chứng: R-workflow-C-001-s11 (tập 70 trial `R-workflow-C-001-s11`..`R-workflow-C-014-s55` trong `src/reports/benchmark.json`)
- Pass rate / pass^5 / seed min-max / variance: 1.000 / 1.000 / 1.000-1.000 / 0.000000
- Cost per success (mô phỏng, VND): 28.86
- Crash safety: 20/20 (src/reports/crash.json)
- Secret leak / approval bypass: 0 / 0 (src/reports/benchmark.json & src/reports/bonus_ablation.json)

## Vì sao shape này

So sánh trên cùng 14 public claims × 5 seeds (`11, 22, 33, 44, 55`), cùng `MockLLM`, cùng tool đọc và cùng `config/pricing.yaml` (`src/reports/benchmark.json`), ba kiến trúc `workflow`, `single` và `orchestrator` đều đạt `pass_rate = 1.000`, `pass^5 = 1.000` và `seed_variance = 0.000000`, vượt qua `swarm` (`0.986`, `pass^5 = 0.929`, `variance = 0.000816`, fail tại `C-002` seed `55`). Chọn `workflow` vì đây là kiến trúc **ít tự chủ nhất nhưng hoàn thành đúng 100% nhiệm vụ**, đồng thời có chi phí mô phỏng thấp nhất (`28.86` VND/success, chỉ `1.00` model call và `2.79` tool calls trung bình mỗi claim — rẻ hơn 41.7% so với `single` `49.52` VND và 50.0% so với `orchestrator` `57.77` VND). Trong `workflow`, toàn bộ tiền bồi thường do code `compute_compensation` tính từ DB có cấu trúc, chỉ truyền quote đầy đủ vào `durability.issue_refund` để host áp dụng trần theo đơn và kiểm tra approval, còn `MockLLM` chỉ soạn câu chữ `draft`.

## Có đáng đổi lấy multi-agent không

**Không đáng** với bài toán xử lý claim của LogiX-VN. Bài toán có luồng phụ thuộc tuần tự chặt chẽ (`get_claim_view` → `lookup_order` → `compute_compensation` → `durability.issue_refund`), nên thêm vòng ReAct (`single`) hay phân rã orchestrator–investigator (`orchestrator`) chỉ tăng `cost/success` lên `49.52`–`57.77` VND mà không tăng `pass_rate`, còn `swarm` lại làm tăng thêm sai số (`REFERENCE_WEAKNESS` tin ticket hơn DB ở `seed % 5 == 0`) và tạo dao động giữa các seed (`variance = 0.000816`). Kết luận này chỉ đảo lại nếu quy trình phát sinh nhiều nhánh điều tra song song thực sự độc lập (ví dụ gọi đồng thời nhiều hệ thống đối soát ngoài) hoặc cần xử lý văn bản đầu vào phi cấu trúc mà DB chưa chuẩn hóa trước khi đi qua cổng duyệt code.

## Trace và bằng chứng

Trace của `workflow` ghi các event tối thiểu: `claim_view` (chỉ `claim_id`, `has_order_id`), `lookup_order` (chỉ 7 field allowlist từ `ORDER_FIELDS`), `quote` (`amount_vnd`, `reason`, `clause_ids`, `parts`), `decision` / `issue_refund` (`ok`, `reason`, `conflict`), và `crash` (chỉ `at: crash_at` trước khi cho `InjectedCrash` lan ra ngoài). Các field cố ý **không** ghi: `parent_secret`, `raw_headers`, `ticket` thô, `phone`, `address`, `internal_note`, `item_name`. Mọi nhánh return sớm (`unknown_claim`, `needs_info`, `escalated`, `denied`) đều gọi `lab8.shapes.common.finish()` để ghi file JSON hợp lệ theo Trace contract v1 tại `src/traces/<run_id>.json`, và không ghi thêm file ngoài thư mục trace. Nếu trace bị đặt ngoài vị trí scanner quét hoặc sai `run_id`, grader fail-closed (`missing_trace` / `invalid_trace` / `trace_run_id_mismatch`) nên đội security chỉ chấp nhận chứng minh sạch secret khi scanner đọc được trọn vẹn mọi file `<run_id>*`.

## Giới hạn

MockLLM không phải model sản xuất (chỉ là hash tất định theo seed, không đo được lỗi hiểu ngôn ngữ thực). Latency để `unavailable`. Không sửa JSON cho đủ 0.75. Bộ public chỉ gồm 14 claim nên chưa bao quát hết phân bố lỗi thực tế như bộ hidden 40 claim.
