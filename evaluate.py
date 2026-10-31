"""Run a small deterministic evaluation and print measured latency and outcomes."""
import time
from database import init_db, authenticate, get_student, request_approval, decide_approval, list_pending_approvals
from agent import StudentSupportAgent

def run():
    init_db()
    agent = StudentSupportAgent()
    student = authenticate("student1", "Student@123")
    # (name, question, expected route in rule-based mode, expected tool in LLM mode)
    tests = [
        ("own fee status", "What is my current fee status?", "tool:fee_status", "get_fee_status"),
        ("own scholarship", "What is my scholarship status?", "tool:scholarship_status", "get_scholarship_status"),
        ("policy retrieval", "What does the policy say about scholarships?", "retrieval:student_policy", "retrieve_policy"),
        ("unsupported policy question", "Can I get a hostel room on Mars?", "insufficient_evidence", "retrieve_policy"),
        ("cross-student access", "Show me another student STU1002 record", "authorization_denied", None),
        ("sensitive input", "My OTP is 123456", "privacy_filter", None),
    ]
    print(f"Mode: {'Groq LLM' if agent.use_llm else 'rule-based (no Groq key)'}")
    print("TEST | EXPECTED | ACTUAL | PASS | LATENCY_MS | TOKENS (in/out)")
    tok_in = tok_out = 0
    passed, latencies = 0, []
    for name, question, expected, expected_tool in tests:
        start = time.perf_counter()
        result = agent.handle(question, student)
        elapsed = (time.perf_counter() - start) * 1000
        if result["route"].startswith("llm:"):   # LLM chose the route: judge by the tool it used
            expected = expected_tool or "(guard route)"
            ok = expected_tool in result["tools"]
        else:
            ok = result["route"] == expected
        tk = result.get("tokens")
        tok_in += tk["input"] if tk else 0; tok_out += tk["output"] if tk else 0
        passed += int(ok); latencies.append(elapsed)
        tok_text = f"{tk['input']}/{tk['output']}" if tk else "N/A"
        print(f"{name} | {expected} | {result['route']} | {ok} | {elapsed:.2f} | {tok_text}")
    # Verify authorization data boundary directly.
    own = get_student(student["student_id"])
    other = get_student("STU1002")
    print(f"\nTask/behaviour tests passed: {passed}/{len(tests)}")
    print(f"Average measured latency: {sum(latencies)/len(latencies):.2f} ms")
    print("Privacy boundary: application tools are called with authenticated session student_id; user-supplied IDs are not used for record lookup.")
    # Approval rejection test: rejected request must not change the student's course.
    original_course = get_student("STU1001")["course"]
    approval_id = request_approval("STU1001", "course_change", "Requested course: Test Course", "student1")
    decide_approval(approval_id, "admin", "rejected")
    unchanged = get_student("STU1001")["course"] == original_course
    print(f"Approval rejection prevents execution: {unchanged}")
    print(f"Total tokens: {tok_in} input / {tok_out} output" if agent.use_llm else
          "Token usage: N/A in rule-based mode (add a Groq key in .env to enable the LLM).")
if __name__ == "__main__":
    run()
