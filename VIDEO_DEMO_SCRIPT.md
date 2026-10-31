# Explanatory video walkthrough (target: 7–9 minutes)

**Opening (30 sec)**  
“This is one Student Support Agent that combines Assignment 1 and Assignment 2. I will show tool use, policy retrieval, memory, privacy, approval, audit and evaluation.”

**Architecture (60 sec)**  
Show README architecture: Streamlit UI -> agent routing -> database tools / policy retrieval -> SQLite. Explain the local deterministic design and that there is no LLM API, so token usage is not applicable.

**Assignment 1 – agent capabilities (2 min)**  
Log in as student1. Ask fee status and scholarship status; expand the trace to show the selected tool and evidence. Ask a portal-failure policy question and show the retrieved policy paragraph. Create a support request and show its reference. Save a non-sensitive preference, sign out and back in, then retrieve the memory.

**Assignment 2 – privacy and safety (2 min)**  
Ask for STU1002 while signed in as student1; show denial and audit. Enter a fake OTP such as 123456; show the warning and explain that the sensitive text is not saved to memory.

**Human approval (1.5 min)**  
Request a course change as student1. Explain that the request is pending and the course has not changed. Sign in as admin, reject one request and show that it does not execute. Create a second request and approve it; explain that only the approval handler performs the update.

**Evaluation and conclusion (1 min)**  
Run `python evaluate.py`. Show measured task results, latency and token usage marked N/A because no model API is called. Explain production hardening items in README.

**Recording checklist**
- Record the actual running application, not only slides.
- Show both student accounts and admin role.
- Expand traces and show audit records.
- Do not show real student data, personal credentials or API keys.
- Upload the video to an accessible location and test the link before submission.
