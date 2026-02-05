"""
Cloud Storage integration for archiving pipeline results.
"""
import os
import json
import logging
from datetime import datetime
from typing import List
from google.cloud import storage

from .models import LotteContextAnalysis, WebexMessage

logger = logging.getLogger(__name__)


class CloudStorageArchive:
    """Save pipeline results to Google Cloud Storage."""
    
    def __init__(self, bucket_name: str = "lotte-ai-news-archive"):
        """
        Initialize Cloud Storage client.
        
        Args:
            bucket_name: GCS bucket name for storing results
        """
        self.bucket_name = bucket_name
        self.client = None
        self.bucket = None
        
        try:
            self.client = storage.Client()
            self.bucket = self.client.bucket(bucket_name)
            logger.info(f"✅ Cloud Storage connected: {bucket_name}")
        except Exception as e:
            logger.warning(f"⚠️  Cloud Storage initialization failed: {e}")
            logger.warning("   Results will not be archived to GCS")
    
    def save_results(
        self,
        articles: List[LotteContextAnalysis],
        messages: List[WebexMessage],
        stats: dict = None
    ) -> bool:
        """
        Save pipeline results to Cloud Storage.
        
        Args:
            articles: Analyzed articles with Lotte context
            messages: Generated Webex messages
            stats: Pipeline statistics
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client or not self.bucket:
            logger.debug("Cloud Storage not configured, skipping archive")
            return False
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            date_prefix = datetime.now().strftime('%Y/%m/%d')
            
            # Save analyzed articles (JSON)
            articles_data = [
                {
                    'title': a.title,
                    'url': a.url,
                    'published_date': a.published_date.isoformat() if a.published_date else None,
                    'source': a.source,
                    'industry_relevance': a.industry_relevance,
                    'value_score': a.value_score,
                    'impact_areas': a.impact_areas,
                    'use_case_summary': a.use_case_summary,
                    'competitive_advantage': a.competitive_advantage,
                    'implementation_difficulty': a.implementation_difficulty,
                    'potential_partners': a.potential_partners,
                    'lotte_context': a.lotte_context,
                    'content': a.content[:500] + '...' if len(a.content) > 500 else a.content  # Truncate long content
                }
                for a in articles
            ]
            
            articles_blob = self.bucket.blob(f"articles/{date_prefix}/articles_{timestamp}.json")
            articles_blob.upload_from_string(
                json.dumps(articles_data, ensure_ascii=False, indent=2),
                content_type='application/json'
            )
            logger.info(f"   📁 Saved {len(articles)} articles to: articles/{date_prefix}/articles_{timestamp}.json")
            
            # Save Webex messages (TXT)
            messages_content = "\n\n" + "="*80 + "\n\n".join(
                [f"Message {i+1}/{len(messages)}:\n{m.text}" for i, m in enumerate(messages)]
            )
            
            messages_blob = self.bucket.blob(f"messages/{date_prefix}/webex_{timestamp}.txt")
            messages_blob.upload_from_string(
                messages_content,
                content_type='text/plain; charset=utf-8'
            )
            logger.info(f"   📁 Saved {len(messages)} messages to: messages/{date_prefix}/webex_{timestamp}.txt")
            
            # Save statistics (JSON)
            if stats:
                stats_blob = self.bucket.blob(f"stats/{date_prefix}/stats_{timestamp}.json")
                stats_blob.upload_from_string(
                    json.dumps(stats, ensure_ascii=False, indent=2),
                    content_type='application/json'
                )
                logger.info(f"   📁 Saved statistics to: stats/{date_prefix}/stats_{timestamp}.json")
            
            logger.info(f"✅ Cloud Storage archive complete")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to save to Cloud Storage: {e}", exc_info=True)
            return False
    
    def list_archives(self, days: int = 7) -> List[str]:
        """
        List recent archives in Cloud Storage.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of archive paths
        """
        if not self.client or not self.bucket:
            return []
        
        try:
            blobs = self.client.list_blobs(
                self.bucket_name,
                prefix="articles/"
            )
            
            archives = []
            for blob in blobs:
                if blob.name.endswith('.json'):
                    archives.append(blob.name)
            
            return sorted(archives, reverse=True)[:days]
            
        except Exception as e:
            logger.error(f"Failed to list archives: {e}")
            return []
