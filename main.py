from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import urllib.request
import json

app = FastAPI(title="ingdownloader API")


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# CONFIGURACIÓN GENERAL DE YT-DLP
# ============================================================

YDL_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "nocheckcertificate": True,
}


# ============================================================
# CONFIGURACIÓN ESPECÍFICA PARA AUDIO
# ============================================================

AUDIO_OPTS = {
    "quiet": True,
    "no_warnings": False,
    "noplaylist": True,
    "skip_download": True,
    "nocheckcertificate": True,

    # Mejor formato de audio disponible
    "format": "bestaudio/best",

    # Evita problemas con listas de reproducción
    "extract_flat": False,
}


# ============================================================
# RUTA PRINCIPAL
# ============================================================

@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "ingdownloader API activa"
    }


# ============================================================
# BÚSQUEDA DE YOUTUBE
# ============================================================

@app.get("/api/search")
def search_youtube(q: str, type: str = "song"):

    if not q or not q.strip():
        return {"results": []}

    try:

        search_query = f"ytsearch6:{q}"

        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:

            res = ydl.extract_info(
                search_query,
                download=False
            )

            if not res:
                return {"results": []}

            entries = res.get("entries", [])

            results = []

            for entry in entries:

                if not entry:
                    continue

                v_id = entry.get("id")

                if not v_id:
                    continue

                duration_seconds = entry.get("duration")

                if duration_seconds:
                    duration = (
                        f"{int(duration_seconds // 60)}:"
                        f"{int(duration_seconds % 60):02d}"
                    )
                else:
                    duration = "3:30"

                results.append({
                    "id": v_id,

                    "title": entry.get(
                        "title",
                        "Sin título"
                    ),

                    "artist": (
                        entry.get("uploader")
                        or entry.get("channel")
                        or "Artista desconocido"
                    ),

                    "duration": duration,

                    "thumbnail": (
                        f"https://i.ytimg.com/vi/"
                        f"{v_id}/hqdefault.jpg"
                    ),

                    "url": (
                        f"https://www.youtube.com/watch?v={v_id}"
                    )
                })

            return {
                "results": results
            }

    except Exception as e:

        print("ERROR EN SEARCH:", repr(e))

        return {
            "results": []
        }


# ============================================================
# OBTENER CANCIONES DE UN ÁLBUM / PLAYLIST
# ============================================================

@app.get("/api/album")
def get_album_tracks(url: str):

    if not url or not url.strip():
        return {
            "tracks": [],
            "title": "Álbum no disponible"
        }

    try:

        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:

            res = ydl.extract_info(
                url,
                download=False
            )

            if not res:

                return {
                    "tracks": [],
                    "title": "Álbum no disponible"
                }

            entries = res.get("entries")

            tracks = []

            # ------------------------------------------------
            # PLAYLIST / ÁLBUM
            # ------------------------------------------------

            if entries:

                for entry in entries:

                    if not entry:
                        continue

                    v_id = entry.get("id")

                    if not v_id:
                        continue

                    duration_seconds = entry.get("duration")

                    if duration_seconds:

                        duration = (
                            f"{int(duration_seconds // 60)}:"
                            f"{int(duration_seconds % 60):02d}"
                        )

                    else:
                        duration = "3:00"

                    tracks.append({

                        "id": v_id,

                        "title": entry.get(
                            "title",
                            "Pista"
                        ),

                        "artist": (
                            entry.get("uploader")
                            or res.get("uploader")
                            or res.get("title")
                            or "YouTube"
                        ),

                        "duration": duration,

                        "thumbnail": (
                            f"https://i.ytimg.com/vi/"
                            f"{v_id}/hqdefault.jpg"
                        ),

                        "url": (
                            f"https://www.youtube.com/watch?v={v_id}"
                        )
                    })

            # ------------------------------------------------
            # VIDEO INDIVIDUAL
            # ------------------------------------------------

            else:

                v_id = res.get("id")

                if v_id:

                    duration_seconds = res.get("duration")

                    if duration_seconds:

                        duration = (
                            f"{int(duration_seconds // 60)}:"
                            f"{int(duration_seconds % 60):02d}"
                        )

                    else:
                        duration = "3:00"

                    tracks.append({

                        "id": v_id,

                        "title": res.get(
                            "title",
                            "Canción"
                        ),

                        "artist": (
                            res.get("uploader")
                            or "YouTube"
                        ),

                        "duration": duration,

                        "thumbnail": (
                            f"https://i.ytimg.com/vi/"
                            f"{v_id}/hqdefault.jpg"
                        ),

                        "url": (
                            f"https://www.youtube.com/watch?v={v_id}"
                        )
                    })

            return {
                "tracks": tracks,
                "title": res.get(
                    "title",
                    "Álbum"
                )
            }

    except Exception as e:

        print("ERROR EN ALBUM:", repr(e))

        return {
            "tracks": [],
            "title": "Álbum no disponible"
        }


# ============================================================
# OBTENER URL DE AUDIO
# ============================================================

@app.get("/api/download")
def get_download_link(
    url: str,
    format: str = "mp3"
):

    if not url or not url.strip():

        raise HTTPException(
            status_code=400,
            detail="Debes proporcionar una URL de YouTube"
        )

    print("=" * 60)
    print("NUEVA SOLICITUD DE DESCARGA")
    print("URL:", url)
    print("FORMATO:", format)
    print("=" * 60)


    # ========================================================
    # MÉTODO 1: PIPED API
    # ========================================================

    try:

        video_id = extract_video_id(url)

        if video_id:

            print(
                "Intentando obtener audio mediante Piped..."
            )

            piped_url = (
                "https://pipedapi.kavin.rocks/"
                f"streams/{video_id}"
            )

            req = urllib.request.Request(
                piped_url,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )

            with urllib.request.urlopen(
                req,
                timeout=8
            ) as response:

                data = json.loads(
                    response.read().decode()
                )

            audio_streams = data.get(
                "audioStreams",
                []
            )

            if audio_streams:

                # Ordenar por bitrate cuando exista
                audio_streams = sorted(
                    audio_streams,
                    key=lambda x: (
                        x.get("bitrate") or
                        x.get("quality") or
                        0
                    ),
                    reverse=True
                )

                best_audio = audio_streams[0]

                stream_url = best_audio.get("url")

                if stream_url:

                    print(
                        "Piped encontró un stream de audio."
                    )

                    return {

                        "success": True,

                        "title": (
                            data.get("title")
                            or "Audio"
                        ),

                        "download_url": stream_url,

                        "format": (
                            best_audio.get("format")
                            or format
                        ),

                        "mime_type": (
                            best_audio.get("mimeType")
                        ),

                        "duration": (
                            data.get("duration")
                        )
                    }

    except Exception as e:

        print(
            "PIPED FALLÓ:",
            repr(e)
        )


    # ========================================================
    # MÉTODO 2: YT-DLP
    # ========================================================

    try:

        print(
            "Intentando obtener audio mediante yt-dlp..."
        )

        with yt_dlp.YoutubeDL(
            AUDIO_OPTS
        ) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

            if not info:

                raise Exception(
                    "yt-dlp no devolvió información"
                )

            print(
                "Video encontrado:",
                info.get("title")
            )

            formats = info.get(
                "formats",
                []
            )

            print(
                "Cantidad de formatos:",
                len(formats)
            )

            # ------------------------------------------------
            # Buscar formatos que realmente tengan URL
            # y contengan audio
            # ------------------------------------------------

            audio_formats = []

            for f in formats:

                stream_url = f.get("url")

                audio_codec = f.get(
                    "acodec"
                )

                if not stream_url:
                    continue

                if not audio_codec:
                    continue

                if audio_codec == "none":
                    continue

                audio_formats.append(f)


            # ------------------------------------------------
            # Si no encontramos formatos, intentar con
            # info["url"] como último recurso
            # ------------------------------------------------

            if not audio_formats:

                direct_url = info.get("url")

                if direct_url:

                    print(
                        "Usando URL directa de yt-dlp."
                    )

                    return {

                        "success": True,

                        "title": (
                            info.get("title")
                            or "Audio"
                        ),

                        "download_url": direct_url,

                        "format": (
                            info.get("ext")
                            or format
                        ),

                        "mime_type": (
                            info.get("mime_type")
                        ),

                        "duration": (
                            info.get("duration")
                        )
                    }

                raise Exception(
                    "yt-dlp no encontró ningún "
                    "formato de audio con URL"
                )


            # ------------------------------------------------
            # Elegir el mejor audio
            # ------------------------------------------------

            def audio_score(f):

                abr = f.get("abr") or 0
                tbr = f.get("tbr") or 0
                filesize = f.get("filesize") or 0

                return (
                    abr,
                    tbr,
                    filesize
                )


            best_audio = max(
                audio_formats,
                key=audio_score
            )

            stream_url = best_audio.get(
                "url"
            )

            if not stream_url:

                raise Exception(
                    "El mejor formato no tiene URL"
                )

            print(
                "Audio encontrado correctamente."
            )

            print(
                "Extensión:",
                best_audio.get("ext")
            )

            print(
                "Codec:",
                best_audio.get("acodec")
            )

            print(
                "Bitrate:",
                best_audio.get("abr")
            )

            return {

                "success": True,

                "title": (
                    info.get("title")
                    or "Audio"
                ),

                "download_url": stream_url,

                "format": (
                    best_audio.get("ext")
                    or format
                ),

                "mime_type": (
                    best_audio.get("mime_type")
                ),

                "duration": (
                    info.get("duration")
                )
            }


    except Exception as e:

        print(
            "=" * 60
        )

        print(
            "ERROR COMPLETO DE YT-DLP:"
        )

        print(
            repr(e)
        )

        print(
            "=" * 60
        )

        raise HTTPException(

            status_code=400,

            detail=(
                "No se pudo obtener el audio. "
                f"Error: {str(e)}"
            )
        )


# ============================================================
# EXTRAER ID DE YOUTUBE
# ============================================================

def extract_video_id(url: str):

    try:

        if "youtube.com/watch" in url:

            if "v=" in url:

                video_id = (
                    url.split("v=")[1]
                    .split("&")[0]
                )

                return video_id


        if "youtu.be/" in url:

            video_id = (
                url.split("youtu.be/")[1]
                .split("?")[0]
            )

            return video_id


        if "youtube.com/shorts/" in url:

            video_id = (
                url.split(
                    "youtube.com/shorts/"
                )[1]
                .split("?")[0]
            )

            return video_id


        # Si aparentemente ya es un ID
        if len(url) == 11 and "/" not in url:

            return url


    except Exception as e:

        print(
            "ERROR EXTRAYENDO VIDEO ID:",
            repr(e)
        )


    return None


# ============================================================
# EJECUTAR SERVIDOR
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )
