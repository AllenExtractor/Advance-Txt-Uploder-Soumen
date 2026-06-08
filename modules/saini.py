import os
import re
import time
import mmap
import datetime
import aiohttp
import aiofiles
import asyncio
import logging
import requests
import tgcrypto
import subprocess
import concurrent.futures
from math import ceil, cos, sin, radians
from utils import progress_bar
from pyrogram import Client, filters
from pyrogram.types import Message
from io import BytesIO
from pathlib import Path  
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode

# ── Speed Boost: 20-25x faster downloads ─────────────────────────────────────
try:
    from speed_boost import turbo_download_video as _turbo_dl, extract_thumb_fast
    _TURBO_AVAILABLE = True
except ImportError:
    _TURBO_AVAILABLE = False
# ─────────────────────────────────────────────────────────────────────────────

def duration(filename):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        output = result.stdout.decode("utf-8", errors="ignore").strip()
        if not output:
            # fallback: try stderr too
            output = result.stderr.decode("utf-8", errors="ignore").strip()
        return float(output) if output else 0.0
    except Exception:
        return 0.0
 
def exec(cmd):
        process = subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        output = process.stdout.decode()
        print(output)
        return output
        #err = process.stdout.decode()

def pull_run(work, cmds):
    with concurrent.futures.ThreadPoolExecutor(max_workers=work) as executor:
        print("Waiting for tasks to complete")
        fut = executor.map(exec,cmds)
        
async def aio(url,name):
    k = f'{name}.pdf'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(k, mode='wb')
                await f.write(await resp.read())
                await f.close()
    return k


async def download(url,name):
    ka = f'{name}.pdf'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(ka, mode='wb')
                await f.write(await resp.read())
                await f.close()
    return ka


def parse_vid_info(info):
    info = info.strip()
    info = info.split("\n")
    new_info = []
    temp = []
    for i in info:
        i = str(i)
        if "[" not in i and '---' not in i:
            while "  " in i:
                i = i.replace("  ", " ")
            i.strip()
            i = i.split("|")[0].split(" ",2)
            try:
                if "RESOLUTION" not in i[2] and i[2] not in temp and "audio" not in i[2]:
                    temp.append(i[2])
                    new_info.append((i[0], i[2]))
            except:
                pass
    return new_info

def vid_info(info):
    info = info.strip()
    info = info.split("\n")
    new_info = dict()
    temp = []
    for i in info:
        i = str(i)
        if "[" not in i and '---' not in i:
            while "  " in i:
                i = i.replace("  ", " ")
            i.strip()
            i = i.split("|")[0].split(" ",3)
            try:
                if "RESOLUTION" not in i[2] and i[2] not in temp and "audio" not in i[2]:
                    temp.append(i[2])
                    
                    # temp.update(f'{i[2]}')
                    # new_info.append((i[2], i[0]))
                    #  mp4,mkv etc ==== f"({i[1]})" 
                    
                    new_info.update({f'{i[2]}':f'{i[0]}'})

            except:
                pass
    return new_info


async def decrypt_and_merge_video(mpd_url, keys_string, output_path, output_name, quality="720"):
    try:
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        cmd1 = f'yt-dlp -f "bv[height<={quality}]+ba/b" -o "{output_path}/file.%(ext)s" --allow-unplayable-format --no-check-certificate --external-downloader aria2c "{mpd_url}"'
        print(f"Running command: {cmd1}")
        os.system(cmd1)
        
        avDir = list(output_path.iterdir())
        print(f"Downloaded files: {avDir}")
        print("Decrypting")

        video_decrypted = False
        audio_decrypted = False

        for data in avDir:
            if data.suffix == ".mp4" and not video_decrypted:
                cmd2 = f'mp4decrypt {keys_string} --show-progress "{data}" "{output_path}/video.mp4"'
                print(f"Running command: {cmd2}")
                os.system(cmd2)
                if (output_path / "video.mp4").exists():
                    video_decrypted = True
                data.unlink()
            elif data.suffix == ".m4a" and not audio_decrypted:
                cmd3 = f'mp4decrypt {keys_string} --show-progress "{data}" "{output_path}/audio.m4a"'
                print(f"Running command: {cmd3}")
                os.system(cmd3)
                if (output_path / "audio.m4a").exists():
                    audio_decrypted = True
                data.unlink()

        if not video_decrypted or not audio_decrypted:
            raise FileNotFoundError("Decryption failed: video or audio file not found.")

        cmd4 = f'ffmpeg -i "{output_path}/video.mp4" -i "{output_path}/audio.m4a" -c copy "{output_path}/{output_name}.mp4"'
        print(f"Running command: {cmd4}")
        os.system(cmd4)
        if (output_path / "video.mp4").exists():
            (output_path / "video.mp4").unlink()
        if (output_path / "audio.m4a").exists():
            (output_path / "audio.m4a").unlink()
        
        filename = output_path / f"{output_name}.mp4"

        if not filename.exists():
            raise FileNotFoundError("Merged video file not found.")

        cmd5 = f'ffmpeg -i "{filename}" 2>&1 | grep "Duration"'
        duration_info = os.popen(cmd5).read()
        print(f"Duration info: {duration_info}")

        return str(filename)

    except Exception as e:
        print(f"Error during decryption and merging: {str(e)}")
        raise

async def run(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    print(f'[{cmd!r} exited with {proc.returncode}]')
    if proc.returncode == 1:
        return False
    if stdout:
        return f'[stdout]\n{stdout.decode()}'
    if stderr:
        return f'[stderr]\n{stderr.decode()}'

    

def old_download(url, file_name, chunk_size = 1024 * 10):
    if os.path.exists(file_name):
        os.remove(file_name)
    r = requests.get(url, allow_redirects=True, stream=True)
    with open(file_name, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                fd.write(chunk)
    return file_name


def human_readable_size(size, decimal_places=2):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if size < 1024.0 or unit == 'PB':
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"


def time_name():
    date = datetime.date.today()
    now = datetime.datetime.now()
    current_time = now.strftime("%H%M%S")
    return f"{date} {current_time}.mp4"


async def download_video(url, cmd, name):
    """
    Turbo-enhanced download_video.
    Uses speed_boost.turbo_download_video (20-25x faster) when available,
    falls back to original aria2c logic if turbo is not available.
    """
    # ── Turbo path (speed_boost.py present) ──────────────────────────────────
    if _TURBO_AVAILABLE:
        try:
            result = await _turbo_dl(url, cmd, name, timeout=3600)
            if result and os.path.isfile(result):
                print(f"[TURBO] Download complete: {result}")
                return result
        except Exception as e:
            print(f"[TURBO] Error, falling back to original: {e}")

    # ── Original path (fallback) ──────────────────────────────────────────────
    download_cmd = f'{cmd} -R 25 --fragment-retries 25 --external-downloader aria2c --downloader-args "aria2c: -x 16 -j 32"'
    global failed_counter
    print(download_cmd)
    logging.info(download_cmd)
    try:
        k = subprocess.run(download_cmd, shell=True, timeout=3600)
    except subprocess.TimeoutExpired:
        print(f"Download timed out for: {name}")
        return name
    if "visionias" in cmd and k.returncode != 0 and failed_counter <= 10:
        failed_counter += 1
        await asyncio.sleep(5)
        await download_video(url, cmd, name)
    failed_counter = 0
    try:
        if os.path.isfile(name):
            return name
        elif os.path.isfile(f"{name}.webm"):
            return f"{name}.webm"
        name = name.split(".")[0]
        if os.path.isfile(f"{name}.mkv"):
            return f"{name}.mkv"
        elif os.path.isfile(f"{name}.mp4"):
            return f"{name}.mp4"
        elif os.path.isfile(f"{name}.mp4.webm"):
            return f"{name}.mp4.webm"
        return name
    except FileNotFoundError as exc:
        return os.path.splitext(name)[0] + ".mp4"


def _pdf_page_is_image_based(page) -> bool:
    """
    Detect if a PDF page is image-based (screenshot/slide/PPT PDFs).
    Returns True if:
      - A single full-page image covers >40% of page area, OR
      - Multiple images combined cover >60% of page area, OR
      - Page has NO extractable text (pure image / scanned / slide)
    These pages need reverse-merge so watermark appears ON TOP.
    """
    try:
        pw = float(page.mediabox.width)
        ph = float(page.mediabox.height)
        page_area = pw * ph

        resources = page.get("/Resources", {})
        if hasattr(resources, "get_object"):
            resources = resources.get_object()
        xobjs = resources.get("/XObject", {})
        if hasattr(xobjs, "get_object"):
            xobjs = xobjs.get_object()

        total_img_area = 0
        for key in xobjs:
            obj = xobjs[key]
            if hasattr(obj, "get_object"):
                obj = obj.get_object()
            if obj.get("/Subtype") == "/Image":
                w = int(obj.get("/Width", 0))
                h = int(obj.get("/Height", 0))
                img_area = w * h
                # Single large image covering >40% → definitely image-based
                if img_area > page_area * 0.40:
                    return True
                total_img_area += img_area

        # Multiple images combined covering >60% → slide/PPT style
        if total_img_area > page_area * 0.60:
            return True

        # No images found via XObject check — try text extraction
        # PPT-exported PDFs often have vector graphics but no text
        try:
            extracted = page.extract_text() or ""
            # If page has very little text (< 20 chars) it's likely a visual/slide page
            if len(extracted.strip()) < 20:
                # Only treat as image-based if there ARE some XObjects (graphics/images)
                if len(list(xobjs.keys())) > 0:
                    return True
        except Exception:
            pass

    except Exception:
        pass
    return False


def _build_wm_stream_and_resources(page_width, page_height, wm_configs, is_img):
    """
    Build a raw PDF content stream for watermark injection.

    FORENSIC FIX: Direct content stream injection instead of merge_page().
    Root cause of previous invisibility:
      - merge_page() cannot guarantee render order on image/hybrid pages.
      - Original white-background image XObject painted OVER the watermark.
      - Color was incorrectly set to '1 1 1 rg' (white) in earlier generated PDFs.

    This function returns raw PDF operator bytes that are APPENDED to the
    page's /Contents array, so the watermark is ALWAYS rendered LAST (on top).
    Color is explicitly set to red-pink (0.85 0.1 0.2) for image pages and
    black for text pages — never white.
    """
    lines = []
    font_map = {}   # /WMFn → /Helvetica-Bold
    gs_map   = {}   # /WMGn → opacity float

    lines.append(b"q")  # save outer graphics state

    for i, cfg in enumerate(wm_configs):
        title    = cfg["title"]
        x_frac   = cfg.get("x_frac", 0.80)
        y_frac   = cfg.get("y_frac", 0.85)
        opacity  = cfg.get("opacity", 0.30)
        rotation = cfg.get("rotation", 0.0)

        font_size = max(8, int(page_width / 28))
        if is_img:
            font_size = max(10, int(page_width / 20))

        x_pos = page_width  * x_frac
        y_pos = page_height * y_frac

        # Image pages: red-pink (visible on both dark and light slide backgrounds)
        # Text pages: black with configured opacity
        if is_img:
            r, g, b = 0.85, 0.1, 0.2
            final_opacity = min(1.0, opacity + 0.45)
        else:
            r, g, b = 0.0, 0.0, 0.0
            final_opacity = opacity

        fn = f"/WMF{i}"   # unique font resource name for this watermark
        gn = f"/WMG{i}"   # unique ExtGState resource name for this watermark
        font_map[fn] = "/Helvetica-Bold"
        gs_map[gn]   = final_opacity

        lines.append(b"q")  # save state per watermark item

        # Set fill color (explicit RGB — never white)
        lines.append(f"{r:.4f} {g:.4f} {b:.4f} rg".encode())
        # Set opacity via ExtGState
        lines.append(f"{gn} gs".encode())

        # Translate + rotate via transformation matrix
        rot_rad = radians(rotation)
        cos_r   = cos(rot_rad)
        sin_r   = sin(rot_rad)
        lines.append(
            f"{cos_r:.6f} {sin_r:.6f} {-sin_r:.6f} {cos_r:.6f} "
            f"{x_pos:.4f} {y_pos:.4f} cm".encode()
        )

        # Text block
        lines.append(b"BT")
        lines.append(f"{fn} {font_size} Tf".encode())
        lines.append(b"0 0 Td")

        # Safely encode title as PDF string
        try:
            txt = title.encode("latin-1")
            txt = txt.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
            lines.append(b"(" + txt + b") Tj")
        except (UnicodeEncodeError, UnicodeDecodeError):
            safe = "".join(c if ord(c) < 128 else "?" for c in title)
            lines.append(f"({safe}) Tj".encode())

        lines.append(b"ET")
        lines.append(b"Q")  # restore per-item state

    lines.append(b"Q")  # restore outer state
    return b"\n".join(lines) + b"\n", font_map, gs_map


def _inject_watermark_stream_into_page(page, stream_bytes, font_map, gs_map, writer):
    """
    Append a pre-built content stream to a PDF page's /Contents array.
    Also registers Font and ExtGState resources on the page.

    This guarantees the watermark is rendered AFTER all existing page content
    (text, images, XObjects) — i.e., always visually on top.
    """
    from pypdf.generic import (
        DecodedStreamObject, ArrayObject, IndirectObject, NameObject,
        DictionaryObject, FloatObject,
    )

    # 1. Build watermark stream object and get its indirect reference
    wm_stream = DecodedStreamObject()
    wm_stream.set_data(stream_bytes)
    wm_ref = writer._add_object(wm_stream)

    # 2. Ensure /Contents is an ArrayObject and append wm_ref at the END
    if "/Contents" in page:
        raw = page.raw_get("/Contents")
        if isinstance(raw, IndirectObject):
            # Single stream → wrap in array, then append
            page[NameObject("/Contents")] = ArrayObject([raw, wm_ref])
        elif isinstance(raw, ArrayObject):
            raw.append(wm_ref)
        else:
            page[NameObject("/Contents")] = ArrayObject([raw, wm_ref])
    else:
        page[NameObject("/Contents")] = ArrayObject([wm_ref])

    # 3. Ensure /Resources dict exists on page
    if "/Resources" not in page:
        page[NameObject("/Resources")] = DictionaryObject()
    resources = page["/Resources"]
    if hasattr(resources, "get_object"):
        resources = resources.get_object()

    # 4. Register Font resources (/WMFn → Helvetica-Bold Type1)
    if "/Font" not in resources:
        resources[NameObject("/Font")] = DictionaryObject()
    font_dict = resources["/Font"]
    if hasattr(font_dict, "get_object"):
        font_dict = font_dict.get_object()

    for fn, font_base_name in font_map.items():
        if fn not in font_dict:
            font_obj = DictionaryObject({
                NameObject("/Type"):     NameObject("/Font"),
                NameObject("/Subtype"):  NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject(font_base_name),
                NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
            })
            font_dict[NameObject(fn)] = writer._add_object(font_obj)

    # 5. Register ExtGState resources (/WMGn → fill + stroke opacity)
    if "/ExtGState" not in resources:
        resources[NameObject("/ExtGState")] = DictionaryObject()
    gs_dict = resources["/ExtGState"]
    if hasattr(gs_dict, "get_object"):
        gs_dict = gs_dict.get_object()

    for gn, opacity in gs_map.items():
        if gn not in gs_dict:
            gs_obj = DictionaryObject({
                NameObject("/Type"): NameObject("/ExtGState"),
                NameObject("/ca"):   FloatObject(opacity),   # fill opacity
                NameObject("/CA"):   FloatObject(opacity),   # stroke opacity
                NameObject("/BM"):   NameObject("/Normal"),  # blend mode
            })
            gs_dict[NameObject(gn)] = writer._add_object(gs_obj)


async def apply_pdf_watermark(input_pdf, output_pdf, watermark_text):
    """
    Apply a diagonal text watermark to every page of a PDF.

    Uses direct content stream injection (NOT merge_page) to guarantee the
    watermark is ALWAYS rendered on top of all page content regardless of
    page type (text, image, hybrid, PPT/slide export).

    Image/slide pages: red-pink text (0.85, 0.1, 0.2) at 75% opacity.
    Text pages: black text at 30% opacity.
    """
    try:
        try:
            from pypdf import PdfReader, PdfWriter
        except ImportError:
            from PyPDF2 import PdfReader, PdfWriter

        reader = PdfReader(input_pdf)
        writer = PdfWriter()

        # Add all pages first so we hold valid page references
        for page in reader.pages:
            writer.add_page(page)

        for pg in writer.pages:
            page_width  = float(pg.mediabox.width)
            page_height = float(pg.mediabox.height)
            is_img      = _pdf_page_is_image_based(pg)

            # Single-watermark: diagonal placement at upper-right area
            single_cfg = [{
                "title":    watermark_text,
                "x_frac":   0.80,
                "y_frac":   0.85,
                "opacity":  0.30,
                "rotation": 45.0,
                "anchor":   "center",
            }]

            stream_bytes, font_map, gs_map = _build_wm_stream_and_resources(
                page_width, page_height, single_cfg, is_img
            )
            _inject_watermark_stream_into_page(pg, stream_bytes, font_map, gs_map, writer)

        with open(output_pdf, "wb") as f_out:
            writer.write(f_out)
        return True
    except Exception as e:
        print(f"PDF watermark error: {e}")
        import traceback; traceback.print_exc()
        return False


async def apply_pdf_watermark_multi(input_pdf, output_pdf, wm_configs):
    """
    Apply multiple watermarks at different locations on every PDF page.

    FORENSIC FIX — Complete rewrite using direct content stream injection.

    ROOT CAUSE OF PREVIOUS INVISIBILITY:
    ─────────────────────────────────────
    1. COLOR BUG: Previous generated PDFs had '1 1 1 rg' (white RGB) for the
       watermark text color. White text on a white slide background = invisible.
    2. MERGE ORDER BUG: pypdf's merge_page() wraps content as a FormXObject.
       On image-based/slide PDFs, the image XObject's transformation matrix
       (e.g. "0.1 0 0 0.1 0 0 cm") and paint operators execute after the merged
       watermark content, physically painting OVER it.
    3. OPACITY LOSS: merge_page() does not reliably propagate /ExtGState opacity
       entries across the merged streams, causing 0% effective opacity.

    FIX APPROACH — Direct Content Stream Injection:
    ─────────────────────────────────────────────────
    • Build raw PDF operator bytes for all watermarks.
    • APPEND those bytes to the page's /Contents array as a new stream object.
    • Because /Contents streams execute in array order, our watermark stream
      runs LAST — guaranteed to render on top of all existing content.
    • Explicit RGB color (never white), explicit opacity ExtGState per item.
    • Works for: text PDFs, image/scan PDFs, PPT/slide exports, hybrid OCR PDFs.

    wm_configs: list of dicts, each with:
      {
        "title"   : str,         watermark text
        "url"     : str | "/d",  clickable URL (added as annotation) or "/d"
        "x_frac"  : float,       x position as fraction of page_width
        "y_frac"  : float,       y position as fraction of page_height
        "opacity" : float,       0.0–1.0 (auto-boosted for image pages)
        "rotation": float,       degrees counter-clockwise
        "anchor"  : str          "center" | "left" | "right"
      }
    Configs where title == "/d" are silently skipped.
    Returns True on success, False on failure.
    """
    try:
        print(f"===== INSIDE apply_pdf_watermark_multi ===== configs={len(wm_configs)} input={input_pdf}")

        try:
            from pypdf import PdfReader, PdfWriter
        except ImportError:
            from PyPDF2 import PdfReader, PdfWriter

        # Filter disabled configs
        active = [cfg for cfg in wm_configs if cfg.get("title", "/d") != "/d"]
        if not active:
            import shutil
            shutil.copy2(input_pdf, output_pdf)
            return True

        reader = PdfReader(input_pdf)
        writer = PdfWriter()

        # Add all pages to writer first (required before modifying page objects)
        for page in reader.pages:
            writer.add_page(page)

        for pg in writer.pages:
            page_width  = float(pg.mediabox.width)
            page_height = float(pg.mediabox.height)
            is_img      = _pdf_page_is_image_based(pg)

            # Build the watermark content stream + resource dicts
            stream_bytes, font_map, gs_map = _build_wm_stream_and_resources(
                page_width, page_height, active, is_img
            )

            # Inject stream as last /Contents entry → renders on top
            _inject_watermark_stream_into_page(pg, stream_bytes, font_map, gs_map, writer)

            # Add URL link annotations if any config has a URL
            for cfg in active:
                url = cfg.get("url", "/d")
                if not url or url == "/d":
                    continue
                try:
                    from pypdf.generic import (
                        DictionaryObject, ArrayObject, NameObject,
                        FloatObject, ByteStringObject, RectangleObject,
                    )
                    title    = cfg["title"]
                    x_frac   = cfg.get("x_frac", 0.80)
                    y_frac   = cfg.get("y_frac", 0.85)
                    rotation = cfg.get("rotation", 0.0)
                    anchor   = cfg.get("anchor", "center")
                    font_size = max(8, int(page_width / 28))
                    if is_img:
                        font_size = max(10, int(page_width / 20))
                    x_pos = page_width  * x_frac
                    y_pos = page_height * y_frac

                    # Rough text width estimate (Helvetica-Bold ~0.6 * font_size per char)
                    char_w    = font_size * 0.6
                    txt_w     = len(title) * char_w
                    if anchor == "center":
                        lx = x_pos - txt_w / 2
                    elif anchor == "right":
                        lx = x_pos - txt_w
                    else:
                        lx = x_pos
                    ly = y_pos - font_size * 0.3
                    rx = lx + txt_w
                    ry = ly + font_size * 1.3

                    annot = DictionaryObject({
                        NameObject("/Type"):    NameObject("/Annot"),
                        NameObject("/Subtype"): NameObject("/Link"),
                        NameObject("/Rect"):    ArrayObject([
                            FloatObject(lx), FloatObject(ly),
                            FloatObject(rx), FloatObject(ry),
                        ]),
                        NameObject("/Border"):  ArrayObject([FloatObject(0), FloatObject(0), FloatObject(0)]),
                        NameObject("/A"):        DictionaryObject({
                            NameObject("/S"):   NameObject("/URI"),
                            NameObject("/URI"): ByteStringObject(url.encode("latin-1")),
                        }),
                    })
                    annot_ref = writer._add_object(annot)
                    if "/Annots" not in pg:
                        from pypdf.generic import ArrayObject as AO
                        pg[NameObject("/Annots")] = AO()
                    pg["/Annots"].append(annot_ref)
                except Exception as link_err:
                    print(f"PDF WM link annotation error: {link_err}")

        with open(output_pdf, "wb") as f_out:
            writer.write(f_out)
        return True

    except Exception as e:
        print(f"PDF multi-watermark error: {e}")
        import traceback; traceback.print_exc()
        return False


# ── PDF Thumbnail downloader — graph.org .jpg URL support + Telegram file_id support ──
async def download_pdf_thumbnail(pdfthumb_url: str, bot=None) -> str | None:
    """
    Download thumbnail from URL (especially graph.org .jpg links) OR
    download from Telegram using file_id (when bot is provided).
    Returns local file path on success, None on failure.
    URL: 5 retries, 45 second timeout total.
    Telegram file_id: direct download via bot.download_media().
    """
    import uuid
    if not pdfthumb_url or pdfthumb_url == "/d":
        return None

    # ── Case 1: Telegram file_id (not a URL, not a local path) ─────────────
    if not (pdfthumb_url.startswith("http://") or pdfthumb_url.startswith("https://")):
        if os.path.exists(pdfthumb_url):
            return pdfthumb_url
        if bot is not None:
            local_thumb = f"pdfthumb_tg_{uuid.uuid4().hex}.jpg"
            try:
                downloaded = await bot.download_media(pdfthumb_url, file_name=local_thumb)
                if downloaded and os.path.exists(downloaded):
                    print(f"PDF thumb downloaded from Telegram file_id: {downloaded}")
                    return downloaded
                else:
                    print(f"PDF thumb Telegram download returned: {downloaded}")
            except Exception as e:
                print(f"PDF thumb Telegram file_id download error: {e}")
            return None
        else:
            print(f"PDF thumb is Telegram file_id but no bot provided, skipping thumbnail.")
            return None

    # ── Case 2: HTTP/HTTPS URL (graph.org .jpg etc) ──────────────────────────
    local_thumb = f"pdfthumb_{uuid.uuid4().hex}.jpg"
    max_retries = 5
    timeout_per_attempt = 9  # 5 retries x 9s = 45s total

    for attempt in range(1, max_retries + 1):
        try:
            dl = requests.get(
                pdfthumb_url,
                timeout=timeout_per_attempt,
                headers={"User-Agent": "Mozilla/5.0"},
                stream=True
            )
            if dl.status_code == 200:
                content = dl.content
                if len(content) > 0:
                    with open(local_thumb, "wb") as tf:
                        tf.write(content)
                    # Validate and convert to proper JPEG for Telegram
                    try:
                        from PIL import Image
                        img = Image.open(local_thumb)
                        img = img.convert("RGB")
                        img.save(local_thumb, "JPEG", quality=90)
                        img.close()
                    except Exception as pil_err:
                        print(f"PDF thumb PIL convert warning: {pil_err}")
                    print(f"PDF thumb downloaded OK (attempt {attempt}): {local_thumb}")
                    return local_thumb
                else:
                    print(f"PDF thumb empty response (attempt {attempt})")
            else:
                print(f"PDF thumb HTTP {dl.status_code} (attempt {attempt})")
        except Exception as e:
            print(f"PDF thumb download error attempt {attempt}: {e}")
        if attempt < max_retries:
            await asyncio.sleep(1)

    print(f"PDF thumb failed after {max_retries} attempts, skipping.")
    if os.path.exists(local_thumb):
        os.remove(local_thumb)
    return None


async def send_doc(bot: Client, m: Message, cc, ka, cc1, prog, count, name, channel_id, pdfwatermark="/d", pdfthumb="/d"):
    import uuid
    import globals as _globals_mod
    print(f"===== PDF BLOCK ENTERED ===== file={ka} pdfwatermark_arg={pdfwatermark}")
    reply = await bot.send_message(channel_id, f"Downloading pdf:\n<pre><code>{name}</code></pre>")
    time.sleep(1)

    safe_name = re.sub(r'[\\/*?:"<>|]', "_", name)
    final_pdf = ka
    watermarked = False
    local_thumb = None

    # ── Build multi-location watermark configs from globals ───────────────────
    _wm_configs = []
    print(f"[PDF WM] globals check → upper_right={_globals_mod.pdf_wm_upper_right}, down_middle={_globals_mod.pdf_wm_down_middle}")

    # Upper Right: 30% opacity, 45° rotation
    ur = getattr(_globals_mod, "pdf_wm_upper_right", {"title": "/d", "url": "/d"})
    if ur.get("title", "/d") != "/d":
        _wm_configs.append({"title": ur["title"], "url": ur.get("url", "/d"),
                             "x_frac": 0.80, "y_frac": 0.85, "opacity": 0.30,
                             "rotation": 45.0, "anchor": "center"})
    # Upper Left: 30% opacity, 0° rotation
    ul = getattr(_globals_mod, "pdf_wm_upper_left", {"title": "/d", "url": "/d"})
    if ul.get("title", "/d") != "/d":
        _wm_configs.append({"title": ul["title"], "url": ul.get("url", "/d"),
                             "x_frac": 0.15, "y_frac": 0.85, "opacity": 0.30,
                             "rotation": 0.0, "anchor": "left"})
    # Down Right: 90% opacity, 0° rotation
    dr = getattr(_globals_mod, "pdf_wm_down_right", {"title": "/d", "url": "/d"})
    if dr.get("title", "/d") != "/d":
        _wm_configs.append({"title": dr["title"], "url": dr.get("url", "/d"),
                             "x_frac": 0.80, "y_frac": 0.06, "opacity": 0.90,
                             "rotation": 0.0, "anchor": "right"})
    # Down Left: 30% opacity, 0° rotation
    dl = getattr(_globals_mod, "pdf_wm_down_left", {"title": "/d", "url": "/d"})
    if dl.get("title", "/d") != "/d":
        _wm_configs.append({"title": dl["title"], "url": dl.get("url", "/d"),
                             "x_frac": 0.15, "y_frac": 0.06, "opacity": 0.30,
                             "rotation": 0.0, "anchor": "left"})
    # Down Middle: 95% opacity, 0° rotation
    dm = getattr(_globals_mod, "pdf_wm_down_middle", {"title": "/d", "url": "/d"})
    if dm.get("title", "/d") != "/d":
        _wm_configs.append({"title": dm["title"], "url": dm.get("url", "/d"),
                             "x_frac": 0.50, "y_frac": 0.04, "opacity": 0.95,
                             "rotation": 0.0, "anchor": "center"})

    print(f"[PDF WM] Active watermark configs: {len(_wm_configs)}")

    # ── Apply watermarks (multi-location if any configs set, else simple rename) ──
    if _wm_configs:
        # Apply all locations in one pass
        _mwm_output = f"@MR_Toxic_1_{safe_name}_mwm.pdf"
        print(f"===== CALLING PDF WATERMARK ===== configs={len(_wm_configs)} → {_mwm_output}")
        try:
            _mwm_success = await asyncio.wait_for(
                apply_pdf_watermark_multi(ka, _mwm_output, _wm_configs),
                timeout=180
            )
            if _mwm_success and os.path.exists(_mwm_output):
                final_pdf = _mwm_output
                watermarked = True
                print(f"[PDF WM] Multi-watermark applied successfully: {_mwm_output}")
            else:
                print(f"[PDF WM] Multi-watermark failed, using original")
                final_pdf = ka
        except asyncio.TimeoutError:
            print("[PDF WM] Multi-watermark timed out, using original")
            final_pdf = ka
        except Exception as _mwm_err:
            print(f"[PDF WM] Multi-watermark error: {_mwm_err}")
            final_pdf = ka
    elif pdfwatermark and pdfwatermark != "/d":
        # Legacy single watermark fallback (old pdfwatermark global)
        wm_output = f"@MR_Toxic_1_{safe_name}_wm.pdf"
        try:
            success = await asyncio.wait_for(
                apply_pdf_watermark(ka, wm_output, pdfwatermark),
                timeout=120
            )
        except asyncio.TimeoutError:
            success = False
            print("[PDF WM] Single watermark timed out")
        if success and os.path.exists(wm_output):
            final_pdf = wm_output
            watermarked = True
    else:
        # No watermark — rename with prefix
        named_pdf = f"@MR_Toxic_1_{safe_name}.pdf"
        try:
            os.rename(ka, named_pdf)
            final_pdf = named_pdf
            ka = named_pdf
        except Exception as rename_err:
            print(f"PDF rename error: {rename_err}")
    # ─────────────────────────────────────────────────────────────────────────

    # ── PDF Thumbnail — 5 retries, 45s total, graph.org .jpg + Telegram file_id support ──
    thumbnail = None
    if pdfthumb and pdfthumb != "/d":
        try:
            local_thumb = await asyncio.wait_for(
                download_pdf_thumbnail(pdfthumb, bot=bot),
                timeout=45
            )
        except asyncio.TimeoutError:
            print("PDF thumbnail download timed out (45s)")
            local_thumb = None
        except Exception as e:
            print(f"PDF thumbnail download error: {e}")
            local_thumb = None
        if local_thumb and os.path.exists(local_thumb):
            thumbnail = local_thumb
        else:
            thumbnail = None

    reply_up = await bot.send_message(channel_id, f"**📩 Uploading PDF 📩:-**\n<blockquote>**{name}**</blockquote>")
    try:
        if thumbnail:
            await bot.send_document(channel_id, final_pdf, caption=cc1, thumb=thumbnail)
        else:
            await bot.send_document(channel_id, final_pdf, caption=cc1)
    except Exception as e:
        print(f"send_document with thumb error: {e}")
        try:
            await bot.send_document(channel_id, final_pdf, caption=cc1)
        except Exception as e2:
            print(f"send_document fallback error: {e2}")

    count += 1
    await reply.delete(True)
    await reply_up.delete(True)
    time.sleep(1)
    if watermarked and os.path.exists(final_pdf):
        os.remove(final_pdf)
    if ka != final_pdf and os.path.exists(ka):
        os.remove(ka)
    elif os.path.exists(ka):
        os.remove(ka)
    if local_thumb and os.path.exists(local_thumb):
        os.remove(local_thumb)
    time.sleep(3)


def decrypt_file(file_path, key):  
    if not os.path.exists(file_path): 
        return False  

    with open(file_path, "r+b") as f:  
        num_bytes = min(28, os.path.getsize(file_path))  
        with mmap.mmap(f.fileno(), length=num_bytes, access=mmap.ACCESS_WRITE) as mmapped_file:  
            for i in range(num_bytes):  
                mmapped_file[i] ^= ord(key[i]) if i < len(key) else i 
    return True  

async def download_and_decrypt_video(url, cmd, name, key):  
    video_path = await download_video(url, cmd, name)  
    
    if video_path:  
        decrypted = decrypt_file(video_path, key)  
        if decrypted:  
            print(f"File {video_path} decrypted successfully.")  
            return video_path  
        else:  
            print(f"Failed to decrypt {video_path}.")  
            return None  

def _fmt_duration(seconds: int) -> str:
    """Convert seconds → H:MM:SS format. E.g. 6397 → 1:46:37"""
    if not seconds or seconds <= 0:
        return "0:00:00"
    h = seconds // 3600
    m_val = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}:{m_val:02d}:{s:02d}"


async def send_vid(bot: Client, m: Message, cc, filename, vidwatermark, thumb, name, prog, channel_id):
    import uuid

    # ── File existence check — fail fast with clear reason ─────────────────
    if not filename or not os.path.isfile(str(filename)):
        await prog.delete(True)
        raise FileNotFoundError(
            f"Download failed: file not found after yt-dlp. "
            f"This URL may be unsupported, private, age-restricted, "
            f"or requires special cookies/token. (expected: {filename})"
        )
    # ──────────────────────────────────────────────────────────────────────

    await prog.delete(True)
    reply1 = await bot.send_message(channel_id, f"**📩 Uploading Video 📩:-**\n<blockquote>**{name}**</blockquote>")
    reply = await m.reply_text(f"**Generate Thumbnail:**\n<blockquote>**{name}**</blockquote>")

    # ── Extract thumbnail frame at 10s from video ──────────────────────────
    safe_thumb = f"thumb_{uuid.uuid4().hex}.jpg"
    try:
        if _TURBO_AVAILABLE:
            # Non-blocking async ffmpeg thumb extraction
            await extract_thumb_fast(filename, safe_thumb)
        else:
            proc_th = await asyncio.create_subprocess_shell(
                f'ffmpeg -y -i "{filename}" -ss 00:00:10 -vframes 1 -update 1 "{safe_thumb}"',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(proc_th.communicate(), timeout=25)
    except Exception:
        pass

    # ── Resolve thumbnail (thumb URL or fallback to extracted frame) ──────
    thumbnail = None
    local_thumb = None
    if thumb and thumb != "/d":
        if thumb.startswith("http://") or thumb.startswith("https://"):
            local_thumb = f"vthumb_{uuid.uuid4().hex}.jpg"
            try:
                dl = requests.get(thumb, timeout=25, headers={"User-Agent": "Mozilla/5.0"}, stream=True)
                if dl.status_code == 200 and len(dl.content) > 0:
                    with open(local_thumb, "wb") as tf:
                        tf.write(dl.content)
                    thumbnail = local_thumb
                else:
                    thumbnail = safe_thumb if os.path.exists(safe_thumb) else None
            except Exception:
                if os.path.exists(local_thumb):
                    os.remove(local_thumb)
                local_thumb = None
                thumbnail = safe_thumb if os.path.exists(safe_thumb) else None
        elif thumb.lower() == "no":
            thumbnail = safe_thumb if os.path.exists(safe_thumb) else None
        else:
            thumbnail = thumb if os.path.exists(thumb) else (safe_thumb if os.path.exists(safe_thumb) else None)
    else:
        thumbnail = safe_thumb if os.path.exists(safe_thumb) else None

    dur = int(duration(filename))
    duration_str = _fmt_duration(dur)
    if duration_str:
        cc = f"**🕐 Video Duration: {duration_str}\n\n" + cc
    start_time = time.time()

    # ── Upload as VIDEO ────────────────────────────────────────────────────
    try:
        await bot.send_video(
            channel_id, filename, caption=cc,
            supports_streaming=True, height=720, width=1280,
            thumb=thumbnail, duration=dur,
            progress=progress_bar, progress_args=(reply, start_time)
        )
    except Exception as e1:
        print(f"send_video failed: {e1}, retrying without thumbnail")
        try:
            await bot.send_video(
                channel_id, filename, caption=cc,
                supports_streaming=True, height=720, width=1280,
                duration=dur,
                progress=progress_bar, progress_args=(reply, start_time)
            )
        except Exception as e2:
            print(f"send_video no-thumb failed: {e2}, fallback to document")
            try:
                await bot.send_document(
                    channel_id, filename, caption=cc,
                    progress=progress_bar, progress_args=(reply, start_time)
                )
            except Exception as e3:
                print(f"send_document fallback failed: {e3}")
                # ── Re-raise so drm_handler can notify user via send_failed_notice ──
                raise RuntimeError(f"All upload attempts failed: {e3}") from e3

    # ── Cleanup ────────────────────────────────────────────────────────────
    if os.path.exists(filename):
        os.remove(filename)
    await reply.delete(True)
    await reply1.delete(True)
    if safe_thumb and os.path.exists(safe_thumb):
        os.remove(safe_thumb)
    if local_thumb and os.path.exists(local_thumb):
        os.remove(local_thumb)

