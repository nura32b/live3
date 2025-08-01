document.addEventListener("DOMContentLoaded", function () {
  function updateVPSClock() {
    const clockElement = document.getElementById("vps-clock");
    if (clockElement) {
      const now = new Date();
      const options = {
        timeZone: "Asia/Jakarta",
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      };
      const formatter = new Intl.DateTimeFormat("id-ID", options);
      clockElement.textContent = formatter.format(now);
    }
  }

  // ======================================================================
  // BAGIAN BARU: Fungsi untuk update statistik sistem
  // ======================================================================
  function updateSystemStats() {
    fetch("/api/system_stats")
      .then((response) => response.json())
      .then((data) => {
        document.getElementById(
          "cpu-usage"
        ).textContent = `${data.cpu_percent}%`;
        document.getElementById(
          "ram-usage"
        ).textContent = `${data.ram_percent}% (${data.ram_used_gb} / ${data.ram_total_gb} GB)`;
        document.getElementById(
          "upload-speed"
        ).textContent = `${data.upload_speed_mbps} Mbps`;
        document.getElementById(
          "download-speed"
        ).textContent = `${data.download_speed_mbps} Mbps`;
      })
      .catch((error) => console.error("Error fetching system stats:", error));
  }
  // ======================================================================
  // AKHIR BAGIAN BARU
  // ======================================================================

  function updateSessionStatuses() {
    fetch("/api/status")
      .then((response) => response.json())
      .then((data) => {
        for (const sessionId in data) {
          const sessionData = data[sessionId];
          if (!sessionData) continue;

          const indicator = document.getElementById(`indicator-${sessionId}`);
          const statusText = document.getElementById(
            `status-text-${sessionId}`
          );
          const durationText = document.getElementById(`duration-${sessionId}`);
          const logText = document.getElementById(`log-${sessionId}`);
          const scheduleText = document.getElementById(
            `schedule-time-${sessionId}`
          );

          // BARU: Update dropdown video
          const videoSelector = document.getElementById(
            `video_file_selector-${sessionId}`
          );
          if (videoSelector) {
            const currentVal = videoSelector.value;
            // Hapus opsi lama, sisakan yang pertama
            while (videoSelector.options.length > 1) {
              videoSelector.remove(1);
            }
            sessionData.available_videos.forEach((videoFile) => {
              const option = new Option(videoFile, videoFile);
              videoSelector.add(option);
            });
            videoSelector.value = currentVal;
          }

          if (indicator) {
            indicator.className = `status-indicator status-${sessionData.status}`;
          }
          if (statusText) {
            statusText.textContent = sessionData.status;
          }
          if (scheduleText) {
            if (
              sessionData.status === "Scheduled" &&
              sessionData.schedule_time
            ) {
              scheduleText.textContent = `(${sessionData.schedule_time})`;
              scheduleText.style.display = "inline";
            } else {
              scheduleText.style.display = "none";
            }
          }
          if (durationText) {
            durationText.textContent = `Durasi Live: ${sessionData.live_duration}`;
          }
          if (logText) {
            logText.textContent = `Log: ${sessionData.last_log}`;
          }
        }
      })
      .catch((error) => console.error("Error fetching session status:", error));
  }

  // Panggil semua fungsi update secara berkala
  setInterval(() => {
    updateVPSClock();
    updateSystemStats();
    updateSessionStatuses();
  }, 3000); // Update setiap 3 detik

  // Panggil sekali saat halaman dimuat
  updateVPSClock();
  updateSystemStats();
  updateSessionStatuses();
});
