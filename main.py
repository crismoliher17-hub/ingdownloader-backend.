import os
import random
import re
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI(title="ING Downloader Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

INVIDIOUS_INSTANCES = [
    "https://inv.nadeko.net",
    "https://invidious.nerdvpn.de",
    "https://invidious.drgns.space",
    "https://vid.puffyan.us"
]

COBALT_INSTANCES = [
    "https://cobalt.api.redlib.onrender.com",
    "https://api.cobalt.tools"
]

def clean_filename(text: str) -> str:
    return re.sub(r'[\/*?:"<>|]', "", text).strip()

async def fetch_invidious(endpoint: str):
    instances = INVIDIOUS_INSTANCES.copy()
    random.shuffle(instances)
    async with httpx.AsyncClient(timeout=10.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
        for instance in instances:
            try:
                res = await client.get(f"{instance}{endpoint}")
                if res.status_code == 200:
                    return res.json()
            except Exception:
                continue
    raise HTTPException(status_code=503, detail="Servidores no disponibles.")

@app.get("/api/search")
async def search(q: str = Query(..., min_length=1)):
    data = await fetch_invidious(f"/api/v1/search?q={q}&type=video")
    results = []
    for item in data:
        if item.get("type") == "video":
            v_id = item.get("videoId")
            mins, secs = divmod(item.get("lengthSeconds", 0), 60)
            results.append({
                "videoId": v_id,
                "title": item.get("title", "Desconocido"),
                "artist": item.get("author", "Artista Desconocido"),
                "duration": f"{mins}:{secs:02d}",
                "thumbnail": f"https://img.youtube.com/vi/{v_id}/hqdefault.jpg"
            })
    return {"results": results}

@app.get("/api/resolve")
async def resolve(video_id: str, title: str = "cancion", artist: str = "artista"):
    yt_url = f"https://www.youtube.com/watch?v={video_id}"
    payload = {"url": yt_url, "downloadMode": "audio", "audioFormat": "mp3", "quality": "320"}
    headers = {"Accept": "application/json", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=12.0) as client:
        for inst in COBALT_INSTANCES:
            try:
                res = await client.post(inst, json=payload, headers=headers)
                if res.status_code == 200 and "url" in res.json():
                    return {
                        "downloadUrl": res.json()["url"],
                        "filename": clean_filename(f"{artist} - {title}.mp3")
                    }
            except Exception:
                continue

    fallback_stream = f"https://inv.nadeko.net/latest_version?id={video_id}&ita=140"
    return {"downloadUrl": fallback_stream, "filename": clean_filename(f"{artist} - {title}.mp3")}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))