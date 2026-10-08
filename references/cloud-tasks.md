# 云端任务

仅 `scripts/paper.py submit|status|fetch` 可在本地执行。测试、转换、编译、渲染及所有验收在 Actions。

任务使用 UTF-8 JSON，包含 `id`、`stage`（reference / review / export）、`files`（显式相对路径列表）、`manuscript`、`metadata`、`profile`，可选 `reference_evidence`、`model_evidence`。路径相对于任务文件；只上传清单文件。

```text
python scripts/paper.py submit request.json --repo Self-Command/reference-paper-studio
python scripts/paper.py status --run RUN_ID
python scripts/paper.py fetch --run RUN_ID --output artifacts/RUN_ID
```

输入复制到独立私有任务分支，默认分支保存技能源码。任务工作流校验 input commit、文件指纹与技能版本，并上传运行证据；下载后查看逐页 PNG。不要把构建成功表述为数学证明或视觉验收完成。
失败后读取 Actions 报告，修复源文件并重新提交，绝不改用本地编译。
