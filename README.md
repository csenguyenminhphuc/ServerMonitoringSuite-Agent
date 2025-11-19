# ServerMonitoringSuite-Agent

A comprehensive server monitoring system (Hệ thống giám sát máy chủ toàn diện) that collects and reports system metrics (thu thập và báo cáo các chỉ số hệ thống) including CPU, RAM, GPU, Disk, and Network with InfluxDB integration and Telegram bot notifications (với tích hợp InfluxDB và thông báo qua Telegram bot).

## 📋 Table of Contents (Mục Lục)

- [Features (Tính Năng)](#-features-tính-năng)
- [System Requirements (Yêu Cầu Hệ Thống)](#️-system-requirements-yêu-cầu-hệ-thống)
- [Installation (Cài Đặt)](#-installation-cài-đặt)
- [Configuration (Cấu Hình)](#️-configuration-cấu-hình)
- [Usage (Sử Dụng)](#-usage-sử-dụng)
- [API Endpoints](#-api-endpoints)
- [Telegram Bot Commands (Lệnh Bot)](#-telegram-bot-commands-lệnh-bot)
- [Alert System (Hệ Thống Cảnh Báo)](#-alert-system-hệ-thống-cảnh-báo)
- [Cloudflare Tunnel Setup (Cài Đặt Tunnel)](#️-cloudflare-tunnel-setup-cài-đặt-tunnel)
- [Administrator Information (Thông Tin Quản Trị Viên)](#-administrator-information-thông-tin-quản-trị-viên)
- [License (Giấy Phép)](#-license-giấy-phép)

## ✨ Features (Tính Năng)

- **Real-time System Monitoring (Giám sát hệ thống thời gian thực)**: Track CPU, RAM, GPU (NVIDIA), Disk, and Network metrics (Theo dõi các chỉ số CPU, RAM, GPU, Disk và Network)
- **InfluxDB Integration (Tích hợp InfluxDB)**: Automatic metrics collection and storage (Thu thập và lưu trữ metrics tự động)
- **Telegram Bot (Bot Telegram)**: Remote monitoring and control via Telegram (Giám sát và điều khiển từ xa qua Telegram)
- **Alert System (Hệ thống cảnh báo)**: Automated threshold-based alerts sent to Telegram (Cảnh báo tự động dựa trên ngưỡng)
- **REST API**: HTTP endpoints for metrics retrieval (Các endpoint HTTP để truy xuất metrics)
- **GPU Support (Hỗ trợ GPU)**: Comprehensive NVIDIA GPU monitoring via nvidia-smi (Giám sát GPU NVIDIA toàn diện)
- **Scheduled Reports (Báo cáo định kỳ)**: Automatic status updates at configurable intervals (Cập nhật trạng thái tự động)
- **Multi-user Support (Hỗ trợ nhiều người dùng)**: User authorization for Telegram bot commands (Phân quyền người dùng)
- **Cloudflare Tunnel**: Secure remote access setup script (Script cài đặt truy cập từ xa an toàn)

## 🖥️ System Requirements (Yêu Cầu Hệ Thống)

- **Operating System (Hệ điều hành)**: Linux (Ubuntu/Debian recommended - khuyến nghị)
- **Python**: 3.8 or higher (trở lên)
- **Hardware (Phần cứng)**: 
  - CPU with at least 2 cores (CPU tối thiểu 2 cores)
  - 2GB RAM minimum (RAM tối thiểu 2GB)
  - Optional (Tùy chọn): NVIDIA GPU with nvidia-smi installed (GPU NVIDIA với nvidia-smi đã cài đặt)
- **Network (Mạng)**: Internet connection for InfluxDB and Telegram (Kết nối Internet cho InfluxDB và Telegram)

## 📦 Installation (Cài Đặt)

### 1. Clone the Repository (Clone Kho Mã Nguồn)

```bash
git clone https://github.com/csenguyenminhphuc/ServerMonitoringSuite-Agent.git
cd ServerMonitoringSuite-Agent
```

### 2. Install Python Dependencies (Cài Đặt Các Thư Viện Python)

```bash
cd metrics
pip install -r requirements.txt
```

### 3. Install NVIDIA Drivers (Cài Đặt NVIDIA Drivers) - Optional (Tùy chọn)

For GPU monitoring (Cho giám sát GPU):

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install nvidia-driver-XXX  # Replace XXX with version number (Thay XXX bằng số phiên bản)
```

### 4. Set Up Cloudflare Tunnel (Cài Đặt Cloudflare Tunnel) - Optional (Tùy chọn)

```bash
cd cloudflare
chmod +x auto_install.sh
./auto_install.sh
```

## ⚙️ Configuration (Cấu Hình)

Create a `.env` file (Tạo file `.env`) in the `metrics/` directory with the following configuration (với cấu hình sau):

```bash
# InfluxDB Configuration (Cấu hình InfluxDB)
INFLUXDB_URL=http://your-influxdb-server:8086
INFLUXDB_TOKEN=your-influxdb-token
INFLUXDB_ORG=your-organization
INFLUXDB_BUCKET=your-bucket-name
COLLECTION_INTERVAL=10  # Seconds between metric collections (Giây giữa các lần thu thập metrics)

# Telegram Bot Configuration (Cấu hình Telegram Bot)
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_ALLOWED_USERS=user_id1,user_id2,user_id3  # Comma-separated User IDs (User IDs cách nhau bởi dấu phẩy)
TELEGRAM_AUTO_SEND_CHAT_ID=your-chat-id  # For automatic status updates (Cho cập nhật trạng thái tự động)
TELEGRAM_AUTO_SEND_INTERVAL=3600  # Seconds, default: 1 hour (Giây, mặc định: 1 giờ)

# Alert System Configuration (Cấu hình hệ thống cảnh báo)
TELEGRAM_ALERT_CHAT_ID=your-alert-chat-id  # Chat ID for alerts (Chat ID cho cảnh báo)
ALERT_CPU_THRESHOLD=80  # CPU usage % threshold (Ngưỡng % sử dụng CPU)
ALERT_RAM_THRESHOLD=85  # RAM usage % threshold (Ngưỡng % sử dụng RAM)
ALERT_GPU_THRESHOLD=90  # GPU memory % threshold (Ngưỡng % bộ nhớ GPU)
ALERT_DISK_THRESHOLD=90  # Disk usage % threshold (Ngưỡng % sử dụng Disk)
ALERT_CHECK_INTERVAL=60  # Check every 60 seconds (Kiểm tra mỗi 60 giây)
ALERT_COOLDOWN=300  # Minimum 5 minutes between same alert type (Tối thiểu 5 phút giữa các cảnh báo cùng loại)
```

### Getting Your Telegram Bot Token (Lấy Token Bot Telegram)

1. Message [@BotFather](https://t.me/BotFather) on Telegram (Nhắn tin cho @BotFather)
2. Send `/newbot` command (Gửi lệnh `/newbot`)
3. Follow the instructions to get your bot token (Làm theo hướng dẫn để nhận token)
4. Send `/mybots` to manage your bot settings (Gửi `/mybots` để quản lý cài đặt)

### Getting Your Telegram User/Chat ID (Lấy User/Chat ID)

1. Start your bot or add it to a group (Khởi động bot hoặc thêm vào nhóm)
2. Run the application (Chạy ứng dụng)
3. Use `/userid` command for personal ID (Dùng lệnh `/userid` cho ID cá nhân)
4. Use `/groupid` command for group ID (Dùng lệnh `/groupid` cho ID nhóm)

## 🚀 Usage (Sử Dụng)

### Start the Monitoring Service (Khởi Động Dịch Vụ Giám Sát)

```bash
cd metrics
python app.py
```

The service will (Dịch vụ sẽ):
- Start Flask API server on port `1232` (Khởi động Flask API server trên cổng `1232`)
- Begin collecting metrics every `COLLECTION_INTERVAL` seconds (Bắt đầu thu thập metrics mỗi `COLLECTION_INTERVAL` giây)
- Send metrics to InfluxDB automatically (Gửi metrics đến InfluxDB tự động)
- Start Telegram bot for remote control (Khởi động Telegram bot để điều khiển từ xa)
- Monitor thresholds and send alerts (Giám sát ngưỡng và gửi cảnh báo)

### Run as Background Service (Chạy Như Background Service)

Create a systemd service file (Tạo file systemd service):

```bash
sudo nano /etc/systemd/system/server-monitor.service
```

Add the following content (Thêm nội dung sau):

```ini
[Unit]
Description=Server Monitoring Agent
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/ServerMonitoringSuite-Agent/metrics
ExecStart=/usr/bin/python3 /path/to/ServerMonitoringSuite-Agent/metrics/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service (Kích hoạt và khởi động service):

```bash
sudo systemctl daemon-reload
sudo systemctl enable server-monitor
sudo systemctl start server-monitor
sudo systemctl status server-monitor
```

## 🔌 API Endpoints

### GET `/metrics`
Returns current system metrics in JSON format (Trả về metrics hệ thống hiện tại dạng JSON).

**Response Example (Ví dụ phản hồi):**
```json
{
  "timestamp": "2025-11-19T10:30:00",
  "system": {
    "hostname": "Ubuntu-Server",
    "platform": "Linux",
    "uptime_hours": 48.5
  },
  "cpu": {
    "usage_percent": 35.2,
    "load_1min": 1.5
  },
  "memory": {
    "total_gb": 32.0,
    "used_gb": 16.5,
    "usage_percent": 51.6
  },
  "gpu": {
    "name": "NVIDIA RTX 3090",
    "memory": {
      "usage_percent": 45.2
    }
  }
}
```

### POST `/send`
Manually trigger metrics push to InfluxDB (Kích hoạt thủ công việc đẩy metrics lên InfluxDB).

### GET `/health`
Check service and InfluxDB connection status (Kiểm tra trạng thái dịch vụ và kết nối InfluxDB).

## 🤖 Telegram Bot Commands (Lệnh Bot)

| Command (Lệnh) | Description (Mô Tả) |
|---------|-------------|
| `/help` or `/start` | Display command list (Hiển thị danh sách lệnh) |
| `/info` | Show system overview (Hiển thị tổng quan hệ thống) |
| `/status` | Display system status with progress bars (Hiển thị trạng thái với thanh tiến trình) |
| `/cpu` | CPU information and per-core usage (Thông tin CPU và sử dụng từng core) |
| `/ram` | RAM and swap memory details (Chi tiết RAM và swap memory) |
| `/disk` | Disk usage information (Thông tin sử dụng ổ cứng) |
| `/gpu` | GPU metrics - NVIDIA only (Metrics GPU - chỉ NVIDIA) |
| `/network` | Network statistics and interfaces (Thống kê mạng và interfaces) |
| `/top` | Top 10 processes by CPU usage (Top 10 processes theo CPU) |
| `/userid` | Display your Telegram User ID (Hiển thị User ID của bạn) |
| `/groupid` | Display Group ID - in groups only (Hiển thị Group ID - chỉ trong nhóm) |
| `/author` | Administrator and author information (Thông tin quản trị viên và tác giả) |

### Example Bot Interactions (Ví Dụ Tương Tác Bot)

```
User: /status
Bot: 📊 SYSTEM STATUS (TRẠNG THÁI HỆ THỐNG)

🖥️ CPU: 45.2%
████████░░

💾 RAM: 51.6%
█████░░░░░
16.5/32.0 GB
```

## 🚨 Alert System (Hệ Thống Cảnh Báo)

The system automatically monitors metrics and sends alerts when thresholds are exceeded (Hệ thống tự động giám sát metrics và gửi cảnh báo khi vượt ngưỡng):

- **CPU Alert (Cảnh báo CPU)**: Triggered when CPU usage exceeds `ALERT_CPU_THRESHOLD` (Kích hoạt khi CPU vượt ngưỡng)
- **RAM Alert (Cảnh báo RAM)**: Triggered when RAM usage exceeds `ALERT_RAM_THRESHOLD` (Kích hoạt khi RAM vượt ngưỡng)
- **GPU Alert (Cảnh báo GPU)**: Triggered when GPU memory usage exceeds `ALERT_GPU_THRESHOLD` (Kích hoạt khi bộ nhớ GPU vượt ngưỡng)
- **Disk Alert (Cảnh báo Disk)**: Triggered when disk usage exceeds `ALERT_DISK_THRESHOLD` (Kích hoạt khi disk vượt ngưỡng)

**Alert Cooldown (Thời gian chờ cảnh báo)**: To prevent spam, the same alert type will only be sent once every `ALERT_COOLDOWN` seconds (Để tránh spam, cùng loại cảnh báo chỉ gửi mỗi `ALERT_COOLDOWN` giây) - default: 5 minutes (mặc định: 5 phút).

**Alert Example (Ví dụ cảnh báo):**
```
⚠️ SYSTEM ALERT

🔴 CPU WARNING
Usage: 85.3% (Threshold: 80%)

🕐 Time: 2025-11-19 10:30:00
🖥️ Host: Ubuntu-Server
```

## ☁️ Cloudflare Tunnel Setup (Cài Đặt Cloudflare Tunnel)

The `cloudflare/auto_install.sh` script helps you set up Cloudflare Tunnel for secure remote access (Script `cloudflare/auto_install.sh` giúp bạn cài đặt Cloudflare Tunnel để truy cập từ xa an toàn):

1. Edit `.env` file and add your Cloudflare tunnel token (Chỉnh sửa file `.env` và thêm Cloudflare tunnel token):
   ```bash
   key_token=your-cloudflare-tunnel-token
   ```

2. Run the installation script (Chạy installation script):
   ```bash
   cd cloudflare
   chmod +x auto_install.sh
   ./auto_install.sh
   ```

This will (Script sẽ):
- Add Cloudflare GPG key (Thêm Cloudflare GPG key)
- Install cloudflared (Cài đặt cloudflared)
- Configure the tunnel service (Cấu hình tunnel service)
- Start the tunnel automatically (Khởi động tunnel tự động)

## 👨‍💻 Administrator Information (Thông Tin Quản Trị Viên)

**Name (Họ Tên)**: Nguyễn Minh Phúc (Engineer - Kỹ sư)  
**Role (Vai Trò)**: DevSecOps Engineer & System Administrator (Kỹ sư DevSecOps & Quản trị viên hệ thống)

### About the Administrator (Giới Thiệu Quản Trị Viên)

Nguyễn Minh Phúc is a specialized DevSecOps engineer with extensive experience in (là kỹ sư DevSecOps chuyên môn với kinh nghiệm sâu rộng về):

- **DevSecOps & Automation (Tự động hóa)**: CI/CD pipeline design and implementation (Thiết kế và triển khai CI/CD pipeline)
- **Infrastructure Management (Quản lý hạ tầng)**: Server administration and monitoring (Quản trị và giám sát server)
- **Container Orchestration (Điều phối container)**: Docker and Kubernetes expertise (Chuyên gia Docker và Kubernetes)
- **Security & Compliance (Bảo mật & Tuân thủ)**: Infrastructure security and best practices (Bảo mật hạ tầng và thực tiễn tốt nhất)
- **Observability (Quan sát)**: System monitoring and logging solutions (Giải pháp giám sát và logging hệ thống)

### Technical Expertise (Chuyên Môn Kỹ Thuật)

- **Programming (Lập trình)**: Python, Bash, Go
- **Infrastructure as Code (Hạ tầng dưới dạng mã)**: Terraform, Ansible
- **Container Technologies (Công nghệ container)**: Docker, Kubernetes, Docker Swarm
- **Monitoring Tools (Công cụ giám sát)**: InfluxDB, Grafana, Prometheus
- **Cloud Platforms (Nền tảng đám mây)**: AWS, Azure, Google Cloud
- **Version Control (Kiểm soát phiên bản)**: Git, GitHub, GitLab

### Project Philosophy (Triết Lý Dự Án)

This monitoring suite was developed to provide (Bộ giám sát này được phát triển để cung cấp):
- **Real-time Visibility (Tầm nhìn thời gian thực)**: Instant access to system metrics (Truy cập ngay lập tức vào metrics hệ thống)
- **Proactive Monitoring (Giám sát chủ động)**: Automated alerts before issues escalate (Cảnh báo tự động trước khi vấn đề leo thang)
- **Remote Management (Quản lý từ xa)**: Telegram-based control for on-the-go administration (Điều khiển qua Telegram cho quản trị di động)
- **Data-Driven Decisions (Quyết định dựa trên dữ liệu)**: Historical metrics storage in InfluxDB (Lưu trữ metrics lịch sử trong InfluxDB)
- **Ease of Use (Dễ sử dụng)**: Simple setup and intuitive commands (Cài đặt đơn giản và lệnh trực quan)

### Contact (Liên Hệ)

For support, feature requests, or contributions, please contact the administrator or open an issue on the GitHub repository (Để được hỗ trợ, yêu cầu tính năng, hoặc đóng góp, vui lòng liên hệ quản trị viên hoặc mở issue trên GitHub repository).

**Version (Phiên bản)**: 1.0.0  
**Last Updated (Cập nhật lần cuối)**: November 2025 (Tháng 11 năm 2025)

## 📄 License (Giấy Phép)

This project is open source (dự án này là mã nguồn mở).

---

**Built with ❤️ by Nguyễn Minh Phúc - DevSecOps & Infrastructure Engineer**