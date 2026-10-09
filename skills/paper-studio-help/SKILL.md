---
name: paper-studio-help
description: 介绍学术论文套件的技能用途、输入、输出、前置条件和独立调用方法；用户只咨询使用方式时不执行文档任务。
---

# 技能说明与使用指导

读取同一能力目录，解释最少需要哪些材料、如何调用、会获得什么，以及当前模板是否就绪。只说明时不跑Actions。

按目录的 inputs、outputs、preconditions、example 展示说明卡。完整使用指导见[技能用途与独立使用](../reference-paper-studio/references/skill-usage.md)。用户只想执行一项技能时给出直接调用方式，并复用已完成阶段。

读取[当前操作说明](../reference-paper-studio/references/suite-workflow.md)，按需读取[能力目录](../reference-paper-studio/catalog/skill-catalog.yaml)。不要默认载入其他技能全部说明或启动多代理。

所有测试、转换、编译、渲染和程序验收只能在GitHub Actions执行。本地仅编辑、读取、submit/status/fetch与查看云端页图。稿件无权更改登记母版，第一版保留，用户批准问题范围后才修复。模型验证、用户确认、自动验收和视觉结果分开记录。
