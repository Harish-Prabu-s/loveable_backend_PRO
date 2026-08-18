"""
Model Registry
==============
Manages loading, versioning, and caching of machine learning models
for the recommendation engine.

Currently stores models locally using joblib. In production, this would
download artifacts from S3.
"""

import os
import joblib
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(settings.BASE_DIR, 'ml_models')

# Ensure directory exists
if not os.path.exists(MODELS_DIR):
    os.makedirs(MODELS_DIR)

class ModelRegistry:
    def __init__(self):
        self._models = {}

    def get_model(self, model_name: str, version: str = 'latest'):
        """
        Retrieves a model from in-memory cache, or loads it from disk.
        """
        cache_key = f"{model_name}_{version}"
        if cache_key in self._models:
            return self._models[cache_key]

        model_path = self._get_model_path(model_name, version)
        if not os.path.exists(model_path):
            logger.warning(f"Model {model_name} (version: {version}) not found at {model_path}.")
            return None

        try:
            model = joblib.load(model_path)
            self._models[cache_key] = model
            logger.info(f"Successfully loaded model {model_name} (v: {version}).")
            return model
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            return None

    def save_model(self, model, model_name: str, version: str = 'latest'):
        """
        Saves a trained model to disk and updates the in-memory cache.
        """
        model_path = self._get_model_path(model_name, version)
        try:
            joblib.dump(model, model_path)
            cache_key = f"{model_name}_{version}"
            self._models[cache_key] = model
            logger.info(f"Successfully saved model {model_name} (v: {version}) to {model_path}.")
            return True
        except Exception as e:
            logger.error(f"Failed to save model {model_name}: {e}")
            return False

    def _get_model_path(self, model_name: str, version: str) -> str:
        # e.g. ml_models/ranker_v_latest.joblib
        filename = f"{model_name}_v_{version}.joblib"
        return os.path.join(MODELS_DIR, filename)

# Singleton registry
registry = ModelRegistry()
