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

TIMEOUT = httpx.Timeout(15.0, connect=8.0)

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

    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def video_id_from_url(value: str) -> str | None:
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
                position = parts.index(marker)
                if len(parts) > position + 1:
                    return parts[position + 1]

    return None


def playlist_id_from_url(value: str) -> str | None:
    parsed = urlparse(value.strip())
    playlist_id = parse_qs(parsed.query).get("list", [None])[0]

    if playlist_id:
        return playlist_id

    match = re.search(r"(?:playlist|list)/([A-Za-z0-9_-]+)", value)
    return match.group(1) if match else None


def thumbnail(video: dict[str, Any]) -> str:
    thumbnails = video.get("videoThumbnails") or video.get("thumbnails") or []

    if not thumbnails:
        video_id = video.get("videoId") or video.get("id")
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else ""

    preferred = next(
        (
            image
            for image in thumbnails
            if image.get("quality") in {"high", "maxres", "medium"}
        ),
        thumbnails[-1],
    )

    return preferred.get("url", "")


def track_from_video(video: dict[str, Any]) -> dict[str, Any]:
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
        "thumbnail": thumbnail(video),
        "source_url": f"https://www.youtube.com/watch?v={video_id}",
    }


async def invidious_get(path: str, params: dict[str, Any] | None = None) -> Any:
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        response = await client.get(
            f"{INVIDIOUS_BASE_URL}{path}",
            params=params,
            headers={
                "Accept": "application/json",
                "User-Agent": "ING-Downloader/2.0",
            },
        )
        response.raise_for_status()
        return response.json()


def select_stream(
    formats: list[dict[str, Any]],
    requested_format: str,
    requested_quality: str,
) -> dict[str, Any] | None:
    if requested_format == "mp3":
        streams = [
            item
            for item in formats
            if "audio/" in str(item.get("type", "")).lower() and item.get("url")
        ]

        if not streams:
            return None

        target = int(requested_quality) * 1000

        return min(
            streams,
            key=lambda item: abs(int(item.get("bitrate") or 0) - target),
        )

    streams = [
        item
        for item in formats
        if "video/" in str(item.get("type", "")).lower() and item.get("url")
    ]

    if not streams:
        return None

    target = int(requested_quality)

    return min(
        streams,
        key=lambda item: abs(int(item.get("height") or 0) - target),
    )


def extension_from_stream(stream: dict[str, Any], requested_format: str) -> str:
    if requested_format == "mp4":
        return "mp4"

    stream_type = str(stream.get("type", "")).lower()

    if "audio/mpeg" in stream_type:
        return "mp3"
    if "audio/mp4" in stream_type:
        return "m4a"
    if "audio/webm" in stream_type:
        return "webm"

    return "audio"


async def cobalt_download(
    source_url: str,
    requested_format: str,
    requested_quality: str,
) -> dict[str, str] | None:
    payload: dict[str, str] = {
        "url": source_url,
        "downloadMode": "audio" if requested_format == "mp3" else "auto",
    }

    if requested_format == "mp3":
        payload["audioFormat"] = "mp3"
        payload["audioBitrate"] = requested_quality
    else:
        payload["youtubeVideoQuality"] = requested_quality

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            response = await client.post(
                COBALT_API_URL,
                json=payload,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": "ING-Downloader/2.0",
                },
            )
            response.raise_for_status()
            data = response.json()

        if data.get("status") in {"redirect", "tunnel"} and data.get("url"):
            return {
                "media_url": data["url"],
                "extension": "mp3" if requested_format == "mp3" else "mp4",
            }
    except (httpx.HTTPError, ValueError):
        return None

    return None


@app.get("/")
async def home() -> dict[str, str]:
    return {"status": "ok", "message": "ING Downloader API activa"}


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "provider": INVIDIOUS_BASE_URL}


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

        return {
            "results": [
                track_from_video(item)
                for item in data
                if item.get("type") in {None, "video"} and item.get("videoId")
            ][:20]
        }
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail="No fue posible consultar el proveedor de búsqueda.",
        ) from error


@app.get("/api/collection")
async def collection(
    url: str = Query(..., min_length=3, max_length=1000),
) -> dict[str, Any]:
    playlist_id = playlist_id_from_url(url)
    video_id = video_id_from_url(url)

    try:
        if playlist_id:
            data = await invidious_get(f"/api/v1/playlists/{playlist_id}")
            videos = data.get("videos") or []

            return {
                "title": data.get("title") or "Playlist",
                "thumbnail": data.get("playlistThumbnail") or "",
                "tracks": [
                    track_from_video(video)
                    for video in videos
                    if video.get("videoId")
                ],
            }

        if video_id:
            video = await invidious_get(f"/api/v1/videos/{video_id}")

            return {
                "title": video.get("title") or "Resultado",
                "thumbnail": thumbnail(video),
                "tracks": [track_from_video(video)],
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
    filename = clean_filename(f"{artist} - {title}")

    converted = await cobalt_download(source_url, format, quality)

    if converted:
        return {
            "media_url": converted["media_url"],
            "filename": f"{filename}.{converted['extension']}",
            "title": title,
            "artist": artist,
            "thumbnail": thumbnail(video),
            "stream_type": "converted",
        }

    stream = select_stream(
        video.get("adaptiveFormats") or video.get("formatStreams") or [],
        format,
        quality,
    )

    if not stream or not stream.get("url"):
        raise HTTPException(
            status_code=502,
            detail="No hay una transmisión disponible para este contenido.",
        )

    return {
        "media_url": stream["url"],
        "filename": f"{filename}.{extension_from_stream(stream, format)}",
        "title": title,
        "artist": artist,
        "thumbnail": thumbnail(video),
        "stream_type": "direct",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
    )
