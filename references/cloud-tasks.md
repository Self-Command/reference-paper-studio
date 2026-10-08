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
# 本地传输与云端任务

本地仅执行以下传输命令（需要 Python 3.10+、Git 和已登录的 GitHub CLI）：

```text
python scripts/paper.py submit --root INPUT_DIRECTORY --request request.json
python scripts/paper.py status --task my-model-proof
python scripts/paper.py status --run RUN_ID
python scripts/paper.py fetch --run RUN_ID --output DOWNLOADED_ARTIFACTS
```

`--repo OWNER/REPO` 为全局参数，须放在 `submit/status/fetch` 之前。默认仓库为 `Self-Command/reference-paper-studio`，提交前要求仓库私有。任务 ID 唯一；重新提交使用新 ID，避免覆盖历史输入。

输入目录中的请求示例：

```json
{
  "id": "my-model-proof",
  "stage": "export",
  "document_kind": "model",
  "manuscript": "model.md",
  "metadata": "metadata.json",
  "profile": "profile.json",
  "expected_equations": 30,
  "files": ["model.md", "metadata.json", "profile.json"]
}
```

所有文件使用相对于输入目录的路径与 `/` 分隔符。`files` 必须逐项列出图片、文献库、参考论文、规则证据、模型验证报告和证据清单；不支持通配符、目录上传、远程图片或越界路径。提交器复制这些文件到私有 `request/任务ID` 分支，附 SHA-256 后触发默认分支工作流。工作流代码与输入提交分别检出，防止输入分支替换处理程序。

阶段：`reference` 需要 `reference_evidence` 指定规则证据 JSON；`review` 需要 `manuscript`；`export` 需要 `manuscript`、`metadata`、`profile`。元数据采用 `title/authors/affiliation/abstract/keywords` 加 `_zh/_en` 后缀。作者信息仅使用真实用户提供值，允许留空。可选 `bibliography` 接受 Pandoc 支持的文献库，顺序编码在共同 AST 中解析一次。原稿的 `[1]` 型文献条目直接保留并检查断引。

完整论文使用 `document_kind: paper`，并提供 `model_evidence`：包括 `status: passed`、`author_approved: true`、`model`、`report`、两者 SHA-256，以及每条定量主张对应的 `source` 和 SHA-256。技能仍需实际阅读报告，不能仅凭字段为真宣称数学正确性。模型格式校样用 `document_kind: model`，不宣称验证通过。

产物中的 `acceptance.json` 分别记录构建、自动检查和视觉审阅状态。两套 PDF 分别为 XeLaTeX 与 LibreOffice Word 兼容校样；PNG 来自云端 Poppler。本地只查看下载的图片，不运行任何渲染器。视觉审阅记录必须指明运行、PDF 与 PNG 指纹、检查页码和发现的问题；存在问题应修改源文件后重新提交云端。

手动触发、轮询与下载不自动完成写作、投稿或发布。Actions 产物默认保留 30 天，需保存时及时下载。安装包不含私人模型和参考论文。

