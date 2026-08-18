"""
Offline / Counterfactual Evaluation Harness
===========================================
Evaluates ranking models using historical interaction data.
Uses Inverse Propensity Scoring (IPS) to correct for position bias.
"""

def evaluate_ranker(model, test_events, position_bias_params):
    """
    Evaluates a ranker model using offline events.
    
    Args:
        model: The ranker model to test.
        test_events: List of dicts representing historical user-content interactions.
                     Must include the 'position' it was served at and the 'outcome' (e.g. watched).
        position_bias_params: Dict mapping position to probability of observation.
    
    Returns:
        float: Estimated policy value (reward) using IPS.
    """
    total_ips_reward = 0.0
    valid_events = 0
    
    for event in test_events:
        pos = event.get('position', 1)
        outcome = event.get('outcome', 0) # e.g. 1 if watched, 0 if skipped
        
        # IPS Weight = 1 / P(observation | position)
        propensity = position_bias_params.get(pos, 0.01)
        ips_weight = 1.0 / propensity
        
        # Our model's score for this item
        # If our model would have ranked it highly, we get the reward
        # (Simplified for MVP: if model score > threshold, assume it was recommended)
        predicted_score = model.predict(event['user_features'], event['content_features'])
        
        # Simple threshold for MVP
        if predicted_score.get('p_complete', 0) > 0.1:
            total_ips_reward += outcome * ips_weight
            valid_events += 1
            
    if valid_events == 0:
        return 0.0
        
    return total_ips_reward / valid_events
