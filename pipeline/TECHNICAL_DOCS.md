# AI News Intelligence Pipeline - Technical Documentation

## System Architecture

### High-Level Flow

```
News APIs → Collect → Dedup1 → Filter → Extract → Dedup2 → Validate → Analyze → Format → Output
```

### Component Breakdown

#### 1. News Collection (`collectors.py`)
- **Purpose**: Fetch AI-related news from multiple sources
- **Sources**: 
  - Naver News Search API
  - Google News API (via newsapi.org or RSS)
- **First Deduplication**: 
  - Combines title + lead paragraph (first 2-3 sentences)
  - Generates embeddings using VertexAI
  - Groups articles with ≥85% cosine similarity
  - Keeps most informative article from each group

**Key Functions**:
- `collect_all()`: Main entry point, coordinates collection from all sources
- `_collect_from_naver()`: Naver News API integration
- `_collect_from_google()`: Google News API integration
- `_first_deduplication()`: Semantic similarity-based dedup
- `_select_most_informative()`: Chooses best article from duplicate group

**Selection Criteria**:
```python
score = len(lead_paragraph) + (100 if media_name else 0) - days_old
```

#### 2. Category Filtering (`filtering.py`)
- **Purpose**: LLM-based pass/fail classification
- **Model**: Gemini 2.0 Flash (temp=0.1 for consistency)
- **Categories**:
  - `solution`: Marketing/advertising AI tools
  - `case`: Company adoption cases
  - `technology`: Data analytics, generative AI, infrastructure
  - `regulation`: Laws, privacy, copyright, compliance

**Critical Logic**:
- Regulatory articles ALWAYS pass
- Default to PASS on LLM errors (fail-safe)
- Rejects only: entertainment, gossip, substance-free announcements

**Output**: JSON with `pass`, `categories[]`, `reason`

#### 3. Content Extraction (`extraction.py`)
- **Purpose**: Extract full article text and perform content-based deduplication
- **Extractor**: newspaper4k (fallback to lead paragraph if fails)
- **Second Deduplication**:
  - Full article content embeddings
  - ≥90% cosine similarity threshold
  - Special handling for regulatory articles (always keep at least one)

**Key Functions**:
- `extract_and_deduplicate()`: Main orchestrator
- `_extract_full_content()`: newspaper4k integration
- `_second_deduplication()`: Content similarity analysis
- `_select_best_with_regulatory_priority()`: Ensures regulatory retention

**Selection Criteria**:
```python
score = len(full_content) + (500 if media_name else 0) + 
        (len(categories) * 100) + (1000 if regulatory else 0)
```

#### 4. Value Validation (`analysis.py` - Step 4)
- **Purpose**: Determine if article has real business value
- **Model**: Gemini 2.0 Flash (temp=0.1)
- **Criteria**:
  - Exclude ONLY if purely academic with no business implications
  - Keep if relevant to marketing, advertising, data, or compliance
  - Regulatory articles retained unless completely irrelevant

**Override Logic**:
```python
if is_regulatory and not has_value:
    # Force keep regulatory articles
    has_value = True
    reason = "Regulatory article retained"
```

#### 5. Lotte Context Analysis (`analysis.py` - Step 5)
- **Purpose**: Analyze article impact on Lotte Members business
- **Model**: Gemini 2.0 Flash (temp=0.1)

**Impact Types**:
- `opportunity`: Business advantage
- `threat`: Competitive risk
- `mixed`: Both opportunities and threats
- `watchlist`: Monitor, unclear impact

**Impact Areas** (multi-select):
- `membership data usage`: Data collection/analysis
- `targeting / segmentation`: Customer targeting
- `advertising agency / data sales business`: Core services
- `online–offline linkage`: Retail integration
- `legal / compliance`: Regulatory compliance
- `none`: No specific area

**Output**: JSON with `impact_type`, `impact_areas[]`, `reasoning`

#### 6. Webex Message Generation (`output.py`)
- **Purpose**: Create actionable Webex notifications
- **Model**: Gemini 2.0 Flash (temp=0.2 for natural language)

**Strict Format**:
```
[Company / Entity]
<explicit company/organization names>

[Key Summary]
<2-3 concise lines, essential facts only>

[Action]
<ONE practical action sentence for practitioners>
```

**Validation Rules**:
- Summary: max 150 chars (2-3 lines)
- Action: max 80 chars (1 sentence)
- Language: Korean
- Tone: Specific and actionable

## Data Models

### NewsArticle
```python
@dataclass
class NewsArticle:
    title: str
    url: str
    published_date: datetime
    source: str  # 'naver' or 'google'
    media_name: Optional[str]
    lead_paragraph: Optional[str]
    full_content: Optional[str]
    title_lead_hash: Optional[str]
    content_embedding: Optional[List[float]]  # 768-dim
```

### CategoryFilterResult
```python
@dataclass
class CategoryFilterResult:
    article: NewsArticle
    passed: bool
    categories: List[Literal['solution', 'case', 'technology', 'regulation']]
    reason: str
    
    def must_keep_for_regulation(self) -> bool:
        return 'regulation' in self.categories
```

### LotteContextAnalysis
```python
@dataclass
class LotteContextAnalysis:
    article: NewsArticle
    impact_type: Literal['opportunity', 'threat', 'mixed', 'watchlist']
    impact_areas: List[Literal[...]]  # 6 possible areas
    reasoning: str
```

## Configuration

### Key Parameters (`config.py`)
```python
# LLM
LLM_MODEL = "gemini-2.0-flash-exp"
LLM_TEMPERATURE = 0.1

# Embeddings
EMBEDDING_MODEL = "text-multilingual-embedding-002"
EMBEDDING_DIMENSION = 768

# Deduplication
FIRST_DEDUP_THRESHOLD = 0.85   # Title + lead
SECOND_DEDUP_THRESHOLD = 0.90  # Full content

# Collection
SEARCH_KEYWORD = "AI"
MAX_ARTICLES_PER_SOURCE = 100
```

## Regulatory Article Protection

### Checkpoint 1: Category Filtering
```python
if 'regulation' in categories:
    passed = True  # Force pass
```

### Checkpoint 2: Value Validation
```python
if is_regulatory and not has_business_value:
    has_business_value = True
    reason = "Regulatory article retained"
```

### Checkpoint 3: Second Deduplication
```python
if has_regulatory_in_group:
    # Prefer keeping a regulatory article
    best = select_best_with_regulatory_priority(group)
```

### Checkpoint 4: Statistics Tracking
```python
stats.regulatory_articles_found = count_at_category_filter
stats.regulatory_articles_retained = count_at_final_output

if found > retained:
    logger.warning("⚠️ Regulatory articles dropped!")
```

## Error Handling Strategy

### Philosophy
**Fail-safe**: When in doubt, keep the article

### Implementation
1. **LLM Errors**: Default to `pass=True`, `category=['technology']`
2. **Extraction Errors**: Fallback to lead paragraph
3. **Embedding Errors**: Return zero vector, skip similarity check
4. **JSON Parse Errors**: Use fallback values, log error
5. **Individual Article Errors**: Continue pipeline, don't abort

### Example
```python
try:
    result = llm_classify(article)
except Exception as e:
    logger.error(f"Classification failed: {e}")
    result = CategoryFilterResult(
        passed=True,  # Fail-safe
        categories=['technology'],
        reason="Error during classification"
    )
```

## Performance Considerations

### Bottlenecks
1. **Content Extraction**: newspaper4k download (rate-limited)
2. **Embedding Generation**: VertexAI API calls (batching possible)
3. **LLM Classification**: Multiple Gemini API calls (parallel possible)

### Optimization Strategies
```python
# Add delay between extractions
time.sleep(0.5)  # Avoid rate limits

# Batch embeddings (future enhancement)
embeddings = embedding_model.embed_documents(texts)

# Cache embeddings (future enhancement)
@lru_cache(maxsize=1000)
def get_cached_embedding(text_hash):
    ...
```

### Estimated Execution Time
- 100 articles collected
- ~2 min collection
- ~5 min filtering (LLM calls)
- ~10 min extraction (rate-limited)
- ~3 min validation & analysis
- **Total**: ~20-25 minutes

## Logging Strategy

### Log Levels
```python
INFO:  Step boundaries, major events, counts
DEBUG: Individual article details, similarity scores
ERROR: Exceptions, failures (with traceback)
```

### Log Format
```python
# Step headers
logger.info("=" * 60)
logger.info("STEP 1: SMART COLLECTION & FIRST FILTERING")
logger.info("=" * 60)

# Progress indicators
logger.info(f"📰 Collecting from Naver News API...")
logger.info(f"✅ Collected {count} articles")

# Article-level
logger.info(f"📄 Filtering article {i}/{total}: {title[:60]}...")
logger.info(f"   ✅ PASS - Categories: {categories}")

# Warnings
logger.warning(f"⚠️ Regulatory articles dropped!")

# Errors
logger.error(f"❌ Error extracting content: {e}")
```

### Output Files
- `pipeline.log`: Detailed execution log
- `webex_messages_YYYYMMDD_HHMMSS.txt`: Final messages
- Console output: Progress and summary

## Testing Strategy

### Unit Tests (Future)
```python
def test_first_deduplication():
    articles = [
        NewsArticle(title="AI 혁신", lead="..."),
        NewsArticle(title="인공지능 혁신", lead="...")  # Similar
    ]
    collector = NewsCollector()
    result = collector._first_deduplication(articles)
    assert len(result) == 1

def test_regulatory_protection():
    result = CategoryFilterResult(
        article=article,
        passed=True,
        categories=['regulation'],
        reason="test"
    )
    assert result.must_keep_for_regulation() == True
```

### Integration Tests
```bash
# Run with test API keys
export GOOGLE_API_KEY=test_key
python -m pipeline.news_pipeline

# Verify output
assert file_exists("webex_messages_*.txt")
assert stats.regulatory_articles_found == stats.regulatory_articles_retained
```

### Manual Testing Checklist
- [ ] Naver API returns articles
- [ ] Google API returns articles (if configured)
- [ ] First deduplication reduces count
- [ ] Category filter marks regulatory as must-keep
- [ ] Content extraction succeeds (or falls back)
- [ ] Second deduplication reduces count
- [ ] Value validation keeps regulatory articles
- [ ] Lotte analysis generates impact areas
- [ ] Webex messages follow strict format
- [ ] Stats show regulatory articles protected

## Deployment Guide

### Windows Task Scheduler
1. Create `run_pipeline.bat`:
   ```batch
   @echo off
   cd C:\path\to\test
   call venv\Scripts\activate
   python run_pipeline.py >> pipeline_cron.log 2>&1
   ```

2. Schedule task:
   - Trigger: Daily at 9:00 AM
   - Action: Run `run_pipeline.bat`
   - Settings: Run whether user is logged on or not

### Linux Cron
```bash
# Edit crontab
crontab -e

# Add daily execution at 9 AM
0 9 * * * cd /path/to/test && ./venv/bin/python run_pipeline.py >> pipeline_cron.log 2>&1
```

### Monitoring
```bash
# Check execution status
tail -f pipeline.log

# Check for errors
grep ERROR pipeline.log

# Verify regulatory protection
grep "regulatory" pipeline.log | grep -i "drop\|lost"
```

## Troubleshooting

### Issue: No articles collected
**Cause**: API credentials invalid or rate limit exceeded
**Solution**: 
```bash
# Test Naver API
curl "https://openapi.naver.com/v1/search/news.json?query=AI&display=10" \
  -H "X-Naver-Client-Id: YOUR_ID" \
  -H "X-Naver-Client-Secret: YOUR_SECRET"

# Check rate limits in API console
```

### Issue: All articles filtered out
**Cause**: LLM too strict or search keyword too broad
**Solution**:
```python
# Increase temperature in config.py
LLM_TEMPERATURE = 0.2  # Was 0.1

# Or broaden categories, check prompts in filtering.py
```

### Issue: Regulatory articles dropped
**Cause**: Critical bug, investigate immediately
**Solution**:
```bash
# Check logs for regulatory articles
grep "regulatory" pipeline.log

# Trace specific article through pipeline
grep "article_title" pipeline.log

# Verify must_keep_for_regulation() logic
```

### Issue: Embedding generation fails
**Cause**: GCP authentication or VertexAI API disabled
**Solution**:
```bash
# Re-authenticate
gcloud auth application-default login

# Enable VertexAI API
gcloud services enable aiplatform.googleapis.com

# Check quota
gcloud compute project-info describe --project=YOUR_PROJECT
```

## Future Enhancements

### High Priority
- [ ] Batch embedding generation (reduce API calls)
- [ ] Embedding caching (avoid recomputation)
- [ ] Parallel LLM classification (speed up filtering)
- [ ] Database storage (track historical articles)

### Medium Priority
- [ ] Multi-language support (English news)
- [ ] Custom company watchlist
- [ ] Sentiment analysis
- [ ] Trend detection (rising topics)

### Low Priority
- [ ] Web UI for manual review
- [ ] Slack integration
- [ ] Email digest option
- [ ] Historical analysis dashboard
