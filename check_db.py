import sqlite3

DB_PATH = "site.db"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

print("=" * 50)
print(f"📁 Файл БД: {DB_PATH}")
print("=" * 50)

# 1. Список таблиц
tables = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()

print("\n📋 Таблицы в БД:")
for t in tables:
    print(f"  • {t['name']}")

# 2. Структура каждой таблицы
for t in tables:
    name = t["name"]
    if name.startswith("sqlite_"):
        continue

    print(f"\n📊 Таблица '{name}':")
    columns = conn.execute(f"PRAGMA table_info({name})").fetchall()
    for col in columns:
        pk = " [PRIMARY KEY]" if col["pk"] else ""
        notnull = " NOT NULL" if col["notnull"] else ""
        print(f"    - {col['name']} ({col['type']}){pk}{notnull}")

    # Количество строк
    count = conn.execute(f"SELECT COUNT(*) as c FROM {name}").fetchone()["c"]
    print(f"    Всего записей: {count}")

# 3. Последние данные из users
print("\n" + "=" * 50)
print("👤 Пользователи (последние 5):")
print("=" * 50)
rows = conn.execute(
    "SELECT id, username, email, created_at FROM users ORDER BY id DESC LIMIT 5"
).fetchall()
if rows:
    for r in rows:
        print(f"  ID {r['id']}: {r['username']} <{r['email']}> — {r['created_at']}")
else:
    print("  (нет пользователей)")

# 4. Последние данные из posts
print("\n📝 Статьи (последние 5):")
rows = conn.execute(
    "SELECT id, title, created_at FROM posts ORDER BY id DESC LIMIT 5"
).fetchall()
if rows:
    for r in rows:
        print(f"  ID {r['id']}: {r['title']} — {r['created_at']}")
else:
    print("  (нет статей)")

# 5. Последние данные из messages
print("\n✉ Сообщения (последние 5):")
rows = conn.execute(
    "SELECT id, name, email, created_at FROM messages ORDER BY id DESC LIMIT 5"
).fetchall()
if rows:
    for r in rows:
        print(f"  ID {r['id']}: {r['name']} <{r['email']}> — {r['created_at']}")
else:
    print("  (нет сообщений)")

conn.close()
print("\n" + "=" * 50)
print("✅ Проверка завершена")
print("=" * 50)