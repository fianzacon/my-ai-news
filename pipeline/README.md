# AI News Intelligence Pipeline for Lotte Members

**Production-ready AI news collection, filtering, and analysis system for advertising & marketing data practitioners.**

## Overview

This pipeline automatically:
1. **Collects** AI-related news from Naver and Google News APIs
2. **Deduplicates** using semantic similarity (title+lead @ 85%, full content @ 90%)
3. **Filters** by category relevance (solution, case, technology, regulation)
4. **Extracts** full article content
5. **Validates** business value for marketing practitioners
6. **Analyzes** impact on Lotte Members business
7. **Generates** Webex-ready message summaries

## Architecture

```
┌─────────────────┐
│  News Sources   │
│  - Naver API    │
│  - Google News  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Step 1: Collect│
│  + First Dedup  │  (Title + Lead, 85%)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Step 2: Category│
│     Filter      │  (LLM: solution/case/tech/regulation)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Step 3: Extract│
│  + Second Dedup │  (Full content, 90%)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Step 4: Value  │
│   Validation    │  (Business relevance)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Step 5: Lotte  │
│  Context Analysis│  (Impact type & areas)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Step 6: Webex   │
│  Message Output │  (Company, Summary, Action)
└─────────────────┘
```

## Critical Features

### ⚖️ Regulatory Article Protection
- Regulatory/legal AI news NEVER dropped throughout pipeline
- Multiple checkpoints ensure compliance articles reach output
- Special handling in deduplication (prefers regulatory when duplicate)

### 🎯 Semantic Deduplication
- Uses VertexAI embeddings (768-dim) for similarity calculation
- Two-stage deduplication:
  - **First**: Title + lead paragraph (85% threshold)
  - **Second**: Full content (90% threshold)
- Selects most informative article from duplicate groups

### 🤖 LLM-Based Intelligence
- Category classification with pass/fail decisions
- Business value validation
- Lotte Members context analysis
- Webex message generation with strict format

## Quick Start

### 1. Install Dependencies

```bash
cd test/pipeline
pip install -r requirements_pipeline.txt
```

### 2. Configure API Keys

Create `.env` file in `test/` directory:

```dotenv
# Required: Google Gemini API for LLM
GOOGLE_API_KEY=your_google_api_key_here

# Required: Naver News API
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret

# Optional: Google News API (newsapi.org)
GOOGLE_NEWS_API_KEY=your_newsapi_key

# Optional: Langfuse for observability
LANGFUSE_PUBLIC_KEY=your_langfuse_public_key
LANGFUSE_SECRET_KEY=your_langfuse_secret_key
LANGFUSE_HOST=http://localhost:3000
```

### 3. Run Pipeline

```bash
# From test/ directory
cd test
python -m pipeline.news_pipeline
```

Or as a module:

```python
from pipeline import NewsIntelligencePipeline

pipeline = NewsIntelligencePipeline()
stats = pipeline.run(save_output=True)
```

## Output

### Webex Messages
Generated in: `webex_messages_YYYYMMDD_HHMMSS.txt`

Format:
```
📰 **AI 뉴스 인텔리전스**

[Company / Entity]
Google, OpenAI

[Key Summary]
Google이 Gemini 2.0을 발표하며 멀티모달 AI 경쟁 심화.
실시간 음성 대화 및 이미지 생성 기능 강화로 마케팅 활용도 증가 예상.

[Action]
경쟁사 AI 도구 벤치마킹 및 자사 데이터 플랫폼 통합 방안 검토

🔗 https://...
```

### Pipeline Logs
- Console output with emoji indicators
- `pipeline.log` file with detailed execution trace
- Statistics summary at completion

## Configuration

Edit [config.py](config.py) to customize:

```python
# LLM Model
LLM_MODEL = "gemini-2.0-flash-exp"
LLM_TEMPERATURE = 0.1

# Deduplication Thresholds
FIRST_DEDUP_THRESHOLD = 0.85   # Title + lead
SECOND_DEDUP_THRESHOLD = 0.90  # Full content

# Collection
SEARCH_KEYWORD = "AI"
MAX_ARTICLES_PER_SOURCE = 100
```

## Project Structure

```
pipeline/
├── __init__.py              # Package initialization
├── news_pipeline.py         # Main orchestrator
├── models.py                # Data structures
├── config.py                # Configuration
├── utils.py                 # Utilities (embeddings, similarity)
├── collectors.py            # Step 1: Collection + first dedup
├── filtering.py             # Step 2: Category filtering
├── extraction.py            # Step 3: Content extraction + second dedup
├── analysis.py              # Steps 4-5: Value validation + Lotte context
├── output.py                # Step 6: Webex message generation
├── requirements_pipeline.txt
└── README.md
```

## API Requirements

### Naver News Search API
- Sign up: https://developers.naver.com/
- Create application → Get Client ID & Secret
- Free tier: 25,000 requests/day

### Google News API (Optional)
- Option 1: News API (newsapi.org) - Free tier: 100 requests/day
- Option 2: Implement RSS feed parsing (no API key needed)

### Google Gemini API
- Get API key: https://aistudio.google.com/app/apikey
- Used for: LLM classification, analysis, message generation
- Free tier available

## Production Deployment

### Daily Scheduled Run

**Windows Task Scheduler:**
```bash
# Create batch file: run_pipeline.bat
cd C:\path\to\test
call venv\Scripts\activate
python -m pipeline.news_pipeline
```

**Linux/Mac Cron:**
```bash
# Run daily at 9 AM
0 9 * * * cd /path/to/test && ./venv/bin/python -m pipeline.news_pipeline
```

### Error Handling
- Pipeline continues on individual article errors
- Defaults to "pass" when LLM classification fails
- Fallback messages generated when formatting fails
- Regulatory articles protected at each checkpoint

### Monitoring
- Check `pipeline.log` for execution details
- Review pipeline statistics in console output
- Monitor regulatory article count (found vs. retained)

## Important Notes

⚠️ **Regulatory Articles**: The pipeline has multiple safeguards to ensure regulatory/legal news is NEVER dropped. If statistics show discrepancy between found vs. retained, investigate immediately.

⚠️ **Rate Limits**: 
- Naver API: 25,000 requests/day
- News API: 100 requests/day (free tier)
- Add delays between requests to avoid rate limiting

⚠️ **Content Extraction**: newspaper4k may fail on some websites. Pipeline falls back to lead paragraph when extraction fails.

⚠️ **Embedding Costs**: VertexAI embeddings have associated costs in production. Monitor usage in GCP console.

## Troubleshooting

### "Missing environment variable" error
- Ensure `.env` file exists in `test/` directory
- Check all required API keys are set

### No articles collected
- Verify Naver/Google API credentials
- Check API rate limits not exceeded
- Review search keyword relevance

### Embedding errors
- Ensure GCP credentials configured: `gcloud auth application-default login`
- Check VertexAI API is enabled in GCP project

### All articles filtered out
- Review category filtering logic in [filtering.py](filtering.py)
- Check LLM temperature (lower = stricter)
- Verify article content is relevant to search keyword

## Development

### Adding New News Sources

Edit [collectors.py](collectors.py):
```python
def _collect_from_new_source(self) -> List[NewsArticle]:
    # Implement collection logic
    articles = []
    # ...
    return articles
```

### Customizing Analysis

Edit [analysis.py](analysis.py) to modify:
- Business value criteria
- Lotte Members impact areas
- Impact type classification

### Changing Output Format

Edit [output.py](output.py) to customize Webex message template.

## License

Internal use for Lotte Members only.

## Support

For issues or questions:
1. Check `pipeline.log` for detailed error messages
2. Review pipeline statistics for bottleneck identification
3. Contact: [Your team contact]
