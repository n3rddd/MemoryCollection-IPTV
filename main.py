import re
import os
import json
import time
import socket
import requests
import threading
from github import Github
from datetime import datetime
from bs4 import BeautifulSoup
from queue import Queue, Empty
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def read_json_file(file_path):
    """
    读取 JSON 文件内容并返回字典数据。
    如果文件不存在，返回 None。
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"读取文件失败: {e}")
        return None

def write_json_file(file_path, data, overwrite=False):
    """
    写入 JSON 数据到文件。
    参数：
    - file_path: JSON 文件路径。
    - data: 要写入的字典数据。
    - overwrite: 为 True 时覆盖文件，为 False 时追加数据。
    """
    if overwrite:
        # 如果需要覆盖文件，直接写入数据
        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
            print(f"数据已覆盖写入到 {file_path}")
        except Exception as e:
            print(f"覆盖写入文件失败: {e}")
    else:
        # 如果需要追加数据，先读取现有文件
        existing_data = read_json_file(file_path)
        
        if not existing_data:
            # 如果文件为空或不存在，初始化数据结构
            existing_data = {"详情": {"iptv": 0, "ip": []}, "直播": {}}

        # 处理 IP 地址
        new_ips = [ip for ip in data["详情"]["ip"] if ip not in existing_data["详情"]["ip"]]
        existing_data["详情"]["ip"].extend(new_ips)
        existing_data["详情"]["iptv"] += data["详情"]["iptv"]

        # 处理频道数据，避免重复添加
        for ip, channels in data["直播"].items():
            if ip not in existing_data["直播"]:
                existing_data["直播"][ip] = channels
            else:
                existing_data["直播"][ip].extend([channel for channel in channels if channel not in existing_data["直播"][ip]])

        # 写入合并后的数据
        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(existing_data, file, ensure_ascii=False, indent=4)
            print(f"数据已追加写入到 {file_path}")
        except Exception as e:
            print(f"追加写入文件失败: {e}")

def check_ip_port(ip_port):
    """检查 IP 和端口是否可连接，返回 True 表示可用，False 表示不可用。"""
    ip, port = ip_port.split(":")
    try:
        with socket.create_connection((ip, int(port)), timeout=5):
            return True
    except (socket.timeout, socket.error):
        return False

def get_ip(area):
    """爬取指定地区的IP地址"""
    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "zh-CN,zh;q=0.9",
        "cache-control": "no-cache",
        "content-type": "application/x-www-form-urlencoded",
        "pragma": "no-cache",
        "proxy-connection": "keep-alive",
        "upgrade-insecure-requests": "1",
        "Referer": "http://tonkiang.us/hoteliptv.php",
        "Referrer-Policy": "strict-origin-when-cross-origin"
    }    

    base_url = "http://tonkiang.us/hoteliptv.php"
    ip_list = set()  

    for area_name in area:  
        data = {
            "0835d": area_name,
            "Submit": "+",
            "town": "9ad8c870",
            "ave": "KuudNuB02s"
        }

        try:
            response = requests.post(base_url, headers=headers, data=data)
            response.raise_for_status()  
        except requests.RequestException as e:
            return {'ip_list': [], 'error': f"请求失败: {e}"}

        soup = BeautifulSoup(response.text, 'html.parser')
        print(soup)
        # 直接在源码中提取IP和端口
        ip_addresses = re.findall(r"hotellist\.html\?s=([\d.]+:\d+)", soup.prettify())
        print(ip_addresses)
        for ip in ip_addresses:
            print(ip)
            ip_list.add(ip)
    
    return {'ip_list': list(ip_list), 'error': None}

def selenium_get_ip(area):
    # 初始化浏览器配置
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # 无头模式，避免打开浏览器窗口
    driver = webdriver.Chrome(options=options)
    
    ip_list = set()  # 使用集合去重
    url = "http://tonkiang.us/hoteliptv.php"
    
    # 访问目标网站
    driver.get(url)

    # 循环处理每个地区
    for area_name in area:
        try:
            # 定位到搜索框并输入地区名称
            search_box = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "search"))
            )
            search_box.clear()  # 清空输入框
            search_box.send_keys(area_name)  # 输入地区名
            search_box.send_keys(Keys.RETURN)  # 模拟按下 Enter 键提交

            # 等待搜索结果加载完成
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "search"))  # 或者根据页面元素的变化来判断
            )

            # 获取页面源代码
            html_content = driver.page_source

            # 使用正则表达式提取 IP:端口
            pattern = r"(\d+\.\d+\.\d+\.\d+:\d+)"
            ip_ports = re.findall(pattern, html_content)

            # 将提取到的 IP:端口加入到集合中，自动去重
            ip_list.update(ip_ports)

        except Exception as e:
            print(f"Error while processing area {area_name}: {e}")
    
    # 关闭浏览器
    driver.quit()

    return {'ip_list': list(ip_list), 'error': None}

def get_iptv(ip_list, output_file="data/Origfile.json", overwrite=False):
    """爬取频道信息，并返回按 IP 分组的频道数据"""
    
    ip_data = {"详情": {"iptv": 0,"ip": []}, "直播": {}}

    for ip in ip_list:
        existing_data = read_json_file(output_file)
        if ip in existing_data["详情"]["ip"]:
            print(f"IP {ip} 已存在，跳过爬取。")
            continue

        if not check_ip_port(ip): 
            print(f"IP {ip} 无法连接，跳过爬取。")
            continue

        url = f"http://tonkiang.us/allllist.php?s={ip}&c=false"
        headers = {
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "proxy-connection": "keep-alive",
            "x-requested-with": "XMLHttpRequest",
            "cookie": "REFERER2=Over; REFERER1=NzDbYr1aObDckO0O0O",
            "Referer": f"http://tonkiang.us/hotellist.html?s={url}",
            "Referrer-Policy": "strict-origin-when-cross-origin"
        }
        response = requests.get(url, headers=headers)
        channels = []

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            results = soup.find_all(class_='result')

            for result in results:
                channel_name = result.find('div', style='float: left;')
                m3u8_url = result.find('td', style='padding-left: 6px;')

                if channel_name and m3u8_url:
                    channels.append([channel_name.get_text(strip=True), m3u8_url.get_text(strip=True), 0])

            if channels:
                ip_data["详情"]["ip"].append(ip)
                ip_data["直播"][ip] = channels
                ip_data["详情"]["iptv"] += len(channels)
                print(f"IP {ip} 爬取了 {len(channels)} 个频道。")
        else:
            print(f"请求失败，状态码: {response.status_code}，IP: {ip}")

    write_json_file(output_file, ip_data, overwrite=overwrite)
    return ip_data

def filter_and_process_channel_data(ip_data, output_file="data/itv.json"):
    """对频道数据进行过滤和处理，并将结果写入到指定文件"""

    db_config = read_json_file("data/db.json")["data"]

    if not db_config or "keywords" not in db_config or "discard_keywords" not in db_config or "replace_keywords" not in db_config:
        print("错误：db_config 配置缺失必要字段")
        return None

    try:
        keywords = [kw.lower() for kw in db_config["keywords"]]
        discard_keywords = [dk.lower() for dk in db_config["discard_keywords"]]
        replace_keywords = {k.lower(): v for k, v in db_config["replace_keywords"].items()}

        processed_data = {"详情": {"iptv": 0,"ip": []}, "直播": {}}
        channel_count = 0  

        for ip, channels in ip_data["直播"].items():
            ip_channels = [] 

            for channel in channels:
                if len(channel) == 3:
                    channel_name, url, speed = channel

                    for k, v in replace_keywords.items():
                        channel_name = re.sub(k, v, channel_name, flags=re.IGNORECASE)

                    channel_name = channel_name.upper()

                    if any(dk in channel_name.lower() for dk in discard_keywords):
                        continue

                    if keywords and not any(kw in channel_name.lower() for kw in keywords):
                        continue

                    url = re.sub(r"(^http://|[ #])", "", url)
                    url = "http://" + url if not url.startswith("http://") else url

                    ip_channels.append([channel_name, url, speed])
                    channel_count += 1  

            if ip_channels:
                processed_data["直播"][ip] = ip_channels
                processed_data["详情"]["ip"].append(ip)  

        processed_data["详情"]["iptv"] = channel_count  

        if "iptv" in processed_data["详情"]:
            processed_data["详情"]["iptv"] = str(processed_data["详情"]["iptv"])  # 示例修改：将频道总数转换为字符串

        write_json_file("data/itv.json",processed_data, True)  
        
        return processed_data

    except Exception as e:
        print(f"处理失败: {e}")
        return None

def test_download_speed(url, test_duration=3):
    """
    测试下载速度，固定访问时间为 test_duration 秒，并加入速度阈值。
    如果下载速度低于阈值，返回 0。
    """
    try:
        start_time = time.time()
        response = requests.get(url, timeout=test_duration + 5, stream=True)
        response.raise_for_status()

        downloaded = 0
        while True:
            elapsed_time = time.time() - start_time
            if elapsed_time >= test_duration:
                break

            for chunk in response.iter_content(chunk_size=4096):
                downloaded += len(chunk)
                elapsed_time = time.time() - start_time
                if elapsed_time >= test_duration:
                    break

        speed = downloaded / test_duration if test_duration > 0 else 0 
        speed_mb_s = round(speed / (1024 * 1024), 2)  

        return speed_mb_s

    except requests.RequestException:
        return 0

def measure_speed_for_ip(ip, channels):
    """
    针对单个 IP 地址下的所有频道进行串行测速。
    """
    results = []
    for index, channel in enumerate(channels):
        name, url, _ = channel
        speed = test_download_speed(url)
        results.append((name, url, speed))
        print(f"\r正在测试 IP {ip} 的频道 [{index + 1}/{len(channels)}]", end="")
    print(f"\n完成 IP {ip} 的测速")
    return ip, results

def natural_key(string):
    """自然排序的辅助函数"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', string)]

def group_and_sort_channels(data):
    """根据规则分组并排序频道信息，并保存到 itvlist.txt 和 itvlist.m3u"""
    channels = []
    for ip, channel_list in data["直播"].items():
        channels.extend(channel_list)

    groups = {
        '央视频道': [],
        '卫视频道': [],
        '其他频道': []
    }

    for name, url, speed in channels:
        if 'cctv' in name.lower():
            groups['央视频道'].append((name, url, speed))
        elif '卫视' in name or '凤凰' in name:
            groups['卫视频道'].append((name, url, speed))
        else:
            groups['其他频道'].append((name, url, speed))

    for group in groups.values():
        group.sort(key=lambda x: ( natural_key(x[0]), -x[2] if x[2] is not None else float('-inf') ))

    with open('itvlist.txt', 'w', encoding='utf-8') as file:
        for group_name, channel_list in groups.items():
            file.write(f"{group_name}:\n")
            for name, url, speed in channel_list:
                file.write(f"{name},{url},{speed}\n")
            file.write("\n") 

        current_time_str = datetime.now().strftime("%m-%d-%H")
        file.write(
            f"{current_time_str},#genre#:\n{current_time_str},https://raw.3zx.top/MemoryCollection/IPTV/main/TB/mv.mp4\n"
        )

    with open('itvlist.m3u', 'w', encoding='utf-8') as m3u_file:
        m3u_file.write('#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml"\n')
        for group_name, channel_list in groups.items():
            for name, url, speed in channel_list:
                m3u_file.write(
                    f'#EXTINF:-1 tvg-name="{name}" tvg-logo="https://raw.3zx.top/MemoryCollection/IPTV/main/TB/{name}.png" group-title="{group_name}",{name}\n'
                )
                m3u_file.write(f"{url}\n") 
        m3u_file.write(
            f'#EXTINF:-1 tvg-name="{current_time_str}" group-title="{current_time_str}", {current_time_str}\n'
        )
        m3u_file.write("https://raw.3zx.top/MemoryCollection/IPTV/main/TB/mv.mp4\n")

    print("分组后的频道信息已保存到 itvlist.txt 和 itvlist.m3u.")
    return groups

def measure_download_speed_parallel(data,MinSpeed = 0.3):
    """
    并行测量多个 IP 地址下的频道下载速度，
    每个 IP 使用一个线程，且每个线程内串行测试该 IP 下的频道。
    在测试频道速度之前，首先检查 IP 地址和端口是否可连接，
    如果无法连接，则跳过该 IP 地址的测速。
    MinSpeed 是最小速度。
    """
    queue = Queue()
    results = {"详情": {"iptv": sum(len(channels) for channels in data.values()), "ip": list(data.keys())}, "直播": {}}
    
    # 保证至少 6 个线程
    max_threads = max(os.cpu_count() or 4, 6)

    for ip, channels in data.items():
        queue.put((ip, channels))

    def worker():
        thread_id = threading.current_thread().name  
        while True:
            try:
                ip, channels = queue.get(timeout=1) 
            except Empty:  
                break

            if not check_ip_port(ip):
                print(f"\r线程 {thread_id}: IP {ip} 端口无法连接，跳过测速", end="")
                queue.task_done()  
                continue   

            channel_speeds = []
            for index, (name, url, _) in enumerate(channels):
                speed = test_download_speed(url)
                speed = round(speed, 2)
            
                if speed > MinSpeed:
                    channel_speeds.append([name, url, speed]) 

                    print(f"\r线程 {thread_id} 正在测试 IP {ip} 的频道 [{index + 1}/{len(channels)}] "
                          f"总体进度 [{len(results['直播']) + 1}/{len(data)}]", end="")

            if channel_speeds:
                results["直播"][ip] = channel_speeds
            queue.task_done()

    threads = []
    for _ in range(max_threads):
        thread = threading.Thread(target=worker)
        thread.start()
        threads.append(thread)

    queue.join() 

    for thread in threads:
        thread.join() 

    write_json_file("data/itv.json", results, overwrite=True)
    return results

def upload_file_to_github(token, repo_name, file_path, folder='', branch='main'):
    """
    将结果上传到 GitHub，并指定文件夹
    """
    g = Github(token)
    repo = g.get_user().get_repo(repo_name)
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    git_path = f"{folder}/{file_path.split('/')[-1]}" if folder else file_path.split('/')[-1]

    try:
        contents = repo.get_contents(git_path, ref=branch)
    except:
        contents = None

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if contents:
            repo.update_file(contents.path, current_time, content, contents.sha, branch=branch)
            print("文件已更新")
        else:
            repo.create_file(git_path, current_time, content, branch=branch)
            print("文件已创建")
    except Exception as e:
        print("文件上传失败:", e)

if __name__ == "__main__":

    ip_data = read_json_file("data/itv.json")
    if int(ip_data["详情"]["iptv"]) < 600:
        area = ["北京", "辽宁","上海"]
        get_iptv(selenium_get_ip(area)["ip_list"])
        filter_and_process_channel_data(read_json_file("data/Origfile.json"))
    iptv_data = read_json_file("data/itv.json")
    results = measure_download_speed_parallel(iptv_data["直播"])
    group_and_sort_channels(results)
    token = os.getenv("GITHUB_TOKEN")
    if token:
        upload_file_to_github(token, "IPTV", "itvlist.txt")
        upload_file_to_github(token, "IPTV", "itvlist.m3u")
        upload_file_to_github(token, "IPTV", "data/itv.json", folder="data")


# json 保存数据格式
# {
#     "详情": {
#         "iptv": 6,
#         "ip": ["117.72.36.109:9099", "59.47.118.242:801", "60.16.18.243:4949"]
#     },
#     "直播": {
#         "117.72.36.109:9099": [
#             ["CCTV2", "http://cdnzxrrs.gz.chinamobile.com:6060/PLTV/88888888/224/3221225706/10000100000000060000000000146027_0.smil/index.m3u8", 0],
#             ["CCTV3", "http://39.135.16.142:6060/PLTV/88888888/224/3221226008/372609400.smil/index.m3u8", 0]
#         ],
#         "59.47.118.242:801": [
#             ["CCTV1", "http://udp://239.3.3.72:10001", 0],
#             ["CCTV1", "http://59.47.118.242:801/hls/72/index.m3u8", 0]
#         ],
#         "60.16.18.243:4949": [
#             ["CCTV1", "http://hls/1/index.m3u8", 0],
#             ["CCTV2", "http://hls/2/index.m3u8", 0]
#         ]
#     }
# }
