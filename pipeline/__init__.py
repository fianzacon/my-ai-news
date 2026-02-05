"""
Pipeline package initialization.
"""

from .news_pipeline import NewsIntelligencePipeline, main
from .models import (
    NewsArticle, 
    CategoryFilterResult, 
    ValueValidationResult, 
    LotteContextAnalysis, 
    WebexMessage,
    PipelineStats
)
from .config import PipelineConfig

__version__ = "1.0.0"
__all__ = [
    "NewsIntelligencePipeline",
    "main",
    "NewsArticle",
    "CategoryFilterResult",
    "ValueValidationResult",
    "LotteContextAnalysis",
    "WebexMessage",
    "PipelineStats",
    "PipelineConfig"
]
