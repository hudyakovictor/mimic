# Module 21: Video ingest (download, validation, decode)

**Путь:** `services/worker/app/video/`

## Файлы

### `ffmpeg_probe.py`
```python
"""
MG-STUB: реализовать:
- probe_media(object_uri) -> MediaInfo
    - download stream head (10 MB) для ffprobe
    - ffprobe -v error -print_format json -show_format -show_streams
    - вернуть: duration_ms, fps, width, height, has_audio, codec_name, bit_rate
- exceptions: MediaUnreadable, MediaCorrupted, MediaTooLarge, MediaTooLong
"""
```

### `frame_extractor.py`
```python
"""
MG-STUB: реализовать:
- FrameExtractor:
    - open(uri) -> context manager
    - read_all() -> list[np.ndarray] (BGR24)  для ≤30 мин видео
        или генератор (chunked) для длинных
    - использует OpenCV cv2.VideoCapture или decord
- AudioExtractor:
    - ffmpeg → mono PCM 16kHz float32 numpy array
    - return audio: np.ndarray shape (N,), sample_rate=16000
"""
```

### `youtube.py`
```python
"""
MG-STUB: реализовать:
- import subprocess 'yt-dlp' (CLI) — НЕ python lib для скорости и совместимости.
- resolve_youtube_url(url) -> {title, duration, video_id, formats}
- download_youtube(url, output_path, format='bestvideo[ext=mp4]+bestaudio[ext=m4a]/best'):
    - yt-dlp -f <format> -o <path> --no-playlist --max-filesize 1G
- exceptions: YouTubeUnavailable, YouTubeTooLong, YouTubeAgeRestricted, DownloadError
"""
```

### `url_downloader.py`
```python
"""
MG-STUB: реализовать:
- download_direct_url(url, output_path, max_bytes=1GB, timeout=600):
    - httpx.AsyncClient.stream('GET', url, follow_redirects=True, timeout=...)
    - progress в Redis: import_task:{task_id}:bytes_downloaded
    - on success: validate (size, mime magic bytes, ffprobe)
"""
```

### `validation.py`
```python
"""
MG-STUB: реализовать:
- validate_video(mp4_path) -> MediaInfo
    - mime: первые 12 байт соответствуют mp4/mov/webm
    - size: ≤ 1 GB
    - duration: ≤ 30 мин
    - decode: cv2.VideoCapture.open + read 1 frame
    - audio: ffprobe наличие audio stream (warn если нет)
- на любом fail → raise ValidationError с reason
"""
```
