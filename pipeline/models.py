"""
Data models for the AI news intelligence pipeline.
"""
from dataclasses import dataclass, field
from typing import List, Literal, Optional
from datetime import datetime


@dataclass
class NewsArticle:
    """Raw news article from API."""
    title: str
    url: str
    published_date: datetime
    source: str  # 'naver' or 'google'
    media_name: Optional[str] = None
    lead_paragraph: Optional[str] = None  # First 2-3 sentences
    full_content: Optional[str] = None
    
    # Deduplication tracking
    title_lead_hash: Optional[str] = None
    content_embedding: Optional[List[float]] = None
    
    def __hash__(self):
        return hash(self.url)


@dataclass
class CategoryFilterResult:
    """Result from Step 2: Category filtering."""
    article: NewsArticle
    passed: bool
    categories: List[Literal['solution', 'case', 'technology', 'regulation']]
    reason: str
    
    def must_keep_for_regulation(self) -> bool:
        """Check if this is a regulatory article that must never be dropped."""
        return 'regulation' in self.categories


@dataclass
class ValueValidationResult:
    """Result from Step 4: Value validation."""
    article: NewsArticle
    has_business_value: bool
    reason: str
    is_regulatory: bool  # Flag to ensure regulatory articles are retained


@dataclass
class LotteContextAnalysis:
    """Result from Step 5: Lotte Members context interpretation."""
    article: NewsArticle
    impact_type: Literal['opportunity', 'threat', 'mixed', 'watchlist']
    impact_areas: List[Literal[
        'membership data usage',
        'targeting / segmentation',
        'advertising agency / data sales business',
        'online–offline linkage',
        'legal / compliance',
        'none'
    ]]
    reasoning: str
    
    # 🆕 Industry classification fields
    industry_relevance: Literal['direct', 'indirect'] = 'direct'  # Default to direct
    industry_category: Optional[str] = None  # e.g., 'retail-marketing', 'healthcare', 'manufacturing'


@dataclass
class WebexMessage:
    """Final output for Step 6: Webex message."""
    article_url: str
    key_summary: str  # 2-3 lines
    
    # Legacy fields (kept for compatibility but not displayed)
    company_entity: str = ""
    action: str = ""
    
    def format(self) -> str:
        """Generate the Webex-ready message (simplified)."""
        return f"""📰 **AI 뉴스 인텔리전스**

{self.key_summary}

🔗 {self.article_url}
"""


@dataclass
class PipelineStats:
    """Statistics for the entire pipeline run."""
    total_collected: int = 0
    after_first_dedup: int = 0
    after_category_filter: int = 0
    after_second_dedup: int = 0
    after_value_validation: int = 0
    final_output_count: int = 0
    
    regulatory_articles_found: int = 0
    regulatory_articles_retained: int = 0
    
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    def print_summary(self):
        """Print a human-readable summary."""
        print("\n" + "="*60)
        print("PIPELINE EXECUTION SUMMARY")
        print("="*60)
        print(f"Total collected: {self.total_collected}")
        print(f"After 1st dedup (title+lead): {self.after_first_dedup} (-{self.total_collected - self.after_first_dedup})")
        print(f"After category filter: {self.after_category_filter} (-{self.after_first_dedup - self.after_category_filter})")
        print(f"After 2nd dedup (content): {self.after_second_dedup} (-{self.after_category_filter - self.after_second_dedup})")
        print(f"After value validation: {self.after_value_validation} (-{self.after_second_dedup - self.after_value_validation})")
        print(f"Final output: {self.final_output_count}")
        print(f"\n⚖️  Regulatory articles: {self.regulatory_articles_found} found, {self.regulatory_articles_retained} retained")
        if self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
            print(f"⏱️  Duration: {duration:.2f} seconds")
        print("="*60 + "\n")
