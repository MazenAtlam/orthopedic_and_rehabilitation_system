"""Flask application factory.

PLACEHOLDER by Mazen: gives the Docker stack and the CI a working health check.
Hussein replaces / extends this file with blueprints, JWT and error handlers.
"""

from flask import Flask, Response, jsonify
from flask_cors import CORS

from app.config import Config


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)
    CORS(app, origins=app.config["CORS_ORIGINS"])

    @app.get("/api/v1/health")
    def health() -> tuple[Response, int]:
        return jsonify({"status": "ok"}), 200

    return app
