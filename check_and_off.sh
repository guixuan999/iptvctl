#!/bin/bash
# 检查是否应该执行关闭操作
# 如果手动定时还在运行中，则跳过

# 检查标志文件是否存在（手动定时运行时创建）
if [ -f /tmp/iptv_manual_timer ]; then
    # 检查文件修改时间是否在10分钟内（定时最长30分钟）
    if [ $(($(date +%s) - $(stat -c %Y /tmp/iptv_manual_timer))) -lt 1800 ]; then
        /usr/bin/logger "IPTV SKIP: manual timer is running"
        exit 0
    fi
fi

# 执行关闭
/sbin/ip link set ens1 down
/usr/bin/logger "IPTV BLOCKED: by schedule"
