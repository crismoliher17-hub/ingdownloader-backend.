from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

app = FastAPI(title="ingdownloader API")

# Habilitar CORS para permitir solicitudes desde cualquier origen (Firebase, localhost, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    """Endpoint de comprobación"""
    return {"status": "ok", "message": "ingdownloader API está corriendo"}

@app.get("/api/search")
def search_youtube(q: str):
    """Busca videos en YouTube usando yt-dlp"""
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

@app.get("/api/download")
def get_download_link(url: str, format: str = "mp3"):
    """Obtiene el enlace directo de descarga"""
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
