from flask import Flask, render_template, jsonify, request
import subprocess
import time
from crontab_manager import (
    get_all_schedules, add_schedule, delete_schedule, 
    update_schedule, toggle_schedule, get_next_schedules
)
from settings import CONFIG
from timer_manager import TimerManager

app = Flask(__name__)

def get_hostname():
    """获取主机名"""
    try:
        with open('/proc/sys/kernel/hostname', 'r') as f:
            return f.read().strip()
    except Exception:
        return 'unknown'

def log_timer_start():
    """记录定时开启的实际开始时间"""
    try:
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        with open(CONFIG.timer_log_file, 'a', encoding='utf-8') as f:
            f.write(f"{timestamp} - START\n")
    except Exception as e:
        print(f"写入日志失败: {e}")

def log_timer_stop():
    """记录定时关闭的实际时间"""
    try:
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        with open(CONFIG.timer_log_file, 'a', encoding='utf-8') as f:
            f.write(f"{timestamp} - STOP\n")
    except Exception as e:
        print(f"写入日志失败: {e}")

def get_timer_logs():
    """获取所有定时开启日志"""
    try:
        if CONFIG.timer_log_file.exists():
            with open(CONFIG.timer_log_file, 'r', encoding='utf-8') as f:
                return f.read().strip().split('\n')
        return []
    except Exception as e:
        print(f"读取日志失败: {e}")
        return []

def run_status_command():
    """执行 status 命令（组合命令）"""
    try:
        result1 = subprocess.run(
            CONFIG.status_command,
            capture_output=True,
            text=True,
            timeout=CONFIG.command_timeout_seconds
        )
        
        result2 = subprocess.run(
            [CONFIG.brctl_command, 'show'],
            capture_output=True,
            text=True,
            timeout=CONFIG.command_timeout_seconds
        )
        
        # 合并输出
        stdout = result1.stdout
        if result2.stdout:
            stdout += '\n' + result2.stdout
        
        # 只要 ip link 命令成功就算成功
        success = result1.returncode == 0
        
        return {
            'success': success,
            'stdout': stdout.strip(),
            'stderr': (result1.stderr + '\n' + result2.stderr).strip(),
            'returncode': result1.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'stdout': '',
            'stderr': 'Command timed out',
            'returncode': -1
        }
    except Exception as e:
        return {
            'success': False,
            'stdout': '',
            'stderr': str(e),
            'returncode': -1
        }

def run_command(cmd):
    """执行系统命令"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=CONFIG.command_timeout_seconds
        )
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout.strip(),
            'stderr': result.stderr.strip(),
            'returncode': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'stdout': '',
            'stderr': 'Command timed out',
            'returncode': -1
        }
    except Exception as e:
        return {
            'success': False,
            'stdout': '',
            'stderr': str(e),
            'returncode': -1
        }

def parse_iptv_status(output):
    """
    解析 iptv-status 输出，判断 IPTV 状态
    ON: 指定网卡包含 <...UP...>
    OFF: 指定网卡不包含 UP
    """
    for line in output.split('\n'):
        if f'{CONFIG.interface}:' in line:
            if 'UP' in line:
                return 'on'
            else:
                return 'off'
    return 'unknown'

def get_current_status():
    """获取当前 IPTV 状态"""
    result = run_status_command()
    print(f"Status command result: success={result['success']}, stdout={result['stdout'][:100]}...")
    if result['success']:
        status = parse_iptv_status(result['stdout'])
        print(f"Parsed status: {status}")
        return status
    print(f"Status command failed: {result['stderr']}")
    return 'unknown'

timer_manager = TimerManager(
    config=CONFIG,
    command_runner=run_command,
    on_start=log_timer_start,
    on_stop=log_timer_stop,
)

def get_timer_status():
    """获取定时关闭状态"""
    return timer_manager.get_remaining()

def cancel_timer():
    """取消定时关闭"""
    cancelled = timer_manager.cancel()
    if cancelled:
        log_timer_stop()
    return cancelled

def should_skip_crontab_off():
    """
    检查是否应该跳过 crontab 的关闭操作
    如果手动定时关闭还在运行中，则跳过
    """
    return timer_manager.should_skip_crontab_off()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/schedule')
def schedule_page():
    return render_template('schedule.html')

@app.route('/api/iptv/status/current')
def iptv_current_status():
    """获取当前 IPTV 状态"""
    status = get_current_status()
    timer_remaining = get_timer_status()
    
    # 获取下一个开启和关闭 schedule（一次性读取，避免不一致）
    next_on, next_off = get_next_schedules()
    
    # 构建返回数据，按时间排序
    next_schedules = []
    
    if next_on:
        next_schedules.append({
            'action': 'on',
            'label': '开启',
            'time': next_on['time'].strftime('%H:%M'),
            'date': next_on['time'].strftime('%Y-%m-%d'),
            'weekday': next_on['schedule']['weekday']
        })
    
    if next_off:
        next_schedules.append({
            'action': 'off',
            'label': '关闭',
            'time': next_off['time'].strftime('%H:%M'),
            'date': next_off['time'].strftime('%Y-%m-%d'),
            'weekday': next_off['schedule']['weekday']
        })
    
    # 按时间排序
    next_schedules.sort(key=lambda x: x['date'] + x['time'])
    
    return jsonify({
        'status': status,
        'timer_remaining': timer_remaining,
        'next_schedules': next_schedules,
        'skip_crontab': should_skip_crontab_off(),
        'hostname': get_hostname()
    })

@app.route('/api/iptv/timer/<int:minutes>')
def set_timer(minutes):
    """设置开启后定时关闭"""
    if minutes <= 0:
        return jsonify({'error': 'Invalid minutes'}), 400

    timer_manager.start(minutes)
    
    return jsonify({
        'success': True,
        'minutes': minutes,
        'message': f'已开启 IPTV，将在 {minutes} 分钟后自动关闭'
    })

@app.route('/api/iptv/timer/cancel')
def cancel_timer_api():
    """取消定时关闭"""
    cancelled = cancel_timer()
    return jsonify({
        'success': cancelled,
        'message': '定时关闭已取消' if cancelled else '没有正在进行的定时任务'
    })

@app.route('/api/iptv/logs')
def get_logs_api():
    """获取定时开启日志"""
    logs = get_timer_logs()
    return jsonify({
        'logs': logs
    })

@app.route('/api/iptv/<action>')
def iptv_control(action):
    if action == 'status':
        result = run_status_command()
        if result['success']:
            result['iptv_state'] = parse_iptv_status(result['stdout'])
        return jsonify(result)
    
    if action not in CONFIG.iptv_commands:
        return jsonify({'error': 'Invalid action'}), 400
    
    # 如果是关闭操作，先取消定时任务
    if action == 'off':
        cancel_timer()
    
    result = run_command(CONFIG.iptv_commands[action])
    return jsonify(result)

# ==================== Schedule API ====================

@app.route('/api/schedules', methods=['GET'])
def get_schedules():
    """获取所有 schedules"""
    schedules = get_all_schedules()
    return jsonify({'schedules': schedules})

@app.route('/api/schedules', methods=['POST'])
def create_schedule():
    """创建新 schedule"""
    data = request.get_json()
    
    schedule = {
        'minute': str(data.get('minute', 0)),
        'hour': str(data.get('hour', 0)),
        'day': data.get('day', '*'),
        'month': data.get('month', '*'),
        'weekday': data.get('weekday', '*'),
        'action': data.get('action', 'off'),
        'enabled': data.get('enabled', True)
    }
    
    # 构建命令（关闭操作会使用检查脚本）
    if schedule['action'] == 'on':
        schedule['command'] = CONFIG.schedule_on_command
    else:
        schedule['command'] = str(CONFIG.check_off_script)
    
    if add_schedule(schedule):
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': '添加失败'}), 500

@app.route('/api/schedules/<schedule_id>', methods=['PUT'])
def update_schedule_api(schedule_id):
    """更新 schedule"""
    data = request.get_json()
    
    updates = {
        'minute': str(data.get('minute', 0)),
        'hour': str(data.get('hour', 0)),
        'day': data.get('day', '*'),
        'month': data.get('month', '*'),
        'weekday': data.get('weekday', '*'),
        'action': data.get('action', 'off'),
        'enabled': data.get('enabled', True)
    }
    
    if update_schedule(schedule_id, updates):
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': '更新失败'}), 500

@app.route('/api/schedules/<schedule_id>', methods=['DELETE'])
def delete_schedule_api(schedule_id):
    """删除 schedule"""
    if delete_schedule(schedule_id):
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': '删除失败'}), 500

@app.route('/api/schedules/<schedule_id>/toggle', methods=['POST'])
def toggle_schedule_api(schedule_id):
    """切换 schedule 使能状态"""
    if toggle_schedule(schedule_id):
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': '切换失败'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
