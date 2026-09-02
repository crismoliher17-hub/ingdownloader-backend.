from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import urllib.request
import urllib.parse
import json
import re
import yt_dlp

app = FastAPI(title="ING Downloader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': 'in_playlist',
    'skip_download': True,
    'nocheckcertificate': True,
    'ignoreerrors': True,
}

def clean_filename(title: str) -> str:
    """Limpia caracteres inválidos para nombres de archivo en Windows/Linux"""
    clean = re.sub(r'[\\/*?:"<>|]', "", title)
    return clean.strip() or "cancion"

@app.get("/")
def home():
    return {"status": "ok", "message": "ING Downloader API Activa"}

@app.get("/api/search")
def search_youtube(q: str, type: str = "song"):
    try:
        query = f"ytsearch10:{q} playlist" if type == "album" else f"ytsearch10:{q}"
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            res = ydl.extract_info(query, download=False)
            entries = res.get('entries', []) if res else []
            
            results = []
            for entry in entries:
                if not entry:
                    continue
                v_id = entry.get("id")
                results.append({
                    "id": v_id,
                    "title": entry.get("title", "Sin título"),
                    "artist": entry.get("uploader") or "Artista Desconocido",
                    "duration": f"{int(entry.get('duration', 0)//60)}:{int(entry.get('duration', 0)%60):02d}" if entry.get('duration') else "3:30",
                    "thumbnail": f"https://i.ytimg.com/vi/{v_id}/hqdefault.jpg" if v_id else "",
                    "url": f"https://www.youtube.com/watch?v={v_id}" if v_id else ""
                })
            return {"results": results}
    except Exception:
        return {"results": []}

@app.get("/api/album")
def get_album_tracks(url: str):
    try:
        target = url if url.startswith("http") else f"ytsearch1:{url} album"
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            res = ydl.extract_info(target, download=False)
            if not res:
                return {"tracks": [], "title": "Álbum no encontrado"}

            if 'entries' in res and res['entries'] and target.startswith("ytsearch"):
                first_item = res['entries'][0]
                if first_item:
                    p_id = first_item.get('id')
                    res = ydl.extract_info(f"https://www.youtube.com/playlist?list={p_id}", download=False) or res

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
                
            return {"tracks": tracks, "title": res.get("title") or "Álbum Seleccionado"}
    except Exception:
        return {"tracks": [], "title": "Error al cargar álbum"}

@app.get("/api/download")
def get_download_link(url: str, format: str = "mp3", quality: str = "320"):
    video_id = url.split("v=")[-1].split("&")[0] if "v=" in url else url.split("/")[-1]
    
    # Intento 1: API de Cobalt con calidad y formato
    try:
        cobalt_payload = json.dumps({
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "downloadMode": "audio" if format == "mp3" else "auto",
            "audioFormat": "mp3",
            "audioBitrate": quality if format == "mp3" else "320"
        }).encode('utf-8')
        
        req = urllib.request.Request(
            "https://api.cobalt.tools/api/json",
            data=cobalt_payload,
            headers={'Content-Type': 'application/json', 'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if "url" in data:
                return {
                    "download_url": data["url"],
                    "filename": f"{clean_filename(data.get('filename', 'cancion'))}.{format}"
                }
    except Exception:
        pass

    # Intento 2: Fallback Piped API
    try:
        req = urllib.request.Request(
            f"https://pipedapi.kavin.rocks/streams/{video_id}",
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=6) as response:
            data = json.loads(response.read().decode('utf-8'))
            streams = data.get("audioStreams", []) if format == "mp3" else data.get("videoStreams", [])
            if streams:
                title = clean_filename(data.get("title", "cancion"))
                return {
                    "download_url": streams[0].get("url"),
                    "filename": f"{title}.{format}"
                }
    except Exception:
        pass

    raise HTTPException(status_code=400, detail="No se pudo procesar el archivo")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
