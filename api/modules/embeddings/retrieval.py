"""
Embedding FAISS Retrieval
=========================
Helper module to build and query the FAISS vector index.

Since we are on a single node (or a small set of Celery workers), we can
build a lightweight in-memory FAISS index and save it to local disk, or 
rebuild it periodically from the ContentEmbedding table.
"""

import os
import faiss
import numpy as np
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

FAISS_INDEX_PATH = os.path.join(settings.BASE_DIR, 'content_faiss.index')
CONTENT_ID_MAP_PATH = os.path.join(settings.BASE_DIR, 'content_faiss_map.npy')

class VectorIndex:
    def __init__(self):
        self.index = None
        self.id_map = []
        self._load()

    def _load(self):
        if os.path.exists(FAISS_INDEX_PATH) and os.path.exists(CONTENT_ID_MAP_PATH):
            try:
                self.index = faiss.read_index(FAISS_INDEX_PATH)
                self.id_map = np.load(CONTENT_ID_MAP_PATH).tolist()
                logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors.")
            except Exception as e:
                logger.error(f"Failed to load FAISS index: {e}")
                self.index = None
                self.id_map = []

    def build_from_db(self):
        """
        Reads all embeddings from DB and builds a fresh FAISS index.
        This is relatively fast for <1M items.
        """
        from .models import ContentEmbedding
        
        embeddings = []
        id_map = []
        
        # In a real system, you might paginate this if it gets too large
        queryset = ContentEmbedding.objects.all()
        
        for record in queryset:
            vec = record.get_embedding()
            if vec is not None:
                embeddings.append(vec)
                id_map.append(record.content_id)
                
        if not embeddings:
            logger.info("No embeddings found to build index.")
            return 0
            
        embeddings_np = np.vstack(embeddings)
        dim = embeddings_np.shape[1]
        
        # L2 normalized Inner Product = Cosine Similarity
        faiss.normalize_L2(embeddings_np)
        
        # Simple flat index (exact search) is fine for < 1M items
        new_index = faiss.IndexFlatIP(dim)
        new_index.add(embeddings_np)
        
        self.index = new_index
        self.id_map = id_map
        
        # Save to disk for other workers
        faiss.write_index(self.index, FAISS_INDEX_PATH)
        np.save(CONTENT_ID_MAP_PATH, np.array(self.id_map))
        
        logger.info(f"Built and saved new FAISS index with {len(id_map)} items.")
        return len(id_map)

    def search(self, query_vector: np.ndarray, k: int = 10):
        """
        Given a query vector (e.g. user interest profile vector or a specific content vector),
        returns the top K most similar content IDs.
        """
        if self.index is None or self.index.ntotal == 0:
            return []
            
        # Ensure correct shape and normalize
        if len(query_vector.shape) == 1:
            query_vector = np.expand_dims(query_vector, axis=0)
            
        q = query_vector.copy().astype(np.float32)
        faiss.normalize_L2(q)
        
        distances, indices = self.index.search(q, k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx != -1 and idx < len(self.id_map):
                results.append((self.id_map[idx], float(dist)))
                
        return results

# Singleton instance
vector_index = VectorIndex()
