import asyncio
import threading

from sentence_transformers import SentenceTransformer

from app.config import settings

_model: SentenceTransformer | None = None
_lock = threading.Lock()


def get_embedder() -> SentenceTransformer:
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                _model = SentenceTransformer(settings.embedding_model, device="cpu")
    return _model


async def embed_query(text: str) -> list[float]:
    model = await asyncio.to_thread(get_embedder)
    vector = await asyncio.to_thread(model.encode, text, normalize_embeddings=True)
    return vector.tolist()
