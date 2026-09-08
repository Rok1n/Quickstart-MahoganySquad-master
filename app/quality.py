from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Variant:
    label: str
    width: int
    height: int
    bitrate: int
    data_size: int
    codec: str
    gear_name: str
    url: str
    source: str

    def public(self) -> dict[str, Any]:
        return asdict(self)


def _first_url(play_addr: dict[str, Any] | None) -> str:
    if not play_addr:
        return ""
    urls = play_addr.get("url_list") or []
    return next((u for u in urls if isinstance(u, str) and u.startswith("http")), "")


def _codec(item: dict[str, Any], url: str) -> str:
    value = " ".join(
        str(item.get(k, "")) for k in ("format", "codec_type", "gear_name", "quality_type")
    ).lower()
    if "265" in value or "hevc" in value or "hvc" in value or "bytevc1" in value:
        return "h265"
    if "264" in value or "avc" in value:
        return "h264"
    if "h265" in url.lower() or "hevc" in url.lower():
        return "h265"
    return "unknown"


def _dimensions(item: dict[str, Any], video: dict[str, Any]) -> tuple[int, int]:
    play = item.get("play_addr") or {}
    width = int(play.get("width") or item.get("width") or 0)
    height = int(play.get("height") or item.get("height") or 0)
    gear = str(item.get("gear_name") or "")
    if not height:
        m = re.search(r"(?:^|[^0-9])(2160|1440|1080|720|540|480|360)p?(?:[^0-9]|$)", gear)
        if m:
            height = int(m.group(1))
    if not width and height:
        vw, vh = int(video.get("width") or 0), int(video.get("height") or 0)
        if vw and vh:
            width = round(height * vw / vh)
    if not width:
        width = int(video.get("width") or 0)
    if not height:
        height = int(video.get("height") or 0)
    return width, height


def _label(width: int, height: int, gear: str) -> str:
    long_edge, short_edge = max(width, height), min(width, height)
    if long_edge >= 3800 or short_edge >= 2100:
        return "2160p"
    if long_edge >= 2500 or short_edge >= 1400:
        return "1440p"
    if long_edge >= 1900 or short_edge >= 1050:
        return "1080p"
    if long_edge >= 1250 or short_edge >= 700:
        return "720p"
    m = re.search(r"(2160|1440|1080|720|540|480|360)p", gear.lower())
    return f"{m.group(1)}p" if m else (f"{height}p" if height else "unknown")


def extract_variants(aweme_detail: dict[str, Any]) -> list[Variant]:
    video = aweme_detail.get("video") or {}
    variants: list[Variant] = []
    seen: set[str] = set()

    for item in video.get("bit_rate") or []:
        play = item.get("play_addr") or {}
        url = _first_url(play)
        if not url or url in seen:
            continue
        seen.add(url)
        width, height = _dimensions(item, video)
        bitrate = int(item.get("bit_rate") or item.get("bitrate") or 0)
        data_size = int(play.get("data_size") or item.get("data_size") or 0)
        gear = str(item.get("gear_name") or "")
        variants.append(
            Variant(
                label=_label(width, height, gear),
                width=width,
                height=height,
                bitrate=bitrate,
                data_size=data_size,
                codec=_codec(item, url),
                gear_name=gear,
                url=url.replace("playwm", "play"),
                source="bit_rate",
            )
        )

    play_addr = video.get("play_addr") or {}
    fallback = _first_url(play_addr)
    if fallback and fallback not in seen:
        width = int(play_addr.get("width") or video.get("width") or 0)
        height = int(play_addr.get("height") or video.get("height") or 0)
        variants.append(
            Variant(
                label=_label(width, height, "play_addr"),
                width=width,
                height=height,
                bitrate=0,
                data_size=int(play_addr.get("data_size") or 0),
                codec="unknown",
                gear_name="play_addr",
                url=fallback.replace("playwm", "play"),
                source="play_addr",
            )
        )

    variants.sort(
        key=lambda v: (v.width * v.height, v.bitrate, v.data_size),
        reverse=True,
    )
    return variants


def select_variant(variants: list[Variant], quality: str = "best", codec: str = "auto") -> Variant:
    if not variants:
        raise ValueError("No downloadable video variants were returned by Douyin")

    candidates = variants
    codec = codec.lower()
    if codec in {"h264", "h265"}:
        exact = [v for v in candidates if v.codec == codec]
        if exact:
            candidates = exact

    quality = quality.lower()
    if quality != "best":
        wanted = re.sub(r"[^0-9]", "", quality)
        if wanted:
            exact = [v for v in candidates if re.sub(r"[^0-9]", "", v.label) == wanted]
            if exact:
                candidates = exact
            else:
                target = int(wanted)
                candidates = sorted(
                    candidates,
                    key=lambda v: abs((int(re.sub(r"[^0-9]", "", v.label) or "0")) - target),
                )
                return candidates[0]

    return max(candidates, key=lambda v: (v.width * v.height, v.bitrate, v.data_size))
