# Báo cáo cá nhân — 2A202603509_NguyenQuangHiep

## 1. Thông tin thành viên

- Họ tên: Nguyễn Quang Hiệp
- MSSV: 2A202603509
- Email: hiepqn1445@gmail.com
- GitHub: hiepquangnguyen

## 2. Phần việc phụ trách

Làm việc độc lập (nhóm 1 thành viên), phụ trách toàn bộ lab:
- Cài đặt 3 shape: `src/lab8/shapes/workflow.py`, `src/lab8/shapes/single.py`, `src/lab8/shapes/orchestrator.py`.
- Kiểm thử bổ sung: `src/tests/test_student_shapes.py`.
- Bonus B4: `src/bonus/__init__.py`, `src/bonus/variants.py`, `src/bonus/stats.py`, `src/bonus/run_b4.py`, `src/tests/test_bonus_b4.py`.
- Đo đạc & viết toàn bộ báo cáo (`TEAM.md`, `decision_adr.md`, `research_card.md`, `group_report.md`, `bonus_report.md`).

## 3. Đóng góp cụ thể

- **Commit chính:** `906eb33` (cài đặt 3 shape, test bổ sung, bonus B4 và sinh báo cáo tự động).
- **Quyết định kỹ thuật:**
  - Giữ toàn bộ phần tính tiền trong `compute_compensation` và truyền quote đầy đủ vào `durability.issue_refund(..., crash_at=crash_at)` để host tự trừ phần hoàn trước đó (`T14`) và tự kiểm approval theo `claim_id`; không nuốt `InjectedCrash` (chỉ ghi trace crash rồi `raise`).
  - Ở `single.py`, dùng `run_react(..., max_steps=8, worker=True)` và chủ động gọi `MockLLM.complete` ở mỗi bước `decide` để phản ánh trung thực chi phí vòng lặp ReAct trong `Budget`.
  - Ở `orchestrator.py`, tạo handoff qua `make_handoff` với `facts={}` và danh sách read-only tool (`lookup_order`, `lookup_policy`, `lookup_refund_history`), không đưa `ticket`, `parent_secret`, `raw_headers` vào handoff hay trace.
  - Ở Bonus B4, cài đặt cluster bootstrap 95% CI resample theo `claim_id` (tránh phóng đại ý nghĩa thống kê do 5 seed trên cùng claim phụ thuộc nhau) và exact two-sided McNemar / sign test chỉ bằng thư viện chuẩn Python (`math`, `random`).

## 4. Bằng chứng

- Lệnh kiểm tra cổng host + test bổ sung + bonus: `python -m pytest -q` → `78 passed, 248 deselected`.
- Lệnh ma trận student (`T01`–`T14`): `python -m pytest -q -m student -o addopts=` → `248 passed, 74 deselected`.
- Crash suite: `python -m lab8.crash_test --count 20 --out reports/crash.json` → `crash_safety 20/20`.
- Benchmark 4 shape: `python -m lab8.benchmark --shapes workflow,single,orchestrator,swarm --cases data/public_claims.jsonl --seeds 11,22,33,44,55 --out reports/benchmark.json` (run id dẫn chứng `R-workflow-C-001-s11`).
- Bonus B4 ablation & stats: `python -m bonus.run_b4 --out reports/bonus_ablation.json`.

## 5. Công cụ AI đã dùng

- Sử dụng trợ lý AI lập trình (Antigravity) để hỗ trợ đọc hiểu codebase, thiết kế cấu trúc 3 shape + Bonus B4, viết test case và tổng hợp số liệu từ các file report.
- **Cách tự kiểm tra kết quả:**
  - Đối chiếu trực tiếp từng điều kiện của `docs/business_rules.md` và `docs/contracts.md` với mã nguồn host (`durability.py`, `policy.py`, `metrics.py`, `handoff.py`).
  - Tự chạy lại toàn bộ lệnh `smoke`, `pytest -q`, `pytest -q -m student -o addopts=`, `lab8.crash_test`, `lab8.benchmark`, `bonus.run_b4`, `lab8.check_submission` và kiểm chứng số liệu khớp hoàn toàn với JSON sinh ra trong `src/reports/`.

## 6. Tự đánh giá

- Hoàn thành đầy đủ tất cả hạng mục bắt buộc (`C1`–`C8`) và mở rộng Bonus B4 đúng phạm vi khoa học, không sửa đổi bất kỳ file thước đo nào của host, đạt 100% pass rate và 0 vi phạm bảo mật/approval trên toàn bộ tập kiểm thử công khai.
