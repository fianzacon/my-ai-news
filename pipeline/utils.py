"""
Utility functions for embeddings, similarity, and common operations.
"""
import hashlib
import logging
from typing import List
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from .config import PipelineConfig
import os

logger = logging.getLogger(__name__)

# Initialize embedding model (singleton)
_embedding_model = None


def get_embedding_model():
    """Get or create the embedding model instance."""
    global _embedding_model
    if _embedding_model is None:
        # Use Google Generative AI instead of Vertex AI (no ADC required with API key)
        google_api_key = os.getenv('GOOGLE_API_KEY')
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")
        
        _embedding_model = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004",
            google_api_key=google_api_key
        )
    return _embedding_model


def generate_embedding(text: str) -> List[float]:
    """
    Generate embedding for given text.
    
    Args:
        text: Input text to embed
        
    Returns:
        List of floats representing the embedding
    """
    if not text or not text.strip():
        return [0.0] * PipelineConfig.EMBEDDING_DIMENSION
    
    try:
        model = get_embedding_model()
        embedding = model.embed_query(text)
        return embedding
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        return [0.0] * PipelineConfig.EMBEDDING_DIMENSION


def generate_embeddings_batch(texts: List[str], batch_size: int = 50) -> List[List[float]]:
    """
    Generate embeddings for multiple texts in batches (MUCH FASTER than one-by-one).
    
    Args:
        texts: List of texts to embed
        batch_size: Number of texts per batch (default 50)
        
    Returns:
        List of embedding vectors
    """
    if not texts:
        return []
    
    try:
        model = get_embedding_model()
        all_embeddings = []
        total_batches = (len(texts) + batch_size - 1) // batch_size
        
        logger.info(f"[Batch Embedding] Processing {len(texts)} texts in {total_batches} batches")
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_num = i // batch_size + 1
            logger.info(f"[Batch {batch_num}/{total_batches}] Embedding {len(batch)} texts...")
            
            # Use embed_documents for batch processing (single API call)
            batch_embeddings = model.embed_documents(batch)
            all_embeddings.extend(batch_embeddings)
        
        logger.info(f"[Batch Embedding] Complete: Generated {len(all_embeddings)} embeddings")
        return all_embeddings
        
    except Exception as e:
        logger.error(f"❌ CRITICAL: Failed to generate batch embeddings: {e}")
        logger.error(f"This will cause deduplication to fail!")
        logger.error(f"Check: 1) Internet connectivity, 2) Google API credentials, 3) DNS resolution")
        # Return None to signal failure (don't silently return zero vectors)
        return None


def calculate_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """
    Calculate cosine similarity between two embeddings.
    
    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector
        
    Returns:
        Similarity score between 0 and 1
    """
    if not embedding1 or not embedding2:
        return 0.0
    
    try:
        # Reshape for sklearn
        emb1 = np.array(embedding1).reshape(1, -1)
        emb2 = np.array(embedding2).reshape(1, -1)
        
        similarity = cosine_similarity(emb1, emb2)[0][0]
        return float(similarity)
    except Exception as e:
        logger.error(f"Failed to calculate similarity: {e}")
        return 0.0


def create_text_hash(text: str) -> str:
    """
    Create a hash for text content for quick comparison.
    
    Args:
        text: Input text
        
    Returns:
        SHA256 hash of the text
    """
    if not text:
        return ""
    
    normalized = text.strip().lower()
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def extract_lead_paragraph(content: str, num_sentences: int = 3) -> str:
    """
    Extract the first N sentences from content to form lead paragraph.
    
    Args:
        content: Full article content
        num_sentences: Number of sentences to extract
        
    Returns:
        Lead paragraph text
    """
    if not content:
        return ""
    
    # Simple sentence splitting (can be improved with NLP)
    sentences = []
    current = []
    
    for char in content:
        current.append(char)
        if char in '.!?' and len(current) > 10:  # Avoid splitting on abbreviations
            sentences.append(''.join(current).strip())
            current = []
            if len(sentences) >= num_sentences:
                break
    
    # If we didn't reach num_sentences, add remaining
    if current and len(sentences) < num_sentences:
        sentences.append(''.join(current).strip())
    
    lead = ' '.join(sentences[:num_sentences])
    return lead if lead else content[:500]  # Fallback to first 500 chars


def normalize_company_name(text: str) -> str:
    """
    Extract and normalize company/entity names from text.
    
    Args:
        text: Text containing company names
        
    Returns:
        Normalized company name
    """
    # This is a placeholder - in production, use NER or regex patterns
    # For now, just clean up the text
    return text.strip()


def setup_logging():
    """Configure logging for the pipeline with Windows encoding support."""
    import sys
    
    # Fix Windows console encoding for emojis
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
