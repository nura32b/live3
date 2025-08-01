#!/bin/bash

# Hentikan skrip jika ada perintah yang gagal
set -e

# --- Konfigurasi ---
PROJECT_DIR="/var/www/stream_app"
REPO_URL="https://github.com/NAMA_ANDA/NAMA_REPO_ANDA.git" # GANTI DENGAN URL REPO ANDA
USER="root" # Ganti jika menggunakan user lain

echo "--- Memulai Instalasi Aplikasi Streaming ---"

# --- 1. Instalasi Dependensi Sistem ---
echo "--> Mengupdate sistem dan menginstal dependensi (Nginx, Python, Git, FFmpeg)..."
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv nginx ffmpeg git

# --- 2. Kloning Proyek dari GitHub ---
echo "--> Menghapus direktori lama dan mengkloning dari GitHub..."
if [ -d "$PROJECT_DIR" ]; then
    sudo rm -rf "$PROJECT_DIR"
fi
sudo git clone "$REPO_URL" "$PROJECT_DIR"

# --- 3. Setup Virtual Environment & Dependensi Python ---
echo "--> Membuat virtual environment..."
sudo python3 -m venv "$PROJECT_DIR/venv"

echo "--> Menginstal dependensi Python dari requirements.txt..."
sudo "$PROJECT_DIR/venv/bin/pip" install --upgrade pip
sudo "$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

# --- 4. Atur Kepemilikan dan Izin Folder ---
echo "--> Mengatur izin folder..."
sudo chown -R $USER:www-data "$PROJECT_DIR"
sudo chmod -R 775 "$PROJECT_DIR"

# --- 5. Setup Gunicorn Service ---
echo "--> Membuat file service Gunicorn..."
sudo bash -c "cat > /etc/systemd/system/stream_app.service" <<EOF
[Unit]
Description=Gunicorn instance to serve stream_app
After=network.target

[Service]
User=$USER
Group=www-data
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin"
ExecStart=$PROJECT_DIR/venv/bin/gunicorn --workers 3 --bind unix:stream_app.sock -m 007 app:app

[Install]
WantedBy=multi-user.target
EOF

# --- 6. Setup Nginx ---
echo "--> Membuat konfigurasi Nginx..."
sudo bash -c "cat > /etc/nginx/sites-available/stream_app" <<EOF
server {
    listen 80;
    server_name _; # Menangkap semua domain/IP

    location /static {
        alias $PROJECT_DIR/static;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:$PROJECT_DIR/stream_app.sock;
    }
}
EOF

echo "--> Mengaktifkan konfigurasi Nginx..."
# Hapus link lama jika ada untuk menghindari error
sudo rm -f /etc/nginx/sites-enabled/stream_app
sudo ln -s /etc/nginx/sites-available/stream_app /etc/nginx/sites-enabled

# Hapus konfigurasi default Nginx jika ada
if [ -f /etc/nginx/sites-enabled/default ]; then
    sudo rm /etc/nginx/sites-enabled/default
fi

# --- 7. Jalankan Semua Service ---
echo "--> Menjalankan service Gunicorn dan Nginx..."
sudo systemctl daemon-reload
sudo systemctl restart stream_app
sudo systemctl enable stream_app
sudo systemctl restart nginx

# --- 8. Konfigurasi Firewall ---
echo "--> Mengizinkan trafik Nginx melalui firewall..."
sudo ufw allow 'Nginx Full'

echo "--- ✅ Instalasi Selesai! ---"
echo "Aplikasi Anda seharusnya sudah bisa diakses melalui IP VPS Anda."