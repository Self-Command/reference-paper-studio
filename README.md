# Reference Paper Studio

中文参考论文驱动的 Codex 学术写作与双格式排版技能。统一稿件生成 Word、LaTeX 和 PDF；测试、编译和渲染全部在 GitHub Actions。

入口为 [SKILL.md](SKILL.md)，云端操作见 [cloud-tasks.md](references/cloud-tasks.md)。仓库保留用户参考资料和模型的私有输入，公开发布需另行去除私有材料。

核心实现：页码与指纹绑定的参考规则、官方模板限定消歧、模型证据门禁、Pandoc 共同文档表示、原生 Word OMML、逐节分栏、数据表三线处理、XeLaTeX 与 LibreOffice 校样、正文/数字/公式回读检查，以及绑定产物的视觉审阅收据。

LibreOffice 校样固定使用官方 26.8.1 Linux 发行包，并核对[官方 SHA-256](https://download.documentfoundation.org/libreoffice/stable/26.8.1/deb/x86_64/LibreOffice_26.8.1_Linux_x86-64_deb.tar.gz.sha256)。Ubuntu 自带的 24.2 保留为失败回归来源，正式校样使用新版；数学组件是必需依赖。

源文件在本地编辑；运行仅在 Actions。`skill-ci.yml` 验证技能、真实模型 30 条公式和格式对象回归，并生成去除私人材料的安装 ZIP。`document-task.yml` 处理显式输入清单或验证上一运行的视觉审阅收据。两者均固定工具和 Action 版本，保存版本记录与输入指纹，产物保留 30 天。

安装时仅解包已通过云端验收的 `reference-paper-studio.zip` 到 `~/.codex/skills`。不要复制带有测试论文和模型的整个仓库到技能目录。下轮对话可用 `$reference-paper-studio` 调用。

实现与复用代码采用 MIT，见 [LICENSE](LICENSE) 和 [来源声明](third_party/NOTICE.md)。参考论文、作者稿件不受该授权覆盖。字体使用开源替代，校样不声称精确复现期刊字体；LibreOffice 校样不等同 Microsoft Word 原生渲染。数学内容保留检查不构成正确性证明。
