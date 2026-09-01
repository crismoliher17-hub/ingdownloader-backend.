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

@app.get("/")
def home():
    return {"status": "ok", "message": "ingdownloader API está corriendo"}

@app.get("/api/search")
def search_youtube(q: str):
    try:
        ydl_opts = {
            'extract_flat': 'in_playlist',
            'skip_download': True,
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(f"ytsearch6:{q}", download=False)
            entries = res.get('entries', [])
            
            results = []
            for entry in entries:
                if not entry:
                    continue
                results.append({
                    "id": entry.get("id"),
                    "title": entry.get("title"),
                    "artist": entry.get("uploader") or "YouTube",
                    "duration": f"{int(entry.get('duration', 0)//60)}:{int(entry.get('duration', 0)%60):02d}" if entry.get('duration') else "3:00",
                    "thumbnail": f"https://i.ytimg.com/vi/{entry.get('id')}/mqdefault.jpg",
                    "url": f"https://www.youtube.com/watch?v={entry.get('id')}"
                })
            return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/album")
def get_album_tracks(url: str):
    """Extrae las canciones de una lista de reproducción o álbum"""
    try:
        ydl_opts = {
            'extract_flat': 'in_playlist',
            'skip_download': True,
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(url, download=False)
            entries = res.get('entries', [])
            
            tracks = []
            for entry in entries:
                if not entry:
                    continue
                tracks.append({
                    "id": entry.get("id"),
                    "title": entry.get("title"),
                    "artist": entry.get("uploader") or res.get("title") or "YouTube",
                    "duration": f"{int(entry.get('duration', 0)//60)}:{int(entry.get('duration', 0)%60):02d}" if entry.get('duration') else "3:00",
                    "thumbnail": f"https://i.ytimg.com/vi/{entry.get('id')}/mqdefault.jpg",
                    "url": f"https://www.youtube.com/watch?v={entry.get('id')}"
                })
            return {"tracks": tracks, "title": res.get("title")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download")
def get_download_link(url: str, format: str = "mp3"):
    try:
        ydl_opts = {
            'format': 'bestaudio/best' if format == 'mp3' else 'bestvideo+bestaudio/best',
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
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
