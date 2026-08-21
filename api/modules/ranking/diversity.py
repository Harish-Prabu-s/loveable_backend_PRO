"""
Diversity & Fatigue Management (MMR)
====================================
Applies Maximal Marginal Relevance (MMR) and creator-fatigue filters
to a ranked list of candidates to ensure a diverse feed.
"""

def apply_mmr(scored_candidates: list, lambda_param: float = 0.3, max_consecutive_creator: int = 2) -> list:
    """
    Greedily selects items from scored_candidates to maximize relevance while
    penalizing redundancy.
    
    Args:
        scored_candidates: list of tuples (score, meta_dict) sorted by score.
        lambda_param: weight of the diversity penalty (0 = purely relevance, 1 = purely diversity)
        max_consecutive_creator: maximum times the same creator can appear in a row
    """
    if not scored_candidates:
        return []
        
    selected = []
    unselected = scored_candidates.copy()
    
    # Track what has been selected to compute redundancy
    selected_tags_all = set()
    sliding_window_tags = [] # For "max 2 same topic in 5 reels" rule
    last_creator_id = None
    consecutive_creator_count = 0
    
    while unselected:
        best_idx = -1
        best_mmr_score = float('-inf')
        
        for i, (score, meta) in enumerate(unselected):
            creator_id = meta.get('creator_id')
            tags = meta.get('tags', [])
            
            # Strict constraint 1: Creator fatigue
            if creator_id == last_creator_id and consecutive_creator_count >= max_consecutive_creator:
                continue # Skip this candidate for now
                
            # Strict constraint 2: Topic fatigue (max 2 same topic in last 5 reels)
            topic_fatigued = False
            if tags:
                # Count occurrences of candidate's tags in the sliding window
                for tag in tags:
                    count = sliding_window_tags.count(tag)
                    if count >= 2:
                        topic_fatigued = True
                        break
            
            if topic_fatigued:
                continue
                
            # Compute redundancy (Jaccard-like overlap of tags with globally selected items)
            redundancy = 0.0
            if selected_tags_all and tags:
                overlap = len(set(tags).intersection(selected_tags_all))
                redundancy = overlap / len(tags)
                
            # MMR Score Formula: λ * Relevance - (1 - λ) * Redundancy
            mmr_score = ((1.0 - lambda_param) * score) - (lambda_param * redundancy * 100)
            
            if mmr_score > best_mmr_score:
                best_mmr_score = mmr_score
                best_idx = i
                
        if best_idx == -1:
            # If all remaining items violate strict constraints, relax constraints 
            # and just take the highest scored remaining item
            best_idx = 0
            
        # Move winner to selected
        winner_score, winner_meta = unselected.pop(best_idx)
        selected.append(winner_meta)
        
        # Update trackers
        winner_creator_id = winner_meta.get('creator_id')
        if winner_creator_id == last_creator_id:
            consecutive_creator_count += 1
        else:
            last_creator_id = winner_creator_id
            consecutive_creator_count = 1
            
        selected_tags_all.update(winner_meta.get('tags', []))
        
        # Update sliding window
        sliding_window_tags.extend(winner_meta.get('tags', []))
        # Keep window size reasonable (approx last 5 items = ~15 tags if avg 3 tags/item)
        if len(sliding_window_tags) > 15:
            sliding_window_tags = sliding_window_tags[-15:]
        
    return selected
