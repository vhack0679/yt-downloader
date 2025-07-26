from flask import Flask, request, jsonify, send_file, render_template
import os
import uuid
import threading
import yt_dlp

app = Flask(__name__)
DOWNLOAD_FOLDER = 'downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
progress_data = {}
format_cache = {}

def download_video_thread(url, format_id, download_id):
    def progress_hook(d):
        if d['status'] == 'downloading':
            progress_data[download_id] = {
                'progress': d.get('_percent_str', '0%'),
                'status': 'downloading'
            }
        elif d['status'] == 'finished':
            progress_data[download_id] = {
                'progress': '100%',
                'status': 'finished'
            }

    outtmpl = os.path.join(DOWNLOAD_FOLDER, f'{download_id}.%(ext)s')
    ydl_opts = {
        'format': format_id,
        'progress_hooks': [progress_hook],
        'outtmpl': outtmpl,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        ext = info.get('ext')
        progress_data[download_id]['file_path'] = outtmpl.replace('%(ext)s', ext)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/formats', methods=['POST'])
def get_formats():
    data = request.json
    url = data['url']
    if url in format_cache:
        return jsonify(format_cache[url])
    with yt_dlp.YoutubeDL({}) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = [
            {
                'format_id': fmt['format_id'],
                'ext': fmt['ext'],
                'resolution': fmt.get('resolution') or f"{fmt.get('width')}x{fmt.get('height')}",
                'filesize': fmt.get('filesize'),
                'format_note': fmt.get('format_note')
            }
            for fmt in info['formats']
            if fmt.get('vcodec') != 'none' and fmt.get('acodec') != 'none'
        ]
        format_cache[url] = formats
        return jsonify(formats)

@app.route('/download', methods=['POST'])
def download():
    data = request.json
    url = data['url']
    format_id = data['format_id']
    download_id = str(uuid.uuid4())
    progress_data[download_id] = {'progress': '0%', 'status': 'queued'}
    thread = threading.Thread(target=download_video_thread, args=(url, format_id, download_id))
    thread.start()
    return jsonify({'download_id': download_id})

@app.route('/progress/<download_id>')
def progress(download_id):
    return jsonify(progress_data.get(download_id, {}))

@app.route('/download/<download_id>')
def serve_file(download_id):
    info = progress_data.get(download_id, {})
    file_path = info.get('file_path')
    if file_path and os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return 'File not found', 404

if __name__ == '__main__':
    app.run(debug=True)
