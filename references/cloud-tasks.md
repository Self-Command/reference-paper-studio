# 本地传输与云端任务

本地只负责上传清单、查询、下载和查看云端页图，不执行测试、转换、编译、渲染或程序验收。需要Python 3.10+、GitHub CLI和有效登录。

```text
python scripts/paper.py submit --root INPUT_DIRECTORY --request INPUT_DIRECTORY/request.json
python scripts/paper.py status --task TASK_ID
python scripts/paper.py status --run RUN_ID
python scripts/paper.py fetch --run RUN_ID --output EMPTY_DESTINATION
```

`--repo OWNER/REPO`是全局参数，放在操作之前。开发仓库Self-Command/reference-paper-studio已按用户指示公开；明确授权的公开材料在submit加`--public-inputs`。正式私人稿件指定其私有任务仓库，不能继承本项目测试材料的公开授权。本次授权范围内无需再次询问。

开发任务可加`--workflow-ref codex/modular-paper-studio`绑定候选处理分支；省略时用默认分支。输入提交与处理程序分别检出，任务分支不能替换执行程序。不要把手动工作流分支参数描述为任意提交SHA；引擎身份由提交器解析并写入请求。

## 版本2契约

导出任务必须使用schema_version: 2。旧导出请求缺少审批绑定，即使能上传也会被云端拒绝；不要用旧id/stage/template_id示例冒充可执行导出。

```json
{
  "schema_version": 2,
  "task_id": "my-format-first",
  "operation": "export",
  "document_kind": "format",
  "manuscript": "manuscript.md",
  "files": [
    {"path": "manuscript.md", "sha256": "ACTUAL_MANUSCRIPT_SHA256", "role": "manuscript"},
    {"path": "approvals.json", "sha256": "ACTUAL_APPROVALS_SHA256", "role": "approvals"}
  ],
  "approval_file": "approvals.json",
  "approvals": {"md_content": "content-1", "presentation": "fonts-1", "export": "export-1"},
  "template": {
    "id": "reference-journal-v1",
    "version": "2.0.0",
    "variant": "front",
    "font_profile": "open-serif",
    "manifest_sha256": "ACTUAL_REGISTERED_MANIFEST_SHA256"
  },
  "outputs": ["docx", "latex", "docx-proof-pdf", "latex-pdf", "previews"]
}
```

大写指纹占位符必须替换成实际64位SHA-256，审批事件必须来自当前用户指令，不能复制示例替用户批准。当前测试母版均为候选，正常任务仍受TEMPLATE_NOT_READY门禁；示例不承诺候选已经正式可用。母版先独立构建、验收与登记，填充只读已登记版本，不在每次导出时重建母版或设置候选绕过开关。

请求不声明input_commit，由云端绑定真正输入提交。engine_commit可省略，由提交器绑定处理分支；已有声明必须与所选引擎一致。详细字段见[请求契约](../schemas/request.schema.json)和[审批契约](../schemas/approval.schema.json)。

files逐项列出稿件、元数据、图片、文献库、证据与审批，使用相对输入目录的`/`路径。没有通配符、目录上传、远程图片或越界路径。仅上传清单文件，不上传整个工作区。任务ID唯一；重新提交用新ID，保留以前输入和首版。

MD元数据使用title/authors/affiliation/abstract/keywords加_zh/_en后缀。外来title/authors/funding等字段不会静默丢弃；先报告位置，确认语义映射。图片和表格要有名称、稳定标识与正文引用。公式保留LaTeX数学及稳定编号；物理排版指令拒绝，稿件不能覆盖模板字体、字号、页边距、栏数或分节。

## 阶段与授权

| operation | 输入与边界 |
|---|---|
| reference | 参考PDF与带页码证据；参考一致项优先，冲突才由指定官方模板消歧 |
| model-review | 定义、符号、模型与验证证据；程序不宣称数学证明 |
| md-review | 标题、逻辑、公式、图表、引用与资源；只检查，不自动修复 |
| template-build | 登记组合及字体；独立母版维护，不按稿件临时调模板 |
| export | MD确认、字体选择、生成授权绑定当前文件、资源和母版；已有批准复用 |
| visual-receipt | 真实逐页复检报告与冻结产物；核验覆盖和身份，不重新渲染 |
| package | 候选包及白名单检查；不代替发布或安装门禁 |

模型校样用document_kind: model；已发表稿件纯格式整理用format，不重新宣称验证科学结论。新研究完整论文用paper，须有模型验证报告、作者确认及定量主张对应证据；方向批准不替代这些要求。字体先问用户，开发合成测试用已批准开源方案，正式稿件不自动替用户选字体。

## 产物与视觉收据

产物包括已生成的Word、LaTeX项目、XeLaTeX PDF、LibreOffice Word兼容PDF、云端Poppler逐页PNG和报告。构建、自动检查、视觉复检与交付状态分开记录；兼容PDF不冒称Microsoft Word原生效果。失败时提供实际已经生成的Word与诊断；若在母版、审批或输入检查前拒绝，明确没有Word，不能虚构首版。

看完两套校样所有页后记录21项清单，结果可以为issues_found。收据任务使用operation: visual-receipt、artifact_run、artifact_name、visual_receipt和仅含收据的清单。收据记录运行ID、检查人、所有Word/TeX/PDF/PNG指纹、输入及母版绑定、检查结果和问题。云端下载冻结产物核验，覆盖不全或身份变化失败；收据成功不意味着视觉无问题。

先交Word、视觉附件与报告，用户批准对应问题范围后再修复。已批准技术开发范围内排查与重跑不重复询问。首版和每次修订独立保留，不用后来的校样改写首次结果。Actions附件默认保存30天，及时下载所需产物；正式安装包不含稿件、实验或任务材料。
