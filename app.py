import streamlit as st
from agent import StudentSupportAgent
from database import init_db, authenticate, get_user, list_pending_approvals, decide_approval, get_audit_logs

st.set_page_config(page_title="Student Support Agent", page_icon="🎓", layout="wide")
init_db()

if "user" not in st.session_state:
    st.session_state.user = None
if "messages" not in st.session_state:
    st.session_state.messages = []

def login_screen():
    st.title("🎓 Intelligent Student Support Agent")
    st.caption("A unified agentic application with tools, policy retrieval, memory, privacy and human approval.")
    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")
    if submitted:
        user = authenticate(username.strip(), password)
        if user:
            st.session_state.user = user
            st.session_state.messages = []
            st.rerun()
        else:
            st.error("Invalid username or password.")
    with st.expander("Demo login accounts"):
        st.write("Student: `student1` / `Student@123`")
        st.write("Second student (privacy test): `student2` / `Student@123`")
        st.write("Administrator/approver: `admin` / `Admin@123`")
    st.info("Demo credentials are for local academic demonstration only. Change them before any real deployment.")

if not st.session_state.user:
    login_screen()
    st.stop()

user = st.session_state.user
agent = StudentSupportAgent()
with st.sidebar:
    st.header("Account")
    st.write(f"**{user['full_name']}**")
    st.caption(f"{user['role'].title()} · {user['student_id'] or 'Administrator'}")
    if st.button("Sign out"):
        st.session_state.user = None
        st.session_state.messages = []
        st.rerun()
    st.divider()
    st.caption("Assignment 1 + Assignment 2")
    import llm
    st.caption("Mode: Groq LLM (" + llm.get_model() + ")" if llm.is_configured() else "Mode: rule-based (no Groq key set)")
    st.write("Tools · RAG · Memory · Access control · Approval · Audit")

st.title("Student Support Chat")
st.caption("Ask about fees, scholarships, policies, support requests or your remembered preferences.")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("How can I help you today?")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Checking the request and relevant information..."):
            result = agent.handle(prompt, user)
        st.markdown(result["answer"])
        if result.get("evidence") or result.get("tools"):
            with st.expander("Retrieved evidence / execution trace"):
                st.write("**Route:**", result.get("route", ""))
                st.write("**Tools:**", ", ".join(result.get("tools", [])) or "None")
                st.write("**Evidence:**", result["evidence"])
                st.write("**Latency:**", f"{result.get('latency_ms', 0):.2f} ms")
                tk = result.get("tokens")
                if tk:
                    st.write("**Token usage:**", f"{tk['input']} input / {tk['output']} output (model: {tk['model']})")
                else:
                    st.write("**Token usage:** Not applicable in rule-based mode (no model API call).")
    st.session_state.messages.append({"role": "assistant", "content": result["answer"]})

if user["role"] == "admin":
    st.divider()
    st.subheader("Administrator approval console")
    pending = list_pending_approvals()
    if not pending:
        st.success("No pending approval requests.")
    for item in pending:
        with st.container(border=True):
            st.write(f"**Request #{item['id']}** · Student: {item['student_id']}")
            st.write(f"Action: {item['action']} · Details: {item['details']}")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Approve", key=f"approve_{item['id']}"):
                    decide_approval(item["id"], user["username"], "approved")
                    st.success("Request approved and action executed.")
                    st.rerun()
            with c2:
                if st.button("Reject", key=f"reject_{item['id']}"):
                    decide_approval(item["id"], user["username"], "rejected")
                    st.warning("Request rejected. No student record was changed.")
                    st.rerun()
    with st.expander("Recent audit records"):
        st.dataframe(get_audit_logs(50), use_container_width=True)
