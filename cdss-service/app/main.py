"""CDSS service. PLACEHOLDER - the real inference API is built in Phase 3."""

from flask import Flask, Response, jsonify

app = Flask(__name__)


@app.get("/health")
def health() -> tuple[Response, int]:
    return jsonify({"status": "ok"}), 200
