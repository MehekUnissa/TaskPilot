from werkzeug.utils import secure_filename

from flask import send_from_directory

from dotenv import load_dotenv
load_dotenv()


import tempfile

from docx import Document


from apscheduler.schedulers.background import BackgroundScheduler

import json
from pywebpush import webpush, WebPushException

import os
from datetime import date, datetime, time, timedelta
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    session,
    send_from_directory,
    Response,
    stream_with_context
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from database import (
    init_db,
    init_notification_tables,
    add_task,
    update_task,
    get_task,
    get_all_tasks,
    set_task_status,
    mark_task_complete,
    delete_task,
    register_user,
    get_user_by_username,
    get_user_by_id,
    update_user_profile,
    save_push_subscription,
    get_tasks_for_notifications,
    get_push_subscriptions,
    delete_push_subscription,
    record_sent_reminder,
    reminder_already_sent
)

from dsa.scheduler import (
    build_task_heap,
    get_next_assignment
)

from google import genai
from google.genai import types

# =========================================
# FLASK APPLICATION SETUP
# =========================================

import os

app = Flask(__name__)

@app.route("/service-worker.js")
def service_worker():
    response = send_from_directory(
        app.static_folder,
        "service-worker.js"
    )

    response.headers["Service-Worker-Allowed"] = "/"

    return response

app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

gemini_client = (
    genai.Client(api_key=GEMINI_API_KEY)
    if GEMINI_API_KEY
    else None
)
# =========================================
# ASSIGNMENT FILE UPLOAD SETTINGS
# =========================================

UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "static",
    "uploads",
    "assignments"
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx",
    "ppt", "pptx",
    "xls", "xlsx", "csv",
    "png", "jpg", "jpeg",
    "txt"
}


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )
    
app.secret_key = os.environ.get(
    "TASKPILOT_SECRET_KEY",
    "change-this-to-a-long-random-secret"
)

# Initialize the database
init_db()
init_notification_tables()
# =========================================
# AUTHENTICATION HELPER
# =========================================

def login_required(route_function):

    @wraps(route_function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))

        return route_function(*args, **kwargs)

    return wrapper

# =========================================
# PUSH NOTIFICATION ROUTES
# =========================================

VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")


@app.context_processor
def notification_settings():
    return {
        "vapid_public_key": VAPID_PUBLIC_KEY
    }



@app.route("/api/push/subscribe", methods=["POST"])
@login_required
def subscribe_to_push():
    data = request.get_json(silent=True) or {}

    endpoint = data.get("endpoint")
    keys = data.get("keys") or {}

    p256dh = keys.get("p256dh")
    auth = keys.get("auth")

    if not endpoint or not p256dh or not auth:
        return jsonify({
            "success": False,
            "message": "Invalid notification subscription."
        }), 400

    save_push_subscription(
        session["user_id"],
        endpoint,
        p256dh,
        auth
    )

    return jsonify({
        "success": True,
        "message": "Notifications enabled successfully."
    })
# =========================================
# HELPER FUNCTIONS
# =========================================

def get_task_collections():

    user_id = session["user_id"]
    all_tasks = get_all_tasks(user_id)

    today = date.today().isoformat()

    pending_tasks = [
        task for task in all_tasks
        if task["status"] != "Completed"
    ]

    completed_tasks = [
        task for task in all_tasks
        if task["status"] == "Completed"
    ]

    overdue_tasks = [
        task for task in pending_tasks
        if task["deadline"] < today
    ]

    return (
        all_tasks,
        pending_tasks,
        completed_tasks,
        overdue_tasks
    )



def get_dashboard_data():

    (
        all_tasks,
        pending_tasks,
        completed_tasks,
        overdue_tasks
    ) = get_task_collections()

    next_task = get_next_assignment(pending_tasks)

    now = datetime.now()
    today = date.today()

    today_string = today.isoformat()

    # Recent assignments
    recent_tasks = sorted(
        all_tasks,
        key=lambda task: task["created_at"] or "",
        reverse=True
    )[:5]

    # Smart deadline reminders
    upcoming_tasks = []

    for task in all_tasks:

        task_data = dict(task)

        # Ignore completed assignments
        if (
            task_data.get("status") == "Completed"
            or task_data.get("completed")
        ):
            continue

        deadline_date = date.fromisoformat(
            task_data["deadline"]
        )

        deadline_time = time.fromisoformat(
            task_data.get("deadline_time") or "23:59"
        )

        deadline_datetime = datetime.combine(
            deadline_date,
            deadline_time
        )

        remaining_time = deadline_datetime - now

        # Ignore overdue assignments
        if remaining_time <= timedelta(0):
            continue

        # Only include assignments due within 7 days
        if remaining_time > timedelta(days=7):
            continue

        days_left = (deadline_date - today).days

        task_data["days_left"] = days_left
        task_data["deadline_datetime"] = deadline_datetime

        # Determine reminder level
        if remaining_time <= timedelta(hours=1):

            task_data["alert_level"] = "1_hour"
            task_data["alert_label"] = "Due within 1 hour"
            task_data["is_within_hour"] = True

        elif remaining_time <= timedelta(days=1):

            task_data["alert_level"] = "1_day"
            task_data["alert_label"] = "Due within 1 day"
            task_data["is_within_hour"] = False

        elif remaining_time <= timedelta(days=3):

            task_data["alert_level"] = "3_days"
            task_data["alert_label"] = "Due within 3 days"
            task_data["is_within_hour"] = False

        else:

            task_data["alert_level"] = "7_days"
            task_data["alert_label"] = "Due within 7 days"
            task_data["is_within_hour"] = False

        upcoming_tasks.append(task_data)

    # Sort by exact deadline
    upcoming_tasks.sort(
        key=lambda task: task["deadline_datetime"]
    )

    # Assignments due today
    due_today_tasks = [
        task for task in upcoming_tasks
        if task["days_left"] == 0
    ]

    return {
        "tasks": all_tasks,
        "recent_tasks": recent_tasks,
        "pending_tasks": pending_tasks,
        "completed_tasks": completed_tasks,
        "overdue_tasks": overdue_tasks,

        "upcoming_tasks": upcoming_tasks,
        "due_today_tasks": due_today_tasks,

        "total_count": len(all_tasks),
        "pending_count": len(pending_tasks),
        "completed_count": len(completed_tasks),
        "overdue_count": len(overdue_tasks),

        "upcoming_count": len(upcoming_tasks),
        "due_today_count": len(due_today_tasks),

        "next_task": next_task,
        "today": today_string
    }

# =========================================
# STUDENT REGISTRATION
# =========================================



@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        full_name = request.form.get("full_name", "").strip()
        student_id = request.form.get("student_id", "").strip()
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        course = request.form.get("course", "").strip()
        year = request.form.get("year", "").strip()
        institution = request.form.get("institution", "").strip()

        # Validate required fields
        if not all([
            full_name, student_id, email, username,
            password, confirm_password, course, year, institution
        ]):
            flash("Please fill in all required fields.", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        # Password strength validation
        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return render_template("register.html")

        if not any(char.isupper() for char in password):
            flash("Password must contain at least one uppercase letter.", "error")
            return render_template("register.html")

        if not any(char.islower() for char in password):
            flash("Password must contain at least one lowercase letter.", "error")
            return render_template("register.html")

        if not any(char.isdigit() for char in password):
            flash("Password must contain at least one number.", "error")
            return render_template("register.html")

        if not any(not char.isalnum() for char in password):
            flash("Password must contain at least one special character.", "error")
            return render_template("register.html")

        if len(username) < 3:
            flash("Username must contain at least 3 characters.", "error")
            return render_template("register.html")

        password_hash = generate_password_hash(password)

        try:
            new_user_id = register_user(
                full_name,
                student_id,
                email,
                username,
                password_hash,
                course,
                year,
                institution
            )

            if not new_user_id:
                flash("Account could not be created.", "error")
                return render_template("register.html")

            flash(
                "Account created successfully! You can now log in.",
                "success"
            )

            return redirect(url_for("login"))

        except Exception as error:

            print("REGISTRATION ERROR:", repr(error))

            error_message = str(error)

            if "UNIQUE constraint failed: users.student_id" in error_message:
                flash("This Student ID is already registered.", "error")

            elif "UNIQUE constraint failed: users.email" in error_message:
                flash("This email is already registered.", "error")

            elif "UNIQUE constraint failed: users.username" in error_message:
                flash("This username is already taken.", "error")

            else:
                flash(f"Registration error: {error}", "error")
            return render_template("register.html")
        
    return render_template("register.html")
# =========================================
# STUDENT LOGIN
# =========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = get_user_by_username(username)

        if user and check_password_hash(
            user["password_hash"], password
        ):

            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]

            flash("Welcome to TaskPilot!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


# =========================================
# STUDENT LOGOUT
# =========================================

@app.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out.", "success")

    return redirect(url_for("login"))

# =========================================
# DASHBOARD
# =========================================

@app.route("/")
@login_required
def dashboard():
    dashboard_data = get_dashboard_data()

    current_user = get_user_by_id(session["user_id"])

    return render_template(
        "dashboard.html",
        **dashboard_data,
        current_user=current_user
    )


# =========================================
# MY ASSIGNMENTS
# =========================================



@app.route("/tasks")
@login_required
def tasks():

    user_id = session["user_id"]
    all_tasks = get_all_tasks(user_id)

    search_query = request.args.get("search", "").strip()
    selected_priority = request.args.get("priority", "")
    selected_status = request.args.get("status", "all")

    today = date.today().isoformat()

    filtered_tasks = all_tasks

    # Search by assignment title or subject
    if search_query:
        filtered_tasks = [
            task for task in filtered_tasks
            if search_query.lower() in task["title"].lower()
            or search_query.lower() in task["subject"].lower()
        ]

    # Filter by priority
    if selected_priority:
        filtered_tasks = [
            task for task in filtered_tasks
            if task["priority"] == selected_priority
        ]

    # Filter by status
    if selected_status == "pending":
        filtered_tasks = [
            task for task in filtered_tasks
            if task["status"] == "Pending"
            and task["deadline"] >= today
        ]

    elif selected_status == "in_progress":
        filtered_tasks = [
            task for task in filtered_tasks
            if task["status"] == "In Progress"
        ]

    elif selected_status == "completed":
        filtered_tasks = [
            task for task in filtered_tasks
            if task["status"] == "Completed"
        ]

    elif selected_status == "overdue":
        filtered_tasks = [
            task for task in filtered_tasks
            if task["status"] != "Completed"
            and task["deadline"] < today
        ]

    return render_template(
        "tasks.html",
        tasks=filtered_tasks,
        search_query=search_query,
        selected_priority=selected_priority,
        selected_status=selected_status,
        today=today
    )


# =========================================
# ADD ASSIGNMENT
# =========================================



@app.route("/tasks/add", methods=["GET", "POST"])
@login_required
def add_assignment():

    user_id = session["user_id"]

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        subject = request.form.get("subject", "").strip()
        deadline = request.form.get("deadline", "").strip()
        deadline_time = request.form.get("deadline_time", "").strip()
        notes = request.form.get("notes", "").strip()

        # Get priority selection
        priority_mode = request.form.get("priority_mode", "automatic")
        manual_priority = request.form.get("manual_priority", "")

        attachment = request.files.get("attachment")
        attachment_path = ""
        attachment_name = ""

        if not title or not subject or not deadline or not deadline_time:
            flash("Please fill in all required fields.", "error")
            return redirect(url_for("add_assignment"))

        try:
            deadline_date = date.fromisoformat(deadline)
            time.fromisoformat(deadline_time)

        except ValueError:
            flash("Please enter a valid deadline date and time.", "error")
            return redirect(url_for("add_assignment"))

        # Determine assignment priority
        if priority_mode == "manual":

            if manual_priority not in ("High", "Medium", "Low"):
                flash("Please select a valid manual priority.", "error")
                return redirect(url_for("add_assignment"))

            priority = manual_priority

        elif priority_mode == "automatic":

            days_left = (deadline_date - date.today()).days

            if days_left <= 2:
                priority = "High"
            elif days_left <= 5:
                priority = "Medium"
            else:
                priority = "Low"

        else:
            flash("Invalid priority selection.", "error")
            return redirect(url_for("add_assignment"))

        # Handle file attachment
        if attachment and attachment.filename:

            if not allowed_file(attachment.filename):
                flash("Unsupported file type.", "error")
                return redirect(url_for("add_assignment"))

            attachment_name = secure_filename(attachment.filename)

            import uuid
            unique_name = f"{uuid.uuid4().hex}_{attachment_name}"

            attachment.save(
                os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
            )

            attachment_path = f"uploads/assignments/{unique_name}"

        # Save assignment
        add_task(
            title,
            subject,
            deadline,
            deadline_time,
            priority,
            notes,
            user_id,
            attachment_path,
            attachment_name
        )

        flash(
            f"Assignment added successfully! Priority: {priority} "
            f"({priority_mode.title()})",
            "success"
        )

        return redirect(url_for("tasks"))

    return render_template("add_assignment.html")

# =========================================
# EDIT ASSIGNMENT
# =========================================




@app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_assignment(task_id):

    user_id = session["user_id"]
    task = get_task(task_id, user_id)

    if not task:
        flash("Assignment not found.", "error")
        return redirect(url_for("tasks"))

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        subject = request.form.get("subject", "").strip()
        deadline = request.form.get("deadline", "").strip()
        deadline_time = request.form.get("deadline_time", "").strip()
        notes = request.form.get("notes", "").strip()

        if not title or not subject or not deadline or not deadline_time:
            flash("Please fill in all required fields.", "error")
            return render_template("edit_assignment.html", task=task)

        try:
            deadline_date = date.fromisoformat(deadline)
            time.fromisoformat(deadline_time)
        except ValueError:
            flash("Please enter a valid deadline date and time.", "error")
            return render_template("edit_assignment.html", task=task)

        # Optional attachment
        attachment = request.files.get("attachment")
        new_attachment_path = None
        new_attachment_name = None

        if attachment and attachment.filename:

            if not allowed_file(attachment.filename):
                flash("Unsupported file type.", "error")
                return render_template("edit_assignment.html", task=task)

            import uuid

            new_attachment_name = secure_filename(attachment.filename)
            unique_name = f"{uuid.uuid4().hex}_{new_attachment_name}"

            attachment.save(
                os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
            )

            new_attachment_path = f"uploads/assignments/{unique_name}"

        days_left = (deadline_date - date.today()).days

        if days_left <= 2:
            priority = "High"
        elif days_left <= 5:
            priority = "Medium"
        else:
            priority = "Low"

        update_task(
            task_id,
            title,
            subject,
            deadline,
            deadline_time,
            priority,
            notes,
            user_id,
            new_attachment_path,
            new_attachment_name
        )

        # Remove the old file only after replacement
        if new_attachment_path and task.get("attachment_path"):
            old_file = os.path.join(
                app.config["UPLOAD_FOLDER"],
                os.path.basename(task["attachment_path"])
            )

            if os.path.isfile(old_file):
                os.remove(old_file)

        flash(
            f"Assignment updated successfully! Priority: {priority}",
            "success"
        )

        return redirect(url_for("tasks"))

    return render_template("edit_assignment.html", task=task)



# =========================================
# MARK ASSIGNMENT COMPLETE / PENDING
# =========================================

@app.route("/tasks/<int:task_id>/complete", methods=["POST"])
@login_required
def complete_assignment(task_id):

    user_id = session["user_id"]
    task = get_task(task_id, user_id)

    if not task:
        flash("Assignment not found.", "error")
        return redirect(url_for("tasks"))

    mark_task_complete(task_id, user_id)

    flash("Assignment status updated.", "success")
    return redirect(request.referrer or url_for("tasks"))


# =========================================
# UPDATE ASSIGNMENT STATUS
# =========================================

@app.route("/tasks/<int:task_id>/status", methods=["POST"])
@login_required
def update_assignment_status(task_id):

    user_id = session["user_id"]
    task = get_task(task_id, user_id)

    if not task:
        flash("Assignment not found.", "error")
        return redirect(url_for("tasks"))

    new_status = request.form.get("status", "")

    if set_task_status(task_id, new_status, user_id):
        flash("Assignment status updated successfully!", "success")
    else:
        flash("Invalid assignment status.", "error")

    return redirect(request.referrer or url_for("tasks"))


# =========================================
# DELETE ASSIGNMENT
# =========================================

@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_assignment(task_id):

    user_id = session["user_id"]
    task = get_task(task_id, user_id)

    if not task:
        flash("Assignment not found.", "error")
        return redirect(url_for("tasks"))

    delete_task(task_id, user_id)

    flash("Assignment deleted successfully.", "success")
    return redirect(url_for("tasks"))

# =========================================
# CALENDAR
# =========================================

@app.route("/calendar")
@login_required
def calendar():

    user_id = session["user_id"]
    tasks = get_all_tasks(user_id)

    return render_template(
        "calendar.html",
        tasks=tasks,
        today=date.today().isoformat()
    )

# =========================================
# ANALYTICS
# =========================================

@app.route("/analytics")
@login_required
def analytics():

    (
        all_tasks,
        pending_tasks,
        completed_tasks,
        overdue_tasks
    ) = get_task_collections()

    total_count = len(all_tasks)
    completed_count = len(completed_tasks)

    if total_count > 0:
        completion_percentage = round(
            (completed_count / total_count) * 100,
            1
        )
    else:
        completion_percentage = 0

    priority_counts = {
        "High": 0,
        "Medium": 0,
        "Low": 0
    }

    for task in all_tasks:
        priority = task["priority"]

        if priority in priority_counts:
            priority_counts[priority] += 1

    subject_counts = {}

    for task in all_tasks:
        subject = task["subject"]
        subject_counts[subject] = (
            subject_counts.get(subject, 0) + 1
        )

    return render_template(
        "analytics.html",
        tasks=all_tasks,
        pending_tasks=pending_tasks,
        completed_tasks=completed_tasks,
        overdue_tasks=overdue_tasks,
        total_count=total_count,
        pending_count=len(pending_tasks),
        completed_count=completed_count,
        overdue_count=len(overdue_tasks),
        priority_counts=priority_counts,
        subject_counts=subject_counts,
        completion_percentage=completion_percentage
    )


# =========================================
# MAX HEAP VISUALIZER
# =========================================

@app.route("/priority-engine")
@login_required
def priority_engine():

    (
        all_tasks,
        pending_tasks,
        completed_tasks,
        overdue_tasks
    ) = get_task_collections()

    task_heap = build_task_heap(pending_tasks)

    heap_items = task_heap.items
    next_task = task_heap.peek()

    return render_template(
        "priority_engine.html",
        heap_items=heap_items,
        next_task=next_task,
        pending_count=len(pending_tasks)
    )


# =========================================
# HEAP DATA API
# =========================================

@app.route("/api/heap")
@login_required
def heap_api():

    (
        all_tasks,
        pending_tasks,
        completed_tasks,
        overdue_tasks
    ) = get_task_collections()

    task_heap = build_task_heap(pending_tasks)

    return jsonify({
        "heap": task_heap.items,
        "next_task": task_heap.peek(),
        "size": task_heap.size()
    })


# =========================================
# MY DETAILS / PROFILE
# =========================================


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():

    user_id = session["user_id"]

    if request.method == "POST":

        full_name = request.form.get("full_name", "").strip()
        course = request.form.get("course", "").strip()
        year = request.form.get("year", "").strip()
        institution = request.form.get("institution", "").strip()
        email = request.form.get("email", "").strip().lower()

        if not all([
            full_name,
            course,
            year,
            institution,
            email
        ]):
            flash("Please fill in all required fields.", "error")
            return redirect(url_for("profile"))

        try:
            update_user_profile(
                user_id,
                full_name,
                course,
                year,
                institution,
                email
            )

            flash("Profile updated successfully!", "success")

        except Exception as error:
            print("PROFILE UPDATE ERROR:", repr(error))

            if "UNIQUE constraint failed" in str(error):
                flash("This email is already registered.", "error")
            else:
                flash("Unable to update profile.", "error")

        return redirect(url_for("profile"))

    current_user = get_user_by_id(user_id)

    if not current_user:
        session.clear()
        flash("Please log in again.", "error")
        return redirect(url_for("login"))

    return render_template(
        "profile.html",
        current_user=current_user
    )

@app.route("/focus")
@login_required
def focus():
    return render_template("focus.html")


# =========================================
# AI ASSIGNMENT CREATION
# =========================================

@app.route("/api/ai-create-assignment", methods=["POST"])
@login_required
def ai_create_assignment():

    if not gemini_client:
        return jsonify({"error": "Gemini API key is missing."}), 503

    data = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Describe the assignment first."}), 400

    today = date.today().isoformat()

    prompt = f"""
    You are TaskPilot's assignment creation assistant.

    Today's date is {today}.

    Extract assignment details from the student's message.

    Return ONLY valid JSON with these fields:
    {{
        "title": "assignment title",
        "subject": "subject name",
        "deadline": "YYYY-MM-DD",
        "deadline_time": "23:59",
        "notes": "additional instructions"
    }}

    Rules:
    - Convert relative dates using today's date.
    - Use 23:59 if no deadline time is mentioned.
    - Do not invent missing title, subject or deadline.
    - Use an empty string for any missing required field.
    - Return no Markdown or extra explanation.

    Student's message: {user_message}
    """

    try:
        response = gemini_client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2
            )
        )

        draft = json.loads(response.text)

        required_fields = [
            "title",
            "subject",
            "deadline"
        ]

        if not all(draft.get(field) for field in required_fields):
            return jsonify({
                "success": False,
                "message": "Please provide the assignment title, subject and deadline."
            }), 400

        try:
            date.fromisoformat(draft["deadline"])
            time.fromisoformat(
                draft.get("deadline_time") or "23:59"
            )
        except ValueError:
            return jsonify({
                "success": False,
                "message": "I couldn't understand the deadline. Please specify it clearly."
            }), 400

        return jsonify({
            "success": True,
            "draft": {
                "title": draft["title"],
                "subject": draft["subject"],
                "deadline": draft["deadline"],
                "deadline_time": draft.get("deadline_time") or "23:59",
                "notes": draft.get("notes", "")
            }
        })

    except Exception:
        app.logger.exception("AI assignment creation error")
        return jsonify({
            "error": "Unable to prepare the assignment."
        }), 500


@app.route("/api/ai-save-assignment", methods=["POST"])
@login_required
def ai_save_assignment():

    data = request.get_json(silent=True) or {}

    title = data.get("title", "").strip()
    subject = data.get("subject", "").strip()
    deadline = data.get("deadline", "").strip()
    deadline_time = data.get("deadline_time", "23:59").strip()
    notes = data.get("notes", "").strip()

    if not title or not subject or not deadline:
        return jsonify({
            "success": False,
            "message": "Assignment details are incomplete."
        }), 400

    try:
        deadline_date = date.fromisoformat(deadline)
        time.fromisoformat(deadline_time)

        if deadline_date < date.today():
            return jsonify({
                "success": False,
                "message": "The deadline cannot be in the past."
            }), 400

        days_left = (deadline_date - date.today()).days

        if days_left <= 2:
            priority = "High"
        elif days_left <= 5:
            priority = "Medium"
        else:
            priority = "Low"

        add_task(
            title,
            subject,
            deadline,
            deadline_time,
            priority,
            notes,
            session["user_id"],
            "",
            ""
        )

        return jsonify({
            "success": True,
            "message": "Assignment created successfully!",
            "priority": priority
        })

    except ValueError:
        return jsonify({
            "success": False,
            "message": "Invalid deadline details."
        }), 400

    except Exception:
        app.logger.exception("AI assignment save error")
        return jsonify({
            "success": False,
            "message": "Unable to save the assignment."
        }), 500


@app.route("/ai-assistant")
@login_required
def ai_assistant():
    return render_template("ai_assistant.html")




@app.route("/api/ai-chat", methods=["POST"])
@login_required
def ai_chat():

    if not gemini_client:
        return jsonify({
            "error": "Gemini API key is missing. Check your .env file."
        }), 503

    message = request.form.get("message", "").strip()

    if len(message) > 10000:
        return jsonify({"error": "Message is too long."}), 400

    attachment = request.files.get("attachment")

    allowed_extensions = {
        "pdf", "docx", "txt", "png", "jpg", "jpeg"
    }

    if not message and not (attachment and attachment.filename):
        return jsonify({
            "error": "Enter a question or attach a file."
        }), 400

    if attachment and attachment.filename:
        if "." not in attachment.filename:
            return jsonify({"error": "Unsupported file type."}), 400

        extension = attachment.filename.rsplit(".", 1)[-1].lower()

        if extension not in allowed_extensions:
            return jsonify({"error": "Unsupported file type."}), 400

        if request.content_length and request.content_length > 10 * 1024 * 1024:
            return jsonify({
                "error": "File must be smaller than 10 MB."
            }), 413

    if not message:
        message = (
            "Please analyze this uploaded document "
            "and explain its important points."
        )

    file_to_delete = None
    temporary_path = None

    try:
        history = json.loads(request.form.get("history", "[]"))

        if not isinstance(history, list):
            history = []

        contents = []

        for item in history[-8:]:
            if not isinstance(item, dict):
                continue

            role = item.get("role")
            content = item.get("content", "")

            if role in ("user", "model") and isinstance(content, str):
                if content.strip():
                    contents.append(
                        types.Content(
                            role=role,
                            parts=[
                                types.Part.from_text(
                                    text=content[:6000]
                                )
                            ]
                        )
                    )

        # PROCESS ATTACHMENT

        if attachment and attachment.filename:

            extension = attachment.filename.rsplit(".", 1)[-1].lower()

            if extension == "pdf":

                with tempfile.NamedTemporaryFile(
                    suffix=".pdf",
                    delete=False
                ) as temporary_file:

                    temporary_path = temporary_file.name
                    temporary_file.write(attachment.read())

                file_to_delete = gemini_client.files.upload(
                    file=temporary_path
                )

                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=message),
                            types.Part.from_uri(
                                file_uri=file_to_delete.uri,
                                mime_type=file_to_delete.mime_type
                            )
                        ]
                    )
                )

            elif extension == "docx":

                document = Document(attachment.stream)

                document_text = "\n".join(
                    paragraph.text
                    for paragraph in document.paragraphs
                )

                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(
                                text=(
                                    message
                                    + "\n\nDocument content:\n"
                                    + document_text[:40000]
                                )
                            )
                        ]
                    )
                )

            elif extension == "txt":

                document_text = attachment.read().decode(
                    "utf-8",
                    errors="replace"
                )

                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(
                                text=(
                                    message
                                    + "\n\nDocument content:\n"
                                    + document_text[:40000]
                                )
                            )
                        ]
                    )
                )

            elif extension in ("png", "jpg", "jpeg"):

                mime_type = (
                    "image/png"
                    if extension == "png"
                    else "image/jpeg"
                )

                image_part = types.Part.from_bytes(
                    data=attachment.read(),
                    mime_type=mime_type
                )

                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=message),
                            image_part
                        ]
                    )
                )

        else:

            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=message)
                    ]
                )
            )

    except Exception:
        app.logger.exception("Gemini request preparation failed")

        if file_to_delete:
            try:
                gemini_client.files.delete(name=file_to_delete.name)
            except Exception:
                pass

        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)

        return jsonify({
            "error": "Unable to prepare your message or attachment."
        }), 500

   
    # STREAM THE GEMINI RESPONSE

    def generate():

        models_to_try = [
            "gemini-3.8-flash",
            "gemini-3.7-flash"
        ]

        last_error = None

        try:

            for model_name in models_to_try:

                received_text = False

                try:
                    app.logger.info(
                        "Trying Gemini model: %s",
                        model_name
                    )

                    response_stream = gemini_client.models.generate_content_stream(
                        model=model_name,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=(
                                "You are TaskPilot AI, an academic study assistant. "
                                "Help students understand concepts, solve assignments "
                                "step by step, summarize documents, explain images "
                                "and create notes. Use uploaded documents as the "
                                "source when provided. Be accurate, clear and concise."
                            ),
                            temperature=0.5,
                            max_output_tokens=1024
                        )
                    )

                    for chunk in response_stream:

                        text_chunk = chunk.text

                        if text_chunk:
                            received_text = True

                            yield (
                                "data: "
                                + json.dumps({"text": text_chunk})
                                + "\n\n"
                            )

                    yield "data: [DONE]\n\n"
                    return

                except Exception as error:

                    last_error = error

                    error_code = getattr(error, "code", None)

                    if error_code != 503 or received_text:
                        raise

                    app.logger.warning(
                        "%s unavailable. Trying backup model.",
                        model_name
                    )

            if last_error:
                raise last_error

        except Exception:

            app.logger.exception("Gemini streaming error")

            yield (
                "data: "
                + json.dumps({
                    "error": "AI response interrupted. Please try again."
                })
                + "\n\n"
            )

        finally:

            if file_to_delete:
                try:
                    gemini_client.files.delete(
                        name=file_to_delete.name
                    )
                except Exception:
                    app.logger.warning(
                        "Could not delete temporary Gemini file."
                    )

            if temporary_path and os.path.exists(temporary_path):
                try:
                    os.remove(temporary_path)
                except OSError:
                    app.logger.warning(
                        "Could not remove temporary PDF."
                    )

    # RETURN STREAMING RESPONSE

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )
 

# =========================================
# BACKGROUND PUSH NOTIFICATIONS
# =========================================

def send_task_push_notification(user_id, task, reminder_type):

    subscriptions = get_push_subscriptions(user_id)

    if not subscriptions:
        return False

        reminder_labels = {
        "7_days": "7-day",
        "3_days": "3-day",
        "1_day": "1-day",
        "1_hour": "1-hour"
    }

    # Calculate exact remaining time
    deadline_date = date.fromisoformat(task["deadline"])

    deadline_time = time.fromisoformat(
        task["deadline_time"]
    )

    deadline_datetime = datetime.combine(
        deadline_date,
        deadline_time
    )

    remaining_seconds = max(
        0,
        int((deadline_datetime - datetime.now()).total_seconds())
    )

    remaining_hours = remaining_seconds // 3600

    remaining_minutes = (
        remaining_seconds % 3600
    ) // 60

    payload = {
        "title": "TaskPilot Deadline Reminder",

        "body": (
            f'"{task["title"]}" is due in '
            f'{remaining_hours}h {remaining_minutes}m! '
            f'({reminder_labels[reminder_type]} reminder)'
        ),

        "url": "/tasks"
    }


    private_key = os.path.join(
        app.root_path,
        os.environ.get("VAPID_PRIVATE_KEY", "private_key.pem")
    )

    vapid_claims = {
        "sub": os.environ.get(
            "VAPID_SUBJECT",
            "mailto:admin@example.com"
        )
    }

    sent_successfully = False

    for subscription in subscriptions:

        try:
            webpush(
                subscription_info={
                    "endpoint": subscription["endpoint"],
                    "keys": {
                        "p256dh": subscription["p256dh"],
                        "auth": subscription["auth"]
                    }
                },
                data=json.dumps(payload),
                vapid_private_key=private_key,
                vapid_claims=vapid_claims
            )

            sent_successfully = True

        except WebPushException as error:
            print("Push notification error:", error)

            if error.response is not None and error.response.status_code in (404, 410):
                delete_push_subscription(subscription["endpoint"])

        except Exception as error:
            print("Notification error:", error)

    return sent_successfully


# =========================================
# AUTOMATIC DEADLINE CHECKER
# =========================================

def check_deadline_notifications():

    now = datetime.now()

    reminders = {
        "7_days": timedelta(days=7),
        "3_days": timedelta(days=3),
        "1_day": timedelta(days=1),
        "1_hour": timedelta(hours=1)
    }

    tasks = get_tasks_for_notifications()

    for task in tasks:

        try:
            deadline_date = date.fromisoformat(task["deadline"])

            deadline_time = time.fromisoformat(
                task["deadline_time"]
            )

            deadline_datetime = datetime.combine(
                deadline_date,
                deadline_time
            )

            remaining = deadline_datetime - now

            # Ignore completed or already overdue tasks
            if remaining.total_seconds() <= 0:
                continue

            deadline_snapshot = deadline_datetime.isoformat()

            for reminder_type, reminder_offset in reminders.items():

                # Check whether this reminder threshold has been reached
                # Five-minute window allows for scheduler delays.
                if (
                    remaining <= reminder_offset
                    and remaining > reminder_offset - timedelta(minutes=5)
                ):

                    already_sent = reminder_already_sent(
                        task["id"],
                        reminder_type,
                        deadline_snapshot
                    )

                    if already_sent:
                        continue

                    success = send_task_push_notification(
                        task["user_id"],
                        task,
                        reminder_type
                    )

                    if success:
                        record_sent_reminder(
                            task["id"],
                            task["user_id"],
                            reminder_type,
                            deadline_snapshot
                        )

        except Exception as error:
            print(
                f"Reminder error for task {task.get('id')}:",
                error
            )

# =========================================
# RUN APPLICATION
# =========================================

if __name__ == "__main__":

    scheduler = BackgroundScheduler()

    scheduler.add_job(
        func=check_deadline_notifications,
        trigger="interval",
        minutes=1,
        id="taskpilot_deadline_checker",
        max_instances=1,
        coalesce=True
    )

    scheduler.start()

    print("TaskPilot background notifications started!")

    app.run(host="0.0.0.0", port=5000, debug=True)
