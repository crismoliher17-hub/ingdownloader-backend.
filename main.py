
import os
import random
import re
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI(title="ING Downloader Backend")

ORIGINS = [
    "https://ingdownlader.web.app",
    "https://ingdownloader.web.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

INVIDIOUS_INSTANCES = [
    "https://inv.nadeko.net",
    "https://invidious.nerdvpn.de",
    "https://invidious.drgns.space",
    "https://vid.puffyan.us",
    "https://invidious.flokinet.to"
]

COBALT_INSTANCES = [
    "https://cobalt.api.redlib.onrender.com",
    "https://api.cobalt.tools"
]

def clean_filename(text: str) -> str:
    return re.sub(r'[\/*?:"<>|]', "", text).strip()

async def fetch_from_invidious(endpoint: str):
    instances = INVIDIOUS_INSTANCES.copy()
    random.shuffle(instances)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
        for instance in instances:
            try:
                res = await client.get(f"{instance}{endpoint}")
                if res.status_code == 200:
                    return res.json(), instance
            except Exception:
                continue
    raise HTTPException(status_code=503, detail="Proveedores no disponibles actualmente.")

@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.get("/api/search")
async def search(q: str = Query(..., min_length=1)):
    data, working_instance = await fetch_from_invidious(f"/api/v1/search?q={q}&type=video")
    results = []
    
    for item in data:
        if item.get("type") == "video":
            video_id = item.get("videoId")
            thumb = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
            
            length_sec = item.get("lengthSeconds", 0)
            mins, secs = divmod(length_sec, 60)
            
            results.append({
                "videoId": video_id,
                "title": item.get("title", "Desconocido"),
                "artist": item.get("author", "Artista Desconocido"),
                "duration": f"{mins}:{secs:02d}",
                "views": f"{item.get('viewCount', 0):,}",
                "thumbnail": thumb
            })
            
    return {"results": results, "provider": working_instance}

@app.get("/api/resolve")
async def resolve(video_id: str, title: str = "cancion", artist: str = "artista", format: str = "mp3"):
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "url": youtube_url,
        "downloadMode": "audio" if format == "mp3" else "video",
        "audioFormat": "mp3",
        "quality": "320"
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        for instance in COBALT_INSTANCES:
            try:
                res = await client.post(instance, json=payload, headers=headers)
                if res.status_code == 200 and "url" in res.json():
                    return {
                        "downloadUrl": res.json()["url"],
                        "filename": clean_filename(f"{artist} - {title}.{format}")
                    }
            except Exception:
                continue

    safe_name = clean_filename(f"{artist} - {title}.mp3")
    return {"downloadUrl": f"https://inv.nadeko.net/latest_version?id={video_id}&ita=140", "filename": safe_name}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))