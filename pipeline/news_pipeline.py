"""
Main pipeline orchestrator for AI News Intelligence.

This pipeline collects, filters, analyzes, and formats AI news for Lotte Members.
"""
import logging
from datetime import datetime
from typing import Optional

from .models import PipelineStats
from .config import PipelineConfig
from .utils import setup_logging
from .collectors import NewsCollector
from .filtering import CategoryFilter
from .extraction import ContentExtractor
from .analysis import BusinessAnalyzer
from .output import WebexFormatter
from .partnership_db import PartnershipDatabaseGenerator
from .cloud_storage import CloudStorageArchive

logger = logging.getLogger(__name__)


class NewsIntelligencePipeline:
    """
    End-to-end AI news intelligence pipeline for Lotte Members.
    
    Steps:
    1. Collect from Naver & Google News APIs
    2. First deduplication (title + lead, 85% threshold)
    3. Category filtering (LLM-based pass/fail)
    4. Full content extraction
    5. Second deduplication (full content, 90% threshold)
    6. Value validation (business relevance)
    7. Lotte Members context analysis
    8. Webex message generation
    """
    
    def __init__(self):
        """Initialize pipeline components."""
        self.collector = NewsCollector()
        self.filter = CategoryFilter()
        self.extractor = ContentExtractor()
        self.analyzer = BusinessAnalyzer()
        self.formatter = WebexFormatter()
        self.partnership_db = PartnershipDatabaseGenerator()
        self.cloud_storage = CloudStorageArchive()
        self.stats = PipelineStats()
    
    def run(self, save_output: bool = True):
        """
        Execute the full pipeline.
        
        Args:
            save_output: Whether to save Webex messages to file
            
        Returns:
            Tuple of (webex_messages, analyzed_articles, stats)
        """
        logger.info("\n" + "=" * 60)
        logger.info("🚀 AI NEWS INTELLIGENCE PIPELINE - STARTING")
        logger.info(f"⏰ Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        try:
            # STEP 1: Collection & First Deduplication
            articles = self.collector.collect_all()
            # Note: collect_all() already returns deduplicated articles
            # The collector logs pre-dedup count internally
            self.stats.total_collected = len(articles)  # This is after first dedup
            self.stats.after_first_dedup = len(articles)
            
            if not articles:
                logger.warning("⚠️  No articles collected, pipeline stopping")
                return [], [], self.stats
            
            # STEP 2: Category Filtering
            filter_results = self.filter.filter_articles(articles)
            self.stats.after_category_filter = len(filter_results)
            self.stats.regulatory_articles_found = sum(
                1 for r in filter_results if r.must_keep_for_regulation()
            )
            
            if not filter_results:
                logger.warning("⚠️  No articles passed category filter, pipeline stopping")
                return [], [], self.stats
            
            # STEP 3: Content Extraction & Second Deduplication
            extracted_results = self.extractor.extract_and_deduplicate(filter_results)
            self.stats.after_second_dedup = len(extracted_results)
            
            if not extracted_results:
                logger.warning("⚠️  No articles after content deduplication, pipeline stopping")
                return [], [], self.stats
            
            # STEP 4 & 5: Value Validation & Lotte Context Analysis
            analyzed_articles = self.analyzer.validate_and_analyze(extracted_results)
            self.stats.after_value_validation = len(analyzed_articles)
            self.stats.regulatory_articles_retained = sum(
                1 for a in analyzed_articles 
                if 'legal / compliance' in a.impact_areas
            )
            
            if not analyzed_articles:
                logger.warning("⚠️  No articles passed value validation, pipeline stopping")
                return [], [], self.stats
            
            # STEP 6: Webex Message Generation
            webex_messages = self.formatter.generate_messages(analyzed_articles)
            self.stats.final_output_count = len(webex_messages)
            
            # Save output
            if save_output and webex_messages:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename_prefix = f"webex_messages"
                self.formatter.save_messages_to_file(analyzed_articles, webex_messages, filename_prefix)
            
            # STEP 7: Partnership Database Generation
            if save_output and analyzed_articles:
                logger.info("\n")
                companies = self.partnership_db.generate_database(analyzed_articles)
                
                if companies:
                    timestamp = datetime.now().strftime('%Y%m%d')
                    db_filename = f"collaboration_partners_{timestamp}.md"
                    self.partnership_db.save_to_markdown(companies, db_filename)
            
            # STEP 8: Cloud Storage Archive

            if analyzed_articles and webex_messages:
                logger.info("\n" + "=" * 60)
                logger.info("STEP 8: CLOUD STORAGE ARCHIVE")
                logger.info("=" * 60)
                
                stats_dict = {
                    'timestamp': datetime.now().isoformat(),
                    'total_collected': self.stats.total_collected,
                    'after_first_dedup': self.stats.after_first_dedup,
                    'after_category_filter': self.stats.after_category_filter,
                    'after_second_dedup': self.stats.after_second_dedup,
                    'after_value_validation': self.stats.after_value_validation,
                    'final_output_count': self.stats.final_output_count,
                    'regulatory_articles_found': self.stats.regulatory_articles_found,
                    'regulatory_articles_retained': self.stats.regulatory_articles_retained
                }
                
                # save_results → save_daily_results로 변경
                self.cloud_storage.save_daily_results(
                    articles=analyzed_articles,
                    messages=webex_messages,
                    stats=stats_dict
                )
            
            # Mark completion
            self.stats.end_time = datetime.now()
            
            return webex_messages, analyzed_articles, self.stats
            

        except KeyboardInterrupt:
            logger.info("\n⚠️  Pipeline interrupted by user")
            self.stats.end_time = datetime.now()
            raise  # 즉시 중단
            
        except Exception as e:
            logger.error(f"\n❌ Pipeline failed with error: {e}", exc_info=True)
            self.stats.end_time = datetime.now()
            raise  # 에러를 다시 throw해서 컨테이너 즉시 종료
        
        finally:
            # Always print summary
            self.stats.print_summary()


def main():
    """Main entry point for the pipeline."""
    # Setup logging
    setup_logging()
    
    logger.info("Initializing AI News Intelligence Pipeline for Lotte Members")
    logger.info(f"Configuration: {PipelineConfig.LLM_MODEL}, "
                f"Dedup thresholds: {PipelineConfig.FIRST_DEDUP_THRESHOLD}/{PipelineConfig.SECOND_DEDUP_THRESHOLD}")
    
    try:
        # Validate configuration
        PipelineConfig.validate()
        
        # Run pipeline
        pipeline = NewsIntelligencePipeline()
        webex_messages, analyzed_articles, stats = pipeline.run(save_output=True)
        
        # Check for critical warnings
        if stats.regulatory_articles_found > stats.regulatory_articles_retained:
            logger.warning(f"\n⚠️  WARNING: Some regulatory articles may have been dropped!")
            logger.warning(f"   Found: {stats.regulatory_articles_found}, Retained: {stats.regulatory_articles_retained}")
        
        if stats.final_output_count == 0:
            logger.warning("\n⚠️  WARNING: Pipeline produced no output messages!")
        else:
            logger.info(f"\n✅ Pipeline completed successfully with {stats.final_output_count} messages")
        
        return stats
        
    except Exception as e:
        logger.error(f"Fatal error in pipeline: {e}", exc_info=True)
        return None



def run_pipeline(max_articles: int = 1000, use_local_cache: bool = False, send_to_webex: bool = True):
    """
    Wrapper function for scheduled execution.
    
    Args:
        max_articles: Maximum number of articles to collect (현재 사용 안 함)
        use_local_cache: Use local cache (현재 사용 안 함)
        send_to_webex: Send to Webex (현재 save_output으로 처리됨)
    
    Returns:
        Tuple of (webex_messages, analyzed_articles, stats)
    """
    # Setup logging
    setup_logging()
    
    logger.info("Initializing AI News Intelligence Pipeline for Lotte Members")
    logger.info(f"Configuration: {PipelineConfig.LLM_MODEL}")
    
    # Validate configuration
    PipelineConfig.validate()
    
    # Run pipeline
    pipeline = NewsIntelligencePipeline()
    webex_messages, analyzed_articles, stats = pipeline.run(save_output=True)
    
    # Warnings
    if stats.regulatory_articles_found > stats.regulatory_articles_retained:
        logger.warning(f"\n⚠️  WARNING: Some regulatory articles may have been dropped!")
    
    if stats.final_output_count == 0:
        logger.warning("\n⚠️  WARNING: Pipeline produced no output messages!")
    else:
        logger.info(f"\n✅ Pipeline completed successfully with {stats.final_output_count} messages")
    
    return webex_messages, analyzed_articles, stats


if __name__ == "__main__":
    main()
