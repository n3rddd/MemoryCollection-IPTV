import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import m3u8
from datetime import datetime, timedelta
import os


# 获取酒店ip  钟馗之眼
def fetch_ips_sele(urls):
    """获取酒店ip"""
    print("开始获取酒店ip")
    # 配置 ChromeDriver 的选项
    chrome_options = Options()

    chrome_options.add_argument("--disable-gpu")  # 修复无头模式问题
    chrome_options.add_argument("--no-sandbox")  # 适配 Linux
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=1920,1080")  # 模拟正常窗口大小
    chrome_options.add_argument("--disable-dev-shm-usage")  # 解决内存问题
    chrome_options.add_argument(f"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-software-rasterizer")  # 关闭软件渲染

    # 隐藏 Selenium 特征
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    # 启动 WebDriver
    driver = webdriver.Chrome(options=chrome_options)

    # 进一步隐藏 Selenium 特征
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.navigator.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """
    })

    all_ips = set()  # 用于存储去重后的 IP:端口
    blocked = False  # 是否被封禁
    skipped_domains = set()  # 被跳过的域名

    for url in urls:
        domain = re.search(r"https?://([^/]+)", url).group(1)  # 提取域名

        if blocked or domain in skipped_domains:
            print(f"跳过 URL: {url} (原因: IP 被封禁或域名相关)")
            continue

        print(f"访问 URL: {url}")
        driver.get(url)

        found_keywords = False
        elapsed_time = 0
        timeout = 60  # 超时时间 60 秒

        while elapsed_time < timeout:
            time.sleep(3)  # 每 3 秒检测一次
            elapsed_time += 3

            try:
                # 检查是否显示 IP 访问异常
                page_source = driver.page_source
                if "[-3000] IP访问异常，疑似为爬虫被暂时禁止访问" in page_source:
                    print(f"检测到封禁信息，跳过所有相关域名：{domain}")
                    blocked = True
                    skipped_domains.add(domain)
                    break

                # 检查页面是否包含关键字
                if re.search(r'找到约\s*\d+|条匹配结果\s*\d+', page_source):
                    print("页面包含目标关键字，开始提取 IP:端口")
                    time.sleep(3)  # 等待 3 秒
                    found_keywords = True
                    break
                else:
                    print(f"等待页面加载... 已等待 {elapsed_time} 秒")
            except Exception as e:
                print(f"检测页面内容时出错: {e}")
                break

        if not found_keywords:
            print(f"超时 {timeout} 秒未找到关键字，跳过 URL: {url}")
            continue

        if blocked:
            continue  # 如果已经封禁，停止继续处理

        # 提取 IP:端口格式
        try:
            pattern = r'(\d+\.\d+\.\d+\.\d+:\d{1,5})'  
            found_ips = re.findall(pattern, page_source)
            all_ips.update(found_ips)
            print(f"提取到 {len(found_ips)} 个 IP:端口")
        except Exception as e:
            print(f"在处理 {url} 时提取 IP:端口时发生错误: {e}")

    driver.quit()  # 关闭浏览器
    return list(all_ips)  # 返回去重后的 IP 列表

# 获取酒店ip  360搜索
def fetch_ips_360(token):
    """360搜索ip"""
    print("360搜索IP")
    headers = {
        "X-QuakeToken": token,
        "Content-Type": "application/json"
    }
    query = '((favicon:"6e6e3db0140929429db13ed41a2449cb" OR favicon:"34f5abfd228a8e5577e7f2c984603144" )) AND country_cn: "中国"'
    data = {
        "query": query,
        "start": 0,
        "size": 20,
        "ignore_cache": False,
        "latest": True,
        "shortcuts": ["610ce2adb1a2e3e1632e67b1"]
    }
    urls = []

    try:
        response = requests.post(
            url="https://quake.360.net/api/v3/search/quake_service",
            headers=headers,
            json=data,
            timeout=10
        )

        if response.status_code == 200:
            ip_data = response.json().get("data", [])
            urls = [f"{entry.get('ip')}:{entry.get('port')}" for entry in ip_data if entry.get('ip') and entry.get('port')]
            print("360IP搜索成功" if urls else "未找到匹配的 IP 数据")
        else:
            pass
    except requests.exceptions.RequestException as e:
        pass
    print(f"提取到 {len(urls)} 个 IP:端口")
    return urls

# 合并 js ip列表
def merge_ips(ips):
    """
    将传入的 IP 列表与 `data/hotel.json` 文件中的 IP 列表合并并去重。

    Args:
        ips (list): 传入的 IP 列表。

    Returns:
        list: 合并去重后的 IP 列表。
    """
    # 读取 `data/hotel.json` 文件
    try:
        with open("data/hotel.json", "r", encoding="utf-8") as file:
            data = json.load(file)
            file_ips = data.get("ip", [])
    except FileNotFoundError:
        file_ips = []  # 如果文件不存在，使用空列表
    except json.JSONDecodeError:
        raise ValueError("JSON 文件格式错误！")

    # 合并并去重
    merged_ips = list(set(ips + file_ips))

    return merged_ips

#  获取频道列表
def get_channels_from_ips(urls):
    """获取频道列表"""

    result = {'ip': [], 'data': {}}

    def fetch_channels(ip):
        """从单个 IP 获取频道信息"""
        try:
            # 构建请求 URL
            response = requests.get(f"http://{ip}/iptv/live/1000.json?key=txiptv", timeout=4)
            data = response.json()

            if 'data' in data:
                channels = {}
                for channel in data['data']:
                    name = channel.get('name', '未知')

                    # 替换规则
                    name = name.replace("cctv", "CCTV")
                    name = name.replace("中央", "CCTV")
                    name = name.replace("央视", "CCTV")
                    name = name.replace("高清", "")
                    name = name.replace("超高", "")
                    name = name.replace("HD", "")
                    name = name.replace("标清", "")
                    name = name.replace("频道", "")
                    name = name.replace("-", "")
                    name = name.replace(" ", "")
                    name = name.replace("PLUS", "+")
                    name = name.replace("＋", "+")
                    name = name.replace("(", "")
                    name = name.replace(")", "")
                    name = re.sub(r"CCTV(\d+)台", r"CCTV\1", name)
                    name = name.replace("CCTV1综合", "CCTV1")
                    name = name.replace("CCTV2财经", "CCTV2")
                    name = name.replace("CCTV3综艺", "CCTV3")
                    name = name.replace("CCTV4国际", "CCTV4")
                    name = name.replace("CCTV4中文国际", "CCTV4")
                    name = name.replace("CCTV4欧洲", "CCTV4")
                    name = name.replace("CCTV5体育", "CCTV5")
                    name = name.replace("CCTV6电影", "CCTV6")
                    name = name.replace("CCTV7军事", "CCTV7")
                    name = name.replace("CCTV7军农", "CCTV7")
                    name = name.replace("CCTV7农业", "CCTV7")
                    name = name.replace("CCTV7国防军事", "CCTV7")
                    name = name.replace("CCTV8电视剧", "CCTV8")
                    name = name.replace("CCTV9记录", "CCTV9")
                    name = name.replace("CCTV9纪录", "CCTV9")
                    name = name.replace("CCTV10科教", "CCTV10")
                    name = name.replace("CCTV11戏曲", "CCTV11")
                    name = name.replace("CCTV12社会与法", "CCTV12")
                    name = name.replace("CCTV13新闻", "CCTV13")
                    name = name.replace("CCTV新闻", "CCTV13")
                    name = name.replace("CCTV14少儿", "CCTV14")
                    name = name.replace("CCTV15音乐", "CCTV15")
                    name = name.replace("CCTV16奥林匹克", "CCTV16")
                    name = name.replace("CCTV17农业农村", "CCTV17")
                    name = name.replace("CCTV17农业", "CCTV17")
                    name = name.replace("CCTV5+体育赛视", "CCTV5+")
                    name = name.replace("CCTV5+体育赛事", "CCTV5+")
                    name = name.replace("CCTV5+体育", "CCTV5+")
                    if name == "内蒙古”": name = "内蒙古卫视"

                    channel_url = f"http://{ip}" + channel.get('url', '未知')
                    channels[name] = channel_url

                return ip, channels
            return None  # 如果没有有效数据，则返回 None
        except requests.RequestException:
            print(f"无法获取 {ip} 的频道列表")
            return None  # 异常时返回 None

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_channels, ip): ip for ip in urls}

        for future in as_completed(futures):
            print(f"正在获取 {futures[future]} 的数据...")
            result_data = future.result()
            if result_data:  # 确保 result_data 非 None
                ip, channels = result_data
                result['data'][ip] = channels
                result['ip'].append(ip)
                print(f"成功获取 {ip} 的数据")
            else:
                print(f"无法获取 {futures[future]} 的数据")

    return result

# 下载指定分片 URL 数据，并返回下载速度 (MB/s)
def download_segment(url, duration=5):
    """下载指定分片 URL 数据，并返回下载速度 (MB/s)"""
    start_time = time.time()
    downloaded_bytes = 0
    try:
        with requests.get(url, stream=True, timeout=duration) as response:
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=1024 * 1024):  # 每次读取 1MB 数据
                downloaded_bytes += len(chunk)
                if time.time() - start_time >= duration:
                    break
        elapsed_time = time.time() - start_time
        if elapsed_time > 0:
            return downloaded_bytes / (1024 * 1024) / elapsed_time  # MB/s
    except requests.RequestException:
        return 0  # 下载失败，速度为 0

# 解析 m3u8 文件并下载总共 5 秒，返回下载速度
def download_m3u8(url, duration=5):
    """解析 m3u8 文件并下载总共 5 秒，返回下载速度"""
    start_time = time.time()  # 添加起始时间记录
    try:
        response = requests.get(url, timeout=duration)
        response.raise_for_status()
        m3u8_obj = m3u8.loads(response.text)

        segment_urls = [seg.uri for seg in m3u8_obj.segments]
        speeds = []

        for segment_url in segment_urls:
            if not segment_url.startswith("http"):
                # 补全相对路径
                segment_url = url.rsplit('/', 1)[0] + '/' + segment_url
            speed = download_segment(segment_url, duration=duration)
            speeds.append(speed)

            # 如果已经下载超过指定的时间，则停止下载
            if time.time() - start_time >= duration:
                break

        avg_speed = sum(speeds) / len(speeds) if speeds else 0
        return avg_speed
    except requests.RequestException:
        return 0

# 对前 max_urls 个频道测速，返回平均速度
def measure_speed(channels, max_urls=4,  duration=5):
    """对前 max_urls 个频道测速，返回平均速度"""
    urls = list(channels.values())[:max_urls]
    speeds = []

    for url in urls:
        speed = download_m3u8(url, duration=duration)
        print(f"IP: {url}，平均速度: {speed:.2f}")
        speeds.append(speed)

    avg_speed = sum(speeds) / len(speeds) if speeds else 0
    return avg_speed

# 多线程处理每个键 (IP)，键下频道同步测速并保存结果
def process_tv_list(tv_list):
    """多线程处理每个键 (IP)，键下频道同步测速并保存结果"""
    results = []

    def process_ip(ip, channels):
        avg_speed = measure_speed(channels)
        if avg_speed >= 0.2:
            for name, url in channels.items():
                results.append(f"{name},{url},{avg_speed:.2f}")
        else:
            print(f"放弃 IP: {ip}，平均速度不足 0.2")

    with ThreadPoolExecutor(max_workers=8) as executor:  # 最少 8 个线程
        futures = {executor.submit(process_ip, ip, channels): ip for ip, channels in tv_list.items()}

        for future in as_completed(futures):
            ip = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"处理 IP {ip} 时发生错误: {e}")

    return results    

# 自然排序
def natural_sort_key(string_):
    """将字符串转换为自然排序的 key"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', string_)]

# 自然排序
def group_and_sort_channels(channel_data):
    """根据规则分组并排序频道信息"""
    groups = {
        '中央频道': [],
        '卫星频道': [],
        '其他频道': [],
        '未分组': []
    }

    for channel_info in channel_data:
        if isinstance(channel_info, list):
            channel_info = ','.join(map(str, channel_info))

        if isinstance(channel_info, str):
            parts = channel_info.split(',')
            if len(parts) == 3:
                name, url, speed = parts[0], parts[1], float(parts[2])
            else:
                print(f"无效数据格式：{channel_info}，跳过该频道")
                continue

            if speed < 0.1:
                continue

            if 'cctv' in name.lower():
                groups['中央频道'].append((name, url, speed))
            elif '卫视' in name or '凤凰' in name:
                groups['卫星频道'].append((name, url, speed))
            else:
                groups['其他频道'].append((name, url, speed))

    for group_name, group in groups.items():
        if group_name == '中央频道':
            group.sort(key=lambda x: (natural_sort_key(x[0]), -x[2] if x[2] is not None else float('-inf')))
        else:
            group.sort(key=lambda x: (len(x[0]), natural_sort_key(x[0]), -x[2] if x[2] is not None else float('-inf')))

    with open("hotel.txt", 'w', encoding='utf-8') as file:
        for group_name, channel_list in groups.items():
            file.write(f"{group_name},#genre#\n")
            for name, url, speed in channel_list:
                file.write(f"{name},{url},{speed}\n")
            file.write("\n")

        new_time = datetime.now() + timedelta(hours=8)
        new_time_str = new_time.strftime("%m-%d %H:%M")

        file.write(f"{new_time_str},#genre#:\n{new_time_str},https://raw.gitmirror.com/MemoryCollection/IPTV/main/TB/mv.mp4\n")

    print("分组后的频道信息已保存到 hotel.txt ")
    return groups

# 写入 hotel.json
def write_channels_to_json(channel_data):
    print("开始写入文件...")
    # 写入文件
    try:
        with open("data/hotel.json", "w", encoding="utf-8") as f:
            json.dump(channel_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"写入文件时发生错误: {e}")

# 主程序入口
def main():

    urls = ["https://www.zoomeye.org/searchResult?q=iconhash%3A%226e6e3db0140929429db13ed41a2449cb%22%20%20-title%3A%22404%22"]
  
    token_360 = os.getenv("token_360")
    print(token_360)
    exit(0)
    ips = list(set(fetch_ips_360(token_360) + fetch_ips_sele(urls)))
    print(ips)
    tv_list = get_channels_from_ips(merge_ips(ips))
    write_channels_to_json(tv_list)
    channel_data= process_tv_list(tv_list["data"])
    group_and_sort_channels(channel_data)

# 运行主程序
if __name__ == "__main__":
    main()
