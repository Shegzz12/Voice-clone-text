import os
import io
import base64
import torch
import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from bark import SAMPLE_RATE, generate_audio, preload_models
from scipy.io.wavfile import write

# Initialize FastAPI app
app = FastAPI(title="Voice Cloning Studio")

# Preload Bark model weights on startup
@app.on_event("startup")
async def startup_event():
    print("Loading Voice Cloning Models...")
    preload_models()
    print("Models loaded successfully!")

class TTSRequest(BaseModel):
    text: str
    voice_preset: str = "v2/en_speaker_6"

# Single-file HTML, CSS, and JS Dashboard
HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voice Cloning Studio</title>
    <style>
        :root {
            --bg: #0f172a;
            --card: #1e293b;
            --accent: #6366f1;
            --text: #f8fafc;
            --subtext: #94a3b8;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
        }
        .container {
            background-color: var(--card);
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
            width: 100%;
            max-width: 600px;
        }
        h1 { margin-top: 0; font-size: 1.5rem; color: var(--text); }
        p { color: var(--subtext); font-size: 0.9rem; }
        label { display: block; margin-top: 15px; font-weight: 600; font-size: 0.85rem; }
        textarea, select, button {
            width: 100%;
            padding: 12px;
            margin-top: 8px;
            border-radius: 6px;
            border: 1px solid #334155;
            background-color: #0f172a;
            color: var(--text);
            box-sizing: border-box;
            font-size: 0.95rem;
        }
        textarea { resize: vertical; height: 100px; }
        button {
            background-color: var(--accent);
            border: none;
            font-weight: 600;
            cursor: pointer;
            margin-top: 20px;
            transition: opacity 0.2s;
        }
        button:hover { opacity: 0.9; }
        button:disabled { background-color: #475569; cursor: not-allowed; }
        .audio-container { margin-top: 25px; text-align: center; }
        audio { width: 100%; margin-top: 10px; }
        .spinner {
            display: none;
            margin: 15px auto;
            border: 3px solid rgba(255,255,255,0.1);
            border-radius: 50%;
            border-top: 3px solid var(--accent);
            width: 24px;
            height: 24px;
            animation: spin 1s linear infinite;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>

<div class="container">
    <h1>Voice Cloning Studio</h1>
    <p>Convert text to speech using cloned voice presets.</p>
    
    <label for="text">Script Text</label>
    <textarea id="text" placeholder="Enter text to generate speech..."></textarea>
    
    <label for="preset">Select Cloned Voice Preset</label>
    <select id="preset">
        <option value="v2/en_speaker_6">Speaker 1 (Male - English)</option>
        <option value="v2/en_speaker_9">Speaker 2 (Female - English)</option>
        <option value="v2/en_speaker_3">Speaker 3 (Male - Deep)</option>
        <option value="v2/en_speaker_1">Speaker 4 (Female - Expressive)</option>
    </select>
    
    <button id="generate-btn" onclick="generateSpeech()">Generate Audio</button>
    <div class="spinner" id="spinner"></div>

    <div class="audio-container" id="audio-box" style="display: none;">
        <p>Generated Result:</p>
        <audio id="audio-player" controls></audio>
    </div>
</div>

<script>
async function generateSpeech() {
    const text = document.getElementById('text').value;
    const preset = document.getElementById('preset').value;
    const btn = document.getElementById('generate-btn');
    const spinner = document.getElementById('spinner');
    const audioBox = document.getElementById('audio-box');
    const audioPlayer = document.getElementById('audio-player');

    if (!text.trim()) {
        alert("Please enter some text.");
        return;
    }

    btn.disabled = true;
    spinner.style.display = 'block';
    audioBox.style.display = 'none';

    try {
        const response = await fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text, voice_preset: preset })
        });

        const data = await response.json();
        if (response.ok) {
            audioPlayer.src = 'data:audio/wav;base64,' + data.audio_base64;
            audioBox.style.display = 'block';
        } else {
            alert("Error: " + data.detail);
        }
    } catch (err) {
        alert("Failed to generate speech. Check server logs.");
        console.error(err);
    } finally {
        btn.disabled = false;
        spinner.style.display = 'none';
    }
}
</script>

</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Serves the single-page HTML interface."""
    return HTMLResponse(content=HTML_LAYOUT)

@app.post("/generate")
async def generate_tts(payload: TTSRequest):
    """Processes text and returns base64 encoded audio."""
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text field cannot be empty.")
    
    try:
        # Generate audio numpy array from Bark model
        audio_array = generate_audio(payload.text, history_prompt=payload.voice_preset)
        
        # Convert float audio array to 16-bit PCM WAV in memory
        audio_array = (audio_array * 32767).astype(np.int16)
        byte_io = io.BytesIO()
        write(byte_io, SAMPLE_RATE, audio_array)
        byte_io.seek(0)
        
        # Encode audio bytes to base64 for direct browser playback
        audio_b64 = base64.b64encode(byte_io.read()).decode('utf-8')
        
        return {"audio_base64": audio_b64}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
