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

# Opciones optimizadas para saltar la detección de bots en servidores cloud (Render)
YDL_BASE_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'extractor_args': {
        'youtube': {
            'player_client': ['ios', 'web_creator', 'mweb']
        }
    }
}

@app.get("/")
def home():
    return {"status": "ok", "message": "ingdownloader API está corriendo"}

@app.get("/api/search")
def search_youtube(q: str, type: str = "song"):
    try:
        search_query = f"ytsearch6:{q} playlist" if type == "album" else f"ytsearch6:{q}"
        
        ydl_opts = {
            **YDL_BASE_OPTS,
            'extract_flat': 'in_playlist',
            'skip_download': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(search_query, download=False)
            entries = res.get('entries', []) if res else []
            
            results = []
            for entry in entries:
                if not entry:
                    continue
                video_id = entry.get("id")
                results.append({
                    "id": video_id,
                    "title": entry.get("title"),
                    "artist": entry.get("uploader") or "YouTube",
                    "duration": f"{int(entry.get('duration', 0)//60)}:{int(entry.get('duration', 0)%60):02d}" if entry.get('duration') else "3:00",
                    "thumbnail": f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg" if video_id else "",
                    "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else entry.get("url", "")
                })
            return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/album")
def get_album_tracks(url: str):
    try:
        ydl_opts = {
            **YDL_BASE_OPTS,
            'extract_flat': 'in_playlist',
            'skip_download': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(url, download=False)
            if not res:
                raise HTTPException(status_code=404, detail="No se pudo obtener información de la URL")
                
            entries = res.get('entries', [])
            tracks = []
            
            if entries:
                for entry in entries:
                    if not entry:
                        continue
                    video_id = entry.get("id")
                    tracks.append({
                        "id": video_id,
                        "title": entry.get("title"),
                        "artist": entry.get("uploader") or res.get("title") or "YouTube",
                        "duration": f"{int(entry.get('duration', 0)//60)}:{int(entry.get('duration', 0)%60):02d}" if entry.get('duration') else "3:00",
                        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg" if video_id else "",
                        "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
                    })
            else:
                video_id = res.get("id")
                tracks.append({
                    "id": video_id,
                    "title": res.get("title"),
                    "artist": res.get("uploader") or "YouTube",
                    "duration": f"{int(res.get('duration', 0)//60)}:{int(res.get('duration', 0)%60):02d}" if res.get('duration') else "3:00",
                    "thumbnail": f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg" if video_id else "",
                    "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else url
                })
                
            return {"tracks": tracks, "title": res.get("title") or "Álbum"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download")
def get_download_link(url: str, format: str = "mp3"):
    try:
        ydl_opts = {
            **YDL_BASE_OPTS,
            'format': 'bestaudio/best' if format == 'mp3' else 'bestvideo+bestaudio/best',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise HTTPException(status_code=404, detail="No se encontró la información del video")
                
            return {
                "title": info.get("title"),
                "download_url": info.get("url"),
                "format": format
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
