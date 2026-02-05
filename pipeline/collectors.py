"""
STEP 1: News collection from Naver and Google News APIs with first deduplication.
"""
import logging
import requests
from datetime import datetime, timedelta
from typing import List, Dict
from urllib.parse import quote
import time

from .models import NewsArticle
from .config import PipelineConfig
from .utils import generate_embedding, generate_embeddings_batch, calculate_similarity, extract_lead_paragraph, create_text_hash

logger = logging.getLogger(__name__)


class NewsCollector:
    """Collects news from multiple sources and performs first deduplication."""
    
    def __init__(self):
        self.config = PipelineConfig()
        
    def collect_all(self) -> List[NewsArticle]:
        """
        Collect news from all sources and perform first deduplication.
        
        Returns:
            List of deduplicated NewsArticle objects
        """
        logger.info("=" * 60)
        logger.info("STEP 1: SMART COLLECTION & FIRST FILTERING")
        logger.info("=" * 60)
        
        all_articles = []
        keywords = self.config.SEARCH_KEYWORDS if isinstance(self.config.SEARCH_KEYWORDS, list) else [self.config.SEARCH_KEYWORDS]
        
        logger.info(f"🔍 Searching with {len(keywords)} keywords: {', '.join(keywords)}")
        
        for keyword in keywords:
            logger.info(f"\n📰 Keyword: '{keyword}'")
            
            # Collect from Naver
            logger.info("   → Naver News API...")
            naver_articles = self._collect_from_naver(keyword)
            logger.info(f"     Collected {len(naver_articles)} articles")
            all_articles.extend(naver_articles)
            
            # Collect from Google
            logger.info("   → Google News API...")
            google_articles = self._collect_from_google(keyword)
            logger.info(f"     Collected {len(google_articles)} articles")
            all_articles.extend(google_articles)
            
            # 💾 Save collected articles immediately after each keyword
            self._save_keyword_results(keyword, naver_articles, google_articles)
        
        logger.info(f"\n✅ Total collected: {len(all_articles)} articles")
        
        # First deduplication
        logger.info("\n🔍 Performing first deduplication (title + lead paragraph)...")
        deduplicated = self._first_deduplication(all_articles)
        logger.info(f"✅ After deduplication: {len(deduplicated)} articles (removed {len(all_articles) - len(deduplicated)})")
        
        return deduplicated
    
    def _collect_from_naver(self, keyword: str = "AI") -> List[NewsArticle]:
        """
        Collect news from Naver News API (yesterday's articles only).
        Uses pagination to ensure we get yesterday's articles even if many articles published today.
        
        Returns:
            List of NewsArticle objects
        """
        articles = []
        
        if not self.config.NAVER_CLIENT_ID or not self.config.NAVER_CLIENT_SECRET:
            logger.warning("Naver API credentials not found, skipping Naver collection")
            return articles
        
        # Calculate yesterday's date range (Korea Time - UTC+9)
        from datetime import timezone
        # Use Korea timezone for comparison
        kst = timezone(timedelta(hours=9))
        now_kst = datetime.now(kst)
        yesterday_kst = now_kst - timedelta(days=1)
        yesterday_start = yesterday_kst.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_end = yesterday_kst.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # For logging (without timezone info)
        yesterday_display = yesterday_kst.strftime('%Y-%m-%d')
        
        url = "https://openapi.naver.com/v1/search/news.json"
        headers = {
            "X-Naver-Client-Id": self.config.NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": self.config.NAVER_CLIENT_SECRET
        }
        
        # Pagination settings
        page = 1
        max_pages = 10  # Naver API limit: start parameter max is 1000 (10 pages)
        min_yesterday_target = 30  # Target at least 30 yesterday articles
        display_per_page = 100
        
        logger.info(f"     📅 Target: {yesterday_display} (yesterday)")
        logger.info(f"     🔄 Searching through available pages...")
        logger.info(f"     ⚠️  Note: Naver API limits to 1000 results per query")
        
        while page <= max_pages:
            start_index = (page - 1) * display_per_page + 1
            
            params = {
                "query": keyword,
                "display": display_per_page,
                "start": start_index,
                "sort": "date"  # Most recent first
            }
            
            try:
                response = requests.get(url, headers=headers, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                items = data.get('items', [])
                
                if not items:
                    logger.info(f"        Page {page}: No more articles available")
                    break
                
                # Count articles by date category
                today_count = 0
                yesterday_count = 0
                older_count = 0
                page_articles = []
                
                for item in items:
                    # Parse date first
                    pub_date_str = item.get('pubDate', '')
                    pub_date = self._parse_naver_date(pub_date_str)
                    
                    # Make pub_date timezone-aware (KST) for comparison
                    if pub_date.tzinfo is None:
                        pub_date = pub_date.replace(tzinfo=kst)
                    
                    # DEBUG: Log first article date for debugging
                    if page == 1 and len(page_articles) == 0 and today_count == 0:
                        logger.info(f"        DEBUG: First article - pub_date={pub_date}, yesterday_end={yesterday_end}")
                    
                    # Categorize by date
                    if pub_date > yesterday_end:
                        today_count += 1
                    elif yesterday_start <= pub_date <= yesterday_end:
                        yesterday_count += 1
                        
                        # Extract lead paragraph from description
                        description = self._clean_html(item.get('description', ''))
                        lead = extract_lead_paragraph(description, self.config.LEAD_PARAGRAPH_SENTENCES)
                        
                        article = NewsArticle(
                            title=self._clean_html(item.get('title', '')),
                            url=item.get('link', ''),
                            published_date=pub_date,
                            source='naver',
                            media_name=None,  # Naver API doesn't provide this directly
                            lead_paragraph=lead
                        )
                        page_articles.append(article)
                    else:
                        older_count += 1
                
                logger.info(f"        Page {page}: today={today_count}, yesterday={yesterday_count}, older={older_count}")
                
                # Add yesterday's articles
                articles.extend(page_articles)
                
                # Early stopping conditions
                # 1. 한 페이지에 오래된 기사가 50개 이상이면 중단 (어제를 지나쳐서 더 오래된 기사들)
                if older_count >= 50:
                    logger.info(f"        ⏹️  Stopping: too many older articles in this page ({older_count})")
                    break
                
                # 2. 목표 개수를 달성했고 연속 2페이지에 어제 기사가 없으면 중단
                if len(articles) >= min_yesterday_target and yesterday_count == 0 and older_count > 0:
                    logger.info(f"        ⏹️  Stopping: reached target ({len(articles)} yesterday articles)")
                    break
                
                # 3. 어제 기사가 나타나기 시작했으면 계속 수집 (조기 중단 안 함)
                
                page += 1
                time.sleep(0.1)  # Rate limiting courtesy
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to collect from Naver page {page}: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error collecting from Naver page {page}: {e}")
                break
        
        logger.info(f"     ✅ Collected {len(articles)} yesterday articles from {page} pages")
        
        return articles
    
    def _collect_from_google(self, keyword: str = "AI") -> List[NewsArticle]:
        """
        Collect news from Google News API (using News API or custom scraper).
        
        Returns:
            List of NewsArticle objects
        """
        articles = []
        
        # Option 1: Use News API (newsapi.org) - requires API key
        if self.config.GOOGLE_NEWS_API_KEY:
            articles = self._collect_from_newsapi(keyword)
        else:
            logger.warning("Google News API key not found, skipping Google collection")
            # Option 2: Could implement RSS feed parsing or other methods
            pass
        
        return articles
    
    def _collect_from_newsapi(self, keyword: str = "AI") -> List[NewsArticle]:
        """
        Collect from News API (newsapi.org) - yesterday's articles only.
        
        Returns:
            List of NewsArticle objects
        """
        articles = []
        
        # Calculate yesterday's date for API parameters (Korea Time)
        from datetime import timezone
        kst = timezone(timedelta(hours=9))
        yesterday_kst = datetime.now(kst) - timedelta(days=1)
        yesterday_str = yesterday_kst.strftime('%Y-%m-%d')
        
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": keyword,
            "language": "ko",  # Korean articles
            "from": yesterday_str,  # Start date (yesterday)
            "to": yesterday_str,    # End date (yesterday)
            "sortBy": "publishedAt",
            "pageSize": min(100, self.config.MAX_ARTICLES_PER_SOURCE),
            "apiKey": self.config.GOOGLE_NEWS_API_KEY
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            items = data.get('articles', [])
            
            for item in items:
                # Extract lead paragraph
                description = item.get('description', '') or item.get('content', '')
                lead = extract_lead_paragraph(description, self.config.LEAD_PARAGRAPH_SENTENCES)
                
                # Parse date
                pub_date_str = item.get('publishedAt', '')
                pub_date = self._parse_iso_date(pub_date_str)
                
                article = NewsArticle(
                    title=item.get('title', ''),
                    url=item.get('url', ''),
                    published_date=pub_date,
                    source='google',
                    media_name=item.get('source', {}).get('name'),
                    lead_paragraph=lead
                )
                articles.append(article)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to collect from News API: {e}")
        except Exception as e:
            logger.error(f"Unexpected error collecting from News API: {e}")
        
        return articles
    
    def _first_deduplication(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """
        Remove duplicates based on title + lead paragraph semantic similarity.
        Threshold: 85% similarity
        Keep the article with more concrete and informative content.
        
        Args:
            articles: List of collected articles
            
        Returns:
            Deduplicated list
        """
        if not articles:
            return []
        
        # Generate hashes and prepare texts for batch embedding
        logger.info(f"   [Step 1a] Preparing {len(articles)} articles for deduplication...")
        texts_for_embedding = []
        for article in articles:
            combined_text = f"{article.title} {article.lead_paragraph or ''}"
            article.title_lead_hash = create_text_hash(combined_text)
            texts_for_embedding.append(combined_text)
        
        # Generate embeddings in batches (MUCH FASTER - single API call per batch)
        logger.info(f"   [Step 1b] Generating embeddings in batches...")
        embeddings = generate_embeddings_batch(texts_for_embedding)
        
        # Check if embedding generation failed
        if embeddings is None or all(sum(emb) == 0 for emb in embeddings):
            logger.error("⚠️  WARNING: Embedding generation failed - falling back to hash-based deduplication")
            logger.error("⚠️  This may result in reduced deduplication quality")
            return self._hash_based_deduplication(articles)
        
        # Create embedding lookup dictionary
        embedding_map = {articles[i].title_lead_hash: embeddings[i] for i in range(len(articles))}
        
        # Group similar articles
        logger.info(f"   [Step 1c] Comparing articles for similarity (threshold: {self.config.FIRST_DEDUP_THRESHOLD})...")
        unique_articles = []
        processed_hashes = set()
        
        for i, article in enumerate(articles):
            if article.title_lead_hash in processed_hashes:
                continue
            
            # Get precomputed embedding
            current_embedding = embedding_map[article.title_lead_hash]
            
            # Find all similar articles
            similar_group = [article]
            
            for j in range(i + 1, len(articles)):
                other = articles[j]
                if other.title_lead_hash in processed_hashes:
                    continue
                
                # Use precomputed embedding (already generated in batch above)
                other_embedding = embedding_map[other.title_lead_hash]
                
                similarity = calculate_similarity(current_embedding, other_embedding)
                
                if similarity >= self.config.FIRST_DEDUP_THRESHOLD:
                    similar_group.append(other)
                    processed_hashes.add(other.title_lead_hash)
            
            # Keep the most informative article from the group
            best_article = self._select_most_informative(similar_group)
            unique_articles.append(best_article)
            processed_hashes.add(article.title_lead_hash)
            
            if len(similar_group) > 1:
                logger.debug(f"   Found {len(similar_group)} similar articles, kept: {best_article.title[:50]}...")
        
        return unique_articles
    
    def _select_most_informative(self, articles: List[NewsArticle]) -> NewsArticle:
        """
        From a group of similar articles, select the most informative one.
        Criteria: longest lead paragraph (more detail), prefer specific media names.
        
        Args:
            articles: Group of similar articles
            
        Returns:
            The most informative article
        """
        if len(articles) == 1:
            return articles[0]
        
        # Score each article
        scored = []
        for article in articles:
            score = 0
            
            # Longer lead paragraph = more detail
            if article.lead_paragraph:
                score += len(article.lead_paragraph)
            
            # Prefer articles with media name specified
            if article.media_name:
                score += 100
            
            # Prefer more recent articles (small bonus)
            # Handle both timezone-aware and timezone-naive datetimes
            try:
                now = datetime.now()
                if article.published_date.tzinfo is not None:
                    # Make now timezone-aware to match article.published_date
                    from datetime import timezone
                    now = datetime.now(timezone.utc)
                score += (now - article.published_date).days * -1
            except (TypeError, AttributeError):
                # Skip date comparison if there's an issue
                pass
            
            scored.append((score, article))
        
        # Return highest scoring article
        scored.sort(reverse=True, key=lambda x: x[0])
        return scored[0][1]
    
    def _hash_based_deduplication(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """
        Fallback deduplication using text hashing when embeddings fail.
        Uses normalized title comparison with 80% similarity threshold.
        """
        logger.info("   [Fallback] Using hash-based deduplication...")
        unique_articles = []
        seen_hashes = set()
        
        for article in articles:
            # Normalize title for comparison
            normalized_title = article.title.lower().strip()
            normalized_title = ''.join(c for c in normalized_title if c.isalnum() or c.isspace())
            title_hash = create_text_hash(normalized_title)
            
            # Check if similar title already seen
            is_duplicate = False
            if title_hash in seen_hashes:
                # Find matching article by hash
                matching_articles = [a for a in unique_articles if create_text_hash(a.title.lower().strip()) == title_hash]
                if matching_articles:
                    # Double-check with string similarity
                    if self._string_similarity(article.title, matching_articles[0].title) > 0.8:
                        is_duplicate = True
            
            if not is_duplicate:
                unique_articles.append(article)
                seen_hashes.add(title_hash)
        
        logger.info(f"   Hash-based dedup: {len(articles)} → {len(unique_articles)}")
        return unique_articles
    
    @staticmethod
    def _string_similarity(s1: str, s2: str) -> float:
        """Calculate simple character-level similarity between two strings."""
        if not s1 or not s2:
            return 0.0
        s1_set = set(s1.lower())
        s2_set = set(s2.lower())
        intersection = len(s1_set & s2_set)
        union = len(s1_set | s2_set)
        return intersection / union if union > 0 else 0.0
    
    @staticmethod
    def _clean_html(text: str) -> str:
        """Remove HTML tags from text."""
        import re
        clean = re.compile('<.*?>')
        return re.sub(clean, '', text)
    
    @staticmethod
    def _parse_naver_date(date_str: str) -> datetime:
        """Parse Naver date format: 'Wed, 26 Jan 2026 12:00:00 +0900'"""
        try:
            # Parse with timezone
            from datetime import timezone
            # Remove day name if present
            if ',' in date_str:
                date_str = date_str.split(',', 1)[1].strip()
            
            # Parse: "29 Jan 2026 12:00:00 +0900"
            # Extract timezone offset
            if '+' in date_str or date_str.count('-') > 2:
                parts = date_str.rsplit(' ', 1)
                date_part = parts[0]
                tz_str = parts[1] if len(parts) > 1 else '+0900'
                
                # Parse timezone offset
                if tz_str.startswith('+') or (tz_str.startswith('-') and len(tz_str) == 5):
                    sign = 1 if tz_str[0] == '+' else -1
                    hours = int(tz_str[1:3])
                    minutes = int(tz_str[3:5])
                    tz_offset = timezone(timedelta(hours=sign*hours, minutes=sign*minutes))
                else:
                    tz_offset = timezone(timedelta(hours=9))  # Default to KST
                
                dt = datetime.strptime(date_part, '%d %b %Y %H:%M:%S')
                return dt.replace(tzinfo=tz_offset)
            else:
                # No timezone info, assume KST
                dt = datetime.strptime(date_str.strip(), '%d %b %Y %H:%M:%S')
                return dt.replace(tzinfo=timezone(timedelta(hours=9)))
        except Exception as e:
            logger.warning(f"Date parse error: {date_str} - {e}")
            return datetime.now(timezone(timedelta(hours=9)))
    
    @staticmethod
    def _parse_iso_date(date_str: str) -> datetime:
        """Parse ISO date format: '2026-01-26T12:00:00Z'"""
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except Exception:
            return datetime.now()
    
    def _save_keyword_results(self, keyword: str, naver_articles: List[NewsArticle], google_articles: List[NewsArticle]):
        """Save collected articles immediately after each keyword collection."""
        import json
        from pathlib import Path
        from datetime import date
        
        # Create results directory
        results_dir = Path("keyword_results")
        results_dir.mkdir(exist_ok=True)
        
        # Create filename with today's date and keyword
        today = date.today()
        safe_keyword = keyword.replace(' ', '_').replace('/', '_')
        filename = results_dir / f"collected_{today.strftime('%Y%m%d')}_{safe_keyword}.json"
        
        # Prepare data
        data = {
            'keyword': keyword,
            'collection_time': datetime.now().isoformat(),
            'naver_count': len(naver_articles),
            'google_count': len(google_articles),
            'naver_articles': [
                {
                    'title': article.title,
                    'url': article.url,
                    'published_date': article.published_date.isoformat() if article.published_date else None,
                    'source': article.source,
                    'media_name': article.media_name,
                    'lead_paragraph': article.lead_paragraph
                }
                for article in naver_articles
            ],
            'google_articles': [
                {
                    'title': article.title,
                    'url': article.url,
                    'published_date': article.published_date.isoformat() if article.published_date else None,
                    'source': article.source,
                    'media_name': article.media_name,
                    'lead_paragraph': article.lead_paragraph
                }
                for article in google_articles
            ]
        }
        
        # Save to file
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"     💾 Saved to: {filename}")
