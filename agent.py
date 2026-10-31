import re, time
from pathlib import Path
from database import (get_fee_status, get_scholarship_status, create_support_request,
                      save_memory, get_memories, request_approval, add_audit, get_student)
from retrieval import retrieve_policy
import json
import llm

ALLOWED_MEMORY_KEYS = {"programme", "preferred_contact", "preferred_language", "preference"}
TEMPORARY = re.compile(r"\b(today|tomorrow|tonight|right now|currently|at the moment|this week)\b", re.I)

SYSTEM_PROMPT = """You are the Student Support Assistant of a business school, helping the signed-in student.
Rules:
1. Fee and scholarship data must come from tools. Never guess it.
2. For policy questions call retrieve_policy and answer ONLY from what it returns. If it returns nothing relevant, say you
   do not have enough information and suggest contacting the administration office or raising a support request.
3. Use save_memory only for stable facts the student states about themselves (programme, preferred contact, language,
   preferences). Never save temporary situations or any OTP, password or PIN.
4. A course change is a sensitive action: call request_course_change. It only SUBMITS a request for administrator approval;
   never say the course has changed.
5. If required information is missing, ask one short question.
6. You can only help with the signed-in student's own data. Be concise and friendly."""

TOOLS = [
    {"type": "function", "function": {"name": "get_fee_status", "description": "Get the signed-in student's fee status and outstanding amount.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_scholarship_status", "description": "Get the signed-in student's scholarship status.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "retrieve_policy", "description": "Search the student policy handbook; returns only the relevant paragraphs.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "create_support_request", "description": "Create a support ticket for the student.", "parameters": {"type": "object", "properties": {"category": {"type": "string", "enum": ["Fees", "Scholarship", "Academics", "IT", "General Support"]}, "description": {"type": "string"}}, "required": ["category", "description"]}}},
    {"type": "function", "function": {"name": "request_course_change", "description": "Request a course change. Needs administrator approval before anything changes.", "parameters": {"type": "object", "properties": {"requested_course": {"type": "string"}}, "required": ["requested_course"]}}},
    {"type": "function", "function": {"name": "save_memory", "description": "Remember a STABLE fact about the student for future sessions.", "parameters": {"type": "object", "properties": {"key": {"type": "string", "enum": sorted(ALLOWED_MEMORY_KEYS)}, "value": {"type": "string"}}, "required": ["key", "value"]}}},
    {"type": "function", "function": {"name": "get_memories", "description": "Recall the facts saved about this student in earlier sessions.", "parameters": {"type": "object", "properties": {}}}},
]

SENSITIVE_PATTERNS = [
    r"\botp\b", r"\bpassword\b", r"\bpasscode\b", r"\bpin\b",
    r"\b\d{6}\b"
]

def is_sensitive_text(text):
    low = text.lower()
    return any(re.search(p, low) for p in SENSITIVE_PATTERNS)

class StudentSupportAgent:
    """Transparent local agent loop: classify -> select context/tool -> execute -> respond -> trace."""
    def __init__(self, use_llm=None):
        # use_llm=None -> automatic: use Groq when a real key is present, otherwise the rule-based route.
        self.use_llm = llm.is_configured() if use_llm is None else (use_llm and llm.is_configured())

    @staticmethod
    def _is_cross_student(q, sid):
        low = q.lower()
        return ("another student" in low or "other student" in low or
                any(t.startswith("stu") and t.upper() != sid for t in re.findall(r"\b[A-Za-z0-9]+\b", q)))

    # ---- tools for the LLM. The student id ALWAYS comes from the signed-in session, never from the model.
    def _run_tool(self, name, args, user, tools, evidence):
        sid, actor = user["student_id"], user["username"]
        tools.append(name)
        if name == "get_fee_status":
            row = get_fee_status(sid); evidence.append(f"student_record:{sid}")
            add_audit(actor, sid, "read_fee_status", sid, "allowed", "Own fee record retrieved")
            return {"fee_status": row["fee_status"], "fee_due": row["fee_due"]} if row else {"error": "no record"}
        if name == "get_scholarship_status":
            row = get_scholarship_status(sid); evidence.append(f"student_record:{sid}")
            add_audit(actor, sid, "read_scholarship_status", sid, "allowed", "Own scholarship record retrieved")
            return {"scholarship_status": row["scholarship_status"]} if row else {"error": "no record"}
        if name == "retrieve_policy":
            policy, chunks = retrieve_policy(args.get("query", ""))
            evidence.extend(chunks or ["No sufficiently relevant policy chunk"])
            add_audit(actor, sid, "policy_question", "student_handbook", "allowed",
                      "Retrieved relevant policy" if chunks else "Insufficient evidence")
            return {"policy_text": policy} if chunks else {"policy_text": "", "note": "No relevant policy found."}
        if name == "create_support_request":
            rid = create_support_request(sid, args.get("category", "General Support"), str(args.get("description", ""))[:500])
            evidence.append(f"support_request:{rid}")
            add_audit(actor, sid, "create_support_request", f"request:{rid}", "allowed", "Created")
            return {"reference_number": rid}
        if name == "request_course_change":
            aid = request_approval(sid, "course_change", f"Requested course: {args.get('requested_course', 'Not specified')}", actor)
            evidence.append(f"approval_request:{aid}")
            add_audit(actor, sid, "course_change_requested", f"approval:{aid}", "pending", "Awaiting administrator decision")
            return {"status": "pending_approval", "request_id": aid, "note": "Course NOT changed yet; administrator must approve."}
        if name == "save_memory":
            key, value = args.get("key", ""), str(args.get("value", ""))
            if key not in ALLOWED_MEMORY_KEYS or is_sensitive_text(value) or TEMPORARY.search(value) or len(value) > 120:
                add_audit(actor, sid, "memory_write", key or "?", "blocked", "Sensitive/temporary/not allowed - not stored")
                return {"error": "not stored: only stable, non-sensitive facts can be remembered"}
            save_memory(sid, key, value); evidence.append(f"memory.{key}")
            add_audit(actor, sid, "memory_write", key, "allowed", "Saved")
            return {"saved": True}
        if name == "get_memories":
            evidence.append("memory items for authenticated student")
            add_audit(actor, sid, "memory_read", "student_memory", "allowed", "Retrieved own memory")
            return get_memories(sid) or {"note": "nothing saved yet"}
        return {"error": f"unknown tool {name}"}

    def _handle_llm(self, q, user, started):
        """Agent loop with Groq: model decides -> tool runs in our code -> model answers. Returns None on failure."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT + f"\nSigned-in student: {user['full_name']}."},
                    {"role": "user", "content": q}]
        tools, evidence, p_tok, c_tok = [], [], 0, 0
        try:
            for _ in range(5):
                msg, p, c = llm.chat(messages, TOOLS)
                p_tok += p; c_tok += c
                calls = msg.get("tool_calls") or []
                if not calls:
                    answer = (msg.get("content") or "").strip() or "Sorry, I could not complete that request."
                    break
                messages.append({"role": "assistant", "content": msg.get("content"), "tool_calls": calls})
                for call in calls:
                    try:
                        args = json.loads(call["function"].get("arguments") or "{}")
                    except ValueError:
                        args = {}
                    result = self._run_tool(call["function"]["name"], args, user, tools, evidence)
                    messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})
            else:
                answer = "Sorry, I could not complete that request. Please try again."
        except llm.LLMError as exc:
            self.last_llm_error = str(exc)
            return None  # caller falls back to the rule-based route
        route = "llm:" + (tools[0] if tools else "direct_answer")
        return {"answer": answer, "route": route, "tools": tools, "evidence": evidence,
                "latency_ms": (time.perf_counter() - started) * 1000,
                "tokens": {"input": p_tok, "output": c_tok, "model": llm.get_model()}}

    def handle(self, question, user):
        started = time.perf_counter()
        # Deterministic guards run BEFORE the model: sensitive text and cross-student requests never reach it.
        if (user.get("role") == "student" and self.use_llm and not is_sensitive_text(question)
                and not self._is_cross_student(question.strip(), user.get("student_id"))):
            out = self._handle_llm(question.strip(), user, started)
            if out:
                return out
        sid = user.get("student_id")
        role = user.get("role")
        q = question.strip()
        low = q.lower()
        tools, evidence, route = [], [], "direct_answer"
        answer = ""
        actor = user["username"]

        if role != "student":
            answer = "Administrator account: use the approval console below to review pending sensitive actions."
            route = "admin_console"
        elif is_sensitive_text(q):
            answer = ("For your safety, I will not save OTPs, passwords, PINs or similar sensitive details. "
                      "Please never share credentials in this chat.")
            route = "privacy_filter"
            add_audit(actor, sid, "sensitive_input_blocked", "chat", "blocked", "Sensitive text not stored")
        elif any(x in low for x in ["what did i tell", "what do you remember", "my earlier preference", "remembered"]):
            memories = get_memories(sid)
            tools.append("retrieve_persistent_memory")
            evidence.append("memory items for authenticated student")
            answer = ("Here is the non-sensitive information I remember: " +
                      "; ".join(memories.values())) if memories else "I do not have any saved preferences for you yet."
            route = "memory_read"
            add_audit(actor, sid, "memory_read", "student_memory", "allowed", "Retrieved own memory")
        elif any(x in low for x in ["remember", "my preference", "i prefer", "my programme"]):
            # Only allow non-sensitive preference facts explicitly requested for memory.
            value = q
            save_memory(sid, "student_preference", value)
            tools.append("save_persistent_memory")
            evidence.append("memory.student_preference")
            answer = "I have saved this non-sensitive preference for your future sessions."
            route = "memory_write"
            add_audit(actor, sid, "memory_write", "student_preference", "allowed", "Saved")
        elif ("another student" in low or "other student" in low or
              any(token.startswith("stu") and token.upper() != sid for token in re.findall(r"\b[A-Za-z0-9]+\b", q))):
            # Deny before any private-record tool can run.
            add_audit(actor, sid, "cross_student_record_access", "student_records", "denied",
                      "Student requested another student's private record")
            answer = "Access denied. You can only view your own private student record."
            route = "authorization_denied"
        elif "policy" in low or "handbook" in low or "what does the policy" in low:
            policy, chunks = retrieve_policy(q)
            tools.append("retrieve_policy")
            evidence.extend(chunks or ["No sufficiently relevant policy chunk"])
            if chunks:
                answer = policy
                route = "retrieval:student_policy"
            else:
                answer = ("I could not find enough information in the available student policy to answer confidently. "
                          "Please contact the student administration/accounts office for confirmation.")
                route = "insufficient_evidence"
            add_audit(actor, sid, "policy_question", "student_handbook", "allowed",
                      "Retrieved relevant policy" if chunks else "Insufficient evidence")
        elif "fee" in low or "payment" in low:
            row = get_fee_status(sid)
            tools.append("get_fee_status")
            evidence.append(f"student_record:{sid}")
            if row:
                answer = f"Your fee status is **{row['fee_status']}**. Outstanding amount: **₹{row['fee_due']:,.2f}**."
                if "next working day" in low or "portal failed" in low:
                    policy, chunks = retrieve_policy("payment portal failure next working day")
                    evidence.extend(chunks)
                    answer += " " + (policy if policy else "The supplied policy does not specify an exception for portal failure. Please contact the accounts office.")
            else:
                answer = "I could not find a fee record for your account."
            route = "tool:fee_status"
            add_audit(actor, sid, "read_fee_status", sid, "allowed", "Own fee record retrieved")
        elif "scholarship" in low:
            row = get_scholarship_status(sid)
            tools.append("get_scholarship_status")
            evidence.append(f"student_record:{sid}")
            answer = f"Your scholarship status is **{row['scholarship_status']}**." if row else "No scholarship record was found."
            route = "tool:scholarship_status"
            add_audit(actor, sid, "read_scholarship_status", sid, "allowed", "Own scholarship record retrieved")
        elif any(x in low for x in ["change my course", "course change", "change course"]):
            requested = q.split("to", 1)[-1].strip() if "to" in low else "Not specified"
            approval_id = request_approval(sid, "course_change", f"Requested course: {requested}", actor)
            tools.append("request_human_approval")
            evidence.append(f"approval_request:{approval_id}")
            answer = (f"Your course-change request has been submitted for administrator approval (request #{approval_id}). "
                      "Your student record has **not** been changed. It will change only if an administrator approves it.")
            route = "approval_required"
            add_audit(actor, sid, "course_change_requested", f"approval:{approval_id}", "pending",
                      "Awaiting administrator decision")
        elif any(x in low for x in ["support request", "raise a ticket", "complaint", "helpdesk"]):
            category = "General Support"
            request_id = create_support_request(sid, category, q)
            tools.append("create_support_request")
            evidence.append(f"support_request:{request_id}")
            answer = f"Your support request has been created successfully. Reference number: **{request_id}**."
            route = "tool:create_support_request"
            add_audit(actor, sid, "create_support_request", f"request:{request_id}", "allowed", "Created")
        else:
            policy, chunks = retrieve_policy(q)
            if chunks:
                answer = policy
                route = "retrieval:student_policy"
                tools.append("retrieve_policy")
                evidence.extend(chunks)
            else:
                answer = ("I could not find enough information in the available student policy to answer confidently. "
                          "Please contact the student administration/accounts office for confirmation.")
                route = "insufficient_evidence"
                evidence.append("No sufficiently relevant policy chunk")
            add_audit(actor, sid, "policy_question", "student_handbook", "allowed", "Retrieved relevant policy" if chunks else "Insufficient evidence")
        latency = (time.perf_counter() - started) * 1000
        return {"answer": answer, "route": route, "tools": tools, "evidence": evidence,
                "latency_ms": latency}
