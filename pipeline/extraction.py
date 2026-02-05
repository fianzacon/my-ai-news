"""
STEP 3: Full text extraction and second deduplication based on content.
"""
import logging
from typing import List, Optional
from newspaper import Article as NewspaperArticle, Config
import time
import requests
from bs4 import BeautifulSoup

from .models import NewsArticle, CategoryFilterResult
from .config import PipelineConfig
from .utils import generate_embedding, calculate_similarity

logger = logging.getLogger(__name__)


class ContentExtractor:
    """Extract full article content and perform content-based deduplication."""
    
    def __init__(self):
        self.config = PipelineConfig()
        
        # Configure newspaper4k
        self.newspaper_config = Config()
        self.newspaper_config.browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        self.newspaper_config.request_timeout = 15
        self.newspaper_config.fetch_images = False
        self.newspaper_config.memoize_articles = False
        self.newspaper_config.language = 'ko'
    
    def extract_and_deduplicate(
        self, 
        filter_results: List[CategoryFilterResult]
    ) -> List[CategoryFilterResult]:
        """
        Extract full content and deduplicate based on full text similarity.
        
        Args:
            filter_results: Articles that passed category filtering
            
        Returns:
            Deduplicated list with full content extracted
        """
        logger.info("\n" + "=" * 60)
        logger.info("STEP 3: FULL TEXT EXTRACTION & SECOND DEDUPLICATION")
        logger.info("=" * 60)
        
        # Extract full content
        logger.info(f"\n📝 Extracting full content for {len(filter_results)} articles...")
        extracted = []
        extraction_failures = 0
        
        for i, result in enumerate(filter_results, 1):
            logger.info(f"   Extracting {i}/{len(filter_results)}: {result.article.title[:50]}...")
            
            try:
                full_content = self._extract_full_content(result.article)
                
                if full_content and len(full_content) > 100:
                    result.article.full_content = full_content
                    extracted.append(result)
                else:
                    # If extraction fails, use lead paragraph as fallback
                    logger.warning(f"      ⚠️  Extraction failed or content too short, using lead paragraph")
                    result.article.full_content = result.article.lead_paragraph or result.article.title
                    extracted.append(result)
                    extraction_failures += 1
                    
            except Exception as e:
                logger.error(f"      ❌ Error extracting content: {e}")
                # Use lead paragraph as fallback
                result.article.full_content = result.article.lead_paragraph or result.article.title
                extracted.append(result)
                extraction_failures += 1
            
            # Rate limiting
            time.sleep(0.5)
        
        logger.info(f"\n✅ Content extraction complete:")
        logger.info(f"   Successful: {len(extracted) - extraction_failures}/{len(filter_results)}")
        logger.info(f"   Fallback to lead: {extraction_failures}")
        
        # Second deduplication
        logger.info(f"\n🔍 Performing second deduplication (full content)...")
        deduplicated = self._second_deduplication(extracted)
        logger.info(f"✅ After deduplication: {len(deduplicated)} articles (removed {len(extracted) - len(deduplicated)})")
        
        return deduplicated
    
    def _extract_full_content(self, article: NewsArticle) -> str:
        """
        Extract full content from article URL.
        Tries multiple methods: newspaper4k, then BeautifulSoup fallback.
        
        Args:
            article: NewsArticle with URL
            
        Returns:
            Full article text
        """
        # Method 1: Try newspaper4k
        content = self._extract_with_newspaper(article)
        if content and len(content) >= 200:
            logger.debug(f"      ✓ newspaper4k: {len(content)} chars")
            return content
        
        # Method 2: Try BeautifulSoup
        content = self._extract_with_beautifulsoup(article)
        if content and len(content) >= 200:
            logger.debug(f"      ✓ BeautifulSoup: {len(content)} chars")
            return content
        
        logger.debug(f"      ✗ All methods failed")
        return ""
    
    def _extract_with_newspaper(self, article: NewsArticle) -> Optional[str]:
        """Extract using newspaper4k library."""
        try:
            news_article = NewspaperArticle(article.url, config=self.newspaper_config)
            news_article.download()
            news_article.parse()
            
            if news_article.text:
                # Update media name if available
                if not article.media_name and news_article.source_url:
                    article.media_name = news_article.source_url
                
                return news_article.text.strip()
            
            return None
            
        except Exception as e:
            logger.debug(f"      newspaper4k error: {str(e)[:50]}")
            return None
    
    def _extract_with_beautifulsoup(self, article: NewsArticle) -> Optional[str]:
        """Fallback extraction using BeautifulSoup with multiple selectors."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            }
            
            response = requests.get(article.url, headers=headers, timeout=10)
            response.raise_for_status()
            response.encoding = response.apparent_encoding  # Handle Korean encoding
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove unwanted elements
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
                tag.decompose()
            
            # Try common Korean news site selectors
            selectors = [
                # Naver
                '#articleBodyContents', '#articeBody', '.article_body', '#newsct_article',
                # Daum
                '.article_view', '#harmonyContainer',
                # Generic
                'article', '.article-body', '.article-content', '#article-body',
                '.news-content', '.article_body', 'div[itemprop="articleBody"]',
                '.post-content', '.entry-content',
            ]
            
            for selector in selectors:
                element = soup.select_one(selector)
                if element:
                    # Get text from all paragraphs within this element
                    paragraphs = element.find_all(['p', 'div'], recursive=True)
                    if paragraphs:
                        texts = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]
                        text = ' '.join(texts)
                        if len(text) >= 200:
                            return text
                    
                    # If no paragraphs, get direct text
                    text = element.get_text(separator=' ', strip=True)
                    if len(text) >= 200:
                        return text
            
            # Last resort: get all paragraphs
            paragraphs = soup.find_all('p')
            if paragraphs:
                text = ' '.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20])
                if len(text) >= 200:
                    return text
            
            return None
            
        except Exception as e:
            logger.debug(f"      BeautifulSoup error: {str(e)[:50]}")
            return None
    
    def _second_deduplication(
        self, 
        results: List[CategoryFilterResult]
    ) -> List[CategoryFilterResult]:
        """
        Remove duplicates based on full content semantic similarity.
        Threshold: 90% similarity
        
        CRITICAL: Regulatory articles must be carefully handled.
        If duplicates exist, keep at least one regulatory article.
        
        Args:
            results: List of articles with full content
            
        Returns:
            Deduplicated list
        """
        if not results:
            return []
        
        # Generate embeddings for full content
        logger.info("   Generating embeddings for full content...")
        for result in results:
            if result.article.full_content:
                embedding = generate_embedding(result.article.full_content)
                result.article.content_embedding = embedding
        
        # Group similar articles
        unique_results = []
        processed_urls = set()
        regulatory_kept = set()  # Track regulatory articles we've kept
        
        for i, result in enumerate(results):
            if result.article.url in processed_urls:
                continue
            
            current_embedding = result.article.content_embedding
            if not current_embedding:
                # If no embedding, keep it
                unique_results.append(result)
                processed_urls.add(result.article.url)
                continue
            
            # Find all similar articles
            similar_group = [result]
            has_regulatory = result.must_keep_for_regulation()
            
            for j in range(i + 1, len(results)):
                other = results[j]
                if other.article.url in processed_urls:
                    continue
                
                other_embedding = other.article.content_embedding
                if not other_embedding:
                    continue
                
                similarity = calculate_similarity(current_embedding, other_embedding)
                
                if similarity >= self.config.SECOND_DEDUP_THRESHOLD:
                    similar_group.append(other)
                    processed_urls.add(other.article.url)
                    
                    if other.must_keep_for_regulation():
                        has_regulatory = True
            
            # Select best article from group
            if has_regulatory:
                # If group contains regulatory articles, prefer keeping a regulatory one
                best = self._select_best_with_regulatory_priority(similar_group)
                logger.debug(f"   ⚖️  Regulatory group: kept {best.article.title[:40]}...")
            else:
                best = self._select_best_article(similar_group)
            
            unique_results.append(best)
            processed_urls.add(result.article.url)
            
            if len(similar_group) > 1:
                logger.debug(f"   Found {len(similar_group)} similar articles, kept: {best.article.title[:50]}...")
        
        return unique_results
    
    def _select_best_with_regulatory_priority(
        self, 
        results: List[CategoryFilterResult]
    ) -> CategoryFilterResult:
        """
        Select best article from a group, prioritizing regulatory articles.
        
        Args:
            results: Group of similar articles
            
        Returns:
            Best article with regulatory priority
        """
        # First, filter to regulatory articles if any exist
        regulatory = [r for r in results if r.must_keep_for_regulation()]
        
        if regulatory:
            # Among regulatory articles, pick the longest/most detailed
            return self._select_best_article(regulatory)
        else:
            # No regulatory articles, use normal selection
            return self._select_best_article(results)
    
    def _select_best_article(
        self, 
        results: List[CategoryFilterResult]
    ) -> CategoryFilterResult:
        """
        Select the best article from a group based on content quality.
        
        Args:
            results: Group of similar articles
            
        Returns:
            Best quality article
        """
        if len(results) == 1:
            return results[0]
        
        # Score each article
        scored = []
        for result in results:
            score = 0
            
            # Longer content = more detail
            if result.article.full_content:
                score += len(result.article.full_content)
            
            # Prefer articles with media name
            if result.article.media_name:
                score += 500
            
            # Bonus for multiple categories (more comprehensive)
            score += len(result.categories) * 100
            
            # Regulatory bonus (even if not specifically selecting for it)
            if result.must_keep_for_regulation():
                score += 1000
            
            scored.append((score, result))
        
        # Return highest scoring
        scored.sort(reverse=True, key=lambda x: x[0])
        return scored[0][1]
