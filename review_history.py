import json
from datetime import datetime, timezone
from uuid import uuid4
from falkordb import FalkorDB


def get_graph():
    return FalkorDB(host="localhost", port=6379).select_graph("buildguard")


def add_label(record, sequence):
    if sequence is not None:
        record["review_label"] = f"REV-{int(sequence):03d}"
    return record


def save_review(review):
    record = dict(review)
    record.pop("review_label", None)
    record["review_id"] = "REV-" + uuid4().hex
    record["created_at"] = datetime.now(timezone.utc).isoformat()
    query = """
    MATCH (request:PaymentRequest {id: $payment_id})
    MERGE (counter:ReviewSequence {id: 'buildguard-reviews'})
    WITH request, counter, coalesce(counter.value, 0) + 1 AS next_number
    SET counter.value = next_number
    CREATE (request)-[:HAS_REVIEW]->(saved:Review {
        id: $review_id,
        created_at: $created_at,
        payload_json: $payload_json,
        sequence: next_number
    })
    RETURN saved.sequence
    """
    rows = get_graph().query(query, params={
        "payment_id": record["payment_id"],
        "review_id": record["review_id"],
        "created_at": record["created_at"],
        "payload_json": json.dumps(record),
    }).result_set
    if len(rows) != 1:
        raise ValueError("Review was not saved against exactly one payment request.")
    return add_label(record, rows[0][0])


def get_review_history(payment_id):
    query = """
    MATCH (:PaymentRequest {id: $payment_id})-[:HAS_REVIEW]->(saved:Review)
    RETURN saved.payload_json, saved.sequence
    ORDER BY saved.created_at DESC, saved.sequence DESC
    LIMIT 20
    """
    rows = get_graph().ro_query(
        query, params={"payment_id": payment_id}
    ).result_set
    return [
        add_label(json.loads(payload), sequence)
        for payload, sequence in rows
    ]


def number_existing_reviews():
    graph = get_graph()
    rows = graph.ro_query("""
        MATCH (saved:Review)
        RETURN saved.id, saved.sequence
        ORDER BY saved.created_at, saved.id
    """).result_set
    numbers = [sequence for _, sequence in rows if sequence is not None]
    if any(type(n) is not int or n < 1 for n in numbers) or len(numbers) != len(set(numbers)):
        raise ValueError("Existing review numbers need manual checking.")
    graph.query("""
        MERGE (counter:ReviewSequence {id: 'buildguard-reviews'})
        SET counter.value = CASE
            WHEN coalesce(counter.value, 0) < $minimum THEN $minimum
            ELSE coalesce(counter.value, 0) END
        RETURN counter.value
    """, params={"minimum": max(numbers, default=0)})
    for review_id, sequence in rows:
        if sequence is None:
            graph.query("""
                MATCH (saved:Review {id: $review_id})
                WHERE saved.sequence IS NULL
                MATCH (counter:ReviewSequence {id: 'buildguard-reviews'})
                WITH saved, counter, counter.value + 1 AS next_number
                SET counter.value = next_number, saved.sequence = next_number
                RETURN saved.sequence
            """, params={"review_id": review_id})
    return len(rows)


if __name__ == "__main__":
    print(f"Short labels ready for {number_existing_reviews()} saved reviews.")
    for review in get_review_history("PAY-001")[:5]:
        print(review["review_label"], review["created_at"], review["recommendation"])
