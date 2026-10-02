"""
AWS Lambda entrypoint for the "Lambda (Function URL / Mock Gate)" box, for
deployment to real AWS infrastructure (see infra/template.yaml).

This wraps the same backend.lambda_handler functions used by the local
FastAPI mock gate (backend/server.py), so behavior is identical whether
running locally or deployed. The `backend/` package is bundled alongside
this file in the Lambda deployment package.

Routing follows the Lambda Function URL payload format v2.0
(API Gateway-style event).
"""
import json

from backend.lambda_handler import (
    HandlerError,
    approve_handler,
    generate_draft_handler,
    list_audit_log_handler,
    list_clients_handler,
)

ROUTES = {
    ("POST", "/generate-draft"): generate_draft_handler,
    ("POST", "/approve"): approve_handler,
}


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "/")

    try:
        if method == "GET" and path == "/health":
            return _response(200, {"status": "ok"})
        if method == "GET" and path == "/clients":
            return _response(200, list_clients_handler())
        if method == "GET" and path == "/audit-log":
            return _response(200, list_audit_log_handler())

        handler_fn = ROUTES.get((method, path))
        if handler_fn is None:
            return _response(404, {"error": f"No route for {method} {path}"})

        payload = json.loads(event.get("body") or "{}")
        result = handler_fn(payload)
        return _response(200, result)

    except HandlerError as e:
        return _response(e.status_code, {"error": e.message})
    except Exception as e:  # noqa: BLE001 - surface unexpected errors to the client
        return _response(500, {"error": f"Internal error: {e}"})
