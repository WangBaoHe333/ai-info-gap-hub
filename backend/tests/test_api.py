from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ["APP_DB_PATH"] = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["ADMIN_USERNAME"] = "tester"
os.environ["ADMIN_PASSWORD"] = "secret"
os.environ["APP_SECRET_KEY"] = "test-secret"

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402
from backend.app.db import insert_question  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def post_payload(status: str = "draft", category: str = "科学上网") -> dict:
    return {
        "title": "测试科学上网风险提示帖子",
        "slug": "test-network-risk-post",
        "summary": "用于验证帖子发布校验、公开可见性和后台状态流转。",
        "category": category,
        "tags": ["测试", "科学上网"],
        "audience": "测试人员",
        "prerequisites": ["准备来源", "填写风险提示"],
        "steps": ["创建草稿", "补充来源", "发布验证"],
        "faq": [{"question": "能否直接搬运？", "answer": "不能，默认只做摘要和短引用。"}],
        "risk_notice": "科学上网相关内容可能受到本地法律法规和平台条款影响。本文仅作信息学习和风险提示，不构成规避监管建议。",
        "body_markdown": "## 测试正文\n这是用于测试的结构化教程正文。",
        "sources": [
            {
                "title": "测试来源",
                "url": "https://example.com/source",
                "site_name": "Example",
                "author": "",
                "used_for": "测试来源标注",
                "license_note": "仅短引用和来源链接",
                "excerpt": "测试短引用",
            }
        ],
        "status": status,
    }


def main() -> None:
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert_true(health.status_code == 200, "health endpoint failed")

        posts = client.get("/api/posts?page=1&page_size=3")
        assert_true(posts.status_code == 200, "public post list failed")
        body = posts.json()
        assert_true(body["total"] >= 8, "seed post count should be at least 8")
        assert_true(len(body["items"]) == 3, "pagination page_size not applied")
        assert_true(all(item["status"] == "published" for item in body["items"]), "public API leaked unpublished posts")
        assert_true(all("scope" not in item for item in body["items"]), "public API should not expose scope")

        default_posts = client.get("/api/posts")
        assert_true(default_posts.status_code == 200, "public default post list failed")
        assert_true(default_posts.json()["page_size"] == 10, "public default page_size should be 10")

        categories = client.get("/api/categories")
        assert_true(categories.status_code == 200, "categories endpoint failed")
        assert_true("资源合集" not in categories.json(), "资源合集 should be removed from categories")

        filtered = client.get("/api/posts?scope=overseas&category=科学上网")
        assert_true(filtered.status_code == 200, "category filter failed")
        assert_true(all(item["category"] == "科学上网" for item in filtered.json()["items"]), "category filter incorrect")

        searched = client.get("/api/posts?q=账号")
        assert_true(searched.status_code == 200, "FTS search failed")
        assert_true(searched.json()["total"] >= 1, "FTS search should find seeded account content")

        chinese_search = client.get("/api/posts?q=海外")
        assert_true(chinese_search.status_code == 200, "Chinese LIKE search failed")
        assert_true(chinese_search.json()["total"] >= 1, "Chinese search should find seeded overseas content")

        first_slug = body["items"][0]["slug"]
        nav = client.get(f"/api/posts/nav/{first_slug}")
        assert_true(nav.status_code == 200, "post nav endpoint failed")
        assert_true("prev" in nav.json() and "next" in nav.json(), "post nav should return prev and next keys")

        cached_question = insert_question("ChatGPT 新手缓存测试问题", "## 缓存回答\n先明确任务，再学习提示词。", "AI工具")
        cached_answer = client.post("/api/qa/ask", json={"question": "ChatGPT 新手缓存测试问题"})
        assert_true(cached_answer.status_code == 200, f"cached QA failed: {cached_answer.text}")
        assert_true(cached_answer.json()["id"] == cached_question["id"], "cached QA should return existing question")
        assert_true(cached_answer.json()["ask_count"] == cached_question["ask_count"] + 1, "cached QA should increment ask_count")

        streamed_answer = client.post("/api/qa/ask/stream", json={"question": "ChatGPT 新手缓存测试问题"})
        assert_true(streamed_answer.status_code == 200, f"streamed cached QA failed: {streamed_answer.text}")
        assert_true('"type": "done"' in streamed_answer.text, "streamed cached QA should return done event")
        assert_true("缓存回答" in streamed_answer.text, "streamed cached QA should include cached answer")

        invalid_login = client.post("/api/admin/login", json={"username": "tester", "password": "wrong"})
        assert_true(invalid_login.status_code == 401, "invalid login should be rejected")

        login = client.post("/api/admin/login", json={"username": "tester", "password": "secret"})
        assert_true(login.status_code == 200, "valid login failed")
        headers = {"Authorization": f"Bearer {login.json()['token']}"}

        unauthorized = client.get("/api/admin/posts")
        assert_true(unauthorized.status_code == 401, "admin posts should require auth")

        bad_publish = post_payload(status="published")
        bad_publish["sources"] = []
        rejected = client.post("/api/admin/posts", json=bad_publish, headers=headers)
        assert_true(rejected.status_code == 400, "published science post without sources should be rejected")

        created = client.post("/api/admin/posts", json=post_payload(status="draft"), headers=headers)
        assert_true(created.status_code == 201, f"create draft failed: {created.text}")
        assert_true("scope" not in created.json(), "admin create response should not expose scope")
        post_id = created.json()["id"]
        slug = created.json()["slug"]

        hidden = client.get(f"/api/posts/{slug}")
        assert_true(hidden.status_code == 404, "draft should not be visible publicly")

        published = client.patch(f"/api/admin/posts/{post_id}/status", json={"status": "published"}, headers=headers)
        assert_true(published.status_code == 200, f"publish failed: {published.text}")

        visible = client.get(f"/api/posts/{slug}")
        assert_true(visible.status_code == 200, "published post should be visible")
        assert_true(visible.json()["sources"][0]["url"] == "https://example.com/source", "source should be returned")

        archived = client.patch(f"/api/admin/posts/{post_id}/status", json={"status": "archived"}, headers=headers)
        assert_true(archived.status_code == 200, "archive status update failed")
        gone = client.get(f"/api/posts/{slug}")
        assert_true(gone.status_code == 404, "archived post should be hidden publicly")

        before_import = client.get("/api/admin/posts", headers=headers).json()["total"]
        blocked_import = client.post("/api/admin/import-url", json={"url": "http://127.0.0.1/private"}, headers=headers)
        assert_true(blocked_import.status_code == 400, "URL import should reject loopback addresses")
        failed_import = client.post("/api/admin/import-url", json={"url": "https://127.0.0.1:1/nope"}, headers=headers)
        assert_true(failed_import.status_code == 400, "failed URL import should return 400")
        after_import = client.get("/api/admin/posts", headers=headers).json()["total"]
        assert_true(before_import == after_import, "failed import should not create dirty data")

    print("API tests passed")


if __name__ == "__main__":
    main()
