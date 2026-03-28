import http.server
import socketserver
import base64
import os
import urllib.parse
import urllib.request
import json
import time

# 配置项
PORT = 8080
FILE_PATH = "/root/agsbx/jh.txt"
SUB_PASS = os.getenv("SUB_PASS", "") # 从环境变量读取订阅密码

# Akile Cloud API 配置 (从环境变量读取)
AKILE_CLIENT = os.getenv("AKILE_CLIENT", "")
AKILE_SECRET = os.getenv("AKILE_SECRET", "")

# 缓存配置
cache_data = {"stats": "upload=0; download=0; total=0; expire=0", "time": 0}
CACHE_TTL = 300 # 5 分钟缓存

def get_akile_stats():
    """从 AkileCloud API 获取流量统计和到期时间"""
    global cache_data
    now = time.time()
    
    # 如果缓存未过期，直接返回
    if now - cache_data["time"] < CACHE_TTL:
        return cache_data["stats"]
    
    try:
        # 1. 获取服务器列表以拿到 ID, 总流量(flow), 到期时间(due_time)
        list_url = "https://api.akile.io/api/v1/server/GetServerList"
        list_data = json.dumps({"page_num": 1, "page_size": 10}).encode('utf-8')
        list_req = urllib.request.Request(list_url, data=list_data, method='POST')
        list_req.add_header('Api-Client', AKILE_CLIENT)
        list_req.add_header('Api-Secret', AKILE_SECRET)
        list_req.add_header('Content-Type', 'application/json')
        
        with urllib.request.urlopen(list_req, timeout=5) as response:
            res = json.loads(response.read().decode())
            if res.get('status') != 200 or not res.get('data', {}).get('list'):
                return cache_data["stats"]
            
            # 取第一个服务器
            server = res['data']['list'][0]
            server_id = server['id']
            total_flow = server.get('flow', 0) # 总流量
            expire_time = server.get('due_time', 0) # 到期时间戳
            
        # 2. 获取服务器统计信息以拿到已用流量
        stats_url = f"https://api.akile.io/api/v1/server/GetServerStatistics?id={server_id}"
        stats_req = urllib.request.Request(stats_url, method='GET')
        stats_req.add_header('Api-Client', AKILE_CLIENT)
        stats_req.add_header('Api-Secret', AKILE_SECRET)
        
        with urllib.request.urlopen(stats_req, timeout=5) as response:
            res_stats = json.loads(response.read().decode())
            used_traffic = 0
            if res_stats.get('status') == 200:
                # Akile 统计返回的是已用流量 (bytes)
                used_traffic = res_stats.get('data', 0)
            
            # 格式化 Header: upload={u}; download={d}; total={t}; expire={e}
            # 这里由于 API 没细分上下行，我们统一放 download
            new_stats = f"upload=0; download={used_traffic}; total={total_flow}; expire={expire_time}"
            cache_data["stats"] = new_stats
            cache_data["time"] = now
            return new_stats
            
    except Exception as e:
        print(f"获取 Akile 统计失败: {e}")
        return cache_data["stats"]

class SubHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # 解析请求的路径
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.strip('/') 
        
        # 验证密码 (如果设置了 SUB_PASS)
        if SUB_PASS and path != SUB_PASS:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(f"403 Forbidden: Invalid password. Use /{SUB_PASS}".encode('utf-8'))
            return
            
        if os.path.exists(FILE_PATH):
            try:
                with open(FILE_PATH, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 获取实时流量统计
                user_info = get_akile_stats()
                
                self.send_response(200)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                # 写入来自 Akile 的真实流量信息
                self.send_header('Subscription-Userinfo', user_info)
                self.end_headers()
                
                # Base64 编码并返回
                b64_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
                self.wfile.write(b64_content.encode('utf-8'))
                
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Error: {e}".encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(f"File not found: {FILE_PATH}".encode('utf-8'))

if __name__ == '__main__':
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), SubHandler) as httpd:
        print(f"订阅服务(含 Akile 流量统计)已启动: http://0.0.0.0:{PORT}/{SUB_PASS}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            httpd.server_close()
