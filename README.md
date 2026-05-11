# AI 信息差中转站

面向国内用户的 AI 信息差教程站，首页地址：<http://39.104.27.129>

项目聚焦“自己找教程、自己实操”，提供科学上网风险提示、海外 AI 账号、海外 AI 工具使用、支付订阅、AI 创作工作流、案例玩法、风险避坑等教程内容。前台用于阅读、搜索、分页和 AI 问答；后台独立管理帖子、来源、免责声明、问答沉淀和访问统计。

## 功能

- 前台首页：7 步教程目录、搜索入口、全站免责声明。
- 帖子列表：分类筛选、关键词搜索、分页、固定页内滚动。
- 帖子详情：教程步骤、准备条件、FAQ、风险提示、参考来源和版权引用说明。
- AI 问答：内置 DeepSeek 模型能力，回答 AI 工具、账号、支付、工作流和风险避坑相关问题。
- 后台管理：管理员登录、帖子新建/编辑/发布/归档、URL 导入草稿、问答扩写成草稿、访问统计。
- 合规默认：外站内容只做摘要、短引用和来源链接，不默认整篇搬运。

## 技术栈

- 前端：Vite + React + TypeScript
- 后端：FastAPI + SQLite
- Markdown：react-markdown + remark-gfm + rehype-sanitize
- AI 问答：DeepSeek Chat Completions API

## 本地运行

```bash
npm install
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`，填入自己的管理员账号、强密码、随机密钥和 DeepSeek API Key：

```env
ADMIN_USERNAME=your-admin-name
ADMIN_PASSWORD=
APP_SECRET_KEY=
CORS_ORIGINS=http://localhost:5173
DEEPSEEK_API_KEY=
```

启动后端：

```bash
python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

启动前端：

```bash
npm run dev
```

访问：

- 前台：<http://127.0.0.1:5173>
- 后台：<http://127.0.0.1:5173/admin>

## 构建与测试

```bash
npm run build
npm run test:api
```

## 部署建议

前端构建为静态文件：

```bash
npm run build
```

后端使用 uvicorn 或 systemd 常驻运行，Nginx 建议：

- `/api/*` 反代到 FastAPI。
- 其他路径返回前端 `dist/index.html`。
- SSE 问答接口建议关闭代理缓存：

```nginx
proxy_buffering off;
proxy_cache off;
proxy_read_timeout 120s;
```

## 安全说明

请不要提交以下内容：

- `.env`
- 生产数据库或本地 SQLite 数据库
- DeepSeek API Key
- 管理员密码
- `APP_SECRET_KEY`
- 服务器私钥、证书、部署凭据
- `dist/`、`node_modules/` 等生成目录

本仓库只提供 `.env.example` 模板。真实配置必须通过服务器环境变量或服务器本地 `.env` 管理。

## 免责声明

本站内容仅供信息学习和资料整理，不构成法律、金融、网络安全、医疗、投资或规避监管建议。涉及科学上网、账号注册、支付订阅、平台政策和数据安全的内容，请自行确认所在地法律法规、平台条款和组织政策。外部来源仅作摘要、短引用和出处标注，版权归原作者或原站所有。
