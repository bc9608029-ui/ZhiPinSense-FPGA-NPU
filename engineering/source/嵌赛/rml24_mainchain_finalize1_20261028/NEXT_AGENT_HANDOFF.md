# 唯一入口

先读 `docs/HANDOFF_MAINCHAIN_FINALIZE1.md`，再运行：

```powershell
python scripts/audit_release.py
```

当前结论是 `PROMOTION_CANDIDATE_OFFLINE_PACKAGE_READY_TARGET_ACCEPTANCE_PENDING`。
不得跳过目标板 C++ 构建、24 项 smoke、物理触控和恢复验证，也不得直接覆盖正式服务。
