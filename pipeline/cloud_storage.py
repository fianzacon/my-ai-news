"""
Cloud Storage integration for archiving pipeline results.
"""
import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from google.cloud import storage

from .models import LotteContextAnalysis, WebexMessage

logger = logging.getLogger(__name__)

class CloudStorageArchive:
    """Save pipeline results to Google Cloud Storage."""
    
    def __init__(self, bucket_name: str = "lotte-ai-news-archive"):
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
    
    def save_daily_results(
        self,
        articles: List[LotteContextAnalysis],
        messages: List[WebexMessage],
        stats: dict = None
    ) -> bool:
        """
        [Stage 1: 자정 실행용] 전체 결과를 하나의 JSON 파일로 GCS에 저장합니다.
        """
        if not self.client or not self.bucket:
            logger.debug("Cloud Storage not configured, skipping archive")
            return False
        
        try:
            date_str = datetime.now().strftime('%Y%m%d')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            result_data = {
                'date': date_str,
                'timestamp': timestamp,
                'analyzed_articles': [],
                'webex_messages': [],
                'stats': stats or {}
            }
            
            # Articles 데이터 변환 (안전하게 추출)
            for context in articles:
                # 1. 원본 기사 객체 찾기 (article, original_article, 또는 context 자체)
                article_obj = getattr(context, 'article', None) or getattr(context, 'original_article', None) or context
                
                # 2. 데이터 추출 (없으면 기본값)
                article_data = {
                    'title': getattr(article_obj, 'title', 'No Title'),
                    'url': getattr(article_obj, 'url', ''),
                    'published_date': article_obj.published_date.isoformat() if hasattr(article_obj, 'published_date') and article_obj.published_date else None,
                    'source': getattr(article_obj, 'source', 'Unknown'),
                    'full_content': getattr(article_obj, 'content', '')[:1000] if hasattr(article_obj, 'content') else '',
                    'lotte_context': {
                        'impact_type': getattr(context, 'impact_type', ''),
                        'impact_areas': getattr(context, 'impact_areas', []),
                        'reasoning': getattr(context, 'reasoning', ''),
                        'industry_relevance': getattr(context, 'industry_relevance', ''),
                        'industry_category': getattr(context, 'industry_category', '')
                    }
                }
                result_data['analyzed_articles'].append(article_data)
            
            # Messages 데이터 변환
            for msg in messages:
                result_data['webex_messages'].append({
                    'text': msg.text,
                    'priority': getattr(msg, 'priority', 'INFO')
                })
            
            # GCS 저장
            blob_path = f"daily_results/{date_str}/results_{timestamp}.json"
            blob = self.bucket.blob(blob_path)
            blob.upload_from_string(
                json.dumps(result_data, ensure_ascii=False, indent=2),
                content_type='application/json'
            )
            
            logger.info(f"✅ Saved to GCS: gs://{self.bucket_name}/{blob_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to save to GCS: {e}", exc_info=True)
            return False

    def load_daily_results(self, date_str: Optional[str] = None) -> Optional[Dict]:
        """
        [Stage 2: 오전 9시 실행용] 특정 날짜의 가장 최신 결과를 GCS에서 로드합니다.
        """
        if not self.client or not self.bucket:
            logger.error("Cloud Storage not connected")
            return None

        try:
            if date_str is None:
                date_str = datetime.now().strftime('%Y%m%d')
            
            prefix = f"daily_results/{date_str}/"
            logger.info(f"🔍 Searching GCS: gs://{self.bucket_name}/{prefix}")
            
            blobs = list(self.client.list_blobs(self.bucket_name, prefix=prefix))
            json_blobs = [b for b in blobs if b.name.endswith('.json')]
            
            if not json_blobs:
                logger.warning(f"⚠️  No result files found for {date_str}")
                return None
            
            # 최신 파일 선택
            latest_blob = sorted(json_blobs, key=lambda x: x.updated, reverse=True)[0]
            logger.info(f"📄 Loading: {latest_blob.name}")
            
            content = latest_blob.download_as_text()
            result_data = json.loads(content)
            
            count = len(result_data.get('webex_messages', []))
            logger.info(f"✅ Loaded {count} messages from GCS")
            return result_data
            
        except Exception as e:
            logger.error(f"❌ Failed to load from GCS: {e}", exc_info=True)
            return None