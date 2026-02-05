"""
Scheduled execution script for AI news pipeline with TWO-STAGE EXECUTION:

TWO-STAGE EXECUTION:
1. Stage 1 (00:00 midnight): Collect yesterday's articles and save to GCS
   - At midnight, "today" articles = 0, so yesterday articles appear on page 1
   - This bypasses Naver API's 1000-result limit
2. Stage 2 (09:00 AM): Read saved results from GCS and send to Webex
   - Retrieve pre-analyzed articles from GCS
   - Send to Webex without re-analyzing
"""

import os
import sys
import logging
import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from pipeline.news_pipeline import run_pipeline
from pipeline.webex_sender import WebexSender
from pipeline.cloud_storage import CloudStorageArchive
from pipeline.models import WebexMessage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('pipeline_scheduled.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def collect_stage() -> bool:
    """
    Stage 1: Collect and analyze articles at midnight (00:00)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info("🌙 STAGE 1: MIDNIGHT COLLECTION (00:00)")
        logger.info("="*60)
        
        # Run pipeline
        logger.info("📊 Running AI news collection pipeline...")
        webex_messages, analyzed_articles, stats = run_pipeline(
            max_articles=1000,
            use_local_cache=False,
            send_to_webex=False  # Don't send yet
        )
        
        if not webex_messages:
            logger.warning("⚠️  No messages generated - pipeline may have failed")
            return False
        
        # Save to GCS
        logger.info("💾 Saving results to Cloud Storage...")
        archive = CloudStorageArchive("lotte-ai-news-archive")
        gcs_success = archive.save_daily_results(
            articles=analyzed_articles,
            messages=webex_messages,
            stats={
                'total_collected': stats.total_collected,
                'after_first_dedup': stats.after_first_dedup,
                'after_category_filter': stats.after_category_filter,
                'after_second_dedup': stats.after_second_dedup,
                'after_value_validation': stats.after_value_validation,
                'final_output_count': stats.final_output_count,
                'regulatory_articles_found': stats.regulatory_articles_found,
                'duration_seconds': stats.duration_seconds
            }
        )
        
        # Also save locally as backup
        logger.info("💾 Saving local backup...")
        date_str = datetime.now().strftime('%Y%m%d')
        output_dir = Path('daily_results')
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f'results_{date_str}.json'
        
        result_data = {
            'date': date_str,
            'timestamp': datetime.now().isoformat(),
            'analyzed_articles': [],
            'webex_messages': [],
            'stats': {
                'total_collected': stats.total_collected,
                'final_output_count': stats.final_output_count,
                'regulatory_articles_found': stats.regulatory_articles_found
            }
        }
        
        # Convert analyzed_articles
        for lotte_context in analyzed_articles:
            article = lotte_context.article
            result_data['analyzed_articles'].append({
                'title': article.title,
                'url': article.url,
                'published_date': article.published_date.isoformat() if article.published_date else None,
                'source': article.source,
                'lead_paragraph': article.lead_paragraph,
                'full_content': article.full_content[:500] if article.full_content else '',
                'lotte_context': {
                    'impact_type': lotte_context.impact_type,
                    'impact_areas': lotte_context.impact_areas,
                    'reasoning': lotte_context.reasoning,
                    'industry_relevance': lotte_context.industry_relevance,
                    'industry_category': lotte_context.industry_category
                }
            })
        
        # Convert webex_messages
        for msg in webex_messages:
            result_data['webex_messages'].append({
                'text': msg.text,
                'priority': msg.priority
            })
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Pipeline complete: {len(webex_messages)} messages generated")
        logger.info(f"   📁 GCS: {'✅ Saved' if gcs_success else '❌ Failed'}")
        logger.info(f"   📁 Local: {output_file}")
        logger.info(f"   📊 Stats: {stats.total_collected} collected → {stats.final_output_count} final")
        logger.info(f"   ⚖️  Regulatory: {stats.regulatory_articles_found} articles")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ STAGE 1 FAILED: {e}", exc_info=True)
        return False

def send_stage() -> bool:
    """
    Stage 2: Send pre-analyzed articles to Webex at 09:00 AM
    
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info("☀️  STAGE 2: MORNING TRANSMISSION (09:00)")
        logger.info("="*60)
        
        # Try to load from GCS first
        logger.info("📥 Loading results from Cloud Storage...")
        archive = CloudStorageArchive("lotte-ai-news-archive")
        result_data = archive.load_daily_results()
        
        # Fallback to local file if GCS fails
        if not result_data:
            logger.warning("⚠️  GCS load failed, trying local backup...")
            date_str = datetime.now().strftime('%Y%m%d')
            local_file = Path('daily_results') / f'results_{date_str}.json'
            
            if not local_file.exists():
                logger.error(f"❌ No results file found (neither GCS nor local)")
                return False
            
            with open(local_file, 'r', encoding='utf-8') as f:
                result_data = json.load(f)
            logger.info(f"✅ Loaded from local backup: {local_file}")
        
        # Reconstruct WebexMessage objects
        webex_messages = []
        for msg_data in result_data.get('webex_messages', []):
            webex_messages.append(WebexMessage(
                text=msg_data['text'],
                priority=msg_data.get('priority', 'INFO')
            ))
        
        if not webex_messages:
            logger.warning("⚠️  No messages to send")
            return False
        
        logger.info(f"📨 Sending {len(webex_messages)} messages to Webex...")
        
        # Send to Webex
        sender = WebexSender(
            room_id=os.getenv('WEBEX_ROOM_ID'),
            token=os.getenv('WEBEX_BOT_TOKEN')
        )
        
        # Create stub analyses for industry_relevance check
        class AnalysisStub:
            def __init__(self, relevance):
                self.industry_relevance = relevance
        
        analyses = [
            AnalysisStub(article.get('lotte_context', {}).get('industry_relevance', ''))
            for article in result_data.get('analyzed_articles', [])
        ]
        
        sender.send_batch(webex_messages, analyses=analyses)
        
        stats_data = result_data.get('stats', {})
        logger.info(f"✅ Transmission complete!")
        logger.info(f"   📊 Messages sent: {len(webex_messages)}")
        logger.info(f"   📈 Total collected: {stats_data.get('total_collected', 'N/A')}")
        logger.info(f"   🎯 Final output: {stats_data.get('final_output_count', 'N/A')}")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ STAGE 2 FAILED: {e}", exc_info=True)
        return False

def main():
    parser = argparse.ArgumentParser(description='Run AI news pipeline (scheduled)')
    parser.add_argument(
        '--stage',
        choices=['collect', 'send', 'both'],
        default='both',
        help='Pipeline stage to run'
    )
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info("🚀 AI NEWS PIPELINE - SCHEDULED EXECUTION")
    logger.info("="*60)
    logger.info(f"   Stage: {args.stage.upper()}")
    logger.info(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)
    
    success = True
    
    if args.stage in ['collect', 'both']:
        success = collect_stage()
        if not success:
            logger.error("❌ Collection stage failed")
            sys.exit(1)
    
    if args.stage in ['send', 'both']:
        success = send_stage()
        if not success:
            logger.error("❌ Send stage failed")
            sys.exit(1)
    
    logger.info("\n" + "="*60)
    logger.info("✅ PIPELINE EXECUTION COMPLETE")
    logger.info("="*60)

if __name__ == "__main__":
    main()