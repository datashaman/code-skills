"""
helpers/transport/receiver.py

Local webhook receiver. Used in `gh_forward` and `self_hosted_webhook`
transports.

Listens on an HTTP port, verifies the GitHub webhook secret, normalizes
the event, and dispatches it through the reconcile loop.

For production self-hosted use, a real WSGI/ASGI server should run this
behind a TLS terminator. For local development (`gh webhook forward`),
a single-thread dev server is fine.
"""

from __future__ import annotations

import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
import os
from pathlib import Path

from ..reconcile import checkpoint
from . import normalize

logger = logging.getLogger(__name__)

PROCESSED_EVENTS_FILE = Path(".workflow/state/processed_events.yml")


class WebhookHandler(BaseHTTPRequestHandler):
    """
    Minimal webhook receiver. Verifies the secret, normalizes the event,
    dispatches to reconcile.

    Returns 200 immediately on success, 401 on signature mismatch, 500
    on internal failure (which causes GitHub to retry).
    """

    secret: bytes = b""  # set by serve()

    def log_message(self, format: str, *args) -> None:
        logger.info(f"{self.address_string()} - {format % args}")

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)

        signature = self.headers.get("X-Hub-Signature-256", "")
        if not _verify_signature(self.secret, body, signature):
            self.send_response(401)
            self.end_headers()
            return

        delivery_id = self.headers.get("X-GitHub-Delivery", "")
        if _already_processed(delivery_id):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"duplicate"}')
            return

        github_event = self.headers.get("X-GitHub-Event", "")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        try:
            events = normalize.normalize_event(github_event, payload, provider="github")
            for event in events:
                checkpoint.reconcile_with_checkpoint(
                    intent="event_driven",
                    context={"event": event},
                )
            _mark_processed(delivery_id)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        except Exception as e:
            logger.exception("Failed to process webhook")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_GET(self) -> None:
        # Health check
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')


def serve(host: str = "0.0.0.0", port: int = 8080, secret_env: str = "WEBHOOK_SECRET") -> None:
    """
    Start the receiver. Blocking; intended for `workflow-advisor serve`.
    """
    secret = os.environ.get(secret_env, "").encode()
    if not secret:
        raise RuntimeError(
            f"{secret_env} environment variable is not set. Webhook secret is required."
        )

    WebhookHandler.secret = secret
    server = HTTPServer((host, port), WebhookHandler)
    logger.info(f"Webhook receiver listening on {host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down receiver")
    finally:
        server.server_close()


def _verify_signature(secret: bytes, body: bytes, signature_header: str) -> bool:
    """GitHub sends X-Hub-Signature-256: sha256={hex_digest}."""
    if not signature_header.startswith("sha256="):
        return False
    expected = signature_header.split("=", 1)[1]
    actual = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, actual)


def _already_processed(delivery_id: str) -> bool:
    """Check if this delivery ID was already processed (idempotency)."""
    if not delivery_id or not PROCESSED_EVENTS_FILE.exists():
        return False
    import yaml

    with PROCESSED_EVENTS_FILE.open() as f:
        records = yaml.safe_load(f) or {}
    return delivery_id in (records.get("delivery_ids") or [])


def _mark_processed(delivery_id: str) -> None:
    """Append the delivery ID to the processed list (with TTL pruning)."""
    if not delivery_id:
        return
    from datetime import datetime, timezone

    import yaml

    PROCESSED_EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    records = {}
    if PROCESSED_EVENTS_FILE.exists():
        with PROCESSED_EVENTS_FILE.open() as f:
            records = yaml.safe_load(f) or {}

    delivery_ids = records.get("delivery_ids", [])
    delivery_ids.append(delivery_id)
    # Cap to last 1000 (TTL would be better; this is a simple ring)
    delivery_ids = delivery_ids[-1000:]

    records["delivery_ids"] = delivery_ids
    records["last_updated"] = datetime.now(timezone.utc).isoformat()
    with PROCESSED_EVENTS_FILE.open("w") as f:
        yaml.dump(records, f)
