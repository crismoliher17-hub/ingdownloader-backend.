```python
import os
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ING Downloader API", version="2.0.0")

FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "https://ingdownloader.web.app,http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

INVIDIOUS_BASE_URL = os.getenv(
    "INVIDIOUS_BASE_URL",
    "https://inv.nadeko.net",
).rstrip("/")

COBALT_API_URL = os.getenv(
    "COBALT_API_URL",
    "https://api.cobalt.tools/",
).rstrip("/") + "/"

REQUEST_TIMEOUT = httpx.Timeout(15.0, connect=8.0)

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def clean_filename(value: str, fallback: str = "archivo") -> str:
    value = re.sub(r'[\\/:*?"<>|]+', "", value or "")
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value[:150] or fallback


def format_duration(seconds: Any) -> str:
    try:
        total = max(0, int(float(seconds)))
    except (TypeError, ValueError):
        return "0:00"

    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def extract_video_id(value: str) -> str | None:
    value = value.strip()

    if re.fullmatch(r"[\w-]{11}", value):
        return value

    parsed = urlparse(value)
    query = parse_qs(parsed.query)

    if query.get("v"):
        return query["v"][0]

    host = parsed.netloc.lower().replace("www.", "")
    parts = [part for part in parsed.path.split("/") if part]

    if host == "youtu.be" and parts:
        return parts[0]

    if host.endswith("youtube.com"):
        for marker in ("shorts", "embed", "live"):
            if marker in parts:
                index = parts.index(marker)
                if len(parts) > index + 1:
                    return parts[index + 1]

    return None


def extract_playlist_id(value: str) -> str | None:
    parsed = urlparse(value.strip())
    playlist_id = parse_qs(parsed.query).get("list", [None])[0]

    if playlist_id:
        return playlist_id

    match = re.search(r"(?:playlist|list)/([A-Za-z0-9_-]+)", value)
    return match.group(1) if match else None


def thumbnail_from_video(video: dict[str, Any]) -> str:
    thumbnails = video.get("videoThumbnails") or video.get("thumbnails") or []

    if not thumbnails:
        video_id = video.get("videoId") or video.get("id")
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else ""

    preferred = next(
        (
            item
            for item in thumbnails
            if item.get("quality") in {"high", "maxres", "medium"}
        ),
        thumbnails[-1],
    )

    return preferred.get("url", "")


def to_track(video: dict[str, Any]) -> dict[str, Any]:
    video_id = video.get("videoId") or video.get("id") or ""

    return {
        "id": video_id,
        "title": video.get("title") or "Sin título",
        "artist": (
            video.get("author")
            or video.get("uploader")
            or video.get("artist")
            or "Artista desconocido"
        ),
        "duration": format_duration(
            video.get("lengthSeconds")
            or video.get("duration")
            or video.get("durationSeconds")
        ),
        "thumbnail": thumbnail_from_video(video),
        "source_url": f"https://www.youtube.com/watch?v={video_id}",
    }


async def invidious_get(path: str, params: dict[str, Any] | None = None) -> Any:
    headers = {
        "Accept": "application/json",
        "User-Agent": "ING-Downloader/2.0",
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        response = await client.get(
            f"{INVIDIOUS_BASE_URL}{path}",
            params=params,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()


def choose_stream(
    formats: list[dict[str, Any]],
    requested_format: str,
    requested_quality: str,
) -> dict[str, Any] | None:
    if requested_format == "mp3":
        audio_formats = [
            item
            for item in formats
            if "audio/" in str(item.get("type", "")).lower()
            and item.get("url")
        ]

        if not audio_formats:
            return None

        try:
            target_bitrate = int(requested_quality) * 1000
        except ValueError:
            target_bitrate = 320000

        return min(
            audio_formats,
            key=lambda item: abs(int(item.get("bitrate") or 0) - target_bitrate),
        )

    video_formats = [
        item
        for item in formats
        if "video/" in str(item.get("type", "")).lower()
        and item.get("url")
    ]

    if not video_formats:
        return None

    try:
        target_height = int(str(requested_quality).replace("p", ""))
    except ValueError:
        target_height = 720

    return min(
        video_formats,
        key=lambda item: abs(int(item.get("height") or 0) - target_height),
    )


def extension_from_stream(stream: dict[str, Any], requested_format: str) -> str:
    if requested_format == "mp4":
        return "mp4"

    mime_type = str(stream.get("type", "")).lower()

    if "audio/mpeg" in mime_type:
        return "mp3"
    if "audio/mp4" in mime_type:
        return "m4a"
    if "audio/webm" in mime_type:
        return "webm"
    if "opus" in mime_type:
        return "opus"

    container = str(stream.get("container", "")).lower()
    return container if container in {"mp3", "m4a", "webm", "opus"} else "audio"


async def resolve_with_cobalt(
    source_url: str,
    requested_format: str,
    requested_quality: str,
) -> dict[str, Any] | None:
    payload: dict[str, Any] = {
        "url": source_url,
        "downloadMode": "audio" if requested_format == "mp3" else "auto",
        "youtubeVideoQuality": requested_quality if requested_format == "mp4" else "720",
    }

    if requested_format == "mp3":
        payload["audioFormat"] = "mp3"
        payload["audioBitrate"] = requested_quality

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "ING-Downloader/2.0",
    }

    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
        ) as client:
            response = await client.post(
                COBALT_API_URL,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        if data.get("status") in {"redirect", "tunnel"} and data.get("url"):
            return {
                "media_url": data["url"],
                "file_extension": "mp3" if requested_format == "mp3" else "mp4",
            }
    except (httpx.HTTPError, ValueError):
        return None

    return None


@app.get("/")
async def home() -> dict[str, str]:
    return {
        "status": "ok",
        "message": "ING Downloader API activa",
    }


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "provider": INVIDIOUS_BASE_URL,
    }


@app.get("/api/search")
async def search(
    q: str = Query(..., min_length=2, max_length=150),
) -> dict[str, list[dict[str, Any]]]:
    try:
        data = await invidious_get(
            "/api/v1/search",
            {
                "q": q,
                "type": "video",
                "sort_by": "relevance",
                "page": 1,
            },
        )

        results = [
            to_track(item)
            for item in data
            if item.get("type") in {None, "video"} and item.get("videoId")
        ]

        return {"results": results[:20]}

    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail="No fue posible consultar el proveedor de búsqueda.",
        ) from error


@app.get("/api/collection")
async def collection(
    url: str = Query(..., min_length=3, max_length=1000),
) -> dict[str, Any]:
    playlist_id = extract_playlist_id(url)
    video_id = extract_video_id(url)

    try:
        if playlist_id:
            data = await invidious_get(f"/api/v1/playlists/{playlist_id}")
            videos = data.get("videos") or []

            return {
                "title": data.get("title") or "Playlist",
                "thumbnail": data.get("playlistThumbnail") or "",
                "tracks": [to_track(video) for video in videos if video.get("videoId")],
            }

        if video_id:
            video = await invidious_get(f"/api/v1/videos/{video_id}")

            return {
                "title": video.get("title") or "Resultado",
                "thumbnail": thumbnail_from_video(video),
                "tracks": [to_track(video)],
            }

        raise HTTPException(
            status_code=400,
            detail="Ingresa una URL válida de video, álbum o playlist.",
        )

    except HTTPException:
        raise

    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail="No fue posible cargar el contenido solicitado.",
        ) from error


@app.get("/api/resolve")
async def resolve(
    video_id: str = Query(..., min_length=11, max_length=20),
    format: str = Query("mp3", pattern="^(mp3|mp4)$"),
    quality: str = Query("320", pattern="^(128|192|320|480|720|1080)$"),
) -> dict[str, Any]:
    source_url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        video = await invidious_get(f"/api/v1/videos/{video_id}")
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail="No fue posible obtener los datos del medio.",
        ) from error

    artist = video.get("author") or "Artista desconocido"
    title = video.get("title") or "Sin título"
    filename_base = clean_filename(f"{artist} - {title}")

    cobalt_result = await resolve_with_cobalt(source_url, format, quality)

    if cobalt_result:
        return {
            "media_url": cobalt_result["media_url"],
            "filename": f"{filename_base}.{cobalt_result['file_extension']}",
            "title": title,
            "artist": artist,
            "thumbnail": thumbnail_from_video(video),
            "stream_type": "converted",
        }

    stream = choose_stream(
        video.get("adaptiveFormats") or video.get("formatStreams") or [],
        format,
        quality,
    )

    if not stream or not stream.get("url"):
        raise HTTPException(
            status_code=502,
            detail="No hay una transmisión disponible para este contenido.",
        )

    extension = extension_from_stream(stream, format)

    return {
        "media_url": stream["url"],
        "filename": f"{filename_base}.{extension}",
        "title": title,
        "artist": artist,
        "thumbnail": thumbnail_from_video(video),
        "stream_type": "direct",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
    )
}
```