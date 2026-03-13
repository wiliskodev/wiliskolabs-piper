import subprocess
import tempfile
import os
import io
import re
import json
import wave
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="WiliskoLabs Studio — Piper TTS")

PIPER_BIN = "/app/piper/piper"
MODELS_DIR = "/app/models"

VOICES = [
    {"voice_id": "fr_FR-siwis-medium", "name": "Siwis", "gender": "female", "locale": "fr-FR", "flag": "🇫🇷", "description": "Femme · Naturelle · Française"},
    {"voice_id": "fr_FR-tom-medium", "name": "Tom", "gender": "male", "locale": "fr-FR", "flag": "🇫🇷", "description": "Homme · Naturel · Français"},
    {"voice_id": "fr_FR-mls-medium", "name": "MLS Femme", "gender": "female", "locale": "fr-FR", "flag": "🇫🇷", "description": "Femme · Studio · Française"},
    {"voice_id": "en_US-amy-medium", "name": "Amy", "gender": "female", "locale": "en-US", "flag": "🇺🇸", "description": "Femme · Pro · Anglaise"},
    {"voice_id": "en_US-ryan-medium", "name": "Ryan", "gender": "male", "locale": "en-US", "flag": "🇺🇸", "description": "Homme · Naturel · Anglais"},
]

def get_available_voices():
    return [v for v in VOICES if os.path.exists(os.path.join(MODELS_DIR, f"{v['voice_id']}.onnx"))]

@app.get("/api/voices")
async def list_voices():
    return {"voices": get_available_voices()}

def split_sentences(text: str, max_chars: int = 250) -> list:
    raw = re.split(r'(?<=[.!?…])\s+', text.strip())
    sentences = []
    current = ""
    for s in raw:
        s = s.strip()
        if not s:
            continue
        if len(current) + len(s) < max_chars:
            current = (current + " " + s).strip()
        else:
            if current:
                sentences.append(current)
            current = s
    if current:
        sentences.append(current)
    result = []
    for s in sentences:
        if len(s) > max_chars:
            parts = re.split(r'(?<=,)\s+', s)
            chunk = ""
            for p in parts:
                if len(chunk) + len(p) < max_chars:
                    chunk = (chunk + " " + p).strip()
                else:
                    if chunk:
                        result.append(chunk)
                    chunk = p
            if chunk:
                result.append(chunk)
        else:
            result.append(s)
    return [s for s in result if s.strip()]

def piper_generate(text: str, model_path: str, speed: float) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            [PIPER_BIN, "--model", model_path, "--output_file", tmp_path,
             "--length_scale", str(round(1.0 / speed, 3)),
             "--noise_scale", "0.667", "--noise_w", "0.8"],
            input=text.encode("utf-8"), capture_output=True, timeout=120
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode())
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

def concat_wav(wav_chunks: list) -> bytes:
    if not wav_chunks:
        raise ValueError("Aucun chunk audio")
    if len(wav_chunks) == 1:
        return wav_chunks[0]
    output = io.BytesIO()
    with wave.open(output, 'wb') as out_wav:
        first = True
        for chunk in wav_chunks:
            with wave.open(io.BytesIO(chunk), 'rb') as w:
                if first:
                    out_wav.setparams(w.getparams())
                    first = False
                out_wav.writeframes(w.readframes(w.getnframes()))
    return output.getvalue()

class TTSRequest(BaseModel):
    voice_id: str
    text: str
    speed: float = 1.0

@app.post("/api/tts/stream")
async def synthesize_stream(req: TTSRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Texte vide")
    if len(req.text) > 15000:
        raise HTTPException(status_code=400, detail="Texte trop long (max 15 000 caractères)")
    model_path = os.path.join(MODELS_DIR, f"{req.voice_id}.onnx")
    if not os.path.exists(model_path):
        raise HTTPException(status_code=404, detail=f"Voix '{req.voice_id}' introuvable")
    speed = max(0.5, min(2.0, req.speed))
    sentences = split_sentences(req.text)
    total = len(sentences)

    def generate():
        wav_chunks = []
        for i, sentence in enumerate(sentences):
            progress = {"type": "progress", "current": i + 1, "total": total,
                        "sentence": sentence[:60] + ("..." if len(sentence) > 60 else "")}
            yield f"data: {json.dumps(progress, ensure_ascii=False)}\n\n"
            try:
                wav_data = piper_generate(sentence, model_path, speed)
                wav_chunks.append(wav_data)
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                return
        try:
            final_audio = concat_wav(wav_chunks)
            import base64
            audio_b64 = base64.b64encode(final_audio).decode()
            yield f"data: {json.dumps({'type': 'done', 'audio': audio_b64, 'total': total})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.post("/api/tts")
async def synthesize_preview(req: TTSRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Texte vide")
    model_path = os.path.join(MODELS_DIR, f"{req.voice_id}.onnx")
    if not os.path.exists(model_path):
        raise HTTPException(status_code=404, detail=f"Voix introuvable")
    speed = max(0.5, min(2.0, req.speed))
    try:
        audio_data = piper_generate(req.text[:200], model_path, speed)
        return StreamingResponse(io.BytesIO(audio_data), media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=preview.wav"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

app.mount("/", StaticFiles(directory="public", html=True), name="static")
