"""
Crontab 管理模块 - 用于管理 IPTV 的定时开关规则
"""
import subprocess
from datetime import datetime, timedelta
from settings import CONFIG

CRONTAB_MARKER_START = CONFIG.crontab_marker_start
CRONTAB_MARKER_END = CONFIG.crontab_marker_end


def get_crontab():
    """获取当前用户的 crontab"""
    try:
        result = subprocess.run(
            ['crontab', '-l'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout
        return ""
    except Exception:
        return ""


def set_crontab(content):
    """设置 crontab"""
    try:
        # 通过管道写入 crontab
        proc = subprocess.Popen(
            ['crontab', '-'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = proc.communicate(input=content, timeout=10)
        return proc.returncode == 0
    except Exception as e:
        print(f"Set crontab error: {e}")
        return False


def split_crontab_sections(crontab_content):
    """拆分托管区块和其他 crontab 内容"""
    lines = crontab_content.splitlines()
    before = []
    managed = []
    after = []
    in_managed_block = False
    managed_found = False

    for line in lines:
        if line.strip() == CRONTAB_MARKER_START:
            managed_found = True
            in_managed_block = True
            continue
        if line.strip() == CRONTAB_MARKER_END:
            in_managed_block = False
            continue

        if in_managed_block:
            managed.append(line)
        elif managed_found:
            after.append(line)
        else:
            before.append(line)

    return before, managed, after, managed_found


def replace_managed_block(crontab_content, managed_lines):
    """只替换 IPTV 托管区块，保留其他 crontab 内容"""
    before, _, after, managed_found = split_crontab_sections(crontab_content)
    output = []

    if before:
        output.extend(before)

    if managed_lines:
        if output and output[-1] != "":
            output.append("")
        output.append(CRONTAB_MARKER_START)
        output.extend(managed_lines)
        output.append(CRONTAB_MARKER_END)

    if after:
        if output and output[-1] != "":
            output.append("")
        output.extend(after)

    if managed_found and not managed_lines and output and output[-1] == "":
        output.pop()

    content = "\n".join(output).rstrip()
    return f"{content}\n" if content else ""


def extract_iptv_schedules(crontab_content):
    """从 crontab 托管区块中提取 IPTV schedule"""
    schedules = []

    _, managed_lines, _, _ = split_crontab_sections(crontab_content)

    for index, line in enumerate(managed_lines):
        stripped_line = line.strip()
        if not stripped_line:
            continue

        schedule = parse_crontab_line(stripped_line)
        if schedule:
            schedule['id'] = str(index)
            schedule['raw'] = line
            schedules.append(schedule)
    
    return schedules


def parse_crontab_line(line):
    """解析单行 crontab 条目"""
    # 格式: m h dom mon dow command
    # 示例: 0 17 * * 1-5 /sbin/ip link set eth3 down
    # 被禁用的: # 0 17 * * 1-5 /sbin/ip link set eth3 down
    
    # 检查是否被禁用（前面有 #）
    enabled = not line.strip().startswith('#')
    
    # 去掉开头的 # 和空格后再解析
    clean_line = line.lstrip('# ').strip()
    parts = clean_line.split()
    if len(parts) < 6:
        return None
    
    minute, hour, day, month, weekday = parts[:5]
    command = ' '.join(parts[5:])
    
    # 判断是开启还是关闭
    if 'up' in command:
        action = 'on'
    elif 'check_and_off' in command:
        action = 'off'
    else:
        action = 'off'
    
    return {
        'id': None,
        'minute': minute,
        'hour': hour,
        'day': day,
        'month': month,
        'weekday': weekday,
        'action': action,
        'command': command,
        'enabled': enabled,
        'raw': line
    }
def build_crontab_line(schedule):
    """从 schedule 字典构建 crontab 行"""
    if schedule.get('action') == 'off':
        command = str(CONFIG.check_off_script)
    else:
        command = schedule.get('command', CONFIG.schedule_on_command)
    
    line = f"{schedule['minute']} {schedule['hour']} {schedule['day']} {schedule['month']} {schedule['weekday']} {command}"
    if not schedule.get('enabled', True):
        line = f"# {line}"
    return line


def get_all_schedules():
    """获取所有 IPTV schedules，按今天优先和当天时刻排序"""
    crontab = get_crontab()
    schedules = extract_iptv_schedules(crontab)
    today = datetime.now().weekday()

    def sort_key(schedule):
        try:
            weekdays = parse_weekday(schedule['weekday'])
            day_offsets = sorted((weekday - today) % 7 for weekday in weekdays)
            nearest_day_offset = day_offsets[0] if day_offsets else 7
            return (
                nearest_day_offset,
                int(str(schedule['hour']).strip()),
                int(str(schedule['minute']).strip()),
                0 if schedule.get('action') == 'on' else 1,
            )
        except (ValueError, TypeError):
            return (99, 99, 99, 99)

    schedules.sort(key=sort_key)
    return schedules


def add_schedule(schedule):
    """添加新的 schedule 到 crontab"""
    crontab = get_crontab()
    _, managed_lines, _, _ = split_crontab_sections(crontab)
    managed_lines.append(build_crontab_line(schedule))
    return set_crontab(replace_managed_block(crontab, managed_lines))


def delete_schedule(schedule_id):
    """删除指定 schedule"""
    crontab = get_crontab()
    schedules = extract_iptv_schedules(crontab)
    
    # 找到要删除的 schedule
    target = next((s for s in schedules if s['id'] == schedule_id), None)
    
    if not target:
        return False
    
    _, managed_lines, _, _ = split_crontab_sections(crontab)
    delete_index = int(schedule_id)
    if delete_index < 0 or delete_index >= len(managed_lines):
        return False

    new_managed_lines = [
        line for index, line in enumerate(managed_lines)
        if index != delete_index
    ]

    if len(new_managed_lines) == len(managed_lines):
        return False

    return set_crontab(replace_managed_block(crontab, new_managed_lines))


def update_schedule(schedule_id, updates):
    """更新 schedule"""
    # 先删除旧的，再添加新的
    if not delete_schedule(schedule_id):
        return False
    
    new_schedule = {
        'minute': updates.get('minute', '0'),
        'hour': updates.get('hour', '0'),
        'day': updates.get('day', '*'),
        'month': updates.get('month', '*'),
        'weekday': updates.get('weekday', '*'),
        'action': updates.get('action', 'off'),
        'enabled': updates.get('enabled', True)
    }
    
    # 构建命令（关闭操作会使用检查脚本）
    if new_schedule['action'] == 'on':
        new_schedule['command'] = CONFIG.schedule_on_command
    else:
        new_schedule['command'] = str(CONFIG.check_off_script)
    
    return add_schedule(new_schedule)


def toggle_schedule(schedule_id):
    """切换 schedule 的使能状态"""
    crontab = get_crontab()
    schedules = extract_iptv_schedules(crontab)
    
    target = next((s for s in schedules if s['id'] == schedule_id), None)
    
    if not target:
        return False
    
    # 切换状态
    target['enabled'] = not target['enabled']
    
    old_line = target['raw']
    if target['enabled']:
        new_line = old_line.lstrip('# ')
    else:
        if not old_line.strip().startswith('#'):
            new_line = f"# {old_line}"
        else:
            new_line = old_line

    _, managed_lines, _, _ = split_crontab_sections(crontab)
    toggle_index = int(schedule_id)
    if toggle_index < 0 or toggle_index >= len(managed_lines):
        return False

    replaced = managed_lines[:]
    replaced[toggle_index] = new_line
    return set_crontab(replace_managed_block(crontab, replaced))


def get_next_schedule():
    """获取下一个将要执行的关闭 schedule（兼容旧代码）"""
    return get_next_schedule_by_action('off')


def get_next_schedule_by_action(action='off', schedules=None):
    """获取下一个将要执行的指定类型的 schedule"""
    # 如果未提供 schedules，则从 crontab 获取
    if schedules is None:
        crontab = get_crontab()
        schedules = extract_iptv_schedules(crontab)
    
    now = datetime.now()
    next_schedule = None
    
    for s in schedules:
        if not s.get('enabled', True):
            continue
        if s['action'] != action:
            continue
        
        # 计算下一次执行时间
        next_time = calculate_next_run(s, now)
        if next_time:
            if next_schedule is None or next_time < next_schedule['time']:
                next_schedule = {
                    'schedule': s,
                    'time': next_time
                }
    
    return next_schedule


def get_next_schedules():
    """一次性获取下一个开启和关闭 schedule（避免重复读取 crontab）"""
    crontab = get_crontab()
    schedules = extract_iptv_schedules(crontab)
    
    next_on = get_next_schedule_by_action('on', schedules)
    next_off = get_next_schedule_by_action('off', schedules)
    
    return next_on, next_off


def calculate_next_run(schedule, from_time):
    """计算 schedule 的下一次执行时间"""
    try:
        hour = int(schedule['hour'])
        minute = int(schedule['minute'])
        
        # 解析 weekday (支持 1-5 或 0,6 等格式)
        weekdays = parse_weekday(schedule['weekday'])
        
        # 从当前时间开始，找到下一次执行
        check_time = from_time.replace(second=0, microsecond=0)
        
        for _ in range(8):  # 最多检查8天
            if check_time.weekday() in weekdays:
                # 检查时间是否已过
                run_time = check_time.replace(hour=hour, minute=minute)
                if run_time > from_time:
                    return run_time
            
            # 检查明天同一时间
            check_time += timedelta(days=1)
        
        return None
    except Exception:
        return None


def parse_weekday(weekday_str):
    """解析 weekday 字符串为列表，转换为 Python weekday 格式（0=周一）"""
    weekdays = []
    
    # 支持格式: * 或 1-5 或 0,6 或 1,3,5
    # crontab: 0=周日, 1=周一, 2=周二...
    # Python: 0=周一, 1=周二, ... 6=周日
    if weekday_str == '*':
        return list(range(7))
    
    parts = weekday_str.split(',')
    for part in parts:
        if '-' in part:
            start, end = part.split('-')
            # 转换 crontab weekday 到 Python weekday
            for i in range(int(start), int(end) + 1):
                weekdays.append(cron_to_python_weekday(i))
        else:
            weekdays.append(cron_to_python_weekday(int(part)))
    
    return weekdays


def cron_to_python_weekday(cron_wd):
    """将 crontab weekday (0=周日) 转换为 Python weekday (0=周一)"""
    # crontab: 0=周日, 1=周一, 2=周二, 3=周三, 4=周四, 5=周五, 6=周六
    # Python:  0=周一, 1=周二, 2=周三, 3=周四, 4=周五, 5=周六, 6=周日
    if cron_wd == 0:
        return 6  # 周日 -> 6
    else:
        return cron_wd - 1  # 周一到周六 -> 0到5
