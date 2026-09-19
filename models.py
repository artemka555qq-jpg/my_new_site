import os
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Связь многие-ко-многим: пользователи <-> игры (избранное)
favorites = db.Table(
    "favorites",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("game_id", db.Integer, db.ForeignKey("games.id"), primary_key=True),
)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    favorites = db.relationship(
        "Game",
        secondary=favorites,
        backref=db.backref("favorited_by", lazy="dynamic"),
        lazy="dynamic",
    )


class Game(db.Model):
    __tablename__ = "games"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    genre = db.Column(db.String(50), nullable=False)       # Экшен, RPG, Стратегия...
    platform = db.Column(db.String(50), nullable=False)    # PC, PS5, Xbox, Mobile
    year = db.Column(db.Integer, nullable=True)
    image = db.Column(db.String(255), nullable=True)       # имя файла обложки
    link = db.Column(db.String(500), nullable=True)        # Steam / YouTube / сайт
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reviews = db.relationship(
        "Review", backref="game", cascade="all, delete-orphan", lazy="dynamic"
    )

    @property
    def avg_rating(self):
        r = self.reviews.all()
        if not r:
            return None
        return round(sum(x.rating for x in r) / len(r), 1)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "genre": self.genre,
            "platform": self.platform,
            "year": self.year,
            "image": self.image,
            "link": self.link,
            "avg_rating": self.avg_rating,
            "reviews_count": self.reviews.count(),
            "created_at": self.created_at.strftime("%d.%m.%Y") if self.created_at else "",
        }


class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("games.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    username = db.Column(db.String(50), nullable=False)
    rating = db.Column(db.Integer, nullable=False)         # 1..10
    text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "rating": self.rating,
            "text": self.text,
            "created_at": self.created_at.strftime("%d.%m.%Y %H:%M") if self.created_at else "",
        }


class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "text": self.text,
            "created_at": self.created_at.strftime("%d.%m.%Y %H:%M") if self.created_at else "",
        }


def init_db(app):
    with app.app_context():
        db.create_all()