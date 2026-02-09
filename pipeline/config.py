"""
Configuration for the AI news intelligence pipeline.
"""
import os
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from parent directory
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()


class RateLimiter:
    """Thread-safe rate limiter to avoid API quota errors."""
    
    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self.request_times = []
        self.lock = threading.Lock()  # Thread-safe for parallel processing
    
    def wait_if_needed(self):
        """Wait if we've hit the rate limit (thread-safe)."""
        with self.lock:
            now = datetime.now()
            
            # Remove requests older than 1 minute
            cutoff = now - timedelta(minutes=1)
            self.request_times = [t for t in self.request_times if t > cutoff]
            
            # If at limit, wait
            if len(self.request_times) >= self.requests_per_minute:
                oldest = self.request_times[0]
                wait_until = oldest + timedelta(minutes=1)
                wait_seconds = (wait_until - now).total_seconds()
                
                if wait_seconds > 0:
                    print(f"[Rate Limit] Waiting {wait_seconds:.1f}s to avoid quota...")
                    time.sleep(wait_seconds + 0.5)  # Add 0.5s buffer
                    # Re-check after sleep
                    now = datetime.now()
                    cutoff = now - timedelta(minutes=1)
                    self.request_times = [t for t in self.request_times if t > cutoff]
            
            # Record this request
            self.request_times.append(datetime.now())


class PipelineConfig:
    """Centralized configuration for the entire pipeline."""
    
    # API Keys
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
    NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
    GOOGLE_NEWS_API_KEY = os.getenv("GOOGLE_NEWS_API_KEY")  # If using News API
    
    # LLM Configuration
    LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")
    LLM_TEMPERATURE = 0.1
    LLM_REQUESTS_PER_MINUTE = int(os.getenv("LLM_REQUESTS_PER_MINUTE", 60))
    
    # Embedding Configuration
    EMBEDDING_MODEL = "models/text-embedding-004"  
    EMBEDDING_DIMENSION = 768
    
    # Deduplication Thresholds
    FIRST_DEDUP_THRESHOLD = 0.85  # Title + lead paragraph similarity
    SECOND_DEDUP_THRESHOLD = 0.90  # Full content similarity
    
    # Collection Parameters
    SEARCH_KEYWORDS = [
        "오픈AI",
        "구글 AI", 
        "Claude",
        "클로드", # AI technology - more specific than just "AI"
        "AI 광고",
        "생성형AI",
        "AI 마케팅",  # AI advertising marketing
        "AI 광고 마케팅",
        "AI 서비스",  # AI services
        "AI 솔루션",
        "생성형 AI",
        "AI 규제"  # Generative AI
    ]
    MAX_ARTICLES_PER_SOURCE = 100  # Limit per API call
    
    # Content Extraction
    LEAD_PARAGRAPH_SENTENCES = 3  # Number of sentences for lead paragraph
    
    # Logging
    LOG_LEVEL = "INFO"
    LOG_FILE = "pipeline.log"
    
    # Retry Configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds
    
    @classmethod
    def validate(cls):
        """Validate that all required configuration is present."""
        missing = []
        
        if not cls.GOOGLE_API_KEY:
            missing.append("GOOGLE_API_KEY")
        if not cls.NAVER_CLIENT_ID:
            missing.append("NAVER_CLIENT_ID")
        if not cls.NAVER_CLIENT_SECRET:
            missing.append("NAVER_CLIENT_SECRET")
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        return True


# Validate on import
try:
    PipelineConfig.validate()
except ValueError as e:
    print(f"⚠️  Configuration warning: {e}")
    print("   Some features may not work without proper API keys in .env file")
