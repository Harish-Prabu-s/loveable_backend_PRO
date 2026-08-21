"""
ContentEmbedding Model
======================
Stores pre-computed vector embeddings for content items (Reels, Posts).

A Celery task generates these for new content using sentence-transformers
(or similar models) on the content's caption and tags.
Another task periodically loads these into a FAISS index for fast nearest-neighbor retrieval.
"""

from django.db import models
import numpy as np

class ContentEmbedding(models.Model):
    content_id = models.PositiveBigIntegerField(
        db_index=True,
        help_text='ID of the Reel or Post this embedding refers to.'
    )
    content_type = models.CharField(
        max_length=10, default='reel',
        choices=(('reel', 'Reel'), ('post', 'Post')),
    )
    
    # Store embedding as a raw binary blob (numpy array bytes) for efficiency
    embedding_blob = models.BinaryField(help_text='Numpy float32 array bytes')
    
    # The version/name of the model used, in case we need to recompute
    model_version = models.CharField(max_length=100, default='all-MiniLM-L6-v2')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('content_type', 'content_id')
        
    def get_embedding(self) -> np.ndarray:
        """Helper to deserialize the binary blob back to a numpy array."""
        if not self.embedding_blob:
            return None
        return np.frombuffer(self.embedding_blob, dtype=np.float32)

    def set_embedding(self, vec: np.ndarray):
        """Helper to serialize a numpy array into the binary blob."""
        self.embedding_blob = vec.astype(np.float32).tobytes()
        
    def __str__(self):
        return f"Embedding for {self.content_type}:{self.content_id} (Model: {self.model_version})"
