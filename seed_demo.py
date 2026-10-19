"""Create demo fixtures while preserving existing saved reviews."""
from falkordb import FalkorDB

NODES = [
    ("Project", "PRJ-001", {"name": "Enugu Demo Build"}),
    ("Agreement", "AGR-001", {
        "scope": "Ground-floor blockwork",
        "amount_ngn": 5000000,
        "payment_rule": "FULL_AFTER_VERIFIED_COMPLETION",
        "payment_history_verified": True,
        "payment_history_ref": "DEMO-LEDGER-AGR-001",
    }),
    ("Agreement", "AGR-002", {
        "scope": "First-floor screeding",
        "amount_ngn": 1500000,
        "payment_rule": "FULL_AFTER_VERIFIED_COMPLETION",
        "payment_history_verified": True,
        "payment_history_ref": "DEMO-LEDGER-AGR-002-EMPTY",
    }),
    ("Payment", "PMT-001", {"amount_ngn": 2000000}),
    ("Variation", "VAR-001", {
        "description": "Additional drainage work",
        "amount_ngn": 500000,
    }),
    ("Person", "PERSON-OKEY", {"name": "Okey"}),
    ("Person", "PERSON-CHAIRMAN", {"name": "Chairman"}),
    ("Person", "PERSON-ENGINEER", {"name": "Demo Site Engineer"}),
    ("Inspection", "INS-001", {
        "completion_verified": True,
        "specification_compliant": True,
        "evidence_ref": "DEMO-INSPECTION-001",
    }),
    ("Inspection", "INS-VAR-001", {
        "completion_verified": True,
        "specification_compliant": True,
        "evidence_ref": "DEMO-DRAINAGE-INSPECTION-001",
    }),
    ("PaymentRequest", "PAY-001", {
        "amount_ngn": 5000000,
        "description": "Request exceeds remaining balance",
    }),
    ("PaymentRequest", "PAY-002", {
        "amount_ngn": 3500000,
        "description": "Remaining blockwork and approved drainage",
    }),
    ("PaymentRequest", "PAY-003", {
        "amount_ngn": 1500000,
        "description": "Awaiting inspection evidence",
    }),
]

EDGES = [
    ("PRJ-001", "HAS_AGREEMENT", "AGR-001"),
    ("PRJ-001", "HAS_AGREEMENT", "AGR-002"),
    ("PMT-001", "PAID_AGAINST", "AGR-001"),
    ("VAR-001", "VARIATION_OF", "AGR-001"),
    ("VAR-001", "REQUIRES_APPROVAL_FROM", "PERSON-OKEY"),
    ("VAR-001", "REQUIRES_APPROVAL_FROM", "PERSON-CHAIRMAN"),
    ("PERSON-OKEY", "APPROVED", "VAR-001"),
    ("PERSON-CHAIRMAN", "APPROVED", "VAR-001"),
    ("INS-001", "INSPECTS", "AGR-001"),
    ("INS-VAR-001", "INSPECTS", "VAR-001"),
    ("PERSON-ENGINEER", "RECORDED", "INS-001"),
    ("PERSON-ENGINEER", "RECORDED", "INS-VAR-001"),
    ("PAY-001", "AGAINST", "AGR-001"),
    ("PAY-002", "AGAINST", "AGR-001"),
    ("PAY-003", "AGAINST", "AGR-002"),
    ("PAY-001", "INCLUDES_VARIATION", "VAR-001"),
    ("PAY-002", "INCLUDES_VARIATION", "VAR-001"),
]


def seed_demo():
    graph = FalkorDB(host="localhost", port=6379).select_graph("buildguard")
    for label, node_id, fields in NODES:
        fields = {**fields, "demo": True}
        setters = ", ".join(f"n.{key} = ${key}" for key in fields)
        graph.query(
            f"MERGE (n:{label} {{id: $node_id}}) SET {setters}",
            params={"node_id": node_id, **fields},
        )
    for source, relation, target in EDGES:
        graph.query(
            "MATCH (a {id: $source}), (b {id: $target}) "
            f"MERGE (a)-[edge:{relation}]->(b) SET edge.demo = true",
            params={"source": source, "target": target},
        )
    print("Demo records ready. Existing saved reviews were kept.")


if __name__ == "__main__":
    seed_demo()
    from payment_review import review_payment

    expected = {
        "PAY-001": "INVESTIGATE",
        "PAY-002": "APPROVE",
        "PAY-003": "HOLD",
    }
    for payment_id, outcome in expected.items():
        report = review_payment(payment_id, persist=False)
        actual = report["recommendation"]
        print(f"{payment_id}: {actual}")
        if actual != outcome:
            raise RuntimeError(f"Expected {outcome} for {payment_id}.")
