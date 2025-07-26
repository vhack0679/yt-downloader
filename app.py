from flask import Flask, request, jsonify, send_file, render_template
import yt_dlp
import os
import uuid

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/formats")
def formats():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing URL"}), 400

    ydl_opts = {"quiet": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = info.get("formats", [])
        result = []
        for f in formats:
            if f.get("ext") == "mp4" and f.get("height"):  # Filter for video formats
                result.append({
                    "format_id": f["format_id"],
                    "format": f["format"],
                    "ext": f["ext"],
                    "resolution": f.get("resolution", f.get("height"))
                })
        return jsonify({"formats": result})

@app.route("/download", methods=["POST"])
def download():
    data = request.json
    url = data.get("url")
    format_id = data.get("format_id")

    download_id = str(uuid.uuid4())
    filename = f"{download_id}.mp4"

    ydl_opts = {
        "quiet": True,
        "outtmpl": filename,
        "format": format_id,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return jsonify({"status": "ok", "download_id": download_id})
    except Exception as e:
        print(e)
        return jsonify({"status": "error", "error": str(e)})

@app.route("/download/<download_id>")
def get_file(download_id):
    path = f"{download_id}.mp4"
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return "File not found", 404
