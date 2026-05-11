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
DEFAULT_REFERER = "http://oxax.tv/"
DEFAULT_ORIGIN = "http://oxax.tv"

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


def build_page_headers():
    return {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Referer": DEFAULT_REFERER,
        "Origin": DEFAULT_ORIGIN,
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }


def build_stream_headers(stream_url):
    parsed = urlparse(stream_url)

    return {
        "Host": parsed.netloc,
        "Connection": "keep-alive",
        "sec-ch-ua-platform": '"Windows"',
        "User-Agent": UA,
        "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "Accept": "*/*",
        "Origin": DEFAULT_ORIGIN,
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": DEFAULT_REFERER,
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
    }


def extract_live_url(page_url: str):
    session = requests.Session()

    response_page = session.get(
        page_url,
        headers=build_page_headers(),
        timeout=20,
        verify=False
    )

    html = response_page.text

    kodk = re.search(r'kodk="(.*?)"', html)
    kos = re.search(r'kos="(.*?)"', html)
    block = re.search(r'#F(.*?)"', html)

    if not block:
        return {
            "status": "error",
            "step": "html_extract",
            "message": "No se encontró bloque #F",
            "http_status": response_page.status_code,
            "page_url": page_url,
            "preview": html[:800]
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
            "step": "base64_decode",
            "message": str(e),
            "datacode_preview": datacode[:800]
        }

    if "file" not in data:
        return {
            "status": "error",
            "step": "json_file",
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
            "step": "stream_url",
            "message": "URL stream inválida",
            "stream_raw": stream_raw
        }

    response_stream = session.get(
        stream_url,
        headers=build_stream_headers(stream_url),
        timeout=15,
        allow_redirects=False,
        verify=False
    )

    location = response_stream.headers.get("Location")

    if not location:
        return {
            "status": "error",
            "step": "redirect_location",
            "message": "No se encontró Location en la respuesta del stream",
            "http_status": response_stream.status_code,
            "stream_url": stream_url,
            "headers": dict(response_stream.headers),
            "preview": response_stream.text[:800]
        }

    live_url = urljoin(stream_url, location)

    return {
        "status": "ok",
        "page_url": page_url,
        "stream_url": stream_url,
        "http_status": response_stream.status_code,
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


@app.route("/resolve")
def resolve():
    url = request.args.get("url")

    if not url:
        return jsonify({
            "status": "error",
            "message": "Falta el parámetro url"
        }), 400

    try:
        response = requests.get(
            url,
            headers=build_stream_headers(url),
            timeout=15,
            allow_redirects=False,
            verify=False
        )

        location = response.headers.get("Location")

        return jsonify({
            "status": "ok",
            "http_status": response.status_code,
            "location": location,
            "url": urljoin(url, location) if location else None,
            "headers": dict(response.headers),
            "preview": response.text[:500] if not location else None
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
