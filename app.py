#!/usr/bin/env python3
"""
YouTube Video Downloader - Single File Version for PythonAnywhere
A Flask web application for downloading YouTube videos using yt-dlp
"""

import os
import time
import uuid
import logging
import threading
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Flask imports
from flask import Flask, render_template_string, request, jsonify, abort, session

# YouTube download library
import yt_dlp
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "youtube-downloader-secret-key-change-in-production")

# Global variables for tracking downloads
download_progress = {}
download_results = {}

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube Video Downloader</title>
    <link href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .hero-section {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 4rem 0;
            margin-bottom: 2rem;
        }
        .card {
            border: none;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .progress-container {
            display: none;
            margin-top: 1rem;
        }
        .format-option {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.5rem;
            border: 1px solid var(--bs-border-color);
            border-radius: 0.375rem;
            margin-bottom: 0.5rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        .format-option:hover {
            background-color: var(--bs-secondary-bg);
            border-color: var(--bs-primary);
        }
        .format-option.selected {
            background-color: var(--bs-primary-bg-subtle);
            border-color: var(--bs-primary);
        }
        .video-info {
            display: none;
            margin-top: 1rem;
        }
        .download-section {
            display: none;
            margin-top: 1rem;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
        }
        .btn-primary:hover {
            background: linear-gradient(135deg, #5a6fd8 0%, #6a4190 100%);
        }
    </style>
</head>
<body>
    <div class="hero-section">
        <div class="container text-center">
            <h1 class="display-4 mb-3">
                <i class="fab fa-youtube text-danger"></i>
                YouTube Downloader
            </h1>
            <p class="lead">Download YouTube videos in various formats and qualities up to 4K</p>
        </div>
    </div>

    <div class="container">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">
                            <i class="fas fa-link"></i>
                            Enter YouTube URL
                        </h5>
                        
                        <form id="urlForm">
                            <div class="mb-3">
                                <input type="url" 
                                       class="form-control" 
                                       id="videoUrl" 
                                       placeholder="https://www.youtube.com/watch?v=..."
                                       required>
                            </div>
                            <button type="submit" class="btn btn-primary">
                                <i class="fas fa-search"></i>
                                Get Video Info
                            </button>
                        </form>

                        <div id="videoInfo" class="video-info">
                            <hr>
                            <div id="videoDetails"></div>
                            <div id="formatsList"></div>
                        </div>

                        <div id="downloadSection" class="download-section">
                            <hr>
                            <button id="downloadBtn" class="btn btn-success">
                                <i class="fas fa-download"></i>
                                Download Selected Format
                            </button>
                        </div>

                        <div id="progressContainer" class="progress-container">
                            <hr>
                            <h6>Download Progress</h6>
                            <div class="progress mb-2">
                                <div id="progressBar" class="progress-bar" role="progressbar" style="width: 0%"></div>
                            </div>
                            <div id="progressText" class="text-muted small"></div>
                            <div id="downloadResult" class="mt-3"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        class YouTubeDownloader {
            constructor() {
                this.selectedFormat = null;
                this.currentDownloadId = null;
                this.initializeEventListeners();
            }

            initializeEventListeners() {
                document.getElementById('urlForm').addEventListener('submit', (e) => {
                    e.preventDefault();
                    this.getVideoInfo();
                });

                document.getElementById('downloadBtn').addEventListener('click', () => {
                    this.startDownload();
                });
            }

            async getVideoInfo() {
                const url = document.getElementById('videoUrl').value;
                if (!url) return;

                try {
                    const response = await fetch('/get_info', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ url: url })
                    });

                    const data = await response.json();
                    
                    if (data.error) {
                        alert('Error: ' + data.error);
                        return;
                    }

                    this.displayVideoInfo(data);
                } catch (error) {
                    alert('Error fetching video info: ' + error.message);
                }
            }

            displayVideoInfo(data) {
                const videoInfo = document.getElementById('videoInfo');
                const videoDetails = document.getElementById('videoDetails');
                const formatsList = document.getElementById('formatsList');

                // Display video details
                videoDetails.innerHTML = `
                    <div class="row mb-3">
                        <div class="col-md-4">
                            <img src="${data.thumbnail}" class="img-fluid rounded" alt="Video thumbnail">
                        </div>
                        <div class="col-md-8">
                            <h6>${data.title}</h6>
                            <p class="text-muted small">
                                <i class="fas fa-user"></i> ${data.uploader} | 
                                <i class="fas fa-clock"></i> ${data.duration} | 
                                <i class="fas fa-eye"></i> ${data.view_count} views
                            </p>
                        </div>
                    </div>
                `;

                // Display formats
                let formatsHtml = '<h6>Available Formats:</h6>';
                data.formats.forEach(format => {
                    const quality = format.quality || 'Unknown';
                    const filesize = format.filesize ? this.formatFileSize(format.filesize) : 'Unknown size';
                    
                    formatsHtml += `
                        <div class="format-option" data-format-id="${format.format_id}">
                            <div>
                                <strong>${quality}</strong>
                                <small class="text-muted d-block">${format.ext.toUpperCase()} - ${filesize}</small>
                            </div>
                            <div class="text-end">
                                <i class="fas fa-download"></i>
                            </div>
                        </div>
                    `;
                });

                formatsList.innerHTML = formatsHtml;

                // Add click handlers for format selection
                document.querySelectorAll('.format-option').forEach(option => {
                    option.addEventListener('click', () => {
                        document.querySelectorAll('.format-option').forEach(o => o.classList.remove('selected'));
                        option.classList.add('selected');
                        this.selectedFormat = option.dataset.formatId;
                        document.getElementById('downloadSection').style.display = 'block';
                    });
                });

                videoInfo.style.display = 'block';
            }

            async startDownload() {
                if (!this.selectedFormat) {
                    alert('Please select a format first');
                    return;
                }

                const url = document.getElementById('videoUrl').value;
                
                try {
                    const response = await fetch('/start_download', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ 
                            url: url, 
                            format_id: this.selectedFormat 
                        })
                    });

                    const data = await response.json();
                    
                    if (data.error) {
                        alert('Error: ' + data.error);
                        return;
                    }

                    this.currentDownloadId = data.download_id;
                    this.showProgress();
                    this.pollProgress();
                } catch (error) {
                    alert('Error starting download: ' + error.message);
                }
            }

            showProgress() {
                document.getElementById('progressContainer').style.display = 'block';
                document.getElementById('progressBar').style.width = '0%';
                document.getElementById('progressText').textContent = 'Starting download...';
            }

            async pollProgress() {
                if (!this.currentDownloadId) return;

                try {
                    const response = await fetch(`/progress/${this.currentDownloadId}`);
                    const data = await response.json();

                    const progressBar = document.getElementById('progressBar');
                    const progressText = document.getElementById('progressText');
                    const downloadResult = document.getElementById('downloadResult');

                    if (data.status === 'downloading') {
                        const percent = Math.round(data.progress || 0);
                        progressBar.style.width = percent + '%';
                        progressText.textContent = `Downloading... ${percent}% (${data.speed || 'Unknown speed'})`;
                        
                        setTimeout(() => this.pollProgress(), 1000);
                    } else if (data.status === 'completed') {
                        progressBar.style.width = '100%';
                        progressText.textContent = 'Download completed!';
                        
                        downloadResult.innerHTML = `
                            <div class="alert alert-success">
                                <i class="fas fa-check-circle"></i>
                                Download completed successfully!
                                <br>
                                <a href="/download/${this.currentDownloadId}" class="btn btn-success btn-sm mt-2">
                                    <i class="fas fa-download"></i> Download File
                                </a>
                            </div>
                        `;
                    } else if (data.status === 'error') {
                        progressBar.classList.add('bg-danger');
                        progressText.textContent = 'Download failed: ' + (data.error || 'Unknown error');
                        
                        downloadResult.innerHTML = `
                            <div class="alert alert-danger">
                                <i class="fas fa-exclamation-circle"></i>
                                Download failed: ${data.error || 'Unknown error'}
                            </div>
                        `;
                    } else {
                        setTimeout(() => this.pollProgress(), 1000);
                    }
                } catch (error) {
                    console.error('Error polling progress:', error);
                    setTimeout(() => this.pollProgress(), 2000);
                }
            }

            formatFileSize(bytes) {
                if (!bytes) return 'Unknown size';
                const sizes = ['Bytes', 'KB', 'MB', 'GB'];
                if (bytes === 0) return '0 Bytes';
                const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)));
                return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
            }
        }

        // Initialize the downloader when page loads
        document.addEventListener('DOMContentLoaded', () => {
            new YouTubeDownloader();
        });
    </script>
</body>
</html>
"""

def is_valid_youtube_url(url):
    """Check if the URL is a valid YouTube URL."""
    try:
        parsed = urlparse(url)
        if parsed.hostname in ['www.youtube.com', 'youtube.com', 'youtu.be']:
            if parsed.hostname == 'youtu.be':
                return bool(parsed.path.strip('/'))
            else:
                return 'v' in parse_qs(parsed.query)
        return False
    except:
        return False

def download_video_thread(download_id, url, format_id):
    """Download video in a separate thread."""
    try:
        download_progress[download_id] = {
            'status': 'downloading',
            'progress': 0,
            'speed': '',
            'eta': ''
        }
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                progress_info = {
                    'status': 'downloading',
                    'progress': 0,
                    'speed': d.get('_speed_str', ''),
                    'eta': d.get('_eta_str', '')
                }
                
                if d.get('total_bytes'):
                    progress_info['progress'] = (d.get('downloaded_bytes', 0) / d['total_bytes']) * 100
                elif d.get('total_bytes_estimate'):
                    progress_info['progress'] = (d.get('downloaded_bytes', 0) / d['total_bytes_estimate']) * 100
                
                download_progress[download_id] = progress_info
                
        # Configure yt-dlp options
        ydl_opts = {
            'format': format_id,
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
            'retries': 5,
            'fragment_retries': 5,
            'skip_unavailable_fragments': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info first
            info = ydl.extract_info(url, download=False)
            
            # Find the selected format
            selected_format = None
            for fmt in info.get('formats', []):
                if fmt.get('format_id') == format_id:
                    selected_format = fmt
                    break
            
            if not selected_format:
                # Fallback to best available format
                formats = [f for f in info.get('formats', []) if f.get('vcodec') != 'none' and f.get('url')]
                if formats:
                    selected_format = max(formats, key=lambda x: x.get('height', 0))
                    logger.info(f"Using fallback format: {selected_format.get('format_id')}")
            
            if not selected_format:
                raise Exception("No suitable format found")
            
            # Prepare result
            title = info.get('title', 'Unknown')
            ext = selected_format.get('ext', 'mp4')
            filename = f"{title}.{ext}".replace('/', '_').replace('\\', '_')
            
            download_results[download_id] = {
                'status': 'completed',
                'filename': filename,
                'title': title,
                'original_url': url,
                'format_id': format_id,
                'direct_url': selected_format.get('url')
            }
            
            download_progress[download_id] = {
                'status': 'completed',
                'progress': 100
            }
            
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        download_progress[download_id] = {
            'status': 'error',
            'error': str(e)
        }

@app.route('/')
def index():
    """Main page."""
    return render_template_string(HTML_TEMPLATE)

@app.route('/get_info', methods=['POST'])
def get_video_info():
    """Get video information and available formats."""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
            
        if not is_valid_youtube_url(url):
            return jsonify({'error': 'Invalid YouTube URL'}), 400
        
        # Configure yt-dlp
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'best',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Extract video information
            video_info = {
                'title': info.get('title', 'Unknown'),
                'uploader': info.get('uploader', 'Unknown'),
                'duration': info.get('duration_string', 'Unknown'),
                'view_count': f"{info.get('view_count', 0):,}" if info.get('view_count') else 'Unknown',
                'thumbnail': info.get('thumbnail', ''),
                'formats': []
            }
            
            # Process formats
            seen_formats = set()
            for fmt in info.get('formats', []):
                if fmt.get('vcodec') == 'none':  # Skip audio-only
                    continue
                    
                format_id = fmt.get('format_id')
                height = fmt.get('height', 0)
                
                if format_id and height and format_id not in seen_formats:
                    quality = f"{height}p"
                    if height >= 2160:
                        quality = "4K (2160p)"
                    elif height >= 1440:
                        quality = "1440p (2K)"
                    elif height >= 1080:
                        quality = "1080p (Full HD)"
                    elif height >= 720:
                        quality = "720p (HD)"
                    elif height >= 480:
                        quality = "480p"
                    elif height >= 360:
                        quality = "360p"
                    else:
                        quality = f"{height}p"
                    
                    video_info['formats'].append({
                        'format_id': format_id,
                        'quality': quality,
                        'ext': fmt.get('ext', 'mp4'),
                        'filesize': fmt.get('filesize'),
                        'height': height
                    })
                    
                    seen_formats.add(format_id)
            
            # Sort formats by quality (highest first)
            video_info['formats'].sort(key=lambda x: x['height'], reverse=True)
            
            return jsonify(video_info)
            
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/start_download', methods=['POST'])
def start_download():
    """Start downloading a video."""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        format_id = data.get('format_id', '')
        
        if not url or not format_id:
            return jsonify({'error': 'URL and format_id are required'}), 400
            
        if not is_valid_youtube_url(url):
            return jsonify({'error': 'Invalid YouTube URL'}), 400
        
        # Generate unique download ID
        download_id = str(uuid.uuid4())
        
        # Start download in separate thread
        thread = threading.Thread(
            target=download_video_thread,
            args=(download_id, url, format_id)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({'download_id': download_id})
        
    except Exception as e:
        logger.error(f"Error starting download: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/progress/<download_id>')
def get_progress(download_id):
    """Get download progress."""
    try:
        progress = download_progress.get(download_id, {'status': 'not_found'})
        
        # If completed, include result info
        if progress.get('status') == 'completed' and download_id in download_results:
            progress['result'] = download_results[download_id]
        
        return jsonify(progress)
        
    except Exception as e:
        logger.error(f"Error getting progress: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)})

@app.route('/download/<download_id>')
def download_file(download_id):
    """Download video file."""
    try:
        if download_id not in download_results:
            abort(404)
            
        result = download_results[download_id]
        if result['status'] != 'completed':
            abort(404)
        
        # Get the direct URL
        direct_url = result.get('direct_url')
        filename = result['filename']
        
        if not direct_url:
            abort(404)
        
        # Stream directly from the URL
        try:
            response = requests.get(direct_url, stream=True, timeout=30)
            response.raise_for_status()
            
            def generate():
                for chunk in response.iter_content(chunk_size=16384):
                    if chunk:
                        yield chunk
            
            return app.response_class(
                generate(),
                mimetype='application/octet-stream',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"',
                    'Content-Length': response.headers.get('Content-Length', '0'),
                    'Cache-Control': 'no-cache'
                }
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Streaming failed: {e}")
            abort(500)
        
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        abort(500)

if __name__ == '__main__':
    # For local development
    app.run(debug=True, host='0.0.0.0', port=5000)
