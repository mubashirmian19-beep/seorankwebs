from flask import Flask, render_template, request, flash, redirect, url_for, session, Response

import sqlite3
import os
import csv
import io

from datetime import datetime, timedelta
from functools import wraps

from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "seorankwebs-dev-secret"
)

DATABASE = os.path.join(app.root_path, "seorankwebs.db")

# Admin login
ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


# =========================
# DATABASE
# =========================

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            company TEXT,
            service TEXT NOT NULL,
            budget TEXT,
            timeline TEXT,
            details TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'New'
        )
    """)

    columns = conn.execute(
        "PRAGMA table_info(inquiries)"
    ).fetchall()

    column_names = [column["name"] for column in columns]

    if "status" not in column_names:
        conn.execute("""
            ALTER TABLE inquiries
            ADD COLUMN status TEXT NOT NULL DEFAULT 'New'
        """)

    conn.commit()
    conn.close()


init_db()


# =========================
# ADMIN PROTECTION
# =========================

def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):

        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))

        return view(*args, **kwargs)

    return wrapped_view


# =========================
# ADMIN LOGIN
# =========================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:

            session.clear()
            session["admin_logged_in"] = True
            session["admin_username"] = username

            return redirect(url_for("admin_dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("admin_login.html")


# =========================
# ADMIN LOGOUT
# =========================

@app.get("/admin/logout")
def admin_logout():

    session.clear()

    flash("You have been logged out.", "success")

    return redirect(url_for("admin_login"))


# =========================
# ADMIN DASHBOARD
# =========================

@app.get("/admin")
@admin_required
def admin_dashboard():

    conn = get_db_connection()

    # =========================
    # ALL INQUIRIES
    # =========================

    inquiries = conn.execute("""
        SELECT *
        FROM inquiries
        ORDER BY id DESC
    """).fetchall()

    # =========================
    # TOTAL INQUIRIES
    # =========================

    total_inquiries = conn.execute("""
        SELECT COUNT(*) AS count
        FROM inquiries
    """).fetchone()["count"]

    # =========================
    # TODAY'S INQUIRIES
    # =========================

    today = datetime.now().strftime("%Y-%m-%d")

    today_inquiries = conn.execute("""
        SELECT COUNT(*) AS count
        FROM inquiries
        WHERE created_at LIKE ?
    """, (today + "%",)).fetchone()["count"]

    # =========================
    # STATUS ANALYTICS
    # =========================

    status_rows = conn.execute("""
        SELECT status, COUNT(*) AS count
        FROM inquiries
        GROUP BY status
    """).fetchall()

    # Default values
    status_counts = {
        "New": 0,
        "Contacted": 0,
        "In Progress": 0,
        "Completed": 0
    }

    # Fill actual database values
    for row in status_rows:

        status = row["status"]

        if status in status_counts:
            status_counts[status] = row["count"]

    # =========================
    # LAST 7 DAYS ACTIVITY
    # =========================

    activity_data = []

    today_date = datetime.now().date()

    for i in range(6, -1, -1):

        activity_date = today_date - timedelta(days=i)

        date_string = activity_date.strftime("%Y-%m-%d")

        count = conn.execute("""
            SELECT COUNT(*) AS count
            FROM inquiries
            WHERE created_at LIKE ?
        """, (date_string + "%",)).fetchone()["count"]

        activity_data.append({
            "label": activity_date.strftime("%b %d"),
            "count": count
        })

    conn.close()

    # =========================
    # SEND DATA TO TEMPLATE
    # =========================

    return render_template(
        "admin_dashboard.html",
        inquiries=inquiries,
        total_inquiries=total_inquiries,
        today_inquiries=today_inquiries,
        status_counts=status_counts,
        activity_data=activity_data
    )


# =========================
# EXPORT INQUIRIES TO CSV
# =========================

@app.get("/admin/export")
@admin_required
def export_inquiries():

    conn = get_db_connection()

    inquiries = conn.execute("""
        SELECT
            id,
            name,
            email,
            phone,
            company,
            service,
            budget,
            timeline,
            details,
            status,
            created_at
        FROM inquiries
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "ID",
        "Client Name",
        "Email",
        "Phone",
        "Company",
        "Service",
        "Budget",
        "Timeline",
        "Details",
        "Status",
        "Created At"
    ])

    for inquiry in inquiries:

        writer.writerow([
            inquiry["id"],
            inquiry["name"],
            inquiry["email"],
            inquiry["phone"] or "",
            inquiry["company"] or "",
            inquiry["service"],
            inquiry["budget"] or "",
            inquiry["timeline"] or "",
            inquiry["details"],
            inquiry["status"],
            inquiry["created_at"]
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv"
    )

    response.headers["Content-Disposition"] = (
        "attachment; filename=seorankwebs_inquiries.csv"
    )

    return response


# =========================
# VIEW SINGLE INQUIRY
# =========================

@app.get("/admin/inquiry/<int:inquiry_id>")
@admin_required
def view_inquiry(inquiry_id):

    conn = get_db_connection()

    inquiry = conn.execute("""
        SELECT *
        FROM inquiries
        WHERE id = ?
    """, (inquiry_id,)).fetchone()

    conn.close()

    if inquiry is None:

        flash("Inquiry not found.", "error")

        return redirect(url_for("admin_dashboard"))

    return render_template(
        "admin_inquiry.html",
        inquiry=inquiry
    )


# =========================
# UPDATE INQUIRY STATUS
# =========================

@app.post("/admin/inquiry/<int:inquiry_id>/status")
@admin_required
def update_inquiry_status(inquiry_id):

    status = request.form.get("status", "").strip()

    allowed_statuses = [
        "New",
        "Contacted",
        "In Progress",
        "Completed"
    ]

    if status not in allowed_statuses:

        flash("Invalid inquiry status.", "error")

        return redirect(
            url_for(
                "view_inquiry",
                inquiry_id=inquiry_id
            )
        )

    conn = get_db_connection()

    inquiry = conn.execute("""
        SELECT id
        FROM inquiries
        WHERE id = ?
    """, (inquiry_id,)).fetchone()

    if inquiry is None:

        conn.close()

        flash("Inquiry not found.", "error")

        return redirect(url_for("admin_dashboard"))

    conn.execute("""
        UPDATE inquiries
        SET status = ?
        WHERE id = ?
    """, (status, inquiry_id))

    conn.commit()
    conn.close()

    flash(
        f"Inquiry status updated to {status}.",
        "success"
    )

    return redirect(
        url_for(
            "view_inquiry",
            inquiry_id=inquiry_id
        )
    )


# =========================
# DELETE INQUIRY
# =========================

@app.post("/admin/inquiry/<int:inquiry_id>/delete")
@admin_required
def delete_inquiry(inquiry_id):

    conn = get_db_connection()

    conn.execute("""
        DELETE FROM inquiries
        WHERE id = ?
    """, (inquiry_id,))

    conn.commit()
    conn.close()

    flash(
        "Inquiry deleted successfully.",
        "success"
    )

    return redirect(url_for("admin_dashboard"))


# =========================
# WEBSITE PAGES
# =========================

@app.get("/")
def home():
    return render_template("index.html")


@app.get("/services")
def services():
    return render_template("services.html")


@app.get("/portfolio")
def portfolio():
    return render_template("portfolio.html")


@app.get("/about")
def about():
    return render_template("about.html")


@app.get("/case-studies")
def case_studies():
    return render_template("case_studies.html")


@app.get("/pricing")
def pricing():
    return render_template("pricing.html")


# =========================
# CONTACT FORM
# =========================

@app.route("/contact", methods=["GET", "POST"])
def contact():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        company = request.form.get("company", "").strip()
        service = request.form.get("service", "").strip()
        budget = request.form.get("budget", "").strip()
        timeline = request.form.get("timeline", "").strip()
        details = request.form.get("details", "").strip()

        if not name or not email or not service or not details:

            flash(
                "Please fill in all required fields.",
                "error"
            )

            return redirect(url_for("contact"))

        if "@" not in email or "." not in email.split("@")[-1]:

            flash(
                "Please enter a valid email address.",
                "error"
            )

            return redirect(url_for("contact"))

        conn = get_db_connection()

        conn.execute("""
            INSERT INTO inquiries (
                name,
                email,
                phone,
                company,
                service,
                budget,
                timeline,
                details,
                created_at,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            email,
            phone,
            company,
            service,
            budget,
            timeline,
            details,
            datetime.now().isoformat(timespec="seconds"),
            "New"
        ))

        conn.commit()
        conn.close()

        flash(
            "Thank you! Your inquiry has been submitted successfully.",
            "success"
        )

        return redirect(url_for("contact"))

    return render_template("contact.html")


# =========================
# RUN APP
# =========================

if __name__ == "__main__":
    app.run(debug=True)
