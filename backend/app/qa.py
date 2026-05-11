from __future__ import annotations

import json
import os
from typing import Any

import httpx

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-v4-pro"


def _api_key() -> str:
    key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_KEY")
    if not key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY，暂时无法使用 AI 问答。")
    return key


def _chat(messages: list[dict[str, str]], *, temperature: float) -> str:
    payload = {
        "model": os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL),
        "temperature": temperature,
        "messages": messages,
    }
    with httpx.Client(timeout=120) as client:
        response = client.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {_api_key()}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
    data = response.json()
    return str(data["choices"][0]["message"]["content"]).strip()


def _loads_json_object(value: str) -> dict[str, Any]:
    text = value.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        import re as _re

        text = _re.sub(r",\s*}", "}", text)
        text = _re.sub(r",\s*]", "]", text)
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"AI 返回了无法解析的 JSON：{exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("AI response must be a JSON object")
    return parsed


def validate_question(question: str) -> dict[str, Any]:
    content = _chat(
        [
            {
                "role": "system",
                "content": (
                    "你是 AI 信息差教程站的问题审核器。判断用户问题是否和 AI 工具、"
                    "海外 AI 账号、支付订阅、科学上网风险、AI 创作工作流、案例玩法、"
                    "账号安全或合规避坑相关。只返回 JSON。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "请返回格式："
                    '{"is_ai_related": true, "topic_keyword": "分类关键词", "reason": "一句话原因"}'
                    f"\n用户问题：{question}"
                ),
            },
        ],
        temperature=0.0,
    )
    parsed = _loads_json_object(content)
    return {
        "is_ai_related": bool(parsed.get("is_ai_related")),
        "topic_keyword": str(parsed.get("topic_keyword") or "").strip(),
        "reason": str(parsed.get("reason") or "").strip(),
    }


def answer_ai_question(question: str) -> str:
    return _chat(
        [
            {
                "role": "system",
                "content": (
                    "你是面向国内普通用户的 AI 信息差教程助手。回答必须中文、务实、"
                    "结构化，控制在 500-1500 字。涉及科学上网、账号、支付、版权、"
                    "隐私和平台政策时必须给风险提示，不提供规避监管或违法操作步骤。"
                ),
            },
            {"role": "user", "content": question},
        ],
        temperature=0.7,
    )


def generate_post_from_question(question: str, answer: str, topic_keyword: str = "") -> dict[str, Any]:
    content = _chat(
        [
            {
                "role": "system",
                "content": (
                    "你是本站编辑，把一个 AI 问答扩写成可发布的原创教程文章。"
                    "只返回 JSON，不要 Markdown 代码块。分类只能从：科学上网、海外 AI 账号、"
                    "海外 AI 工具使用、支付订阅、AI 创作工作流、案例玩法、风险避坑 中选择。"
                    "必须有风险提示和至少一个来源，来源可以使用本站问答作为内部来源。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "请返回字段：title, summary, category, tags, audience, prerequisites, "
                    "steps, faq, risk_notice, body_markdown, sources, status。status 固定 draft。"
                    "\nsource 格式：title,url,site_name,author,used_for,license_note,excerpt。"
                    "\n问题："
                    f"{question}\n\n回答：{answer}\n\n主题关键词：{topic_keyword}"
                ),
            },
        ],
        temperature=0.8,
    )
    parsed = _loads_json_object(content)
    parsed["status"] = "draft"
    parsed.setdefault("tags", [topic_keyword or "AI问答"])
    parsed.setdefault("sources", [])
    if not parsed["sources"]:
        public_url = os.getenv("PUBLIC_SITE_URL", "").strip().rstrip("/")
        source_url = f"{public_url}/qa" if public_url else "https://ai-info-gap.example.com/qa"
        parsed["sources"] = [
            {
                "title": "本站 AI 问答",
                "url": source_url,
                "site_name": "AI 信息差中转站",
                "author": "",
                "used_for": "由用户问题和 AI 回答扩写为教程草稿。",
                "license_note": "本站原创整理，发布前请人工审核。",
                "excerpt": question[:120],
            }
        ]
    return parsed
