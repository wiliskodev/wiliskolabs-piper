FROM python:3.11-slim

WORKDIR /app

# Outils système
RUN apt-get update && apt-get install -y wget curl && rm -rf /var/lib/apt/lists/*

# ── Télécharger Piper (binaire Linux x86_64) ──────────────────
RUN wget -q https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz \
    && tar -xzf piper_linux_x86_64.tar.gz \
    && rm piper_linux_x86_64.tar.gz \
    && chmod +x /app/piper/piper

# ── Télécharger les modèles de voix ───────────────────────────
RUN mkdir -p /app/models

# Voix françaises
RUN wget -q -O /app/models/fr_FR-siwis-medium.onnx \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx" \
 && wget -q -O /app/models/fr_FR-siwis-medium.onnx.json \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json"

RUN wget -q -O /app/models/fr_FR-tom-medium.onnx \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/tom/medium/fr_FR-tom-medium.onnx" \
 && wget -q -O /app/models/fr_FR-tom-medium.onnx.json \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/tom/medium/fr_FR-tom-medium.onnx.json"

RUN wget -q -O /app/models/fr_FR-mls-medium.onnx \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/mls/medium/fr_FR-mls-medium.onnx" \
 && wget -q -O /app/models/fr_FR-mls-medium.onnx.json \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/mls/medium/fr_FR-mls-medium.onnx.json"

# Voix anglaises
RUN wget -q -O /app/models/en_US-amy-medium.onnx \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx" \
 && wget -q -O /app/models/en_US-amy-medium.onnx.json \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json"

RUN wget -q -O /app/models/en_US-ryan-medium.onnx \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium/en_US-ryan-medium.onnx" \
 && wget -q -O /app/models/en_US-ryan-medium.onnx.json \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium/en_US-ryan-medium.onnx.json"

# ── Installer les dépendances Python ──────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copier le code ─────────────────────────────────────────────
COPY . .

EXPOSE 8000

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
