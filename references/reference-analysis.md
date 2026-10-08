# 参考分析

先登记用户指定的已发表论文、文类、年份、期刊、原始页码和材料角色。初稿保留研究内容，但不能覆盖已发表论文的版式。
每条规则分别记录 property、value、source、pages、scope、confidence、adopted_reason。写作结构与物理版式分开；扫描页或低质量抽取标为 needs_review，不建立可靠规则。
一致观察采用参考论文值；差异项目才读取官方模板的明确条文。未知项保持未确认。PDF 字体坐标只提供观察证据，不能证明原始 Word 样式。
不复制参考论文句段、结果或数据。核对正文、模型、图表和末页，输出可追溯规则而非一份平均模板。
# 实际操作

首次接触参考 PDF 时，只列 `sources`、页码和 `render_previews: true`，把尚未查看的观察标为 `reviewed: false`。提交 `reference` 云端任务后读取抽取质量报告，并查看下载的逐页 PNG；此时才可记录已核实观察，再提交规则解析。不可根据文件名、期刊名或左右文字数量直接填入 `reviewed: true`。

每条 `observations` 至少包含 `property`、`value`、`source`、`pages`、`observation`、`scope` 和 `reviewed`。源文件清单格式见私有仓库的参考回归材料；观察正文由当前 Codex 完成，不需要 Actions 调用模型 API。用 `official_document` 指定模板文件和页码，`official` 中各项目只能处理参考论文冲突。低质量抽取仍需人工核验，不能由几何统计代替视觉证据。

