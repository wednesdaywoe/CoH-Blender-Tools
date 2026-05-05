"""CoH Workshop HTTP server.

Designed to run on Blender's bundled Python via:
    blender --background --python workshop/server.py

The server stays alive until the launching shell window is closed.
It does not use bpy directly; when geometry round-trip work is needed,
it spawns a fresh `blender --background --python ...` subprocess so the
server's request handling stays clean.

Routes (all JSON unless noted):
    GET  /                         → static/index.html
    GET  /api/config               → current configuration / readiness
    POST /api/config               → set CoH install path
    GET  /api/piggs/search?q=…     → search file paths across all piggs
    POST /api/extract              → extract one file to the work dir
    GET  /api/work                 → list files in the work dir
    POST /api/stage                → round-trip (or stage as-is) and pack as patch pigg
    GET  /api/overrides            → list workshop-created overrides in the patch dir
    POST /api/overrides/remove     → delete a workshop override
    POST /api/shutdown             → stop the server
"""

from __future__ import annotations

import json
import mimetypes
import sys
import threading
import time
import webbrowser
import shutil
import subprocess
import traceback
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ─── Paths ──────────────────────────────────────────────────────────────────

WORKSHOP_DIR = Path(__file__).resolve().parent
BUNDLE_DIR = WORKSHOP_DIR.parent               # the CoH Blender Tools bundle root
STATIC_DIR = WORKSHOP_DIR / "static"
WORK_DIR = WORKSHOP_DIR / "work"
CONFIG_PATH = WORKSHOP_DIR / "config.json"

# Vendored pigg reader (pure stdlib) ships in <bundle>/lib/.
sys.path.insert(0, str(BUNDLE_DIR / "lib"))
from pigg_wrangler.pigg import PiggCollection  # noqa: E402

# Patch-pigg writer ships next to this file.
sys.path.insert(0, str(WORKSHOP_DIR))
from make_patch_pigg import build_pigg  # noqa: E402

# ─── Constants ──────────────────────────────────────────────────────────────

PORT = 8765
PATCH_PIGG_PREFIX = "coh_workshop_"      # workshop-owned overrides
SEARCH_LIMIT = 200


def find_blender_exe() -> Path:
    """Locate blender.exe.

    When this server runs under `blender --background --python …`,
    `sys.executable` is the bundled python.exe (typically at
    <install>/<version>/python/bin/python.exe), not blender.exe itself.
    Walk up the path looking for the sibling blender.exe.
    """
    py = Path(sys.executable).resolve()
    for ancestor in [py.parent, *py.parents]:
        candidate = ancestor / "blender.exe"
        if candidate.exists():
            return candidate
    # Fallbacks if we're not running under Blender (e.g. dev mode under py.exe).
    for guess in [
        Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"),
        Path(r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"),
        Path(r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe"),
        Path(r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe"),
    ]:
        if guess.exists():
            return guess
    raise RuntimeError(f"Could not locate blender.exe (started from {py})")


_blender_exe: Path | None = None


def blender_exe() -> Path:
    global _blender_exe
    if _blender_exe is None:
        _blender_exe = find_blender_exe()
    return _blender_exe

# ─── Config persistence ─────────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text("utf-8"))
        except Exception:
            return {}
    return {}


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), "utf-8")


def detect_install(install_root: Path) -> dict:
    """Validate a CoH install path and detect the patch directory.

    Returns a dict with `valid`, `client_dir`, `piggs_dir`, `patch_dir`,
    `pigg_count`, and (if invalid) `reason`.
    """
    if not install_root.is_dir():
        return {"valid": False, "reason": f"Not a directory: {install_root}"}

    # Try common layouts.  Some installs put everything under Client/, others
    # use the install root itself.
    candidates = [install_root / "Client", install_root]
    client_dir = None
    for c in candidates:
        if (c / "piggs").is_dir() and any((c / "piggs").glob("*.pigg")):
            client_dir = c
            break
    if client_dir is None:
        return {
            "valid": False,
            "reason": f"No Client/piggs/*.pigg under {install_root}",
        }

    piggs_dir = client_dir / "piggs"

    # Patch dir = any sibling of `piggs` that contains *.pigg files.
    # For Ouroboros that's `ouro/`.  Other installs may use a different name.
    patch_dir = None
    for sibling in client_dir.iterdir():
        if sibling.is_dir() and sibling.name.lower() != "piggs":
            if any(sibling.glob("*.pigg")):
                patch_dir = sibling
                break
    if patch_dir is None:
        # Default to a `patches` dir we'll create later if missing.
        patch_dir = client_dir / "patches"

    pigg_count = sum(1 for _ in piggs_dir.glob("*.pigg"))

    return {
        "valid": True,
        "install_root": str(install_root),
        "client_dir": str(client_dir),
        "piggs_dir": str(piggs_dir),
        "patch_dir": str(patch_dir),
        "pigg_count": pigg_count,
    }


# ─── Pigg collection caching ────────────────────────────────────────────────

_pigg_cache: dict[str, PiggCollection] = {}


def get_collection(dir_path: Path) -> PiggCollection:
    key = str(dir_path)
    if key not in _pigg_cache:
        _pigg_cache[key] = PiggCollection(dir_path)
    return _pigg_cache[key]


def invalidate_pigg_cache() -> None:
    _pigg_cache.clear()


# ─── Workshop operations ────────────────────────────────────────────────────

def search_piggs(needle: str, limit: int = SEARCH_LIMIT) -> list[dict]:
    """Search the configured piggs for paths containing `needle`."""
    cfg = load_config()
    detect = detect_install(Path(cfg.get("install_root", "")))
    if not detect["valid"]:
        return []
    needle_lower = needle.lower()
    results = []
    for dir_path in [Path(detect["piggs_dir"]), Path(detect["patch_dir"])]:
        if not dir_path.is_dir():
            continue
        coll = get_collection(dir_path)
        for archive in coll.readers:
            for path in archive.list_paths():
                if needle_lower in path.lower():
                    results.append({
                        "pigg": Path(archive.pigg_path).name,
                        "internal_path": path,
                        "size": archive.get(path).uncompressed_size,
                    })
                    if len(results) >= limit:
                        return results
    return results


def extract_file(pigg_name: str, internal_path: str) -> dict:
    """Extract a file from a named pigg into WORK_DIR. Writes a sidecar
    .meta.json so we can reconstruct the override path later."""
    cfg = load_config()
    detect = detect_install(Path(cfg.get("install_root", "")))
    if not detect["valid"]:
        raise RuntimeError("CoH install not configured")

    archive = None
    for dir_path in [Path(detect["piggs_dir"]), Path(detect["patch_dir"])]:
        if not dir_path.is_dir():
            continue
        coll = get_collection(dir_path)
        for arc in coll.readers:
            if Path(arc.pigg_path).name == pigg_name and arc.has(internal_path):
                archive = arc
                break
        if archive:
            break
    if archive is None:
        raise RuntimeError(f"Not found: {pigg_name}:{internal_path}")

    data = archive.extract(internal_path)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    basename = internal_path.rsplit("/", 1)[-1]
    out_path = WORK_DIR / basename
    out_path.write_bytes(data)
    meta = {
        "internal_path": internal_path,
        "source_pigg": pigg_name,
        "extracted_at": int(time.time()),
        "size": len(data),
    }
    (WORK_DIR / f"{basename}.meta.json").write_text(json.dumps(meta, indent=2))
    return {"work_file": basename, "size": len(data), "internal_path": internal_path}


def list_work_files() -> list[dict]:
    if not WORK_DIR.is_dir():
        return []
    out = []
    for p in sorted(WORK_DIR.iterdir()):
        if p.suffix == ".json" or p.is_dir():
            continue
        meta_path = WORK_DIR / f"{p.name}.meta.json"
        meta = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
            except Exception:
                meta = {}
        stat = p.stat()
        out.append({
            "name": p.name,
            "size": stat.st_size,
            "mtime": int(stat.st_mtime),
            "internal_path": meta.get("internal_path", ""),
            "source_pigg": meta.get("source_pigg", ""),
        })
    return out


def stage_override(work_file: str, internal_path: str, roundtrip: bool) -> dict:
    """Optionally round-trip the .geo through Blender, then pack into a
    workshop-tagged patch pigg and drop it in the patch dir."""
    cfg = load_config()
    detect = detect_install(Path(cfg.get("install_root", "")))
    if not detect["valid"]:
        raise RuntimeError("CoH install not configured")

    src = WORK_DIR / work_file
    if not src.exists():
        raise RuntimeError(f"Not in work dir: {work_file}")

    payload_path = src
    if roundtrip:
        rt_out = WORK_DIR / f"_roundtripped_{src.name}"
        rt_script = WORKSHOP_DIR / "roundtrip_geo.py"
        cmd = [str(blender_exe()), "--background", "--python", str(rt_script),
               "--", str(src), str(rt_out)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 or not rt_out.exists():
            raise RuntimeError(
                f"Round-trip failed (exit {result.returncode}):\n"
                f"STDOUT:\n{result.stdout[-2000:]}\n"
                f"STDERR:\n{result.stderr[-2000:]}"
            )
        payload_path = rt_out

    patch_dir = Path(detect["patch_dir"])
    patch_dir.mkdir(parents=True, exist_ok=True)
    pigg_name = f"{PATCH_PIGG_PREFIX}{src.stem}.pigg"
    pigg_path = patch_dir / pigg_name

    pigg_bytes = build_pigg([(internal_path, payload_path.read_bytes())])
    pigg_path.write_bytes(pigg_bytes)

    invalidate_pigg_cache()
    return {
        "pigg_path": str(pigg_path),
        "pigg_name": pigg_name,
        "size": pigg_path.stat().st_size,
        "roundtripped": roundtrip,
    }


def list_overrides() -> list[dict]:
    cfg = load_config()
    detect = detect_install(Path(cfg.get("install_root", "")))
    if not detect["valid"]:
        return []
    patch_dir = Path(detect["patch_dir"])
    if not patch_dir.is_dir():
        return []
    out = []
    for p in sorted(patch_dir.glob(f"{PATCH_PIGG_PREFIX}*.pigg")):
        # Peek inside to get the internal path
        try:
            from pigg_wrangler.pigg import PiggArchive
            arc = PiggArchive(str(p))
            internal_paths = arc.list_paths()
        except Exception:
            internal_paths = []
        st = p.stat()
        out.append({
            "name": p.name,
            "size": st.st_size,
            "mtime": int(st.st_mtime),
            "internal_paths": internal_paths,
        })
    return out


def remove_override(pigg_filename: str) -> dict:
    if not pigg_filename.startswith(PATCH_PIGG_PREFIX):
        raise RuntimeError("Refusing to remove file not owned by workshop")
    cfg = load_config()
    detect = detect_install(Path(cfg.get("install_root", "")))
    if not detect["valid"]:
        raise RuntimeError("CoH install not configured")
    target = Path(detect["patch_dir"]) / pigg_filename
    if not target.exists():
        raise RuntimeError(f"Not found: {pigg_filename}")
    target.unlink()
    invalidate_pigg_cache()
    return {"removed": pigg_filename}


# ─── HTTP handler ───────────────────────────────────────────────────────────

class WorkshopHandler(BaseHTTPRequestHandler):
    server_version = "CoHWorkshop/1.0"

    def log_message(self, fmt, *args):  # noqa: N802 - signature is fixed
        # Quieter than the default
        sys.stderr.write(f"[{self.log_date_time_string()}] {fmt % args}\n")

    # ─── Utility ─────────────────────────────────────────────────────────────

    def _send_json(self, obj, status: int = 200) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _send_static(self, rel: str) -> None:
        path = (STATIC_DIR / rel).resolve()
        if not str(path).startswith(str(STATIC_DIR.resolve())):
            self.send_error(403)
            return
        if not path.exists():
            self.send_error(404)
            return
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # ─── Routes ──────────────────────────────────────────────────────────────

    def do_GET(self):  # noqa: N802
        url = urllib.parse.urlparse(self.path)
        path = url.path

        if path == "/" or path == "/index.html":
            return self._send_static("index.html")

        if path.startswith("/static/"):
            return self._send_static(path[len("/static/"):])

        if path == "/api/config":
            cfg = load_config()
            install = cfg.get("install_root", "")
            detect = detect_install(Path(install)) if install else {"valid": False}
            return self._send_json({
                "config": cfg,
                "detect": detect,
                "ready": detect.get("valid", False),
            })

        if path == "/api/piggs/search":
            qs = urllib.parse.parse_qs(url.query)
            needle = (qs.get("q", [""])[0]).strip()
            if not needle:
                return self._send_json({"results": []})
            try:
                results = search_piggs(needle)
                return self._send_json({"results": results})
            except Exception as e:
                return self._send_json({"error": str(e)}, status=500)

        if path == "/api/work":
            try:
                return self._send_json({"files": list_work_files()})
            except Exception as e:
                return self._send_json({"error": str(e)}, status=500)

        if path == "/api/overrides":
            try:
                return self._send_json({"overrides": list_overrides()})
            except Exception as e:
                return self._send_json({"error": str(e)}, status=500)

        self.send_error(404)

    def do_POST(self):  # noqa: N802
        url = urllib.parse.urlparse(self.path)
        path = url.path
        body = self._read_json()

        try:
            if path == "/api/config":
                install = (body.get("install_root") or "").strip()
                detect = detect_install(Path(install))
                if not detect["valid"]:
                    return self._send_json({"error": detect["reason"]}, status=400)
                cfg = load_config()
                cfg["install_root"] = install
                save_config(cfg)
                invalidate_pigg_cache()
                return self._send_json({"config": cfg, "detect": detect, "ready": True})

            if path == "/api/extract":
                pigg = body.get("pigg")
                internal_path = body.get("internal_path")
                if not pigg or not internal_path:
                    return self._send_json({"error": "pigg and internal_path required"}, status=400)
                return self._send_json(extract_file(pigg, internal_path))

            if path == "/api/stage":
                wf = body.get("work_file")
                ip = body.get("internal_path")
                roundtrip = bool(body.get("roundtrip", True))
                if not wf or not ip:
                    return self._send_json({"error": "work_file and internal_path required"}, status=400)
                return self._send_json(stage_override(wf, ip, roundtrip))

            if path == "/api/overrides/remove":
                name = body.get("pigg_filename")
                if not name:
                    return self._send_json({"error": "pigg_filename required"}, status=400)
                return self._send_json(remove_override(name))

            if path == "/api/shutdown":
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return self._send_json({"shutting_down": True})

        except Exception as e:
            tb = traceback.format_exc()
            sys.stderr.write(tb)
            return self._send_json({"error": str(e), "traceback": tb}, status=500)

        self.send_error(404)


# ─── Entry point ────────────────────────────────────────────────────────────

def main():
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), WorkshopHandler)
    url = f"http://127.0.0.1:{PORT}/"
    print(f"\nCoH Workshop running on {url}")
    print("Close this window to stop the workshop.\n")

    def open_browser():
        time.sleep(0.4)  # give the server a moment to bind
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=open_browser, daemon=True).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    httpd.server_close()


if __name__ == "__main__":
    main()
