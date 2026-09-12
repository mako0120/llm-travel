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
    return issues
