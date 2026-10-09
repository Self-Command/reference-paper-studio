
## K-Dense scientific-agent-skills (0.3.0 adaptation)

MIT, Copyright (c) 2025 K-Dense Inc.
Upstream https://github.com/K-Dense-AI/scientific-agent-skills
Inspected and copied commit 92ace75ac21efe19a620434e0ca4e356081fe807.
Files: scientific-writing/{_common.py,audit_claims.py,check_consistency.py}; peer-review/{_common.py,validate_claim_evidence.py}; citation-management/{_common.py,doi_to_bibtex.py}.
Original license: scripts/studio/vendor/kdense/LICENSE.md.
Adaptation: each command entry checks the Actions environment before execution; helper implementations remain upstream. The shared adapter executes explicitly authored consistency registries. Line-based audits are not represented as mathematical proofs or automatic Chinese AST evidence audits.
