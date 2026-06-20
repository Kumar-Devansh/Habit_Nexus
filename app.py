from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session
)
import requests
import csv
from io import StringIO

from datetime import date, timedelta
from database import (
    get_db_connection,
    init_db
)
import os
from werkzeug.utils import secure_filename

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

import os

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "dev-secret"
)

UPLOAD_FOLDER = "static/uploads/profile_pictures"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(
    app.config["UPLOAD_FOLDER"],
    exist_ok=True
)

init_db()
@app.route("/")
def home():

    return render_template(
        "home.html"
    )

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    routines = conn.execute(
        """
        SELECT *
        FROM routines
        WHERE user_id=?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    total = len(routines)

    completed = sum(
        routine["completed"]
        for routine in routines
    )

    progress = 0

    if total > 0:

        progress = round(
            (completed / total) * 100
        )

    heatmap_data = conn.execute(
    """
    SELECT
        DATE(tl.log_date) as log_date,

        COUNT(*) as total,

        SUM(tl.completed) as completed

    FROM task_logs tl

    JOIN routines r
    ON tl.routine_id = r.id

    WHERE r.user_id=?

    GROUP BY tl.log_date

    ORDER BY tl.log_date
    """,
    (session["user_id"],)
).fetchall()


    conn.close()

    streak = calculate_streak(
        session["user_id"]
    )

    return render_template(
        "dashboard/dashboard.html",

        routines=routines,

        total=total,

        completed=completed,

        progress=progress,

        streak=streak,

        heatmap_data=heatmap_data
    )
@app.route(
    "/login",
    methods=["GET","POST"]
)

def login():

    if request.method=="POST":

        identifier=request.form["identifier"]

        password=request.form["password"]

        conn=get_db_connection()

        user=conn.execute(
            """
            SELECT *
            FROM users
            WHERE username=?
            OR email=?
            """,
            (
                identifier,
                identifier
            )
        ).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"]=user["id"]

            return redirect(
                "/dashboard"
            )

    return render_template(
        "auth/login.html"
    )
@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        "/login"
    )
@app.route(
    "/register",
    methods=["GET","POST"]
)

def register():

    if request.method=="POST":

        username=request.form["username"]

        email=request.form["email"]

        password=request.form["password"]

        hashed_password=generate_password_hash(
            password
        )

        conn=get_db_connection()

        existing_user=conn.execute(
            """
            SELECT *
            FROM users
            WHERE username=?
            OR email=?
            """,
            (
                username,
                email
            )
        ).fetchone()

        if existing_user:

            conn.close()

            return "User already exists"

        conn.execute(
            """
            INSERT INTO users
            (
            username,
            email,
            password
            )

            VALUES
            (?,?,?)
            """,
            (
                username,
                email,
                hashed_password
            )
        )

        conn.commit()

        conn.close()

        return redirect(
            "/login"
        )

    return render_template(
        "auth/register.html"
    )


@app.route("/analytics")
def analytics():

    if "user_id" not in session:

        return redirect("/login")

    conn = get_db_connection()

    routines = conn.execute(
        """
        SELECT *
        FROM routines
        WHERE user_id=?
        """,
        (session["user_id"],)
    ).fetchall()

    total = len(routines)

    completed = sum(
        routine["completed"]
        for routine in routines
    )

    progress = 0

    if total > 0:

        progress = round(
            (completed / total) * 100
        )

    streak = calculate_streak(
        session["user_id"]
    )

    conn.close()

    return render_template(
        "dashboard/analytics.html",

        total=total,

        completed=completed,

        progress=progress,

        streak=streak
    )




@app.route("/calendar")
def calendar():

    if "user_id" not in session:

        return redirect("/login")

    conn = get_db_connection()

    logs = conn.execute(
        """
        SELECT *

        FROM task_logs tl

        JOIN routines r
        ON tl.routine_id = r.id

        WHERE r.user_id=?

        ORDER BY log_date DESC
        """,
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template(
        "dashboard/calendar.html",
        logs=logs
    )



@app.route("/leaderboard")
def leaderboard():

    if "user_id" not in session:

        return redirect("/login")

    conn = get_db_connection()

    users = conn.execute(
        """
        SELECT *
        FROM users
        """
    ).fetchall()

    leaderboard_data = []

    for user in users:

        progress = 0

        total_tasks = conn.execute(
            """
            SELECT COUNT(*) as total
            FROM routines
            WHERE user_id=?
            """,
            (user["id"],)
        ).fetchone()["total"]

        completed_tasks = conn.execute(
            """
            SELECT COUNT(*) as completed
            FROM task_logs tl

            JOIN routines r
            ON tl.routine_id = r.id

            WHERE r.user_id=?
            AND tl.completed=1
            """,
            (user["id"],)
        ).fetchone()["completed"]

        if total_tasks > 0:

            progress = round(
                (completed_tasks / total_tasks) * 100
            )

        leaderboard_data.append({

            "username": user["username"],

            "progress": progress
        })

    conn.close()

    leaderboard_data = sorted(
        leaderboard_data,
        key=lambda x: x["progress"],
        reverse=True
    )

    return render_template(
        "friends/leaderboard.html",
        leaderboard_data=leaderboard_data
    )
@app.route("/notifications")
def notifications():

    if "user_id" not in session:

        return redirect("/login")

    conn = get_db_connection()

    notifications = conn.execute(
        """
        SELECT *
        FROM notifications
        WHERE user_id=?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template(
        "dashboard/notifications.html",
        notifications=notifications
    )
@app.route(
    "/search-users",
    methods=["GET","POST"]
)
def search_users():

    if "user_id" not in session:

        return redirect("/login")

    users = []

    if request.method == "POST":

        query = request.form["query"]

        conn = get_db_connection()

        users = conn.execute(
            """
            SELECT *
            FROM users
            WHERE username LIKE ?
            """,
            (f"%{query}%",)
        ).fetchall()

        conn.close()

    return render_template(
        "friends/search_users.html",
        users=users
    )
@app.route("/profile", methods=["GET", "POST"])
def profile():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id=?
        """,
        (session["user_id"],)
    ).fetchone()

    if request.method == "POST":

        username = request.form.get("username")
        bio = request.form.get("bio")
        college = request.form.get("college")
        branch = request.form.get("branch")
        year = request.form.get("year")
        github = request.form.get("github")
        linkedin = request.form.get("linkedin")
        leetcode = request.form.get("leetcode")

        uploaded_file = request.files.get("profile_image")
        print("FILE RECEIVED:", uploaded_file)

        image_path = user["profile_image"]

        if uploaded_file and uploaded_file.filename:

            filename = secure_filename(
                uploaded_file.filename
            )

            filepath = os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename
            )

            uploaded_file.save(filepath)

            image_path = (
                f"/static/uploads/profile_pictures/{filename}"
            )

            print("IMAGE SAVED:", image_path)

        conn.execute(
            """
            UPDATE users
            SET
                profile_image=?,
                username=?,
                bio=?,
                college=?,
                branch=?,
                year=?,
                github=?,
                linkedin=?,
                leetcode=?
            WHERE id=?
            """,
            (
                image_path,
                username,
                bio,
                college,
                branch,
                year,
                github,
                linkedin,
                leetcode,
                session["user_id"]
            )
        )

        conn.commit()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE id=?
            """,
            (session["user_id"],)
        ).fetchone()

    profile_fields = [
        user["profile_image"],
        user["bio"],
        user["college"],
        user["branch"],
        user["year"],
        user["github"],
        user["linkedin"],
        user["leetcode"]
    ]

    filled_fields = sum(
        1 for field in profile_fields
        if field
    )

    completion_percentage = int(
        (filled_fields / len(profile_fields)) * 100
    )

    conn.close()

    return render_template(
        "profile/profile.html",
        user=user,
        completion_percentage=completion_percentage
    )
@app.route(
    "/settings",
    methods=["GET","POST"]
)
def settings():

    if "user_id" not in session:

        return redirect("/login")

    conn = get_db_connection()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id=?
        """,
        (session["user_id"],)
    ).fetchone()

    if request.method == "POST":

        username = request.form["username"]

        email = request.form["email"]

        conn.execute(
            """
            UPDATE users
            SET username=?,
                email=?
            WHERE id=?
            """,
            (
                username,
                email,
                session["user_id"]
            )
        )

        password = request.form["password"]

        if password:

            hashed_password = generate_password_hash(
                password
            )

            conn.execute(
                """
                UPDATE users
                SET password=?
                WHERE id=?
                """,
                (
                    hashed_password,
                    session["user_id"]
                )
            )

        conn.commit()

        conn.close()

        return redirect("/settings")

    conn.close()

    return render_template(
        "profile/settings.html",
        user=user
    )
@app.route(
    "/add_routine",
    methods=["POST"]
)
def add_routine():

    if "user_id" not in session:
        return redirect("/login")

    task = request.form["task"]

    if task.strip():

        conn = get_db_connection()

        conn.execute(
            """
            INSERT INTO routines
            (
                user_id,
                task_name,
                completed
            )
            VALUES (?,?,0)
            """,
            (
                session["user_id"],
                task
            )
        )

        conn.commit()

        conn.close()

    return redirect("/dashboard")

@app.route("/delete/<int:id>")
def delete(id):

    if "user_id" not in session:

        return redirect("/login")

    conn = get_db_connection()

    conn.execute(
        """
        DELETE FROM routines
        WHERE id=?
        AND user_id=?
        """,
        (
            id,
            session["user_id"]
        )
    )

    conn.commit()

    conn.close()

    return redirect("/dashboard")
@app.route("/toggle/<int:id>")
def toggle(id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    routine = conn.execute(
        """
        SELECT *
        FROM routines
        WHERE id=?
        AND user_id=?
        """,
        (
            id,
            session["user_id"]
        )
    ).fetchone()

    if not routine:

        conn.close()

        return redirect("/dashboard")

    new_status = 1

    if routine["completed"] == 1:
        new_status = 0

    conn.execute(
        """
        UPDATE routines
        SET completed=?
        WHERE id=?
        """,
        (
            new_status,
            id
        )
    )

    today = date.today().isoformat()

    existing_log = conn.execute(
        """
        SELECT *
        FROM task_logs
        WHERE routine_id=?
        AND log_date=?
        """,
        (
            id,
            today
        )
    ).fetchone()

    if existing_log:

        conn.execute(
            """
            UPDATE task_logs
            SET completed=?
            WHERE id=?
            """,
            (
                new_status,
                existing_log["id"]
            )
        )

    else:

        conn.execute(
            """
            INSERT INTO task_logs
            (
                routine_id,
                log_date,
                completed
            )
            VALUES (?,?,?)
            """,
            (
                id,
                today,
                new_status
            )
        )

    conn.commit()

    conn.close()

    return redirect("/dashboard")

@app.route("/send-request/<int:user_id>")
def send_request(user_id):

    if "user_id" not in session:
        return redirect("/login")

    if user_id == session["user_id"]:
        return redirect("/friends-hub")

    conn = get_db_connection()

    existing_request = conn.execute(
        """
        SELECT *
        FROM friend_requests
        WHERE
        (sender_id=? AND receiver_id=?)
        OR
        (sender_id=? AND receiver_id=?)
        """,
        (
            session["user_id"],
            user_id,
            user_id,
            session["user_id"]
        )
    ).fetchone()

    existing_friend = conn.execute(
        """
        SELECT *
        FROM friends
        WHERE
        (user1_id=? AND user2_id=?)
        OR
        (user1_id=? AND user2_id=?)
        """,
        (
            session["user_id"],
            user_id,
            user_id,
            session["user_id"]
        )
    ).fetchone()

    if not existing_request and not existing_friend:

        conn.execute(
            """
            INSERT INTO friend_requests
            (
                sender_id,
                receiver_id,
                status
            )
            VALUES (?,?,?)
            """,
            (
                session["user_id"],
                user_id,
                "pending"
            )
        )

        conn.commit()

    conn.close()

    return redirect("/friends-hub")

@app.route("/accept-request/<int:request_id>")
def accept_request(request_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    request_data = conn.execute(
        """
        SELECT *
        FROM friend_requests
        WHERE id=?
        """,
        (request_id,)
    ).fetchone()

    if request_data:

        conn.execute(
            """
            INSERT INTO friends
            (
                user1_id,
                user2_id
            )
            VALUES (?,?)
            """,
            (
                request_data["sender_id"],
                request_data["receiver_id"]
            )
        )

        conn.execute(
            """
            DELETE FROM friend_requests
            WHERE id=?
            """,
            (request_id,)
        )

        conn.commit()

    conn.close()

    return redirect("/friends-hub")

@app.route("/remove-friend/<int:friend_id>")
def remove_friend(friend_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    conn.execute(
        """
        DELETE FROM friends
        WHERE
        (user1_id=? AND user2_id=?)
        OR
        (user1_id=? AND user2_id=?)
        """,
        (
            session["user_id"],
            friend_id,
            friend_id,
            session["user_id"]
        )
    )

    conn.commit()
    conn.close()

    return redirect("/friends-hub")

@app.route("/requests")
def requests_page():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    requests = conn.execute(
        """
        SELECT
            friend_requests.id,
            users.username,
            users.profile_image

        FROM friend_requests

        JOIN users
        ON friend_requests.sender_id = users.id

        WHERE friend_requests.receiver_id=?
        AND friend_requests.status='pending'
        """,
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template(
        "friends/requests.html",
        requests=requests
    )

def calculate_streak(user_id):

    conn = get_db_connection()

    streak = 0

    current_day = date.today()

    while True:

        day_str = current_day.isoformat()

        logs = conn.execute(
            """
            SELECT *
            FROM task_logs tl

            JOIN routines r
            ON tl.routine_id = r.id

            WHERE r.user_id=?
            AND tl.log_date=?
            """,
            (
                user_id,
                day_str
            )
        ).fetchall()

        if not logs:
            break

        total = len(logs)

        completed = sum(
            log["completed"]
            for log in logs
        )

        if completed < total:
            break

        streak += 1

        current_day -= timedelta(days=1)

    conn.close()

    return streak

@app.route("/friends-hub")
def friends():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    users = conn.execute(
    """
    SELECT *
    FROM users
    WHERE id != ?
    AND id NOT IN (
        SELECT receiver_id
        FROM friend_requests
        WHERE sender_id = ?

        UNION

        SELECT sender_id
        FROM friend_requests
        WHERE receiver_id = ?

        UNION

        SELECT user1_id
        FROM friends

        UNION

        SELECT user2_id
        FROM friends
    )
    """,
    (
        session["user_id"],
        session["user_id"],
        session["user_id"]
    )
).fetchall()

    requests = conn.execute(
        """
        SELECT
            friend_requests.id,
            users.username,
            users.profile_image
        FROM friend_requests
        JOIN users
        ON friend_requests.sender_id = users.id
        WHERE friend_requests.receiver_id=?
        AND friend_requests.status='pending'
        """,
        (session["user_id"],)
    ).fetchall()

    friends = conn.execute(
        """
        SELECT users.*
        FROM friends
        JOIN users
        ON users.id =
        CASE
            WHEN friends.user1_id = ?
            THEN friends.user2_id
            ELSE friends.user1_id
        END
        WHERE friends.user1_id = ?
        OR friends.user2_id = ?
        """,
        (
            session["user_id"],
            session["user_id"],
            session["user_id"]
        )
    ).fetchall()

    conn.close()

    return render_template(
        "friends/friends_hub.html",
        users=users,
        requests=requests,
        friends=friends
    )

@app.route("/friend-profile/<int:user_id>")
def friend_profile(user_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    friend = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id=?
        """,
        (user_id,)
    ).fetchone()

    total_tasks = conn.execute(
        """
        SELECT COUNT(*)
        FROM routines
        WHERE user_id=?
        """,
        (user_id,)
    ).fetchone()[0]

    completed_tasks = conn.execute(
        """
        SELECT COUNT(*)
        FROM routines
        WHERE user_id=?
        AND completed=1
        """,
        (user_id,)
    ).fetchone()[0]
    conn.close()

    if not friend:
        return "User not found"

    return render_template(
        "friends/friend_profile.html",
        friend=friend,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks
    )

def fetch_leetcode_data(username):

    url = "https://leetcode.com/graphql"

    query = """
    query userProfile($username: String!) {

      matchedUser(username: $username) {

        submitStats {
          acSubmissionNum {
            difficulty
            count
          }
        }

        tagProblemCounts {
          advanced {
            tagName
            problemsSolved
          }

          intermediate {
            tagName
            problemsSolved
          }

          fundamental {
            tagName
            problemsSolved
          }
        }

        profile {
          ranking
          reputation
        }
      }
    }
    """

    variables = {
        "username": username
    }

    response = requests.post(

        url,

        json={
            "query": query,
            "variables": variables
        }
    )

    return response.json()

@app.route("/dsa_tracker")
def dsa_tracker():
        # =========================
    # DEFAULT SAFE VALUES
    # =========================

    topic_analytics = []

    weak_topics = []

    readiness_score = 0

    easy_count = 0

    medium_count = 0

    hard_count = 0

    total_solved = 0

    streak = 0

    weekly_counts = [0, 0, 0, 0, 0, 0, 0]

    weekly_labels = [
        "Mon",
        "Tue",
        "Wed",
        "Thu",
        "Fri",
        "Sat",
        "Sun"
    ]


    if "user_id" not in session:

        return redirect("/login")

    user_id = session["user_id"]

    conn = get_db_connection()

    # LEETCODE USERNAME

    profile = conn.execute(
        """
        SELECT *
        FROM dsa_profiles
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()


    if profile:

        username = profile["leetcode_username"]

        query = """
        query userPublicProfile($username: String!) {

            matchedUser(username: $username) {

                username

                profile {
                    ranking
                    reputation
                }

                submitStats {
                    acSubmissionNum {
                        difficulty
                        count
                    }
                }

                tagProblemCounts {

                    advanced {
                        tagName
                        problemsSolved
                    }

                    intermediate {
                        tagName
                        problemsSolved
                    }

                    fundamental {
                        tagName
                        problemsSolved
                    }
                }

                badges {
                    name
                }
            }
        }
        """


        variables = {
            "username": username
        }

        try:
            response = requests.post(
                "https://leetcode.com/graphql",
                json={
                    "query": query,
                    "variables": variables
                },
                timeout=10
            )

            if response.status_code == 200:
                leetcode_data = response.json()
            else:
                leetcode_data = None

        except requests.RequestException:
            leetcode_data = None

        
            if (
                leetcode_data.get("data")
                and leetcode_data["data"].get("matchedUser")
            ):

                user_data = leetcode_data["data"]["matchedUser"]

                stats = user_data["submitStats"]["acSubmissionNum"]

                total_solved = stats[0]["count"]

                today = date.today().isoformat()

                existing = conn.execute(
                    """
                    SELECT id
                    FROM dsa_history
                    WHERE user_id = ?
                    AND log_date = ?
                    """,
                    (
                        user_id,
                        today
                    )
                ).fetchone()

                if existing:

                    conn.execute(
                        """
                        UPDATE dsa_history
                        SET solved_count = ?
                        WHERE id = ?
                        """,
                        (
                            total_solved,
                            existing["id"]
                        )
                    )

                else:

                    conn.execute(
                        """
                        INSERT INTO dsa_history(
                            user_id,
                            solved_count,
                            log_date
                        )
                        VALUES(?,?,?)
                        """,
                        (
                            user_id,
                            total_solved,
                            today
                        )
                    )
                
                topic_analytics = []

                weak_topics = []

                readiness_score = 0

                if leetcode_data \
                and leetcode_data.get("data") \
                and leetcode_data["data"].get("matchedUser"):

                    tag_data = (
                        leetcode_data["data"]
                        ["matchedUser"]
                        .get("tagProblemCounts")
                    )

                    if not tag_data:
                        tag_data = {
                            "advanced": [],
                            "intermediate": [],
                            "fundamental": []
                        }

                    all_topics = (
                        tag_data["advanced"] +
                        tag_data["intermediate"] +
                        tag_data["fundamental"]
                    )

                    # SORT TOPICS

                    all_topics = sorted(

                        all_topics,

                        key=lambda x: x["problemsSolved"],

                        reverse=True
                    )

                    topic_analytics = all_topics[:8]

                    # WEAK TOPICS

                    weak_topics = [

                        topic for topic in all_topics

                        if topic["problemsSolved"] < 5
                    ][:5]

                    # READINESS SCORE

                    total = sum([
                        x["problemsSolved"]
                        for x in all_topics
                    ])

                    readiness_score = min(

                        int(total / 4),

                        100
                    )


                

                conn.commit()

            

    # TOPICS

    topics = conn.execute(
        """
        SELECT *
        FROM dsa_topics
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchall()

    # PENDING

    pending_topics = conn.execute(
        """
        SELECT *
        FROM pending_topics
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchall()

    history = conn.execute(
        """
        SELECT *
        FROM dsa_history
        WHERE user_id = ?
        ORDER BY log_date
        """,
        (user_id,)
    ).fetchall()

    

    # =========================
    # WEEKLY ANALYTICS
    # =========================

    weekly_data = conn.execute("""

    SELECT
        solved_count,
        log_date
    FROM dsa_history
    WHERE user_id=?
    ORDER BY log_date DESC
    LIMIT 7

    """,(session["user_id"],)).fetchall()

    weekly_data = weekly_data[::-1]

    weekly_labels = [
        row["log_date"]
        for row in weekly_data
    ]

    weekly_counts = [
        row["solved_count"]
        for row in weekly_data
    ]

    # =========================
    # TOTAL PROBLEMS
    # =========================

    easy_count = 0
    medium_count = 0
    hard_count = 0

    if leetcode_data \
    and leetcode_data.get("data") \
    and leetcode_data["data"].get("matchedUser"):

        stats = (
            leetcode_data["data"]
            ["matchedUser"]
            ["submitStats"]
            ["acSubmissionNum"]
        )

        difficulty_map = {
            item["difficulty"]: item["count"]
            for item in stats
        }

        easy_count = difficulty_map.get("Easy", 0)
        medium_count = difficulty_map.get("Medium", 0)
        hard_count = difficulty_map.get("Hard", 0)
    total_solved = (
        easy_count +
        medium_count +
        hard_count
    )

    # =========================
    # STREAK CALCULATION
    # =========================

    streak = len([
        x for x in weekly_counts
        if x > 0
    ])

    

    conn.close()

    return render_template(
        "dashboard/dsa_tracker.html",
        profile=profile,
        leetcode_data=leetcode_data,
        topics=topics,
        pending_topics=pending_topics,
        history=history,
        weekly_labels=weekly_labels,
        weekly_counts=weekly_counts,
        easy_count=easy_count,
        medium_count=medium_count,
        hard_count=hard_count,
        total_solved=total_solved,
        streak=streak,
        topic_analytics=topic_analytics,

        weak_topics=weak_topics,

        readiness_score=readiness_score,

    )

@app.route(
    "/add_dsa_topic",
    methods=["POST"]
)
def add_dsa_topic():

    if "user_id" not in session:

        return redirect("/login")

    user_id = session["user_id"]

    topic_name = request.form["topic_name"]

    completed = request.form["completed"]

    target = request.form["target"]

    conn = get_db_connection()

    conn.execute(
        """
        INSERT INTO dsa_topics(
            user_id,
            topic_name,
            completed,
            target
        )
        VALUES(?,?,?,?)
        """,
        (
            user_id,
            topic_name,
            completed,
            target
        )
    )

    conn.commit()

    conn.close()

    return redirect("/dsa_tracker")

@app.route(
    "/add_pending_topic",
    methods=["POST"]
)
def add_pending_topic():

    if "user_id" not in session:

        return redirect("/login")

    user_id = session["user_id"]

    topic_name = request.form["topic_name"]

    conn = get_db_connection()

    conn.execute(
        """
        INSERT INTO pending_topics(
            user_id,
            topic_name
        )
        VALUES(?,?)
        """,
        (
            user_id,
            topic_name
        )
    )

    conn.commit()

    conn.close()

    return redirect("/dsa_tracker")

@app.route(
    "/save_leetcode",
    methods=["POST"]
)
def save_leetcode():

    if "user_id" not in session:

        return redirect("/login")

    user_id = session["user_id"]

    username = request.form["leetcode_username"]


    conn = get_db_connection()

    existing = conn.execute(
        """
        SELECT *
        FROM dsa_profiles
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()

    if existing:

        conn.execute(
            """
            UPDATE dsa_profiles
            SET leetcode_username = ?
            WHERE user_id = ?
            """,
            (
                username,
                user_id
            )
        )

    else:

        conn.execute(
            """
            INSERT INTO dsa_profiles(
                user_id,
                leetcode_username
            )
            VALUES(?,?)
            """,
            (
                user_id,
                username
            )
        )

    conn.commit()

    conn.close()

    return redirect("/dsa_tracker")

@app.route("/export_dsa_csv")
def export_dsa_csv():

    if "user_id" not in session:

        return redirect("/login")

    user_id = session["user_id"]

    conn = get_db_connection()

    topics = conn.execute(
        """
        SELECT *
        FROM dsa_topics
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchall()

    conn.close()

    output = StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "Topic",
        "Completed",
        "Target"
    ])

    for topic in topics:

        writer.writerow([
            topic["topic_name"],
            topic["completed"],
            topic["target"]
        ])

    output.seek(0)

    return Response(
        output,
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment;filename=dsa_progress.csv"
        }
    )

@app.route("/delete_dsa_topic/<int:id>")
def delete_dsa_topic(id):

    conn = get_db_connection()

    conn.execute(
        """
        DELETE FROM dsa_topics
        WHERE id = ?
        """,
        (id,)
    )

    conn.commit()

    conn.close()

    return redirect("/dsa_tracker")

@app.route(
    "/update_dsa_topic/<int:id>",
    methods=["POST"]
)
def update_dsa_topic(id):

    completed = request.form["completed"]

    target = request.form["target"]

    conn = get_db_connection()

    conn.execute(
        """
        UPDATE dsa_topics
        SET completed = ?,
            target = ?
        WHERE id = ?
        """,
        (
            completed,
            target,
            id
        )
    )

    conn.commit()

    conn.close()

    return redirect("/dsa_tracker")

@app.route("/delete_pending_topic/<int:id>")
def delete_pending_topic(id):

    conn = get_db_connection()

    conn.execute(
        "DELETE FROM pending_topics WHERE id=?",
        (id,)
    )

    conn.commit()

    conn.close()

    return redirect("/dsa_tracker")


if __name__ == "__main__":

    app.run(
        debug=True
    )