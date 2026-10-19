from falkordb import FalkorDB

def get_missing_approvals(payment_id):
    graph = FalkorDB(host="localhost", port=6379).select_graph("buildguard")
    query = """
    MATCH (r:PaymentRequest {id: $payment_id})-[:INCLUDES_VARIATION]->(v:Variation)
    MATCH (v)-[:REQUIRES_APPROVAL_FROM]->(person:Person)
    OPTIONAL MATCH (person)-[approval:APPROVED]->(v)
    WITH r, v, person, approval
    WHERE approval IS NULL
    RETURN r.id, v.id, person.id, person.name
    """
    return graph.ro_query(query, params={"payment_id": payment_id}).result_set

def get_approval_policy_issues(payment_id):
    graph = FalkorDB(host="localhost", port=6379).select_graph("buildguard")
    query = """
    MATCH (:PaymentRequest {id: $payment_id})-[:INCLUDES_VARIATION]->(v:Variation)
    OPTIONAL MATCH (v)-[:REQUIRES_APPROVAL_FROM]->(okey:Person {id: 'PERSON-OKEY'})
    OPTIONAL MATCH (v)-[:REQUIRES_APPROVAL_FROM]->(chairman:Person {id: 'PERSON-CHAIRMAN'})
    RETURN DISTINCT v.id, okey.id, chairman.id
    """
    rows = graph.ro_query(query, params={"payment_id": payment_id}).result_set
    issues = []
    for variation_id, okey_id, chairman_id in rows:
        if okey_id is None or chairman_id is None:
            issues.append(f"HOLD: {variation_id} approval policy is incomplete; Okey and Chairman must both be required.")
    return issues
def get_approved_variations(payment_id):
    graph = FalkorDB(host="localhost", port=6379).select_graph("buildguard")
    query = """
    MATCH (r:PaymentRequest {id: $payment_id})-[:AGAINST]->(a:Agreement)
    MATCH (r)-[:INCLUDES_VARIATION]->(v:Variation)-[:VARIATION_OF]->(a)
    MATCH (v)-[:REQUIRES_APPROVAL_FROM]->(okey:Person {id: 'PERSON-OKEY'})
    MATCH (v)-[:REQUIRES_APPROVAL_FROM]->(chairman:Person {id: 'PERSON-CHAIRMAN'})
    MATCH (okey)-[:APPROVED]->(v)
    MATCH (chairman)-[:APPROVED]->(v)
    RETURN DISTINCT v.id, v.amount_ngn
    """
    rows = graph.ro_query(query, params={"payment_id": payment_id}).result_set
    return [{"variation_id": variation_id, "amount_ngn": amount} for variation_id, amount in rows]
def get_variation_inspection_issues(payment_id):
    graph = FalkorDB(host="localhost", port=6379).select_graph("buildguard")
    query = """
    MATCH (:PaymentRequest {id: $payment_id})-[:INCLUDES_VARIATION]->(v:Variation)
    OPTIONAL MATCH (i:Inspection)-[:INSPECTS]->(v)
    RETURN DISTINCT v.id, i.id, i.completion_verified,
           i.specification_compliant, i.evidence_ref
    """
    rows = graph.ro_query(query, params={"payment_id": payment_id}).result_set
    issues = []
    for variation_id, inspection_id, complete, compliant, reference in rows:
        if inspection_id is None:
            issues.append(f"HOLD: {variation_id} has no inspection evidence.")
        elif complete is not True or compliant is not True:
            issues.append(f"HOLD: {variation_id} completion and specification compliance are not both verified.")
        elif not reference:
            issues.append(f"HOLD: {variation_id} inspection has no evidence reference.")
    return issues
if __name__ == "__main__":
    print(get_missing_approvals("PAY-001"))
