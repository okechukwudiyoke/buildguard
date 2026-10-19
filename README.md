# BuildGuard

**Review before release.**

Construction payment oversight powered by FalkorDB and a Gemini agent.
BuildGuard connects agreements, previous payments, variations, approvals
and inspections to explain whether a request should proceed to human review.

## Demo cases

| Request | Finding | Recommendation |
| --- | --- | --- |
| PAY-001 | NGN 5m requested against NGN 3.5m remaining | INVESTIGATE |
| PAY-002 | NGN 3.5m requested with verified demo evidence | APPROVE |
| PAY-003 | Inspection evidence missing | HOLD |

These are independent scenarios. BuildGuard does not reserve or release funds.

## How it works

FalkorDB stores the connected records and saved review snapshots.
Cypher queries traverse these relationships:

- PaymentRequest --AGAINST--> Agreement
- Payment --PAID_AGAINST--> Agreement
- PaymentRequest --INCLUDES_VARIATION--> Variation
- Variation --VARIATION_OF--> Agreement
- Variation --REQUIRES_APPROVAL_FROM--> Person
- Person --APPROVED--> Variation
- Inspection --INSPECTS--> Agreement or Variation
- PaymentRequest --HAS_REVIEW--> Review

The Python policy engine checks the remaining balance, supported payment
rule, required approvals, inspections and referenced payment history.

The Gemini agent must retrieve both tools before answering:

1. get_payment_review: current graph-backed policy review.
2. get_review_history: up to three recent saved reviews.

The displayed recommendation comes from Python. The agent explains the
evidence and changes within the retrieved history. Its tools cannot change
approvals, inspections or payments.

## Local setup

Requirements: Python 3.12, Docker with Docker Compose, and Git.
Port 6379 must be available.

```bash
git clone https://github.com/okechukwudiyoke/buildguard.git
cd buildguard
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
sudo docker compose up -d --wait
python seed_demo.py
```

The Docker image is pinned by digest. A named volume persists graph data.
The seed restores demo fixture values and preserves existing saved reviews.
A fresh installation starts with empty review history.

Ask BuildGuard requires a Gemini API key. Run this command by itself,
enter your key at the prompt, and press Enter:

```bash
read -r -s -p "Gemini API key: " GEMINI_API_KEY
```

Then start the application:

```bash
export GEMINI_API_KEY
export GEMINI_MODEL="gemini-3.8-flash"
python app.py
```

Open http://127.0.0.1:5000.

Policy previews, saved reviews and evidence panels also work without an
API key. Start those features with `python app.py`.

## Demonstration

1. Select PAY-001: the request exceeds the remaining balance by NGN 1.5m.
2. Click Run & save review to record a snapshot.
3. Ask: "Explain the findings and what changed since earlier reviews."
4. Expand View graph tool results to inspect the retrieved evidence.
5. Open a saved review to inspect its recorded evidence.
6. Select PAY-002 for APPROVE and PAY-003 for HOLD.

A preview reads current evidence without saving. Saved reviews retain
UUIDs and receive short references such as REV-001. Numbering spans all
requests, so one request's history can contain gaps.

The dashboard retrieves up to 20 saved reviews per request. The agent
retrieves up to three. Missing fields in older reports do not prove
the underlying database lacked that evidence.

## Command-line use

```bash
python seed_demo.py
python payment_review.py PAY-001
python agent.py PAY-001 "Why is this request flagged?"
python review_history.py
```

`payment_review.py` saves a review. `review_history.py` also assigns
short references to older unnumbered reviews while retaining stored UUIDs
and JSON reports.

## Main files

| File | Purpose |
| --- | --- |
| app.py | Flask API |
| templates/index.html | Dashboard and agent interface |
| payment_review.py | Payment policy checks |
| inspect_variation.py | Approval and variation inspection queries |
| review_history.py | Saved reviews and short references |
| agent.py | Gemini tool loop |
| seed_demo.py | Reproducible demo fixtures |
| compose.yaml | Pinned database image and persistent volume |

## Scope and limitations

Policy version: fixed-price-demo-v1.
Supported rule: FULL_AFTER_VERIFIED_COMPLETION.
Variations require approval from Okey and Chairman.

All ledger and inspection references are demo fixtures. They do not
represent external document verification or bank reconciliation.
Saved JSON reports are snapshots, not a tamper-proof audit system.

Graph failures return HOLD with an incomplete review. Provider failures
return an agent error. The interface clears stale results when requests
change or reviews fail.

This local demonstration has no authentication. Production work would
require access controls, exact monetary arithmetic, transactional
consistency, document verification and broader payment policies.

APPROVE means the implemented demo checks passed for human review.
BuildGuard does not release payments.

## Author

Okechukwu Diyoke  
https://github.com/okechukwudiyoke

## Hackathon track

Agents That Act on Connected Data.

## AI assistance

ChatGPT/Codex assisted with coding, debugging, documentation and test design.
Okechukwu Diyoke supplied the construction use case and policy requirements,
made the product and policy decisions, and ran and checked the demo scenarios
through guided development sessions. The project uses synthetic demo data.
