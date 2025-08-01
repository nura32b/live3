from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os
import json
import time
from stream_manager import StreamManager
import psutil # <- BARU: Import psutil

# Konfigurasi
UPLOAD_FOLDER = 'videos'
CONFIG_FOLDER = 'configs'
ALLOWED_EXTENSIONS = {'mp4', 'mov', 'mkv', 'flv'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CONFIG_FOLDER'] = CONFIG_FOLDER
app.secret_key = 'kunci-rahasia-untuk-flash-message' # <- BARU: Diperlukan untuk flash message

# Buat satu instance StreamManager untuk seluruh aplikasi
stream_manager = StreamManager()

# ======================================================================
# BAGIAN BARU: Untuk monitoring sistem
# ======================================================================
last_net_io = psutil.net_io_counters()
last_time = time.time()

@app.route('/api/system_stats')
def api_system_stats():
    global last_net_io, last_time

    # 1. CPU Usage
    cpu_percent = psutil.cpu_percent(interval=None)

    # 2. RAM Usage
    ram = psutil.virtual_memory()
    ram_total_gb = ram.total / (1024**3)
    ram_used_gb = ram.used / (1024**3)
    ram_percent = ram.percent

    # 3. Network Speed
    current_net_io = psutil.net_io_counters()
    current_time = time.time()
    
    time_diff = current_time - last_time
    bytes_sent_diff = current_net_io.bytes_sent - last_net_io.bytes_sent
    bytes_recv_diff = current_net_io.bytes_recv - last_net_io.bytes_recv

    # Hindari pembagian dengan nol jika interval terlalu cepat
    if time_diff == 0:
        upload_speed_mbps = 0
        download_speed_mbps = 0
    else:
        # Konversi bytes per detik ke Megabits per detik (Mbps)
        upload_speed_mbps = (bytes_sent_diff * 8 / time_diff) / (1024**2)
        download_speed_mbps = (bytes_recv_diff * 8 / time_diff) / (1024**2)

    # Simpan state saat ini untuk perhitungan berikutnya
    last_net_io = current_net_io
    last_time = current_time
    
    return jsonify({
        'cpu_percent': f"{cpu_percent:.1f}",
        'ram_percent': f"{ram_percent:.1f}",
        'ram_used_gb': f"{ram_used_gb:.2f}",
        'ram_total_gb': f"{ram_total_gb:.2f}",
        'upload_speed_mbps': f"{upload_speed_mbps:.2f}",
        'download_speed_mbps': f"{download_speed_mbps:.2f}"
    })
# ======================================================================
# AKHIR BAGIAN BARU
# ======================================================================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html', sessions=stream_manager.sessions)

# ======================================================================
# BAGIAN BARU: Route untuk manajemen file video
# ======================================================================
@app.route('/files')
def manage_files():
    try:
        video_files = [f for f in os.listdir(UPLOAD_FOLDER) if os.path.isfile(os.path.join(UPLOAD_FOLDER, f))]
    except FileNotFoundError:
        video_files = []
    return render_template('files.html', files=video_files)

@app.route('/files/upload', methods=['POST'])
def upload_file():
    if 'video_file' not in request.files:
        flash('Tidak ada file yang dipilih', 'danger')
        return redirect(url_for('manage_files'))
    
    file = request.files['video_file']
    if file.filename == '':
        flash('Tidak ada file yang dipilih', 'danger')
        return redirect(url_for('manage_files'))
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        flash(f"File '{filename}' berhasil diupload.", 'success')
    else:
        flash('Format file tidak diizinkan!', 'danger')
        
    return redirect(url_for('manage_files'))

@app.route('/files/delete/<filename>', methods=['POST'])
def delete_file(filename):
    # Keamanan dasar untuk mencegah penghapusan di luar folder videos
    safe_filename = secure_filename(filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
    
    if os.path.exists(file_path):
        os.remove(file_path)
        flash(f"File '{safe_filename}' berhasil dihapus.", 'success')
    else:
        flash('File tidak ditemukan.', 'danger')
        
    return redirect(url_for('manage_files'))
# ======================================================================
# AKHIR BAGIAN BARU
# ======================================================================

# ... (sisa kode app.py Anda yang lain tidak berubah) ...
@app.route('/add_session', methods=['POST'])
def add_session():
    stream_manager.add_session()
    return redirect(url_for('index'))

@app.route('/remove_session/<session_id>', methods=['POST'])
def remove_session(session_id):
    stream_manager.remove_session(session_id)
    return redirect(url_for('index'))

@app.route('/update_session/<session_id>', methods=['POST'])
def update_session(session_id):
    video_path = stream_manager.sessions[session_id].get('video_path', '')
    
    # Perubahan di sini: Hanya update video path jika nama file dipilih dari dropdown
    # Upload file sekarang ditangani di halaman manajemen file
    selected_video = request.form.get('video_file_selector')
    if selected_video:
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], selected_video)

    schedule_datetime_str = request.form.get('schedule_datetime')

    config = {
        'title': request.form.get('title'),
        'stream_key': request.form.get('stream_key'),
        'duration': request.form.get('duration'),
        'schedule_datetime': schedule_datetime_str,
        'video_path': video_path
    }
    stream_manager.update_session_config(session_id, config)
    return redirect(url_for('index'))

@app.route('/start_stream/<session_id>', methods=['POST'])
def start_stream(session_id):
    stream_manager.start_stream(session_id)
    return redirect(url_for('index'))

@app.route('/stop_stream/<session_id>', methods=['POST'])
def stop_stream(session_id):
    stream_manager.stop_stream(session_id)
    return redirect(url_for('index'))

@app.route('/api/status')
def api_status():
    # BARU: Sertakan daftar video yang tersedia untuk dropdown
    available_videos = [f for f in os.listdir(UPLOAD_FOLDER) if os.path.isfile(os.path.join(UPLOAD_FOLDER, f))]
    statuses = stream_manager.get_all_statuses()
    for sid in statuses:
        statuses[sid]['available_videos'] = available_videos
    return jsonify(statuses)

@app.route('/save_config', methods=['POST'])
def save_config():
    file_path = os.path.join(app.config['CONFIG_FOLDER'], "config.json")
    data_to_save = []
    for sid, session in stream_manager.sessions.items():
        conf = {k: v for k, v in session.items() if k not in ['ffmpeg_process', 'log_queue', 'start_time']}
        data_to_save.append(conf)

    with open(file_path, 'w') as f:
        json.dump(data_to_save, f, indent=4)
    flash('Konfigurasi berhasil disimpan.', 'success')
    return redirect(url_for('index'))

@app.route('/load_config', methods=['POST'])
def load_config():
    file_path = os.path.join(app.config['CONFIG_FOLDER'], "config.json")
    if os.path.exists(file_path):
        for sid in list(stream_manager.sessions.keys()):
            stream_manager.remove_session(sid)
        with open(file_path, 'r') as f:
            configs = json.load(f)
            for conf in configs:
                new_sid = stream_manager.add_session()
                stream_manager.update_session_config(new_sid, conf)
        flash('Konfigurasi berhasil dimuat.', 'success')
    else:
        flash('File konfigurasi tidak ditemukan.', 'warning')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)