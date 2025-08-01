import subprocess
import threading
import os
import sys
import time
from datetime import datetime
import pytz
import queue
import uuid

class StreamManager:
    def __init__(self):
        self.sessions = {}  # Akan menyimpan semua sesi, key-nya adalah session_id

    def _get_gmt7_now(self):
        return datetime.now(pytz.timezone("Asia/Bangkok"))

    def add_session(self, config=None):
        session_id = str(uuid.uuid4()) # ID unik untuk setiap sesi
        
        # Data default untuk sesi baru
        self.sessions[session_id] = {
            'id': session_id,
            'title': config.get('title', f"Stream {len(self.sessions) + 1}"),
            'stream_key': config.get('stream_key', ''),
            'video_path': config.get('video_path', ''),
            'duration': config.get('duration', '00:00:00'),
            'schedule_time': config.get('schedule_time', None),
            'status': 'Idle', # Status: Idle, Scheduled, LIVE, Stopped, Error
            'ffmpeg_process': None,
            'start_time': None,
            'log_queue': queue.Queue(),
            'last_log': 'No logs yet.'
        }
        return session_id

    def remove_session(self, session_id):
        if session_id in self.sessions:
            self.stop_stream(session_id)
            del self.sessions[session_id]
            return True
        return False

    def get_session_status(self, session_id):
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        
        # Proses log dari queue
        try:
            while True:
                line = session['log_queue'].get_nowait()
                if "frame=" in line or "bitrate=" in line:
                    session['last_log'] = line.strip()
        except queue.Empty:
            pass

        live_duration = "00:00:00"
        if session['status'] == 'LIVE' and session['start_time']:
            elapsed = int(time.time() - session['start_time'])
            h, rem = divmod(elapsed, 3600)
            m, s = divmod(rem, 60)
            live_duration = f"{h:02}:{m:02}:{s:02}"
            
        return {
            'id': session['id'],
            'title': session['title'],
            'status': session['status'],
            'live_duration': live_duration,
            'last_log': session['last_log']
        }

    def get_all_statuses(self):
        return {sid: self.get_session_status(sid) for sid in self.sessions}

    def update_session_config(self, session_id, config):
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session['title'] = config.get('title', session['title'])
            session['stream_key'] = config.get('stream_key', session['stream_key'])
            session['video_path'] = config.get('video_path', session['video_path'])
            session['duration'] = config.get('duration', session['duration'])
            
            # Handling schedule time dari input baru
            schedule_datetime_str = config.get('schedule_datetime')
            if schedule_datetime_str:
                # Format dari datetime-local adalah 'YYYY-MM-DDTHH:MM'
                # Kita ubah ke format yang diterima fungsi schedule '%Y-%m-%d %H:%M'
                formatted_schedule_str = schedule_datetime_str.replace('T', ' ')
                self.schedule_stream(session_id, formatted_schedule_str)
            return True
        return False

    def start_stream(self, session_id):
        if session_id not in self.sessions:
            return False
        
        session = self.sessions[session_id]
        stream_key = session['stream_key']
        video_file = session['video_path']

        if not stream_key or not video_file or not os.path.exists(video_file):
            session['status'] = 'Error'
            session['last_log'] = "Error: Stream Key or Video Path is invalid."
            return False

        # Hentikan proses lama jika ada
        if session['ffmpeg_process']:
            self.stop_stream(session_id)
            
        rtmp_url = f"rtmp://a.rtmp.youtube.com/live2/{stream_key}"
        ffmpeg_cmd = [
            "ffmpeg", "-stream_loop", "-1", "-re", "-i", video_file,
            "-c", "copy", "-f", "flv", "-reconnect", "1", "-reconnect_streamed", "1", 
            "-reconnect_delay_max", "10", rtmp_url
        ]

        try:
            session['status'] = 'LIVE'
            session['start_time'] = time.time()
            session['ffmpeg_process'] = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                bufsize=1,
                text=True
            )

            # Thread untuk memantau log FFmpeg
            threading.Thread(target=self._enqueue_log_output, args=(session_id,), daemon=True).start()

            # Thread untuk memantau durasi jika diset
            duration_str = session.get('duration', '00:00:00')
            if duration_str and duration_str != '00:00:00':
                h, m, s = map(int, duration_str.split(':'))
                duration_seconds = h*3600 + m*60 + s
                if duration_seconds > 0:
                    threading.Thread(target=self._monitor_duration, args=(session_id, duration_seconds), daemon=True).start()
                    
        except Exception as e:
            session['status'] = 'Error'
            session['last_log'] = f"Failed to start ffmpeg: {e}"
            return False
        
        return True

    def _enqueue_log_output(self, session_id):
        session = self.sessions.get(session_id)
        if not session or not session['ffmpeg_process']:
            return
        
        pipe = session['ffmpeg_process'].stderr
        for line in iter(pipe.readline, ''):
            if session['status'] != 'LIVE':
                break
            session['log_queue'].put(line)
        pipe.close()

    def _monitor_duration(self, session_id, duration_seconds):
        session = self.sessions.get(session_id)
        if not session: return
        
        time.sleep(duration_seconds)

        # Cek lagi apakah sesi masih ada dan berjalan sebelum menghentikannya
        if session_id in self.sessions and self.sessions[session_id]['status'] == 'LIVE':
             self.stop_stream(session_id)

    def schedule_stream(self, session_id, schedule_datetime_str):
        session = self.sessions.get(session_id)
        if not session: return False
        
        try:
            gmt7 = pytz.timezone("Asia/Bangkok")
            scheduled_time = datetime.strptime(schedule_datetime_str, "%Y-%m-%d %H:%M")
            scheduled_time = gmt7.localize(scheduled_time)
            
            now = self._get_gmt7_now()
            wait_time = (scheduled_time - now).total_seconds()
            
            if wait_time < 0:
                session['status'] = 'Error'
                session['last_log'] = 'Error: Schedule time is in the past.'
                return False

            session['status'] = 'Scheduled'
            session['schedule_time'] = scheduled_time.strftime("%Y-%m-%d %H:%M:%S %Z")
            
            def delayed_start():
                time.sleep(wait_time)
                # Cek lagi jika sesi masih ada dan terjadwal
                if session_id in self.sessions and self.sessions[session_id]['status'] == 'Scheduled':
                    self.start_stream(session_id)

            threading.Thread(target=delayed_start, daemon=True).start()
            return True
        except Exception as e:
            session['status'] = 'Error'
            session['last_log'] = f"Error parsing schedule time: {e}"
            return False

    def stop_stream(self, session_id):
        if session_id in self.sessions and self.sessions[session_id]['ffmpeg_process']:
            session = self.sessions[session_id]
            session['status'] = 'Stopped'
            try:
                session['ffmpeg_process'].terminate()
                session['ffmpeg_process'].wait(timeout=5)
            except subprocess.TimeoutExpired:
                session['ffmpeg_process'].kill()
            except Exception:
                pass # Proses mungkin sudah mati
            
            session['ffmpeg_process'] = None
            session['start_time'] = None
            return True
        return False