import http.server
import socketserver
import base64
import os
import urllib.parse
import json
import re

# 配置项
PORT = 8080
FILE_PATH = "/root/agsbx/jh.txt"
SUB_PASS = os.getenv("SUB_PASS", "") # 从环境变量读取订阅密码

def parse_node(uri):
    """简单解析常见的订阅链接 URI"""
    try:
        if uri.startswith('vmess://'):
            data = json.loads(base64.b64decode(uri[8:]).decode('utf-8'))
            node = {
                'name': data.get('ps', 'vmess-node'),
                'type': 'vmess',
                'server': data.get('add'),
                'port': int(data.get('port', 443)),
                'uuid': data.get('id'),
                'alterId': int(data.get('aid', 0)),
                'cipher': data.get('scy', 'auto'),
                'udp': True,
                'tls': data.get('tls') == 'tls',
                'network': data.get('net', 'tcp')
            }
            if node['tls']:
                node['servername'] = data.get('sni') or data.get('host')
                if data.get('fp'): node['client-fingerprint'] = data.get('fp')
                if data.get('alpn'): node['alpn'] = data.get('alpn').split(',') if isinstance(data.get('alpn'), str) else data.get('alpn')
                node['skip-cert-verify'] = True # 针对 Argo 等不稳定节点默认跳过证书验证
                
            if node['network'] == 'ws':
                node['packet-encoding'] = 'packet'
                path = data.get('path', '/')
                if not path.startswith('/'): path = '/' + path
                node['ws-opts'] = {
                    'path': path
                }
                if data.get('host'): node['ws-opts']['headers'] = {'Host': data.get('host')}
            elif node['network'] == 'h2':
                node['h2-opts'] = {'path': data.get('path', '/'), 'host': [data.get('host')] if data.get('host') else []}
            elif node['network'] == 'grpc':
                node['grpc-opts'] = {'grpc-service-name': data.get('path', '')}
            elif node['network'] == 'xhttp':
                node['packet-encoding'] = 'xudp'
                node['xhttp-opts'] = {'path': data.get('path', '/'), 'mode': data.get('mode', 'auto')}
                if data.get('host'): node['xhttp-opts']['headers'] = {'Host': data.get('host')}
            return node
            
        elif uri.startswith(('vless://', 'anytls://', 'any-reality://')):
            # 处理协议头
            if uri.startswith('vless://'):
                rest = uri[8:]
            elif uri.startswith('anytls://'):
                rest = uri[9:]
            else:
                rest = uri[14:]
            
            # 由于 anytls 可能包含特殊字符，直接用正则或 urlparse
            parsed = urllib.parse.urlparse('vless://' + rest)
            params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
            
            userinfo = parsed.netloc.split('@')
            uuid = userinfo[0]
            host_port = userinfo[1].split(':')
            host = host_port[0]
            port = int(host_port[1])
            name = urllib.parse.unquote(parsed.fragment) if parsed.fragment else host
            
            # 修正：根据原始 URI 判定实际协议头，因为接下来 parsed.scheme 会被强制设为 vless
            actual_scheme = 'anytls' if uri.startswith('anytls://') else 'any-reality' if uri.startswith('any-reality://') else 'vless'
            
            # 检测是否为 Reality 或 TLS (即使没有明确的 security 参数)
            is_anytls = actual_scheme in ['anytls', 'any-reality']
            is_reality = params.get('security') == 'reality' or bool(params.get('pbk')) or actual_scheme == 'any-reality'
            is_tls = params.get('security') == 'tls' or is_reality or bool(params.get('flow')) or is_anytls
            
            node = {
                'name': name,
                'type': 'vless',
                'server': host,
                'port': port,
                'uuid': uuid,
                'encryption': params.get('encryption', 'none'),
                'udp': True,
                'tls': is_tls,
                'network': params.get('type', 'tcp'),
                'servername': params.get('sni') or params.get('host') or host,
                'client-fingerprint': params.get('fp', 'chrome')
            }
            
            if is_tls:
                node['skip-cert-verify'] = True 
            
            if is_reality:
                node['reality'] = True
                node['reality-opts'] = {
                    'public-key': params.get('pbk', ''),
                    'short-id': params.get('sid', '')
                }
            
            # 只有 TCP 网络才能使用 xtls-rprx-vision 流控
            if params.get('flow') and node['network'] == 'tcp':
                node['flow'] = params.get('flow')
            
            if node['network'] == 'ws':
                node['packet-encoding'] = 'xudp' # 针对 argosbx 的 VLESS-WS-ENC 进行优化
                path = params.get('path', '/')
                if not path.startswith('/'): path = '/' + path
                node['ws-opts'] = {
                    'path': path
                }
                if params.get('host'): node['ws-opts']['headers'] = {'Host': params.get('host')}
            elif node['network'] == 'grpc':
                 node['grpc-opts'] = {'grpc-service-name': params.get('serviceName', '')}
            elif node['network'] == 'xhttp':
                node['packet-encoding'] = 'xudp'
                path = params.get('path', '/')
                if not path.startswith('/'): path = '/' + path
                node['xhttp-opts'] = {
                    'path': path,
                    'mode': params.get('mode', 'auto')
                }
                if params.get('host'): node['xhttp-opts']['headers'] = {'Host': params.get('host')}
            return node
        elif uri.startswith('ss://'):
            # ss://base64(method:password)@host:port#name
            parsed = urllib.parse.urlparse(uri)
            name = urllib.parse.unquote(parsed.fragment) if parsed.fragment else 'ss-node'
            if '@' in parsed.netloc:
                userinfo_encoded, endpoint = parsed.netloc.split('@')
                userinfo = base64.b64decode(userinfo_encoded).decode('utf-8')
                method, password = userinfo.split(':')
                host, port = endpoint.split(':')
            else:
                userinfo = base64.b64decode(parsed.netloc).decode('utf-8')
                method, password, host, port = re.split('[:@]', userinfo)
            
            return {
                'name': name,
                'type': 'ss',
                'server': host,
                'port': int(port),
                'cipher': method,
                'password': password,
                'udp': True
            }
        elif uri.startswith('hysteria2://'):
            # hysteria2://password@host:port?query#name
            parsed = urllib.parse.urlparse(uri)
            params = urllib.parse.parse_qs(parsed.query)
            password, endpoint = parsed.netloc.split('@')
            host, port = endpoint.split(':')
            name = urllib.parse.unquote(parsed.fragment) if parsed.fragment else host
            return {
                'name': name,
                'type': 'hysteria2',
                'server': host,
                'port': int(port),
                'password': password,
                'sni': params.get('sni', [host])[0],
                'skip-cert-verify': params.get('insecure', ['0'])[0] == '1' or params.get('allowInsecure', ['0'])[0] == '1',
                'alpn': params.get('alpn', ['h3'])[0].split(',')
            }
        elif uri.startswith('tuic://'):
            # tuic://uuid:password@host:port?query#name
            parsed = urllib.parse.urlparse(uri)
            params = urllib.parse.parse_qs(parsed.query)
            userinfo, endpoint = parsed.netloc.split('@')
            uuid, password = userinfo.split(':')
            host, port = endpoint.split(':')
            name = urllib.parse.unquote(parsed.fragment) if parsed.fragment else host
            return {
                'name': name,
                'type': 'tuic',
                'server': host,
                'port': int(port),
                'uuid': uuid,
                'password': password,
                'sni': params.get('sni', [host])[0],
                'skip-cert-verify': params.get('allowInsecure', ['0'])[0] == '1',
                'alpn': params.get('alpn', ['h3'])[0].split(','),
                'congestion-controller': params.get('congestion_control', ['bbr'])[0],
                'udp-relay-mode': params.get('udp_relay_mode', ['native'])[0]
            }
    except Exception as e:
        print(f"解析节点失败: {uri[:20]}... Error: {e}")
    return None

def generate_clash_yaml(nodes):
    """手动构建简单的 Clash YAML 配置文件"""
    proxies = []
    for node in nodes:
        if node:
            proxies.append(node)
    
    if not proxies:
        return "proxies: []"

    # 简易 YAML 序列化 (避免引入依赖)
    def to_yaml(obj, indent=0):
        res = ""
        space = " " * indent
        if isinstance(obj, dict):
            for k, v in obj.items():
                if v is None or v == "": continue
                if isinstance(v, (dict, list)):
                    res += f"{space}{k}:\n{to_yaml(v, indent + 2)}"
                else:
                    val = f'"{v}"' if isinstance(v, str) else str(v).lower() if isinstance(v, bool) else v
                    res += f"{space}{k}: {val}\n"
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    first = True
                    for line in to_yaml(item, indent + 2).splitlines():
                        if first:
                            res += f"{space}- {line.strip()}\n"
                            first = False
                        else:
                            res += f"{line}\n"
                else:
                    res += f"{space}- {item}\n"
        return res

    proxy_names = [p['name'] for p in proxies]
    
    yaml_content = "port: 7890\nsocks-port: 7891\nallow-lan: true\nmode: rule\nlog-level: info\nexternal-controller: :9090\n\n"
    yaml_content += "proxies:\n"
    yaml_content += to_yaml(proxies, 2)
    
    yaml_content += "\nproxy-groups:\n"
    yaml_content += "  - name: 🚀 自动选择\n    type: url-test\n    url: https://www.gstatic.com/generate_204\n    interval: 300\n    proxies:\n"
    for name in proxy_names: yaml_content += f"      - \"{name}\"\n"
    
    yaml_content += "  - name: 🔰 代理选择\n    type: select\n    proxies:\n      - 🚀 自动选择\n      - DIRECT\n"
    for name in proxy_names: yaml_content += f"      - \"{name}\"\n"
    
    yaml_content += "\nrules:\n  - MATCH,🔰 代理选择\n"
    return yaml_content

class SubHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # 解析请求的路径和参数
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.strip('/') # 获取路径并去掉首尾斜杠
        query = parsed_url.query
        
        # 验证密码 (如果设置了 SUB_PASS)
        if SUB_PASS and path != SUB_PASS:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(f"403 Forbidden: Invalid or missing password. Use /{SUB_PASS} for access.".encode('utf-8'))
            return
            
        user_agent = self.headers.get('User-Agent', '').lower()
        is_clash = 'clash' in user_agent or 'mihomo' in user_agent or 'meta' in user_agent or 'clash' in query
        
        self.send_response(200)
        
        if is_clash:
            self.send_header('Content-type', 'application/yaml; charset=utf-8')
        else:
            self.send_header('Content-type', 'text/plain; charset=utf-8')
        
        # 流量统计信息
        self.send_header('Subscription-Userinfo', 'upload=0; download=0; total=1073741824000; expire=2062560867')
        self.end_headers()
        
        if os.path.exists(FILE_PATH):
            try:
                with open(FILE_PATH, 'r', encoding='utf-8') as f:
                    lines = [l.strip() for l in f.readlines() if l.strip()]
                
                if is_clash:
                    nodes = [parse_node(l) for l in lines]
                    content = generate_clash_yaml(nodes)
                    self.wfile.write(content.encode('utf-8'))
                else:
                    content = "\n".join(lines)
                    b64_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
                    self.wfile.write(b64_content.encode('utf-8'))
            except Exception as e:
                msg = f"Error: {e}"
                self.wfile.write(base64.b64encode(msg.encode('utf-8')).decode('utf-8').encode('utf-8') if not is_clash else msg.encode('utf-8'))
        else:
            msg = f"File not found: {FILE_PATH}"
            if is_clash:
                self.wfile.write(msg.encode('utf-8'))
            else:
                self.wfile.write(base64.b64encode(msg.encode('utf-8')))

if __name__ == '__main__':
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), SubHandler) as httpd:
        print(f"订阅服务已启动: http://0.0.0.0:{PORT}")
        print(f"支持格式: V2Ray (Base64) & Clash/Mihomo (YAML)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            httpd.server_close()
