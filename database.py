import sqlite3, hashlib, os, json
from pathlib import Path

DB_PATH = Path(__file__).with_name("student_support.db")

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _hash(password, salt=None):
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 180000)
    return salt.hex() + "$" + digest.hex()

def _verify(password, stored):
    salt_hex, digest_hex = stored.split("$", 1)
    return _hash(password, bytes.fromhex(salt_hex)).split("$", 1)[1] == digest_hex

def init_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, full_name TEXT NOT NULL,
          role TEXT NOT NULL, student_id TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS students(
          student_id TEXT PRIMARY KEY, full_name TEXT, programme TEXT, fee_status TEXT,
          fee_due REAL, scholarship_status TEXT, course TEXT
        );
        CREATE TABLE IF NOT EXISTS memory(
          student_id TEXT NOT NULL, memory_key TEXT NOT NULL, memory_value TEXT NOT NULL,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(student_id,memory_key)
        );
        CREATE TABLE IF NOT EXISTS support_requests(
          id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL,
          category TEXT NOT NULL, description TEXT NOT NULL, status TEXT DEFAULT 'Open',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS approvals(
          id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL,
          action TEXT NOT NULL, details TEXT NOT NULL, status TEXT DEFAULT 'pending',
          requested_by TEXT NOT NULL, decided_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          decided_at TEXT
        );
        CREATE TABLE IF NOT EXISTS audit(
          id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL, student_id TEXT,
          action TEXT NOT NULL, resource TEXT, decision TEXT NOT NULL, result TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            c.execute("INSERT INTO students VALUES(?,?,?,?,?,?,?)",
                      ("STU1001","Aarav Shah","PGDM - Big Data Analytics","Partially Paid",25000,"Eligible - verification pending","Business Analytics"))
            c.execute("INSERT INTO students VALUES(?,?,?,?,?,?,?)",
                      ("STU1002","Diya Mehta","PGDM - Marketing","Paid",0,"Not eligible","Marketing Management"))
            c.execute("INSERT INTO users VALUES(?,?,?,?,?)",
                      ("student1",_hash("Student@123"),"Aarav Shah","student","STU1001"))
            c.execute("INSERT INTO users VALUES(?,?,?,?,?)",
                      ("student2",_hash("Student@123"),"Diya Mehta","student","STU1002"))
            c.execute("INSERT INTO users VALUES(?,?,?,?,?)",
                      ("admin",_hash("Admin@123"),"Demo Administrator","admin",None))

def authenticate(username, password):
    with connect() as c:
        row = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if row and _verify(password, row["password_hash"]):
        return dict(row)
    return None

def get_user(username):
    with connect() as c:
        row = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    return dict(row) if row else None

def get_student(student_id):
    with connect() as c:
        row = c.execute("SELECT * FROM students WHERE student_id=?", (student_id,)).fetchone()
    return dict(row) if row else None

def get_fee_status(student_id):
    return get_student(student_id)

def get_scholarship_status(student_id):
    return get_student(student_id)

def create_support_request(student_id, category, description):
    with connect() as c:
        cur = c.execute("INSERT INTO support_requests(student_id,category,description) VALUES(?,?,?)",
                        (student_id, category, description))
        return cur.lastrowid

def save_memory(student_id, key, value):
    with connect() as c:
        c.execute("""INSERT INTO memory(student_id,memory_key,memory_value) VALUES(?,?,?)
                     ON CONFLICT(student_id,memory_key) DO UPDATE SET
                     memory_value=excluded.memory_value, updated_at=CURRENT_TIMESTAMP""",
                  (student_id, key, value))

def get_memories(student_id):
    with connect() as c:
        rows = c.execute("SELECT memory_key,memory_value FROM memory WHERE student_id=?", (student_id,)).fetchall()
    return {r["memory_key"]: r["memory_value"] for r in rows}

def request_approval(student_id, action, details, requested_by):
    with connect() as c:
        cur = c.execute("INSERT INTO approvals(student_id,action,details,requested_by) VALUES(?,?,?,?)",
                        (student_id, action, details, requested_by))
        return cur.lastrowid

def list_pending_approvals():
    with connect() as c:
        rows = c.execute("SELECT * FROM approvals WHERE status='pending' ORDER BY id").fetchall()
    return [dict(r) for r in rows]

def decide_approval(approval_id, admin, decision):
    with connect() as c:
        item = c.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        if not item or item["status"] != "pending":
            return False
        c.execute("UPDATE approvals SET status=?,decided_by=?,decided_at=CURRENT_TIMESTAMP WHERE id=?",
                  (decision, admin, approval_id))
        result = "No record change: rejected"
        if decision == "approved" and item["action"] == "course_change":
            # The action executes only after an authorized administrator approval.
            c.execute("UPDATE students SET course=? WHERE student_id=?",
                      (item["details"].replace("Requested course: ", "", 1), item["student_id"]))
            result = "Course updated after approval"
        c.execute("""INSERT INTO audit(actor,student_id,action,resource,decision,result)
                     VALUES(?,?,?,?,?,?)""",
                  (admin, item["student_id"], item["action"], f"approval:{approval_id}", decision, result))
        return True

def add_audit(actor, student_id, action, resource, decision, result):
    with connect() as c:
        c.execute("""INSERT INTO audit(actor,student_id,action,resource,decision,result)
                     VALUES(?,?,?,?,?,?)""", (actor, student_id, action, resource, decision, result))

def get_audit_logs(limit=50):
    with connect() as c:
        rows = c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
