# 科学写作与证据适配

基于MIT K-Dense scientific-writing、peer-review、citation-management的主张登记、方法结果一致性与有边界审查进行适配。固定上游与许可证见 scripts/studio/vendor/kdense/LICENSE.md 和 THIRD_PARTY_NOTICES.md。

主张与证据一一关联。公开文献身份核实不是全文支持核实；DOI存在不证明某一结论。模型定义、假设、约束、推导、代码对应、实例复现与泛化证据分开报告。一次求解成功不证明模型普遍正确。

scientific-writing/check_consistency.py由云端适配器执行作者登记的数字/单位/方法结果记录。上游按物理行扫描的audit_claims.py不能直接把中文自动换行当段落；输入应由AST对象与旁置主张登记形成。不把页码、编号、年份、维度都算实验数字。

正式论文不出现内部claim/evidence标记。证据缺口留在报告，不填入虚构结果或参考文献。
