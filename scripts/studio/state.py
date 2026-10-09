"""Explicit workflow transitions; success never generates user approval."""
from transitions import Machine
from .runtime import require_actions
STATES=["intake","plan_confirmed","references_ready","model_reviewed","model_confirmed","md_draft","md_reviewed","md_confirmed","presentation_confirmed","export_authorized","cloud_build","visual_review_reported","awaiting_user_decision","revision_authorized","revised","delivered"]
EDGES=[("confirm_plan","intake","plan_confirmed"),("finish_references","plan_confirmed","references_ready"),("review_model","references_ready","model_reviewed"),("confirm_model","model_reviewed","model_confirmed"),("draft_md","model_confirmed","md_draft"),("review_md","md_draft","md_reviewed"),("confirm_md","md_reviewed","md_confirmed"),("confirm_presentation","md_confirmed","presentation_confirmed"),("authorize_export","presentation_confirmed","export_authorized"),("build","export_authorized","cloud_build"),("report_visual","cloud_build","visual_review_reported"),("await_decision","visual_review_reported","awaiting_user_decision"),("authorize_revision","awaiting_user_decision","revision_authorized"),("revise","revision_authorized","revised"),("rebuild","revised","cloud_build"),("approve_delivery","awaiting_user_decision","delivered")]
USER_EVENTS={"confirm_plan","confirm_model","confirm_md","confirm_presentation","authorize_export","authorize_revision","approve_delivery"}
class ProjectFlow:
    def __init__(self, initial="intake"):
        require_actions()
        self.authorized=False
        self.model_evidence_ready=False
        transitions=[{"trigger":event,"source":src,"dest":dest,**({"conditions":"has_authorization"} if event in USER_EVENTS else {"conditions":"has_model_evidence"} if event=="draft_md" else {})} for event,src,dest in EDGES]
        self.machine=Machine(model=self,states=STATES,transitions=transitions,initial=initial,auto_transitions=False,send_event=False)
    def has_authorization(self): return self.authorized
    def has_model_evidence(self): return self.model_evidence_ready
    def apply(self,event,authorized=False,model_context=None):
        require_actions()
        self.authorized=authorized
        try:
            if event=="draft_md" and model_context is not None:
                from .manuscript import model_gate
                result=model_gate(model_context["root"],model_context["source"],model_context.get("evidence"),True)
                self.model_evidence_ready=result["status"]=="evidence_bound"
            return self.trigger(event)
        finally:
            self.authorized=False
            self.model_evidence_ready=False
