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

echo ""
echo "==================================="
echo "2. 配置服务文件"
echo "==================================="
# 创建需要的目录
mkdir -p /root/agsbx/

GITHUB_RAW_URL="https://raw.githubusercontent.com/318182456/sub_server/main"

# 检查并下载 sub_server.py
if [ ! -f "./sub_server.py" ]; then
    echo "未在本地找到 sub_server.py，正在下载..."
    curl -sL ${GITHUB_RAW_URL}/sub_server.py -o sub_server.py
fi

# 检查并下载 sub-server.service
if [ ! -f "./sub-server.service" ]; then
    echo "未在本地找到 sub-server.service，正在下载..."
    curl -sL ${GITHUB_RAW_URL}/sub-server.service -o sub-server.service
fi

if [ ! -f "./sub_server.py" ]; then
    echo "错误：无法获取 sub_server.py，请检查网络！"
    exit 1
fi

# 拷贝代码
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
if [ ! -f "./sub-server.service" ]; then
    echo "错误：无法获取 sub-server.service，请检查网络！"
    exit 1
fi

cp ./sub-server.service /etc/systemd/system/sub-server.service

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

echo "您的订阅链接是: http://${PUBLIC_IP}:8080/"
echo "（如果无法访问，请检查服务器防火墙/安全组是否放行了 8080 端口）"
echo ""
echo "【常用命令】"
echo "查看服务状态: systemctl status sub-server.service"
echo "重启服务    : systemctl restart sub-server.service"
echo "查看日志    : journalctl -fu sub-server.service"
echo "==================================="
