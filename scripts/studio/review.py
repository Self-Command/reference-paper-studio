"""Evidence inventory, never a substitute for mathematical verification."""
import re
from pathlib import Path
from .runtime import require_actions, write_json, digest
from .manuscript import parse, text_of


def review(source, output):
    require_actions()
    ast, equations = parse(source, output)
    text = text_of(ast["blocks"])
    categories = {"problem": r"问题|任务|冲突", "assumptions": r"假设|前提", "symbols": r"符号|变量|参数", "constraints": r"约束", "objectives": r"目标", "algorithm": r"算法|求解", "validation": r"验证|实验|证明"}
    result = {"model_sha256": digest(source), "equations": [e["id"] for e in equations],
              "sections_present": {k: bool(re.search(pattern, text)) for k, pattern in categories.items()},
              "mathematical_correctness": "not_verified", "author_approval": "required_before_paper",
              "required_review": ["变量定义、单位与取值域", "假设适用范围及周期边界", "约束必要性、充分性与等价证明", "目标函数和可行性", "求解结果独立复核及反例", "泛化边界、基准与消融证据"],
              "warning": "Section presence and native math conversion are inventory checks, not proofs or experimental results."}
    write_json(Path(output)/"model-review.json", result)
    return result
