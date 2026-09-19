import os
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, flash, abort, jsonify
)
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

import models

app = Flask(__name__)
app.secret_key = "change-me-to-a-long-random-string"


# ---------- Login Manager ----------
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Войдите, чтобы продолжить"
login_manager.login_message_category = "error"


class User(UserMixin):
    def __init__(self, row):
        self.id = str(row["id"])
        self.username = row["username"]
        self.email = row["email"]
        self.bio = row["bio"] if "bio" in row.keys() else ""
        self.is_admin = bool(row["is_admin"])


@login_manager.user_loader
def load_user(user_id):
    row = models.get_user_by_id(int(user_id))
    return User(row) if row else None


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return wrapper


def human_date(date_str):
    try:
        dt = datetime.strptime(date_str, "%d.%m.%Y %H:%M")
    except Exception:
        return date_str
    sec = (datetime.now() - dt).total_seconds()
    if sec < 60:
        return "только что"
    if sec < 3600:
        return f"{int(sec // 60)} мин назад"
    if sec < 86400:
        return f"{int(sec // 3600)} ч назад"
    if sec < 604800:
        return f"{int(sec // 86400)} дн назад"
    return date_str


app.jinja_env.filters["human_date"] = human_date


# ---------- Главная ----------
@app.route("/")
def index():
    return render_template("index.html")


# ---------- Игры ----------
@app.route("/games")
def games():
    return render_template("games.html")


@app.route("/games/minesweeper")
def minesweeper():
    return render_template("minesweeper.html")


@app.route("/games/2048")
def game2048():
    return render_template("game2048.html")


@app.route("/games/tic-tac-toe")
def tictactoe():
    return render_template("tictactoe.html")


# ---------- Рекорды ----------
@app.route("/api/score", methods=["POST"])
def api_score():
    """Сохраняет результат игры. Вызывается из JS."""
    if not current_user.is_authenticated:
        return jsonify({"ok": False, "error": "not_authenticated"}), 401

    data = request.get_json(silent=True) or {}
    game = data.get("game")
    score = data.get("score")

    if game not in ("minesweeper", "2048"):
        return jsonify({"ok": False, "error": "unknown_game"}), 400
    try:
        score = int(score)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "bad_score"}), 400

    models.save_score(int(current_user.id), game, score)
    best = models.get_user_best(int(current_user.id), game)
    return jsonify({"ok": True, "best": best})


@app.route("/leaderboard/<game>")
def leaderboard(game):
    if game not in ("minesweeper", "2048"):
        abort(404)
    rows = models.get_leaderboard(game, limit=20)
    return render_template("leaderboard.html", game=game, rows=rows)


# ---------- Регистрация / Вход ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        if not username or not email or not password:
            flash("Заполните все поля", "error")
        elif len(username) < 3:
            flash("Логин — минимум 3 символа", "error")
        elif len(password) < 6:
            flash("Пароль — минимум 6 символов", "error")
        elif password != password2:
            flash("Пароли не совпадают", "error")
        elif models.user_exists(username, email):
            flash("Логин или email уже заняты", "error")
        else:
            is_admin = 1 if models.count_users() == 0 else 0
            models.create_user(username, email,
                               generate_password_hash(password),
                               is_admin=is_admin)
            flash("Регистрация успешна! Теперь войдите.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        row = models.get_user_by_username(username)
        if row and check_password_hash(row["password_hash"], password):
            login_user(User(row))
            flash(f"Добро пожаловать, {row['username']}!", "success")
            return redirect(request.args.get("next") or url_for("index"))
        flash("Неверный логин или пароль", "error")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Вы вышли из аккаунта", "success")
    return redirect(url_for("index"))


# ---------- Профиль / Настройки ----------
@app.route("/profile/<username>")
def profile(username):
    row = models.get_user_by_username(username)
    if row is None:
        abort(404)
    return render_template("profile.html", user=row)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        form_type = request.form.get("form_type")
        if form_type == "profile":
            models.update_user(
                int(current_user.id),
                email=request.form.get("email", "").strip(),
                bio=request.form.get("bio", "").strip(),
            )
            flash("Профиль обновлён", "success")
        elif form_type == "password":
            old = request.form.get("old_password", "")
            new = request.form.get("new_password", "")
            new2 = request.form.get("new_password2", "")
            row = models.get_user_by_id(int(current_user.id))
            if not check_password_hash(row["password_hash"], old):
                flash("Старый пароль неверный", "error")
            elif len(new) < 6:
                flash("Новый пароль — минимум 6 символов", "error")
            elif new != new2:
                flash("Пароли не совпадают", "error")
            else:
                models.update_user(int(current_user.id),
                                   password_hash=generate_password_hash(new))
                flash("Пароль изменён", "success")
        return redirect(url_for("settings"))
    row = models.get_user_by_id(int(current_user.id))
    return render_template("settings.html", user=row)


# ---------- Контакты ----------
@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        text = request.form.get("text", "").strip()
        if not (name and email and text):
            flash("Заполните все поля", "error")
        else:
            models.create_message(name, email, text)
            flash("Спасибо! Сообщение отправлено.", "success")
            return redirect(url_for("contact"))
    return render_template("contact.html")


# ---------- Админка ----------
@app.route("/admin")
@admin_required
def admin():
    users = models.get_all_users()
    messages = models.get_all_messages()
    return render_template("admin.html", users=users, messages=messages)


@app.route("/admin/user/<int:user_id>/toggle_admin", methods=["POST"])
@admin_required
def toggle_admin(user_id):
    row = models.get_user_by_id(user_id)
    if row:
        models.update_user(user_id, is_admin=not bool(row["is_admin"]))
        flash(f"Права {row['username']} изменены", "success")
    return redirect(url_for("admin"))


@app.route("/admin/user/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    if user_id == int(current_user.id):
        flash("Нельзя удалить самого себя", "error")
    else:
        models.delete_user(user_id)
        flash("Пользователь удалён", "success")
    return redirect(url_for("admin"))


@app.route("/admin/message/<int:message_id>/delete", methods=["POST"])
@admin_required
def delete_message(message_id):
    models.delete_message(message_id)
    flash("Сообщение удалено", "success")
    return redirect(url_for("admin"))


# ---------- Ошибки ----------
@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


models.init_db()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)