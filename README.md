# IPTV 控制器

通过 Web 界面控制家里 IPTV 的开关，支持定时关闭和计划管理。

## 功能特性

- 📺 实时显示 IPTV 状态（开启/关闭）
- ⏰ 开启后定时关闭（10/20/30分钟）
- 📅 计划管理（基于 crontab）
- 🔄 手动定时与计划冲突检测
- � 观看记录（日志查看、日期筛选、统计）
- �📱 移动端优化界面

## 项目结构

```
iptvctl/
├── app.py                 # Flask 后端
├── crontab_manager.py     # crontab 管理模块
├── check_and_off.sh       # 关闭前检查脚本
├── requirements.txt       # Python 依赖
├── timer_log.txt          # 定时开启日志（自动生成）
├── templates/
│   ├── index.html         # 主控制页面
│   └── schedule.html      # 计划管理页面
└── README.md              # 说明文档
```

## 安装步骤

### 1. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 2. 确保脚本有执行权限

```bash
chmod +x check_and_off.sh
```

### 3. 以 root 身份运行（推荐）

由于需要执行 `ip link` 和 `crontab` 命令，建议以 root 身份运行服务。

**使用 systemd 服务：**

创建服务文件 `/etc/systemd/system/iptvctl.service`：

```ini
[Unit]
Description=IPTV Controller
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/iptvctl
ExecStart=/usr/bin/python3 /path/to/iptvctl/app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启用并启动服务：

```bash
sudo systemctl enable iptvctl
sudo systemctl start iptvctl
```

## 运行

### 开发模式

```bash
python app.py
```

访问 http://localhost:5000

## 使用说明

### 主页面

- **状态显示**：实时显示 IPTV 当前状态
- **开启/关闭按钮**：手动控制 IPTV
- **定时按钮**：开启 IPTV 并在指定时间后自动关闭
- **下次计划操作**：显示最近的开启和关闭计划（按时间排序）
- **观看记录**：查看定时开启历史，支持日期筛选和统计

### 计划管理页面

- 添加、编辑、删除定时任务
- 启用/禁用任务
- 支持按星期设置重复规则
- 按下次执行时间排序显示

### 观看记录

- **表格显示**：序号、日期时间、操作
- **分页功能**：每页显示 5 条记录
- **日期筛选**：选择日期查看当天记录
- **统计功能**：显示选定日期的总观看分钟数
- **智能日期显示**：今天/昨天/具体日期

### 冲突检测

当手动开启定时关闭功能时（如开启10分钟），计划中的关闭操作会被跳过，避免冲突。

## API 接口

### IPTV 控制

- `GET /api/iptv/on` - 开启 IPTV
- `GET /api/iptv/off` - 关闭 IPTV
- `GET /api/iptv/status/current` - 获取当前状态（包含下次计划操作）
- `GET /api/iptv/timer/<minutes>` - 设置开启后定时关闭
- `GET /api/iptv/timer/cancel` - 取消定时关闭
- `GET /api/iptv/logs` - 获取观看记录

### 计划管理

- `GET /api/schedules` - 获取所有计划
- `POST /api/schedules` - 创建计划
- `PUT /api/schedules/<id>` - 更新计划
- `DELETE /api/schedules/<id>` - 删除计划
- `POST /api/schedules/<id>/toggle` - 切换启用状态

## 注意事项

1. 项目需要 root 权限运行（用于执行 `ip link` 和 `crontab` 命令）
2. 确保 `check_and_off.sh` 有执行权限
3. 计划基于系统 crontab 实现
4. 项目目录可以部署在任意位置
5. 日志文件 `timer_log.txt` 会自动生成在项目目录

## 日志查看

```bash
# 如果使用 systemd
sudo journalctl -u iptvctl -f

# 系统日志
sudo tail -f /var/log/syslog | grep IPTV
```

## 技术说明

- **后端**：Flask + Python 3
- **前端**：原生 HTML/CSS/JavaScript
- **定时任务**：系统 crontab
- **日志存储**：文本文件
- **冲突检测**：通过 `/tmp/iptv_manual_timer` 标志文件实现
