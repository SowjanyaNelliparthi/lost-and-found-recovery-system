# Lost and Found Item Recovery Management System

## Student details

- Student name: **Sowjanya Nelliparthi**
- Student ID: **Add your student ID before submission**
- Project type: Individual Python project

## Problem statement

People may report a lost belonging and a found belonging using different descriptions. Without a shared searchable register, the owner may not discover that someone found the item. This application keeps the reports in separate lost and found lists and helps users review possible pairs.

## Objective

Provide an application to register, search, compare, verify, and track lost and found items. A possible keyword match is only a suggestion. It is never automatically marked recovered. The app runs locally with SQLite and can be published on Render with PostgreSQL.

## Features

- Register, log in, and log out; each account has its own saved reports.
- Add lost and found reports with name, category, color, location, date, and description.
- Search and view reports; browse possible matches.
- Verify a match, then record recovery after the item is returned.
- View summary counts and recent activity.
- Ask the local report assistant about saved reports and recovery steps. It uses deterministic keyword rules and works without an API key or internet AI service.
- Export your signed-in report data as a JSON file from `/api/export`.

## Technologies and Python concepts

Python 3.10+, Flask, SQLite for local use, PostgreSQL for the Render deployment, HTML, CSS, and browser JavaScript. Python concepts include variables and data types, conditionals, loops, functions, lists and dictionaries, classes and objects, constructors, encapsulation through service/repository boundaries, exception handling, JSON file export, regular expressions, and modules/packages. Inheritance is not forced into the design because it does not make these project operations clearer.

## Project structure

```text
app.py                    Flask routes and application startup
lost_found/
  database.py             SQLite database and repository operations
  models.py               User, ItemReport, and ItemMatch data classes
  services.py             Validation, authentication, matching, assistant logic
index.html                Dashboard layout
styles.css                Dashboard appearance
app.js                    Browser interactions and page rendering
data/                     SQLite data created when the app runs (not committed)
tests/test_operations.py  Automated project test cases
screenshots/              Add your own project screenshots here
Submission/               Project report and presentation
requirements.txt          Python package requirements
start.bat                 Windows setup and run helper
render.yaml               Render web service and PostgreSQL setup
```

The earlier Node version is preserved in `web-version/` for reference. The active project uses Python and Flask.

## Classes and methods

- `Database`: opens SQLite connections, creates tables, stores and reads users, sessions, and account report data.
- `AuthService`: validates account input, hashes passwords with per-user salts, registers users, and checks login credentials.
- `MatchService`: `suggestions(data)` compares report words with a weighted keyword score. It does not verify a match or mark recovery.
- `AssistantService`: `answer(question, data)` searches the signed-in report data using local rules and offers workflow guidance.
- `User`, `ItemReport`, and `ItemMatch`: data classes that describe the main project records.

## Application workflow

Browser input → Flask route → input validation and service rules → SQLite locally or PostgreSQL on Render → JSON response → dashboard/report output. User passwords are never stored as plain text. Session tokens are stored as hashes in the database and sent to the browser in an HttpOnly cookie.

## Business rules

- Lost reports and found reports are kept in separate lists.
- Each report receives a unique ID in the browser app.
- Keyword overlap creates a possible match only; people must review and verify it.
- Only verified matches can be marked recovered. Already recovered matches cannot be recovered again.
- Report entry requires login. Reports belong to the signed-in account.

## Validation and exception handling

Server-side validation checks names, email addresses, password lengths, question length, JSON shape, and data size. A regular expression validates email format. Flask routes catch validation errors and return clear messages and status codes. Database and request-size errors are also handled so they do not expose internal details to the browser. The interface validates required form fields as well.

## File handling and data storage

SQLite is used locally at `data/lost-found.sqlite`. On Render, the app uses the PostgreSQL connection supplied through `DATABASE_URL`. The authenticated `/api/export` route downloads the current account's reports as JSON. Local `data/` and `.env` are ignored by Git so personal report data and credentials are not included in the repository.

## Installation and execution (Windows)

1. Install Python 3.10 or later and ensure the `python` command works.
2. Open this project folder in File Explorer.
3. Double-click `start.bat`. If Flask is already installed, it starts the server without internet. If not, it needs internet once to install Flask from `requirements.txt`.
4. Keep the command window open; it must stay running while you use the app. The app chooses an available local port and opens the address in your browser (usually **http://127.0.0.1:8000**).
5. Register an account, create reports, and explore the dashboard. Close the server with Ctrl+C in its command window.

You can also run `python -m pip install -r requirements.txt`, followed by `python app.py`, from this folder. Locally, the app listens on your own computer only until it is deployed to a hosting service.

In VS Code, you can start the server from **Terminal → Run Task → Start Lost & Found App**. Keep the task's terminal running while using the browser. If Windows has reserved the preferred port, the app tries 8080, 5000, and 3000 automatically.

## Publish a public Render demo

The `render.yaml` blueprint creates a public Flask web service and a PostgreSQL database. To deploy after pushing this repository to GitHub:

1. Push this project to a public GitHub repository.
2. Sign in to Render and choose **New → Blueprint**.
3. Connect the GitHub repository and deploy the `render.yaml` blueprint.
4. Wait for the build and deployment to finish, then open the service URL shown in the Render dashboard. Share that URL with others.
5. Test the health page at `<your-service-url>/api/health`, then register and try the app.

This is a classroom demo configuration. Render's free web service sleeps after 15 minutes without traffic, so the first visit after idle time can take about a minute. The free PostgreSQL database expires after 30 days, and Render deletes its data after the expiration grace period. Do not use real or sensitive personal information in this public demo. See [Render's free instance limits](https://render.com/docs/free) and [Flask deployment guide](https://render.com/docs/deploy-flask).

## Testing

Run the automated tests with `python -m unittest discover -s tests -v`. The test suite covers valid registration, invalid input, duplicate accounts, login, matching, assistant responses, report persistence, and access control. After automated checks, manually verify the full browser workflow and that reports persist after restarting the server.

## Screenshots and sample outputs

Save screenshots of the dashboard, lost and found forms, search, possible match, verification, recovery, and assistant in `screenshots/`. Capture actual output from your running app; do not use sample data as proof of a completed recovery. A sample local assistant response is: “Top possible match: lost report L101 and found report F201 (keyword score 79%). Review both reports before verification.”

## Submission checklist

- [ ] Add your student ID above and in the report/presentation.
- [ ] Run the app and complete the test cases.
- [ ] Add screenshots from your own run.
- [ ] Record your own explanation video and be ready to explain the code.
- [ ] Create your individual GitHub repository and upload the reviewed source files. Never upload `.env`, passwords, or personal SQLite data.

The existing HTML/CSS dashboard was retained to match the requested design. Its server, account handling, matching helper, and data storage are Python-based. `web-version/` preserves the earlier Node implementation for reference.
