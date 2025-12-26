"""
PySpark HTTP Client - Connects to PySpark service for model predictions

This service makes HTTP requests to the PySpark service (port 5001)
instead of loading the model directly in the backend.
"""

import httpx
from typing import List, Optional
from models.schemas import EAOSLabel
import logging

logger = logging.getLogger(__name__)


class PySparkClient:
    """
    HTTP client for PySpark service

    Makes requests to PySpark service which uses:
    - Model inference for predictions
    - PandasUDF for batch processing (when batch >= 10)
    """

    def __init__(self, base_url: str = "http://localhost:5001"):
        """
        Initialize PySpark client

        Args:
            base_url: URL of PySpark service (default: http://localhost:5001)
        """
        self.base_url = base_url
        self.timeout = httpx.Timeout(120.0, connect=5.0)  # 2 min for inference, 5s for connect

        # Test connection
        try:
            self._check_health()
            logger.info(f"✅ Connected to PySpark service at {base_url}")
        except Exception as e:
            logger.warning(f"⚠️  PySpark service not available at {base_url}: {e}")

    def _check_health(self) -> bool:
        """Check if PySpark service is healthy"""
        with httpx.Client(timeout=httpx.Timeout(5.0)) as client:
            response = client.get(f"{self.base_url}/health")
            response.raise_for_status()
            data = response.json()

            if not data.get("model") or not data.get("spark"):
                raise Exception(f"PySpark service unhealthy: {data}")

            return True

    def predict(
        self,
        text: str,
        confidence_threshold: float = 0.3
    ) -> List[EAOSLabel]:
        """
        Predict EAOS labels for a single comment

        Args:
            text: Comment text
            confidence_threshold: Minimum confidence threshold (not used by service currently)

        Returns:
            List of EAOSLabel objects
        """
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/predict",
                    json={"text": text}
                )
                response.raise_for_status()
                data = response.json()

            # Convert predictions to EAOSLabel objects
            labels = []
            for pred in data.get("predictions", []):
                labels.append(EAOSLabel(
                    entity=pred.get("entity", ""),
                    aspect=pred.get("aspect", ""),
                    opinion=pred.get("opinion", ""),
                    sentiment=pred.get("sentiment", ""),
                    confidence=pred.get("confidence", 0.0)
                ))

            return labels

        except httpx.RequestError as e:
            logger.error(f"Request to PySpark service failed: {e}")
            raise Exception(f"PySpark service unavailable: {e}")

        except httpx.HTTPStatusError as e:
            logger.error(f"PySpark service returned error: {e.response.text}")
            raise Exception(f"PySpark service error: {e.response.text}")

    def predict_batch(
        self,
        texts: List[str],
        confidence_threshold: float = 0.3
    ) -> List[List[EAOSLabel]]:
        """
        Predict EAOS labels for multiple comments

        Uses PySpark PandasUDF for batch >= 10, direct model for batch < 10

        Args:
            texts: List of comment texts
            confidence_threshold: Minimum confidence threshold

        Returns:
            List of lists of EAOSLabel objects
        """
        try:
            # Format comments for PySpark service
            comments = [
                {"id": str(i), "text": text}
                for i, text in enumerate(texts)
            ]

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/predict/batch",
                    json={"comments": comments}
                )
                response.raise_for_status()
                data = response.json()

            # Log which method was used
            method = data.get("method", "unknown")
            logger.info(f"Batch prediction used method: {method}")

            # Convert predictions to EAOSLabel objects
            results = []
            for result in data.get("results", []):
                labels = []
                for pred in result.get("predictions", []):
                    labels.append(EAOSLabel(
                        entity=pred.get("entity", ""),
                        aspect=pred.get("aspect", ""),
                        opinion=pred.get("opinion", ""),
                        sentiment=pred.get("sentiment", ""),
                        confidence=pred.get("confidence", 0.0)
                    ))
                results.append(labels)

            return results

        except httpx.RequestError as e:
            logger.error(f"Request to PySpark service failed: {e}")
            raise Exception(f"PySpark service unavailable: {e}")

        except httpx.HTTPStatusError as e:
            logger.error(f"PySpark service returned error: {e.response.text}")
            raise Exception(f"PySpark service error: {e.response.text}")


# Global instance (singleton)
_pyspark_client: Optional[PySparkClient] = None


def get_pyspark_client() -> Optional[PySparkClient]:
    """Get or create PySpark client instance"""
    global _pyspark_client

    if _pyspark_client is None:
        try:
            _pyspark_client = PySparkClient()
        except Exception as e:
            logger.warning(f"Failed to create PySpark client: {e}")
            _pyspark_client = None

    return _pyspark_client
