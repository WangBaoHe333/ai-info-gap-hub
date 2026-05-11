from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.getenv("APP_DB_PATH", DATA_DIR / "ai_info_gap.db"))

POST_STATUSES = {"draft", "published", "archived"}
POST_CATEGORIES = [
    "科学上网",
    "海外 AI 账号",
    "海外 AI 工具使用",
    "支付订阅",
    "AI 创作工作流",
    "案例玩法",
    "风险避坑",
]
CATEGORY_ALIASES = {
    "国外 AI 账号": "海外 AI 账号",
    "国外 AI 工具使用": "海外 AI 工具使用",
    "资源合集": "海外 AI 工具使用",
}
QUESTION_STALE_SECONDS = int(os.getenv("QUESTION_STALE_SECONDS", str(7 * 24 * 60 * 60)))
QUESTION_SIMILARITY_THRESHOLD = float(os.getenv("QUESTION_SIMILARITY_THRESHOLD", "0.72"))
_QUESTION_CONSOLIDATION_LOCK = threading.Lock()


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", lowered).strip("-")
    return slug or f"post-{int(datetime.now(UTC).timestamp())}"


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _create_posts_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            summary TEXT NOT NULL,
            category TEXT NOT NULL,
            tags TEXT NOT NULL DEFAULT '[]',
            audience TEXT NOT NULL,
            prerequisites TEXT NOT NULL DEFAULT '[]',
            steps TEXT NOT NULL DEFAULT '[]',
            faq TEXT NOT NULL DEFAULT '[]',
            risk_notice TEXT NOT NULL,
            body_markdown TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('draft', 'published', 'archived')),
            published_at TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )


def _create_sources_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS post_sources (
            id TEXT PRIMARY KEY,
            post_id TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            site_name TEXT NOT NULL DEFAULT '',
            author TEXT NOT NULL DEFAULT '',
            used_for TEXT NOT NULL DEFAULT '',
            license_note TEXT NOT NULL DEFAULT '',
            excerpt TEXT NOT NULL DEFAULT '',
            position INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE
        )
        """
    )


def _create_indexes_and_fts(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_published_at ON posts(published_at)")
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
            post_id UNINDEXED,
            title,
            summary,
            category,
            tags,
            audience,
            body,
            steps,
            faq,
            sources
        )
        """
    )


def _create_ai_questions_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL UNIQUE,
            answer TEXT NOT NULL,
            topic_keyword TEXT DEFAULT '',
            ask_count INTEGER DEFAULT 1,
            is_promoted INTEGER DEFAULT 0,
            promoted_post_id TEXT,
            answer_updated_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    columns = _table_columns(conn, "ai_questions")
    if "answer_updated_at" not in columns:
        conn.execute("ALTER TABLE ai_questions ADD COLUMN answer_updated_at TEXT")
        conn.execute("UPDATE ai_questions SET answer_updated_at = updated_at WHERE answer_updated_at IS NULL OR answer_updated_at = ''")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_questions_ask_count ON ai_questions(ask_count)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_questions_promoted ON ai_questions(is_promoted)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_questions_updated ON ai_questions(answer_updated_at)")
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS ai_questions_fts USING fts5(
            question_id UNINDEXED,
            question,
            topic_keyword
        )
        """
    )


def _migrate_scope_schema_if_needed(conn: sqlite3.Connection) -> None:
    columns = _table_columns(conn, "posts")
    if not columns or "scope" not in columns:
        return

    sources = [dict(row) for row in conn.execute("SELECT * FROM post_sources").fetchall()] if _table_columns(conn, "post_sources") else []
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DROP TABLE IF EXISTS posts_fts")
    conn.execute("ALTER TABLE posts RENAME TO posts_with_scope")
    conn.execute("DROP TABLE IF EXISTS post_sources")
    _create_posts_table(conn)
    _create_sources_table(conn)
    conn.execute(
        """
        INSERT INTO posts (
            id, title, slug, summary, category, tags, audience, prerequisites,
            steps, faq, risk_notice, body_markdown, status, published_at, updated_at
        )
        SELECT
            id, title, slug, summary,
            CASE
                WHEN category = '国外 AI 账号' THEN '海外 AI 账号'
                WHEN category = '国外 AI 工具使用' THEN '海外 AI 工具使用'
                WHEN category = '资源合集' THEN '海外 AI 工具使用'
                ELSE category
            END,
            tags, audience, prerequisites, steps, faq, risk_notice,
            body_markdown, status, published_at, updated_at
        FROM posts_with_scope
        """
    )
    for source in sources:
        conn.execute(
            """
            INSERT INTO post_sources (
                id, post_id, title, url, site_name, author, used_for,
                license_note, excerpt, position
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source["id"],
                source["post_id"],
                source["title"],
                source["url"],
                source.get("site_name", ""),
                source.get("author", ""),
                source.get("used_for", ""),
                source.get("license_note", ""),
                source.get("excerpt", ""),
                source.get("position", 0),
            ),
        )
    conn.execute("DROP TABLE posts_with_scope")
    conn.execute("PRAGMA foreign_keys = ON")


def _normalize_existing_positioning(conn: sqlite3.Connection) -> None:
    if not _table_columns(conn, "posts"):
        return
    conn.execute(
        """
        UPDATE posts
        SET
            title = REPLACE(REPLACE(REPLACE(title, '国外 AI', '海外 AI'), '国外案例', '海外案例'), '国外产品', '海外产品'),
            slug = REPLACE(REPLACE(slug, 'overseas-ai', 'haiwai-ai'), 'overseas-', 'haiwai-'),
            summary = REPLACE(REPLACE(REPLACE(summary, '国外 AI', '海外 AI'), '国外案例', '海外案例'), '国外产品', '海外产品'),
            category = CASE
                WHEN category = '国外 AI 账号' THEN '海外 AI 账号'
                WHEN category = '国外 AI 工具使用' THEN '海外 AI 工具使用'
                WHEN category = '资源合集' THEN '海外 AI 工具使用'
                ELSE category
            END,
            audience = REPLACE(audience, '国外 AI', '海外 AI'),
            prerequisites = REPLACE(REPLACE(prerequisites, '国外案例', '海外案例'), '国外文章', '海外文章'),
            steps = REPLACE(REPLACE(REPLACE(steps, '国外 AI', '海外 AI'), '国外案例', '海外案例'), '国外文章', '海外文章'),
            faq = REPLACE(REPLACE(REPLACE(faq, '国外 AI', '海外 AI'), '国外案例', '海外案例'), '国外文章', '海外文章'),
            risk_notice = REPLACE(REPLACE(REPLACE(risk_notice, '国外 AI', '海外 AI'), '国外案例', '海外案例'), '国外工具', '海外工具'),
            body_markdown = REPLACE(REPLACE(REPLACE(body_markdown, '国外 AI', '海外 AI'), '国外案例', '海外案例'), '国外案例放进', '海外案例放进')
        """
    )


def _create_visits_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL DEFAULT '/',
            ip_hash TEXT NOT NULL,
            ua_hash TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_visits_timestamp ON visits(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_visits_ip_hash ON visits(ip_hash)")


def init_db() -> None:
    with connect() as conn:
        _migrate_scope_schema_if_needed(conn)
        _create_posts_table(conn)
        _create_sources_table(conn)
        _create_indexes_and_fts(conn)
        _create_ai_questions_table(conn)
        _create_visits_table(conn)
        _normalize_existing_positioning(conn)
        _rebuild_fts(conn)
        _rebuild_question_fts(conn)
    consolidate_all_questions()


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _source_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "url": row["url"],
        "site_name": row["site_name"],
        "author": row["author"],
        "used_for": row["used_for"],
        "license_note": row["license_note"],
        "excerpt": row["excerpt"],
    }


def _post_from_row(row: sqlite3.Row, sources: list[dict[str, Any]]) -> dict[str, Any]:
    post = dict(row)
    for field in ("tags", "prerequisites", "steps", "faq"):
        post[field] = _loads(post[field], [])
    post["sources"] = sources
    return post


def _listify(value: Any, field: str) -> list[Any]:
    if isinstance(value, list):
        return value
    if not isinstance(value, str) or not value.strip():
        return []
    if field in ("tags",):
        items = re.split(r"\n|,", value)
    else:
        items = value.split("\n")
    return [item.strip() for item in items if item.strip()]


def _normalize_sources(value: Any) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("sources must be a list")
    normalized: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("each source must be an object")
        title = str(item.get("title", "")).strip()
        url = str(item.get("url", "")).strip()
        if not title or not url:
            raise ValueError("each source requires title and url")
        normalized.append(
            {
                "id": str(item.get("id", "")).strip(),
                "title": title,
                "url": url,
                "site_name": str(item.get("site_name", "")).strip(),
                "author": str(item.get("author", "")).strip(),
                "used_for": str(item.get("used_for", "")).strip(),
                "license_note": str(item.get("license_note", "")).strip(),
                "excerpt": str(item.get("excerpt", "")).strip(),
            }
        )
    return normalized


def normalize_post_payload(payload: dict[str, Any], *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    data = dict(existing or {})
    data.update({key: value for key, value in payload.items() if value is not None})

    required = ["title", "summary", "category", "audience", "risk_notice", "body_markdown"]
    missing = [key for key in required if not str(data.get(key, "")).strip()]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    data["category"] = CATEGORY_ALIASES.get(data["category"], data["category"])
    if data["category"] not in POST_CATEGORIES:
        raise ValueError("unsupported category")
    if data.get("status", "draft") not in POST_STATUSES:
        raise ValueError("status must be draft, published, or archived")

    for field in ("tags", "prerequisites", "steps"):
        data[field] = [str(item).strip() for item in _listify(data.get(field), field) if str(item).strip()]

    faq_items = _listify(data.get("faq"), "faq")
    data["faq"] = [
        {
            "question": str(item.get("question", "")).strip(),
            "answer": str(item.get("answer", "")).strip(),
        }
        for item in faq_items
        if isinstance(item, dict) and (str(item.get("question", "")).strip() or str(item.get("answer", "")).strip())
    ]

    data["sources"] = _normalize_sources(data.get("sources", []))
    data["slug"] = str(data.get("slug") or slugify(data["title"])).strip()
    if not data["slug"]:
        data["slug"] = slugify(data["title"])

    if data["status"] == "published":
        if not data["steps"]:
            raise ValueError("published posts require at least one step")
        if not data["sources"]:
            raise ValueError("published posts require at least one source")
        if data["category"] == "科学上网" and len(str(data["risk_notice"]).strip()) < 20:
            raise ValueError("科学上网 posts require a detailed risk notice")

    now = utc_now()
    data["updated_at"] = now
    if data["status"] == "published" and not data.get("published_at"):
        data["published_at"] = now
    return data


def _fetch_sources(conn: sqlite3.Connection, post_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM post_sources WHERE post_id = ? ORDER BY position ASC, title ASC",
        (post_id,),
    ).fetchall()
    return [_source_from_row(row) for row in rows]


def _sync_sources(conn: sqlite3.Connection, post_id: str, sources: list[dict[str, str]]) -> None:
    conn.execute("DELETE FROM post_sources WHERE post_id = ?", (post_id,))
    for index, source in enumerate(sources):
        conn.execute(
            """
            INSERT INTO post_sources (
                id, post_id, title, url, site_name, author, used_for,
                license_note, excerpt, position
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source.get("id") or f"{post_id}-source-{index + 1}",
                post_id,
                source["title"],
                source["url"],
                source.get("site_name", ""),
                source.get("author", ""),
                source.get("used_for", ""),
                source.get("license_note", ""),
                source.get("excerpt", ""),
                index,
            ),
        )


def _sync_fts(conn: sqlite3.Connection, post_id: str) -> None:
    post = get_post(post_id, include_unpublished=True, conn=conn)
    conn.execute("DELETE FROM posts_fts WHERE post_id = ?", (post_id,))
    if not post:
        return
    source_text = " ".join(
        " ".join([source["title"], source["site_name"], source["used_for"], source["excerpt"]])
        for source in post["sources"]
    )
    conn.execute(
        """
        INSERT INTO posts_fts (
            post_id, title, summary, category, tags, audience, body, steps, faq, sources
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            post_id,
            post["title"],
            post["summary"],
            post["category"],
            " ".join(post["tags"]),
            post["audience"],
            post["body_markdown"],
            " ".join(post["steps"]),
            " ".join(f'{item.get("question", "")} {item.get("answer", "")}' for item in post["faq"]),
            source_text,
        ),
    )


def _rebuild_fts(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM posts_fts")
    rows = conn.execute("SELECT id FROM posts").fetchall()
    for row in rows:
        _sync_fts(conn, row["id"])


def insert_post(post: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_post_payload(post)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO posts (
                id, title, slug, summary, category, tags, audience,
                prerequisites, steps, faq, risk_notice, body_markdown,
                status, published_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized["id"],
                normalized["title"],
                normalized["slug"],
                normalized["summary"],
                normalized["category"],
                json.dumps(normalized["tags"], ensure_ascii=False),
                normalized["audience"],
                json.dumps(normalized["prerequisites"], ensure_ascii=False),
                json.dumps(normalized["steps"], ensure_ascii=False),
                json.dumps(normalized["faq"], ensure_ascii=False),
                normalized["risk_notice"],
                normalized["body_markdown"],
                normalized["status"],
                normalized.get("published_at"),
                normalized["updated_at"],
            ),
        )
        _sync_sources(conn, normalized["id"], normalized["sources"])
        _sync_fts(conn, normalized["id"])
    return get_post(normalized["id"], include_unpublished=True) or normalized


def update_post(post_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    current = get_post(post_id, include_unpublished=True)
    if not current:
        return None
    normalized = normalize_post_payload(payload, existing=current)
    with connect() as conn:
        conn.execute(
            """
            UPDATE posts
            SET title = ?, slug = ?, summary = ?, category = ?, tags = ?,
                audience = ?, prerequisites = ?, steps = ?, faq = ?, risk_notice = ?,
                body_markdown = ?, status = ?, published_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                normalized["title"],
                normalized["slug"],
                normalized["summary"],
                normalized["category"],
                json.dumps(normalized["tags"], ensure_ascii=False),
                normalized["audience"],
                json.dumps(normalized["prerequisites"], ensure_ascii=False),
                json.dumps(normalized["steps"], ensure_ascii=False),
                json.dumps(normalized["faq"], ensure_ascii=False),
                normalized["risk_notice"],
                normalized["body_markdown"],
                normalized["status"],
                normalized.get("published_at"),
                normalized["updated_at"],
                post_id,
            ),
        )
        _sync_sources(conn, post_id, normalized["sources"])
        _sync_fts(conn, post_id)
    return get_post(post_id, include_unpublished=True)


def list_posts(
    *,
    include_unpublished: bool = False,
    category: str | None = None,
    tag: str | None = None,
    q: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 50)
    clauses: list[str] = []
    params: list[Any] = []

    if not include_unpublished:
        clauses.append("p.status = ?")
        params.append("published")
    elif status:
        clauses.append("p.status = ?")
        params.append(status)
    if category:
        category = CATEGORY_ALIASES.get(category, category)
        clauses.append("p.category = ?")
        params.append(category)
    if tag:
        clauses.append("p.tags LIKE ?")
        params.append(f'%"{tag}"%')

    join = ""
    if q:
        if re.search(r"[\u4e00-\u9fff]", q):
            like_q = f"%{q}%"
            clauses.append("(p.title LIKE ? OR p.summary LIKE ? OR p.body_markdown LIKE ?)")
            params.extend([like_q, like_q, like_q])
        else:
            join = "JOIN posts_fts f ON f.post_id = p.id"
            clauses.append("posts_fts MATCH ?")
            params.append(q)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    order = "ORDER BY COALESCE(p.published_at, p.updated_at) DESC"
    offset = (page - 1) * page_size

    with connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(DISTINCT p.id) FROM posts p {join} {where}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT DISTINCT p.* FROM posts p
            {join}
            {where}
            {order}
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()
        all_ids = [row["id"] for row in rows]
        sources_map: dict[str, list[dict[str, Any]]] = {}
        if all_ids:
            placeholders = ",".join("?" for _ in all_ids)
            src_rows = conn.execute(
                f"SELECT * FROM post_sources WHERE post_id IN ({placeholders}) ORDER BY position ASC, title ASC",
                all_ids,
            ).fetchall()
            for src in src_rows:
                sources_map.setdefault(src["post_id"], []).append(_source_from_row(src))
        items = [_post_from_row(row, sources_map.get(row["id"], [])) for row in rows]

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": max((total + page_size - 1) // page_size, 1),
    }


def get_post(identifier: str, *, include_unpublished: bool = False, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
    own_conn = conn is None
    active_conn = conn or connect()
    try:
        query = "SELECT * FROM posts WHERE (id = ? OR slug = ?)"
        params: list[Any] = [identifier, identifier]
        if not include_unpublished:
            query += " AND status = ?"
            params.append("published")
        row = active_conn.execute(query, params).fetchone()
        if not row:
            return None
        return _post_from_row(row, _fetch_sources(active_conn, row["id"]))
    finally:
        if own_conn:
            active_conn.close()


def distinct_categories() -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT category FROM posts WHERE status = 'published' ORDER BY category"
        ).fetchall()
    db_categories = {row[0] for row in rows}
    return [category for category in POST_CATEGORIES if category in db_categories]


def distinct_tags() -> list[str]:
    tags: set[str] = set()
    with connect() as conn:
        rows = conn.execute("SELECT tags FROM posts WHERE status = 'published'").fetchall()
    for row in rows:
        tags.update(_loads(row["tags"], []))
    return sorted(tags)


def seed_if_empty(seed_posts: list[dict[str, Any]]) -> None:
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    if count:
        return
    for post in seed_posts:
        insert_post(post)


def _question_from_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["is_promoted"] = bool(data["is_promoted"])
    return data


def _normalize_question_text(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().lower())


def _ngrams(value: str, n: int = 2) -> set[str]:
    text = _normalize_question_text(value)
    if len(text) < n:
        return {text} if text else set()
    return {text[index : index + n] for index in range(len(text) - n + 1)}


def _question_terms(value: str) -> list[str]:
    terms = re.findall(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]{2,}", value.lower())
    return [term for term in terms if len(term) >= 2][:8]


def _char_overlap(a: str, b: str) -> float:
    left = _ngrams(a)
    right = _ngrams(b)
    if not left or not right:
        return 0.0
    return len(left & right) / max(len(left), len(right))


def _sync_question_fts(conn: sqlite3.Connection, question_id: int) -> None:
    row = conn.execute("SELECT id, question, topic_keyword FROM ai_questions WHERE id = ?", (question_id,)).fetchone()
    conn.execute("DELETE FROM ai_questions_fts WHERE question_id = ?", (question_id,))
    if not row:
        return
    conn.execute(
        """
        INSERT INTO ai_questions_fts (question_id, question, topic_keyword)
        VALUES (?, ?, ?)
        """,
        (row["id"], row["question"], row["topic_keyword"]),
    )


def _rebuild_question_fts(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM ai_questions_fts")
    rows = conn.execute("SELECT id FROM ai_questions").fetchall()
    for row in rows:
        _sync_question_fts(conn, row["id"])


def find_similar_question(question: str, *, threshold: float = QUESTION_SIMILARITY_THRESHOLD) -> dict[str, Any] | None:
    normalized_question = re.sub(r"\s+", " ", question).strip()
    if not normalized_question:
        return None
    with connect() as conn:
        exact = conn.execute("SELECT * FROM ai_questions WHERE question = ?", (normalized_question,)).fetchone()
        if exact:
            return _question_from_row(exact)

        candidates: dict[int, sqlite3.Row] = {}
        terms = _question_terms(normalized_question)
        if terms:
            match_query = " OR ".join(terms)
            try:
                rows = conn.execute(
                    """
                    SELECT q.* FROM ai_questions q
                    JOIN ai_questions_fts f ON f.question_id = q.id
                    WHERE ai_questions_fts MATCH ?
                    ORDER BY q.ask_count DESC, q.updated_at DESC
                    LIMIT 20
                    """,
                    (match_query,),
                ).fetchall()
                candidates.update({row["id"]: row for row in rows})
            except sqlite3.OperationalError:
                pass

        if len(candidates) < 20:
            rows = conn.execute(
                """
                SELECT * FROM ai_questions
                ORDER BY ask_count DESC, updated_at DESC
                LIMIT 100
                """
            ).fetchall()
            candidates.update({row["id"]: row for row in rows})

    best: sqlite3.Row | None = None
    best_score = 0.0
    for candidate in candidates.values():
        score = _char_overlap(normalized_question, candidate["question"])
        if score > best_score:
            best = candidate
            best_score = score
    if best and best_score >= threshold:
        return _question_from_row(best)
    return None


def increment_ask_count(question_id: int) -> dict[str, Any] | None:
    now = utc_now()
    with connect() as conn:
        conn.execute(
            """
            UPDATE ai_questions
            SET ask_count = ask_count + 1, updated_at = ?
            WHERE id = ?
            """,
            (now, question_id),
        )
        row = conn.execute("SELECT * FROM ai_questions WHERE id = ?", (question_id,)).fetchone()
    return _question_from_row(row) if row else None


def is_answer_stale(question: dict[str, Any], *, stale_seconds: int = QUESTION_STALE_SECONDS) -> bool:
    timestamp = str(question.get("answer_updated_at") or question.get("updated_at") or "")
    if not timestamp:
        return True
    try:
        updated_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return True
    return (datetime.now(UTC) - updated_at).total_seconds() > stale_seconds


def insert_question(question: str, answer: str, topic_keyword: str = "") -> dict[str, Any]:
    normalized_question = re.sub(r"\s+", " ", question).strip()
    if not normalized_question:
        raise ValueError("question is required")
    now = utc_now()
    with connect() as conn:
        existing = conn.execute(
            "SELECT * FROM ai_questions WHERE question = ?",
            (normalized_question,),
        ).fetchone()
        if not existing:
            similar = find_similar_question(normalized_question)
            if similar:
                existing = conn.execute("SELECT * FROM ai_questions WHERE id = ?", (similar["id"],)).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE ai_questions
                SET ask_count = ask_count + 1,
                    answer = ?,
                    topic_keyword = CASE WHEN ? = '' THEN topic_keyword ELSE ? END,
                    answer_updated_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (answer, topic_keyword, topic_keyword, now, now, existing["id"]),
            )
            _sync_question_fts(conn, existing["id"])
            row = conn.execute("SELECT * FROM ai_questions WHERE id = ?", (existing["id"],)).fetchone()
        else:
            cursor = conn.execute(
                """
                INSERT INTO ai_questions (
                    question, answer, topic_keyword, ask_count, is_promoted,
                    promoted_post_id, answer_updated_at, created_at, updated_at
                )
                VALUES (?, ?, ?, 1, 0, NULL, ?, ?, ?)
                """,
                (normalized_question, answer, topic_keyword, now, now, now),
            )
            _sync_question_fts(conn, cursor.lastrowid)
            row = conn.execute("SELECT * FROM ai_questions WHERE id = ?", (cursor.lastrowid,)).fetchone()
    if not row:
        raise ValueError("failed to save question")
    return _question_from_row(row)


def consolidate_all_questions() -> None:
    if not _QUESTION_CONSOLIDATION_LOCK.acquire(blocking=False):
        return
    try:
        with connect() as conn:
            rows = [dict(row) for row in conn.execute(
                """
                SELECT * FROM ai_questions
                ORDER BY ask_count DESC, updated_at DESC
                """
            ).fetchall()]
            keepers: list[dict[str, Any]] = []
            for row in rows:
                merged_into: dict[str, Any] | None = None
                for keeper in keepers:
                    if _char_overlap(row["question"], keeper["question"]) >= QUESTION_SIMILARITY_THRESHOLD:
                        merged_into = keeper
                        break
                if not merged_into:
                    keepers.append(row)
                    continue
                keep_answer_from_row = str(row["answer_updated_at"] or row["updated_at"]) > str(
                    merged_into["answer_updated_at"] or merged_into["updated_at"]
                )
                new_updated_at = utc_now()
                conn.execute(
                    """
                    UPDATE ai_questions
                    SET ask_count = ask_count + ?,
                        answer = CASE WHEN ? THEN ? ELSE answer END,
                        topic_keyword = CASE WHEN topic_keyword = '' THEN ? ELSE topic_keyword END,
                        answer_updated_at = CASE WHEN ? THEN ? ELSE answer_updated_at END,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        row["ask_count"],
                        int(keep_answer_from_row),
                        row["answer"],
                        row["topic_keyword"],
                        int(keep_answer_from_row),
                        row["answer_updated_at"] or row["updated_at"],
                        new_updated_at,
                        merged_into["id"],
                    ),
                )
                merged_into["ask_count"] = int(merged_into["ask_count"]) + int(row["ask_count"])
                merged_into["updated_at"] = new_updated_at
                if not merged_into.get("topic_keyword") and row.get("topic_keyword"):
                    merged_into["topic_keyword"] = row["topic_keyword"]
                if keep_answer_from_row:
                    merged_into["answer"] = row["answer"]
                    merged_into["answer_updated_at"] = row["answer_updated_at"] or row["updated_at"]
                conn.execute("DELETE FROM ai_questions WHERE id = ?", (row["id"],))
            _rebuild_question_fts(conn)
    finally:
        _QUESTION_CONSOLIDATION_LOCK.release()


def list_popular_questions(*, include_all: bool = False, limit: int = 12) -> list[dict[str, Any]]:
    limit = min(max(limit, 1), 100)
    where = "" if include_all else "WHERE q.is_promoted = 0"
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT
                q.*,
                p.slug AS promoted_post_slug,
                p.status AS promoted_post_status
            FROM ai_questions q
            LEFT JOIN posts p ON p.id = q.promoted_post_id
            {where}
            ORDER BY q.ask_count DESC, q.updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_question_from_row(row) for row in rows]


def get_question(question_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM ai_questions WHERE id = ?", (question_id,)).fetchone()
    return _question_from_row(row) if row else None


def promote_question(question_id: int, post_id: str) -> dict[str, Any] | None:
    now = utc_now()
    with connect() as conn:
        conn.execute(
            """
            UPDATE ai_questions
            SET is_promoted = 1, promoted_post_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (post_id, now, question_id),
        )
        row = conn.execute("SELECT * FROM ai_questions WHERE id = ?", (question_id,)).fetchone()
    return _question_from_row(row) if row else None


_BOT_UA_PATTERNS = [
    "bot", "crawler", "spider", "scraper", "curl", "wget", "python", "go-http",
    "java/", "node-fetch", "axios", "bytespider", "googlebot", "bingbot",
    "slurp", "duckduckbot", "baiduspider", "yandex", "sogou", "facebookexternalhit",
    "twitterbot", "rogerbot", "linkedinbot", "embedly", "quora link preview",
    "showyoubot", "outbrain", "pinterest", "slack", "vkshare", "w3c_validator",
    "redditbot", "applebot", "whatsapp", "flipboard", "tumblr", "bitlybot",
    "semrush", "ahrefsbot", "dotbot", "mj12bot", "archiver", "httrack",
    "check_http", "nmap", "masscan", "netcraft", "zgrab",
]


def _is_bot(ua: str) -> bool:
    if not ua:
        return False
    lowered = ua.lower()
    return any(pattern in lowered for pattern in _BOT_UA_PATTERNS)


def _hash_visitor(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def record_visit(path: str, ip: str, ua: str) -> dict[str, int]:
    if _is_bot(ua):
        now = utc_now()
        today = now[:10]
        with connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
            today_pv = conn.execute(
                "SELECT COUNT(*) FROM visits WHERE timestamp >= ?",
                (today,),
            ).fetchone()[0]
        return {"total_visits": total, "today_visits": today_pv}
    now = utc_now()
    ip_hash = _hash_visitor(ip)
    ua_hash = _hash_visitor(ua)
    short_path = path[:512]
    with connect() as conn:
        conn.execute(
            "INSERT INTO visits (path, ip_hash, ua_hash, timestamp) VALUES (?, ?, ?, ?)",
            (short_path, ip_hash, ua_hash, now),
        )
        today = now[:10]
        total = conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
        today_pv = conn.execute(
            "SELECT COUNT(*) FROM visits WHERE timestamp >= ?",
            (today,),
        ).fetchone()[0]
    return {"total_visits": total, "today_visits": today_pv}


def get_stats() -> dict[str, Any]:
    now_utc = datetime.now(UTC)
    today_str = now_utc.strftime("%Y-%m-%d")
    yesterday_str = (now_utc - timedelta(days=1)).strftime("%Y-%m-%d")
    week_start = (now_utc - timedelta(days=now_utc.weekday())).strftime("%Y-%m-%d")

    with connect() as conn:
        today_pv = conn.execute(
            "SELECT COUNT(*) FROM visits WHERE timestamp >= ?", (today_str,)
        ).fetchone()[0]
        today_uv = conn.execute(
            "SELECT COUNT(DISTINCT ip_hash || ua_hash) FROM visits WHERE timestamp >= ?",
            (today_str,),
        ).fetchone()[0]

        yesterday_pv = conn.execute(
            "SELECT COUNT(*) FROM visits WHERE timestamp >= ? AND timestamp < ?",
            (yesterday_str, today_str),
        ).fetchone()[0]
        yesterday_uv = conn.execute(
            "SELECT COUNT(DISTINCT ip_hash || ua_hash) FROM visits WHERE timestamp >= ? AND timestamp < ?",
            (yesterday_str, today_str),
        ).fetchone()[0]

        week_pv = conn.execute(
            "SELECT COUNT(*) FROM visits WHERE timestamp >= ?", (week_start,)
        ).fetchone()[0]
        week_uv = conn.execute(
            "SELECT COUNT(DISTINCT ip_hash || ua_hash) FROM visits WHERE timestamp >= ?",
            (week_start,),
        ).fetchone()[0]

        total_pv = conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
        total_uv = conn.execute(
            "SELECT COUNT(DISTINCT ip_hash || ua_hash) FROM visits"
        ).fetchone()[0]

        # 最近 7 天每天 PV/UV（含零访问天数）
        daily_rows = conn.execute(
            """
            SELECT
                substr(timestamp, 1, 10) AS date,
                COUNT(*) AS pv,
                COUNT(DISTINCT ip_hash || ua_hash) AS uv
            FROM visits
            WHERE timestamp >= ?
            GROUP BY date
            ORDER BY date ASC
            """,
            ((now_utc - timedelta(days=6)).strftime("%Y-%m-%d"),),
        ).fetchall()
        daily_map = {row[0]: {"date": row[0], "pv": row[1], "uv": row[2]} for row in daily_rows}
        daily = []
        for i in range(6, -1, -1):
            day_str = (now_utc - timedelta(days=i)).strftime("%Y-%m-%d")
            daily.append(daily_map.get(day_str, {"date": day_str, "pv": 0, "uv": 0}))

    return {
        "today": {"pv": today_pv, "uv": today_uv},
        "yesterday": {"pv": yesterday_pv, "uv": yesterday_uv},
        "this_week": {"pv": week_pv, "uv": week_uv},
        "total": {"pv": total_pv, "uv": total_uv},
        "daily": daily,
    }
