from flask import Flask, request, jsonify, send_file
import os
import uuid
import threading
import yt_dlp

app = Flask(__name__)
DOWNLOAD_FOLDER = 'downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
progress_data = {}

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
    return "✅ YouTube Downloader API is working."

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    if not data or 'url' not in data or 'format_id' not in data:
        return jsonify({'error': 'Missing url or format_id'}), 400

    url = data['url']
    format_id = data['format_id']
    download_id = str(uuid.uuid4())
    progress_data[download_id] = {'progress': '0%', 'status': 'queued'}
    
    thread = threading.Thread(target=download_video_thread, args=(url, format_id, download_id))
    thread.start()
    return jsonify({'download_id': download_id})

@app.route('/progress/<download_id>')
def progress(download_id):
    return jsonify(progress_data.get(download_id, {'error': 'Invalid ID'}))

@app.route('/download/<download_id>')
def serve_file(download_id):
    info = progress_data.get(download_id, {})
    file_path = info.get('file_path')
    if file_path and os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return 'File not found', 404

if __name__ == '__main__':
    app.run()
