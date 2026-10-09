
## K-Dense scientific-agent-skills (0.3.0 adaptation)

MIT, Copyright (c) 2025 K-Dense Inc.
Upstream https://github.com/K-Dense-AI/scientific-agent-skills
Inspected and copied commit 92ace75ac21efe19a620434e0ca4e356081fe807.
Files: scientific-writing/{_common.py,audit_claims.py,check_consistency.py}; peer-review/{_common.py,validate_claim_evidence.py}; citation-management/{_common.py,doi_to_bibtex.py}.
Original license: scripts/studio/vendor/kdense/LICENSE.md.
Adaptation: each command entry checks the Actions environment before execution; helper implementations remain upstream. The shared adapter executes explicitly authored consistency registries. Line-based audits are not represented as mathematical proofs or automatic Chinese AST evidence audits.

## FontTools and CALS cloud investigation

FontTools 4.66.1 (MIT), https://github.com/fonttools/fonttools, is an installed dependency for reading selected font-face metadata and glyph maps. No upstream source is copied into this repository and no fonts are extracted, rewritten or redistributed by this inspection.

The cloud math-width adapter also reads the registered face's cmap/hmtx/unitsPerEm through FontTools, retaining operator spacing and a safety margin. It does not change the selected fonts; actual Word/XeLaTeX glyph and overflow checks still decide acceptance. See https://fonttools.readthedocs.io/en/latest/ttLib/ttFont.html and https://fonttools.readthedocs.io/en/latest/ttLib/tables/_h_m_t_x.html.

CALS 2.4.2 by Oleg Parashchenko (LPPL), https://ctan.org/pkg/cals, is provided by the pinned TeX Live environment. Our adapter uses its documented interfaces; no upstream source is copied. Candidate region.body/table.three-line v2 components use native columns/CALS, pending export regression and visual review. The native two-column feasibility check passed in Actions 37945165806; the failed automatic continuation experiment inside multicols is retained in Actions 37944090286. The released v1 engine remains unchanged.

Cuted 2.0 (2021/10/04) by Sigitas Tolušis, LPPL 1.3 or later, https://ctan.org/pkg/cuted, is supplied by the pinned 2023 TeX Live environment. A diagnostic adapter calls its strip interface for a fixed end region; it is not registered as the production backend: the short probe passed, but Actions 37961172886 lost end metadata in the real model, detected by rendered-title validation and confirmed on the cloud last-page preview. Region.end v3 retains native new-page output with the whitespace limitation reported. Cloud setup records the installed version/hash. No upstream source is copied or altered; latest CTAN 2.10 targets a newer kernel and is not silently substituted.
