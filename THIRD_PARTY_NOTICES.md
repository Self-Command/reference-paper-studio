
## K-Dense scientific-agent-skills (0.3.0 adaptation)

MIT, Copyright (c) 2025 K-Dense Inc.
Upstream https://github.com/K-Dense-AI/scientific-agent-skills
Inspected and copied commit 92ace75ac21efe19a620434e0ca4e356081fe807.
Files: scientific-writing/{_common.py,audit_claims.py,check_consistency.py}; peer-review/{_common.py,validate_claim_evidence.py}; citation-management/{_common.py,doi_to_bibtex.py}.
Original license: scripts/studio/vendor/kdense/LICENSE.md.
Adaptation: each command entry checks the Actions environment before execution; helper implementations remain upstream. The shared adapter executes explicitly authored consistency registries. Line-based audits are not represented as mathematical proofs or automatic Chinese AST evidence audits.

## FontTools and CALS cloud investigation

FontTools 4.66.1 (MIT), https://github.com/fonttools/fonttools, is an installed dependency for reading selected font-face metadata and glyph maps. No upstream source is copied into this repository and no fonts are extracted, rewritten or redistributed by this inspection.

CALS 2.4.2 by Oleg Parashchenko (LPPL), https://ctan.org/pkg/cals, is provided by the pinned TeX Live environment. Our adapter uses its documented interfaces; no upstream source is copied. Candidate region.body/table.three-line v2 components use native columns/CALS, pending export regression and visual review. The native two-column feasibility check passed in Actions 37945165806; the failed automatic continuation experiment inside multicols is retained in Actions 37944090286. The released v1 engine remains unchanged.

Cuted 2.0 (2021/10/04) by Sigitas Tolušis, LPPL 1.3 or later, https://ctan.org/pkg/cuted, is the version supplied by the pinned 2023 TeX Live environment. The candidate region.end v2 calls its strip interface for the fixed full-width end abstract; body objects cannot invoke this interface. Cloud setup checks the version and records the installed file hash. No upstream implementation is copied or altered; latest CTAN 2.10 targets a newer LaTeX kernel and is not silently substituted.
