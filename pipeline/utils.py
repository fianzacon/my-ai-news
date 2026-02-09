"""
Utility functions for embeddings, similarity, and common operations.
"""
import hashlib
import logging
from typing import List, Optional
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import google.generativeai as genai
from .config import PipelineConfig
import os
import time

logger = logging.getLogger(__name__)

# Initialize embedding model (singleton)
_embedding_model_initialized = False


def initialize_embedding_model():
    """Initialize the Google Generative AI client."""
    global _embedding_model_initialized
    if not _embedding_model_initialized:
        google_api_key = os.getenv('GOOGLE_API_KEY')
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")
        
        genai.configure(api_key=google_api_key)
        _embedding_model_initialized = True


def generate_embedding(text: str) -> List[float]:
    """
    Generate embedding for given text using Native Google SDK.
    """
    if not text or not text.strip():
        return [0.0] * PipelineConfig.EMBEDDING_DIMENSION
    
    try:
        initialize_embedding_model()
        
        # 모델명 안전 처리
        model_name = PipelineConfig.EMBEDDING_MODEL
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"

        result = genai.embed_content(
            model=model_name,
            content=text,
            task_type="retrieval_document"
        )
        return result['embedding']
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        return [0.0] * PipelineConfig.EMBEDDING_DIMENSION


def generate_embeddings_batch(texts: List[str], batch_size: int = 10) -> Optional[List[List[float]]]:
    """
    Generate embeddings for multiple texts using iterative approach.
    Note: Batch size reduced to avoid Rate Limit errors since we loop.
    """
    if not texts:
        return []
    
    try:
        initialize_embedding_model()
        all_embeddings = []
        
        # 모델명 안전 처리
        model_name = PipelineConfig.EMBEDDING_MODEL
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"

        total_batches = (len(texts) + batch_size - 1) // batch_size
        logger.info(f"[Batch Embedding] Processing {len(texts)} texts using iterative loop")
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_num = i // batch_size + 1
            logger.info(f"[Batch {batch_num}/{total_batches}] Processing {len(batch)} items...")
            
            # [수정됨] 사용자님이 알려주신 확실한 방법 (Iterative Loop)
            batch_embeddings = []
            for text in batch:
                try:
                    result = genai.embed_content(
                        model=model_name,
                        content=text,
                        task_type="retrieval_document"
                    )
                    batch_embeddings.append(result['embedding'])
                except Exception as inner_e:
                    logger.warning(f"Failed to embed single item in batch: {inner_e}")
                    # 실패 시 0벡터로 채워서 인덱스 밀림 방지
                    batch_embeddings.append([0.0] * PipelineConfig.EMBEDDING_DIMENSION)
            
            all_embeddings.extend(batch_embeddings)
            
            # [중요] 반복문 사용 시 속도 제한(Rate Limit) 방지를 위해 약간 대기
            time.sleep(1) 
        
        logger.info(f"[Batch Embedding] Complete: Generated {len(all_embeddings)} embeddings")
        return all_embeddings
        
    except Exception as e:
        logger.error(f"❌ CRITICAL: Failed to generate batch embeddings: {e}")
        return None


def calculate_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """Calculate cosine similarity."""
    if not embedding1 or not embedding2:
        return 0.0
    
    try:
        emb1 = np.array(embedding1).reshape(1, -1)
        emb2 = np.array(embedding2).reshape(1, -1)
        return float(cosine_similarity(emb1, emb2)[0][0])
    except Exception as e:
        logger.error(f"Failed to calculate similarity: {e}")
        return 0.0


def create_text_hash(text: str) -> str:
    """Create SHA256 hash."""
    if not text: 
        return ""
    return hashlib.sha256(text.strip().lower().encode('utf-8')).hexdigest()


def extract_lead_paragraph(content: str, num_sentences: int = 3) -> str:
    """Extract lead paragraph."""
    if not content:
        return ""
    
    sentences = []
    current = []
    
    for char in content:
        current.append(char)
        if char in '.!?' and len(current) > 10:
            sentences.append(''.join(current).strip())
            current = []
            if len(sentences) >= num_sentences:
                break
    
    if current and len(sentences) < num_sentences:
        sentences.append(''.join(current).strip())
    
    lead = ' '.join(sentences[:num_sentences])
    return lead if lead else content[:500]


def normalize_company_name(text: str) -> str:
    """Normalize company name."""
    return text.strip()


def setup_logging():
    """Configure logging with Windows encoding support."""
    import sys
    
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    
    logging.basicConfig(
        level=getattr(logging, PipelineConfig.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(PipelineConfig.LOG_FILE, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )