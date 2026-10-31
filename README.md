# Intelligent Student Support Agent (Assignments 1 & 2)

A single integrated Streamlit application implementing the requirements in both assignment briefs:
- Agent loop and tool selection
- Fee and scholarship lookup, support-ticket creation
- Persistent non-sensitive memory
- Student-policy retrieval (RAG-style relevant paragraph selection)
- Login identity and server-side record authorization
- Human approval for course changes
- Audit records, traces and evaluation

## 1. Architecture

`app.py` (chat UI) -> `agent.py` (classify/plan/execute/respond) -> tools in `database.py` and `retrieval.py` -> SQLite + `student_policy.txt`.

The agent has two modes:
- **Groq LLM mode (when a key is set in `.env`)** - the Groq model decides whether to answer directly or call a tool (fee, scholarship, policy retrieval, support request, course-change request, memory). Tools run in our own code, always use the signed-in student's ID, and every action is audited. Token usage is the real input/output count reported by the Groq API.
- **Rule-based mode (no key)** - the original deterministic router. It is also the automatic fallback if Groq is unreachable. Token usage is reported as **N/A**, not estimated.

Safety checks that run in code **before** the model is called: sensitive text (OTP/password/PIN) is blocked, and requests for another student's record are denied. Course changes always wait for administrator approval.

## Groq API key (one place only)

1. Open the file `.env` in this folder.
2. Replace `PASTE_YOUR_KEY_HERE` with your Groq key (starts with `gsk_`).
3. Save, then run `streamlit run app.py`. The sidebar shows **Mode: Groq LLM** when the key is detected.

`.env` is listed in `.gitignore` - **never upload it to GitHub or share it**. Use `.env.example` as the public template. If a key is ever exposed, delete it in the Groq console and create a new one.

## 2. Setup

Python 3.10+ is recommended.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The SQLite database is created automatically on first run.

## 3. Demo accounts

| Role | Username | Password | Student ID |
|---|---|---|---|
| Student | student1 | Student@123 | STU1001 |
| Student | student2 | Student@123 | STU1002 |
| Administrator | admin | Admin@123 | — |

These are synthetic demonstration accounts only. Do not deploy with demo credentials.

## 4. Demonstration scenarios

1. Sign in as `student1`; ask “What is my current fee status?”
2. Ask “What is my scholarship status?”
3. Ask “The payment portal failed. Can I pay on the next working day?” The handbook says there is no automatic extension; contact Accounts.
4. Ask “Create a support request for my portal issue.”
5. Ask “Remember that I prefer email communication.” Then sign out/in and ask “What do you remember?”
6. Ask “Show me another student STU1002 record.” Access must be denied.
7. Ask “My OTP is 123456.” It must not be stored in memory.
8. Ask “Change my course to Data Science.” A pending approval is created; no record change occurs yet.
9. Sign in as admin and reject the request. Confirm that no change occurred. Repeat and approve a new request to demonstrate the approved path.

## 5. Privacy, approval and audit controls

- The authenticated user's `student_id` comes from the login record. Student tools receive this ID; the agent does not use a student ID supplied in the chat to fetch a private record.
- Cross-student requests are denied and audited.
- Sensitive credentials are blocked from memory and the user is warned not to share them.
- Course changes create a pending approval. Only an administrator can decide. The database update occurs only after approval; rejection does not execute the change.
- Important actions create audit rows with actor, student, action, resource, decision and result.

## 6. Evaluation

Run:

```bash
python evaluate.py
```

The script reports the actual route, pass/fail and measured latency for its local test set. Token usage is N/A because there is no LLM API call. Run the script on the submission machine and paste its output into the final evaluation table/video. The supplied sample database is synthetic.

## 7. Limitations and production hardening

This is a classroom prototype, not a production student information system. Before real deployment, integrate institutional SSO, HTTPS, role/permission management, encrypted database/backups, secret management, rate limiting, CSRF/session hardening, formal approval delegation, retention policies and security testing. The local keyword retriever is intentionally simple; a production RAG pipeline could use embeddings/vector search and a vetted LLM with strict tool schemas.

## 8. Repository contents

- `app.py` — Streamlit chat UI and administrator approval console
- `agent.py` — agent loop, routing, safety checks and trace
- `database.py` — SQLite schema, demo users, tools, approvals and audit
- `retrieval.py` — relevant handbook paragraph retrieval
- `student_policy.txt` — sample student policy/handbook
- `evaluate.py` — repeatable local evaluation
- `tests/` — automated unit tests
