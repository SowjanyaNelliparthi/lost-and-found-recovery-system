"""Start the local Lost and Found web application."""
import hashlib
import json
import os
import re
import secrets
import threading
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, make_response, request, send_from_directory
from werkzeug.serving import make_server

from lost_found.database import Database
from lost_found.services import AssistantService, AuthService, ValidationError

ROOT = Path(__file__).resolve().parent


def load_local_environment():
    """Read simple KEY=VALUE settings without requiring an extra dependency."""
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_local_environment()
app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 1_100_000
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("APP_ENV") == "production"
database = Database(os.environ.get("DATABASE_URL", os.environ.get("DB_PATH", str(ROOT / "data" / "lost-found.sqlite"))))
auth_service = AuthService(database)
assistant_service = AssistantService()
SESSION_COOKIE = "lf_session"


def error(message, status=400):
    return jsonify(error=message), status


def read_json():
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise ValidationError("Request body must be a JSON object.")
    return value


def token_digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def current_user():
    token = request.cookies.get(SESSION_COOKIE, "")
    return database.get_session_user(token_digest(token), int(time.time() * 1000)) if token else None


def require_user():
    user = current_user()
    if not user:
        return None, error("Please log in to continue.", 401)
    return user, None


def set_session_cookie(response, token):
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="Lax", secure=app.config["SESSION_COOKIE_SECURE"],
                        max_age=7 * 24 * 60 * 60, path="/")
    return response


def issue_session(user):
    token = secrets.token_urlsafe(32)
    database.create_session(token_digest(token), user["id"], int(time.time() * 1000) + 7 * 24 * 60 * 60 * 1000)
    response = make_response(jsonify(user={"name": user["name"], "email": user["email"]}), 201)
    return set_session_cookie(response, token)


@app.get("/api/health")
def health():
    return jsonify(ok=True, aiConfigured=False, assistantMode="local report helper")


@app.post("/api/auth/register")
def register():
    try:
        body = read_json()
        user = auth_service.register(body.get("name"), body.get("email"), body.get("password"))
        return issue_session(user)
    except ValidationError as exc:
        return error(str(exc))
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            return error("An account already exists for this email.", 409)
        app.logger.exception("Registration failed")
        return error("The account could not be created.", 500)


@app.post("/api/auth/login")
def login():
    try:
        body = read_json()
        user = auth_service.verify_login(body.get("email"), body.get("password"))
        if not user:
            return error("Email or password is incorrect.", 401)
        response = make_response(jsonify(user={"name": user["name"], "email": user["email"]}))
        token = secrets.token_urlsafe(32)
        database.create_session(token_digest(token), user["id"], int(time.time() * 1000) + 7 * 24 * 60 * 60 * 1000)
        return set_session_cookie(response, token)
    except ValidationError as exc:
        return error(str(exc))
    except Exception:
        app.logger.exception("Login failed")
        return error("The account could not be accessed.", 500)


@app.post("/api/auth/logout")
def logout():
    token = request.cookies.get(SESSION_COOKIE, "")
    if token:
        database.delete_session(token_digest(token))
    response = make_response(jsonify(ok=True))
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="Lax")
    return response


@app.get("/api/auth/me")
def who_am_i():
    user = current_user()
    return jsonify(user={"name": user["name"], "email": user["email"]} if user else None)


def valid_data(payload, previous=None):
    """Check report structure and enforce match/recovery state transitions."""
    if (not isinstance(payload, dict)
            or not all(isinstance(payload.get(key), list) for key in ("lost", "found", "matches", "activity"))
            or len(json.dumps(payload)) > 1_000_000):
        return False

    reports = {}
    for kind, prefix in (("lost", "L"), ("found", "F")):
        reports[kind] = {}
        for item in payload[kind]:
            if not isinstance(item, dict):
                return False
            item_id = item.get("id")
            if not isinstance(item_id, str) or not re.fullmatch(rf"{prefix}\d+", item_id):
                return False
            status = item.get("status", "unrecovered")
            if not isinstance(status, str) or status not in {"unrecovered", "recovered"} or item_id in reports[kind]:
                return False
            reports[kind][item_id] = item

    pairs = {}
    recovered_lost, recovered_found = set(), set()
    for match in payload["matches"]:
        if not isinstance(match, dict):
            return False
        lost_id, found_id = match.get("lostId"), match.get("foundId")
        if (not isinstance(lost_id, str) or not isinstance(found_id, str)
                or lost_id not in reports["lost"] or found_id not in reports["found"]):
            return False
        key = (lost_id, found_id)
        if key in pairs:
            return False
        verified = match.get("verified", False)
        recovered = match.get("recovered", False)
        if type(verified) is not bool or type(recovered) is not bool or (recovered and not verified):
            return False
        pairs[key] = match
        if recovered:
            if lost_id in recovered_lost or found_id in recovered_found:
                return False
            recovered_lost.add(lost_id)
            recovered_found.add(found_id)

    for kind, recovered_ids in (("lost", recovered_lost), ("found", recovered_found)):
        for item_id, item in reports[kind].items():
            if (item.get("status", "unrecovered") == "recovered") != (item_id in recovered_ids):
                return False

    if previous is not None:
        # Reports cannot silently disappear from an account's register.
        for kind in ("lost", "found"):
            old_ids = {item.get("id") for item in previous.get(kind, []) if isinstance(item, dict)}
            if not old_ids.issubset(reports[kind]):
                return False
        old_pairs = {(m.get("lostId"), m.get("foundId")): m for m in previous.get("matches", []) if isinstance(m, dict)}
        for key, match in pairs.items():
            old_match = old_pairs.get(key)
            if old_match is None and (match.get("verified", False) or match.get("recovered", False)):
                return False
            if old_match is not None:
                if old_match.get("verified", False) and not match.get("verified", False):
                    return False
                if old_match.get("recovered", False) and not match.get("recovered", False):
                    return False
                if match.get("recovered", False) and not old_match.get("verified", False):
                    return False
        for key, old_match in old_pairs.items():
            if old_match.get("recovered", False) and not pairs.get(key, {}).get("recovered", False):
                return False

    return True


@app.get("/api/data")
def get_data():
    user, failure = require_user()
    if failure:
        return failure
    return jsonify(database.read_user_data(user["id"]))


@app.put("/api/data")
def put_data():
    user, failure = require_user()
    if failure:
        return failure
    try:
        payload = read_json()
        current = database.read_user_data(user["id"])
        if not valid_data(payload, current):
            return error("Report data has an invalid format or is too large.")
        database.save_user_data(user["id"], payload, datetime.now(timezone.utc).isoformat())
        return jsonify(ok=True)
    except ValidationError as exc:
        return error(str(exc))
    except Exception:
        app.logger.exception("Saving report data failed")
        return error("The report data could not be saved.", 500)


@app.post("/api/assistant")
def assistant():
    user, failure = require_user()
    if failure:
        return failure
    try:
        body = read_json()
        answer = assistant_service.answer(body.get("question"), database.read_user_data(user["id"]))
        return jsonify(answer=answer, mode="local")
    except ValidationError as exc:
        return error(str(exc))
    except Exception:
        app.logger.exception("Assistant request failed")
        return error("The assistant could not read your reports.", 500)


@app.get("/api/export")
def export_data():
    user, failure = require_user()
    if failure:
        return failure
    payload = database.read_user_data(user["id"])
    response = make_response(json.dumps(payload, ensure_ascii=False, indent=2))
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=lost-found-reports.json"
    return response


@app.get("/")
def index():
    return send_from_directory(ROOT, "index.html")


@app.get("/<path:filename>")
def static_files(filename):
    if filename.startswith(("data/", ".", "lost_found/", "tests/", "Submission/")):
        return error("Not found.", 404)
    return send_from_directory(ROOT, filename)


@app.errorhandler(413)
def too_large(_exc):
    return error("The request is too large.", 413)


@app.errorhandler(404)
def not_found(_exc):
    if request.path.startswith("/api/"):
        return error("API route not found.", 404)
    return error("Page not found.", 404)


if __name__ == "__main__":
    production = os.environ.get("APP_ENV") == "production" or "PORT" in os.environ
    host = os.environ.get("HOST", "0.0.0.0" if production else "127.0.0.1")
    preferred_port = int(os.environ.get("PORT", "8000"))
    ports = list(dict.fromkeys([preferred_port, 8080, 5000, 3000]))
    server = None
    for port in ports:
        try:
            server = make_server(host, port, app, threaded=True)
            break
        except OSError as exc:
            print(f"Port {port} is unavailable ({exc}). Trying another local port...")

    if server is None:
        print("Windows would not allow the app to use ports 8000, 8080, 5000, or 3000.")
        print("This is a local Windows port restriction, not an internet connection issue.")
        input("Press Enter to close this window...")
    else:
        address = f"http://{host}:{server.server_port}"
        print(f"Starting Lost and Found at {address}")
        print("Keep this window open. Close it with Ctrl+C when you finish.")
        if os.environ.get("APP_ENV") != "production":
            threading.Timer(1.2, lambda: webbrowser.open(address)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nLost and Found has stopped.")
        finally:
            server.server_close()
