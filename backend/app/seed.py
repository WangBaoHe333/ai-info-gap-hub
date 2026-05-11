from __future__ import annotations

from datetime import UTC, datetime, timedelta


def _published_at(days_ago: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat(timespec="seconds").replace("+00:00", "Z")


SEED_POSTS = [
    {
        "id": "seed-domestic-network-prep",
        "title": "使用海外 AI 前，先检查网络环境和账号安全",
        "slug": "network-prep-for-haiwai-ai",
        "summary": "面向新手的准备清单：先理解网络稳定性、账号注册、隐私保护和本地合规责任，再决定是否继续使用海外 AI 服务。",
        "category": "科学上网",
        "tags": ["网络准备", "账号安全", "新手入门"],
        "audience": "想了解海外 AI 服务但还没有系统准备的普通用户和创作者",
        "prerequisites": ["明确所在地区的法律和平台条款", "准备独立邮箱和密码管理器", "确认自己理解数据跨境和隐私风险"],
        "steps": [
            "先阅读目标 AI 服务的服务条款、支持地区和账号政策。",
            "为 AI 服务准备单独邮箱，不复用重要银行、工作或实名主邮箱。",
            "使用密码管理器生成强密码，并开启双重验证。",
            "不要上传身份证、合同、客户资料、商业机密等敏感内容做测试。",
            "保存官方帮助文档链接，遇到异常优先查官方说明，不轻信来路不明的配置包。"
        ],
        "faq": [
            {
                "question": "这篇文章会教具体绕过方法吗？",
                "answer": "不会。本站只提供通用准备、风险提示和来源导航，不承诺规避限制或绕过监管。"
            },
            {
                "question": "海外 AI 服务一定适合我吗？",
                "answer": "不一定。你需要同时考虑可用性、成本、数据合规、账号稳定性和替代方案。"
            }
        ],
        "risk_notice": "科学上网、跨境访问和使用国外服务可能受到所在地区法律法规、平台条款和网络环境限制影响。本文只做信息学习和风险提示，不构成法律、网络安全或规避监管建议。",
        "body_markdown": "## 先建立安全边界\n很多人第一次使用海外 AI 时只关注能不能打开网页，但更重要的是账号、隐私和合规边界。建议先把邮箱、密码、二次验证和数据使用习惯准备好。\n\n## 不要把工具可用性等同于合规性\n某个工具在技术上可以访问，不代表在你的所在地、行业或工作场景中一定可以使用。涉及公司数据、客户资料和未公开内容时，应优先使用经过组织批准的工具。",
        "sources": [
            {
                "title": "OpenAI Terms of Use",
                "url": "https://openai.com/policies/terms-of-use/",
                "site_name": "OpenAI",
                "author": "OpenAI",
                "used_for": "用于提示读者先阅读官方服务条款。",
                "license_note": "引用官方政策链接，不转载全文。",
                "excerpt": "Terms of Use"
            },
            {
                "title": "Google Account Help: 2-Step Verification",
                "url": "https://support.google.com/accounts/answer/185839",
                "site_name": "Google Help",
                "author": "Google",
                "used_for": "用于说明账号双重验证的安全实践。",
                "license_note": "引用官方帮助页面，不转载全文。",
                "excerpt": "2-Step Verification"
            }
        ],
        "status": "published",
        "published_at": _published_at(0),
    },
    {
        "id": "seed-overseas-chatgpt-account-basics",
        "title": "海外 AI 账号注册前要准备哪些基础资料",
        "slug": "haiwai-ai-account-basics",
        "summary": "用清单方式梳理邮箱、手机号、地区、支付、备份验证和账号恢复资料，减少后续无法登录或无法订阅的风险。",
        "category": "海外 AI 账号",
        "tags": ["ChatGPT", "账号注册", "双重验证"],
        "audience": "准备注册 ChatGPT、Claude、Gemini 等海外 AI 服务的国内用户",
        "prerequisites": ["可长期使用的邮箱", "密码管理器", "了解目标服务支持地区"],
        "steps": [
            "先确认目标服务的官方入口和支持地区，避免进入仿冒网站。",
            "使用独立邮箱注册，并保存恢复邮箱和二次验证方式。",
            "注册后立刻检查账号安全设置，记录恢复码。",
            "需要订阅时先阅读价格、退款、地区限制和税费说明。",
            "把账号恢复材料放入安全笔记，不要分享给第三方代注册人员。"
        ],
        "faq": [
            {
                "question": "可以找别人代注册吗？",
                "answer": "不建议。代注册会带来账号归属、隐私泄露和后续找回困难。"
            }
        ],
        "risk_notice": "海外 AI 账号的注册、订阅和使用受服务条款、支持地区和本地法律影响。本文只提供准备清单，不保证任何账号一定可注册、可订阅或长期可用。",
        "body_markdown": "## 账号资料要可长期维护\nAI 账号不是一次性工具。邮箱、手机号、二次验证和支付记录都可能用于后续安全验证，因此不要使用不可控的临时资料。\n\n## 优先官方入口\n搜索引擎广告和社交平台链接中可能存在仿冒页面。注册前应核对域名、证书和官方帮助文档。",
        "sources": [
            {
                "title": "OpenAI Help Center",
                "url": "https://help.openai.com/",
                "site_name": "OpenAI Help Center",
                "author": "OpenAI",
                "used_for": "作为账号和订阅问题的官方帮助入口。",
                "license_note": "仅引用入口链接，不转载内容。",
                "excerpt": "Help Center"
            }
        ],
        "status": "published",
        "published_at": _published_at(1),
    },
    {
        "id": "seed-overseas-ai-tool-comparison",
        "title": "ChatGPT、Claude、Gemini 适合哪些创作任务",
        "slug": "chatgpt-claude-gemini-creator-tasks",
        "summary": "从文案、长文、资料整理、图片理解和多语言改写几个任务维度，帮助创作者选择合适的海外 AI 工具。",
        "category": "海外 AI 工具使用",
        "tags": ["工具选择", "创作者", "工作流"],
        "audience": "想把海外 AI 工具接入日常内容生产的国内创作者",
        "prerequisites": ["已有一个可用 AI 账号", "准备 3 个真实创作任务作为测试样本"],
        "steps": [
            "列出自己每周最高频的 3 个内容任务。",
            "分别用不同 AI 工具完成同一任务，记录速度、准确性和修改次数。",
            "把输出结果按可发布程度打分，而不是只看回答是否很长。",
            "为每个工具固定一个主场景，避免频繁切换导致效率下降。"
        ],
        "faq": [
            {
                "question": "是否需要同时订阅多个工具？",
                "answer": "MVP 阶段不建议。先用真实任务测出一个主力工具，再决定是否补充其他工具。"
            }
        ],
        "risk_notice": "海外 AI 工具输出可能包含事实错误、过时信息或版权风险。发布前应人工核验，不要直接把生成内容用于医疗、法律、金融等高风险决策。",
        "body_markdown": "## 按任务选择工具\n创作者不需要追求每个模型都熟练。更有效的方式是把工具映射到任务：选题、脚本、长文、翻译、资料整理、图片理解分别测试。\n\n## 建立自己的评分表\n建议记录输入成本、输出质量、修改次数、最终是否发布。这个表比网上泛泛评测更适合你的账号。",
        "sources": [
            {
                "title": "Claude",
                "url": "https://claude.ai/",
                "site_name": "Anthropic",
                "author": "Anthropic",
                "used_for": "作为 Claude 工具入口来源。",
                "license_note": "仅引用工具入口。",
                "excerpt": "Claude"
            },
            {
                "title": "Gemini",
                "url": "https://gemini.google.com/",
                "site_name": "Google",
                "author": "Google",
                "used_for": "作为 Gemini 工具入口来源。",
                "license_note": "仅引用工具入口。",
                "excerpt": "Gemini"
            }
        ],
        "status": "published",
        "published_at": _published_at(2),
    },
    {
        "id": "seed-domestic-payment-subscription",
        "title": "订阅海外 AI 工具前先算清楚成本和退款风险",
        "slug": "haiwai-ai-subscription-cost-risk",
        "summary": "整理订阅前要确认的价格、账单周期、退款规则、税费、团队席位和取消路径，避免被自动续费拖累。",
        "category": "支付订阅",
        "tags": ["订阅", "退款", "成本控制"],
        "audience": "准备为海外 AI 工具付费的个人创作者和小团队",
        "prerequisites": ["明确预算上限", "了解支付方式风险", "准备订阅记录表"],
        "steps": [
            "订阅前截图价格、功能限制、账单周期和退款说明。",
            "优先选择月付测试，不在没验证价值前直接年付。",
            "建立订阅记录表，记录续费日期、用途和负责人。",
            "连续 30 天没有产生明确价值的工具，进入取消观察名单。",
            "取消订阅后保存确认邮件或页面截图。"
        ],
        "faq": [
            {
                "question": "为什么要记录取消路径？",
                "answer": "很多工具取消入口较深，提前记录能减少自动续费损失。"
            }
        ],
        "risk_notice": "跨境支付和订阅可能涉及汇率、税费、退款失败、账号地区限制和支付合规问题。本文只做成本管理建议，不构成金融或支付建议。",
        "body_markdown": "## 先月付验证\n很多 AI 工具初看很强，但真正嵌入工作流后才知道是否值得付费。建议先用一个月验证真实价值。\n\n## 订阅表比记忆可靠\n把工具名称、金额、续费日、用途、取消路径写进表格，是小团队控制成本最简单的方法。",
        "sources": [
            {
                "title": "OpenAI Pricing",
                "url": "https://openai.com/api/pricing/",
                "site_name": "OpenAI",
                "author": "OpenAI",
                "used_for": "作为订阅和价格核对入口示例。",
                "license_note": "引用官方价格页面，不转载价格表。",
                "excerpt": "Pricing"
            }
        ],
        "status": "published",
        "published_at": _published_at(3),
    },
    {
        "id": "seed-domestic-creator-workflow",
        "title": "把海外 AI 工具接入短视频选题工作流",
        "slug": "haiwai-ai-short-video-workflow",
        "summary": "用固定流程把热点、评论、脚本、封面和复盘串起来，让 AI 只负责加速，不替代创作者判断。",
        "category": "AI 创作工作流",
        "tags": ["短视频", "选题", "脚本"],
        "audience": "希望用 AI 提高内容生产效率的短视频创作者",
        "prerequisites": ["一个内容选题表", "近 10 条历史内容数据", "可用 AI 文本工具"],
        "steps": [
            "每天收集 5 条同行高互动内容，只记录主题和评论需求。",
            "让 AI 把评论问题整理成选题角度。",
            "用固定脚本结构生成初稿，再人工加入个人经验。",
            "发布后记录点击率、完播率、收藏率和评论质量。",
            "每周复盘，把有效提示词和结构沉淀成模板。"
        ],
        "faq": [
            {
                "question": "AI 写的脚本能直接发吗？",
                "answer": "不建议。直接发布容易同质化，也可能包含事实错误。应加入个人案例和核验过程。"
            }
        ],
        "risk_notice": "AI 生成内容可能与他人作品相似或包含错误。涉及引用、数据、观点和案例时，应核验来源并避免侵犯他人版权或误导用户。",
        "body_markdown": "## AI 是流程加速器\n成熟内容账号不会只靠 AI 生成，而是把 AI 放进选题、脚本、标题、封面和复盘环节，每一步都保留人工判断。\n\n## 复盘是核心\n如果不记录发布结果，提示词很难持续变好。建议每周把有效结构沉淀为模板。",
        "sources": [
            {
                "title": "YouTube Creator Academy",
                "url": "https://www.youtube.com/creators/",
                "site_name": "YouTube",
                "author": "YouTube",
                "used_for": "作为创作者内容运营学习入口。",
                "license_note": "仅引用入口链接。",
                "excerpt": "Creators"
            }
        ],
        "status": "published",
        "published_at": _published_at(4),
    },
    {
        "id": "seed-overseas-case-study-reading",
        "title": "怎么读海外 AI 案例，提炼成国内可执行选题",
        "slug": "read-haiwai-ai-case-to-domestic-topic",
        "summary": "把海外产品案例拆成用户、场景、工具、结果和限制，再转换成适合国内创作者的选题。",
        "category": "案例玩法",
        "tags": ["案例拆解", "选题", "信息差"],
        "audience": "做 AI 资讯、工具测评、商业案例拆解的创作者",
        "prerequisites": ["一个海外案例链接", "目标平台受众画像", "选题评分表"],
        "steps": [
            "先确认案例是否来自官方、媒体还是个人经验。",
            "提取案例中的用户、任务、工具、成本、结果和限制。",
            "判断哪些条件在国内不成立，不要照搬结论。",
            "改写成三个国内读者能执行的选题。",
            "发布时标注原案例来源和自己的改写视角。"
        ],
        "faq": [
            {
                "question": "能不能直接翻译海外文章？",
                "answer": "不建议。更稳妥的方式是摘要、评论、短引用和来源链接，并加入自己的分析。"
            }
        ],
        "risk_notice": "海外案例可能存在语境差异、商业宣传和数据不完整。改写为国内内容时应明确限制，不应夸大收益或复制原文表达。",
        "body_markdown": "## 不要把翻译当原创\n真正有价值的信息差不是翻译，而是把海外案例放进本地场景重新判断：谁能用、怎么做、风险在哪。\n\n## 输出自己的判断\n帖子应说明你认为什么值得借鉴，什么不能直接套用。",
        "sources": [
            {
                "title": "The Batch",
                "url": "https://www.deeplearning.ai/the-batch/",
                "site_name": "DeepLearning.AI",
                "author": "DeepLearning.AI",
                "used_for": "作为 AI 案例和趋势观察来源之一。",
                "license_note": "仅引用来源入口，不转载文章。",
                "excerpt": "The Batch"
            }
        ],
        "status": "published",
        "published_at": _published_at(5),
    },
    {
        "id": "seed-domestic-risk-avoidance",
        "title": "使用 AI 资料和外站文章时，先避开版权和事实风险",
        "slug": "ai-content-copyright-fact-check-risk",
        "summary": "整理创作者常见风险：整篇搬运、未标注来源、未经核验的数据、过时教程和 AI 幻觉。",
        "category": "风险避坑",
        "tags": ["版权", "事实核验", "引用"],
        "audience": "需要长期做 AI 教程、资讯和资源整理的创作者",
        "prerequisites": ["准备来源记录表", "了解短引用和摘要的区别"],
        "steps": [
            "每次引用外站内容都记录标题、URL、作者、站点和访问日期。",
            "只摘录必要短句用于评论和说明，不把原文作为本站主体。",
            "用自己的结构重写摘要、步骤和判断。",
            "涉及价格、政策、模型能力时回到官方来源核验。",
            "无法确认授权的内容，不做全文转载。"
        ],
        "faq": [
            {
                "question": "标注来源就能全文搬运吗？",
                "answer": "通常不能。标注来源不等于获得转载授权。"
            }
        ],
        "risk_notice": "版权和合理使用判断依赖具体场景。本文是内容运营风险提示，不构成法律意见；大规模转载或商业使用前应确认授权或咨询专业人士。",
        "body_markdown": "## 标注来源不是授权\n引用外站内容时，来源链接是必要但不充分的条件。本站默认采用摘要、短引用、评论和来源链接的方式。\n\n## 建立来源表\n来源表能帮助后续更新、撤稿和核验，也能让读者知道每个判断来自哪里。",
        "sources": [
            {
                "title": "U.S. Copyright Office Fair Use FAQ",
                "url": "https://www.copyright.gov/help/faq/faq-fairuse.html",
                "site_name": "U.S. Copyright Office",
                "author": "U.S. Copyright Office",
                "used_for": "用于说明合理使用和引用没有固定字数规则。",
                "license_note": "引用官方说明页面，不转载全文。",
                "excerpt": "fair use"
            }
        ],
        "status": "published",
        "published_at": _published_at(6),
    },
    {
        "id": "seed-overseas-resource-navigation",
        "title": "海外 AI 学习资源如何做成自己的资料库",
        "slug": "haiwai-ai-resource-library",
        "summary": "把官方文档、帮助中心、博客、课程和案例库分层收藏，形成可复用的 AI 信息差资料库。",
        "category": "海外 AI 工具使用",
        "tags": ["资料库", "学习资源", "来源管理"],
        "audience": "需要持续追踪海外 AI 信息的国内内容运营者和学习者",
        "prerequisites": ["一个收藏工具或表格", "固定标签体系", "每周整理时间"],
        "steps": [
            "把资源分成官方文档、帮助中心、产品博客、课程、案例五类。",
            "每个资源记录用途，而不是只保存链接。",
            "用标签标注适合的内容方向，如账号、支付、工具教程、案例。",
            "每周清理失效链接和过时说明。",
            "发布帖子时从资料库引用来源，而不是临时搜索。"
        ],
        "faq": [
            {
                "question": "资料库要不要公开？",
                "answer": "早期建议先内部使用，等来源质量稳定后再整理成公开工具使用索引。"
            }
        ],
        "risk_notice": "外部资源可能更新、下线或改变条款。使用前应回到原站确认最新信息，本站整理不保证永久准确。",
        "body_markdown": "## 资料库的价值在于复用\n只收藏链接很快会变成信息垃圾。给每条资源写清用途，才能在写帖子时快速调用。\n\n## 官方来源优先\n涉及账号、价格、政策和功能时，官方文档比二手教程更可靠。",
        "sources": [
            {
                "title": "OpenAI Docs",
                "url": "https://platform.openai.com/docs",
                "site_name": "OpenAI Platform",
                "author": "OpenAI",
                "used_for": "作为官方文档来源示例。",
                "license_note": "仅引用文档入口。",
                "excerpt": "Docs"
            }
        ],
        "status": "published",
        "published_at": _published_at(7),
    },
]
