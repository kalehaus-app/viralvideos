"""Publisher — uploads a finished bundle to YouTube (or writes a dry-run manifest).

Real mode uses the YouTube Data API v3 (resumable upload + thumbnail set). It
requires OAuth client secrets and the ``google-api-python-client`` stack. The
first run opens an interactive consent flow and caches a refreshable token.

Safety: visibility defaults to ``private`` (see config) so nothing goes public
unless you explicitly opt in. In dry-run / unconfigured mode it writes
``publish_manifest.json`` describing exactly what *would* be uploaded.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..config import Config
from ..models import Metadata
from ..utils import get_logger

log = get_logger("viralagent.publish")

_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class Publisher:
    def __init__(self, config: Config, *, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run

    def publish(
        self, video_path: Optional[str], metadata: Metadata, out_dir: Path
    ) -> Optional[str]:
        backend = self.config.providers.get("publish", "auto")
        can_upload = (
            backend in ("auto", "youtube")
            and not self.dry_run
            and video_path is not None
            and Path(video_path).exists()
            and self._youtube_configured()
        )
        if not can_upload:
            return self._dry_run_manifest(video_path, metadata, out_dir)

        try:
            return self._upload(video_path, metadata)
        except Exception as exc:  # pragma: no cover - network/SDK variance
            log.error("YouTube upload failed (%s); wrote manifest instead.", exc)
            return self._dry_run_manifest(video_path, metadata, out_dir)

    # ------------------------------------------------------------------ #
    def _youtube_configured(self) -> bool:
        secrets = self.config.secrets
        if not Path(secrets.youtube_client_secrets).exists():
            return False
        try:
            import googleapiclient  # noqa: F401
            import google_auth_oauthlib  # noqa: F401
        except ImportError:
            log.info("google-api-python-client not installed; skipping upload.")
            return False
        return True

    def _credentials(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        secrets = self.config.secrets
        token_path = Path(secrets.youtube_token_file)
        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), _SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    secrets.youtube_client_secrets, _SCOPES
                )
                creds = flow.run_local_server(port=0)
            token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    def _upload(self, video_path: str, metadata: Metadata) -> str:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        youtube = build("youtube", "v3", credentials=self._credentials())
        body = {
            "snippet": {
                "title": metadata.title,
                "description": metadata.description,
                "tags": metadata.tags,
                "categoryId": metadata.category_id,
            },
            "status": {
                "privacyStatus": metadata.visibility,
                "selfDeclaredMadeForKids": metadata.made_for_kids,
            },
        }
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(
            part="snippet,status", body=body, media_body=media
        )
        response = None
        while response is None:
            _status, response = request.next_chunk()
        video_id = response["id"]
        log.info("Uploaded to YouTube: https://youtu.be/%s", video_id)

        if metadata.thumbnail_path and Path(metadata.thumbnail_path).exists():
            try:
                youtube.thumbnails().set(
                    videoId=video_id, media_body=MediaFileUpload(metadata.thumbnail_path)
                ).execute()
                log.info("Thumbnail set.")
            except Exception as exc:  # pragma: no cover
                log.warning("Thumbnail upload failed: %s", exc)
        return video_id

    def _dry_run_manifest(
        self, video_path: Optional[str], metadata: Metadata, out_dir: Path
    ) -> None:
        manifest = {
            "would_upload": video_path,
            "title": metadata.title,
            "description": metadata.description,
            "tags": metadata.tags,
            "categoryId": metadata.category_id,
            "privacyStatus": metadata.visibility,
            "madeForKids": metadata.made_for_kids,
            "thumbnail": metadata.thumbnail_path,
        }
        path = out_dir / "publish_manifest.json"
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("Dry-run: wrote %s (visibility=%s).", path.name, metadata.visibility)
        return None
