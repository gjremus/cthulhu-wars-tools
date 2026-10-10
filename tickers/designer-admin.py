#!/usr/bin/env python3
"""
Designer admin helper for the extraction checker (Haiku every 2 min, Sonnet fallback).

Reads the owner admin token from its file so it never has to appear in a prompt.

  designer-admin.py list-extract            open extract requests (JSON array; [] if none)
  designer-admin.py faction <fid>           full faction record (JSON)
  designer-admin.py unit <uid>              full unit record (JSON)
  designer-admin.py image <imageId>         download image, convert to PNG, print local path
  designer-admin.py patch <fid> <ops.json>  POST {"ops": [...]} from the file to admin patch
  designer-admin.py done <rid> [summary...] mark request done; the summary (one or two plain
                                            sentences on what you did) goes into the admin
                                            console's Claude terminal log
  designer-admin.py tlog-add <type> <user> <id> <promptFile>
                                            add a Claude terminal log row (type: admin, design
                                            extraction, design menu, design build, design bug fix)
  designer-admin.py tlog-summary <id> <summaryFile>
                                            set that row's summary from a file
  designer-admin.py handoff <rid> <reason>  queue request for the Sonnet fallback
  designer-admin.py unit-build-status <uid> <status> [version]
                                            set unit build status (status: in_progress, built, none)
  designer-admin.py request-status <rid> <status>
                                            set request status
  designer-admin.py grid <imageId> [x y w h]
                                            copy with labelled pixel grid (or a zoomed area of it)
                                            so you can read off crop coordinates; prints path
  designer-admin.py crop <imageId> x y w h [--knockout] [--circle]
                                            cut out an area (original-image pixels) to a PNG;
                                            --knockout makes the background around the shape
                                            see-through and trims it; --circle keeps only the
                                            circle/oval that fills the box (round emblems);
                                            prints the PNG path and a preview-on-pink path
  designer-admin.py upload <png>            upload a PNG to the designer; prints the image id

Requests that the Sonnet fallback has already failed MAX_ATTEMPTS times are left out of
list-extract (and the owner is alerted once) so a stuck request cannot loop forever.
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

HOME = os.environ.get('HOME', '/Users/gremus')
TOKEN_FILE = f"{HOME}/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Maps/Library at Celaeno/Server Deployment/owner-admin-token.txt"
SERVER = "https://cwo.freeddns.org"
HANDOFF_FILE = "/tmp/cw-designer-extract-handoff.json"
ATTEMPTS_FILE = "/tmp/cw-designer-extract-attempts.json"
ALERTS_FILE = "/tmp/cw-ticker-alerts.txt"
IMG_DIR = "/tmp/cw-designer-img"
MAX_ATTEMPTS = 3


def token():
    with open(TOKEN_FILE) as f:
        return f.read().strip()


def api(path, body=None):
    url = f"{SERVER}/designer/api/admin/{token()}/{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method='POST' if data else 'GET')
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        # Never echo the URL: it contains the token.
        sys.exit(f"ERROR: HTTP {e.code} on admin/{path.split('?')[0]}: {e.read().decode(errors='replace')[:300]}")


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(path, value):
    with open(path, 'w') as f:
        json.dump(value, f, indent=2)


def list_extract():
    reqs = [r for r in api('requests?status=open').get('requests', []) if r.get('type') == 'extract']
    attempts = load(ATTEMPTS_FILE, {})
    keep = []
    for r in reqs:
        a = attempts.get(r['id'], {})
        if a.get('count', 0) >= MAX_ATTEMPTS:
            if not a.get('alerted'):
                with open(ALERTS_FILE, 'a') as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Designer extract gave up after "
                            f"{MAX_ATTEMPTS} tries: {r.get('faction', '?')} ({r['id']}) - needs a look\n")
                a['alerted'] = True
                attempts[r['id']] = a
                save(ATTEMPTS_FILE, attempts)
            continue
        keep.append(r)
    # Designer page "Extraction status": listed by the checker = picked up (no longer "waiting")
    for r in keep:
        if not r.get('pickedUp'):
            try:
                api(f"requests/{r['id']}", {'mark': 'picked'})
            except (Exception, SystemExit) as e:  # api() exits on HTTP errors; never break the listing
                print(f"WARN: could not mark {r['id']} picked up: {e}", file=sys.stderr)
    print(json.dumps(keep, indent=2))


def mark_started(fid):
    """Reading a faction to extract it = the designer page shows "in process" for its oldest open extract."""
    try:
        reqs = [r for r in api('requests?status=open').get('requests', [])
                if r.get('type') == 'extract' and r.get('fid') == fid]
        if reqs:
            oldest = min(reqs, key=lambda r: r.get('created', 0))
            if not oldest.get('startedAt'):
                api(f"requests/{oldest['id']}", {'mark': 'started'})
    except (Exception, SystemExit) as e:
        print(f"WARN: could not mark {fid} in process: {e}", file=sys.stderr)


def image(image_id):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', image_id):
        sys.exit("ERROR: bad image id")
    os.makedirs(IMG_DIR, exist_ok=True)
    src = os.path.join(IMG_DIR, image_id)
    if not os.path.exists(src):
        urllib.request.urlretrieve(f"{SERVER}/designer/img/{image_id}", src)
    png = os.path.splitext(src)[0] + '.png'
    if not os.path.exists(png):
        subprocess.run(['/usr/bin/sips', '-s', 'format', 'png', src, '--out', png],
                       check=True, capture_output=True)
    print(png)


def need_pil():
    # The ticker python has no Pillow; the system one does.
    try:
        import PIL  # noqa: F401
    except ImportError:
        if sys.executable != '/usr/bin/python3':
            os.execv('/usr/bin/python3', ['/usr/bin/python3'] + sys.argv)
        sys.exit("ERROR: Pillow not available")


def local_png(image_id):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', image_id):
        sys.exit("ERROR: bad image id")
    png = os.path.join(IMG_DIR, os.path.splitext(image_id)[0] + '.png')
    if not os.path.exists(png):
        with open(os.devnull, 'w') as null:
            sys.stdout, old = null, sys.stdout
            try:
                image(image_id)
            finally:
                sys.stdout = old
    return png


def grid(image_id, box):
    from PIL import Image, ImageDraw
    im = Image.open(local_png(image_id)).convert('RGB')
    x0, y0 = 0, 0
    if box:
        x0, y0, w, h = box
        im = im.crop((x0, y0, x0 + w, y0 + h))
    # Show at most ~1400 px wide; zoomed areas are scaled up so small icons are easy to see.
    scale = min(4.0, 1400 / max(im.width, 1))
    im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))))
    step = 100 if not box else (10 if max(box[2], box[3]) <= 200 else 25 if max(box[2], box[3]) <= 500 else 50)
    d = ImageDraw.Draw(im)
    first = lambda o: (o + step - 1) // step * step
    for gx in range(first(x0), x0 + int(im.width / scale) + 1, step):
        px = int((gx - x0) * scale)
        major = gx % (step * 5) == 0
        d.line([(px, 0), (px, im.height)], fill=(255, 0, 0) if major else (255, 160, 0), width=1)
        d.text((px + 2, 2), str(gx), fill=(255, 255, 0), stroke_width=2, stroke_fill=(0, 0, 0))
    for gy in range(first(y0), y0 + int(im.height / scale) + 1, step):
        py = int((gy - y0) * scale)
        major = gy % (step * 5) == 0
        d.line([(0, py), (im.width, py)], fill=(255, 0, 0) if major else (255, 160, 0), width=1)
        d.text((2, py + 2), str(gy), fill=(255, 255, 0), stroke_width=2, stroke_fill=(0, 0, 0))
    tag = f"-{x0}-{y0}-{box[2]}-{box[3]}" if box else ''
    out = os.path.join(IMG_DIR, f"{os.path.splitext(image_id)[0]}-grid{tag}.png")
    im.save(out)
    print(out)
    print("labels are ORIGINAL image pixels; pass them straight to crop")


def crop(image_id, box, knockout, circle):
    from PIL import Image, ImageDraw, ImageChops
    from collections import deque
    x, y, w, h = box
    im = Image.open(local_png(image_id)).convert('RGBA').crop((x, y, x + w, y + h))
    raw, mask = im.copy(), None
    if circle:
        # Drawn 4x bigger then shrunk, for a smooth edge.
        m = Image.new('L', (w * 4, h * 4), 0)
        ImageDraw.Draw(m).ellipse((0, 0, w * 4 - 1, h * 4 - 1), fill=255)
        mask = m.resize((w, h), Image.LANCZOS)
        im.putalpha(ImageChops.multiply(im.getchannel('A'), mask))
    if knockout:
        # Background = colour along the crop border. Flood-fill from the border through
        # pixels close to it and make them see-through (soft edge), then trim.
        px = im.load()
        W, H = im.size
        border = [px[i, 0] for i in range(W)] + [px[i, H - 1] for i in range(W)] + \
                 [px[0, j] for j in range(H)] + [px[W - 1, j] for j in range(H)]
        if circle:
            # The box corners outside the oval are real background; sample those.
            border = [c for c, a in zip(raw.getdata(), mask.getdata()) if a == 0] or border
        bg = tuple(sorted(c[k] for c in border)[len(border) // 2] for k in range(3))
        dist = lambda c: max(abs(c[0] - bg[0]), abs(c[1] - bg[1]), abs(c[2] - bg[2]))
        hard, soft = 40, 80
        seen = bytearray(W * H)
        q = deque((i, j) for i in range(W) for j in (0, H - 1))
        q.extend((i, j) for j in range(H) for i in (0, W - 1))
        while q:
            i, j = q.popleft()
            if seen[j * W + i]:
                continue
            seen[j * W + i] = 1
            c = px[i, j]
            dd = 0 if c[3] == 0 else dist(c)
            if dd >= soft:
                continue
            a = 0 if dd <= hard else int(255 * (dd - hard) / (soft - hard))
            px[i, j] = (c[0], c[1], c[2], min(c[3], a))
            for ni, nj in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                if 0 <= ni < W and 0 <= nj < H and not seen[nj * W + ni]:
                    q.append((ni, nj))
        bbox = im.getchannel('A').getbbox()
        if not bbox:
            sys.exit("ERROR: knockout removed everything; crop is all background")
        im = im.crop(bbox)
        kept = sum(1 for a in im.getchannel('A').getdata() if a > 0) / (im.width * im.height)
        print(f"kept {kept:.0%} of the trimmed area (near 100% = background not removed)")
    out = os.path.join(IMG_DIR, f"crop-{os.path.splitext(image_id)[0][:12]}-{x}-{y}-{w}-{h}"
                                f"{'-k' if knockout else ''}{'-c' if circle else ''}.png")
    im.save(out)
    print(out)
    # Preview: 3x bigger on bright pink, so leftover background is easy to spot.
    scale = max(1, min(4, 300 // max(im.width, im.height, 1)))
    big = im.resize((im.width * scale, im.height * scale), Image.LANCZOS)
    prev = Image.new('RGBA', (big.width + 20, big.height + 20), (255, 0, 255, 255))
    prev.alpha_composite(big, (10, 10))
    prev_path = out[:-4] + '-preview.png'
    prev.convert('RGB').save(prev_path)
    print(f"preview (look at this; pink = see-through): {prev_path}")


def upload(path):
    with open(path, 'rb') as f:
        data = f.read()
    if not data.startswith(b'\x89PNG'):
        sys.exit("ERROR: upload takes a PNG file")
    req = urllib.request.Request(f"{SERVER}/designer/api/admin/{token()}/images", data=data, method='POST')
    req.add_header('Content-Type', 'image/png')
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(json.load(r)['id'])
    except urllib.error.HTTPError as e:
        sys.exit(f"ERROR: HTTP {e.code} on admin/images: {e.read().decode(errors='replace')[:300]}")


def ints(vals):
    try:
        out = [int(v) for v in vals]
    except ValueError:
        sys.exit("ERROR: x y w h must be whole numbers")
    if out[2] <= 0 or out[3] <= 0 or out[0] < 0 or out[1] < 0:
        sys.exit("ERROR: bad box")
    return out


def handoff(rid, reason):
    queued = load(HANDOFF_FILE, [])
    if not any(h['id'] == rid for h in queued):
        queued.append({'id': rid, 'reason': reason})
    save(HANDOFF_FILE, queued)
    print(f"handed off {rid}")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'list-extract':
        list_extract()
    elif cmd == 'faction' and len(args) == 1:
        mark_started(args[0])
        print(json.dumps(api(f'factions/{args[0]}'), indent=2))
    elif cmd == 'unit' and len(args) == 1:
        print(json.dumps(api(f'units/{args[0]}'), indent=2))
    elif cmd == 'image' and len(args) == 1:
        image(args[0])
    elif cmd == 'patch' and len(args) == 2:
        ops = load(args[1], None)
        if ops is None:
            sys.exit(f"ERROR: could not read JSON from {args[1]}")
        if isinstance(ops, dict):
            ops = ops.get('ops', [])
        print(json.dumps(api(f'factions/{args[0]}/patch', {'ops': ops})))
    elif cmd == 'done' and len(args) >= 1:
        print(json.dumps(api(f'requests/{args[0]}', {'status': 'done'})))
        if len(args) > 1:
            api(f'terminal-log/{args[0]}', {'summary': ' '.join(args[1:])})
    elif cmd == 'tlog-add' and len(args) == 4:
        prompt = open(args[3], errors='replace').read().strip()
        print(json.dumps(api('terminal-log', {'type': args[0], 'user': args[1], 'id': args[2],
                                              'prompt': prompt, 'summary': 'Queued.'})))
    elif cmd == 'tlog-summary' and len(args) == 2:
        summary = open(args[1], errors='replace').read().strip()
        api(f'terminal-log/{args[0]}', {'summary': summary})
    elif cmd == 'handoff' and len(args) >= 2:
        handoff(args[0], ' '.join(args[1:]))
    elif cmd == 'unit-build-status' and len(args) in (2, 3):
        body = {'status': args[1]}
        if len(args) == 3:
            body['version'] = args[2]
        print(json.dumps(api(f'units/{args[0]}/build-status', body)))
    elif cmd == 'request-status' and len(args) == 2:
        print(json.dumps(api(f'requests/{args[0]}', {'status': args[1]})))
    elif cmd == 'grid' and len(args) in (1, 5):
        need_pil()
        grid(args[0], ints(args[1:]) if len(args) == 5 else None)
    elif cmd == 'crop' and len(args) >= 5 and set(args[5:]) <= {'--knockout', '--circle'}:
        need_pil()
        crop(args[0], ints(args[1:5]), '--knockout' in args[5:], '--circle' in args[5:])
    elif cmd == 'upload' and len(args) == 1:
        upload(args[0])
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
