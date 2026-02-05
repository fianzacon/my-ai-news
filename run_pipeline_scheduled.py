"""
Scheduled pipeline runner with Webex integration.

TWO-STAGE EXECUTION:
1. Stage 1 (00:00 midnight): Collect yesterday's articles and save to JSON
   - At midnight, "today" articles = 0, so yesterday articles appear on page 1
   - This bypasses Naver API's 1000-result limit
2. Stage 2 (09:00 AM): Read saved JSON and send to Webex

Usage:
  - Run at 00:00: python run_pipeline_scheduled.py --stage collect
  - Run at 09:00: python run_pipeline_scheduled.py --stage send
"""
import sys
import os
import json
import argparse
from datetime import datetime, date
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline.news_pipeline import NewsIntelligencePipeline
from pipeline.webex_sender import WebexSender
from pipeline.config import PipelineConfig
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pipeline_scheduled.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Directory to store daily results
RESULTS_DIR = Path("daily_results")
RESULTS_DIR.mkdir(exist_ok=True)


def collect_stage():
    """Stage 1: Collect articles at midnight and save to JSON."""
    try:
        logger.info("="*60)
        logger.info("🌙 STAGE 1: MIDNIGHT COLLECTION (00:00)")
        logger.info("="*60)
        logger.info("💡 At midnight, 'today' articles = 0, so yesterday articles appear on page 1")
        logger.info("   This bypasses Naver API's 1000-result limit!\n")
        
        # Run pipeline
        logger.info("📊 Running AI news collection pipeline...")
        pipeline = NewsIntelligencePipeline()
        webex_messages, analyzed_articles, stats = pipeline.run(save_output=True)
        
        logger.info(f"✅ Pipeline complete: {len(webex_messages)} messages generated")
        
        # Save results to JSON for later Webex sending
        today = date.today()
        result_file = RESULTS_DIR / f"results_{today.strftime('%Y%m%d')}.json"
        
        # Convert analyzed articles to serializable format
        articles_data = []
        for lotte_context in analyzed_articles:
            # analyzed_articles는 List[LotteContextAnalysis]
            article = lotte_context.article
            
            # Serialize lotte_context
            lotte_context_data = {
                'impact_type': lotte_context.impact_type,
                'impact_areas': lotte_context.impact_areas,
                'reasoning': lotte_context.reasoning,
                'industry_relevance': lotte_context.industry_relevance,
                'industry_category': lotte_context.industry_category
            }
            
            articles_data.append({
                'title': article.title,
                'url': article.url,
                'published_date': article.published_date.isoformat() if article.published_date else None,
                'source': article.source,
                'media_name': article.media_name,
                'lead_paragraph': article.lead_paragraph,
                'lotte_context': lotte_context_data
            })
        
        # Convert WebexMessage objects to dict
        messages_data = []
        for msg in webex_messages:
            messages_data.append({
                'article_url': msg.article_url,
                'key_summary': msg.key_summary,
                'company_entity': msg.company_entity,
                'action': msg.action
            })
        
        result_data = {
            'date': today.isoformat(),
            'collection_time': datetime.now().isoformat(),
            'webex_messages': messages_data,
            'analyzed_articles': articles_data,
            'stats': {
                'total_collected': stats.total_collected,
                'after_first_dedup': stats.after_first_dedup,
                'after_category_filter': stats.after_category_filter,
                'after_second_dedup': stats.after_second_dedup,
                'after_value_validation': stats.after_value_validation,
                'final_output_count': stats.final_output_count,
                'regulatory_articles_found': stats.regulatory_articles_found,
                'regulatory_articles_retained': stats.regulatory_articles_retained
            }
        }
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n💾 Results saved to: {result_file}")
        logger.info("="*60)
        logger.info("✅ STAGE 1 COMPLETED - Articles ready for 9AM delivery")
        logger.info("="*60)
        stats.print_summary()
        
        return 0
    
    except Exception as e:
        logger.error(f"\n❌ STAGE 1 FAILED: {e}", exc_info=True)
        return 1


def send_stage():
    """Stage 2: Read saved JSON and send to Webex at 9AM."""
    try:
        logger.info("="*60)
        logger.info("☀️  STAGE 2: MORNING DELIVERY (09:00)")
        logger.info("="*60)
        
        # Find today's result file
        today = date.today()
        result_file = RESULTS_DIR / f"results_{today.strftime('%Y%m%d')}.json"
        
        if not result_file.exists():
            logger.error(f"❌ No results file found: {result_file}")
            logger.error("   Make sure Stage 1 (midnight collection) ran successfully")
            return 1
        
        logger.info(f"📂 Loading results from: {result_file}")
        with open(result_file, 'r', encoding='utf-8') as f:
            result_data = json.load(f)
        
        webex_messages = result_data['webex_messages']
        logger.info(f"📊 Loaded {len(webex_messages)} messages from collection")
        logger.info(f"   Collection time: {result_data['collection_time']}")
        
        # Reconstruct analyses with industry_relevance for filtering
        from pipeline.models import LotteContextAnalysis
        analyses = []
        for article_data in result_data['analyzed_articles']:
            # Create a minimal object with industry_relevance for WebexSender filtering
            class AnalysisStub:
                def __init__(self, industry_relevance):
                    self.industry_relevance = industry_relevance
            
            analyses.append(AnalysisStub(article_data['lotte_context']['industry_relevance']))
        
        # Send to Webex (if configured)
        webex_bot_token = os.getenv('WEBEX_BOT_TOKEN')
        webex_room_id = os.getenv('WEBEX_ROOM_ID')
        
        if webex_bot_token and webex_room_id:
            logger.info("\n📤 Sending messages to Webex...")
            
            sender = WebexSender(
                bot_token=webex_bot_token,
                room_id=webex_room_id
            )
            
            # Send messages with industry_relevance for filtering
            result = sender.send_messages(
                messages=webex_messages,
                analyses=analyses,
                batch_mode='single'
            )
            
            logger.info(f"✅ Webex delivery complete: {result['success_count']}/{result['total']} succeeded")
        else:
            logger.warning("⚠️  Webex credentials not found - skipping Webex send")
            logger.warning("   Set WEBEX_BOT_TOKEN and WEBEX_ROOM_ID environment variables")
        
        logger.info("\n" + "="*60)
        logger.info("✅ STAGE 2 COMPLETED - Messages delivered to Webex")
        logger.info("="*60)
        
        # Print stats
        stats_data = result_data['stats']
        logger.info(f"\nPipeline Statistics:")
        logger.info(f"  Total collected: {stats_data['total_collected']}")
        logger.info(f"  After 1st dedup: {stats_data['after_first_dedup']}")
        logger.info(f"  After filtering: {stats_data['after_category_filter']}")
        logger.info(f"  After 2nd dedup: {stats_data['after_second_dedup']}")
        logger.info(f"  After validation: {stats_data['after_value_validation']}")
        logger.info(f"  Final output: {stats_data['final_output_count']}")
        
        return 0
    
    except Exception as e:
        logger.error(f"\n❌ STAGE 2 FAILED: {e}", exc_info=True)
        return 1


def main():
    """Main entry point with stage selection."""
    parser = argparse.ArgumentParser(description='Run scheduled AI news pipeline')
    parser.add_argument(
        '--stage',
        choices=['collect', 'send', 'both'],
        default='both',
        help='Stage to run: collect (00:00), send (09:00), or both (for testing)'
    )
    args = parser.parse_args()
    
    if args.stage == 'collect':
        return collect_stage()
    elif args.stage == 'send':
        return send_stage()
    else:  # both
        logger.info("🧪 TESTING MODE: Running both stages sequentially\n")
        exit_code = collect_stage()
        if exit_code == 0:
            logger.info("\n" + "="*60 + "\n")
            exit_code = send_stage()
        return exit_code


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
