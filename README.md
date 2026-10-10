# Reference Paper Studio

中文参考论文驱动的 Codex 学术写作与双格式排版技能。统一稿件生成 Word、LaTeX 和 PDF；测试、编译和渲染全部在 GitHub Actions。

入口为 [SKILL.md](SKILL.md)，云端操作见 [cloud-tasks.md](references/cloud-tasks.md)。用户已于2026-10-10确认仓库现有材料为可公开测试材料，并明确授权直接公开原仓库；历史、分支和附件保留。后续正式作者稿不因此获得公开授权，提交器仍检查目标可见性与公开范围。

核心实现：版本化 DOCX 母版、内容无权覆盖的字体和分节、完整双栏正文、可逆原生 OMML 换行、参考规则及模型证据门禁、Pandoc 共同表示、三线表、实际栏边界测量、XeLaTeX 与 LibreOffice 校样，以及绑定产物的视觉审阅收据。

当前在 `codex/modular-paper-studio` 开发0.3.0候选：10个技能入口共享一个内核，9类MD结构及组件化物理模板。使用 Pandoc、docxtpl、python-docx 1.2.0和lxml 6.0.2填充固定母版。具体输入、输出与独立调用见[技能说明](references/skill-usage.md)，阶段与限制见[开发记录](docs/implementation-status.md)。

schema_version 2请求只选择登记模板身份、版本、变体与字体方案，显式声明资源及指纹；原profile接口和物理版式覆盖被拒绝。MD是唯一正式内容源，先确认内容，选择字体，再授权生成。正文栏数按模板登记；原参考模板持续双栏，公式、数据表、图片不得跨栏。个人审阅变体图题在上、表题在下，不能冒称符合所有期刊官方规则。

九类MD目前按用户要求保留待审。合成测试使用已说明的开源字体；正式用户导出不能替用户默认选字体。候选母版不开放正式导出，验收前不替换已安装技能。Node对比实验保持隔离，不参与正式生成。

LibreOffice 校样固定使用官方 26.8.1 Linux 发行包，并核对[官方 SHA-256](https://download.documentfoundation.org/libreoffice/stable/26.8.1/deb/x86_64/LibreOffice_26.8.1_Linux_x86-64_deb.tar.gz.sha256)。Ubuntu 自带的 24.2 保留为失败回归来源，正式校样使用新版；数学组件是必需依赖。

共同表示与公式转换固定为 [Pandoc 3.12.1 官方发行版](https://github.com/jgm/pandoc/releases/tag/3.12.1)，安装前检查 GitHub 发行资产的 SHA-256，版本记录随产物保存。

源文件在本地编辑；运行仅在 Actions。`skill-ci.yml` 验证技能、真实模型 30 条公式和格式对象回归，并生成去除私人材料的安装 ZIP。`document-task.yml` 处理显式输入清单或验证上一运行的视觉审阅收据。两者均固定工具和 Action 版本，保存版本记录与输入指纹，产物保留 30 天。

0.3.0候选包是 `reference-paper-studio-suite-candidate.zip`，其中10个技能目录并列，共享资源只保存在总技能目录。候选包明确 `installation_allowed: false`。正式版本只有在MD审定、承诺模板验收、逐页视觉审阅和发布门槛全部通过后才能安装；本轮尚未替换本机旧技能。

实现与复用代码采用 MIT，见 [LICENSE](LICENSE) 和 [来源声明](third_party/NOTICE.md)。参考论文、作者稿件不受该授权覆盖。字体使用开源替代，校样不声称精确复现期刊字体；LibreOffice 校样不等同 Microsoft Word 原生渲染。数学内容保留检查不构成正确性证明。
