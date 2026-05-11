import re
import json
import base64
import urllib3
import requests

from flask import Flask, jsonify, request
from flask_cors import CORS
from urllib.parse import urljoin, urlparse

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
CORS(app)

DEFAULT_PAGE_URL = "http://oxax.tv/oh-ah.html"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/148.0.0.0 Safari/537.36"
)

GARBAGE = [
    "FNTU2RzNE",
    "FNTU2RzNEUQ==",
    "FNTU2RzNEUTE=",
    "FNTU2RzNEUTFW",
    "FNTU2RzUQ==M=",
    "UTFW",
    "M=",
    "UTE=",
    "UQ==",
    "FNTU2RzM=",
    "FNTU2RzNEUTFWNTU2RzNEUTE=",
    "FNTU2RzNEUT",
    "FWNTU2RzNEUTE=",
    "FNTU2Rz",
    "FNTU2RzN",
    "EUTE="
]


def extract_live_url(page_url: str):
    session = requests.Session()

    headers_page = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Referer": "http://oxax.tv/",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive"
    }

    r = session.get(
        page_url,
        headers=headers_page,
        timeout=15,
        verify=False
    )

    html = r.text

    kodk = re.search(r'kodk="(.*?)"', html)
    kos = re.search(r'kos="(.*?)"', html)
    block = re.search(r'#F(.*?)"', html)

    if not block:
        return {
            "status": "error",
            "message": "No se encontró bloque #F",
            "http_status": r.status_code,
            "preview": html[:500]
        }

    datacode = block.group(1)

    for gb in GARBAGE:
        datacode = datacode.replace(gb, "")

    try:
        datacode += "=" * (-len(datacode) % 4)

        decoded = base64.b64decode(datacode).decode(
            "utf-8",
            errors="ignore"
        )

        data = json.loads(decoded)

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error decodificando Base64/JSON: {str(e)}",
            "datacode": datacode[:500]
        }

    if "file" not in data:
        return {
            "status": "error",
            "message": "No existe 'file' en el JSON decodificado",
            "decoded": data
        }

    stream_raw = data["file"]

    if kodk:
        stream_raw = stream_raw.replace("{v1}", kodk.group(1))

    if kos:
        stream_raw = stream_raw.replace("{v2}", kos.group(1))

    stream_url = stream_raw.split(" or ")[0].strip()

    if not stream_url.startswith("http"):
        return {
            "status": "error",
            "message": "URL stream inválida",
            "stream_raw": stream_raw
        }

    parsed = urlparse(stream_url)

    headers_stream = {
        "Host": parsed.netloc,
        "Connection": "keep-alive",
        "sec-ch-ua-platform": '"Windows"',
        "User-Agent": UA,
        "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "Accept": "*/*",
        "Origin": "http://oxax.tv",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "http://oxax.tv/",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate"
    }

    r2 = session.get(
        stream_url,
        headers=headers_stream,
        timeout=10,
        allow_redirects=False,
        verify=False
    )

    location = r2.headers.get("Location")

    if not location:
        return {
            "status": "error",
            "message": "No se encontró Location en la respuesta del stream",
            "http_status": r2.status_code,
            "stream_url": stream_url,
            "preview": r2.text[:500],
            "headers": dict(r2.headers)
        }

    live_url = urljoin(stream_url, location)

    return {
        "status": "ok",
        "page_url": page_url,
        "stream_url": stream_url,
        "http_status": r2.status_code,
        "location": location,
        "url": live_url
    }


@app.route("/")
def home():
    return "mas18TV API funcionando"


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "mas18TV Render Python API"
    })


@app.route("/live")
def live():
    page_url = request.args.get("page", DEFAULT_PAGE_URL)
    result = extract_live_url(page_url)
    status_code = 200 if result.get("status") == "ok" else 500
    return jsonify(result), status_code
