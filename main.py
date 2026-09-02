from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import urllib.request
import json
import yt_dlp

app = FastAPI(title="ingdownloader API")

# Configuración CORS para permitir peticiones desde tu frontend en Firebase
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Opciones ligeras de yt-dlp para búsqueda sin sobrecargar la IP
YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': 'in_playlist',
    'skip_download': True,
    'nocheckcertificate': True,
    'ignoreerrors': True,
}

@app.get("/")
def home():
    return {"status": "ok", "message": "ingdownloader API activa"}

# 1. BUSCADOR (Canciones y Álbumes)
@app.get("/api/search")
def search_youtube(q: str, type: str = "song"):
    try:
        search_query = f"ytsearch8:{q} playlist" if type == "album" else f"ytsearch8:{q}"
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            res = ydl.extract_info(search_query, download=False)
            entries = res.get('entries', []) if res else []
            
            results = []
            for entry in entries:
                if not entry:
                    continue
                v_id = entry.get("id")
                results.append({
                    "id": v_id,
                    "title": entry.get("title", "Sin título"),
                    "artist": entry.get("uploader") or "YouTube",
                    "duration": f"{int(entry.get('duration', 0)//60)}:{int(entry.get('duration', 0)%60):02d}" if entry.get('duration') else "3:30",
                    "thumbnail": f"https://i.ytimg.com/vi/{v_id}/hqdefault.jpg" if v_id else "",
                    "url": f"https://www.youtube.com/watch?v={v_id}" if v_id else ""
                })
            return {"results": results}
    except Exception:
        return {"results": []}

# 2. CARGADOR DE ÁLBUMES / PLAYLISTS
@app.get("/api/album")
def get_album_tracks(url: str):
    try:
        target = url if url.startswith("http") else f"ytsearch1:{url} album"
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            res = ydl.extract_info(target, download=False)
            if not res:
                return {"tracks": [], "title": "Álbum no encontrado"}
                
            if 'entries' in res and res['entries']:
                first_item = res['entries'][0]
                if target.startswith("ytsearch") and first_item:
                    p_id = first_item.get('id')
                    playlist_url = f"https://www.youtube.com/playlist?list={p_id}"
                    res = ydl.extract_info(playlist_url, download=False) or res

            entries = res.get('entries', [])
            tracks = []
            
            if entries:
                for entry in entries:
                    if not entry:
                        continue
                    v_id = entry.get("id")
                    tracks.append({
                        "id": v_id,
                        "title": entry.get("title", "Pista"),
                        "artist": entry.get("uploader") or res.get("title") or "YouTube",
                        "duration": f"{int(entry.get('duration', 0)//60)}:{int(entry.get('duration', 0)%60):02d}" if entry.get('duration') else "3:00",
                        "thumbnail": f"https://i.ytimg.com/vi/{v_id}/hqdefault.jpg" if v_id else "",
                        "url": f"https://www.youtube.com/watch?v={v_id}" if v_id else ""
                    })
            else:
                v_id = res.get("id")
                tracks.append({
                    "id": v_id,
                    "title": res.get("title", "Canción"),
                    "artist": res.get("uploader") or "YouTube",
                    "duration": f"{int(res.get('duration', 0)//60)}:{int(res.get('duration', 0)%60):02d}" if res.get('duration') else "3:00",
                    "thumbnail": f"https://i.ytimg.com/vi/{v_id}/hqdefault.jpg" if v_id else "",
                    "url": f"https://www.youtube.com/watch?v={v_id}" if v_id else url
                })
                
            return {"tracks": tracks, "title": res.get("title") or "Álbum"}
    except Exception:
        return {"tracks": [], "title": "Álbum no disponible"}

# 3. GENERADOR DE ENLACES DE REPRODUCCIÓN Y DESCARGA SIN BLOQUEOS
@app.get("/api/download")
def get_download_link(url: str, format: str = "mp3"):
    video_id = url.split("v=")[-1].split("&")[0] if "v=" in url else url.split("/")[-1]
    
    # ESTRATEGIA 1: Usar la API pública de Cobalt (Especializada en descargas directas sin bloqueo)
    try:
        cobalt_url = "https://api.cobalt.tools/api/json"
        payload = json.dumps({
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "downloadMode": "audio" if format == "mp3" else "auto",
            "audioFormat": "mp3"
        }).encode('utf-8')
        
        req = urllib.request.Request(
            cobalt_url,
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0'
            },
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if "url" in data:
                return {
                    "title": "Descarga de Música",
                    "download_url": data["url"],
                    "format": format
                }
    except Exception:
        pass

    # ESTRATEGIA 2: Fallback con Piped API (Streaming directo e inmune a bloques de IP servidor)
    try:
        req = urllib.request.Request(
            f"https://pipedapi.kavin.rocks/streams/{video_id}",
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=6) as response:
            data = json.loads(response.read().decode('utf-8'))
            if format == "mp3":
                streams = data.get("audioStreams", [])
            else:
                streams = data.get("videoStreams", [])
                
            if streams:
                return {
                    "title": data.get("title", "Audio"),
                    "download_url": streams[0].get("url"),
                    "format": format
                }
    except Exception:
        pass

    # ESTRATEGIA 3: Invidious API
    try:
        req = urllib.request.Request(
            f"https://inv.idhol.de/api/v1/videos/{video_id}",
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=6) as response:
            data = json.loads(response.read().decode('utf-8'))
            format_streams = data.get("adaptiveFormats", [])
            for stream in format_streams:
                if format == "mp3" and "audio" in stream.get("type", ""):
                    return {
                        "title": data.get("title", "Audio"),
                        "download_url": stream.get("url"),
                        "format": format
                    }
    except Exception:
        pass

    raise HTTPException(status_code=400, detail="No se pudo procesar la solicitud de descarga")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
