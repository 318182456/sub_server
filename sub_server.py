import http.server
import socketserver
import base64
import os

# 配置项
PORT = 8080
FILE_PATH = "/root/agsbx/jh.txt"

class SubHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # 我们目前让根路径 / 返回订阅信息
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            # 增加一个模拟的流量信息让客户端显示有量可用（可选）
            self.send_header('Subscription-Userinfo', 'upload=0; download=0; total=1073741824000; expire=2062560867')
            self.end_headers()
            
            if os.path.exists(FILE_PATH):
                try:
                    with open(FILE_PATH, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    # 过滤并拼接所有的代理链接
                    valid_lines = [line.strip() for line in lines if line.strip()]
                    content = "\n".join(valid_lines)
                    
                    # Base64 编码 (Mihomo 和 v2rayN 支持直接解析 Base64 编码的配置)
                    b64_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
                    self.wfile.write(b64_content.encode('utf-8'))
                except Exception as e:
                    self.wfile.write(base64.b64encode(f"读取文件出错: {e}".encode('utf-8')))
            else:
                self.wfile.write(base64.b64encode(f"文件未找到 (File not found): {FILE_PATH}".encode('utf-8')))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

if __name__ == '__main__':
    # 确保 socket 可以重用，避免端口被占用错误
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), SubHandler) as httpd:
        print(f"订阅服务运行在 http://0.0.0.0:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            httpd.server_close()
