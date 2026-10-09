---
name: paper-visual-review
description: 对云端论文校样或指定Word逐页检查，提供视觉附件、问题清单与复检报告；只检查时不修复。
---

# 论文视觉复检

Word转换只走Actions。查看全部云端页图，按21项清单逐项记录。检查完成可有问题；不以绿色Actions或OOXML栏数替代真实看图。

读取[当前操作说明](../reference-paper-studio/references/visual-checklist.md)，按需读取[能力目录](../reference-paper-studio/catalog/skill-catalog.yaml)。不要默认载入其他技能全部说明或启动多代理。

所有测试、转换、编译、渲染和程序验收只能在GitHub Actions执行。本地仅编辑、读取、submit/status/fetch与查看云端页图。稿件无权更改登记母版，第一版保留，用户批准问题范围后才修复。模型验证、用户确认、自动验收和视觉结果分开记录。
