#!/bin/bash
# 订阅服务端 - 自动部署与启动脚本

# 确保以 root 权限运行
if [ "$EUID" -ne 0 ]; then
  echo "请使用 root 权限运行此脚本 (Please run as root)"
  exit
fi

echo "==================================="
echo "1. 检查并安装 Python3"
echo "==================================="
if ! command -v python3 &> /dev/null
then
    echo "未检测到 Python3，正在执行安装..."
    apt-get update
    apt-get install -y python3
else
    echo "Python3 已安装！"
fi

# 交互式获取订阅密码
echo ""
read -p "请输入订阅后台管理密码 (SUB_PASS): " SUB_PASS
read -p "请输入 Akile Cloud Client ID (AKILE_CLIENT): " AKILE_CLIENT
read -p "请输入 Akile Cloud Secret (AKILE_SECRET): " AKILE_SECRET

echo ""
echo "==================================="
echo "2. 配置服务文件"
echo "==================================="
# 创建下载与配置目录
mkdir -p /root/sub_server
cd /root/sub_server

GITHUB_RAW_URL="https://raw.githubusercontent.com/318182456/sub_server/main"

# 强制下载最新的 sub_server.py
echo "正在从 GitHub 获取最新的 sub_server.py..."
curl -sL ${GITHUB_RAW_URL}/sub_server.py -o sub_server.py

# 强制下载最新的 sub-server.service
echo "正在从 GitHub 获取最新的 sub-server.service..."
curl -sL ${GITHUB_RAW_URL}/sub-server.service -o sub-server.service

if [ ! -f "./sub_server.py" ]; then
    echo "错误：无法获取 sub_server.py，请检查网络！"
    exit 1
fi

# 创建业务目录
mkdir -p /root/agsbx/

# 从子文件夹拷贝代码
cp ./sub_server.py /root/agsbx/sub_server.py
chmod +x /root/agsbx/sub_server.py

# 确保 jh.txt 文件存在（防止启动报错）
if [ ! -f "/root/agsbx/jh.txt" ]; then
    echo "注意: 未检测到 /root/agsbx/jh.txt，已自动创建一个空文件"
    touch /root/agsbx/jh.txt
fi

echo ""
echo "==================================="
echo "3. 配置自启动 Systemd 服务"
echo "==================================="
cat <<EOF > /etc/systemd/system/sub-server.service
[Unit]
Description=Node Subscription Python Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/agsbx
ExecStart=/usr/bin/python3 /root/agsbx/sub_server.py
Restart=always
RestartSec=3
Environment=SUB_PASS=$SUB_PASS
Environment=AKILE_CLIENT=$AKILE_CLIENT
Environment=AKILE_SECRET=$AKILE_SECRET

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable sub-server.service
systemctl restart sub-server.service

echo ""
echo "==================================="
echo "        🎉 部署完成！ 🎉           "
echo "==================================="
echo "服务已经设置在开机时自动启动。"
echo "正在监听端口: 8080"
echo ""
echo "获取您的公网IP中..."
PUBLIC_IP=$(curl -s ifconfig.me)
if [ -z "$PUBLIC_IP" ]; then
    PUBLIC_IP="您的服务器IP"
fi

echo "您的订阅链接是: http://${PUBLIC_IP}:8080/${SUB_PASS}"
echo "（如果无法访问，请检查服务器防火墙/安全组是否放行了 8080 端口）"
echo ""
echo "【常用命令】"
echo "查看服务状态: systemctl status sub-server.service"
echo "重启服务    : systemctl restart sub-server.service"
echo "查看日志    : journalctl -fu sub-server.service"
echo "==================================="
