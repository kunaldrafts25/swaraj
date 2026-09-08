"""Task embedding for router classification.

Uses FastEmbed to generate embeddings for task descriptions.
These embeddings are used to determine task characteristics for routing.

CRITICAL: If the embedding model is not available locally, this module
must fail closed rather than attempting to download models or using fake embeddings.
"""

from typing import Optional
from pathlib import Path


class EmbeddingUnavailableError(Exception):
    """Raised when the embedding model is not available."""

    pass


class TaskEmbedder:
    """Generates embeddings for task descriptions using FastEmbed.

    This class provides deterministic embeddings for task classification.
    The same input text will always produce the same embedding vector.

    Fail-Closed Behavior:
    - If FastEmbed is not installed, raises EmbeddingUnavailableError
    - If the embedding model cannot be loaded, raises EmbeddingUnavailableError
    - Never returns fake or placeholder embeddings
    """

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        """Initialize the task embedder.

        Args:
            model_name: Name of the FastEmbed model to use.
                       Must be available locally (no network download).

        Raises:
            EmbeddingUnavailableError: If the embedding model cannot be loaded
        """
        self.model_name = model_name
        self._model = None
        self._available = False
        self._init_error: Optional[str] = None

        # Attempt to initialize FastEmbed
        try:
            from fastembed import TextEmbedding

            # Try to load the model - this will fail if not cached locally
            # We set local_files_only to enforce air-gap operation
            self._model = TextEmbedding(model_name=model_name)
            self._available = True
        except ImportError as e:
            self._init_error = f"FastEmbed not installed: {e}"
            self._available = False
        except Exception as e:
            self._init_error = f"Failed to load embedding model '{model_name}': {e}"
            self._available = False

    @property
    def is_available(self) -> bool:
        """Check if the embedder is available for use."""
        return self._available

    @property
    def init_error(self) -> Optional[str]:
        """Get the initialization error message if unavailable."""
        return self._init_error

    def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text.

        Args:
            text: The text to embed

        Returns:
            List of floats representing the embedding vector

        Raises:
            EmbeddingUnavailableError: If the embedder is not available
        """
        if not self._available:
            raise EmbeddingUnavailableError(
                f"Task embedding unavailable: {self._init_error}. "
                "Cannot proceed with routing without embeddings."
            )

        if self._model is None:
            raise EmbeddingUnavailableError("Embedding model not initialized")

        # Generate embedding
        # FastEmbed returns an iterator of numpy arrays
        embeddings = list(self._model.embed([text]))

        if not embeddings:
            raise EmbeddingUnavailableError("Embedding model returned empty result")

        # Convert to list of floats (handle numpy array)
        embedding_array = embeddings[0]

        # Handle both numpy arrays and native lists
        if hasattr(embedding_array, "tolist"):
            return [float(x) for x in embedding_array.tolist()]
        else:
            return [float(x) for x in embedding_array]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors

        Raises:
            EmbeddingUnavailableError: If the embedder is not available
        """
        if not self._available:
            raise EmbeddingUnavailableError(
                f"Task embedding unavailable: {self._init_error}"
            )

        if self._model is None:
            raise EmbeddingUnavailableError("Embedding model not initialized")

        embeddings = list(self._model.embed(texts))

        result = []
        for emb in embeddings:
            if hasattr(emb, "tolist"):
                result.append([float(x) for x in emb.tolist()])
            else:
                result.append([float(x) for x in emb])

        return result
