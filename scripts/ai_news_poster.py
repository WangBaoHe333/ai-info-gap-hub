#!/usr/bin/env python3
"""AI新闻自动采集 - 从 HackerNews + Techmeme 采集AI新闻，用 DeepSeek V4 Pro 生成中文文章，存为草稿"""

import urllib.request
import urllib.error
import urllib.parse
import json
import os
import sys
import time
import logging
import xml.etree.ElementTree as ET
from datetime import datetime

# ==== 从 .env 加载配置 ====
ENV_FILE = '/opt/ai-info-gap-hub/.env'


def _load_env():
    """从 .env 文件加载环境变量（不覆盖已设的环境变量）"""
    if not os.path.isfile(ENV_FILE):
        return
    with open(ENV_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_env()

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')

if not DEEPSEEK_API_KEY:
    raise RuntimeError('DEEPSEEK_API_KEY not set in .env')
if not ADMIN_PASSWORD:
    raise RuntimeError('ADMIN_PASSWORD not set in .env')

DEEPSEEK_API = 'https://api.deepseek.com/chat/completions'
ADMIN_API = 'http://127.0.0.1:8008/api/admin'
LOG_FILE = '/opt/scripts/ai_news_poster.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)


def fetch_hackernews():
    """从 HN Algolia API 搜索 AI 相关热门文章"""
    items = []
    queries = ['chatgpt', 'openai', 'claude', 'gemini', 'llm', 'ai+copilot',
               'anthropic', 'gpt', 'deepseek', 'ai+coding']
    for q in queries:
        try:
            url = ('https://hn.algolia.com/api/v1/search_by_date?query=%s'
                   '&tags=story&hitsPerPage=8&numericFilters=points>10') % urllib.parse.quote(q)
            req = urllib.request.Request(url, headers={'User-Agent': 'NewsBot/1.0'})
            resp = urllib.request.urlopen(req, timeout=15)
            data = json.loads(resp.read())
            for hit in data.get('hits', []):
                items.append({
                    'title': hit.get('title', ''),
                    'url': hit.get('url', 'https://news.ycombinator.com/item?id=%s' % hit.get('objectID', '')),
                    'date': hit.get('created_at', '')[:10],
                    'source': 'HackerNews',
                    'score': hit.get('points', 0)
                })
            time.sleep(0.3)
        except Exception as e:
            log.error('  HN search [%s] error: %s', q, e)
    seen = set()
    uniq = []
    for it in items:
        t = it['title'].strip().lower()
        if t not in seen:
            seen.add(t)
            uniq.append(it)
    uniq.sort(key=lambda x: x.get('score', 0), reverse=True)
    log.info('  HN: %d AI-related stories (from %d raw)', len(uniq), len(items))
    return uniq


def fetch_techmeme():
    items = []
    try:
        req = urllib.request.Request(
            'https://www.techmeme.com/feed.xml',
            headers={'User-Agent': 'Mozilla/5.0 (compatible; NewsBot/1.0)'}
        )
        resp = urllib.request.urlopen(req, timeout=15)
        data = resp.read().decode('utf-8', errors='ignore')
        root = ET.fromstring(data)
        ai_kw = ['ai', 'chatgpt', 'openai', 'claude', 'gemini', 'gpt', 'llm',
                 'anthropic', 'copilot', 'cursor', 'mistral', 'deepseek', 'perplexity',
                 'agent', 'coder', 'llama', 'sora', 'midjourney']
        for item in root.iter('item'):
            title = item.findtext('title', '')
            if any(k in title.lower() for k in ai_kw):
                items.append({
                    'title': title,
                    'url': item.findtext('link', ''),
                    'date': item.findtext('pubDate', ''),
                    'source': 'Techmeme'
                })
        log.info('  Techmeme: %d AI-related', len(items))
    except Exception as e:
        log.error('  Techmeme error: %s', e)
    return items


def call_deepseek(prompt):
    payload = json.dumps({
        'model': 'deepseek-v4-pro',
        'messages': [
            {
                'role': 'system',
                'content': '你是一个专业的AI行业编辑，擅长将海外AI新闻用通俗易懂的中文总结给国内读者。文章风格：信息密度高、不说废话、有数据有观点、带"人话总结"。输出JSON时字符串内的双引号必须用反斜杠转义。只输出JSON对象，不要包含```json```标记或任何说明文字。'
            },
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.7,
        'max_tokens': 8192
    }).encode('utf-8')

    req = urllib.request.Request(DEEPSEEK_API, data=payload, headers={
        'Authorization': 'Bearer ' + DEEPSEEK_API_KEY,
        'Content-Type': 'application/json'
    })
    try:
        resp = urllib.request.urlopen(req, timeout=180)
        result = json.loads(resp.read())
        msg = result['choices'][0]['message']
        content = msg.get('content', '') or msg.get('reasoning_content', '')
        usage = result.get('usage', {})
        log.info('  DeepSeek: %d tokens (in %d + out %d)',
                 usage.get('total_tokens', 0),
                 usage.get('prompt_tokens', 0),
                 usage.get('completion_tokens', 0))
        return content
    except Exception as e:
        log.error('  DeepSeek error: %s', e)
        try:
            log.error('  Response body: %s', e.read()[:300])
        except Exception:
            pass
        return None


def login_admin():
    data = json.dumps({'username': ADMIN_USERNAME, 'password': ADMIN_PASSWORD}).encode()
    req = urllib.request.Request(
        ADMIN_API + '/login', data=data,
        headers={'Content-Type': 'application/json'}
    )
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())['token']


def create_draft(token, post_data):
    payload = json.dumps(post_data, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        ADMIN_API + '/posts', data=payload,
        headers={
            'Authorization': 'Bearer ' + token,
            'Content-Type': 'application/json; charset=utf-8'
        },
        method='POST'
    )
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())


def main():
    log.info('===== AI News Poster Start =====')

    # Step 1: 采集新闻
    hn_news = fetch_hackernews()
    tm_news = fetch_techmeme()

    all_news = hn_news + tm_news
    seen = set()
    unique_news = []
    for n in all_news:
        t = n['title'].strip().lower()
        if t not in seen:
            seen.add(t)
            unique_news.append(n)

    log.info('Total unique AI news: %d', len(unique_news))

    if len(unique_news) < 3:
        log.warning('Not enough news (%d), aborting', len(unique_news))
        return

    # Step 2: 整理新闻列表
    today = datetime.now().strftime('%Y-%m-%d')
    news_text = '\n'.join([
        '%d. [%s](%s) | 来源: %s' % (i+1, n['title'], n['url'], n['source'])
        for i, n in enumerate(unique_news[:30])
    ])

    # Step 3: 调用 DeepSeek 生成文章
    prompt = ('今天是%s，以下是今天海外AI行业的最新新闻：\n\n%s\n\n'
              '请从以上新闻中选出1-3条最重要的，写一篇面向国内AI用户的新闻简报。\n\n'
              '按以下JSON结构输出（必须合法JSON，字段完整。字符串内双引号用反斜杠转义）：\n'
              '{\n'
              '  "title": "中文标题，吸引人但不标题党",\n'
              '  "slug": "ai-news-%s-xxx",\n'
              '  "summary": "50-100字中文摘要",\n'
              '  "category": "海外 AI 工具使用",\n'
              '  "tags": ["行业动态", "产品名"],\n'
              '  "audience": "已经在使用或关注海外AI工具的国内用户",\n'
              '  "prerequisites": ["对ChatGPT、Claude有基本了解"],\n'
              '  "steps": ["可操作步骤1", "步骤2", "步骤3", "步骤4"],\n'
              '  "faq": [{"question": "问题", "answer": "回答"}],\n'
              '  "risk_notice": "本文信息基于外部新闻源整理，数据和时效性以原始来源为准。仅供参考。",\n'
              '  "body_markdown": "完整Markdown正文，1500-2000字。结构：## 人话总结\\n...\\n\\n## 发生了什么\\n...\\n\\n## 详细解读\\n...\\n\\n## 对你的影响\\n...\\n\\n## 现在该做什么\\n...",\n'
              '  "sources": [{"title": "原文标题", "url": "原文URL", "site_name": "来源", "used_for": "参考了什么", "excerpt": "摘录", "license_note": "仅做新闻摘要引用"}],\n'
              '  "status": "published"\n'
              '}\n\n'
              '要求：\n'
              '- body_markdown 信息密度高、语言通俗口语化、有具体数据\n'
              '- 正文可用表格展示对比数据\n'
              '- steps 要具体可操作\n'
              '- sources 的 title/url 必须引用上面新闻列表中的真实新闻\n'
              '- status 必须是 "published"，直接发布\n'
              '- 只输出JSON对象，不要包含任何额外文字') % (today, news_text, today.replace('-', ''))

    log.info('Calling DeepSeek V4 Pro...')
    content = call_deepseek(prompt)

    if not content:
        log.error('DeepSeek API failed, exiting')
        return

    # Step 4: 解析 JSON
    log.info('Parsing response...')
    try:
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            json_str = content[json_start:json_end]
            post_data = json.loads(json_str)
        else:
            log.error('No JSON found in response')
            log.error('Raw (first 800): %s', content[:800])
            return
    except json.JSONDecodeError as e:
        log.error('JSON error: %s', e)
        log.error('Raw (first 800): %s', content[:800])
        return

    # Step 5: 发布
    log.info('Posting draft...')
    try:
        token = login_admin()
        result = create_draft(token, post_data)
        log.info('SUCCESS: [%s] %s', result.get('status', '?'), result.get('title', '')[:80])
    except Exception as e:
        log.error('Post failed: %s', e)
        return

    log.info('===== AI News Poster End =====')


if __name__ == '__main__':
    main()
