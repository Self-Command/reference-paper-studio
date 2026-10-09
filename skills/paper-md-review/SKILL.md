---
name: paper-md-review
description: 只审查Markdown论文的标题摘要、逻辑、章节、模型、证据、公式、图表与文献，输出可定位问题；不擅自修稿。
---

# MD论文审查

检查正式内容和旁置证据。按稳定对象ID报告，程序性解析/检查走Actions；数学审查与转换检查分开。确认当前MD快照后才能导出。

读取[当前操作说明](../reference-paper-studio/references/scientific-evidence.md)，按需读取[能力目录](../reference-paper-studio/catalog/skill-catalog.yaml)。不要默认载入其他技能全部说明或启动多代理。

所有测试、转换、编译、渲染和程序验收只能在GitHub Actions执行。本地仅编辑、读取、submit/status/fetch与查看云端页图。稿件无权更改登记母版，第一版保留，用户批准问题范围后才修复。模型验证、用户确认、自动验收和视觉结果分开记录。
