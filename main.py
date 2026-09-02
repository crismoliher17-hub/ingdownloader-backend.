import os
import re
import logging
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import httpx
from async_lru import alru_cache

# Configuración de Logging para trazabilidad real (Punto 1)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ingdownloader")

app = FastAPI(title="ING Downloader Backend Pro")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lista de instancias por defecto (Punto 5)
DEFAULT_PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://api.piped.private.coffee",
    "https://pipedapi.mha.fi",
    "https://pipedapi.backend.art"
]

def get_instances():
    """Permite sobreescribir instancias desde variables de entorno sin tocar código (Punto 5)"""
    env_instances = os.getenv("PIPED_INSTANCES")
    if env_instances:
        return [i.strip() for i in env_instances.split(",") if i.strip()]
    return DEFAULT_PIPED_INSTANCES

# Sanitización de nombres de archivo limpia y usada (Punto 7)
def clean_filename(text: str) -> str:
    cleaned = re.sub(r'[\/*?:"<>|]', "", text).strip()
    return cleaned if cleaned else "audio"

# Validación estricta del patrón de video_id de YouTube (Punto 6)
YOUTUBE_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{11}$")

# Caché en memoria para búsquedas por 10 minutos (Punto 4)
@alru_cache(maxsize=128, ttl=600)
async def cached_search(query: str):
    instances = get_instances()
    # Timeouts diferenciados: conectarse rápido (3s), esperar datos razonable (7s) (Punto 2)
    timeout_config = httpx.Timeout(connect=3.0, read=7.0, write=5.0, pool=5.0)
    
    async with httpx.AsyncClient(timeout=timeout_config, headers={"User-Agent": "Mozilla/5.0"}) as client:
        for instance in instances:
            try:
                res = await client.get(f"{instance}/search?q={query}&filter=music_songs")
                if res.status_code == 200:
                    items = res.json().get("items", [])
                    results = []
                    for item in items:
                        if item.get("type") == "stream":
                            url_path = item.get("url", "")
                            v_id = url_path.replace("/watch?v=", "") if "/watch?v=" in url_path else item.get("id", "")
                            if not v_id or not YOUTUBE_ID_REGEX.match(v_id):
                                continue
                            mins, secs = divmod(item.get("duration", 0), 60)
                            results.append({
                                "videoId": v_id,
                                "title": item.get("title", "Desconocido"),
                                "artist": item.get("uploaderName", "Artista Desconocido"),
                                "duration": f"{mins}:{secs:02d}",
                                "thumbnail": item.get("thumbnail", f"https://img.youtube.com/vi/{v_id}/hqdefault.jpg")
                            })
                    if results:
                        logger.info(f"Búsqueda exitosa para '{query}' usando instancia: {instance}")
                        return results
            except httpx.RequestError as exc:
                # Loggear el motivo exacto de la falla sin silenciar a ciegas (Punto 1)
                logger.warning(f"Error al conectar con {instance} para '{query}': {exc}")
            except Exception as exc:
                logger.error(f"Error inesperado procesando {instance}: {exc}")

    raise HTTPException(status_code=503, detail="No hay servidores de búsqueda disponibles en este momento.")

@app.get("/api/search")
async def search(q: str = Query(..., min_length=1)):
    results = await cached_search(q)
    return {"results": results}

@app.get("/api/stream/{video_id}")
async def stream_audio(
    video_id: str = Path(..., description="ID del video de YouTube")
):
    # Validación de formato de video_id (Punto 6)
    if not YOUTUBE_ID_REGEX.match(video_id):
        raise HTTPException(status_code=400, detail="Formato de video_id inválido.")

    instances = get_instances()
    timeout_config = httpx.Timeout(connect=3.0, read=10.0, write=5.0, pool=5.0)
    audio_url = None

    async with httpx.AsyncClient(timeout=timeout_config, headers={"User-Agent": "Mozilla/5.0"}) as client:
        for instance in instances:
            try:
                res = await client.get(f"{instance}/streams/{video_id}")
                if res.status_code == 200:
                    streams = res.json().get("audioStreams", [])
                    if streams:
                        audio_url = streams[0].get("url")
                        logger.info(f"Stream de audio obtenido para {video_id} desde {instance}")
                        break
            except Exception as exc:
                logger.warning(f"Falla al obtener stream de {instance} para {video_id}: {exc}")

    if not audio_url:
        raise HTTPException(status_code=404, detail="Audio no disponible o restringido.")

    # Generador con control de desconexión del cliente (Punto 3)
    async def audio_generator() -> AsyncGenerator[bytes, None]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream("GET", audio_url) as response:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        yield chunk
        except (httpx.StreamError, asyncio.CancelledError):
            logger.info(f"Cliente desconectado a mitad de streaming para ID: {video_id}")
            return

    return StreamingResponse(
        audio_generator(), 
        media_type="audio/mpeg",
        headers={"Content-Disposition": f'inline; filename="{clean_filename(video_id)}.mp3"'}
    )

if __name__ == "__main__":
    import uvicorn
    import asyncio
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))