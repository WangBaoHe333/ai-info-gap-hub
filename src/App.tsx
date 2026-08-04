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
  Filter,
  LayoutDashboard,
  LogOut,
  Plus,
  Search,
  ShieldAlert,
  Sparkles,
  X
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  clearAdminToken,
  createAdminPost,
  fetchAdminPosts,
  fetchCategories,
  fetchPost,
  fetchPosts,
  fetchTags,
  getAdminToken,
  importUrlDraft,
  login,
  updateAdminPost,
  updatePostStatus
} from "./api";
import type { FAQItem, PaginatedPosts, Post, PostFilters, PostPayload, PostSource, PostStatus } from "./types";

type Route =
  | { name: "home" }
  | { name: "list" }
  | { name: "detail"; slug: string }
  | { name: "admin" };

type AdminStatus = PostStatus | "all";

const CATEGORY_ORDER = [
  "科学上网",
  "海外 AI 账号",
  "海外 AI 工具使用",
  "支付订阅",
  "AI 创作工作流",
  "案例玩法",
  "风险避坑"
];

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

function useQueryFilters(): PostFilters {
  return useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return {
      page: Number(params.get("page") || "1"),
      page_size: DEFAULT_PAGE_SIZE,
      category: params.get("category") || undefined,
      tag: params.get("tag") || undefined,
      q: params.get("q") || undefined
    };
  }, [window.location.search]);
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
  categories,
  tags,
  onNavigate
}: {
  posts: PaginatedPosts | null;
  categories: string[];
  tags: string[];
  onNavigate: (path: string) => void;
}) {
  const [latestPage, setLatestPage] = useState(1);
  const [latestResult, setLatestResult] = useState<PaginatedPosts | null>(posts);
  const [latestError, setLatestError] = useState<string | null>(null);

  useEffect(() => {
    fetchPosts({ page: latestPage, page_size: DEFAULT_PAGE_SIZE })
      .then((data) => {
        setLatestResult(data);
        setLatestError(null);
      })
      .catch((err: Error) => setLatestError(err.message));
  }, [latestPage]);

  useEffect(() => {
    if (posts && latestPage === 1) setLatestResult(posts);
  }, [posts, latestPage]);

  const latestCount = latestResult?.total ?? posts?.total ?? 0;
  return (
    <main className="home-page">
      <section className="hero-panel">
        <div>
          <h1>帮助国内用户打破 AI 信息差</h1>
          <p>聚合科学上网风险提示、海外 AI 账号、工具使用、支付订阅和案例玩法，所有内容都标注出处。</p>
          <SearchPanel onSearch={(query) => onNavigate(`/posts${query ? `?q=${encodeURIComponent(query)}` : ""}`)} />
        </div>
        <div className="focus-cards">
          <button onClick={() => onNavigate("/posts?category=%E7%A7%91%E5%AD%A6%E4%B8%8A%E7%BD%91")} type="button">
            <span>入门准备</span>
            <strong>科学上网、账号安全、合规风险</strong>
            <small>面向国内用户</small>
          </button>
          <button onClick={() => onNavigate("/posts?category=%E6%B5%B7%E5%A4%96%20AI%20%E5%B7%A5%E5%85%B7%E4%BD%BF%E7%94%A8")} type="button">
            <span>海外 AI 工具</span>
            <strong>账号、工具、案例、官方资源</strong>
            <small>{latestCount} 条内容</small>
          </button>
        </div>
      </section>

      <section className="notice-band">
        <ShieldAlert size={18} />
        <span>
          科学上网类内容仅提供通用准备、风险提示和来源导航。请自行确认所在地法律法规、平台条款和组织合规要求。
        </span>
      </section>

      <div className="home-grid">
        <section className="content-block home-latest-panel">
          <div className="section-head">
            <h2>最新帖子</h2>
            <button onClick={() => onNavigate("/posts")} type="button">
              查看全部
            </button>
          </div>
          {latestError ? <EmptyState title="读取失败" body={latestError} /> : null}
          <div className="post-list post-list-scroll">
            {latestResult?.items.map((post) => <PostListItem key={post.id} post={post} onOpen={() => onNavigate(`/posts/${post.slug}`)} />)}
            {latestResult && latestResult.items.length === 0 ? <EmptyState title="暂无帖子" body="后台发布后会显示在这里。" /> : null}
          </div>
          {latestResult ? <Pagination result={latestResult} onNavigate={setLatestPage} /> : null}
        </section>
        <aside className="side-stack">
          <section className="side-card">
            <h2>内容分类</h2>
            <div className="category-grid">
              {categories.map((category) => (
                <button key={category} onClick={() => onNavigate(`/posts?category=${encodeURIComponent(category)}`)} type="button">
                  {category}
                </button>
              ))}
            </div>
          </section>
          <section className="side-card">
            <h2>热门标签</h2>
            <div className="tag-cloud">
              {tags.slice(0, 14).map((tag) => (
                <button key={tag} onClick={() => onNavigate(`/posts?tag=${encodeURIComponent(tag)}`)} type="button">
                  {tag}
                </button>
              ))}
            </div>
          </section>
        </aside>
      </div>
    </main>
  );
}

function PostListItem({ post, onOpen }: { post: Post; onOpen: () => void }) {
  return (
    <article className="post-item">
      <div className="post-main">
        <div className="post-meta">
          <span>{post.category}</span>
          <span>{formatDate(post.published_at)}</span>
        </div>
        <button className="post-title" onClick={onOpen} type="button">
          {post.title}
        </button>
        <p>{post.summary}</p>
        <div className="post-tags">
          {post.tags.slice(0, 5).map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
        </div>
      </div>
      {post.category === "科学上网" ? (
        <div className="inline-risk">
          <AlertTriangle size={15} />
          含合规与风险提示
        </div>
      ) : null}
    </article>
  );
}

function ListPage({
  categories,
  tags,
  filters,
  onNavigate
}: {
  categories: string[];
  tags: string[];
  filters: PostFilters;
  onNavigate: (path: string) => void;
}) {
  const [result, setResult] = useState<PaginatedPosts | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);

  useEffect(() => {
    fetchPosts(filters)
      .then((data) => {
        setResult(data);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, [filters.page, filters.category, filters.tag, filters.q]);

  const makePath = (next: PostFilters) => {
    const params = new URLSearchParams();
    const merged = { ...filters, ...next };
    Object.entries(merged).forEach(([key, value]) => {
      if (value && key !== "page_size") params.set(key, String(value));
    });
    return `/posts?${params.toString()}`;
  };
  const go = (path: string) => {
    setFiltersOpen(false);
    onNavigate(path);
  };
  const activeFilters = [filters.category, filters.tag, filters.q ? `关键词：${filters.q}` : null].filter(Boolean);

  return (
    <main className="list-page">
      <section className="list-toolbar">
        <div>
          <h1>{filters.category ?? "全部信息差帖子"}</h1>
          <p>按主题、标签和关键词检索面向国内用户的教程帖。</p>
        </div>
        <SearchPanel initialQuery={filters.q ?? ""} onSearch={(query) => onNavigate(makePath({ q: query || undefined, page: 1 }))} />
      </section>

      {filters.category === "科学上网" ? <ScienceNotice /> : null}

      <div className="list-workspace">
        <div className="list-actions">
          <button className="filter-toggle" onClick={() => setFiltersOpen(true)} type="button" aria-expanded={filtersOpen}>
            <Filter size={16} />
            筛选
          </button>
          <div className="active-filters" aria-label="当前筛选">
            {activeFilters.length ? activeFilters.map((item) => <span key={item}>{item}</span>) : <span>全部帖子</span>}
          </div>
        </div>

        <section className="content-block list-results-panel">
          {error ? <EmptyState title="读取失败" body={error} /> : null}
          <div className="result-line">
            <span>{result?.total ?? 0} 条结果</span>
            <span>第 {result?.page ?? 1} / {result?.total_pages ?? 1} 页</span>
          </div>
          <div className="post-list post-list-scroll">
            {result?.items.map((post) => <PostListItem key={post.id} post={post} onOpen={() => onNavigate(`/posts/${post.slug}`)} />)}
            {result && result.items.length === 0 ? <EmptyState title="没有找到匹配帖子" body="换一个关键词或清空筛选条件。" /> : null}
          </div>
          {result ? <Pagination result={result} onNavigate={(page) => onNavigate(makePath({ page }))} /> : null}
        </section>
      </div>

      {filtersOpen ? (
        <div className="filter-drawer-layer" role="presentation" onClick={() => setFiltersOpen(false)}>
          <aside className="filter-drawer" role="dialog" aria-modal="true" aria-label="帖子筛选" onClick={(event) => event.stopPropagation()}>
            <div className="drawer-head">
              <h2>
                <Filter size={16} />
                筛选帖子
              </h2>
              <button onClick={() => setFiltersOpen(false)} type="button" aria-label="关闭筛选">
                <X size={18} />
              </button>
            </div>
            <button className={!filters.category && !filters.tag && !filters.q ? "selected" : ""} onClick={() => go("/posts")} type="button">
              全部帖子
            </button>
            <hr />
            <strong>分类</strong>
            {categories.map((category) => (
              <button
                className={filters.category === category ? "selected" : ""}
                key={category}
                onClick={() => go(makePath({ category, page: 1 }))}
                type="button"
              >
                {category}
              </button>
            ))}
            <hr />
            <strong>标签</strong>
            <div className="compact-tags">
              {tags.slice(0, 18).map((tag) => (
                <button className={filters.tag === tag ? "selected" : ""} key={tag} onClick={() => go(makePath({ tag, page: 1 }))} type="button">
                  {tag}
                </button>
              ))}
            </div>
          </aside>
        </div>
      ) : null}
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
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    fetchPost(slug)
      .then((data) => {
        setPost(data);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, [slug]);

  if (error) return <main className="detail-page"><EmptyState title="帖子不存在" body={error} /></main>;
  if (!post) return <main className="detail-page"><EmptyState title="正在读取帖子" body="正在加载教程步骤、风险提示和来源。" /></main>;

  return (
    <main className="detail-page">
      <button className="back-button" onClick={() => onNavigate("/posts")} type="button">
        <ChevronLeft size={16} />
        返回列表
      </button>
      {post.category === "科学上网" ? <ScienceNotice /> : null}
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
    </main>
  );
}

function MarkdownBlock({ value }: { value: string }) {
  const blocks = value.split(/\n+/).filter(Boolean);
  return (
    <section className="markdown-body">
      {blocks.map((block) => {
        if (block.startsWith("## ")) return <h2 key={block}>{block.slice(3)}</h2>;
        if (block.startsWith("# ")) return <h2 key={block}>{block.slice(2)}</h2>;
        if (block.startsWith("- ")) return <p key={block}>• {block.slice(2)}</p>;
        return <p key={block}>{block}</p>;
      })}
    </section>
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
            <p>独立管理帖子、来源、免责声明和 URL 导入草稿。默认开发账号 admin / admin123。</p>
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
    </main>
  );
}

function AdminEditor({ post, draft, onSaved }: { post: Post | null; draft: PostPayload | null; onSaved: (post: Post) => void }) {
  const [form, setForm] = useState<PostPayload>(EMPTY_POST);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
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
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const saved = post ? await updateAdminPost(post.id, form) : await createAdminPost(form);
      setError(null);
      onSaved(saved);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="editor-panel" onSubmit={submit}>
      <h2>{post ? "编辑帖子" : "新建帖子"}</h2>
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
      <button className="primary-button" type="submit">
        保存帖子
      </button>
    </form>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="empty-state">
      <BookOpen size={24} />
      <h2>{title}</h2>
      <p>{body}</p>
    </div>
  );
}

export function App() {
  const [route, navigate] = useRoute();
  const filters = useQueryFilters();
  const [homePosts, setHomePosts] = useState<PaginatedPosts | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchPosts({ page_size: 10 }), fetchCategories(), fetchTags()])
      .then(([postsResult, categoriesResult, tagsResult]) => {
        setHomePosts(postsResult);
        setCategories(categoriesResult);
        setTags(tagsResult);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  if (route.name === "admin") {
    return <AdminPage />;
  }

  let page: React.ReactNode;
  if (error) {
    page = <main className="home-page"><EmptyState title="服务暂时不可用" body={`${error}。请确认 FastAPI 服务正在运行。`} /></main>;
  } else if (route.name === "list") {
    page = <ListPage categories={categories} filters={filters} onNavigate={navigate} tags={tags} />;
  } else if (route.name === "detail") {
    page = <DetailPage slug={route.slug} onNavigate={navigate} />;
  } else {
    page = <HomePage categories={categories} onNavigate={navigate} posts={homePosts} tags={tags} />;
  }

  return <PublicShell onNavigate={navigate}>{page}</PublicShell>;
}
