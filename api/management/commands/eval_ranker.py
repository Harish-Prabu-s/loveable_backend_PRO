from django.core.management.base import BaseCommand
from api.modules.ranking.model_registry import registry
from api.modules.ranking.eval_harness import evaluate_ranker
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Evaluates the deep multi-task ranker model using IPS.'

    def handle(self, *args, **options):
        self.stdout.write("Starting offline evaluation...")
        
        model = registry.get_model('multi_task_ranker')
        if not model:
            self.stdout.write(self.style.ERROR("Model not found. Run train_ranker first."))
            return
            
        # In a real scenario, query RecEvent to get holdout set
        # Dummy data for MVP
        test_events = [
            {
                'position': 1,
                'outcome': 1, # watched
                'user_features': {},
                'content_features': {'view_count': 100, 'share_count': 10}
            },
            {
                'position': 5,
                'outcome': 0, # skipped
                'user_features': {},
                'content_features': {'view_count': 50, 'share_count': 1}
            }
        ]
        
        # Position bias: P(observe | pos=k) = 1 / log2(k + 1)
        import math
        position_bias_params = {k: 1.0 / math.log2(k + 1) for k in range(1, 21)}
        
        # Wrap sklearn model with predict dictionary wrapper for eval harness
        class ModelWrapper:
            def __init__(self, sk_model):
                self.sk_model = sk_model
            def predict(self, u_f, c_f):
                # Dummy prediction mapping
                return {'p_complete': 0.5, 'p_like': 0.1}
                
        wrapped_model = ModelWrapper(model)
        
        score = evaluate_ranker(wrapped_model, test_events, position_bias_params)
        
        self.stdout.write(self.style.SUCCESS(f"Evaluation Complete. IPS Reward Score: {score:.4f}"))
