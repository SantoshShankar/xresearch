from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TopicDomain(str, Enum):
    AI = "ai"
    LLM = "llm"
    CRICKET = "cricket"
    GENERAL = "general"


class TrendSource(str, Enum):
    GOOGLE_TRENDS = "google_trends"
    REDDIT = "reddit"
    GNEWS = "gnews"
    HACKER_NEWS = "hacker_news"
    HUGGINGFACE = "huggingface"
    ARXIV = "arxiv"
    PAPERS_WITH_CODE = "papers_with_code"
    CRICAPI = "cricapi"
    X_API = "x_api"
    RSS = "rss"


class Trend(BaseModel):
    title: str
    description: str = ""
    url: str = ""
    source: TrendSource
    domain: TopicDomain = TopicDomain.GENERAL
    score: float = 0.0  # normalized relevance/popularity score 0-1
    raw_score: float = 0.0  # source-specific raw score
    hashtags: list[str] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = Field(default_factory=dict)


class PostType(str, Enum):
    SINGLE = "single"
    THREAD = "thread"


class Post(BaseModel):
    content: str
    trend: Trend
    post_type: PostType = PostType.SINGLE
    hashtags: list[str] = Field(default_factory=list)
    thread_parts: list[str] = Field(default_factory=list)  # for threads
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_valid_length(self) -> bool:
        if self.post_type == PostType.SINGLE:
            return len(self.content) <= 280
        return all(len(part) <= 280 for part in self.thread_parts)


class PostStatus(str, Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    POSTED = "posted"
    FAILED = "failed"


class PostResult(BaseModel):
    post: Post
    status: PostStatus = PostStatus.DRAFT
    post_id: str = ""
    error: str = ""
    posted_at: datetime | None = None


class PostMetrics(BaseModel):
    post_id: str
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    impressions: int = 0
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
