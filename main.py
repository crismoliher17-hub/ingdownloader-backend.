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

# Lista de instancias de Piped para la búsqueda rápida y estable
PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://api.piped.private.coffee",
    "https://pipedapi.mha.fi",
    "https://pipedapi.backend.art"
]

COBALT_INSTANCES = [
    "https://cobalt.api.redlib.onrender.com",
    "https://api.cobalt.tools"
]

def clean_filename(text: str) -> str:
    return re.sub(r'[\/*?:"<>|]', "", text).strip()

async def fetch_piped_search(query: str):
    instances = PIPED_INSTANCES.copy()
    random.shuffle(instances)
    async with httpx.AsyncClient(timeout=8.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
        for instance in instances:
            try:
                res = await client.get(f"{instance}/search?q={query}&filter=music_songs")
                if res.status_code == 200:
                    data = res.json()
                    items = data.get("items", [])
                    if items:
                        return items
            except Exception:
                continue
            
        # Intento de respaldo sin filtro si no hay resultados
        for instance in instances:
            try:
                res = await client.get(f"{instance}/search?q={query}&filter=all")
                if res.status_code == 200:
                    data = res.json()
                    items = data.get("items", [])
                    if items:
                        return items
            except Exception:
                continue

    raise HTTPException(status_code=503, detail="Servidores no disponibles.")

@app.get("/api/search")
async def search(q: str = Query(..., min_length=1)):
    items = await fetch_piped_search(q)
    results = []
    
    for item in items:
        # Piped devuelve 'stream' para videos/canciones
        if item.get("type") == "stream":
            url_path = item.get("url", "")
            v_id = url_path.replace("/watch?v=", "") if "/watch?v=" in url_path else item.get("id", "")
            
            if not v_id:
                continue

            duration_sec = item.get("duration", 0)
            mins, secs = divmod(duration_sec if duration_sec > 0 else 0, 60)
            
            results.append({
                "videoId": v_id,
                "title": item.get("title", "Desconocido"),
                "artist": item.get("uploaderName", "Artista Desconocido"),
                "duration": f"{mins}:{secs:02d}",
                "thumbnail": item.get("thumbnail", f"https://img.youtube.com/vi/{v_id}/hqdefault.jpg")
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

    # Servidor de respaldo alternativo si falla Cobalt
    fallback_stream = f"https://pipedapi.kavin.rocks/streams/{video_id}"
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            res = await client.get(fallback_stream)
            if res.status_code == 200:
                audio_streams = res.json().get("audioStreams", [])
                if audio_streams:
                    return {
                        "downloadUrl": audio_streams[0]["url"],
                        "filename": clean_filename(f"{artist} - {title}.mp3")
                    }
        except Exception:
            pass

    raise HTTPException(status_code=500, detail="No se pudo resolver el enlace de descarga.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))