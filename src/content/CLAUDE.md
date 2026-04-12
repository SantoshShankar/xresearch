# Team: Content

## Responsibility
Generate engaging X posts using LLMs, tailored to trending topics in AI/LLMs and cricket.

## Scope
- Prompt engineering for trend-aware post generation
- Post formatting (character limits, hashtags, thread creation)
- Tone/style management (informative, witty, engagement-optimized)
- A/B variations for the same trend
- Content filtering (avoid controversial/inappropriate content)

## Interface
- `generate_posts(trends: list[Trend], count: int) -> list[Post]`
- Takes `Trend` objects from the trends team
- Returns `Post` objects defined in `src/core/models.py`

## Conventions
- Use Claude API (anthropic SDK) for post generation
- Prompts live in a `prompts/` subdirectory as text files
- Each topic domain (AI, cricket) can have specialized prompt templates
- Always validate post length (<280 chars unless thread)
