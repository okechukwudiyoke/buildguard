import json
import math
import sys
from falkordb import FalkorDB
from redis.exceptions import RedisError
from review_history import save_review
from inspect_variation import (
    get_missing_approvals,
    get_approval_policy_issues,
    get_approved_variations,
    get_variation_inspection_issues,
)

def review_payment(payment_id, persist=True):
    if not isinstance(payment_id, str) or not payment_id.strip():
        raise ValueError("A payment request ID is required.")
    payment_id = payment_id.strip()
    graph = FalkorDB(host="localhost", port=6379).select_graph("buildguard")
    query = """
    MATCH (r:PaymentRequest {id: $payment_id})-[:AGAINST]->(a:Agreement)
    OPTIONAL MATCH (paid:Payment)-[:PAID_AGAINST]->(a)
    WITH r, a, coalesce(sum(paid.amount_ngn), 0) AS already_paid
    OPTIONAL MATCH (i:Inspection)-[:INSPECTS]->(a)
    RETURN r.id, r.amount_ngn, a.amount_ngn, already_paid,
           a.amount_ngn - already_paid AS remaining_balance,
           i.id, i.completion_verified, i.specification_compliant, a.payment_rule,
           a.payment_history_verified, a.payment_history_ref, i.evidence_ref, a.id
    """
    rows = graph.ro_query(query, params={"payment_id": payment_id}).result_set
    if len(rows) != 1:
        return {
            "payment_id": payment_id,
            "recommendation": "HOLD",
            "review_complete": False,
            "findings": ["HOLD: request or agreement is missing, or multiple matches require manual review."]
        }
    (
        payment_id, requested, agreed, paid, remaining,
        inspection_id, complete, compliant, payment_rule,
        history_verified, history_reference, inspection_reference, agreement_id
    ) = rows[0]
    approved_variations = get_approved_variations(payment_id)
    amounts = [requested, agreed, paid] + [v["amount_ngn"] for v in approved_variations]
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in amounts):
        raise ValueError("Payment evidence contains invalid numeric amounts.")
    variation_total = sum(item["amount_ngn"] for item in approved_variations)
    authorised_value = agreed + variation_total
    remaining = authorised_value - paid
    findings = []
    if requested <= 0 or agreed <= 0 or paid < 0 or any(v["amount_ngn"] <= 0 for v in approved_variations):
        findings.append("HOLD: request, agreement and variation amounts must be positive; previous payments cannot be negative.")
    if history_verified is not True or not isinstance(history_reference, str) or not history_reference.strip():
        findings.append("HOLD: payment history has not been verified against a referenced ledger.")
    if inspection_id is not None and (not isinstance(inspection_reference, str) or not inspection_reference.strip()):
        findings.append("HOLD: agreement inspection has no evidence reference.")
    findings.extend(get_approval_policy_issues(payment_id))
    findings.extend(get_variation_inspection_issues(payment_id))
    if payment_rule != "FULL_AFTER_VERIFIED_COMPLETION":
        findings.append("HOLD: payment rule is missing or unsupported; manual review required.")
    if requested > remaining:
        findings.append(f"INVESTIGATE: request exceeds remaining balance by NGN {requested - remaining:,.2f}.")
    if inspection_id is None:
        findings.append("HOLD: inspection evidence is missing.")
    elif complete is not True or compliant is not True:
        findings.append("HOLD: completion and specification compliance are not both verified.")
    for _, variation_id, person_id, person_name in get_missing_approvals(payment_id):
        findings.append(f"HOLD: {variation_id} is missing approval from {person_name} ({person_id}).")
    if any(finding.startswith("INVESTIGATE:") for finding in findings):
        recommendation = "INVESTIGATE"
    elif findings:
        recommendation = "HOLD"
    else:
        recommendation = "APPROVE"
    review = {
        "policy_version": "fixed-price-demo-v1",
        "agreement_id": agreement_id,
        "agreement_value_ngn": agreed,
        "approved_variations": approved_variations,
        "authorised_value_ngn": authorised_value,
        "payment_id": payment_id,
        "recommendation": recommendation,
        "review_complete": not findings,
        "requested_ngn": requested,
        "already_paid_ngn": paid,
        "remaining_balance_ngn": remaining,
        "inspection_id": inspection_id,
        "inspection_evidence_ref": inspection_reference,
        "payment_history_verified": history_verified,
        "payment_history_ref": history_reference,
        "payment_rule": payment_rule,
        "findings": findings,
    }
    return save_review(review) if persist else review

if __name__ == "__main__":
    payment_id = sys.argv[1] if len(sys.argv) > 1 else "PAY-001"
    try:
        result = review_payment(payment_id)
    except (RedisError, ValueError) as error:
        result = {
            "payment_id": payment_id,
            "recommendation": "HOLD",
            "review_complete": False,
            "findings": ["HOLD: review could not be completed."],
            "error": str(error),
        }
    print(json.dumps(result, indent=2))
