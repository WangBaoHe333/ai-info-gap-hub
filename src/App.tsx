import {
  AlertTriangle,
  Archive,
  BookOpen,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Edit3,
  ExternalLink,
  FileDown,
  LayoutDashboard,
  LogOut,
  MessageCircle,
  Plus,
  Search,
  Send,
  ShieldAlert,
  Sparkles,
  X
} from "lucide-react";
import { Children, FormEvent, isValidElement, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import rehypeSanitize from "rehype-sanitize";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  clearAdminToken,
  askQaQuestionStream,
  createAdminPost,
  fetchAdminPosts,
  fetchAdminQaQuestions,
  fetchPopularQuestions,
  fetchPost,
  fetchPostNav,
  fetchPosts,
  fetchStats,
  getAdminToken,
  importUrlDraft,
  login,
  promoteQaQuestion,
  recordVisit,
  updateAdminPost,
  updatePostStatus
} from "./api";
import type { PostNavItem, StatsData } from "./api";
import type { FAQItem, PaginatedPosts, Post, PostFilters, PostPayload, PostSource, PostStatus, QaQuestion } from "./types";

type Route =
  | { name: "home" }
  | { name: "list" }
  | { name: "detail"; slug: string }
  | { name: "admin" };

type AdminStatus = PostStatus | "all";
type AdminTab = "posts" | "qa" | "stats";
type TocItem = { id: string; title: string };

const CATEGORY_ORDER = [
  "科学上网",
  "海外 AI 账号",
  "海外 AI 工具使用",
  "支付订阅",
  "AI 创作工作流",
  "案例玩法",
  "风险避坑"
];

const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  "科学上网": "了解网络访问的基础准备，迈出第一步",
  "海外 AI 账号": "手把手教你注册第一个海外AI工具",
  "海外 AI 工具使用": "认识主流AI工具，掌握提示词技巧",
  "支付订阅": "解决付费难题，安全便捷地开通订阅",
  "AI 创作工作流": "多工具配合，搭建高效内容生产线",
  "案例玩法": "真实案例，看看别人怎么用AI提效和创造",
  "风险避坑": "账号安全、隐私保护、合规使用"
};

const DEFAULT_PAGE_SIZE = 10;
const EMPTY_POST: PostPayload = {
  title: "",
  slug: "",
  summary: "",
  category: "科学上网",
  tags: [],
  audience: "",
  prerequisites: [],
  steps: [],
  faq: [],
  risk_notice: "",
  body_markdown: "",
  sources: [],
  status: "draft"
};

function routeFromLocation(): Route {
  const path = window.location.pathname;
  if (path === "/admin") return { name: "admin" };
  if (path === "/posts") return { name: "list" };
  const detailMatch = path.match(/^\/posts\/([^/]+)$/);
  if (detailMatch) return { name: "detail", slug: decodeURIComponent(detailMatch[1]) };
  return { name: "home" };
}

function useDocumentTitle(title: string) {
  useEffect(() => {
    const prev = document.title;
    document.title = title ? `${title} - AI 信息差中转站` : "AI 信息差中转站";
    return () => {
      document.title = prev;
    };
  }, [title]);
}

function useRoute(): [Route, (path: string) => void] {
  const [route, setRoute] = useState<Route>(() => routeFromLocation());
  useEffect(() => {
    const onPopState = () => setRoute(routeFromLocation());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);
  const navigate = useCallback((path: string) => {
    window.history.pushState({}, "", path);
    setRoute(routeFromLocation());
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);
  return [route, navigate];
}

function formatDate(value: string | null): string {
  if (!value) return "未发布";
  return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(value));
}

function listToText(value: string[]): string {
  return value.join("\n");
}

function textToList(value: string): string[] {
  return value
    .split(/\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function faqToText(value: FAQItem[]): string {
  return value.map((item) => `${item.question}｜${item.answer}`).join("\n");
}

function textToFAQ(value: string): FAQItem[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [question, ...rest] = line.split("｜");
      return { question: question.trim(), answer: rest.join("｜").trim() };
    })
    .filter((item) => item.question || item.answer);
}

function sourcesToText(value: PostSource[]): string {
  return value
    .map((item) => [item.title, item.url, item.site_name, item.author, item.used_for, item.license_note, item.excerpt].join(" | "))
    .join("\n");
}

function textToSources(value: string): PostSource[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [title = "", url = "", site_name = "", author = "", used_for = "", license_note = "", excerpt = ""] = line
        .split("|")
        .map((part) => part.trim());
      return { title, url, site_name, author, used_for, license_note, excerpt };
    })
    .filter((item) => item.title && item.url);
}

function baseHeadingId(value: string): string {
  return (
    value
      .trim()
      .replace(/[`*_~[\]()#]/g, "")
      .replace(/\s+/g, "-")
      .toLowerCase() || "section"
  );
}

function uniqueHeadingId(value: string, counts: Map<string, number>): string {
  const base = baseHeadingId(value);
  const count = counts.get(base) ?? 0;
  counts.set(base, count + 1);
  return count ? `${base}-${count + 1}` : base;
}

function extractToc(markdown: string): TocItem[] {
  const counts = new Map<string, number>();
  return markdown
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith("## "))
    .map((line) => {
      const title = line.slice(3).trim();
      return { id: uniqueHeadingId(title, counts), title };
    });
}

function nodeToText(node: ReactNode): string {
  return Children.toArray(node)
    .map((child) => {
      if (typeof child === "string" || typeof child === "number") return String(child);
      if (isValidElement<{ children?: ReactNode }>(child)) return nodeToText(child.props.children);
      return "";
    })
    .join("");
}

function useQueryFilters(route: Route): PostFilters {
  return useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return {
      page: Number(params.get("page") || "1"),
      page_size: DEFAULT_PAGE_SIZE,
      category: params.get("category") || undefined,
      tag: params.get("tag") || undefined,
      q: params.get("q") || undefined
    };
  }, [route]);
}

function DisclaimerFooter() {
  return (
    <footer className="site-footer">
      <strong>免责声明</strong>
      <span>
        本站内容仅供信息学习和资料整理，不构成法律、金融、网络安全、医疗、投资或规避监管建议。外部来源仅作摘要、短引用和出处标注，版权归原作者或原站所有。
      </span>
    </footer>
  );
}

function PublicShell({ children, onNavigate }: { children: React.ReactNode; onNavigate: (path: string) => void }) {
  return (
    <div className="public-shell">
      <header className="site-header">
        <button className="brand" onClick={() => onNavigate("/")} type="button">
          <span className="brand-mark">
            <Sparkles size={18} />
          </span>
          <span>AI 信息差中转站</span>
        </button>
        <nav aria-label="站点导航">
          <button onClick={() => onNavigate("/")} type="button">
            首页
          </button>
          <button onClick={() => onNavigate("/posts")} type="button">
            帖子
          </button>
          <button onClick={() => onNavigate("/posts?category=%E6%B5%B7%E5%A4%96%20AI%20%E5%B7%A5%E5%85%B7%E4%BD%BF%E7%94%A8")} type="button">
            工具教程
          </button>
        </nav>
      </header>
      {children}
      <DisclaimerFooter />
      <FloatingQaButton />
    </div>
  );
}

function SearchPanel({ initialQuery = "", onSearch }: { initialQuery?: string; onSearch: (query: string) => void }) {
  const [value, setValue] = useState(initialQuery);
  return (
    <form
      className="search-panel"
      onSubmit={(event) => {
        event.preventDefault();
        onSearch(value.trim());
      }}
    >
      <Search size={18} />
      <input value={value} onChange={(event) => setValue(event.target.value)} placeholder="搜索科学上网、海外 AI、支付订阅、案例玩法" />
      <button type="submit">搜索</button>
    </form>
  );
}

function HomePage({
  posts,
  onNavigate
}: {
  posts: PaginatedPosts | null;
  onNavigate: (path: string) => void;
}) {
  useDocumentTitle("");

  return (
    <main className="home-page">
      <section className="hero-panel">
        <div>
          <h1>帮助国内用户打破 AI 信息差</h1>
          <p>7 步系统教程，从网络准备到账号安全，手把手带你用好海外 AI 工具。</p>
          <SearchPanel onSearch={(query) => onNavigate(`/posts${query ? `?q=${encodeURIComponent(query)}` : ""}`)} />
        </div>
      </section>

      <StepCards posts={posts?.items ?? []} onNavigate={onNavigate} />
    </main>
  );
}

function StepCards({ posts, onNavigate }: { posts: Post[]; onNavigate: (path: string) => void }) {
  return (
    <section className="step-cards-panel" aria-label="课程目录">
      <div className="step-cards">
        {CATEGORY_ORDER.map((category, index) => {
          const categoryPosts = posts.filter((post) => post.category === category);
          const latest = categoryPosts[0];

          return (
            <button
              key={category}
              className="step-card"
              onClick={() => onNavigate(`/posts?category=${encodeURIComponent(category)}`)}
              type="button"
            >
              <div className="step-card-index">
                <span>{index + 1}</span>
              </div>
              <div className="step-card-body">
                <h3>{category}</h3>
                {latest ? <p>{latest.title}</p> : <p className="step-card-empty">暂无内容</p>}
                {categoryPosts.length > 1 ? <small>还有 {categoryPosts.length - 1} 篇相关内容</small> : null}
              </div>
              <ChevronRight className="step-card-arrow" />
            </button>
          );
        })}
      </div>
    </section>
  );
}

function PostListItem({
  post,
  onOpen,
  showCategory = false
}: {
  post: Post;
  onOpen: () => void;
  showCategory?: boolean;
}) {
  return (
    <button className="list-card" onClick={onOpen} type="button">
      {showCategory ? <span className="list-card-category">{post.category}</span> : null}
      <strong>{post.title}</strong>
      <p>{post.summary}</p>
      <time>{formatDate(post.published_at)}</time>
    </button>
  );
}

function ListPage({
  filters,
  onNavigate
}: {
  filters: PostFilters;
  onNavigate: (path: string) => void;
}) {
  const [result, setResult] = useState<PaginatedPosts | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPosts({ ...filters, page_size: 10 })
      .then((data) => {
        setResult(data);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, [filters.page, filters.category, filters.tag, filters.q]);

  const isSearching = !!filters.q;
  const currentCategory = filters.category;
  const categoryDesc = currentCategory ? CATEGORY_DESCRIPTIONS[currentCategory] ?? "" : "";
  const pageTitle = filters.q ? `搜索：${filters.q}` : currentCategory || "全部帖子";
  useDocumentTitle(pageTitle);

  return (
    <main className="list-page">
      {currentCategory && !isSearching ? (
        <div className="list-header">
          <button className="back-button" onClick={() => onNavigate("/")} type="button">
            <ChevronLeft size={16} />
            返回首页
          </button>
          <h1>{currentCategory}</h1>
          <p>{categoryDesc}</p>
        </div>
      ) : null}

      {isSearching ? (
        <div className="list-header">
          <h1>搜索结果：「{filters.q}」</h1>
          <p>{result?.total ?? 0} 条结果</p>
        </div>
      ) : !currentCategory ? (
        <div className="list-header">
          <h1>全部帖子</h1>
        </div>
      ) : null}

      <SearchPanel
        initialQuery={filters.q ?? ""}
        onSearch={(query) =>
          onNavigate(
            query
              ? `/posts?q=${encodeURIComponent(query)}`
              : currentCategory
                ? `/posts?category=${encodeURIComponent(currentCategory)}`
                : "/posts"
          )
        }
      />

      {error ? <EmptyState title="读取失败" body={error} /> : null}

      <div className="list-cards">
        {result?.items.map((post) => (
          <PostListItem
            key={post.id}
            post={post}
            onOpen={() => onNavigate(`/posts/${post.slug}`)}
            showCategory={!currentCategory || isSearching}
          />
        ))}
        {result && result.items.length === 0 ? <EmptyState title="没有找到帖子" body="换个分类或搜索词试试。" /> : null}
      </div>

      {result ? (
        <Pagination
          result={result}
          onNavigate={(page) => {
            const params = new URLSearchParams();
            params.set("page", String(page));
            params.set("page_size", "10");
            if (currentCategory) params.set("category", currentCategory);
            if (filters.q) params.set("q", filters.q);
            onNavigate(`/posts?${params.toString()}`);
          }}
        />
      ) : null}

      <div className="category-pills">
        <button className={!currentCategory && !filters.q ? "selected" : ""} onClick={() => onNavigate("/posts")} type="button">
          全部
        </button>
        {CATEGORY_ORDER.map((cat) => (
          <button
            key={cat}
            className={currentCategory === cat && !filters.q ? "selected" : ""}
            onClick={() => onNavigate(`/posts?category=${encodeURIComponent(cat)}`)}
            type="button"
          >
            {cat}
          </button>
        ))}
      </div>
    </main>
  );
}

function Pagination({ result, onNavigate }: { result: PaginatedPosts; onNavigate: (page: number) => void }) {
  return (
    <div className="pagination">
      <button disabled={result.page <= 1} onClick={() => onNavigate(result.page - 1)} type="button">
        <ChevronLeft size={16} />
        上一页
      </button>
      <span>
        {result.page} / {result.total_pages}
      </span>
      <button disabled={result.page >= result.total_pages} onClick={() => onNavigate(result.page + 1)} type="button">
        下一页
        <ChevronRight size={16} />
      </button>
    </div>
  );
}

function DetailPage({ slug, onNavigate }: { slug: string; onNavigate: (path: string) => void }) {
  const [post, setPost] = useState<Post | null>(null);
  const [nav, setNav] = useState<{ prev: PostNavItem | null; next: PostNavItem | null }>({ prev: null, next: null });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchPost(slug), fetchPostNav(slug)])
      .then(([postData, navData]) => {
        setPost(postData);
        setNav(navData);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, [slug]);

  useDocumentTitle(post?.title ?? "");

  if (error) {
    return (
      <main className="detail-page">
        <EmptyState title="帖子不存在" body={error}>
          <button className="primary-button" onClick={() => onNavigate("/")} type="button">
            返回首页
          </button>
        </EmptyState>
      </main>
    );
  }
  if (!post) return <main className="detail-page"><EmptyState title="正在读取帖子" body="正在加载教程步骤、风险提示和来源。" /></main>;

  const toc = extractToc(post.body_markdown);

  return (
    <main className="detail-page">
      <div className="detail-back-actions" aria-label="返回导航">
        <button className="back-button primary" onClick={() => onNavigate("/")} type="button">
          <ChevronLeft size={16} />
          返回首页
        </button>
        <button className="back-button subtle" onClick={() => onNavigate("/posts")} type="button">
          全部帖子
        </button>
      </div>
      {post.category === "科学上网" ? <ScienceNotice /> : null}
      <div className="detail-workspace">
        <article className="article-shell">
          <header className="article-head">
            <div className="post-meta">
              <span>{post.category}</span>
              <span>{formatDate(post.published_at)}</span>
            </div>
            <h1>{post.title}</h1>
            <p>{post.summary}</p>
            <div className="post-tags">
              {post.tags.map((tag) => (
                <span key={tag}>{tag}</span>
              ))}
            </div>
          </header>

          <section className="disclaimer-card">
            <ShieldAlert size={18} />
            <div>
              <strong>内容免责声明</strong>
              <p>本文仅供信息学习，不构成法律、网络安全、金融或规避监管建议。外部内容仅作短引用和来源标注，版权归原作者或原站所有。</p>
            </div>
          </section>

          <div className="article-grid">
            <section>
              <h2>适合人群</h2>
              <p>{post.audience}</p>
            </section>
            <section>
              <h2>风险提示</h2>
              <p>{post.risk_notice}</p>
            </section>
          </div>

          <section>
            <h2>准备条件</h2>
            <ul className="check-list">
              {post.prerequisites.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>

          <section>
            <h2>操作步骤</h2>
            <ol className="steps-list">
              {post.steps.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ol>
          </section>

          <MarkdownBlock value={post.body_markdown} />

          {post.faq.length ? (
            <section>
              <h2>常见问题</h2>
              <div className="faq-list">
                {post.faq.map((item) => (
                  <div key={`${item.question}-${item.answer}`}>
                    <strong>{item.question}</strong>
                    <p>{item.answer}</p>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          <section>
            <h2>参考来源</h2>
            <div className="source-list">
              {post.sources.map((source) => (
                <a href={source.url} key={`${source.title}-${source.url}`} target="_blank" rel="noreferrer" className="source-card">
                  <strong>
                    {source.title}
                    <ExternalLink size={14} />
                  </strong>
                  <span>{source.site_name || source.author || source.url}</span>
                  {source.excerpt ? <em>短引用：{source.excerpt}</em> : null}
                  {source.used_for ? <small>用途：{source.used_for}</small> : null}
                  {source.license_note ? <small>版权说明：{source.license_note}</small> : null}
                </a>
              ))}
            </div>
          </section>
        </article>
        <PrevNextNav prev={nav.prev} next={nav.next} onNavigate={onNavigate} />
        <ArticleToc items={toc} />
      </div>
    </main>
  );
}

function PrevNextNav({
  prev,
  next,
  onNavigate
}: {
  prev: PostNavItem | null;
  next: PostNavItem | null;
  onNavigate: (path: string) => void;
}) {
  if (!prev && !next) return null;

  return (
    <nav className="prev-next-nav" aria-label="文章导航">
      {prev ? (
        <button className="prev-next-btn" onClick={() => onNavigate(`/posts/${prev.slug}`)} type="button">
          <span>上一步</span>
          <strong>{prev.title}</strong>
        </button>
      ) : (
        <div aria-hidden="true" />
      )}
      {next ? (
        <button className="prev-next-btn next" onClick={() => onNavigate(`/posts/${next.slug}`)} type="button">
          <span>下一步</span>
          <strong>{next.title}</strong>
        </button>
      ) : (
        <div aria-hidden="true" />
      )}
    </nav>
  );
}

function MarkdownBlock({ value }: { value: string }) {
  const headingCounts = new Map<string, number>();
  return (
    <section className="markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
        components={{
          h2: ({ children }) => {
            const title = nodeToText(children);
            return <h2 id={uniqueHeadingId(title, headingCounts)}>{children}</h2>;
          }
        }}
      >
        {value}
      </ReactMarkdown>
    </section>
  );
}

function ArticleToc({ items }: { items: TocItem[] }) {
  if (!items.length) {
    return (
      <aside className="article-toc empty">
        <h2>目录</h2>
        <p>正文未设置二级标题。</p>
      </aside>
    );
  }

  return (
    <aside className="article-toc" aria-label="文章目录">
      <h2>目录</h2>
      <nav>
        {items.map((item) => (
          <button
            key={item.id}
            onClick={() => document.getElementById(item.id)?.scrollIntoView({ behavior: "smooth", block: "start" })}
            type="button"
          >
            {item.title}
          </button>
        ))}
      </nav>
    </aside>
  );
}

const DEFAULT_QA_PROMPTS = [
  "ChatGPT、Claude、Gemini 新手应该先学哪个？",
  "国内用户注册海外 AI 账号前要准备什么？",
  "订阅海外 AI 工具时有哪些支付和账号风险？"
];

function FloatingQaButton() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className="floating-qa-button" onClick={() => setOpen(true)} type="button" aria-label="打开 AI 问答">
        <MessageCircle size={22} />
        AI 问答
      </button>
      {open ? <QaChatDialog onClose={() => setOpen(false)} /> : null}
    </>
  );
}

function QaChatDialog({ onClose }: { onClose: () => void }) {
  const [popular, setPopular] = useState<QaQuestion[]>([]);
  const [question, setQuestion] = useState("");
  const [current, setCurrent] = useState<QaQuestion | null>(null);
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [waitSeconds, setWaitSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchPopularQuestions()
      .then(setPopular)
      .catch(() => setPopular([]));
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    if (!loading) return;
    const timer = window.setInterval(() => {
      setWaitSeconds((seconds) => seconds + 1);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [loading]);

  const promptItems = popular.length ? popular.slice(0, 3).map((item) => item.question) : DEFAULT_QA_PROMPTS;

  async function submit(nextQuestion = question) {
    const clean = nextQuestion.trim();
    if (!clean || loading) return;
    setCurrent(null);
    setQuestion(clean);
    setLoading(true);
    setWaitSeconds(0);
    setStatusMessage("正在提交问题...");
    setError(null);
    try {
      const answer = await askQaQuestionStream(clean, setStatusMessage);
      setCurrent(answer);
      setQuestion("");
      bodyRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
      setStatusMessage("");
    }
  }

  return (
    <div className="qa-dialog-layer" role="dialog" aria-modal="true" aria-label="AI 问答">
      <div className="qa-dialog">
        <header className="qa-dialog-head">
          <div>
            <strong>AI 问答</strong>
            <span>只回答 AI 工具、账号、支付、工作流和风险避坑问题</span>
          </div>
          <button onClick={onClose} type="button" aria-label="关闭 AI 问答">
            <X size={18} />
          </button>
        </header>

        <div className="qa-dialog-body" ref={bodyRef}>
          {!current && !loading ? (
            <div className="qa-empty">
              <MessageCircle size={28} />
              <h2>想了解什么 AI 信息差？</h2>
              <div className="qa-suggestions">
                {promptItems.map((item) => (
                  <button
                    key={item}
                    onClick={() => {
                      setQuestion(item);
                      window.setTimeout(() => inputRef.current?.focus(), 0);
                    }}
                    type="button"
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {current ? (
            <div className="qa-answer">
              <div className="qa-question-bubble">{current.question}</div>
              <MarkdownBlock value={current.answer} />
            </div>
          ) : null}

          {loading ? (
            <div className="qa-loading" aria-label="正在生成回答">
              <div>
                <span />
                <span />
                <span />
              </div>
              <p className="qa-status-text">
                {statusMessage || "正在生成回答，请耐心等待..."}（已等待 {waitSeconds} 秒）
              </p>
              {waitSeconds > 45 ? <p className="qa-status-hint">回答越详细耗时越长，通常 30-60 秒，偶尔更久</p> : null}
            </div>
          ) : null}

          {error ? <div className="qa-error">{error}</div> : null}
        </div>

        <form
          className="qa-input-row"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <input ref={inputRef} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="问一个 AI 工具或账号相关问题" />
          <button disabled={loading || !question.trim()} type="submit">
            <Send size={16} />
          </button>
        </form>
      </div>
    </div>
  );
}

function ScienceNotice() {
  return (
    <section className="science-notice">
      <AlertTriangle size={18} />
      <div>
        <strong>科学上网内容提示</strong>
        <p>本分类只提供通用准备、风险识别和来源导航。请自行确认所在地法律法规、平台条款、工作组织政策和数据安全要求。</p>
      </div>
    </section>
  );
}

function AdminPage() {
  const [token, setToken] = useState(() => getAdminToken());
  const [loginError, setLoginError] = useState<string | null>(null);

  if (!token) {
    return (
      <div className="admin-page-shell">
        <main className="admin-login-page">
          <form
            className="login-card"
            onSubmit={async (event) => {
              event.preventDefault();
              const data = new FormData(event.currentTarget);
              try {
                await login(String(data.get("username")), String(data.get("password")));
                setToken(getAdminToken());
                setLoginError(null);
              } catch (err) {
                setLoginError((err as Error).message);
              }
            }}
          >
            <LayoutDashboard size={26} />
            <h1>后台管理</h1>
            <p>管理帖子、来源、免责声明和 URL 导入。</p>
            <input name="username" placeholder="管理员账号" autoComplete="username" />
            <input name="password" placeholder="密码" type="password" autoComplete="current-password" />
            {loginError ? <div className="form-error">{loginError}</div> : null}
            <button className="primary-button" type="submit">
              登录
            </button>
          </form>
        </main>
        <DisclaimerFooter />
      </div>
    );
  }

  return (
    <div className="admin-page-shell">
      <AdminConsole
        onLogout={() => {
          clearAdminToken();
          setToken(null);
        }}
      />
      <DisclaimerFooter />
    </div>
  );
}

function AdminConsole({ onLogout }: { onLogout: () => void }) {
  const [result, setResult] = useState<PaginatedPosts | null>(null);
  const [statusFilter, setStatusFilter] = useState<AdminStatus>("all");
  const [tab, setTab] = useState<AdminTab>("posts");
  const [editing, setEditing] = useState<Post | null>(null);
  const [draft, setDraft] = useState<PostPayload | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [importUrl, setImportUrl] = useState("");

  const loadPosts = useCallback(async () => {
    try {
      setResult(await fetchAdminPosts({ status: statusFilter, page_size: 30 }));
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }, [statusFilter]);

  useEffect(() => {
    loadPosts();
  }, [loadPosts]);

  async function changeStatus(post: Post, status: PostStatus) {
    try {
      await updatePostStatus(post.id, status);
      setMessage(`已更新为 ${status}`);
      await loadPosts();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function importDraft(event: FormEvent) {
    event.preventDefault();
    try {
      const imported = await importUrlDraft(importUrl);
      setDraft(imported);
      setEditing(null);
      setMessage("已生成 URL 导入草稿，请人工审核后保存");
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <main className="admin-console-page">
      <header className="admin-topbar">
        <div>
          <strong>AI 信息差后台</strong>
          <span>帖子、来源和免责声明管理</span>
        </div>
        <button className="ghost-button" onClick={onLogout} type="button">
          <LogOut size={16} />
          退出
        </button>
      </header>
      <nav className="admin-tabs">
        <button className={tab === "posts" ? "selected" : ""} onClick={() => setTab("posts")} type="button">
          帖子管理
        </button>
        <button className={tab === "qa" ? "selected" : ""} onClick={() => setTab("qa")} type="button">
          AI 问答沉淀
        </button>
        <button className={tab === "stats" ? "selected" : ""} onClick={() => setTab("stats")} type="button">
          访问统计
        </button>
      </nav>
      {tab === "posts" ? (
        <div className="admin-layout">
          <section className="admin-list-panel">
            <div className="admin-section-head">
              <div>
                <h1>帖子管理</h1>
                <p>发布前会校验来源、步骤和风险提示。</p>
              </div>
              <button
                className="primary-button"
                onClick={() => {
                  setEditing(null);
                  setDraft(null);
                }}
                type="button"
              >
                <Plus size={16} />
                新建
              </button>
            </div>
            <form className="import-box" onSubmit={importDraft}>
              <FileDown size={17} />
              <input value={importUrl} onChange={(event) => setImportUrl(event.target.value)} placeholder="粘贴外站文章 URL，生成待审核草稿" />
              <button type="submit">导入</button>
            </form>
            <div className="admin-filters">
              {(["all", "draft", "published", "archived"] as AdminStatus[]).map((status) => (
                <button className={statusFilter === status ? "selected" : ""} key={status} onClick={() => setStatusFilter(status)} type="button">
                  {status === "all" ? "全部" : status}
                </button>
              ))}
            </div>
            {error ? <div className="form-error">{error}</div> : null}
            {message ? <div className="form-success">{message}</div> : null}
            <div className="admin-table">
              {result?.items.map((post) => (
                <div className="admin-row" key={post.id}>
                  <div>
                    <span className={`status-pill ${post.status}`}>{post.status}</span>
                    <strong>{post.title}</strong>
                    <small>
                      {post.category} · {formatDate(post.published_at)}
                    </small>
                  </div>
                  <div className="row-actions">
                    <button onClick={() => setEditing(post)} type="button" title="编辑">
                      <Edit3 size={16} />
                    </button>
                    <button onClick={() => changeStatus(post, "published")} type="button" title="发布">
                      <CheckCircle2 size={16} />
                    </button>
                    <button onClick={() => changeStatus(post, "archived")} type="button" title="归档">
                      <Archive size={16} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>
          <AdminEditor
            draft={draft}
            post={editing}
            onSaved={async (saved) => {
              setEditing(saved);
              setDraft(null);
              setMessage("已保存帖子");
              await loadPosts();
            }}
          />
        </div>
      ) : tab === "qa" ? (
        <AdminQuestionList />
      ) : (
        <AdminStatsPanel />
      )}
    </main>
  );
}

function AdminStatsPanel() {
  const [stats, setStats] = useState<StatsData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStats()
      .then((data) => {
        setStats(data);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  if (error) return <section className="admin-question-panel"><div className="form-error">{error}</div></section>;
  if (!stats) return <section className="admin-question-panel"><EmptyState title="正在加载统计" body="正在查询访问数据..." /></section>;

  const maxPv = Math.max(...stats.daily.map((d) => d.pv), 1);

  return (
    <section className="admin-stats-panel">
      <div className="admin-section-head">
        <div>
          <h1>访问统计</h1>
          <p>全站 PV/UV 数据，IP 哈希脱敏统计。</p>
        </div>
      </div>
      <div className="stats-cards">
        <div className="stats-card">
          <span className="stats-card-value">{stats.today.pv.toLocaleString()}</span>
          <span className="stats-card-label">今日 PV</span>
        </div>
        <div className="stats-card">
          <span className="stats-card-value">{stats.today.uv.toLocaleString()}</span>
          <span className="stats-card-label">今日 UV</span>
        </div>
        <div className="stats-card">
          <span className="stats-card-value">{stats.total.pv.toLocaleString()}</span>
          <span className="stats-card-label">累计 PV</span>
        </div>
        <div className="stats-card">
          <span className="stats-card-value">{stats.total.uv.toLocaleString()}</span>
          <span className="stats-card-label">累计 UV</span>
        </div>
      </div>

      <div className="stats-weekly">
        <div className="stats-weekly-head">
          <strong>本周</strong>
          <span>PV {stats.this_week.pv.toLocaleString()} · UV {stats.this_week.uv.toLocaleString()}</span>
        </div>
        <div className="stats-bars">
          {stats.daily.map((day) => (
            <div className="stats-bar-item" key={day.date}>
              <div className="stats-bar-stack">
                <div className="stats-bar-pv" style={{ height: `${(day.pv / maxPv) * 100}%` }} title={`PV ${day.pv}`} />
              </div>
              <span className="stats-bar-label">{day.date.slice(5)}</span>
              <span className="stats-bar-value">{day.pv}</span>
            </div>
          ))}
        </div>
      </div>

      {stats.yesterday.pv > 0 ? (
        <div className="stats-compare">
          昨日 PV {stats.yesterday.pv.toLocaleString()} · UV {stats.yesterday.uv.toLocaleString()}
        </div>
      ) : null}
    </section>
  );
}

function AdminQuestionList() {
  const [questions, setQuestions] = useState<QaQuestion[]>([]);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [loadingId, setLoadingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadQuestions = useCallback(async () => {
    try {
      setQuestions(await fetchAdminQaQuestions());
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    loadQuestions();
  }, [loadQuestions]);

  async function promote(question: QaQuestion) {
    const confirmText = question.is_promoted
      ? "确定要重新生成文章？AI 会再生成一篇完整教程并保存为草稿，之前生成的文章不会自动删除。"
      : "确定要将此问题扩写为文章？AI 会生成一篇完整教程并自动保存为草稿。";
    if (!window.confirm(confirmText)) return;
    setLoadingId(question.id);
    setError(null);
    try {
      const result = await promoteQaQuestion(question.id);
      setMessage(`已生成草稿：${result.post.title}`);
      setQuestions((current) =>
        current.map((item) =>
          item.id === question.id
            ? {
                ...item,
                is_promoted: true,
                promoted_post_id: result.post.id,
                promoted_post_slug: result.post.slug,
                promoted_post_status: result.post.status
              }
            : item
        )
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoadingId(null);
    }
  }

  return (
    <section className="admin-question-panel">
      <div className="admin-section-head">
        <div>
          <h1>AI 问答沉淀</h1>
          <p>把高频问题扩写成正式帖子。</p>
        </div>
      </div>
      {error ? <div className="form-error">{error}</div> : null}
      {message ? <div className="form-success">{message}</div> : null}
      <div className="qa-admin-table">
        {questions.map((item) => (
          <div className="qa-admin-row" key={item.id}>
            <button className="qa-admin-question" onClick={() => setExpandedId(expandedId === item.id ? null : item.id)} type="button">
              <strong>{item.question}</strong>
              <span>
                {item.topic_keyword || "未分类"} · 被问 {item.ask_count} 次 ·{" "}
                {item.is_promoted ? `已生成${item.promoted_post_status ? `（${item.promoted_post_status}）` : ""}` : "未生成"}
                {item.promoted_post_slug ? (
                  <a href={`/posts/${item.promoted_post_slug}`} target="_blank" rel="noreferrer" title="查看文章">
                    <ExternalLink size={12} />
                  </a>
                ) : null}
              </span>
            </button>
            <button disabled={loadingId === item.id} onClick={() => promote(item)} type="button">
              {loadingId === item.id ? "生成中" : item.is_promoted ? "重新生成" : "生成文章"}
            </button>
            {expandedId === item.id ? (
              <div className="qa-admin-answer">
                <MarkdownBlock value={item.answer} />
              </div>
            ) : null}
          </div>
        ))}
        {!questions.length ? <EmptyState title="暂无问答" body="用户通过右下角 AI 问答提问后，会沉淀到这里。" /> : null}
      </div>
    </section>
  );
}

function AdminEditor({
  post,
  draft,
  onSaved
}: {
  post: Post | null;
  draft: PostPayload | null;
  onSaved: (post: Post) => void | Promise<void>;
}) {
  const [form, setForm] = useState<PostPayload>(EMPTY_POST);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setError(null);
    setSuccess(null);
    if (draft) {
      setForm(draft);
      return;
    }
    if (!post) {
      setForm(EMPTY_POST);
      return;
    }
    setForm({
      title: post.title,
      slug: post.slug,
      summary: post.summary,
      category: post.category,
      tags: post.tags,
      audience: post.audience,
      prerequisites: post.prerequisites,
      steps: post.steps,
      faq: post.faq,
      risk_notice: post.risk_notice,
      body_markdown: post.body_markdown,
      sources: post.sources,
      status: post.status
    });
  }, [post, draft]);

  function updateField<K extends keyof PostPayload>(key: K, value: PostPayload[K]) {
    setSuccess(null);
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const saved = post ? await updateAdminPost(post.id, form) : await createAdminPost(form);
      await onSaved(saved);
      setSuccess(`已保存：${saved.title}`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="editor-panel" onSubmit={submit}>
      <h2>{post ? "编辑帖子" : "新建帖子"}</h2>
      <div className="editor-scroll">
        <label>
          标题
          <input value={form.title} onChange={(event) => updateField("title", event.target.value)} required />
        </label>
        <label>
          Slug
          <input value={form.slug} onChange={(event) => updateField("slug", event.target.value)} placeholder="留空则自动生成" />
        </label>
        <label>
          摘要
          <textarea value={form.summary} onChange={(event) => updateField("summary", event.target.value)} required />
        </label>
        <div className="form-grid">
          <label>
            分类
            <select value={form.category} onChange={(event) => updateField("category", event.target.value)}>
              {CATEGORY_ORDER.map((category) => (
                <option key={category}>{category}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="form-grid">
          <label>
            状态
            <select value={form.status} onChange={(event) => updateField("status", event.target.value as PostStatus)}>
              <option value="draft">draft</option>
              <option value="published">published</option>
              <option value="archived">archived</option>
            </select>
          </label>
          <label>
            标签
            <textarea value={listToText(form.tags)} onChange={(event) => updateField("tags", textToList(event.target.value))} />
          </label>
        </div>
        <label>
          适合人群
          <textarea value={form.audience} onChange={(event) => updateField("audience", event.target.value)} required />
        </label>
        <label>
          准备条件（每行一项）
          <textarea value={listToText(form.prerequisites)} onChange={(event) => updateField("prerequisites", textToList(event.target.value))} />
        </label>
        <label>
          操作步骤（每行一步，发布必填）
          <textarea className="tall" value={listToText(form.steps)} onChange={(event) => updateField("steps", textToList(event.target.value))} />
        </label>
        <label>
          FAQ（每行：问题｜回答）
          <textarea value={faqToText(form.faq)} onChange={(event) => updateField("faq", textToFAQ(event.target.value))} />
        </label>
        <label>
          风险提示 / 免责声明（科学上网发布时必须详细填写）
          <textarea className="tall" value={form.risk_notice} onChange={(event) => updateField("risk_notice", event.target.value)} required />
        </label>
        <label>
          正文 Markdown
          <textarea className="extra-tall" value={form.body_markdown} onChange={(event) => updateField("body_markdown", event.target.value)} required />
        </label>
        <label>
          来源（每行：标题 | URL | 站点 | 作者 | 用途 | 版权说明 | 短引用）
          <textarea className="extra-tall" value={sourcesToText(form.sources)} onChange={(event) => updateField("sources", textToSources(event.target.value))} />
        </label>
        <div className="editor-warning">
          <AlertTriangle size={16} />
          发布内容必须为原创摘要和结构化教程；外站内容只保留短引用、用途说明和来源链接。
        </div>
        {error ? <div className="form-error">{error}</div> : null}
        {success ? <div className="form-success">{success}</div> : null}
      </div>
      <div className="editor-actions">
        <span>{success ?? (post ? "正在编辑帖子" : draft ? "正在编辑导入草稿" : "正在新建帖子")}</span>
        <button className="primary-button" disabled={saving} type="submit">
          {saving ? "保存中..." : success ? "已保存" : "保存帖子"}
        </button>
      </div>
    </form>
  );
}

function EmptyState({ title, body, children }: { title: string; body: string; children?: ReactNode }) {
  return (
    <div className="empty-state">
      <BookOpen size={24} />
      <h2>{title}</h2>
      <p>{body}</p>
      {children}
    </div>
  );
}

export function App() {
  const [route, navigate] = useRoute();
  const filters = useQueryFilters(route);
  const [homePosts, setHomePosts] = useState<PaginatedPosts | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPosts({ page_size: 50 })
      .then((postsResult) => {
        setHomePosts(postsResult);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  // 访问统计：路由变化时上报，同 path 不重复
  const lastRecordedPath = useRef("");
  useEffect(() => {
    const currentPath = window.location.pathname + window.location.search;
    if (currentPath !== lastRecordedPath.current) {
      lastRecordedPath.current = currentPath;
      recordVisit(currentPath).catch(() => {
        /* 静默失败，不影响页面 */
      });
    }
  }, [route]);

  if (route.name === "admin") {
    return <AdminPage />;
  }

  let page: React.ReactNode;
  if (error) {
    page = <main className="home-page"><EmptyState title="服务暂时不可用" body={`${error}。请确认 FastAPI 服务正在运行。`} /></main>;
  } else if (route.name === "list") {
    page = <ListPage filters={filters} onNavigate={navigate} />;
  } else if (route.name === "detail") {
    page = <DetailPage slug={route.slug} onNavigate={navigate} />;
  } else {
    page = <HomePage onNavigate={navigate} posts={homePosts} />;
  }

  return <PublicShell onNavigate={navigate}>{page}</PublicShell>;
}
