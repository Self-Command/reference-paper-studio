---
name: paper-export
description: 用已确认MD、登记母版、字体和有效生成授权，在GitHub Actions生成可编辑Word、LaTeX、PDF与首版诊断报告。
---

# Word与LaTeX云端生成

核对当前内容确认、字体选择和导出授权；已有有效指令复用。只读母版，拒绝物理格式覆盖，保留首版，即使失败也提供已有Word和报告。

读取[当前操作说明](../reference-paper-studio/references/cloud-tasks.md)，按需读取[能力目录](../reference-paper-studio/catalog/skill-catalog.yaml)。不要默认载入其他技能全部说明或启动多代理。

所有测试、转换、编译、渲染和程序验收只能在GitHub Actions执行。本地仅编辑、读取、submit/status/fetch与查看云端页图。稿件无权更改登记母版，第一版保留，用户批准问题范围后才修复。模型验证、用户确认、自动验收和视觉结果分开记录。
