"""Validation, account, matching and local assistant business rules."""
import hashlib
import hmac
import re
import secrets
import time
import uuid


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class ValidationError(ValueError):
    """Input did not meet a project rule."""


class AuthService:
    def __init__(self, database):
        self.database = database

    @staticmethod
    def _password_hash(password, salt):
        return hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt), n=2**14, r=8, p=1).hex()

    def register(self, name, email, password):
        name, email = str(name or "").strip(), str(email or "").strip().lower()
        if not name or len(name) > 60:
            raise ValidationError("Enter a name between 1 and 60 characters.")
        if len(email) > 120 or not EMAIL_PATTERN.fullmatch(email):
            raise ValidationError("Enter a valid email address.")
        if not isinstance(password, str) or not 10 <= len(password) <= 200:
            raise ValidationError("Use a password between 10 and 200 characters.")
        if self.database.get_user_by_email(email):
            raise ValidationError("An account already exists for this email.")
        user_id, salt = uuid.uuid4().hex, secrets.token_hex(16)
        self.database.create_user(user_id, name, email, salt, self._password_hash(password, salt),
                                  time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        return self.database.get_user_by_id(user_id)

    def verify_login(self, email, password):
        user = self.database.get_user_by_email(str(email or "").strip().lower())
        if not user or not isinstance(password, str) or len(password) > 200:
            return None
        candidate = self._password_hash(password, user["salt"])
        return self.database.get_user_by_id(user["id"]) if hmac.compare_digest(candidate, user["password_hash"]) else None


def keyword_score(lost, found):
    """Return a transparent weighted overlap score from 0 to 100."""
    def words(value):
        return set(re.findall(r"[a-z0-9]+", str(value or "").lower()))
    score = 0.0
    for weight, left, right in ((3, "name", "name"), (2, "category", "category"),
                                (2, "color", "color"), (3, "location", "location"),
                                (2, "description", "description")):
        tokens = words(lost.get(left))
        other = words(found.get(right))
        if tokens:
            score += weight * len(tokens & other) / len(tokens)
    return min(100, round(score / 12 * 100))


class MatchService:
    """Build candidate matches; verification and recovery remain separate actions."""
    def __init__(self, threshold=35):
        self.threshold = threshold

    def suggestions(self, data):
        existing = {(match.get("lostId"), match.get("foundId")) for match in data["matches"]}
        results = []
        for lost in data["lost"]:
            for found in data["found"]:
                score = keyword_score(lost, found)
                if score >= self.threshold and (lost.get("id"), found.get("id")) not in existing:
                    results.append({"lostId": lost.get("id"), "foundId": found.get("id"), "score": score})
        return sorted(results, key=lambda item: item["score"], reverse=True)


class AssistantService:
    """Provide deterministic local report help without external AI or credentials."""
    def answer(self, question, data):
        query = str(question or "").strip()
        if not query or len(query) > 1000:
            raise ValidationError("Enter a question from 1 to 1000 characters.")
        words = set(re.findall(r"[a-z0-9]+", query.lower()))
        if any(word in words for word in {"match", "matches", "matching"}):
            suggestions = MatchService().suggestions(data)
            if not suggestions:
                return "There are no new possible matches in your reports yet. Add reports with matching item details or check the existing matches."
            pair = suggestions[0]
            return f"Top possible match: lost report {pair['lostId']} and found report {pair['foundId']} (keyword score {pair['score']}%). Review both reports before verification."
        candidates = data["lost"] + data["found"]
        ranked = []
        for item in candidates:
            item_words = set(re.findall(r"[a-z0-9]+", " ".join(str(item.get(k, "")) for k in ("name", "category", "color", "location", "description")).lower()))
            overlap = len(words & item_words)
            if overlap:
                ranked.append((overlap, item))
        if ranked:
            ranked.sort(key=lambda result: result[0], reverse=True)
            item = ranked[0][1]
            return f"Closest report: {item.get('id')} is a {item.get('color', '').lower()} {item.get('name')} at {item.get('location')} ({item.get('status', 'unrecovered')}). Use Search Items to review the full report."
        if any(word in words for word in {"recover", "recovery", "verify", "verified"}):
            return "Review the possible pair first, choose Verify Match, and mark it recovered only after the item is returned."
        return f"Your register currently has {len(data['lost'])} lost reports, {len(data['found'])} found reports, and {len(data['matches'])} saved matches. Ask about an item, location, possible match, or recovery steps."
