"""
Embedding Tasks
===============
Periodic Celery tasks to generate vector embeddings for new content and
rebuild the FAISS index.
"""

import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

# Lazy load the model so it doesn't block worker startup
_model = None

def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            # all-MiniLM-L6-v2 is fast and small (~80MB), good for basic semantics
            _model = SentenceTransformer('all-MiniLM-L6-v2')
        except ImportError:
            logger.error("sentence-transformers not installed.")
            return None
    return _model

@shared_task(name='api.modules.embeddings.tasks.generate_content_embeddings')
def generate_content_embeddings():
    """
    Finds content without an embedding in the DB, generates it, and saves it.
    Runs periodically (e.g., every 5 mins).
    """
    from api.models import Reel, Post
    from .models import ContentEmbedding
    
    # Simple strategy: find latest N reels/posts, check if they have embeddings.
    # In a fully robust system, you might use a signals/events queue.
    
    # 1. Process Reels
    recent_reels = Reel.objects.filter(is_archived=False).order_by('-created_at')[:50]
    reel_ids = [r.id for r in recent_reels]
    existing = set(ContentEmbedding.objects.filter(
        content_id__in=reel_ids, content_type='reel'
    ).values_list('content_id', flat=True))
    
    reels_to_process = [r for r in recent_reels if r.id not in existing]
    
    # 2. Process Posts
    recent_posts = Post.objects.filter(is_archived=False).order_by('-created_at')[:50]
    post_ids = [p.id for p in recent_posts]
    existing_posts = set(ContentEmbedding.objects.filter(
        content_id__in=post_ids, content_type='post'
    ).values_list('content_id', flat=True))
    
    posts_to_process = [p for p in recent_posts if p.id not in existing_posts]
    
    all_content = reels_to_process + posts_to_process
    
    if not all_content:
        logger.info("No new content to embed.")
        return {'processed': 0}
        
    model = _get_model()
    if model is None:
        return {'error': 'Model not loaded'}
        
    texts_to_embed = []
    for item in all_content:
        # Combine caption and tags into a single text document
        tags = [t.name for t in item.hashtags.all()]
        text = f"{item.caption or ''} {' '.join(tags)}".strip()
        if not text:
            text = "unknown" # fallback for empty content
        texts_to_embed.append(text)
        
    # Generate embeddings in batch
    embeddings = model.encode(texts_to_embed)
    
    # Simple keyword-based Auto-Tagging (Phase 2.3)
    # If the text mentions these keywords, we auto-assign the topic tag
    TOPIC_KEYWORDS = {
        'comedy': ['funny', 'laugh', 'joke', 'hilarious', 'prank', 'comedy'],
        'dance': ['dance', 'choreography', 'move', 'song', 'rhythm'],
        'technology': ['tech', 'programming', 'code', 'software', 'app', 'gadget'],
        'sports': ['game', 'match', 'play', 'football', 'basketball', 'cricket'],
        'food': ['recipe', 'cook', 'delicious', 'tasty', 'foodie', 'eat'],
    }
    
    from api.models import Hashtag
    
    # Save to DB
    saved = 0
    for item, emb, text in zip(all_content, embeddings, texts_to_embed):
        content_type = 'reel' if isinstance(item, Reel) else 'post'
        obj = ContentEmbedding(content_id=item.id, content_type=content_type)
        obj.set_embedding(emb)
        obj.save()
        
        # Auto-tagging logic
        text_lower = text.lower()
        new_tags = []
        for topic, keywords in TOPIC_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                # We found a match, get or create the topic tag
                tag, _ = Hashtag.objects.get_or_create(name=topic)
                new_tags.append(tag)
                
        if new_tags:
            item.hashtags.add(*new_tags)
            
        saved += 1
        
    logger.info(f"Generated embeddings for {saved} new items.")
    return {'processed': saved}

@shared_task(name='api.modules.embeddings.tasks.rebuild_faiss_index')
def rebuild_faiss_index():
    """
    Rebuilds the in-memory FAISS index from the DB.
    Runs periodically (e.g., every 15 mins).
    """
    from .retrieval import vector_index
    count = vector_index.build_from_db()
    return {'index_size': count}
