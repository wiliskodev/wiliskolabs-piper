import subprocess
import tempfile
import os
import io
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="WiliskoLabs Studio — Piper TTS")

PIPER_BIN = "/app/piper/piper"
MODELS_DIR = "/app/models"

# ── Catalogue des voix disponibles ───────────────────────────
VOICES = [
    {
        "voice_id": "fr_FR-siwis-medium",
        "name": "Siwis",
        "gender": "female",
        "locale": "fr-FR",
        "flag": "🇫🇷",
        "description": "Femme · Naturelle · Française"
    },
    {
        "voice_id": "fr_FR-tom-medium",
        "name": "Tom",
        "gender": "male",
        "locale": "fr-FR",
        "flag": "🇫🇷",
        "description": "Homme · Naturel · Français"
    },
    {
        "voice_id": "fr_FR-mls-medium",
        "name": "MLS Femme",
        "gender": "female",
        "locale": "fr-FR",
        "flag": "🇫🇷",
        "description": "Femme · Studio · Française"
    },
    {
        "voice_id": "en_US-amy-medium",
        "name": "Amy",
        "gender": "female",
        "locale": "en-US",
        "flag": "🇺🇸",
        "description": "Femme · Pro · Anglaise"
    },
    {
        "voice_id": "en_US-ryan-medium",
        "name": "Ryan",
        "gender": "male",
        "locale": "en-US",
        "flag": "🇺🇸",
        "description": "Homme · Naturel · Anglais"
    },
]


# ── Filtrer les voix dont le modèle est bien présent ─────────
def get_available_voices():
    available = []
    for v in VOICES:
        model_path = os.path.join(MODELS_DIR, f"{v['voice_id']}.onnx")
        if os.path.exists(model_path):
            available.append(v)
    return available


@app.get("/api/voices")
async def list_voices():
    return {"voices": get_available_voices()}


# ── TTS ──────────────────────────────────────────────────────
class TTSRequest(BaseModel):
    voice_id: str
    text: str
    speed: float = 1.0   # 0.5 (lent) à 2.0 (rapide)


@app.post("/api/tts")
async def synthesize(req: TTSRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Le texte est vide")
    if len(req.text) > 5000:
        raise HTTPException(status_code=400, detail="Texte trop long (max 5000 caractères)")

    # Vérifier que la voix existe
    model_path = os.path.join(MODELS_DIR, f"{req.voice_id}.onnx")
    if not os.path.exists(model_path):
        raise HTTPException(status_code=404, detail=f"Voix '{req.voice_id}' non trouvée")

    # Clamp la vitesse
    speed = max(0.5, min(2.0, req.speed))

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        # Appel Piper via subprocess
        result = subprocess.run(
            [
                PIPER_BIN,
                "--model", model_path,
                "--output_file", tmp_path,
                "--length_scale", str(1.0 / speed),  # Piper inverse : 0.5 = rapide
                "--noise_scale", "0.667",
                "--noise_w", "0.8",
            ],
            input=req.text.encode("utf-8"),
            capture_output=True,
            timeout=60
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Erreur Piper : {result.stderr.decode()}"
            )

        # Lire le WAV généré
        with open(tmp_path, "rb") as f:
            audio_data = f.read()

        os.unlink(tmp_path)

        if not audio_data:
            raise HTTPException(status_code=500, detail="Aucun audio généré")

        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=wiliskolabs-voiceover.wav"}
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Timeout — texte trop long")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Fichiers statiques (frontend) ────────────────────────────
app.mount("/", StaticFiles(directory="public", html=True), name="static")
