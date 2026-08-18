"""
Satisfaction Predictor
======================
Applies the masterplan's weighted formula to predict overall user
satisfaction from individual engagement probabilities.

Formula from Section 3:
Satisfaction = (P(Complete) * 2) + (P(Like) * 3) + (P(Save) * 4) + 
               (P(Share) * 5) - (P(Skip) * 3) - (P(Not Interested) * 10)
"""

def compute_satisfaction_score(predictions: dict) -> float:
    """
    Computes a single satisfaction score based on predicted probabilities
    of various user actions.
    
    Args:
        predictions: dict with keys like 'p_complete', 'p_like', 'p_save',
                     'p_share', 'p_skip', 'p_not_interested'.
                     Values should be floats between 0.0 and 1.0.
    """
    p_complete = predictions.get('p_complete', 0.0)
    p_like = predictions.get('p_like', 0.0)
    p_save = predictions.get('p_save', 0.0)
    p_share = predictions.get('p_share', 0.0)
    p_skip = predictions.get('p_skip', 0.0)
    p_not_interested = predictions.get('p_not_interested', 0.0)
    
    score = (
        (p_complete * 2.0) +
        (p_like * 3.0) +
        (p_save * 4.0) +
        (p_share * 5.0) -
        (p_skip * 3.0) -
        (p_not_interested * 10.0)
    )
    
    return score
