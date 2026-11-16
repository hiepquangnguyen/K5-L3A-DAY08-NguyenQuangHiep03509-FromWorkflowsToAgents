# Team

## Thông tin nhóm

- Tên nhóm: NguyenQuangHiep03509 (nhóm 1 thành viên)
- Lớp: L3A
- Repo nhóm: `K5-L3A-DAY08-NguyenQuangHiep03509-FromWorkflowsToAgents` (xem [SUBMISSION.md](SUBMISSION.md))
- URL repo, nhánh nộp, commit chốt: `https://github.com/hiepquangnguyen/K5-L3A-DAY08-NguyenQuangHiep03509-FromWorkflowsToAgents`, nhánh `main`, commit `906eb33`

## Thành viên

| STT | Họ tên | MSSV | Email | GitHub | Vai trò |
| --: | ------ | ---- | ----- | ------ | ------- |
|   1 | Nguyễn Quang Hiệp | 2A202603509 | hiepqn1445@gmail.com | hiepquangnguyen | Toàn bộ hệ thống (workflow, single, orchestrator, test, benchmark, bonus B4, báo cáo) |

Gợi ý chia vai:

- Nhóm 6 người: integration; workflow; single agent; orchestrator; ledger/policy/crash; eval/report.
- Nhóm 4 người: workflow + integration; single; orchestrator + handoff; ledger + evaluation.

## Bảng đóng góp

`python -m lab8.check_submission` đọc bảng này bằng máy: giữ nguyên tiêu đề `## Bảng đóng góp` và các cột. Mỗi người một dòng: commit có nội dung và ít nhất một test đã thêm hoặc sửa.

| Người | Vai | Commit | Test đã thêm hoặc sửa |
| --- | --- | --- | --- |
| Nguyễn Quang Hiệp | Toàn bộ (3 shapes, durability/handoff verification, benchmark, bonus B4, báo cáo) | 906eb33 | `src/tests/test_student_shapes.py`, `src/tests/test_bonus_b4.py` |

## Cá nhân

Mỗi thành viên đồng thời tạo một báo cáo riêng trong `report/` theo dạng:

```text
report/team/MSSV_HoTen.md
```

Ví dụ: `report/team/20241234_NguyenVanAn.md`.

Sao chép mục dưới đây cho từng thành viên.

## 2A202603509_NguyenQuangHiep

### Phần việc phụ trách

- Cài đặt và hoàn thiện cả 3 kiến trúc `workflow`, `single`, `orchestrator` (`src/lab8/shapes/*.py`).
- Viết bộ test kiểm tra biên bảo mật, approval, stacking, homoglyph và 3 điểm crash (`src/tests/test_student_shapes.py`).
- Thực hiện benchmark, crash test, ablation R1 và toàn bộ Bonus B4 (`src/bonus/*.py`, `src/tests/test_bonus_b4.py`).
- Hoàn thiện bộ báo cáo (`group_report.md`, `decision_adr.md`, `research_card.md`, `bonus_report.md`, `2A202603509_NguyenQuangHiep.md`).

### Đóng góp cụ thể

- Cài đặt tách bạch ranh giới code/model cho `workflow.py`, `single.py` (`run_react`, `max_steps=8`, đếm `Budget`), và `orchestrator.py` (`make_handoff`, `run_readonly_investigators`, trace sanitized handoff).
- Xây dựng gói Bonus B4 gồm `rules_only`, `swarm_pruned`, `orchestrator_no_investigator`, `workflow_no_policy_guard` và mô-đun thống kê chuẩn thư viện chuẩn (`bootstrap_pass_rate_ci`, `mcnemar_paired_test`, `sign_test_paired_metric`).

### Bằng chứng

- Commit: `906eb33`
- Test: `src/tests/test_student_shapes.py`, `src/tests/test_bonus_b4.py` (`78 passed` cổng host, `248 passed` ma trận student).
- Reports: `src/reports/crash.json` (`20/20`), `src/reports/benchmark.json`, `src/reports/bonus_ablation.json`.
