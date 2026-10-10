# 独立 Word 内核接入

`catalog/word-engine.json` 锁定公开仓库 `Self-Command/word-module-studio` 的完整提交与版本。
`scripts/studio/word_adapter.py` 校验实际 checkout 和导入路径，调用外部内核；不复制通用排版实现。

模板、组件和规则由论文套件编译成数据。外部 `consumers/reference_paper.py` 将规则投影为
`TemplateSpec`，统一内核不按期刊或比赛名称分支。模型证据、MD 审批、字体确认、正式导出授权、
模板来源与年份、LaTeX 仍由论文套件负责。

`Pinned Word engine consumer` Actions 回归九类组合、原参考布局，以及原始模型 M1—M30。
这些是计划授权的技术验收，不代表待审 MD 骨架或正式投稿模板已获批准。

JSON 入口 `word-export` 复用版本 2 请求及真实审批检查，仅接受 `docx`、`docx-proof-pdf`、
`previews` 输出。候选内核和候选模板仍须通过候选环境保护。默认双输出入口保持原版本，
整套论文技能 0.3.0 的发布条件仍包括待审 MD、双输出与对应模板验收。

内核更新必须修改完整提交与版本，并重跑消费方回归；不能指向浮动分支或自动升级。
