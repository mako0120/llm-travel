"""Versioned, deterministic handoff contracts for independent agent teams."""

CONTRACT_VERSION = "1.0"

REQUIRED = {
    "RequirementInput": ("requirements",),
    "RetrievedContext": ("items",),
    "PlanCandidate": ("plan",),
    "ValidationResult": ("valid", "issues"),
    "FeedbackAnalysis": ("metrics", "scope"),
    "ImprovementProposal": ("condition", "problem", "improvement", "evidence"),
    "DevelopmentIssue": ("title", "objective", "acceptance_criteria"),
    "EvalResult": ("dataset_version", "cases", "passed", "scope"),
    "ResearchRequest": ("profile_id", "requirements", "source_targets", "batch_unit", "retry_limit", "timeout_seconds"),
    "ResearchResult": ("request_id", "state", "evidence", "confidence", "fallback"),
}


def validate_handoff(name, document):
    """Return structured issues; do not execute instructions contained in data."""
    issues = []
    if name not in REQUIRED:
        return [{"code": "unknown_contract", "path": "name", "message": "Contract name is not supported."}]
    if not isinstance(document, dict):
        return [{"code": "invalid_document", "path": "document", "message": "Contract document must be an object."}]
    if document.get("contract_version") != CONTRACT_VERSION:
        issues.append({"code": "unsupported_version", "path": "contract_version", "message": "Contract version is unsupported."})
    trace_id = document.get("trace_id")
    if not isinstance(trace_id, str) or not trace_id.strip():
        issues.append({"code": "invalid_trace_id", "path": "trace_id", "message": "A nonempty trace ID is required."})
    for field in REQUIRED[name]:
        if field not in document:
            issues.append({"code": "missing_field", "path": field, "message": "Required field is missing."})
    if name == "RequirementInput" and "requirements" in document and not isinstance(document["requirements"], list):
        issues.append({"code": "invalid_requirements", "path": "requirements", "message": "Requirements must be a list."})
    if name == "RetrievedContext" and "items" in document and not isinstance(document["items"], list):
        issues.append({"code": "invalid_items", "path": "items", "message": "Items must be a list."})
    if name == "PlanCandidate" and "plan" in document and not isinstance(document["plan"], dict):
        issues.append({"code": "invalid_plan", "path": "plan", "message": "Plan must be an object."})
    if name == "ValidationResult":
        if "valid" in document and type(document["valid"]) is not bool:
            issues.append({"code": "invalid_valid", "path": "valid", "message": "Valid must be boolean."})
        if "issues" in document and not isinstance(document["issues"], list):
            issues.append({"code": "invalid_issues", "path": "issues", "message": "Issues must be a list."})
    if name == "ImprovementProposal":
        if "condition" in document and not isinstance(document["condition"], dict):
            issues.append({"code": "invalid_condition", "path": "condition", "message": "Condition must be an object."})
        for field in ("problem", "improvement"):
            if field in document and (not isinstance(document[field], str) or not document[field].strip()):
                issues.append({"code": "invalid_text", "path": field, "message": "Text must be nonempty."})
    if name == "EvalResult":
        for field in ("cases", "passed"):
            if field in document and (type(document[field]) is not int or document[field] < 0):
                issues.append({"code": "invalid_count", "path": field, "message": "Count must be a nonnegative integer."})
        if all(type(document.get(key)) is int for key in ("cases", "passed")) and document["passed"] > document["cases"]:
            issues.append({"code": "invalid_count", "path": "passed", "message": "Passed cannot exceed cases."})
    if name == "ResearchRequest":
        if "profile_id" in document and (not isinstance(document["profile_id"], str) or not document["profile_id"].strip()):
            issues.append({"code": "invalid_profile_id", "path": "profile_id", "message": "Profile ID must be an opaque nonempty string."})
        if "requirements" in document and not isinstance(document["requirements"], dict):
            issues.append({"code": "invalid_research_input", "path": "requirements", "message": "Requirements must be structured data."})
        if "source_targets" in document and not isinstance(document["source_targets"], list):
            issues.append({"code": "invalid_research_input", "path": "source_targets", "message": "Source targets must be a list."})
        for index, target in enumerate(document.get("source_targets", [])):
            if not isinstance(target, dict) or not all(isinstance(target.get(key), str) and target[key].strip() for key in ("query", "location", "category")):
                issues.append({"code": "invalid_source_target", "path": f"source_targets[{index}]", "message": "Target needs query, location, and category."})
            elif (type(target.get("freshness_minutes")) is not int or target["freshness_minutes"] < 1
                  or not isinstance(target.get("source_types"), list) or not target["source_types"]):
                issues.append({"code": "invalid_source_target", "path": f"source_targets[{index}]", "message": "Target needs freshness and source types."})
        if document.get("batch_unit") != "section":
            issues.append({"code": "invalid_batch_unit", "path": "batch_unit", "message": "Research batch unit must be section."})
        if type(document.get("retry_limit")) is not int or not 0 <= document.get("retry_limit", -1) <= 2:
            issues.append({"code": "invalid_retry_limit", "path": "retry_limit", "message": "Retry limit must be 0 to 2."})
        if type(document.get("timeout_seconds")) is not int or not 1 <= document.get("timeout_seconds", 0) <= 120:
            issues.append({"code": "invalid_timeout", "path": "timeout_seconds", "message": "Timeout must be 1 to 120 seconds."})
    if name == "ResearchResult":
        if document.get("state") not in ("ready", "failed", "unconfigured"):
            issues.append({"code": "invalid_research_state", "path": "state", "message": "Research state is invalid."})
        if "evidence" in document and not isinstance(document["evidence"], list):
            issues.append({"code": "invalid_evidence", "path": "evidence", "message": "Evidence must be a list."})
        if document.get("confidence") not in ("high", "medium", "low", "unknown"):
            issues.append({"code": "invalid_confidence", "path": "confidence", "message": "Confidence is invalid."})
        if document.get("fallback") not in ("continue_with_labels", "ask_user", "exclude_candidate", "stop"):
            issues.append({"code": "invalid_fallback", "path": "fallback", "message": "Fallback is invalid."})
    return issues
