import os
import secrets
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, abort
)
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import desc, or_

from models import db, User, Game, Review, Message

# ---------- Конфиг ----------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

# Папка для загрузки обложек
UPLOAD_FOLDER = os.path.join("static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB

# БД: PostgreSQL на Render, SQLite локально
database_url = os.environ.get("DATABASE_URL")
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///site.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# ---------- Flask-Login ----------
login_manager = LoginManager(app)
login_manager.login_view = "login"


class CurrentUser(UserMixin):
    def __init__(self, u):
        self.id = str(u.id)
        self.username = u.username
        self.is_admin = u.is_admin


@login_manager.user_loader
def load_user(user_id):
    u = User.query.get(int(user_id))
    return CurrentUser(u) if u else None


# ---------- Утилиты ----------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return wrapper


# ---------- Публичные страницы ----------
@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    genre = request.args.get("genre", "").strip()
    platform = request.args.get("platform", "").strip()

    query = Game.query
    if q:
        query = query.filter(Game.title.ilike(f"%{q}%"))
    if genre:
        query = query.filter(Game.genre == genre)
    if platform:
        query = query.filter(Game.platform == platform)

    games = query.order_by(desc(Game.id)).all()

    # Списки для фильтров
    all_genres = [g[0] for g in db.session.query(Game.genre).distinct().all()]
    all_platforms = [p[0] for p in db.session.query(Game.platform).distinct().all()]

    return render_template(
        "index.html",
        games=[g.to_dict() for g in games],
        genres=sorted(all_genres),
        platforms=sorted(all_platforms),
        q=q, selected_genre=genre, selected_platform=platform,
    )


@app.route("/game/<int:game_id>")
def game_detail(game_id):
    game = Game.query.get(game_id)
    if not game:
        abort(404)

    reviews = game.reviews.order_by(desc(Review.id)).all()
    is_fav = False
    if current_user.is_authenticated:
        u = User.query.get(int(current_user.id))
        is_fav = u.favorites.filter(Game.id == game.id).count() > 0

    return render_template(
        "game.html",
        game=game.to_dict(),
        reviews=[r.to_dict() for r in reviews],
        is_fav=is_fav,
    )


# ---------- Отзывы ----------
@app.route("/game/<int:game_id>/review", methods=["POST"])
@login_required
def add_review(game_id):
    game = Game.query.get(game_id)
    if not game:
        abort(404)

    try:
        rating = int(request.form.get("rating", 0))
    except ValueError:
        rating = 0

    text = request.form.get("text", "").strip()

    if rating < 1 or rating > 10:
        flash("Оценка должна быть от 1 до 10", "error")
        return redirect(url_for("game_detail", game_id=game_id))

    # Один отзыв от одного пользователя (заменим старый)
    existing = Review.query.filter_by(game_id=game_id, user_id=int(current_user.id)).first()
    if existing:
        existing.rating = rating
        existing.text = text
        flash("Отзыв обновлён", "success")
    else:
        review = Review(
            game_id=game_id,
            user_id=int(current_user.id),
            username=current_user.username,
            rating=rating,
            text=text,
        )
        db.session.add(review)
        flash("Отзыв добавлен", "success")

    db.session.commit()
    return redirect(url_for("game_detail", game_id=game_id))


# ---------- Избранное ----------
@app.route("/favorites")
@login_required
def favorites():
    u = User.query.get(int(current_user.id))
    games = u.favorites.order_by(desc(Game.id)).all()
    return render_template("favorites.html", games=[g.to_dict() for g in games])


@app.route("/game/<int:game_id>/favorite", methods=["POST"])
@login_required
def toggle_favorite(game_id):
    game = Game.query.get(game_id)
    if not game:
        abort(404)

    u = User.query.get(int(current_user.id))
    if u.favorites.filter(Game.id == game_id).count() > 0:
        u.favorites.remove(game)
        flash("Удалено из избранного", "success")
    else:
        u.favorites.append(game)
        flash("Добавлено в избранное", "success")

    db.session.commit()
    return redirect(url_for("game_detail", game_id=game_id))


# ---------- Аутентификация ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not (username and email and password):
            flash("Заполните все поля", "error")
        elif User.query.filter_by(username=username).first():
            flash("Логин уже занят", "error")
        elif User.query.filter_by(email=email).first():
            flash("Email уже занят", "error")
        elif len(password) < 6:
            flash("Пароль должен быть минимум 6 символов", "error")
        else:
            u = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                is_admin=False,
            )
            db.session.add(u)
            db.session.commit()
            flash("Регистрация успешна! Войдите.", "success")
            return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        u = User.query.filter_by(username=username).first()
        if u and check_password_hash(u.password_hash, password):
            login_user(CurrentUser(u))
            flash("Вы вошли", "success")
            return redirect(url_for("index"))

        flash("Неверный логин или пароль", "error")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Вы вышли", "success")
    return redirect(url_for("index"))


# ---------- Админка ----------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Быстрый вход в админку по паролю (создаёт/использует пользователя admin)."""
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            admin = User.query.filter_by(username="admin").first()
            if not admin:
                admin = User(
                    username="admin",
                    email="admin@site.local",
                    password_hash=generate_password_hash(secrets.token_hex(16)),
                    is_admin=True,
                )
                db.session.add(admin)
                db.session.commit()
            login_user(CurrentUser(admin))
            return redirect(url_for("admin"))
        flash("Неверный пароль", "error")

    return render_template("admin_login.html")


@app.route("/admin")
@login_required
@admin_required
def admin():
    games = Game.query.order_by(desc(Game.id)).all()
    messages = Message.query.order_by(desc(Message.id)).all()
    return render_template(
        "admin.html",
        games=[g.to_dict() for g in games],
        messages=[m.to_dict() for m in messages],
    )


@app.route("/admin/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_game():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        genre = request.form.get("genre", "").strip()
        platform = request.form.get("platform", "").strip()
        year_raw = request.form.get("year", "").strip()
        link = request.form.get("link", "").strip()

        if not (title and description and genre and platform):
            flash("Заполните обязательные поля", "error")
            return redirect(url_for("add_game"))

        year = None
        if year_raw:
            try:
                year = int(year_raw)
            except ValueError:
                pass

        # Загрузка картинки
        image_filename = None
        file = request.files.get("image")
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            import time
            filename = f"{int(time.time())}_{filename}"
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            image_filename = filename

        game = Game(
            title=title,
            description=description,
            genre=genre,
            platform=platform,
            year=year,
            link=link or None,
            image=image_filename,
        )
        db.session.add(game)
        db.session.commit()
        flash("Игра добавлена", "success")
        return redirect(url_for("admin"))

    return render_template("add_game.html")


@app.route("/admin/delete/<int:game_id>", methods=["POST"])
@login_required
@admin_required
def delete_game(game_id):
    game = Game.query.get(game_id)
    if game:
        db.session.delete(game)
        db.session.commit()
        flash("Игра удалена", "success")
    return redirect(url_for("admin"))


# ---------- Обратная связь ----------
@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        text = request.form.get("text", "").strip()

        if not (name and email and text):
            flash("Заполните все поля", "error")
        else:
            msg = Message(name=name, email=email, text=text)
            db.session.add(msg)
            db.session.commit()
            flash("Спасибо! Сообщение отправлено.", "success")
            return redirect(url_for("contact"))

    return render_template("contact.html")


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


# ---------- Инициализация БД ----------
with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=DEBUG)