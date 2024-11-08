import json
import requests
import socket
from bs4 import BeautifulSoup
import re
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty
from datetime import datetime
import time
from github import Github



def write_json_file(file_path, data, overwrite=False):
    """
    写入 JSON 数据到文件。
    参数：
    - file_path: JSON 文件路径。
    - data: 要写入的字典数据。
    - overwrite: 为 True 时覆盖文件，为 False 时追加数据。
    """
    if overwrite:
        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
            print(f"数据已覆盖写入到 {file_path}")
        except Exception as e:
            print(f"覆盖写入文件失败: {e}")
    else:
        existing_data = read_json_file(file_path)
        
        # 如果读取到的现有数据为空，则初始化为默认数据结构
        if not existing_data:
            existing_data = {"详情": {"ip": [], "iptv": 0}, "直播": {}}

        # 更新“详情”字段：追加新的 IP 和累加频道总数
        new_ips = [ip for ip in data["详情"]["ip"] if ip not in existing_data["详情"]["ip"]]
        existing_data["详情"]["ip"].extend(new_ips)
        existing_data["详情"]["iptv"] += data["详情"]["iptv"]
        
        # 合并“直播”字段
        for ip, channels in data["直播"].items():
            if ip not in existing_data["直播"]:
                existing_data["直播"][ip] = channels
            else:
                # 如果 IP 已存在，追加频道数据
                existing_data["直播"][ip].extend([channel for channel in channels if channel not in existing_data["直播"][ip]])

        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(existing_data, file, ensure_ascii=False, indent=4)
            print(f"数据已追加写入到 {file_path}")
        except Exception as e:
            print(f"追加写入文件失败: {e}")

def read_json_file(file_path):
    """读取 JSON 文件内容并返回数据。如果文件不存在或内容无效，返回一个空的默认结构。"""
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except Exception as e:
            print(f"读取 JSON 文件失败: {e}")
    return {"详情": {"ip": [], "iptv": 0}, "直播": {}}

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
        "cache-control": "max-age=0",
        "content-type": "application/x-www-form-urlencoded",
        "upgrade-insecure-requests": "1",
        "cookie": "REFERER2=Game; REFERER1=Over",
        "Referer": "http://www.foodieguide.com/iptvsearch/hoteliptv.php",
        "Referrer-Policy": "strict-origin-when-cross-origin"
    }

    base_url = "http://www.foodieguide.com/iptvsearch/hoteliptv.php"
    
    ip_list = set()  # 用于存储所有有效的 IP 地址

    for area_name in area:  # 遍历每个地区
        data = {"saerch": area_name, "Submit": "+", "names": "Tom", "city": "HeZhou", "address": "Ca94122"}

        try:
            response = requests.post(base_url, headers=headers, data=data, timeout=10)
            response.raise_for_status()  # 检查请求是否成功
        except requests.RequestException as e:
            return {'ip_list': [], 'error': f"请求失败: {e}"}

        soup = BeautifulSoup(response.text, 'html.parser')
        results = soup.find_all("div", class_="result")

        for result in results:
            # 查找 IP 链接
            ip_link = result.find("a", href=re.compile(r"hotellist\.html\?s="))
            if ip_link:
                ip_address = re.search(r"s=([\d.]+:\d+)", ip_link['href'])
                if ip_address:
                    # 检查状态
                    status_div = result.find("div", style="color: crimson;")
                    if status_div and "暂时失效" in status_div.get_text():
                        continue  # 跳过失效的 IP
                    ip_list.add(ip_address.group(1))  # 添加有效 IP
    
    return {'ip_list': list(ip_list), 'error': None}
    {'ip_list': ['59.44.203.42:9901', '175.150.152.34:9005', '218.24.193.146:808', '117.72.36.109:9099', '60.16.18.243:4949', '59.47.118.242:801', '175.190.127.179:4949'], 'error': None}

def get_iptv(ip_list, output_file="data/Origfile.json", overwrite=False):
    """爬取频道信息，并返回按 IP 分组的频道数据"""
    
    ip_data = {"详情": {"ip": [], "iptv": 0}, "直播": {}}

    for ip in ip_list:
        existing_data = read_json_file(output_file)
        if ip in existing_data["详情"]["ip"]:
            print(f"IP {ip} 已存在，跳过爬取。")
            continue

        if not check_ip_port(ip): 
            print(f"IP {ip} 无法连接，跳过爬取。")
            continue

        url = f"http://www.foodieguide.com/iptvsearch/allllist.php?s={ip}&y=false"
        headers = {
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9",
            "x-requested-with": "XMLHttpRequest",
            "Referer": f"http://www.foodieguide.com/iptvsearch/hotellist.html?s={ip}",
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

    # 写入或追加数据
    write_json_file(output_file, ip_data, overwrite=overwrite)
    
    return ip_data

def filter_and_process_channel_data(ip_data, output_file="data/itv.json"):
    """对频道数据进行过滤和处理，并将结果写入到指定文件"""

    # 加载 db.json 配置文件
    db_config = read_json_file("data/db.json")["data"]

    # 检查 db_config 是否有效
    if not db_config or "keywords" not in db_config or "discard_keywords" not in db_config or "replace_keywords" not in db_config:
        print("错误：db_config 配置缺失必要字段")
        return None

    try:
        # 读取 db_config 中的关键词和替换规则
        keywords = [kw.lower() for kw in db_config["keywords"]]
        discard_keywords = [dk.lower() for dk in db_config["discard_keywords"]]
        replace_keywords = {k.lower(): v for k, v in db_config["replace_keywords"].items()}

        processed_data = {"详情": {"ip": [], "iptv": 0}, "直播": {}}
        channel_count = 0  # 初始化频道数量计数器

        # 遍历 ip_data["直播"]
        for ip, channels in ip_data["直播"].items():
            ip_channels = []  # 存储过滤后的频道信息

            # 遍历该 IP 下的所有频道
            for channel in channels:
                if len(channel) == 3:
                    channel_name, url, speed = channel

                    # 应用替换规则
                    for k, v in replace_keywords.items():
                        channel_name = re.sub(re.escape(k), v, channel_name, flags=re.IGNORECASE)

                    # 过滤包含不需要的关键词的频道名称
                    if any(dk in channel_name.lower() for dk in discard_keywords):
                        continue

                    # 保留包含指定关键词的频道名称
                    if keywords and not any(kw in channel_name.lower() for kw in keywords):
                        continue

                    # 特殊处理：清除括号内容和“高清”等词
                    channel_name = re.sub(r"（.*?）", "", channel_name)
                    channel_name = re.sub(r"高清|超清", "", channel_name).strip()

                    # 处理 URL，确保以 "http://" 开头
                    url = re.sub(r"(^http://|[ #])", "", url)
                    url = "http://" + url if not url.startswith("http://") else url

                    # 添加频道信息
                    ip_channels.append([channel_name, url, speed])
                    channel_count += 1  # 每添加一个频道，增加频道计数

            if ip_channels:
                processed_data["直播"][ip] = ip_channels
                processed_data["详情"]["ip"].append(ip)  # 添加 IP 到详情的 IP 列表

        # 设置 iptv 的值
        processed_data["详情"]["iptv"] = channel_count  # 频道总数

        # 替换处理 'iptv' 字段，假设需要做一些修改
        if "iptv" in processed_data["详情"]:
            processed_data["详情"]["iptv"] = str(processed_data["详情"]["iptv"])  # 示例修改：将频道总数转换为字符串

        # 使用 write_json_file 覆盖写入处理结果
        write_json_file("data/itv.json",processed_data, True)  
        
        print(f"处理结果已保存到 {output_file}")
        return processed_data

    except Exception as e:
        print(f"处理失败: {e}")
        return None


    """同步多线程对 IP 和频道进行测试，并将有效结果写入 JSON 文件。"""
    result_data = {"详情": {"ip": [], "iptv": 0}, "直播": {}}
    with ThreadPoolExecutor(max_workers=5) as executor:  # 设置最大线程数
        futures = []
        for ip, channels in data.items():
            futures.append(executor.submit(process_ip_channels, ip, channels, result_data["直播"]))

        for future in futures:
            future.result()  # 等待每个线程执行完成

    # 统计有效 IP 和频道数量
    result_data["详情"]["ip"] = list(result_data["直播"].keys())
    result_data["详情"]["iptv"] = sum(len(channels) for channels in result_data["直播"].values())
    
    # 覆盖写入 JSON 文件
    write_json_file("data/itv.json", result_data, overwrite=True)

def test_download_speed(url, test_duration=3, speed_threshold=0.3):
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

        speed = downloaded / test_duration if test_duration > 0 else 0  # 使用固定的 test_duration
        speed_mb_s = round(speed / (1024 * 1024), 2)  # 转换为 MB/s 并保留两位小数

        # 如果下载速度低于阈值，返回 0
        if speed_mb_s < speed_threshold:
            return 0

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

    # 定义分组
    groups = {
        '央视频道': [],
        '卫视频道': [],
        '其他频道': []
    }

    # 将频道按名称分类
    for name, url, speed in channels:
        if 'cctv' in name.lower():
            groups['央视频道'].append((name, url, speed))
        elif '卫视' in name or '凤凰' in name:
            groups['卫视频道'].append((name, url, speed))
        else:
            groups['其他频道'].append((name, url, speed))

    # 对每组进行排序
    for group in groups.values():
        group.sort(key=lambda x: (
            natural_key(x[0]),  # 名称自然排序
            -x[2] if x[2] is not None else float('-inf')  # 速度从高到低排序
        ))

    # 保存到 itvlist.txt 文件
    with open('itvlist.txt', 'w', encoding='utf-8') as file:
        for group_name, channel_list in groups.items():
            file.write(f"{group_name}:\n")
            for name, url, speed in channel_list:
                file.write(f"{name},{url},{speed}\n")
            file.write("\n")  # 打印空行分隔组

        # 添加当前时间的频道到“更新时间”分组
        current_time_str = datetime.now().strftime("%m-%d-%H")
        file.write(
            f"{current_time_str},#genre#:\n{current_time_str},https://git.3zx.top/https://raw.githubusercontent.com/MemoryCollection/IPTV/main/TB/mv.mp4\n"
        )

    # 生成 itvlist.m3u 文件
    with open('itvlist.m3u', 'w', encoding='utf-8') as m3u_file:
        m3u_file.write('#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml"\n')
        for group_name, channel_list in groups.items():
            for name, url, speed in channel_list:
                m3u_file.write(
                    f'#EXTINF:-1 tvg-name="{name}" tvg-logo="https://git.3zx.top/https://raw.githubusercontent.com/MemoryCollection/IPTV/main/TB/{name}.png" group-title="{group_name}",{name}\n'
                )
                m3u_file.write(f"{url}\n")  # 只写入 URL，不带速度

        # 添加当前时间的频道信息到 M3U 文件
        m3u_file.write(
            f'#EXTINF:-1 tvg-name="{current_time_str}" group-title="{current_time_str}", {current_time_str}\n'
        )
        m3u_file.write("https://git.3zx.top/https://raw.githubusercontent.com/MemoryCollection/IPTV/main/TB/mv.mp4\n")

    print("分组后的频道信息已保存到 itvlist.txt 和 itvlist.m3u.")
    return groups

def measure_download_speed_parallel(data):
    """
    并行测量多个 IP 地址下的频道下载速度，每个 IP 使用一个线程，
    且每个线程内串行测试该 IP 下的频道。
    空闲线程会自动获取新的任务，直到所有任务完成。
    """
    queue = Queue()
    results = {"详情": {"ip": list(data.keys()), "iptv": sum(len(channels) for channels in data.values())}, "直播": {}}
    max_threads = max(os.cpu_count() or 4, 4)

    # 将数据添加到队列中
    for ip, channels in data.items():
        queue.put((ip, channels))

    def worker():
        thread_id = threading.current_thread().name  # 获取当前线程名称
        while True:
            try:
                ip, channels = queue.get(timeout=1)  # 如果队列空，1秒后重试获取任务
            except Empty:  # 如果队列空，退出线程
                break

            # 执行测速
            channel_speeds = []
            for index, (name, url, _) in enumerate(channels):
                speed = test_download_speed(url)
                speed = round(speed, 2)  # 转换速度为MB/s，并保留小数点后两位
                channel_speeds.append([name, url, speed])  # 将测速结果添加到每个频道信息

                # 按线程名称格式化进度输出
                print(
                    f"\r线程 {thread_id} 正在测试 IP {ip} 的频道 [{index + 1}/{len(channels)}] "
                    f"总体进度 [{len(results['直播']) + 1}/{len(data)}]", 
                    end=""
                )
            
            # 将结果保存到 "直播" 字段
            results["直播"][ip] = channel_speeds
            queue.task_done()  # 标记任务完成

    # 启动多线程
    threads = []
    for _ in range(max_threads):
        thread = threading.Thread(target=worker)
        thread.start()
        threads.append(thread)

    # 等待所有任务完成
    queue.join()  # 阻塞主线程，直到所有任务都完成

    for thread in threads:
        thread.join()  # 等待所有线程执行完毕

    # 覆盖写入文件
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
        area = ["北京", "辽宁"]
        get_iptv(get_ip(area)["ip_list"])
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
#         "ip": ["117.72.36.109:9099", "59.47.118.242:801", "60.16.18.243:4949"],
#         "iptv": 6
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
