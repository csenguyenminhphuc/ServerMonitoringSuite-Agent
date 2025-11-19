from flask import Flask, jsonify
import psutil
import platform
from datetime import datetime
import subprocess
import json
import re
import os
import asyncio
import threading
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Load environment variables
load_dotenv()

app = Flask(__name__)

# InfluxDB Configuration
INFLUXDB_URL = os.getenv('INFLUXDB_URL')
INFLUXDB_TOKEN = os.getenv('INFLUXDB_TOKEN')
INFLUXDB_ORG = os.getenv('INFLUXDB_ORG')
INFLUXDB_BUCKET = os.getenv('INFLUXDB_BUCKET')
COLLECTION_INTERVAL = int(os.getenv('COLLECTION_INTERVAL', 10))

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_ALLOWED_USERS = os.getenv('TELEGRAM_ALLOWED_USERS', '').split(',') if os.getenv('TELEGRAM_ALLOWED_USERS') else []
TELEGRAM_AUTO_SEND_CHAT_ID = os.getenv('TELEGRAM_AUTO_SEND_CHAT_ID')  # Chat ID để gửi status tự động
TELEGRAM_AUTO_SEND_INTERVAL = int(os.getenv('TELEGRAM_AUTO_SEND_INTERVAL', 3600))  # Interval (giây), mặc định 1 giờ

# Alert Thresholds Configuration
TELEGRAM_ALERT_CHAT_ID = os.getenv('TELEGRAM_ALERT_CHAT_ID')  # Chat ID để gửi cảnh báo
ALERT_CPU_THRESHOLD = float(os.getenv('ALERT_CPU_THRESHOLD', 80))  # CPU % threshold
ALERT_RAM_THRESHOLD = float(os.getenv('ALERT_RAM_THRESHOLD', 85))  # RAM % threshold
ALERT_GPU_THRESHOLD = float(os.getenv('ALERT_GPU_THRESHOLD', 90))  # GPU Memory % threshold
ALERT_DISK_THRESHOLD = float(os.getenv('ALERT_DISK_THRESHOLD', 90))  # Disk % threshold
ALERT_CHECK_INTERVAL = int(os.getenv('ALERT_CHECK_INTERVAL', 60))  # Kiểm tra mỗi 60s
ALERT_COOLDOWN = int(os.getenv('ALERT_COOLDOWN', 300))  # Chỉ gửi lại sau 5 phút

# Biến lưu trạng thái alert (tránh spam)
last_alert_time = {
    'cpu': 0,
    'ram': 0,
    'gpu': 0,
    'disk': 0
}

# Initialize InfluxDB client
influxdb_client = None
write_api = None

if all([INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG, INFLUXDB_BUCKET]):
    try:
        influxdb_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
        write_api = influxdb_client.write_api(write_options=SYNCHRONOUS)
        print(f"✅ InfluxDB connected: {INFLUXDB_URL}")
    except Exception as e:
        print(f"❌ InfluxDB connection failed: {e}")
else:
    print("⚠️  InfluxDB not configured - metrics will not be sent to InfluxDB")

def get_gpu_info():
    """Lấy thông tin GPU NVIDIA sử dụng nvidia-smi (GPU đầu tiên)"""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=index,name,temperature.gpu,utilization.gpu,memory.total,memory.used,memory.free,power.draw,power.limit,fan.speed', 
             '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return None
            
        # Chỉ lấy GPU đầu tiên
        line = result.stdout.strip().split('\n')[0]
        if line:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 10:
                mem_total = float(parts[4]) if parts[4] != '[N/A]' else 0
                mem_used = float(parts[5]) if parts[5] != '[N/A]' else 0
                mem_free = float(parts[6]) if parts[6] != '[N/A]' else 0
                
                return {
                    "index": int(parts[0]),
                    "name": parts[1],
                    "temperature_c": round(float(parts[2]), 1) if parts[2] != '[N/A]' else None,
                    "usage_percent": round(float(parts[3]), 1) if parts[3] != '[N/A]' else None,
                    "memory": {
                        "total_gb": round(mem_total / 1024, 2),
                        "used_gb": round(mem_used / 1024, 2),
                        "free_gb": round(mem_free / 1024, 2),
                        "usage_percent": round((mem_used / mem_total * 100), 2) if mem_total > 0 else 0
                    },
                    "power_draw_w": round(float(parts[7]), 1) if parts[7] != '[N/A]' else None,
                    "power_limit_w": round(float(parts[8]), 1) if parts[8] != '[N/A]' else None,
                    "fan_speed_percent": round(float(parts[9]), 1) if parts[9] != '[N/A]' else None
                }
        
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return None

def get_temperature_sensors():
    """Lấy thông tin nhiệt độ từ các cảm biến Linux"""
    temps = {}
    try:
        sensors = psutil.sensors_temperatures()
        if sensors:
            for name, entries in sensors.items():
                temps[name] = []
                for entry in entries:
                    temps[name].append({
                        "label": entry.label or "unknown",
                        "current": entry.current,
                        "high": entry.high if entry.high else None,
                        "critical": entry.critical if entry.critical else None
                    })
    except (AttributeError, Exception):
        pass
    
    return temps if temps else None

def get_fan_sensors():
    """Lấy thông tin quạt từ các cảm biến Linux"""
    fans = {}
    try:
        fan_sensors = psutil.sensors_fans()
        if fan_sensors:
            for name, entries in fan_sensors.items():
                fans[name] = []
                for entry in entries:
                    fans[name].append({
                        "label": entry.label or "unknown",
                        "current_rpm": entry.current
                    })
    except (AttributeError, Exception):
        pass
    
    return fans if fans else None

def get_battery_info():
    """Lấy thông tin pin (nếu có)"""
    try:
        battery = psutil.sensors_battery()
        if battery:
            return {
                "percent": battery.percent,
                "power_plugged": battery.power_plugged,
                "seconds_left": battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else None
            }
    except (AttributeError, Exception):
        pass
    
    return None

def collect_metrics():
    """Thu thập metrics để trả về hoặc gửi đến InfluxDB"""
    """Lấy các thông số metrics quan trọng của server"""
    
    # CPU metrics
    cpu_percent = psutil.cpu_percent(interval=1)
    
    # Load average (Linux)
    try:
        load_avg = psutil.getloadavg()
    except (AttributeError, OSError):
        load_avg = (None, None, None)
    
    # Memory metrics
    memory = psutil.virtual_memory()
    
    # Disk metrics - tổng hợp tất cả partition
    disk_total = 0
    disk_used = 0
    disk_free = 0
    seen_devices = set()
    
    for partition in psutil.disk_partitions(all=False):
        # Bỏ qua các mountpoint là file hoặc bind mount trùng lặp
        if partition.mountpoint.startswith('/etc/') or partition.mountpoint.startswith('/usr/'):
            continue
        if partition.mountpoint.startswith('/dev/') or partition.mountpoint.startswith('/tmp/'):
            continue
            
        # Chỉ lấy 1 lần cho mỗi device
        device_key = f"{partition.device}_{partition.fstype}"
        if device_key in seen_devices:
            continue
        seen_devices.add(device_key)
        
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            disk_total += usage.total
            disk_used += usage.used
            disk_free += usage.free
        except (PermissionError, OSError):
            continue
    
    # Disk IO
    disk_io = psutil.disk_io_counters()
    
    # Network metrics
    net_io = psutil.net_io_counters()
    
    # System info
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    
    # GPU info
    gpu_info = get_gpu_info()
    
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "system": {
            "hostname": "Ubuntu-Server",
            "platform": platform.system(),
            "os_version": platform.release(),
            "uptime_hours": round((datetime.now() - boot_time).total_seconds() / 3600, 2)
        },
        "cpu": {
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "usage_percent": round(cpu_percent, 2),
            "load_1min": round(load_avg[0], 2) if load_avg[0] is not None else None,
            "load_5min": round(load_avg[1], 2) if load_avg[1] is not None else None,
            "load_15min": round(load_avg[2], 2) if load_avg[2] is not None else None
        },
        "memory": {
            "total_gb": round(memory.total / (1024**3), 2),
            "used_gb": round(memory.used / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "usage_percent": round(memory.percent, 2)
        },
        "disk": {
            "total_gb": round(disk_total / (1024**3), 2),
            "used_gb": round(disk_used / (1024**3), 2),
            "free_gb": round(disk_free / (1024**3), 2),
            "usage_percent": round((disk_used / disk_total * 100), 2) if disk_total > 0 else 0
        },
        "network": {
            "sent_gb": round(net_io.bytes_sent / (1024**3), 2),
            "recv_gb": round(net_io.bytes_recv / (1024**3), 2),
            "sent_mb_per_sec": round((net_io.bytes_sent / (1024**2)) / ((datetime.now() - boot_time).total_seconds()), 2),
            "recv_mb_per_sec": round((net_io.bytes_recv / (1024**2)) / ((datetime.now() - boot_time).total_seconds()), 2),
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
            "errors": net_io.errin + net_io.errout,
            "drops": net_io.dropin + net_io.dropout
        },
        "gpu": gpu_info
    }
    
    return metrics

def send_to_influxdb(metrics):
    """Gửi metrics đến InfluxDB"""
    if not write_api:
        return False
    
    try:
        hostname = metrics['system']['hostname']
        timestamp = datetime.fromisoformat(metrics['timestamp'])
        
        # CPU metrics
        point = Point("cpu") \
            .tag("host", hostname) \
            .field("physical_cores", metrics['cpu']['physical_cores']) \
            .field("logical_cores", metrics['cpu']['logical_cores']) \
            .field("usage_percent", metrics['cpu']['usage_percent']) \
            .field("load_1min", metrics['cpu']['load_1min'] or 0) \
            .field("load_5min", metrics['cpu']['load_5min'] or 0) \
            .field("load_15min", metrics['cpu']['load_15min'] or 0) \
            .time(timestamp, WritePrecision.NS)
        write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
        
        # Memory metrics
        point = Point("memory") \
            .tag("host", hostname) \
            .field("total_gb", metrics['memory']['total_gb']) \
            .field("used_gb", metrics['memory']['used_gb']) \
            .field("available_gb", metrics['memory']['available_gb']) \
            .field("usage_percent", metrics['memory']['usage_percent']) \
            .time(timestamp, WritePrecision.NS)
        write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
        
        # Disk metrics
        point = Point("disk") \
            .tag("host", hostname) \
            .field("total_gb", metrics['disk']['total_gb']) \
            .field("used_gb", metrics['disk']['used_gb']) \
            .field("free_gb", metrics['disk']['free_gb']) \
            .field("usage_percent", metrics['disk']['usage_percent']) \
            .time(timestamp, WritePrecision.NS)
        write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
        
        # Network metrics
        point = Point("network") \
            .tag("host", hostname) \
            .field("sent_gb", metrics['network']['sent_gb']) \
            .field("recv_gb", metrics['network']['recv_gb']) \
            .field("sent_mb_per_sec", metrics['network']['sent_mb_per_sec']) \
            .field("recv_mb_per_sec", metrics['network']['recv_mb_per_sec']) \
            .field("packets_sent", metrics['network']['packets_sent']) \
            .field("packets_recv", metrics['network']['packets_recv']) \
            .field("errors", metrics['network']['errors']) \
            .field("drops", metrics['network']['drops']) \
            .time(timestamp, WritePrecision.NS)
        write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
        
        # GPU metrics
        if metrics['gpu']:
            gpu = metrics['gpu']
            point = Point("gpu") \
                .tag("host", hostname) \
                .tag("gpu_index", str(gpu['index'])) \
                .tag("gpu_name", gpu['name']) \
                .field("temperature_c", gpu['temperature_c'] or 0) \
                .field("usage_percent", gpu['usage_percent'] or 0) \
                .field("memory_total_gb", gpu['memory']['total_gb']) \
                .field("memory_used_gb", gpu['memory']['used_gb']) \
                .field("memory_free_gb", gpu['memory']['free_gb']) \
                .field("memory_usage_percent", gpu['memory']['usage_percent']) \
                .field("power_draw_w", gpu['power_draw_w'] or 0) \
                .field("power_limit_w", gpu['power_limit_w'] or 0) \
                .field("fan_speed_percent", gpu['fan_speed_percent'] or 0) \
                .time(timestamp, WritePrecision.NS)
            write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
        
        # System uptime
        point = Point("system") \
            .tag("host", hostname) \
            .field("uptime_hours", metrics['system']['uptime_hours']) \
            .time(timestamp, WritePrecision.NS)
        write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
        
        print(f"✅ Metrics sent to InfluxDB at {timestamp}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send metrics to InfluxDB: {e}")
        return False

def scheduled_collect():
    """Hàm chạy định kỳ để thu thập và gửi metrics"""
    metrics = collect_metrics()
    send_to_influxdb(metrics)

@app.route('/metrics', methods=['GET'])
def get_metrics():
    """API endpoint để lấy metrics hiện tại"""
    metrics = collect_metrics()
    return jsonify(metrics)

@app.route('/send', methods=['POST'])
def send_metrics():
    """API endpoint để gửi metrics lên InfluxDB ngay lập tức"""
    metrics = collect_metrics()
    success = send_to_influxdb(metrics)
    return jsonify({
        "success": success,
        "message": "Metrics sent to InfluxDB" if success else "Failed to send metrics"
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Kiểm tra trạng thái kết nối InfluxDB"""
    influxdb_status = "connected" if influxdb_client else "not configured"
    if influxdb_client:
        try:
            influxdb_client.health()
            influxdb_status = "connected"
        except:
            influxdb_status = "disconnected"
    
    return jsonify({
        "status": "healthy",
        "influxdb": influxdb_status,
        "collection_interval": COLLECTION_INTERVAL
    })

# ============= TELEGRAM BOT COMMANDS =============

def check_authorization(user_id: int) -> bool:
    """Kiểm tra xem user có quyền sử dụng bot không"""
    if not TELEGRAM_ALLOWED_USERS or len(TELEGRAM_ALLOWED_USERS) == 0:
        return True  # Nếu không cấu hình, cho phép tất cả
    return str(user_id) in TELEGRAM_ALLOWED_USERS

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị danh sách lệnh"""
    if not check_authorization(update.effective_user.id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng bot này!")
        return
    
    help_text = """🤖 *DANH SÁCH LỆNH BOT*

📊 *Thông tin tổng quan:*
/info - Thông tin hệ thống tổng quát
/status - Trạng thái hệ thống

💻 *Thông tin chi tiết:*
/cpu - Thông tin CPU
/ram - Thông tin RAM
/disk - Thông tin ổ cứng
/gpu - Thông tin GPU (nếu có)
/network - Thông tin mạng
/top - Các process đang chạy (top 10)

🆔 *Thông tin bot:*
/userid - Xem User ID của bạn
/groupid - Xem Group ID (nếu trong group)
/author - Thông tin tác giả & admin
/help - Hiển thị trợ giúp này
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị thông tin tổng quan hệ thống"""
    if not check_authorization(update.effective_user.id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng bot này!")
        return
    
    metrics = collect_metrics()
    sys = metrics['system']
    cpu = metrics['cpu']
    mem = metrics['memory']
    disk = metrics['disk']
    
    info_text = f"""🖥️ *THÔNG TIN HỆ THỐNG*

*Hệ điều hành:*
• Hostname: `Ubuntu-Server`
• Platform: {sys['platform']} {sys['os_version']}
• Uptime: {sys['uptime_hours']} giờ

*CPU:*
• Cores: {cpu['physical_cores']} physical / {cpu['logical_cores']} logical
• Usage: {cpu['usage_percent']}%
• Load avg: {cpu['load_1min']} / {cpu['load_5min']} / {cpu['load_15min']}

*RAM:*
• Total: {mem['total_gb']} GB
• Used: {mem['used_gb']} GB ({mem['usage_percent']}%)
• Available: {mem['available_gb']} GB

*Disk:*
• Total: {disk['total_gb']} GB
• Used: {disk['used_gb']} GB ({disk['usage_percent']}%)
• Free: {disk['free_gb']} GB
"""
    
    if metrics['gpu']:
        gpu = metrics['gpu']
        info_text += f"""
*GPU:*
• Name: {gpu['name']}
• Memory: {gpu['memory']['used_gb']}/{gpu['memory']['total_gb']} GB ({gpu['memory']['usage_percent']}%)
• Temp: {gpu['temperature_c']}°C
"""
    
    await update.message.reply_text(info_text, parse_mode='Markdown')

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị trạng thái hệ thống"""
    if not check_authorization(update.effective_user.id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng bot này!")
        return
    
    metrics = collect_metrics()
    
    # Tạo thanh progress bar
    def make_bar(percent, length=10):
        filled = int(percent / 100 * length)
        return '█' * filled + '░' * (length - filled)
    
    cpu_bar = make_bar(metrics['cpu']['usage_percent'])
    ram_bar = make_bar(metrics['memory']['usage_percent'])
    disk_bar = make_bar(metrics['disk']['usage_percent'])
    
    status_text = f"""📊 *TRẠNG THÁI HỆ THỐNG*

🖥️ *CPU:* {metrics['cpu']['usage_percent']}%
{cpu_bar}

💾 *RAM:* {metrics['memory']['usage_percent']}%
{ram_bar}
{metrics['memory']['used_gb']}/{metrics['memory']['total_gb']} GB

💿 *Disk:* {metrics['disk']['usage_percent']}%
{disk_bar}
{metrics['disk']['used_gb']}/{metrics['disk']['total_gb']} GB
"""
    
    # Network info
    net = metrics['network']
    status_text += f"""
🌐 *Network:*
• Sent: {net['sent_gb']} GB
• Recv: {net['recv_gb']} GB
• Errors: {net['errors']}
"""
    
    # GPU Memory (không hiện GPU Compute nữa)
    if metrics['gpu']:
        gpu = metrics['gpu']
        gpu_mem_bar = make_bar(gpu['memory']['usage_percent'])
        status_text += f"""
🎮 *GPU Memory:* {gpu['memory']['usage_percent']}%
{gpu_mem_bar}
{gpu['memory']['used_gb']}/{gpu['memory']['total_gb']} GB
"""
    
    await update.message.reply_text(status_text, parse_mode='Markdown')

async def cmd_cpu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị thông tin CPU chi tiết"""
    if not check_authorization(update.effective_user.id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng bot này!")
        return
    
    metrics = collect_metrics()
    cpu = metrics['cpu']
    
    # Lấy thông tin per-core
    per_core = psutil.cpu_percent(interval=1, percpu=True)
    core_info = '\n'.join([f"Core {i}: {percent}%" for i, percent in enumerate(per_core)])
    
    cpu_text = f"""
💻 **THÔNG TIN CPU**

**Tổng quan:**
• Physical Cores: {cpu['physical_cores']}
• Logical Cores: {cpu['logical_cores']}
• Usage: {cpu['usage_percent']}%

**Load Average:**
• 1 min: {cpu['load_1min']}
• 5 min: {cpu['load_5min']}
• 15 min: {cpu['load_15min']}

**Usage per Core:**
{core_info}
"""
    
    await update.message.reply_text(cpu_text, parse_mode='Markdown')

async def cmd_ram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị thông tin RAM chi tiết"""
    if not check_authorization(update.effective_user.id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng bot này!")
        return
    
    metrics = collect_metrics()
    mem = metrics['memory']
    
    # Lấy thêm thông tin swap
    swap = psutil.swap_memory()
    
    ram_text = f"""
💾 **THÔNG TIN RAM**

**Virtual Memory:**
• Total: {mem['total_gb']} GB
• Used: {mem['used_gb']} GB
• Available: {mem['available_gb']} GB
• Usage: {mem['usage_percent']}%

**Swap Memory:**
• Total: {round(swap.total / (1024**3), 2)} GB
• Used: {round(swap.used / (1024**3), 2)} GB
• Free: {round(swap.free / (1024**3), 2)} GB
• Usage: {swap.percent}%
"""
    
    await update.message.reply_text(ram_text, parse_mode='Markdown')

async def cmd_disk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị thông tin ổ cứng chi tiết"""
    if not check_authorization(update.effective_user.id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng bot này!")
        return
    
    metrics = collect_metrics()
    disk = metrics['disk']
    
    disk_text = f"""💿 *THÔNG TIN Ổ CỨNG*

• Total: {disk['total_gb']} GB
• Used: {disk['used_gb']} GB
• Free: {disk['free_gb']} GB
• Usage: {disk['usage_percent']}%
"""
    
    await update.message.reply_text(disk_text, parse_mode='Markdown')

async def cmd_gpu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị thông tin GPU"""
    if not check_authorization(update.effective_user.id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng bot này!")
        return
    
    gpu_info = get_gpu_info()
    
    if not gpu_info:
        await update.message.reply_text("❌ Không tìm thấy GPU hoặc nvidia-smi không khả dụng")
        return
    
    gpu = gpu_info
    gpu_text = f"""
🎮 **THÔNG TIN GPU**

**GPU:** {gpu['name']} (Index: {gpu['index']})

**Compute Usage:**
• GPU Utilization: {gpu['usage_percent']}%
• Temperature: {gpu['temperature_c']}°C
• Fan Speed: {gpu['fan_speed_percent']}%

**Memory Usage:**
• Total: {gpu['memory']['total_gb']} GB
• Used: {gpu['memory']['used_gb']} GB
• Free: {gpu['memory']['free_gb']} GB
• Usage: {gpu['memory']['usage_percent']}%

**Power:**
• Power Draw: {gpu['power_draw_w']} W
• Power Limit: {gpu['power_limit_w']} W
"""
    
    await update.message.reply_text(gpu_text, parse_mode='Markdown')

async def cmd_network(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị thông tin mạng chi tiết"""
    if not check_authorization(update.effective_user.id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng bot này!")
        return
    
    metrics = collect_metrics()
    net = metrics['network']
    
    # Lấy thông tin network interfaces
    net_if_addrs = psutil.net_if_addrs()
    net_if_stats = psutil.net_if_stats()
    
    interfaces_info = []
    for iface_name, iface_addrs in net_if_addrs.items():
        if iface_name.startswith('lo'):
            continue  # Bỏ qua loopback
        
        stats = net_if_stats.get(iface_name)
        if stats and stats.isup:
            # Lấy IP address
            ipv4 = None
            for addr in iface_addrs:
                if addr.family == 2:  # AF_INET (IPv4)
                    ipv4 = addr.address
                    break
            
            if ipv4:
                interfaces_info.append(f"• {iface_name}: {ipv4} - Speed: {stats.speed} Mbps")
    
    net_text = f"""🌐 *THÔNG TIN MẠNG*

*Tổng quan:*
• Sent: {net['sent_gb']} GB
• Received: {net['recv_gb']} GB
• Packets Sent: {net['packets_sent']}
• Packets Recv: {net['packets_recv']}
• Errors: {net['errors']}
• Drops: {net['drops']}

*Network Interfaces:*
{chr(10).join(interfaces_info) if interfaces_info else 'Không có thông tin'}
"""
    
    await update.message.reply_text(net_text, parse_mode='Markdown')

async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị top 10 processes đang chạy"""
    if not check_authorization(update.effective_user.id):
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng bot này!")
        return
    
    # Gửi message đang xử lý
    processing_msg = await update.message.reply_text("⏳ Đang thu thập thông tin processes...")
    
    # Lấy danh sách processes với CPU usage đúng (cần interval)
    cpu_count = psutil.cpu_count()
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'memory_percent']):
        try:
            # Lấy CPU percent với interval để có số liệu chính xác
            cpu_percent = proc.cpu_percent(interval=0.1)
            # Normalize CPU về 100% (chia cho số cores)
            cpu_normalized = cpu_percent / cpu_count if cpu_count else cpu_percent
            pinfo = proc.info
            processes.append({
                'pid': pinfo['pid'],
                'name': pinfo['name'][:20],  # Giới hạn độ dài tên
                'cpu': cpu_normalized,
                'mem': pinfo['memory_percent'] or 0
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    
    # Sort by CPU usage, sau đó by Memory nếu CPU bằng nhau
    processes.sort(key=lambda x: (x['cpu'], x['mem']), reverse=True)
    top_10 = processes[:10]
    
    top_text = "⚡ *TOP 10 PROCESSES (CPU)*\n\n"
    top_text += "```\n"
    top_text += f"{'PID':<8} {'NAME':<20} {'CPU%':<8} {'MEM%':<8}\n"
    top_text += "-" * 50 + "\n"
    for p in top_10:
        top_text += f"{p['pid']:<8} {p['name']:<20} {p['cpu']:<8.1f} {p['mem']:<8.1f}\n"
    top_text += "```"
    
    # Xóa message đang xử lý và gửi kết quả
    await processing_msg.delete()
    await update.message.reply_text(top_text, parse_mode='Markdown')

async def cmd_userid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị User ID của người dùng"""
    user = update.effective_user
    userid_text = f"""
👤 **THÔNG TIN USER**

• User ID: `{user.id}`
• Username: @{user.username if user.username else 'N/A'}
• First Name: {user.first_name}
• Last Name: {user.last_name if user.last_name else 'N/A'}
"""
    await update.message.reply_text(userid_text, parse_mode='Markdown')

async def cmd_groupid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị Group ID (nếu trong group)"""
    chat = update.effective_chat
    
    if chat.type in ['group', 'supergroup']:
        groupid_text = f"""
👥 **THÔNG TIN GROUP**

• Group ID: `{chat.id}`
• Group Name: {chat.title}
• Type: {chat.type}
"""
    else:
        groupid_text = "❌ Lệnh này chỉ hoạt động trong group!"
    
    await update.message.reply_text(groupid_text, parse_mode='Markdown')

async def cmd_author(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị thông tin tác giả và admin"""
    author_text = """
👨‍💻 *THÔNG TIN TÁC GIẢ & ADMIN*

*Tác giả:* Kỹ sư Nguyễn Minh Phúc
*Vai trò:* DevSecOps & Infrastructure Engineer

*Giới thiệu:*
• Chuyên gia về DevSecOps, tự động hóa hệ thống
• Quản trị và giám sát hạ tầng server
• Phát triển các công cụ monitoring và automation
• Đảm bảo bảo mật và hiệu suất hệ thống

*Chuyên môn:*
• CI/CD Pipeline & Automation
• Container & Kubernetes
• System Monitoring & Observability
• Security & Infrastructure as Code
• Python, Docker, Terraform, Ansible

*Bot này:*
Được phát triển để giám sát và quản lý server từ xa thông qua Telegram, giúp theo dõi tài nguyên hệ thống (CPU, RAM, GPU, Network) một cách thuận tiện và real-time.

📧 Contact: [Admin]
🔧 Version: 1.0.0
"""
    await update.message.reply_text(author_text, parse_mode='Markdown')

async def check_and_send_alerts(application):
    """Kiểm tra ngưỡng và gửi cảnh báo"""
    if not TELEGRAM_ALERT_CHAT_ID:
        return
    
    try:
        import time
        current_time = time.time()
        metrics = collect_metrics()
        alerts = []
        
        # Kiểm tra CPU
        cpu_usage = metrics['cpu']['usage_percent']
        if cpu_usage >= ALERT_CPU_THRESHOLD:
            if current_time - last_alert_time['cpu'] >= ALERT_COOLDOWN:
                alerts.append(f"🔴 *CPU WARNING*\nUsage: {cpu_usage}% (Threshold: {ALERT_CPU_THRESHOLD}%)")
                last_alert_time['cpu'] = current_time
        
        # Kiểm tra RAM
        ram_usage = metrics['memory']['usage_percent']
        if ram_usage >= ALERT_RAM_THRESHOLD:
            if current_time - last_alert_time['ram'] >= ALERT_COOLDOWN:
                alerts.append(f"🟠 *RAM WARNING*\nUsage: {ram_usage}% (Threshold: {ALERT_RAM_THRESHOLD}%)\n{metrics['memory']['used_gb']}/{metrics['memory']['total_gb']} GB")
                last_alert_time['ram'] = current_time
        
        # Kiểm tra Disk
        disk_usage = metrics['disk']['usage_percent']
        if disk_usage >= ALERT_DISK_THRESHOLD:
            if current_time - last_alert_time['disk'] >= ALERT_COOLDOWN:
                alerts.append(f"🟡 *DISK WARNING*\nUsage: {disk_usage}% (Threshold: {ALERT_DISK_THRESHOLD}%)\n{metrics['disk']['used_gb']}/{metrics['disk']['total_gb']} GB")
                last_alert_time['disk'] = current_time
        
        # Kiểm tra GPU
        if metrics['gpu']:
            gpu_usage = metrics['gpu']['memory']['usage_percent']
            if gpu_usage >= ALERT_GPU_THRESHOLD:
                if current_time - last_alert_time['gpu'] >= ALERT_COOLDOWN:
                    alerts.append(f"🟣 *GPU MEMORY WARNING*\nUsage: {gpu_usage}% (Threshold: {ALERT_GPU_THRESHOLD}%)\n{metrics['gpu']['memory']['used_gb']}/{metrics['gpu']['memory']['total_gb']} GB\nGPU: {metrics['gpu']['name']}")
                    last_alert_time['gpu'] = current_time
        
        # Gửi tất cả alerts
        if alerts:
            alert_text = "⚠️ *SYSTEM ALERT*\n\n" + "\n\n".join(alerts)
            alert_text += f"\n\n🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            alert_text += f"\n🖥️ Host: `{metrics['system']['hostname']}`"
            
            await application.bot.send_message(
                chat_id=TELEGRAM_ALERT_CHAT_ID,
                text=alert_text,
                parse_mode='Markdown'
            )
            print(f"⚠️  Alert sent: {len(alerts)} warning(s)")
            
    except Exception as e:
        print(f"❌ Failed to check/send alerts: {e}")

async def send_auto_status(application):
    """Gửi status tự động đến chat đã cấu hình"""
    if not TELEGRAM_AUTO_SEND_CHAT_ID:
        return
    
    try:
        metrics = collect_metrics()
        
        def make_bar(percent, length=10):
            filled = int(percent / 100 * length)
            return '█' * filled + '░' * (length - filled)
        
        cpu_bar = make_bar(metrics['cpu']['usage_percent'])
        ram_bar = make_bar(metrics['memory']['usage_percent'])
        disk_bar = make_bar(metrics['disk']['usage_percent'])
        
        status_text = f"""📊 *AUTO STATUS UPDATE*

🖥️ *CPU:* {metrics['cpu']['usage_percent']}%
{cpu_bar}

💾 *RAM:* {metrics['memory']['usage_percent']}%
{ram_bar}
{metrics['memory']['used_gb']}/{metrics['memory']['total_gb']} GB

💿 *Disk:* {metrics['disk']['usage_percent']}%
{disk_bar}
{metrics['disk']['used_gb']}/{metrics['disk']['total_gb']} GB
"""
        
        net = metrics['network']
        status_text += f"""
🌐 *Network:*
• Sent: {net['sent_gb']} GB
• Recv: {net['recv_gb']} GB
"""
        
        if metrics['gpu']:
            gpu = metrics['gpu']
            gpu_mem_bar = make_bar(gpu['memory']['usage_percent'])
            status_text += f"""
🎮 *GPU Memory:* {gpu['memory']['usage_percent']}%
{gpu_mem_bar}
{gpu['memory']['used_gb']}/{gpu['memory']['total_gb']} GB
"""
        
        await application.bot.send_message(
            chat_id=TELEGRAM_AUTO_SEND_CHAT_ID,
            text=status_text,
            parse_mode='Markdown'
        )
        print(f"✅ Auto-status sent to chat {TELEGRAM_AUTO_SEND_CHAT_ID}")
    except Exception as e:
        print(f"❌ Failed to send auto-status: {e}")

async def start_telegram_bot():
    """Khởi động Telegram Bot"""
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️  Telegram Bot not configured - TELEGRAM_BOT_TOKEN not found")
        return
    
    # Tạo application với retry và timeout config
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(
        connection_pool_size=8,
        read_timeout=30.0,
        write_timeout=30.0,
        connect_timeout=30.0,
        pool_timeout=30.0,
    )
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).request(request).build()
    
    # Đăng ký handlers
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("start", cmd_help))
    application.add_handler(CommandHandler("info", cmd_info))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("cpu", cmd_cpu))
    application.add_handler(CommandHandler("ram", cmd_ram))
    application.add_handler(CommandHandler("disk", cmd_disk))
    application.add_handler(CommandHandler("gpu", cmd_gpu))
    application.add_handler(CommandHandler("network", cmd_network))
    application.add_handler(CommandHandler("top", cmd_top))
    application.add_handler(CommandHandler("userid", cmd_userid))
    application.add_handler(CommandHandler("groupid", cmd_groupid))
    application.add_handler(CommandHandler("author", cmd_author))
    
    # Thiết lập Bot Commands Menu (nút bấm nhanh)
    from telegram import BotCommand
    commands = [
        BotCommand("author", "Thông tin tác giả"),
        BotCommand("help", "Hiển thị danh sách lệnh"),
        BotCommand("info", "Thông tin hệ thống"),
        BotCommand("status", "Trạng thái hệ thống"),
        BotCommand("cpu", "Thông tin CPU"),
        BotCommand("ram", "Thông tin RAM"),
        BotCommand("disk", "Thông tin Disk"),
        BotCommand("gpu", "Thông tin GPU"),
        BotCommand("network", "Thông tin mạng"),
        BotCommand("top", "Top processes"),
        BotCommand("userid", "Xem User ID"),
        BotCommand("groupid", "Xem Group ID"),
    ]
    await application.bot.set_my_commands(commands)
    
    # Khởi tạo và chạy bot với drop_pending_updates=True
    try:
        await application.initialize()
        await application.start()
        print(f"🤖 Telegram Bot started successfully")
        
        # Test kết nối
        bot_info = await application.bot.get_me()
        print(f"✅ Connected as @{bot_info.username}")
        
        # Thêm job scheduler cho auto-send status và alerts
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        scheduler = AsyncIOScheduler()
        
        if TELEGRAM_AUTO_SEND_CHAT_ID:
            scheduler.add_job(
                send_auto_status,
                'interval',
                seconds=TELEGRAM_AUTO_SEND_INTERVAL,
                args=[application]
            )
            print(f"📤 Auto-send status enabled: every {TELEGRAM_AUTO_SEND_INTERVAL}s to chat {TELEGRAM_AUTO_SEND_CHAT_ID}")
        
        if TELEGRAM_ALERT_CHAT_ID:
            scheduler.add_job(
                check_and_send_alerts,
                'interval',
                seconds=ALERT_CHECK_INTERVAL,
                args=[application]
            )
            print(f"⚠️  Alert monitoring enabled: checking every {ALERT_CHECK_INTERVAL}s")
            print(f"   CPU: {ALERT_CPU_THRESHOLD}% | RAM: {ALERT_RAM_THRESHOLD}% | GPU: {ALERT_GPU_THRESHOLD}% | Disk: {ALERT_DISK_THRESHOLD}%")
        
        if TELEGRAM_AUTO_SEND_CHAT_ID or TELEGRAM_ALERT_CHAT_ID:
            scheduler.start()
        
        # Bắt đầu polling với stop_signals=None để tránh lỗi signal trong thread
        await application.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message"],
            timeout=30,
            bootstrap_retries=5
        )
        
        # Giữ bot chạy
        while True:
            await asyncio.sleep(1)
            
    except asyncio.CancelledError:
        print("🛑 Bot cancelled")
    except Exception as e:
        print(f"❌ Telegram Bot error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
        except:
            pass

def run_bot_in_thread():
    """Chạy Telegram bot trong thread riêng"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(start_telegram_bot())
    except Exception as e:
        print(f"❌ Telegram Bot error: {e}")
    finally:
        loop.close()

if __name__ == '__main__':
    # Khởi động scheduler để gửi metrics định kỳ
    if write_api:
        scheduler = BackgroundScheduler()
        scheduler.add_job(func=scheduled_collect, trigger="interval", seconds=COLLECTION_INTERVAL)
        scheduler.start()
        print(f"📊 Scheduler started - collecting metrics every {COLLECTION_INTERVAL} seconds")
    
    # Khởi động Telegram Bot trong thread riêng
    if TELEGRAM_BOT_TOKEN:
        bot_thread = threading.Thread(target=run_bot_in_thread, daemon=True)
        bot_thread.start()
    
    try:
        app.run(host='0.0.0.0', port=1232, debug=False)
    except (KeyboardInterrupt, SystemExit):
        if write_api:
            scheduler.shutdown()
            influxdb_client.close()
        print("\n👋 Server stopped")