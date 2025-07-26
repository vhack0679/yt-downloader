from flask import Flask, render_template, request, redirect, url_for, jsonify
import yt_dlp
import os
import uuid
import threading

app = Flask(__name__)
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), 'downloads')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

progress_dict = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/formats', methods=['POST'])
def get_formats():
    url = request.form['url']
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'format': 'bestvideo*+bestaudio/best',
        'noplaylist': True,
    }

    formats = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            for fmt in info.get('formats', []):
                if fmt.get('ext') and fmt.get('format_id') and fmt.get('url'):
                    formats.append({
                        'format_id': fmt['format_id'],
                        'ext': fmt['ext'],
                        'resolution': fmt.get('resolution', fmt.get('height', 'unknown')),
                        'filesize': fmt.get('filesize')
                    })
        except Exception as e:
            return jsonify({'error': str(e)})

    return jsonify({'formats': formats})


@app.route('/download', methods=['POST'])
def download():
    url = request.form['url']
    format_id = request.form['format_id']
    uid = str(uuid.uuid4())
    progress_dict[uid] = "Starting download..."

    def download_video_thread():
        ydl_opts = {
            'format': format_id,
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'{uid}.%(ext)s'),
            'progress_hooks': [lambda d: progress_dict.update({uid: d['_percent_str']}) if d['status'] == 'downloading' else None],
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            progress_dict[uid] = "Download complete"
        except Exception as e:
            progress_dict[uid] = f"Error: {str(e)}"

    threading.Thread(target=download_video_thread).start()
    return jsonify({'id': uid})

@app.route('/progress/<uid>')
def progress(uid):
    return jsonify({'progress': progress_dict.get(uid, 'Unknown ID')})
