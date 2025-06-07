import requests
import threading
from queue import Queue
import time
import argparse
from urllib.parse import urljoin
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='admin_finder.log'
)

# 常见后台路径列表
COMMON_ADMIN_PATHS = [
    'admin', 'login', 'wp-admin', 'dashboard', 'manage', 'backend', 
    'admin.php', 'login.php', 'admin/login', 'admin/index', 'cms',
    'system', 'webadmin', 'administrator', 'control', 'admincp',
    'manage.php', 'admin_area', 'admin_login', 'auth/login', 'admin_panel'
]

class AdminFinder:
    def __init__(self, url, threads=10, timeout=10, verbose=False):
        """初始化 AdminFinder 类
        
        Args:
            url: 目标网站的基础 URL
            threads: 线程数量，默认为 10
            timeout: 请求超时时间，默认为 10 秒
            verbose: 是否显示详细信息，默认为 False
        """
        self.base_url = url
        self.threads = threads
        self.timeout = timeout
        self.verbose = verbose
        self.path_queue = Queue()
        self.results = []
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def _worker(self):
        """工作线程函数，处理队列中的路径"""
        while True:
            path = self.path_queue.get()
            if path is None:
                break
                
            try:
                full_url = urljoin(self.base_url, path)
                start_time = time.time()
                response = self.session.get(full_url, headers=self.headers, timeout=self.timeout, allow_redirects=True)
                elapsed_time = time.time() - start_time
                
                # 分析响应
                status_code = response.status_code
                content_length = len(response.text)
                
                # 判断是否可能是后台页面
                is_potential_admin = self._analyze_response(response)
                
                if is_potential_admin:
                    result = {
                        'url': full_url,
                        'status_code': status_code,
                        'content_length': content_length,
                        'response_time': elapsed_time,
                        'is_potential_admin': True
                    }
                    self.results.append(result)
                    print(f"[+] 发现潜在后台页面: {full_url} (状态码: {status_code}, 响应时间: {elapsed_time:.2f}s)")
                    logging.info(f"发现潜在后台页面: {full_url} (状态码: {status_code})")
                
                if self.verbose:
                    print(f"[-] 检查: {full_url} (状态码: {status_code}, 响应时间: {elapsed_time:.2f}s)")
            
            except requests.exceptions.RequestException as e:
                if self.verbose:
                    print(f"[-] 错误: {path} - {str(e)}")
                logging.warning(f"请求错误: {path} - {str(e)}")
            finally:
                self.path_queue.task_done()
    
    def _analyze_response(self, response):
        """分析响应内容，判断是否可能是后台页面
        
        Args:
            response: requests.Response 对象
        
        Returns:
            bool: 如果可能是后台页面返回 True，否则返回 False
        """
        # 检查状态码
        if response.status_code in [200, 401, 403]:
            # 检查页面内容中是否包含与登录相关的关键词
            content = response.text.lower()
            login_keywords = ['login', 'admin', 'dashboard', 'sign in', 'authentication', 'auth', 'password']
            for keyword in login_keywords:
                if keyword in content:
                    return True
            
            # 检查页面标题中是否包含与管理相关的关键词
            title_start = content.find('<title>') + 7
            title_end = content.find('</title>')
            if title_start > 7 and title_end > title_start:
                title = content[title_start:title_end].lower()
                admin_keywords = ['admin', '管理', '后台', 'dashboard', 'control panel']
                for keyword in admin_keywords:
                    if keyword in title:
                        return True
        
        return False
    
    def add_path(self, path):
        """向队列中添加路径"""
        self.path_queue.put(path)
    
    def add_paths(self, paths):
        """向队列中添加多个路径"""
        for path in paths:
            self.add_path(path)
    
    def run(self):
        """运行扫描"""
        print(f"开始扫描 {self.base_url} 的后台页面...")
        logging.info(f"开始扫描 {self.base_url} 的后台页面")
        
        # 创建工作线程
        workers = []
        for _ in range(self.threads):
            t = threading.Thread(target=self._worker)
            t.daemon = True
            t.start()
            workers.append(t)
        
        # 等待所有任务完成
        self.path_queue.join()
        
        # 停止工作线程
        for _ in range(self.threads):
            self.path_queue.put(None)
        for t in workers:
            t.join()
        
        print(f"扫描完成。共检查 {self.path_queue.qsize()} 个路径，发现 {len(self.results)} 个潜在后台页面。")
        logging.info(f"扫描完成。发现 {len(self.results)} 个潜在后台页面")
        
        return self.results

def main():
    """主函数，处理命令行参数并运行扫描"""
    parser = argparse.ArgumentParser(description='网站后台页面查找工具')
    parser.add_argument('-u', '--url', required=True, help='目标网站的基础 URL')
    parser.add_argument('-t', '--threads', type=int, default=10, help='线程数量，默认为 10')
    parser.add_argument('-T', '--timeout', type=int, default=10, help='请求超时时间，默认为 10 秒')
    parser.add_argument('-v', '--verbose', action='store_true', help='显示详细信息')
    parser.add_argument('-f', '--file', help='从文件中读取路径列表')
    
    args = parser.parse_args()
    
    # 确保 URL 以 http 或 https 开头
    if not args.url.startswith(('http://', 'https://')):
        print("错误: URL 必须以 http:// 或 https:// 开头")
        return
    
    # 创建查找器实例
    finder = AdminFinder(args.url, args.threads, args.timeout, args.verbose)
    
    # 添加路径
    if args.file:
        try:
            with open(args.file, 'r') as f:
                paths = [line.strip() for line in f if line.strip()]
                finder.add_paths(paths)
        except Exception as e:
            print(f"错误: 无法读取路径文件 - {str(e)}")
            return
    else:
        # 使用默认路径列表
        finder.add_paths(COMMON_ADMIN_PATHS)
    
    # 运行扫描
    results = finder.run()
    
    # 输出结果
    if results:
        print("\n潜在后台页面列表:")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result['url']} (状态码: {result['status_code']})")
    else:
        print("\n未发现潜在的后台页面。")

if __name__ == "__main__":
    main()    