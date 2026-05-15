FROM python:3.12-slim

ARG GIT_SHA=unknown
ENV GIT_SHA=$GIT_SHA

WORKDIR /app

COPY requirements.txt .
# Force PyTorch CPU-only (sentence-transformers/llama-index tirent CUDA par défaut)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
