export type PostStatus = "draft" | "published" | "archived";

export interface PostSource {
  id?: string;
  title: string;
  url: string;
  site_name: string;
  author: string;
  used_for: string;
  license_note: string;
  excerpt: string;
}

export interface FAQItem {
  question: string;
  answer: string;
}

export interface Post {
  id: string;
  title: string;
  slug: string;
  summary: string;
  category: string;
  tags: string[];
  audience: string;
  prerequisites: string[];
  steps: string[];
  faq: FAQItem[];
  risk_notice: string;
  body_markdown: string;
  sources: PostSource[];
  status: PostStatus;
  published_at: string | null;
  updated_at: string;
}

export type PostPayload = Omit<Post, "id" | "published_at" | "updated_at">;

export interface PaginatedPosts {
  items: Post[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface PostFilters {
  page?: number;
  page_size?: number;
  category?: string;
  tag?: string;
  q?: string;
  status?: PostStatus | "all";
}
