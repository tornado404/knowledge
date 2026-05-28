FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Configure pip mirror (Tsinghua)
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

# Install Python dependencies
RUN pip install --no-cache-dir \
    langchain>=0.3.0 \
    langchain_community>=0.3.0 \
    langchain_text_splitters>=0.3.0 \
    langchain_huggingface \
    langchain_anthropic \
    langgraph \
    langsmith \
    "unstructured[md]>=0.16.0" \
    pymilvus>=2.4.0 \
    python-dotenv>=1.0.0 \
    tavily-python>=0.3.0 \
    fastapi \
    uvicorn[standard] \
    sentence-transformers \
    tiktoken

# Copy kgsrc and set up as package
COPY kgsrc/ /app/kgsrc/
RUN echo '[project]' > /app/kgsrc/pyproject.toml && \
    echo 'name = "kgsrc"' >> /app/kgsrc/pyproject.toml && \
    echo 'version = "0.1"' >> /app/kgsrc/pyproject.toml && \
    echo 'requires-python = ">=3.11"' >> /app/kgsrc/pyproject.toml && \
    echo '[tool.setuptools.packages.find]' >> /app/kgsrc/pyproject.toml && \
    echo 'where = ["."]' >> /app/kgsrc/pyproject.toml && \
    echo '[build-system]' >> /app/kgsrc/pyproject.toml && \
    echo 'requires = ["setuptools>=61"]' >> /app/kgsrc/pyproject.toml && \
    echo 'build-backend = "setuptools.build_meta"' >> /app/kgsrc/pyproject.toml && \
    pip install --no-cache-dir -e /app/kgsrc

# Copy .env.txt for config
COPY .env.txt /app/.env.txt

# Expose API port
EXPOSE 8000

# Run FastAPI server
CMD ["python", "-m", "uvicorn", "knowledge_vector.chat:app", "--host", "0.0.0.0", "--port", "8000"]
