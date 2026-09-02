import urllib.request
import json

@app.get("/api/download")
def get_download_link(url: str, format: str = "mp3"):
    # Extraer el ID del video de la URL
    video_id = url.split("v=")[-1].split("&")[0] if "v=" in url else url.split("/")[-1]
    
    # 1. Intentar obtener el stream desde la API pública de Piped (evita bloqueo de IP)
    try:
        req = urllib.request.Request(
            f"https://pipedapi.kavin.rocks/streams/{video_id}",
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            audio_streams = data.get("audioStreams", [])
            if audio_streams:
                # Tomar la primera opción de audio disponible
                best_audio = audio_streams[0].get("url")
                return {
                    "title": data.get("title", "Audio"),
                    "download_url": best_audio,
                    "format": format
                }
    except Exception:
        pass

    # 2. Fallback con yt-dlp tradicional
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            if info and info.get("url"):
                return {
                    "title": info.get("title"),
                    "download_url": info.get("url"),
                    "format": format
                }
    except Exception:
        pass

    raise HTTPException(status_code=400, detail="No se pudo generar el enlace de reproduccion")
