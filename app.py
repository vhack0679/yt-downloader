from flask import Flask, request, jsonify, send_file, render_template_string
import os
import uuid
import threading
import yt_dlp

app = Flask(__name__)
DOWNLOAD_FOLDER = 'downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
progress_data = {}

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>YouTube Downloader</title>
    <style>
        body { font-family: Arial; text-align: center; margin-top: 50px; }
        input, button, select { padding: 10px; margin: 5px; width: 300px; }
        progress { width: 300px; height: 20px; }
    </style>
</head>
<body>
    <h2>🎬 YouTube Downloader</h2>
    <input id="url" placeholder="Paste YouTube link here" />
    <br>
    <button onclick="fetchFormats()">Get Formats</button>
    <br>
    <select id="formatSelect"></select>
    <br>
    <button onclick="startDownload()">Download</button>
    <br><br>
    <progress id="progressBar" value="0" max="100"></progress>
    <p id="statusText"></p>

    <script>
        let currentDownloadId = '';

        function fetchFormats() {
            const url = document.getElementById("url").value;
            fetch('/formats', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url })
            })
            .then(res => res.json())
            .then(data => {
                const select = document.getElementById("formatSelect");
                select.innerHTML = "";
                data.formats.forEach(f => {
                    const opt = document.createElement("option");
                    opt.value = f.format_id;
                    opt.text = `${f.format_id} - ${f.resolution} - ${f.ext}`;
                    select.appendChild(opt);
                });
            });
        }

        function startDownload() {
            const url = document.getElementById("url").value;
            const format_id = document.getElementById("formatSelect").value;
            fetch('/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url, format_id: format_id })
            })
            .then(res => res.json())
            .then(data => {
                currentDownloadId = data.download_id;
                checkProgress();
            });
        }

        function checkProgress() {
            fetch(`/progress/${currentDownloadId}`)
                .then(res => res.json())
                .then(data => {
                    const percent = parseFloat(data.progress || '0');
                    document.getElementById("progressBar").value = percent;
                    document.getElementById("statusText").innerText = `Status: ${data.status || 'N/A'} - ${data.progress}`;

                    if (data.status === 'finished') {
                        document.getElementById("statusText").innerHTML += `<br><a href="/download/${currentDownloadId}" target="_blank">Download File</a>`;
                    } else {
                        setTimeout(checkProgress, 2000);
                    }
                });
        }
    </script>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/formats', methods=['POST'])
def get_formats():
    url = request.json['url']
    formats_list = []
    try:
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            for fmt in info.get('formats', []):
                if fmt.get('vcodec') != 'none' and fmt.get('acodec') != 'none':
                    formats_list.append({
                        'format_id': fmt['format_id'],
                        'ext': fmt['ext'],
                        'resolution': fmt.get('format_note', fmt.get('height', 'N/A'))
                    })
    except Exception as e:
        return jsonify({'error': str(e)})
    
    return jsonify({'formats': formats_list})

def download_video_thread(url, format_id, download_id):
    def progress_hook(d):
        if d['status'] == 'downloading':
            progress_data[download_id] = {
                'progress': d.get('_percent_str', '0%').replace('%', ''),
                'status': 'downloading'
            }
        elif d['status'] == 'finished':
            progress_data[download_id] = {
                'progress': '100',
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

@app.route('/download', methods=['POST'])
def download():
    data = request.json
    url = data['url']
    format_id = data['format_id']
    download_id = str(uuid.uuid4())
    progress_data[download_id] = {'progress': '0', 'status': 'queued'}
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
