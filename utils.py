import time
import logging
from functools import wraps
from typing import Callable, Any

def rate_limit(calls: int, period: float = 60.0) -> Callable:
    """Rate limiting decorator"""
    timestamps = []
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            now = time.time()
            
            # Remove timestamps older than our period
            while timestamps and now - timestamps[0] > period:
                timestamps.pop(0)
                
            # Check if we've hit our rate limit
            if len(timestamps) >= calls:
                sleep_time = timestamps[0] + period - now
                if sleep_time > 0:
                    logging.info(f"Rate limit reached, sleeping for {sleep_time:.2f}s")
                    time.sleep(sleep_time)
                    
            timestamps.append(now)
            return func(*args, **kwargs)
        return wrapper
    return decorator

def chunk_text(text: str, max_tokens: int = 4000) -> list[str]:
    """Split text into chunks that respect sentence boundaries"""
    # Approximate tokens (rough estimate: 4 chars = 1 token)
    chars_per_chunk = max_tokens * 4
    
    # Split into sentences (naive approach)
    sentences = [s.strip() for s in text.split('.') if s.strip()]
    
    chunks = []
    current_chunk = []
    current_length = 0
    
    for sentence in sentences:
        sentence_length = len(sentence)
        
        if current_length + sentence_length > chars_per_chunk:
            # Save current chunk if it's not empty
            if current_chunk:
                chunks.append('. '.join(current_chunk) + '.')
                current_chunk = []
                current_length = 0
        
        current_chunk.append(sentence)
        current_length += sentence_length
    
    # Add any remaining text
    if current_chunk:
        chunks.append('. '.join(current_chunk) + '.')
    
    return chunks