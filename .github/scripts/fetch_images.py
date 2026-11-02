"""Download product photos into images/ so the page hosts its own copies.

Run it on your own computer from the repo folder:   python3 .github/scripts/fetch_images.py
then commit and push images/ and index.html.

(It doesn't work from GitHub Actions: on 2026-11-01 Sierra, TJ Maxx and Marshalls
all answered 403 to GitHub's servers.)

For each listing without a hosted copy it saves images/<store>-<id>.jpg and records
"local" on that listing in index.html, so the page uses the hosted copy first.
Sierra links point at 60px thumbnails, so larger sizes of the same image are tried
and only a larger copy is saved (the page already falls back to the thumbnail link).
TJ Maxx / Marshalls get one plain request; if refused, the photo is skipped.
"""
import json, os, re, sys, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "images")
UA = "allbirds-size9 photo fetch (GitHub Actions; https://github.com/senator-donut/allbirds-size9)"

def slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower())

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, "", b""
    except Exception as e:
        return str(e)[:60], "", b""

def is_image(b):
    return b[:3] == b"\xff\xd8\xff" or b[:8] == b"\x89PNG\r\n\x1a\n" or (b[:4] == b"RIFF" and b[8:12] == b"WEBP")

def main():
    hpath = os.path.join(ROOT, "index.html")
    html = open(hpath, encoding="utf-8").read()
    block_m = re.search(r'(<script id="report-data" type="application/json">)(.*?)(</script>)', html, re.S)
    data = json.loads(block_m.group(2))
    os.makedirs(OUT, exist_ok=True)
    mpath = os.path.join(OUT, "manifest.json")
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    saved = skipped = kept = 0
    for it in data["items"]:
        if not it.get("image"):
            continue
        name = f'{slug(it["store"])}-{it["productId"].lower()}.jpg'
        dest = os.path.join(OUT, name)
        if os.path.exists(dest):
            it["local"] = "images/" + name
            kept += 1
            continue
        src = it["image"]
        tm = re.match(r"^(.*~)60(\.\d+\.jpg)$", src) if it.get("thumb") else None
        candidates = [tm.group(1) + sz + tm.group(2) for sz in ("1500", "460")] if tm else [src]
        got = None
        for url in candidates:
            status, ctype, body = get(url)
            ok = status == 200 and is_image(body) and len(body) > 2000
            print(f"  {name}: {status} {len(body):>7}B {'OK' if ok else 'no'}  {url[:110]}")
            if ok:
                got = (url, body)
                break
            time.sleep(0.3)
        if got:
            open(dest, "wb").write(got[1])
            it["local"] = "images/" + name
            manifest[name] = {"source": got[0], "bytes": len(got[1]), "listing": it["url"]}
            saved += 1
        else:
            skipped += 1
        time.sleep(0.3)
    json.dump(manifest, open(mpath, "w"), indent=2, sort_keys=True)
    if saved or kept:
        block = "\n  " + json.dumps(data, indent=2, ensure_ascii=False).replace("\n", "\n  ") + "\n  "
        new_html = html[:block_m.start(2)] + block + html[block_m.end(2):]   # build fully before touching the file
        json.loads(re.search(r'<script id="report-data" type="application/json">(.*?)</script>', new_html, re.S).group(1))
        tmp = hpath + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(new_html)
        os.replace(tmp, hpath)
    print(f"saved {saved}, already had {kept}, could not get {skipped}")

if __name__ == "__main__":
    sys.exit(main())
