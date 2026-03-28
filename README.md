# Proxy Subscription Service Server (Sub Server)

A lightweight HTTP service to serve proxy node configurations (e.g. from a local `jh.txt` file) encoded in Base64 formatting compatible with clients like Mihomo and v2rayN.

## 一键安装脚本 (Debian / Ubuntu 系列系统)

以 **root** 用户身份连接到您的 Debian/Ubuntu 服务器，然后执行以下一键安装命令：

```bash
apt-get update && apt-get install -y curl && bash <(curl -sL https://raw.githubusercontent.com/318182456/sub_server/main/install.sh)
```

### 其他安装方式 (Git Clone)

如果您希望克隆此仓库进行安装：

```bash
apt-get update && apt-get install -y git && git clone https://github.com/318182456/sub_server.git && cd sub_server && chmod +x install.sh && ./install.sh
```

### 安装过程说明：

1. 自动检查并安装 `python3` 和 `curl`。
2. 将核心脚本 `sub_server.py` 部署到 `/root/agsbx/` 目录下。
3. 检查并生成 `/root/agsbx/jh.txt` 节点空文件（您可以往里面写入代理或者订阅的节点信息，每行一个节点）。
4. 注册并配置系统的 Systemd 服务 (`sub-server.service`) 实现开机自启动。
5. 脚本运行完成后会输出包含公网IP的订阅链接，例如 `http://<您的IP>:8080/`。

## 客户端支持

本服务端支持多种客户端，并能自动识别：

- **V2Ray / v2rayN / Shadowrocket**: 默认返回 Base64 编码的节点列表。
- **Clash / Mihomo / Clash Meta**: 自动识别 User-Agent 并返回 **YAML** 配置文件。
  - 如果自动识别失效，可以在链接末尾添加 `?clash=1` 手动强制返回 YAML 格式，例如：`http://<您的IP>:8080/?clash=1`

## 常用命令

*   **查看服务运行状态**: `systemctl status sub-server.service`
*   **重启服务**: `systemctl restart sub-server.service`
*   **停止服务**: `systemctl stop sub-server.service`
*   **查看运行日志**: `journalctl -fu sub-server.service`

## 节点添加

直接编辑 `/root/agsbx/jh.txt` 文件，每行添加一个代理链接（如 `vmess://...` 或 `vless://...` 等）。修改完成后会自动生效。
