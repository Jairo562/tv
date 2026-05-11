from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

@app.route("/")
def home():
    return "Jairo162TV API funcionando"

@app.route("/resolve")
def resolve():
    url = request.args.get("url")

    if not url:
        return jsonify({
            "status": "error",
            "message": "Falta el parámetro url"
        }), 400

    try:
        r = requests.get(
            url,
            allow_redirects=False,
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        return jsonify({
            "status": "ok",
            "code": r.status_code,
            "redirect": r.headers.get("Location"),
            "headers": dict(r.headers)
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
