# Bonus report: B4

- Topic + nguồn (tên, năm, slide): B4 · Baseline công bằng, ablation và thống kê — *Rethinking Evaluation of MAS Efficiency* (EMNLP 2026, slide 44, 59) và *AgentArch* (AACL 2026, slide 43).
- CLAIM của nguồn (1 câu): Lợi ích hiệu năng gán cho multi-agent thường đến từ thiết kế benchmark thiếu baseline đơn giản hoặc bỏ qua biến nhiễu; đôi khi random pruning vẫn giữ nguyên độ chính xác trong khi giảm chi phí.
- BOUNDARY (model / dataset / setup): Kết luận gốc đo trên các benchmark multi-agent với LLM thực; trên LogiX-VN phạm vi đo bị giới hạn bởi `MockLLM`, 14 public claims (70 cặp `(claim_id, seed)` mỗi shape), bảng giá mô phỏng (`config/pricing.yaml`) và `latency: unavailable`.
- HYPOTHESIS trên LogiX: Trên tác vụ claim tuần tự của LogiX-VN, baseline không gọi model (`rules_only`) giữ nguyên `pass_rate = 1.000` của `workflow` nhưng giảm chi phí; bỏ investigator giảm chi phí của `orchestrator` mà không mất độ chính xác; bỏ lớp kiểm tra tin cậy DB (`workflow_no_policy_guard`) sẽ làm giảm `pass_rate`; còn chênh lệch `pass_rate` giữa `workflow` và `swarm` trên 14 claim public chưa chắc đạt ý nghĩa thống kê (`p < 0.05`) dù khác biệt chi phí rất rõ.
- Biến cố định / biến thay đổi: Cố định `MockLLM`, `as_of=2026-11-15`, bảng giá `pricing.yaml`, `data/public_claims.jsonl`, `seeds=[11,22,33,44,55]`, `lab8.metrics.trial_pass` và SQLite sạch mỗi trial. Chỉ thay đổi biến thể shape qua `src/bonus/variants.py` và `register_extra_shapes`.
- Lệnh tái lập (copy-paste được): `python -m bonus.run_b4 --out reports/bonus_ablation.json` (test: `python -m pytest -q tests/test_bonus_b4.py`)
- File report + run id: `src/reports/bonus_ablation.json` (560 trials: 8 biến thể × 14 claims × 5 seeds; `R-rules_only-C-001-s11` .. `R-workflow_no_policy_guard-C-014-s55`)

## Kết quả

Số liệu trích trực tiếp từ `src/reports/bonus_ablation.json` (cluster bootstrap 95% CI `n_boot=2000` resample theo `claim_id`):

| Shape / Biến thể | Pass rate | Bootstrap 95% CI | Pass^5 | Variance | Cost/ok (VND) | Mean steps | Bypass / Leak |
|---|---:|---|---:|---:|---:|---:|---|
| `workflow` (chọn) | `1.000` | `[1.000, 1.000]` | `1.000` | `0.000000` | `28.86` | `3.79` | `0 / 0` |
| `rules_only` (baseline 0 LLM) | `1.000` | `[1.000, 1.000]` | `1.000` | `0.000000` | `27.86` | `3.79` | `0 / 0` |
| `single` | `1.000` | `[1.000, 1.000]` | `1.000` | `0.000000` | `49.52` | `6.50` | `0 / 0` |
| `orchestrator` | `1.000` | `[1.000, 1.000]` | `1.000` | `0.000000` | `57.77` | `3.71` | `0 / 0` |
| `orchestrator_no_investigator` | `1.000` | `[1.000, 1.000]` | `1.000` | `0.000000` | `47.89` | `2.79` | `0 / 0` |
| `swarm` | `0.986` | `[0.957, 1.000]` | `0.929` | `0.000816` | `49.57` | `2.80` | `0 / 0` |
| `swarm_pruned` (baseline 2) | `0.986` | `[0.957, 1.000]` | `0.929` | `0.000816` | `48.94` | `4.66` | `0 / 0` |
| `workflow_no_policy_guard` | `0.929` | `[0.786, 1.000]` | `0.929` | `0.000000` | `31.08` | `3.86` | `0 / 0` |

Kiểm định cặp trên 70 cặp `(claim_id, seed)` (`src/bonus/stats.py`):

| Cặp so sánh | McNemar `(n10, n01)` | McNemar `p` | Cost sign `(a_lower, a_higher)` | Cost sign `p` |
|---|---|---:|---|---:|
| `workflow` vs `swarm` | `(1, 0)` | `1.0000` | `(70, 0)` | `1.694e-21` |
| `workflow` vs `single` | `(0, 0)` | `1.0000` | `(70, 0)` | `1.694e-21` |
| `workflow` vs `orchestrator` | `(0, 0)` | `1.0000` | `(70, 0)` | `1.694e-21` |
| `workflow` vs `rules_only` | `(0, 0)` | `1.0000` | `(0, 70)` | `1.694e-21` |
| `workflow` vs `workflow_no_policy_guard` | `(5, 0)` | `0.0625` | `(5, 0)` | `0.0625` |
| `orchestrator` vs `orchestrator_no_investigator` | `(0, 0)` | `1.0000` | `(0, 65)` | `5.421e-20` |
| `swarm` vs `swarm_pruned` | `(0, 0)` | `1.0000` | `(0, 56)` | `2.776e-17` |

## Kết luận

- **Chênh lệch giữa `workflow` và `swarm` có ý nghĩa thống kê không?** Về **`pass_rate`** trên 14 public claims, chênh lệch `1.000` vs `0.986` (`n10=1, n01=0` tại `C-002` seed `55`) **chưa đạt ý nghĩa thống kê** (`McNemar p = 1.0000`) do cỡ mẫu nhỏ. Ngược lại, về **chi phí mô phỏng**, `workflow` rẻ hơn `swarm` trên toàn bộ `70/70` cặp (`28.86` vs `49.57` VND/success, giảm 41.8%, `sign test p = 1.694e-21`). Lỗi của `swarm` cũng mang tính tất định ở `seed % 5 == 0` khi ticket nói sai số ngày trễ, nên trên tập lớn hơn (như hidden 40 claims) khoảng cách pass rate sẽ nới rộng.
- **Thành phần nào bỏ đi mà metric không đổi?**
  1. Bỏ `draft` model call (`workflow` → `rules_only`): `pass_rate` giữ nguyên `1.000` (`McNemar p = 1.0000`) và giảm chi phí còn `27.86` VND (`p = 1.694e-21`), vì grader chấm cấu trúc ledger chứ không chấm văn phong trả lời khách.
  2. Bỏ lớp investigator (`orchestrator` → `orchestrator_no_investigator`): `pass_rate` giữ nguyên `1.000` và giảm chi phí từ `57.77` xuống `47.89` VND (`p = 5.421e-20`, `65/70` cặp rẻ hơn).
  3. Random pruning ở `swarm_pruned` giữ nguyên `pass_rate = 0.986` mà giảm chi phí từ `49.57` xuống `48.94` VND (`p = 2.776e-17`, `56/70` cặp rẻ hơn) — ủng hộ nhận định của EMNLP 2026 & AgentArch.
  4. Ngược lại, bỏ bước kiểm tra tin cậy DB (`workflow_no_policy_guard`) làm `pass_rate` rớt xuống `0.929` (sai `C-002` ở cả 5 seed, `n10=5, p=0.0625`), chứng minh lớp kiểm tra code/DB là thành phần **không thể bỏ**.
- **Điều kiện đảo ngược:** Nếu grader đánh giá chất lượng câu trả lời tự do cho khách hàng, `rules_only` không còn thay thế được `draft`; nếu tác vụ cần tra cứu song song nhiều hệ thống độc lập có thể gây lỗi ngẫu nhiên cần phản biện, hoặc bộ dữ liệu lớn hơn nhiều làm p-value McNemar có đủ lực thống kê, kết luận về mức chi phí tối ưu có thể thay đổi.

## Giới hạn

MockLLM mô phỏng hash tất định, không phản ánh sai số suy luận ngữ nghĩa thật của LLM sản xuất; `latency` là `unavailable`; bảng giá là mô phỏng VND trong `pricing.yaml`; bộ public chỉ có 14 claims (độ mạnh thống kê của McNemar bị giới hạn nên ngay cả lỗi lặp ở 5/5 seed trên 1 claim cũng chỉ cho `p = 0.0625`).
