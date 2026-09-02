from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

app = FastAPI(title="ingdownloader API")

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
    'extractor_args': {
        'youtube': {
            'player_client': ['android_creator', 'ios', 'web']
        }
    }
}

@app.get("/")
def home():
    return {"status": "ok", "message": "ingdownloader API activa"}

@app.get("/api/search")
def search_youtube(q: str, type: str = "song"):
    try:
        search_query = f"ytsearch6:{q}"
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
                    "artist": entry.get("uploader") or "Artista desconocido",
                    "duration": f"{int(entry.get('duration', 0)//60)}:{int(entry.get('duration', 0)%60):02d}" if entry.get('duration') else "3:30",
                    "thumbnail": f"https://i.ytimg.com/vi/{v_id}/hqdefault.jpg" if v_id else "",
                    "url": f"https://www.youtube.com/watch?v={v_id}" if v_id else ""
                })
            return {"results": results}
    except Exception as e:
        # Retorna lista vacía en lugar de colapsar con 500
        return {"results": []}

@app.get("/api/album")
def get_album_tracks(url: str):
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            res = ydl.extract_info(url, download=False)
            if not res:
                return {"tracks": [], "title": "Álbum"}
                
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
    except Exception as e:
        # Devuelve estructura limpia vacía en lugar de lanzar Error 500
        return {"tracks": [], "title": "Álbum no disponible"}

@app.get("/api/download")
def get_download_link(url: str, format: str = "mp3"):
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise HTTPException(status_code=404, detail="Video no encontrado")
            return {
                "title": info.get("title"),
                "download_url": info.get("url"),
                "format": format
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail="YouTube bloqueó la petición temporalmente")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
