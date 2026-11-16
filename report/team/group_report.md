# Báo cáo nhóm — Lab 8 LogiX-VN

## 1. Thông tin nhóm

- Tên nhóm: NguyenQuangHiep03509 (cá nhân — 1 thành viên)
- Thành viên: xem `TEAM.md`
- Commit chốt (trùng `report/team/decision_adr.md`): 906eb33

## 2. Mục tiêu và cách tiếp cận

Bài lab mô phỏng hệ thống xử lý yêu cầu hoàn phí vận chuyển và bồi thường hư hỏng của LogiX-VN qua 4 kiến trúc có mức độ tự chủ tăng dần (`workflow`, `single`, `orchestrator`, `swarm`), cùng chia sẻ một hợp đồng đầu ra `RunResult`, một bộ tool đọc theo allowlist, một bảng giá mô phỏng (`config/pricing.yaml`) và một cổng ghi tiền duy nhất của host (`durability.issue_refund`). Do làm cá nhân toàn bộ bài, tôi tiếp cận theo 4 bước tuần tự: (1) kiểm tra nền tảng host gate và contract (`smoke`, `pytest -q`, đọc `durability.py`, `policy.py`, `handoff.py`, `metrics.py`); (2) cài đặt lần lượt 3 shape `workflow`, `single`, `orchestrator` đảm bảo tách bạch ranh giới code/model và xử lý crash/retry đúng quy tắc; (3) bổ sung test kiểm tra các bẫy ẩn (`approval_claim_mismatch`, `revoked`, stacking max, đơn hủy, homoglyph, cả 3 điểm crash); (4) chạy benchmark công bằng 4 shape × 5 seed, thực hiện ablation R1 & Bonus B4 để ra quyết định kiến trúc bằng số liệu.

## 3. Giải pháp

Cả 3 shape tự cài đặt đều tuân thủ ranh giới code/model trong `docs/architecture.md`:
- **Shape A (`src/lab8/shapes/workflow.py`):** Quy trình Python cố định: `get_claim_view` → kiểm tra thiếu `order_id` (`needs_info`) → `lookup_order` theo `principal_id` (`escalated` nếu không thấy hoặc sai chủ sở hữu) → `compute_compensation` tính tiền từ dữ liệu DB có cấu trúc → `MockLLM.complete(..., purpose="draft")` soạn câu trả lời mô phỏng → nếu quote `> 0`, truyền **quote đầy đủ** và `crash_at` vào `durability.issue_refund` (không trừ trước phần đã hoàn, không nuốt `InjectedCrash`).
- **Shape B (`src/lab8/shapes/single.py`):** Dùng `lab8.runtime.run_react` với `max_steps=8` và `worker=True` để khóa cứng chỉ dùng read tool (`get_claim_view`, `lookup_order`, `lookup_policy`, `lookup_refund_history`, `compute_compensation`). Mỗi bước vòng lặp ghi nhận 1 lượt `MockLLM.complete` vào `Budget`. Kết thúc vòng ReAct, code ngoài vòng lặp mới gọi `durability.issue_refund`.
- **Shape C (`src/lab8/shapes/orchestrator.py`):** Orchestrator đọc `get_claim_view`, lập kế hoạch (`purpose="plan"`), đóng gói `handoff.v1` qua `lab8.handoff.make_handoff` (chỉ gồm trường allowlist, `facts={}`, cấm hoàn toàn `parent_secret`, `raw_headers` và write tools), chạy `lab8.runtime.run_readonly_investigators` (kèm `lookup_refund_history`), tổng hợp rồi orchestrator tự quote và gọi host.
- **Bảo mật & Trace contract v1:** Mọi nhánh thoát sớm (`unknown_claim`, `needs_info`, `escalated`, `denied`) đều trả `RunResult` qua `lab8.shapes.common.finish()` để đảm bảo ghi trace mới khớp `run_id`, tuyệt đối không ghi `ticket` thô, `parent_secret`, `raw_headers`, `phone`, `address`, `internal_note`, `item_name`.

## 4. Kết quả

Số liệu trích từ `src/reports/benchmark.json` (14 public claims × 5 seeds `11, 22, 33, 44, 55` = 70 trial/shape) và `src/reports/crash.json`:

| Shape | Pass rate | Pass^5 | Seed min–max | Variance | Cost/success (VND) | Mean / p95 steps |
|---|---:|---:|---|---:|---:|---:|
| `workflow` | `1.000` | `1.000` | `1.000–1.000` | `0.000000` | `28.86` | `3.79 / 4.0` |
| `single` | `1.000` | `1.000` | `1.000–1.000` | `0.000000` | `49.52` | `6.50 / 7.0` |
| `orchestrator` | `1.000` | `1.000` | `1.000–1.000` | `0.000000` | `57.77` | `3.71 / 4.0` |
| `swarm` | `0.986` | `0.929` | `0.929–1.000` | `0.000816` | `49.57` | `2.80 / 3.0` |

- **Crash safety (`src/reports/crash.json`):** `20/20` kịch bản an toàn (`before_effect`, `after_effect_before_checkpoint`, `after_checkpoint`, `amount_conflict_on_retry`, `retry_without_approval`, `swarm_after_effect_before_checkpoint`).
- **Bộ test tự động:** Cổng host `python -m pytest -q` đạt `78 passed` (gồm cả test mới trong `src/tests/test_student_shapes.py` và `src/tests/test_bonus_b4.py`); ma trận `student` đạt `248 passed`.
- **Self-check hidden:** Thư mục `student_drop/` chưa được phát trong repo nên chưa chạy `hidden_selfcheck.json`.
- **Quyết định & nghiên cứu:** Chọn `workflow` ([decision_adr.md](decision_adr.md)); phiếu ablation R1 ([research_card.md](research_card.md)); kết quả mở rộng B4 với baseline `rules_only`, `swarm_pruned`, cluster bootstrap 95% CI và McNemar/sign test ([bonus_report.md](bonus_report.md)).

## 5. Khó khăn và cách xử lý

1. **Test fixture dùng chung DB SQLite:** Khi viết test `test_stacking_max_cancelled_and_missing_order_homoglyph` trong `src/tests/test_student_shapes.py`, chạy nhiều claim liên tiếp trên cùng một file `.sqlite` khiến `unexpected_ledger_rows` báo lỗi do claim trước để lại dòng trong `refund_ledger`. Cách xử lý: tách mỗi `(shape, claim_id)` thành một file SQLite mới giống cơ chế cô lập của `lab8.benchmark`.
2. **Glob pattern trên Windows PowerShell:** Lệnh `pytest -q tests/test_bonus_*.py` trong PowerShell không tự mở rộng ký tự `*` như bash. Cách xử lý: truyền trực tiếp tên file `tests/test_bonus_b4.py` hoặc chạy `pytest -q` trên toàn bộ thư mục `tests/`.

## 6. Tổng hợp đóng góp

Chi tiết đóng góp cá nhân (1 thành viên đảm nhận toàn bộ bài lab) nằm trong `TEAM.md` (bảng đóng góp) và báo cáo cá nhân `report/team/2A202603509_NguyenQuangHiep.md`.

## 7. Hạn chế và hướng cải thiện

`MockLLM` không phải model sản xuất (output là chuỗi hash cố định theo seed, không mô phỏng sai sót suy luận ngữ nghĩa tự nhiên); `latency` là `unavailable` nên chưa đo được trade-off độ trễ thực giữa `single` (nhiều lượt LLM tuần tự) và `orchestrator`; bảng giá VND chỉ là mô phỏng; bộ public chỉ có 14 claim nên làm giảm độ mạnh kiểm định thống kê McNemar. Hướng cải thiện tiếp theo là chạy đánh giá thêm trên tập hidden 40 claims và tích hợp mô hình độ trễ mô phỏng có phụ thuộc DAG nếu triển khai nhiều investigator song song.

## 8. Tài liệu tham khảo

- Tài liệu đề bài & hợp đồng trong repo: `README.md`, `docs/business_rules.md`, `docs/contracts.md`, `docs/architecture.md`, `docs/metrics.md`, `docs/bonus_topics.md`.
- Google Research (2026), *Towards a Science of Scaling Agent Systems*.
- EMNLP (2026), *Rethinking Evaluation of MAS Efficiency*; AACL (2026), *AgentArch*.
