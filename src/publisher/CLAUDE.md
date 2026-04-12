# Team: Publisher

## Responsibility
Publish generated posts to X, handle scheduling, and track post performance.

## Scope
- Post to X via API v2
- Schedule posts for optimal engagement times
- Rate limit management
- Post status tracking (posted, failed, scheduled)
- Basic analytics retrieval (likes, retweets, impressions)

## Interface
- `publish(post: Post) -> PostResult`
- `schedule(post: Post, at: datetime) -> PostResult`
- `get_metrics(post_id: str) -> PostMetrics`

## Conventions
- Use Tweepy or raw X API v2 with OAuth 2.0
- Never post without confirmation in dev mode
- Log every publish attempt with post ID and status
- Implement exponential backoff for rate limits
