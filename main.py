import os
import random
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI(title="ING Downloader Backend")

# 1. Configuración de CORS permitiendo dominios reales y locales
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

# 2. Pool de instancias públicas de Invidious (rotación automática si una cae)
INVIDIOUS_INSTANCES = [
    "https://inv.nadeko.net",
    "https://invidious.nerdvpn.de",
    "https://invidious.drgns.space",
    "https://vid.puffyan.us",
    "https://invidious.flokinet.to",
    "https://invidious.projectsegfau.lt"
]

# Instancias públicas de Cobalt para obtener enlaces directos de reproducción/descarga
COBALT_INSTANCES = [
    "https://cobalt.api.redlib.onrender.com",
    "https://api.cobalt.tools"
]

async def fetch_from_invidious(endpoint: str):
    """Intenta consultar múltiples instancias de Invidious en secuencia si una falla."""
    instances = INVIDIOUS_INSTANCES.copy()
    random.shuffle(instances)  # Balanceo de carga aleatorio
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
        for instance in instances:
            try:
                url = f"{instance}{endpoint}"
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    return data, instance
            except Exception:
                continue
                
    raise HTTPException(
        status_code=503, 
        detail="Todos los proveedores de búsqueda están saturados o caídos momentáneamente."
    )

@app.get("/api/health")
async def health():
    return {"status": "ok", "origins": ORIGINS}

@app.get("/api/search")
async def search(q: str = Query(..., min_length=1)):
    encoded_q = httpx.URL(q).raw_path.decode("utf-8") if hasattr(httpx.URL(q), "raw_path") else q
    endpoint = f"/api/v1/search?q={q}&type=video"
    data, working_instance = await fetch_from_invidious(endpoint)
    
    # Normalización de resultados para el frontend
    results = []
    for item in data:
        if item.get("type") == "video":
            results.append({
                "videoId": item.get("videoId"),
                "title": item.get("title"),
                "author": item.get("author"),
                "lengthSeconds": item.get("lengthSeconds"),
                "publishedText": item.get("publishedText"),
                "viewCount": item.get("viewCount"),
                "thumbnail": item.get("videoThumbnails", [{}])[0].get("url", "")
            })
    return {"results": results, "provider": working_instance}

@app.get("/api/resolve")
async def resolve(video_id: str, format: str = "mp3", quality: str = "320"):
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
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
                if res.status_code == 200:
                    data = res.json()
                    if "url" in data:
                        return {"downloadUrl": data["url"]}
            except Exception:
                continue

    # Fallback directo si Cobalt no responde
    return {"downloadUrl": f"https://inv.nadeko.net/latest_version?id={video_id}&ita=140"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
