FROM nvidia/cuda:12.6.2-cudnn-runtime-ubuntu22.04

# Install Python 3.11
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-dev \
    python3-pip \
    python3.11-venv \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && rm -rf /var/lib/apt/lists/*

# GPU最適化のための環境変数
ENV PYTHONUNBUFFERED=1
ENV TORCH_COMPILE=1
ENV MKL_NUM_THREADS=8
ENV OMP_NUM_THREADS=8
ENV OPENBLAS_NUM_THREADS=8

# GPU環境用の環境変数
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility
ENV CUDA_LAUNCH_BLOCKING=0
ENV CUDA_HOME=/usr/local/cuda
# WSL2ドライバパスを優先（必須）
ENV LD_LIBRARY_PATH=/usr/lib/wsl/lib:/usr/local/cuda/lib64:/usr/local/nvidia/lib:/usr/local/nvidia/lib64:${LD_LIBRARY_PATH}

ENV PYTHONDONTWRITEBYTECODE=1

# Set work directory
WORKDIR /app

# Install system dependencies for document processing
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        gosu \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-jpn \
        libtesseract-dev \
        libgl1-mesa-dev \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
        libgomp1 \
        libgcc-s1 \
        poppler-utils \
        libpoppler-cpp-dev \
        qpdf \
        ghostscript \
        fonts-noto-cjk \
        fonts-ipafont \
        fonts-ipaexfont \
        fonts-takao \
        fonts-vlgothic \
        libmecab-dev \
        mecab \
        mecab-ipadic-utf8 \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

# Tesseractの設定
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata
RUN mkdir -p /usr/share/tesseract-ocr/5/tessdata

# MeCabの設定
RUN mkdir -p /usr/local/etc \
    && ln -s /etc/mecabrc /usr/local/etc/mecabrc

# Copy pyproject.toml
COPY pyproject.toml poetry.lock* ./

# Generate requirements.txt from pyproject.toml (excluding torch)
RUN pip install poetry poetry-plugin-export \
    && poetry export -f requirements.txt --output requirements.txt --without-hashes \
    && grep -v '^torch' requirements.txt | grep -v '^torchvision' | grep -v '^torchaudio' > requirements_no_torch.txt \
    && pip install -r requirements_no_torch.txt \
    && pip install torch==2.6.0+cu126 torchvision==0.21.0+cu126 torchaudio==2.6.0+cu126 --index-url https://download.pytorch.org/whl/cu126

# Copy application
COPY app ./app

# Create directories and non-root user
RUN adduser --disabled-password --gecos '' --uid 1000 appuser \
    && chown -R appuser:appuser /app \
    && mkdir -p /tmp/.docling_cache/huggingface \
    && mkdir -p /tmp/.docling_cache/transformers \
    && mkdir -p /tmp/.docling_cache/torch \
    && mkdir -p /tmp/.easyocr_models \
    && mkdir -p /tmp/document_processing \
    && mkdir -p /data/documents \
    && chown -R appuser:appuser /tmp/.docling_cache /tmp/.easyocr_models /tmp/document_processing /data/documents

# Expose port
EXPOSE 8011

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8011/health || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8011"]
