
import sqlite3
from pathlib import Path
from datetime import datetime


DATABASE_PATH = Path(__file__).parent / "database" / "taskpilot.db"


def get_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection



def init_db():
    with get_connection() as connection:

        # Student accounts
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                student_id TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                course TEXT NOT NULL,
                year TEXT NOT NULL,
                institution TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Tasks table
        connection.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                subject TEXT NOT NULL,
                deadline TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'Medium',
                notes TEXT DEFAULT '',
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
        """)

        # Safely add columns used by newer TaskPilot features
        task_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(tasks)"
            ).fetchall()
        }

        if "deadline_time" not in task_columns:
            connection.execute("""
                ALTER TABLE tasks
                ADD COLUMN deadline_time TEXT NOT NULL DEFAULT '23:59'
            """)

        if "attachment_path" not in task_columns:
            connection.execute("""
                ALTER TABLE tasks
                ADD COLUMN attachment_path TEXT DEFAULT ''
            """)

        if "attachment_name" not in task_columns:
            connection.execute("""
                ALTER TABLE tasks
                ADD COLUMN attachment_name TEXT DEFAULT ''
            """)

        if "status" not in task_columns:
            connection.execute("""
        ALTER TABLE tasks
        ADD COLUMN status TEXT NOT NULL DEFAULT 'Pending'
    """)

            connection.execute("""
        UPDATE tasks
        SET status = CASE
            WHEN completed = 1 THEN 'Completed'
            ELSE 'Pending'
        END
    """)

        if "user_id" not in task_columns:
            connection.execute("""
                ALTER TABLE tasks
                ADD COLUMN user_id INTEGER REFERENCES users(id)
            """)


        # Existing profile table is retained for compatibility.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                full_name TEXT DEFAULT '',
                course TEXT DEFAULT '',
                year TEXT DEFAULT '',
                institution TEXT DEFAULT '',
                email TEXT DEFAULT ''
            )
        """)

        connection.execute("""
            INSERT OR IGNORE INTO profile (id)
            VALUES (1)
        """)

def init_notification_tables():
    with get_connection() as connection:

        # Stores browser push notification subscriptions
        connection.execute("""
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                endpoint TEXT NOT NULL UNIQUE,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE
            )
        """)

        # Prevents sending the same reminder more than once
        connection.execute("""
            CREATE TABLE IF NOT EXISTS sent_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                reminder_type TEXT NOT NULL,
                deadline_snapshot TEXT NOT NULL,
                sent_at TEXT NOT NULL,

                UNIQUE (
                    task_id,
                    reminder_type,
                    deadline_snapshot
                ),

                FOREIGN KEY (task_id) REFERENCES tasks(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE
            )
        """)

        connection.commit()

# ---------------- STUDENT REGISTRATION ----------------



def register_user(
    full_name,
    student_id,
    email,
    username,
    password_hash,
    course,
    year,
    institution
):
    with get_connection() as connection:

        cursor = connection.execute("""
            INSERT INTO users (
                full_name,
                student_id,
                email,
                username,
                password_hash,
                course,
                year,
                institution,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            full_name,
            student_id,
            email,
            username,
            password_hash,
            course,
            year,
            institution,
            datetime.now().isoformat(timespec="seconds")
        ))

        user_id = cursor.lastrowid

    return user_id



def get_user_by_username(username):
    with get_connection() as connection:
        row = connection.execute("""
            SELECT * FROM users
            WHERE username = ?
        """, (username,)).fetchone()

    return dict(row) if row else None


def get_user_by_id(user_id):
    with get_connection() as connection:
        row = connection.execute("""
            SELECT id, full_name, student_id, email,
                   username, course, year, institution, created_at
            FROM users
            WHERE id = ?
        """, (user_id,)).fetchone()

    return dict(row) if row else None


# ---------------- TASK MANAGEMENT ----------------

def add_task(
    title,
    subject,
    deadline,
    deadline_time,
    priority,
    notes,
    user_id=None,
    attachment_path="",
    attachment_name=""
):
    with get_connection() as connection:

        connection.execute("""
            INSERT INTO tasks (
                title,
                subject,
                deadline,
                deadline_time,
                priority,
                notes,
                completed,
                status,
                created_at,
                user_id,
                attachment_path,
                attachment_name
            )
            VALUES (?, ?, ?, ?, ?, ?, 0, 'Pending', ?, ?, ?, ?)
        """, (
            title,
            subject,
            deadline,
            deadline_time,
            priority,
            notes,
            datetime.now().isoformat(timespec="seconds"),
            user_id,
            attachment_path,
            attachment_name
        ))
        

def update_task(
    task_id,
    title,
    subject,
    deadline,
    deadline_time,
    priority,
    notes,
    user_id=None,
    attachment_path=None,
    attachment_name=None
):
    with get_connection() as connection:

        connection.execute("""
            UPDATE tasks
            SET title = ?,
                subject = ?,
                deadline = ?,
                deadline_time = ?,
                priority = ?,
                notes = ?,
                attachment_path = COALESCE(?, attachment_path),
                attachment_name = COALESCE(?, attachment_name)
            WHERE id = ?
            AND (? IS NULL OR user_id = ?)
        """, (
            title,
            subject,
            deadline,
            deadline_time,
            priority,
            notes,
            attachment_path,
            attachment_name,
            task_id,
            user_id,
            user_id
        ))


def get_task(task_id, user_id=None):
    with get_connection() as connection:
        row = connection.execute("""
            SELECT * FROM tasks
            WHERE id = ? AND (? IS NULL OR user_id = ?)
        """, (task_id, user_id, user_id)).fetchone()

    return dict(row) if row else None


def get_all_tasks(user_id=None):
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT * FROM tasks
            WHERE (? IS NULL OR user_id = ?)
            ORDER BY
                CASE status
                    WHEN 'Pending' THEN 1
                    WHEN 'In Progress' THEN 2
                    WHEN 'Completed' THEN 3
                    ELSE 4
                END,
                deadline ASC,
                id DESC
        """, (user_id, user_id)).fetchall()

    return [dict(row) for row in rows]


def set_task_status(task_id, status, user_id=None):
    allowed_statuses = [
        "Pending", "In Progress", "Completed"
    ]

    if status not in allowed_statuses:
        return False

    completed = 1 if status == "Completed" else 0
    completed_at = (
        datetime.now().isoformat(timespec="seconds")
        if completed else None
    )

    with get_connection() as connection:
        cursor = connection.execute("""
            UPDATE tasks
            SET status = ?,
                completed = ?,
                completed_at = ?
            WHERE id = ? AND (? IS NULL OR user_id = ?)
        """, (
            status, completed, completed_at,
            task_id, user_id, user_id
        ))

    return cursor.rowcount > 0


def mark_task_complete(task_id, user_id=None):
    task = get_task(task_id, user_id)

    if task:
        new_status = (
            "Pending"
            if task["status"] == "Completed"
            else "Completed"
        )
        set_task_status(task_id, new_status, user_id)


def delete_task(task_id, user_id=None):
    with get_connection() as connection:
        connection.execute("""
            DELETE FROM tasks
            WHERE id = ? AND (? IS NULL OR user_id = ?)
        """, (task_id, user_id, user_id))


# ---------------- OLD PROFILE SUPPORT ----------------

def get_profile():
    with get_connection() as connection:
        row = connection.execute("""
            SELECT * FROM profile WHERE id = 1
        """).fetchone()

    return dict(row) if row else {}


def save_profile(full_name, course, year, institution, email):
    with get_connection() as connection:
        connection.execute("""
            UPDATE profile
            SET full_name = ?,
                course = ?,
                year = ?,
                institution = ?,
                email = ?
            WHERE id = 1
        """, (
            full_name, course, year, institution, email
        ))
# ---------------- UPDATE STUDENT PROFILE ----------------

def update_user_profile(
    user_id,
    full_name,
    course,
    year,
    institution,
    email
):
    with get_connection() as connection:
        cursor = connection.execute("""
            UPDATE users
            SET full_name = ?,
                course = ?,
                year = ?,
                institution = ?,
                email = ?
            WHERE id = ?
        """, (
            full_name,
            course,
            year,
            institution,
            email,
            user_id
        ))

    return cursor.rowcount > 0

def repair_task_foreign_key():

    connection = get_connection()

    try:
        # Temporarily disable foreign key checking
        connection.execute("PRAGMA foreign_keys = OFF")

        connection.execute("BEGIN IMMEDIATE")

        # Create a corrected tasks table
        connection.execute("""
            CREATE TABLE tasks_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                subject TEXT NOT NULL,
                deadline TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'Medium',
                notes TEXT DEFAULT '',
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL DEFAULT 'Pending',
                user_id INTEGER REFERENCES users(id)
            )
        """)

        # Copy every existing assignment
        connection.execute("""
            INSERT INTO tasks_new (
                id, title, subject, deadline, priority,
                notes, completed, created_at, completed_at,
                status, user_id
            )
            SELECT
                id, title, subject, deadline, priority,
                notes, completed, created_at, completed_at,
                status, user_id
            FROM tasks
        """)

        # Replace the old table
        connection.execute("DROP TABLE tasks")

        connection.execute("""
            ALTER TABLE tasks_new RENAME TO tasks
        """)

        connection.commit()

        # Re-enable foreign key checking
        connection.execute("PRAGMA foreign_keys = ON")

        # Verify the corrected relationship
        foreign_keys = connection.execute(
            "PRAGMA foreign_key_list(tasks)"
        ).fetchall()

        print("DATABASE REPAIR SUCCESSFUL!")
        print("Foreign keys:", [dict(row) for row in foreign_keys])

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
# =========================================
# PUSH NOTIFICATION FUNCTIONS
# =========================================

def save_push_subscription(user_id, endpoint, p256dh, auth):
    with get_connection() as connection:
        connection.execute("""
            INSERT INTO push_subscriptions (
                user_id, endpoint, p256dh, auth, created_at
            )
            VALUES (?, ?, ?, ?, ?)

            ON CONFLICT(endpoint) DO UPDATE SET
                user_id = excluded.user_id,
                p256dh = excluded.p256dh,
                auth = excluded.auth
        """, (
            user_id,
            endpoint,
            p256dh,
            auth,
            datetime.now().isoformat()
        ))


def get_push_subscriptions(user_id):
    with get_connection() as connection:
        cursor = connection.execute("""
            SELECT id, endpoint, p256dh, auth
            FROM push_subscriptions
            WHERE user_id = ?
        """, (user_id,))

        rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "endpoint": row[1],
                "p256dh": row[2],
                "auth": row[3]
            }
            for row in rows
        ]


def delete_push_subscription(endpoint):
    with get_connection() as connection:
        connection.execute("""
            DELETE FROM push_subscriptions
            WHERE endpoint = ?
        """, (endpoint,))


def record_sent_reminder(
    task_id,
    user_id,
    reminder_type,
    deadline_snapshot
):
    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT OR IGNORE INTO sent_reminders (
                task_id,
                user_id,
                reminder_type,
                deadline_snapshot,
                sent_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            task_id,
            user_id,
            reminder_type,
            deadline_snapshot,
            datetime.now().isoformat()
        ))

        return cursor.rowcount > 0

def get_tasks_for_notifications():
    with get_connection() as connection:
        cursor = connection.execute("""
            SELECT
                id,
                title,
                deadline,
                deadline_time,
                user_id,
                status,
                completed
            FROM tasks
            WHERE status != 'Completed'
              AND completed = 0
              AND user_id IS NOT NULL
        """)

        rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "title": row[1],
                "deadline": row[2],
                "deadline_time": row[3] or "23:59",
                "user_id": row[4],
                "status": row[5],
                "completed": row[6]
            }
            for row in rows
        ]
def reminder_already_sent(task_id, reminder_type, deadline_snapshot):
    with get_connection() as connection:
        result = connection.execute("""
            SELECT id
            FROM sent_reminders
            WHERE task_id = ?
              AND reminder_type = ?
              AND deadline_snapshot = ?
        """, (
            task_id,
            reminder_type,
            deadline_snapshot
        )).fetchone()

        return result is not None