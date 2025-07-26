from flask import Flask, request, jsonify, send_file, render_template_string
import os
import uuid
import threading
import yt_dlp

app = Flask(__name__)
DOWNLOAD_FOLDER = 'downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
progress_data = {}

# HTML frontend served at root
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>YouTube Downloader</title>
</head>
<body>
    <h2>YouTube Downloader</h2>
    <input type="text" id="url" placeholder="Enter YouTube URL" style="width:300px;"><br><br>
    <select id="quality">
        <option value="best">Best</option>
        <option value="worst">Worst</option>
        <option value="bestaudio">Audio Only</option>
    </select><br><br>
    <button onclick="startDownload()">Download</button>
    <p id="status"></p>

    <script>
        let downloadId = "";

        function startDownload() {
            const url = document.getElementById('url').value;
            const format_id = document.getElementById('quality').value;
            document.getElementById('status').innerText = "Starting download...";

            fetch('/download', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ url: url, format_id: format_id })
            })
            .then(response => response.json())
            .then(data => {
                downloadId = data.download_id;
                checkProgress();
            });
        }

        function checkProgress() {
            fetch('/progress/' + downloadId)
            .then(response => response.json())
            .then(data => {
                document.getElementById('status').innerText = 
                    "Progress: " + (data.progress || "N/A") + " | Status: " + (data.status || "N/A");

                if (data.status === 'finished') {
                    const a = document.createElement('a');
                    a.href = '/download/' + downloadId;
                    a.innerText = "Click here to download your file";
                    a.download = "";
                    document.body.appendChild(a);
                } else {
                    setTimeout(checkProgress, 1000);
                }
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

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
        'quiet': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        ext = info.get('ext')
        progress_data[download_id]['file_path'] = outtmpl.replace('%(ext)s', ext)

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
