"""Tests for authentication, storage, keyword matching, and assistant rules."""
import tempfile
import unittest
from pathlib import Path

from app import app
from lost_found.database import Database
from lost_found.services import AssistantService, AuthService, MatchService, ValidationError


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp_dir.name) / "test.sqlite")
        self.auth = AuthService(self.database)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_register_login_and_unique_email(self):
        user = self.auth.register("Student", "student@example.com", "safe-password-123")
        self.assertEqual(user["name"], "Student")
        self.assertIsNotNone(self.auth.verify_login("STUDENT@example.com", "safe-password-123"))
        self.assertIsNone(self.auth.verify_login("student@example.com", "wrong-password"))
        with self.assertRaises(ValidationError):
            self.auth.register("Other", "student@example.com", "safe-password-123")

    def test_registration_rejects_invalid_email_and_short_password(self):
        for email, password in (("bad-email", "safe-password-123"), ("a@b.com", "short")):
            with self.subTest(email=email):
                with self.assertRaises(ValidationError):
                    self.auth.register("Student", email, password)

    def test_keyword_suggestion_does_not_mutate_recovery_status(self):
        data = {
            "lost": [{"id": "L1", "name": "Wallet", "category": "Personal Belongings", "color": "Black", "location": "Classroom", "description": "leather wallet"}],
            "found": [{"id": "F1", "name": "Wallet", "category": "Personal Belongings", "color": "Black", "location": "Classroom", "description": "wallet near bench"}],
            "matches": [], "activity": []}
        matches = MatchService().suggestions(data)
        self.assertEqual(matches[0]["lostId"], "L1")
        self.assertEqual(matches[0]["foundId"], "F1")
        self.assertNotIn("recovered", matches[0])
        self.assertEqual(data["matches"], [])

    def test_assistant_answers_from_report_data_and_validates_question(self):
        data = {"lost": [], "found": [], "matches": [], "activity": []}
        answer = AssistantService().answer("How do I recover an item?", data)
        self.assertIn("verify", answer.lower())
        with self.assertRaises(ValidationError):
            AssistantService().answer("", data)


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        import app as app_module
        self.module = app_module
        self.previous = app_module.database
        self.previous_auth = app_module.auth_service
        app_module.database = Database(Path(self.temp_dir.name) / "routes.sqlite")
        app_module.auth_service = AuthService(app_module.database)
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def tearDown(self):
        self.client = None
        self.module.database = self.previous
        self.module.auth_service = self.previous_auth
        self.database = None
        self.previous = None
        self.temp_dir.cleanup()

    def test_login_required_and_user_data_persists(self):
        self.assertEqual(self.client.get("/api/data").status_code, 401)
        response = self.client.post("/api/auth/register", json={"name": "Student", "email": "student@example.com", "password": "safe-password-123"})
        self.assertEqual(response.status_code, 201)
        payload = {"lost": [{"id": "L100"}], "found": [], "matches": [], "activity": []}
        self.assertEqual(self.client.put("/api/data", json=payload).status_code, 200)
        self.assertEqual(self.client.get("/api/data").json, payload)
        self.assertIn("lost-found-reports.json", self.client.get("/api/export").headers["Content-Disposition"])
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 200)
        self.assertEqual(self.client.get("/api/data").status_code, 401)

    def test_local_assistant_endpoint(self):
        self.client.post("/api/auth/register", json={"name": "Student", "email": "student@example.com", "password": "safe-password-123"})
        response = self.client.post("/api/assistant", json={"question": "Show possible matches"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["mode"], "local")
        self.assertIn("no new possible matches", response.json["answer"])


if __name__ == "__main__":
    unittest.main()
