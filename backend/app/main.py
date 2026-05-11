from __future__ import annotations

import ipaddress
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from .auth import create_token, verify_login, verify_token
from .db import (
    connect,
    distinct_categories,
    distinct_tags,
    find_similar_question,
    get_post,
    get_question,
    get_stats,
    increment_ask_count,
    init_db,
    insert_question,
    insert_post,
    is_answer_stale,
    list_popular_questions,
    list_posts,
    normalize_post_payload,
    promote_question,
    record_visit,
    slugify,
    seed_if_empty,
    update_post,
    utc_now,
)
from .qa import answer_ai_question, generate_post_from_question, validate_question
from .seed import SEED_POSTS

app = FastAPI(title="AI 信息差帖子站 API", version="0.2.0")

_qa_rate_limit: dict[str, list[float]] = defaultdict(list)
_QA_RATE_LIMIT = 5
_QA_RATE_WINDOW = 60
_BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "169.254.169.254",
    "100.100.100.200",
    "metadata.google.internal",
}

_cors_origins = os.getenv("CORS_ORIGINS", "")
cors_origins = [o.strip() for o in _cors_origins.split(",") if o.strip()] if _cors_origins else []

if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _check_qa_rate_limit(ip: str) -> bool:
    now = time.time()
    window = now - _QA_RATE_WINDOW
    _qa_rate_limit[ip] = [timestamp for timestamp in _qa_rate_limit[ip] if timestamp > window]
    if len(_qa_rate_limit[ip]) >= _QA_RATE_LIMIT:
        return False
    _qa_rate_limit[ip].append(now)
    return True


def _is_safe_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    if not host or host in _BLOCKED_HOSTS:
        return False
    try:
        addr = ipaddress.ip_address(host)
        if addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_multicast:
            return False
    except ValueError:
        pass
    return True


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    token: str


class SourcePayload(BaseModel):
    id: str | None = None
    title: str = Field(min_length=1)
    url: HttpUrl | str
    site_name: str = ""
    author: str = ""
    used_for: str = ""
    license_note: str = ""
    excerpt: str = ""

    def as_db_payload(self) -> dict[str, str]:
        payload = self.model_dump()
        payload["url"] = str(payload["url"])
        return {key: str(value or "") for key, value in payload.items()}


class FAQPayload(BaseModel):
    question: str = ""
    answer: str = ""


class PostPayload(BaseModel):
    title: str = Field(min_length=2)
    slug: str | None = None
    summary: str = Field(min_length=6)
    category: str
    tags: list[str] = Field(default_factory=list)
    audience: str = Field(min_length=2)
    prerequisites: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    faq: list[FAQPayload] = Field(default_factory=list)
    risk_notice: str = Field(min_length=6)
    body_markdown: str = Field(min_length=6)
    sources: list[SourcePayload] = Field(default_factory=list)
    status: Literal["draft", "published", "archived"] = "draft"

    def as_db_payload(self) -> dict[str, Any]:
        payload = self.model_dump()
        payload["sources"] = [source.as_db_payload() for source in self.sources]
        payload["faq"] = [item.model_dump() for item in self.faq]
        return payload


class StatusPayload(BaseModel):
    status: Literal["draft", "published", "archived"]


class ImportUrlPayload(BaseModel):
    url: HttpUrl | str


class AskQuestionPayload(BaseModel):
    question: str = Field(min_length=2, max_length=500)


class PromoteQuestionPayload(BaseModel):
    question_id: int = Field(ge=1)


class _ArticleHTMLParser(HTMLParser):
    _self_closing = {"br", "hr", "img", "input", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.meta: dict[str, str] = {}
        self._in_title = False
        self._skip_depth = 0
        self.text_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.lower(): value or "" for key, value in attrs}
        if tag == "meta":
            name = attrs_map.get("name", "").lower() or attrs_map.get("property", "").lower()
            content = attrs_map.get("content", "").strip()
            if name and content:
                self.meta[name] = content
        if tag in self._self_closing:
            return
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        text = re.sub(r"\s+", " ", data).strip()
        if not text:
            return
        if self._in_title:
            self.title += text
            return
        if not self._skip_depth and len(text) > 20:
            self.text_chunks.append(text)


def require_admin(authorization: Annotated[str | None, Header()] = None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_token(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


def _background_refresh_answer(question_id: int, question: str, topic_keyword: str) -> None:
    try:
        answer = answer_ai_question(question)
        now = utc_now()
        with connect() as conn:
            conn.execute(
                """
                UPDATE ai_questions
                SET answer = ?,
                    topic_keyword = CASE WHEN ? = '' THEN topic_keyword ELSE ? END,
                    answer_updated_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (answer, topic_keyword, topic_keyword, now, now, question_id),
            )
            row = conn.execute("SELECT id, question, topic_keyword FROM ai_questions WHERE id = ?", (question_id,)).fetchone()
            conn.execute("DELETE FROM ai_questions_fts WHERE question_id = ?", (question_id,))
            if row:
                conn.execute(
                    """
                    INSERT INTO ai_questions_fts (question_id, question, topic_keyword)
                    VALUES (?, ?, ?)
                    """,
                    (row["id"], row["question"], row["topic_keyword"]),
                )
    except Exception:
        import sys

        print(f"[bg-refresh] 后台刷新答案失败 question_id={question_id}", file=sys.stderr, flush=True)


@app.on_event("startup")
def startup() -> None:
    init_db()
    seed_if_empty(SEED_POSTS)


class VisitPayload(BaseModel):
    path: str = Field(default="/", max_length=512)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/visits")
def visit(payload: VisitPayload, request: Request) -> dict[str, int]:
    ip = request.headers.get("X-Real-IP") or (request.client.host if request.client else "unknown")
    ua = request.headers.get("User-Agent", "")
    return record_visit(payload.path, ip, ua)


@app.post("/api/admin/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    if not verify_login(payload.username, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    return LoginResponse(token=create_token(payload.username))


@app.get("/api/posts")
def posts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    category: str | None = None,
    tag: str | None = None,
    q: str | None = Query(default=None, min_length=1),
) -> dict[str, Any]:
    return list_posts(page=page, page_size=page_size, category=category, tag=tag, q=q)


@app.get("/api/posts/nav/{slug}")
def post_nav(slug: str) -> dict[str, Any]:
    post = get_post(slug)
    if not post or post["status"] != "published":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文章不存在")
    published_at = post.get("published_at") or post.get("updated_at")
    with connect() as conn:
        prev_row = conn.execute(
            """
            SELECT slug, title, category FROM posts
            WHERE status = 'published' AND COALESCE(published_at, updated_at) < ?
            ORDER BY COALESCE(published_at, updated_at) DESC
            LIMIT 1
            """,
            (published_at,),
        ).fetchone()
        next_row = conn.execute(
            """
            SELECT slug, title, category FROM posts
            WHERE status = 'published' AND COALESCE(published_at, updated_at) > ?
            ORDER BY COALESCE(published_at, updated_at) ASC
            LIMIT 1
            """,
            (published_at,),
        ).fetchone()
    return {
        "prev": dict(prev_row) if prev_row else None,
        "next": dict(next_row) if next_row else None,
    }


@app.get("/api/posts/{slug}")
def post_detail(slug: str) -> dict[str, Any]:
    post = get_post(slug)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


@app.get("/api/categories")
def categories() -> list[str]:
    return distinct_categories()


@app.get("/api/tags")
def tags() -> list[str]:
    return distinct_tags()


@app.post("/api/qa/ask")
def ask_question(payload: AskQuestionPayload, request: Request) -> dict[str, Any]:
    question = payload.question.strip()
    client_ip = request.headers.get("X-Real-IP") or (request.client.host if request.client else "unknown")
    if not _check_qa_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="提问太频繁，请稍后再试（每分钟最多 5 次）",
        )
    cached = find_similar_question(question)
    if cached:
        saved = increment_ask_count(cached["id"]) or cached
        if is_answer_stale(saved) and saved.get("ask_count", 0) >= 3:
            threading.Thread(
                target=_background_refresh_answer,
                args=(saved["id"], saved["question"], saved.get("topic_keyword", "")),
                daemon=True,
            ).start()
        return saved
    try:
        validation = validate_question(question)
    except Exception as exc:
        import sys
        print(f"[qa] 问题验证失败：{exc}", file=sys.stderr, flush=True)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI 服务暂时不可用，请稍后重试") from exc
    if not validation["is_ai_related"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation["reason"] or "这个问题和本站 AI 主题不相关，请换一个 AI 工具、账号、支付、工作流或风险避坑问题。",
        )
    try:
        answer = answer_ai_question(question)
        saved = insert_question(question, answer, validation["topic_keyword"])
    except Exception as exc:
        import sys
        print(f"[qa] 回答生成失败：{exc}", file=sys.stderr, flush=True)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI 服务暂时不可用，请稍后重试") from exc
    return saved


@app.post("/api/qa/ask/stream")
def ask_question_stream(payload: AskQuestionPayload, request: Request) -> StreamingResponse:
    question = payload.question.strip()
    client_ip = request.headers.get("X-Real-IP") or (request.client.host if request.client else "unknown")
    if not _check_qa_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="提问太频繁，请稍后再试（每分钟最多 5 次）",
        )

    def event(data: dict[str, Any]) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    def generate():
        try:
            yield event({"type": "status", "message": "正在查找是否已有相似答案..."})
            cached = find_similar_question(question)
            if cached:
                saved = increment_ask_count(cached["id"]) or cached
                yield event({"type": "status", "message": "已找到相似问题，正在读取缓存答案..."})
                if is_answer_stale(saved) and saved.get("ask_count", 0) >= 3:
                    threading.Thread(
                        target=_background_refresh_answer,
                        args=(saved["id"], saved["question"], saved.get("topic_keyword", "")),
                        daemon=True,
                    ).start()
                yield event({"type": "done", "data": saved})
                return

            yield event({"type": "status", "message": "正在验证问题是否与 AI 相关..."})
            validation = validate_question(question)
            if not validation["is_ai_related"]:
                yield event(
                    {
                        "type": "error",
                        "message": validation["reason"]
                        or "这个问题和本站 AI 主题不相关，请换一个 AI 工具、账号、支付、工作流或风险避坑问题。",
                    }
                )
                return

            yield event({"type": "status", "message": "验证通过，正在生成回答，请耐心等待..."})
            answer = answer_ai_question(question)
            saved = insert_question(question, answer, validation["topic_keyword"])
            yield event({"type": "done", "data": saved})
        except Exception as exc:
            import sys
            print(f"[qa-stream] 错误：{exc}", file=sys.stderr, flush=True)
            yield event({"type": "error", "message": "AI 服务暂时不可用，请稍后重试"})

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/qa/popular")
def popular_questions(limit: int = Query(default=6, ge=1, le=20)) -> list[dict[str, Any]]:
    return list_popular_questions(limit=limit)


@app.get("/api/admin/posts", dependencies=[Depends(require_admin)])
def admin_posts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    status_filter: Literal["draft", "published", "archived"] | None = Query(default=None, alias="status"),
    category: str | None = None,
    q: str | None = Query(default=None, min_length=1),
) -> dict[str, Any]:
    return list_posts(
        include_unpublished=True,
        status=status_filter,
        page=page,
        page_size=page_size,
        category=category,
        q=q,
    )


@app.get("/api/admin/posts/{post_id}", dependencies=[Depends(require_admin)])
def admin_post(post_id: str) -> dict[str, Any]:
    post = get_post(post_id, include_unpublished=True)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


@app.post("/api/admin/posts", dependencies=[Depends(require_admin)], status_code=status.HTTP_201_CREATED)
def create_post(payload: PostPayload) -> dict[str, Any]:
    data = payload.as_db_payload()
    data["id"] = str(uuid4())
    data["slug"] = data.get("slug") or slugify(data["title"])
    try:
        return insert_post(data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        if "UNIQUE constraint failed: posts.slug" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"slug '{data['slug']}' 已存在，请换一个标题或手动填写 slug",
            ) from exc
        raise


@app.put("/api/admin/posts/{post_id}", dependencies=[Depends(require_admin)])
def replace_post(post_id: str, payload: PostPayload) -> dict[str, Any]:
    try:
        updated = update_post(post_id, payload.as_db_payload())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        if "UNIQUE constraint failed: posts.slug" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="slug 已存在，请换一个",
            ) from exc
        raise
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return updated


@app.patch("/api/admin/posts/{post_id}/status", dependencies=[Depends(require_admin)])
def change_status(post_id: str, payload: StatusPayload) -> dict[str, Any]:
    try:
        updated = update_post(post_id, {"status": payload.status})
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return updated


@app.post("/api/admin/import-url", dependencies=[Depends(require_admin)])
def import_url(payload: ImportUrlPayload) -> dict[str, Any]:
    url = str(payload.url)
    if not _is_safe_url(url):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不允许访问内网地址")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "AI-Info-Gap-Hub/0.2 (+draft importer)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            content_type = response.headers.get("content-type", "")
            raw = response.read(600_000)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"URL import failed: {exc}") from exc

    charset_match = re.search(r"charset=([\w-]+)", content_type, re.I)
    charset = charset_match.group(1) if charset_match else "utf-8"
    html = raw.decode(charset, errors="ignore")
    parser = _ArticleHTMLParser()
    parser.feed(html)

    parsed_url = urllib.parse.urlparse(url)
    title = parser.meta.get("og:title") or parser.title.strip() or parsed_url.netloc
    description = parser.meta.get("description") or parser.meta.get("og:description") or ""
    excerpt = " ".join(parser.text_chunks[:4])[:600]
    summary = description[:240] or excerpt[:240] or "从外部链接导入的待审核草稿，请人工补充摘要、步骤和风险提示。"

    draft = {
        "title": title[:120],
        "slug": slugify(title),
        "summary": summary,
        "category": "海外 AI 工具使用",
        "tags": ["URL导入", "待审核"],
        "audience": "请填写适合人群",
        "prerequisites": ["请人工补充准备条件"],
        "steps": ["阅读原文并确认授权或引用边界", "改写为本站原创摘要和步骤", "补充风险提示和来源说明"],
        "faq": [],
        "risk_notice": "这是 URL 导入生成的草稿，发布前必须人工核验事实、版权、来源和本地合规风险。",
        "body_markdown": f"## 导入摘要\n{summary}\n\n## 编辑提醒\n请不要整篇搬运原站内容。保留必要短引用、来源链接和你自己的结构化说明。",
        "sources": [
            {
                "title": title[:120],
                "url": url,
                "site_name": parsed_url.netloc,
                "author": "",
                "used_for": "URL 导入草稿来源，发布前需人工核验。",
                "license_note": "未确认授权；默认仅允许摘要、短引用和来源链接。",
                "excerpt": excerpt[:260],
            }
        ],
        "status": "draft",
    }
    normalize_post_payload(draft)
    return draft


@app.get("/api/admin/stats", dependencies=[Depends(require_admin)])
def admin_stats() -> dict[str, Any]:
    return get_stats()


@app.get("/api/admin/qa/questions", dependencies=[Depends(require_admin)])
def admin_qa_questions(limit: int = Query(default=50, ge=1, le=100)) -> list[dict[str, Any]]:
    return list_popular_questions(include_all=True, limit=limit)


@app.post("/api/admin/qa/promote", dependencies=[Depends(require_admin)])
def admin_promote_question(payload: PromoteQuestionPayload) -> dict[str, Any]:
    question = get_question(payload.question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    try:
        generated = generate_post_from_question(
            question["question"],
            question["answer"],
            question.get("topic_keyword", ""),
        )
        generated["id"] = str(uuid4())
        base_slug = generated.get("slug") or slugify(generated["title"])
        generated["slug"] = f"{base_slug}-qa-{payload.question_id}-{uuid4().hex[:6]}"
        post = insert_post(generated)
        promoted = promote_question(payload.question_id, post["id"])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        import sys
        print(f"[qa-promote] 文章生成失败：{exc}", file=sys.stderr, flush=True)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI 服务暂时不可用，请稍后重试") from exc
    return {"question": promoted, "post": post}


_STATIC_DIR = Path(__file__).resolve().parents[2] / "dist"

if os.getenv("SERVE_STATIC", "").lower() == "true" and _STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=_STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def _spa_fallback(full_path: str):
        # 防止路径遍历攻击
        safe_path = Path(full_path).as_posix().lstrip("/")
        if ".." in safe_path.split("/"):
            return FileResponse(_STATIC_DIR / "index.html")
        file_path = _STATIC_DIR / safe_path
        resolved = file_path.resolve()
        if not str(resolved).startswith(str(_STATIC_DIR.resolve())):
            return FileResponse(_STATIC_DIR / "index.html")
        if resolved.is_file():
            return FileResponse(resolved)
        return FileResponse(_STATIC_DIR / "index.html")
