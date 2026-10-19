from pathlib import Path
from flask import Flask, jsonify, request, render_template
from werkzeug.exceptions import HTTPException
from falkordb import FalkorDB
from redis.exceptions import RedisError
from payment_review import review_payment
from review_history import get_review_history

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16384

def blocked_response(message, status):
    return jsonify({
        "recommendation": "HOLD",
        "review_complete": False,
        "error": message,
        "findings": ["HOLD: " + message],
    }), status

@app.after_request
def prevent_stale_results(response):
    response.headers["Cache-Control"] = "no-store"
    return response

@app.get("/")
def index():
    template = Path(app.root_path) / "templates" / "index.html"
    if template.is_file():
        return render_template("index.html")
    return jsonify(service="BuildGuard", message="API is running")

@app.get("/api/health")
def health():
    graph = FalkorDB(host="localhost", port=6379).select_graph("buildguard")
    rows = graph.ro_query("MATCH (n) RETURN count(n)").result_set
    return jsonify(status="ok", graph="buildguard", nodes=rows[0][0])

@app.get("/api/requests")
def list_requests():
    graph = FalkorDB(host="localhost", port=6379).select_graph("buildguard")
    query = """
    MATCH (r:PaymentRequest {demo: true})
    RETURN r.id, r.description, r.amount_ngn
    ORDER BY r.id
    """
    rows = graph.ro_query(query).result_set
    return jsonify([
        {"payment_id": payment_id, "description": description, "amount_ngn": amount}
        for payment_id, description, amount in rows
    ])

@app.get("/api/review/<payment_id>")
def preview_review(payment_id):
    return jsonify(review_payment(payment_id, persist=False))

@app.post("/api/review")
def run_review():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("Send a JSON object containing payment_id.")
    return jsonify(review_payment(data.get("payment_id"), persist=True))

@app.get("/api/history/<payment_id>")
def history(payment_id):
    return jsonify(get_review_history(payment_id))

@app.errorhandler(RedisError)
def graph_error(error):
    return blocked_response("Graph review is unavailable; verification could not be completed.", 503)

@app.errorhandler(ValueError)
def input_error(error):
    return blocked_response(str(error), 400)

@app.errorhandler(HTTPException)
def http_error(error):
    return blocked_response(error.description, error.code or 500)

@app.errorhandler(Exception)
def unexpected_error(error):
    app.logger.error("Request failed: %s", type(error).__name__)
    return blocked_response("Review could not be completed.", 500)


@app.post("/api/agent")
def agent_review():
    from agent import ask_buildguard
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("Send payment_id and question as a JSON object.")
    try:
        return jsonify(ask_buildguard(
            data.get("payment_id"),
            data.get("question", "Explain this request and its saved history."),
        ))
    except (ValueError, RedisError):
        raise
    except Exception as error:
        app.logger.warning("Agent request failed: %s", type(error).__name__)
        return blocked_response(
            "AI-assisted review is unavailable. Please try again.", 503
        )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
