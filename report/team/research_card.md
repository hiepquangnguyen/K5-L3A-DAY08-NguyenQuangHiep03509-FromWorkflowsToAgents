# Research card

File này nằm cố định ở `report/team/research_card.md`; `python -m lab8.check_submission` đọc cột "Nhóm điền" bằng máy.

Phần này nối tiếp phần mini research ở buổi lý thuyết (slide 62–63). Chọn **một** câu R1–R4, điền 6 dòng, rồi biến nó thành **một ablation** chạy được trong lab: giữ nguyên model (MockLLM), tool, seed, corpus và giá, chỉ thay đổi một biến.

| Câu | Nguồn (thư viện tham khảo, slide 68–69) | Câu hỏi gợi ý cho lab |
| --- | --- | --- |
| R1 · Scaling | Google Research 2026, *Towards a Science of Scaling Agent Systems* | Task claims chủ yếu tuần tự hay song song được? Dự đoán thêm investigator sẽ làm pass rate và cost/success thay đổi thế nào. |
| R2 · Failure taxonomy | MAST, NeurIPS 2025, *Why Do Multi-Agent LLM Systems Fail?* | Các trial fail của swarm (seed 55) thuộc nhóm nào: lỗi giao việc, lệch mục tiêu, hay lỗi kiểm chứng? |
| R3 · Architecture choices | AgentArch, AACL 2026 | Nếu đổi topology mà giữ nguyên mọi thứ khác, biến nào phải cố định để kết luận còn đúng? |
| R4 · Evaluation confounders | EMNLP 2026, *Rethinking Evaluation of MAS Efficiency* | Làm sao chứng minh chênh lệch giữa A/B/C/D là do topology, không phải do prompt, tool hay seed? |

## Phiếu của nhóm

Điền vào cột cuối. Không xóa hai cột đầu.

| Field | Hướng dẫn | Nhóm điền |
| --- | --- | --- |
| CÂU | R1 / R2 / R3 / R4 | R1 |
| SOURCE | Paper/blog, năm, URL, loại bằng chứng (benchmark, production report, blog kinh nghiệm) | Google Research (2026), *Towards a Science of Scaling Agent Systems* (slides 15, 24, 33, 41 — empirical scaling benchmark trên agent systems) |
| CLAIM | Một kết luận gốc của nguồn. Không viết rộng hơn phạm vi paper | Multi-agent / delegation chỉ có lợi khi bài toán tách song song được; trên task suy luận tuần tự, thêm điều phối agent không cải thiện độ chính xác (thậm chí giảm 39–70% ở biến thể MAS) và tăng chi phí điều phối |
| BOUNDARY | Model / dataset / setup giới hạn kết luận đó | Kết luận đo trên các benchmark của Google Research với LLM thực và độ trễ thực; trên LogiX-VN bị giới hạn bởi MockLLM (seeded hash), 14 public claims và bảng giá mô phỏng (`latency: unavailable`) |
| HYPOTHESIS | Nếu đổi shape A→B (hoặc bật/tắt một thành phần), metric X sẽ đổi theo hướng nào, khoảng bao nhiêu | Khi chuyển từ `workflow` (tuần tự trực tiếp) sang `orchestrator` (thêm lớp lập kế hoạch + investigator read-only qua `handoff.v1`), `pass_rate` giữ nguyên ở `1.000` (vì cùng logic DB và `compute_compensation`), nhưng `cost_per_success_vnd` sẽ tăng khoảng 2× do thêm lượt gọi `MockLLM` (`plan`, `investigate`) và tool đọc |
| METHOD | Biến giữ cố định: model, tools, seed, corpus, giá, evaluator. Biến duy nhất được thay đổi: … | Giữ cố định: `MockLLM`, cùng bộ tool đọc (`src/config/tools.manifest.v1.1.yaml`), `seeds=[11,22,33,44,55]`, `data/public_claims.jsonl` (14 claims), `config/pricing.yaml`, `as_of=2026-11-15`, `lab8.metrics`. Biến duy nhất thay đổi: topology từ `workflow` sang `orchestrator` (thêm handoff + investigator read-only) |
| FAILURE / METRIC | Một lỗi dự kiến và cách đo nó: pass rate, pass^5, variance, cost/success, leak, bypass | Rủi ro: investigator hoặc trace mang theo `parent_secret`/PII qua ranh giới handoff (`secret_leak > 0`), hoặc chi phí/bước tăng vô ích. Đo bằng `pass_rate`, `pass_5`, `seed_variance`, `cost_per_success_vnd`, `mean_model_calls`, `mean_tool_calls`, `secret_leak` |

## Kết quả ablation

- Lệnh đã chạy (copy nguyên văn): `python -m lab8.benchmark --shapes workflow,single,orchestrator,swarm --cases data/public_claims.jsonl --seeds 11,22,33,44,55 --out reports/benchmark.json`
- Run id / file report: `src/reports/benchmark.json` (70 trial cho mỗi shape, ví dụ `R-workflow-C-001-s11`..`R-workflow-C-014-s55` so với `R-orchestrator-C-001-s11`..`R-orchestrator-C-014-s55`)
- Kết quả so với hypothesis (đúng / sai / không kết luận được), kèm số liệu: **Đúng với hypothesis.** `workflow` đạt `pass_rate = 1.000`, `pass_5 = 1.000`, `seed_variance = 0.000000`, `cost_per_success_vnd = 28.86`, `mean_model_calls = 1.00`, `mean_tool_calls = 2.79`. Khi chuyển sang `orchestrator` (thêm investigator layer), `pass_rate = 1.000` và `pass_5 = 1.000` không đổi, nhưng `cost_per_success_vnd` tăng lên `57.77` VND (+100.2%, `mean_model_calls = 2.93`, `mean_tool_calls = 5.57`), với 0 `secret_leak` và 0 `approval_bypass`. Ngoài ra ở `single` (ReAct), `cost_per_success_vnd = 49.52` VND và `mean_steps = 6.50`.
- Giới hạn: MockLLM không phải model sản xuất, latency là `unavailable`. Số claim public nhỏ (14 claims) nên chưa phản ánh hết trường hợp ticket mơ hồ thực tế nơi LLM thực có thể sai lệch nhiều hơn.

Muốn đi xa hơn một ablation để lấy điểm cộng thì xem [docs/bonus_topics.md](../../docs/bonus_topics.md).
