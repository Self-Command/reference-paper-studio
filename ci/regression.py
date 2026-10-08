"""Actual-model and synthetic-object integration, cloud only."""
from pathlib import Path
import json
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from studio.runtime import require_actions, write_json, digest
from studio.pipeline import export
from studio.references import analyze
from studio.review import review

require_actions()
root=Path(__file__).resolve().parents[1]
references=analyze(root/"fixtures/references","evidence.json",root/"build/reference-analysis")
review(root/"fixtures/model/model.md",root/"build/model-review")
export(root/"fixtures/model",{"manuscript":"model.md","metadata":"metadata.json","profile":"profile.json","document_kind":"model","expected_equations":30},root/"build/model",references["rules"])
# Synthetic values are labelled as a format test; never presented as research data.
fixture=root/"build/synthetic-input"; fixture.mkdir(parents=True,exist_ok=True)
from PIL import Image, ImageDraw
image=Image.new("RGB",(600,180),"white"); draw=ImageDraw.Draw(image); draw.rectangle((30,30,570,150),outline="black",width=3); draw.text((50,75),"FORMAT TEST: INPUT -> MODEL -> CHECK",fill="black"); image.save(fixture/"diagram.png")
(fixture/"model.md").write_text(r"""# 格式回归样例

以下数值仅用于格式测试，并非实验结果。依次检验{{fig:F1}}、{{tab:T1}}、{{eq:S1}}与引用[1]。

表1 格式测试数值 / Table 1 Synthetic values

| 项目 | 数值 |
|---|---:|
| 样例 A | 12.50 |
| 样例 B | 3.75 |

![图1 处理流程 / Fig. 1 Processing flow](diagram.png){width=65%}

\[ f(x)=\begin{cases}\frac{x_i^2}{1+x_i},&x_i>0,\\0,&x_i\le0.\end{cases}\tag{S1}\]

\[\begin{aligned}\min\quad &\sum_{i=1}^{n}x_i\\\text{s.t.}\quad &x_i\ge0,\quad i=1,\ldots,n.\end{aligned}\tag{S2}\]

# 参考文献

[1] 示例文献条目，仅用于顺序编码保留测试。
""",encoding="utf-8")
meta={"title_zh":"排版能力回归样例","authors_zh":"测试作者（非论文署名）","affiliation_zh":"格式测试","abstract_zh":"验证通栏前置信息、双栏正文、原生公式、图下题、表上题。","keywords_zh":["格式测试"],"title_en":"Formatting regression fixture","abstract_en":"Synthetic material for formatting checks only.","keywords_en":["format test"]}
write_json(fixture/"metadata.json",meta)
profile=json.loads((root/"assets/profiles/chinese-journal.json").read_text());profile["english_abstract_position"]="end"
write_json(fixture/"profile.json",profile)
export(fixture,{"manuscript":"model.md","metadata":"metadata.json","profile":"profile.json","expected_equations":2},root/"build/objects-end")
write_json(root/"build/regression-summary.json",{"status":"passed","original_model_equations":30,"object_fixture":"passed","english_abstract_positions":["front","end"],"mathematical_correctness":"not_asserted"})
