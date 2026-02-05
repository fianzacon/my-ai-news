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
            articles_data = []
            for a in articles:
                # LotteContextAnalysis 객체 내부에 원본 기사 객체(article)가 있다고 가정
                # 만약 속성명이 'article'이 아니라면 'original_article' 등으로 변경 필요
                source_article = getattr(a, 'article', None) or getattr(a, 'original_article', None)
                
                # 안전 장치: 원본 기사 객체를 못 찾으면 분석 객체 자체(a)를 사용 시도
                target_obj = source_article if source_article else a
                
                article_dict = {
                    # 원본 기사 정보 (nested object에서 추출)
                    'title': getattr(target_obj, 'title', 'No Title'),
                    'url': getattr(target_obj, 'url', ''),
                    'published_date': target_obj.published_date.isoformat() if hasattr(target_obj, 'published_date') and target_obj.published_date else None,
                    'source': getattr(target_obj, 'source', 'Unknown'),
                    'content': getattr(target_obj, 'content', '')[:500] + '...' if getattr(target_obj, 'content', '') and len(getattr(target_obj, 'content', '')) > 500 else getattr(target_obj, 'content', ''),
                    
                    # AI 분석 결과 정보 (LotteContextAnalysis 객체에서 추출)
                    'industry_relevance': getattr(a, 'industry_relevance', None),
                    'value_score': getattr(a, 'value_score', 0),
                    'impact_areas': getattr(a, 'impact_areas', []),
                    'use_case_summary': getattr(a, 'use_case_summary', ''),
                    'competitive_advantage': getattr(a, 'competitive_advantage', ''),
                    'implementation_difficulty': getattr(a, 'implementation_difficulty', ''),
                    'potential_partners': getattr(a, 'potential_partners', []),
                    'lotte_context': getattr(a, 'lotte_context', '')
                }
                articles_data.append(article_dict)
            
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
