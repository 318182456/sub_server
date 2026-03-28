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

def parse_node(uri):
    """简单解析常见的订阅链接 URI"""
    try:
        if uri.startswith('vmess://'):
            data = json.loads(base64.b64decode(uri[8:]).decode('utf-8'))
            return {
                'name': data.get('ps', 'vmess-node'),
                'type': 'vmess',
                'server': data.get('add'),
                'port': int(data.get('port', 443)),
                'uuid': data.get('id'),
                'alterId': int(data.get('aid', 0)),
                'cipher': data.get('scy', 'auto'),
                'udp': True,
                'tls': data.get('tls') == 'tls',
                'sni': data.get('sni'),
                'network': data.get('net', 'tcp'),
                'ws-opts': {'path': data.get('path'), 'headers': {'Host': data.get('host')}} if data.get('net') == 'ws' else None
            }
        elif uri.startswith('vless://'):
            parsed = urllib.parse.urlparse(uri)
            params = urllib.parse.parse_qs(parsed.query)
            # vless://uuid@host:port?query#name
            userinfo = parsed.netloc.split('@')
            uuid = userinfo[0]
            host_port = userinfo[1].split(':')
            host = host_port[0]
            port = int(host_port[1])
            name = urllib.parse.unquote(parsed.fragment) if parsed.fragment else host
            
            node = {
                'name': name,
                'type': 'vless',
                'server': host,
                'port': port,
                'uuid': uuid,
                'cipher': 'auto',
                'udp': True,
                'tls': params.get('security', [''])[0] in ['tls', 'reality'],
                'servername': params.get('sni', [''])[0],
                'network': params.get('type', ['tcp'])[0],
            }
            if params.get('security', [''])[0] == 'reality':
                node['reality-opts'] = {
                    'public-key': params.get('pbk', [''])[0],
                    'short-id': params.get('sid', [''])[0]
                }
            if params.get('flow', [''])[0]:
                node['flow'] = params.get('flow')[0]
            if node['network'] == 'ws':
                node['ws-opts'] = {'path': params.get('path', ['/'])[0], 'headers': {'Host': params.get('host', [''])[0]}}
            elif node['network'] == 'grpc':
                 node['grpc-opts'] = {'grpc-service-name': params.get('serviceName', [''])[0]}
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
    yaml_content += "  - name: 🚀 自动选择\n    type: url-test\n    url: http://www.gstatic.com/generate_204\n    interval: 300\n    proxies:\n"
    for name in proxy_names: yaml_content += f"      - \"{name}\"\n"
    
    yaml_content += "  - name: 🔰 代理选择\n    type: select\n    proxies:\n      - 🚀 自动选择\n      - DIRECT\n"
    for name in proxy_names: yaml_content += f"      - \"{name}\"\n"
    
    yaml_content += "\nrules:\n  - MATCH,🔰 代理选择\n"
    return yaml_content

class SubHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        user_agent = self.headers.get('User-Agent', '').lower()
        query = urllib.parse.urlparse(self.path).query
        is_clash = 'clash' in user_agent or 'mihomo' in user_agent or 'meta' in user_agent or 'clash' in query
        
        if self.path.startswith('/') or self.path == '':
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
                    self.wfile.write(base64.b64encode(msg.encode('utf-8')) if not is_clash else msg.encode('utf-8'))
            else:
                msg = f"File not found: {FILE_PATH}"
                self.wfile.write(base64.b64encode(msg.encode('utf-8')) if not is_clash else msg.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

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
