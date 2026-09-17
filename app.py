import os
import io
import base64
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from gtts import gTTS
import requests

app = FastAPI(title="Voice Studio Dual Engine")

class TTSRequest(BaseModel):
    text: str
    engine: str
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    api_key: str = ""

HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voice Studio - Dynamic Cloning</title>
    <style>
        :root { --bg: #0f172a; --card: #1e293b; --accent: #6366f1; --text: #f8fafc; --subtext: #94a3b8; }
        body { font-family: system-ui, sans-serif; background-color: var(--bg); color: var(--text); display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; }
        .container { background-color: var(--card); padding: 30px; border-radius: 12px; width: 100%; max-width: 600px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); }
        label { display: block; margin-top: 15px; font-weight: 600; font-size: 0.85rem; color: var(--subtext); }
        textarea, select, input, button { width: 100%; padding: 12px; margin-top: 8px; border-radius: 6px; border: 1px solid #334155; background-color: #0f172a; color: var(--text); box-sizing: border-box; }
        textarea { height: 90px; resize: vertical; }
        button { background-color: var(--accent); border: none; font-weight: 600; cursor: pointer; margin-top: 15px; }
        button:disabled { background-color: #475569; }
        .api-box { display: none; background: #090d16; padding: 15px; border-radius: 8px; border: 1px dashed #334155; margin-top: 12px; }
        .record-controls { display: flex; gap: 10px; margin-top: 8px; }
        .record-controls button { margin-top: 0; flex: 1; }
        .btn-danger { background-color: #ef4444; }
        .btn-success { background-color: #22c55e; }
        .divider { text-align: center; color: var(--subtext); margin: 12px 0; font-size: 0.8rem; font-weight: bold; }
    </style>
</head>
<body>

<div class="container">
    <h2>Voice Studio</h2>
    <p style="color: var(--subtext); font-size: 0.9rem;">Convert text to speech or clone your own voice live.</p>
    
    <label for="text">Script Text</label>
    <textarea id="text" placeholder="Type what you want the voice to say..."></textarea>
    
    <label for="engine">Generation Engine</label>
    <select id="engine" onchange="toggleEngineFields()">
        <option value="gtts">Lightweight Engine (Free Standard Voice)</option>
        <option value="elevenlabs">ElevenLabs API (Custom Voice Cloning)</option>
    </select>

    <div id="elevenlabs-fields" class="api-box">
        <label for="api_key">ElevenLabs API Key</label>
        <input type="password" id="api_key" placeholder="Paste your xi-api-key here">
        
        <!-- Record Audio Option -->
        <label>Record Voice Sample Live</label>
        <div class="record-controls">
            <button id="start-rec-btn" type="button" onclick="startRecording()">🎤 Start Mic</button>
            <button id="stop-rec-btn" type="button" class="btn-danger" onclick="stopRecording()" disabled>⏹️ Stop</button>
        </div>
        <audio id="recorded-preview" controls style="display:none; width: 100%; margin-top: 10px;"></audio>

        <div class="divider">— OR —</div>

        <!-- Upload File Option -->
        <label for="clone_file">Upload Audio File (MP3 / WAV)</label>
        <input type="file" id="clone_file" accept="audio/*">
        
        <div class="divider">— OR —</div>

        <!-- Use Existing ID Option -->
        <label for="voice_id">Use Existing Voice ID</label>
        <input type="text" id="voice_id" value="21m00Tcm4TlvDq8ikWAM" placeholder="Default: Rachel">
    </div>

    <button id="generate-btn" onclick="generateSpeech()">Generate Audio</button>

    <div id="audio-box" style="display:none; margin-top:20px; text-align:center;">
        <p>Result:</p>
        <audio id="audio-player" controls style="width: 100%;"></audio>
    </div>
</div>

<script>
let mediaRecorder;
let audioChunks = [];
let recordedAudioBlob = null;

function toggleEngineFields() {
    const engine = document.getElementById('engine').value;
    document.getElementById('elevenlabs-fields').style.display = engine === 'elevenlabs' ? 'block' : 'none';
}

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) audioChunks.push(event.data);
        };

        mediaRecorder.onstop = () => {
            recordedAudioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            const preview = document.getElementById('recorded-preview');
            preview.src = URL.createObjectURL(recordedAudioBlob);
            preview.style.display = 'block';
        };

        mediaRecorder.start();
        document.getElementById('start-rec-btn').disabled = true;
        document.getElementById('stop-rec-btn').disabled = false;
    } catch (err) {
        alert("Microphone access denied or unsupported browser.");
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
        document.getElementById('start-rec-btn').disabled = false;
        document.getElementById('stop-rec-btn').disabled = true;
    }
}

async function generateSpeech() {
    const text = document.getElementById('text').value;
    const engine = document.getElementById('engine').value;
    const apiKey = document.getElementById('api_key').value;
    let voiceId = document.getElementById('voice_id').value;
    const fileInput = document.getElementById('clone_file');
    const btn = document.getElementById('generate-btn');

    if (!text.trim()) return alert("Please enter text.");
    if (engine === 'elevenlabs' && !apiKey.trim()) return alert("ElevenLabs requires an API Key.");

    btn.disabled = true;

    try {
        // Handle Voice Cloning via Live Recording OR File Upload
        if (engine === 'elevenlabs' && (recordedAudioBlob || fileInput.files.length > 0)) {
            btn.innerText = "Cloning Voice...";
            const formData = new FormData();
            formData.append("api_key", apiKey);
            formData.append("name", "Custom_Clone_" + Date.now());

            if (recordedAudioBlob) {
                formData.append("file", recordedAudioBlob, "mic_recording.wav");
            } else if (fileInput.files.length > 0) {
                formData.append("file", fileInput.files[0]);
            }

            const cloneRes = await fetch('/clone-voice', { method: 'POST', body: formData });
            const cloneData = await cloneRes.json();
            
            if (!cloneRes.ok) throw new Error(cloneData.detail || "Voice cloning failed.");
            
            voiceId = cloneData.voice_id;
            document.getElementById('voice_id').value = voiceId;
        }

        // Generate TTS Audio
        btn.innerText = "Generating Speech...";
        const response = await fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, engine, api_key: apiKey, voice_id: voiceId })
        });

        const data = await response.json();
        if (response.ok) {
            const player = document.getElementById('audio-player');
            player.src = 'data:audio/mp3;base64,' + data.audio_base64;
            document.getElementById('audio-box').style.display = 'block';
        } else {
            alert("Error: " + data.detail);
        }
    } catch (err) {
        alert("Request failed: " + err.message);
    } finally {
        btn.disabled = false;
        btn.innerText = "Generate Audio";
    }
}
</script>

</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def get_index():
    return HTMLResponse(content=HTML_LAYOUT)

@app.post("/clone-voice")
async def clone_voice(api_key: str = Form(...), name: str = Form("My Custom Voice"), file: UploadFile = File(...)):
    url = "https://api.elevenlabs.io/v1/voices/add"
    headers = {"xi-api-key": api_key}
    
    file_bytes = await file.read()
    files = {"files": (file.filename, file_bytes, file.content_type)}
    data = {"name": name, "description": "Cloned directly from Voice Studio app"}
    
    response = requests.post(url, headers=headers, data=data, files=files)
    
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=f"ElevenLabs Cloning Error: {response.text}")
    
    res_data = response.json()
    return {"voice_id": res_data.get("voice_id")}

@app.post("/generate")
async def generate_tts(payload: TTSRequest):
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text field cannot be empty.")
    
    if payload.engine == "gtts":
        try:
            tts = gTTS(text=payload.text, lang="en")
            mp3_fp = io.BytesIO()
            tts.write_to_fp(mp3_fp)
            mp3_fp.seek(0)
            return {"audio_base64": base64.b64encode(mp3_fp.read()).decode('utf-8')}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"gTTS error: {str(e)}")

    elif payload.engine == "elevenlabs":
        api_key = payload.api_key or os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            raise HTTPException(status_code=400, detail="ElevenLabs API Key missing.")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{payload.voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }
        data = {"text": payload.text, "model_id": "eleven_monolingual_v1"}

        response = requests.post(url, json=data, headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)

        audio_b64 = base64.b64encode(response.content).decode('utf-8')
        return {"audio_base64": audio_b64}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
