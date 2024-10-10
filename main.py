import requests
from bs4 import BeautifulSoup
import re
import random
import time
import threading
from queue import Queue
from github import Github
from datetime import datetime
import os

def get_ua():
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15',
        'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Mobile Safari/537.36'
    ]
    return random.choice(user_agents)

def get_headers(base_url):
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh-Hans;q=0.9,zh;q=0.8,und;q=0.7",
        "Cache-Control": "max-age=0",
        "Content-Type": "application/x-www-form-urlencoded",
        "DNT": "1",
        "Origin": base_url,
        "User-Agent": get_ua()
    }
    return headers

def ip_exists(ip):
    """检查ip是否在文件中存在"""
    try:
        with open('itv.txt', 'r', encoding='utf-8') as f:
            for line in f:
                if ip in line:
                    return True
    except FileNotFoundError:
        return False  # 如果文件不存在，返回 False
    return False

def get_ip(diqu):
    """爬取ip"""
    base_url = "http://tonkiang.us/hoteliptv.php"
    data = {"saerch": diqu, "Submit": "+"}
    ip_list = set()
    print("开始爬取ip")
    with requests.Session() as session:
        try:
            response = session.post(base_url, headers=get_headers(base_url), data=data)
            if not response.ok:
                print(f"Failed to fetch initial page: {response.status_code}")
                return ip_list

            soup = BeautifulSoup(response.content, 'html.parser')

            ip_list = set()
            for link in soup.find_all('a', href=True):
                match = re.search(r'hotellist\.html\?s=(\d+\.\d+\.\d+\.\d+:\d+)', link['href'])
                if match:
                    ip_list.add(match.group(1))
            print(ip_list)
            return ip_list
        except Exception as e:
            print(f"An error occurred: {e}")
            return set()

def get_iptv(ip_list):
    """爬取频道信息，并过滤掉udp"""
    print("开始爬取频道信息")
    all_results = []  # 用于存储所有 IP 的结果

    for ip in ip_list:
        if ip_exists(ip):
            print(f"IP {ip} 已存在，跳过爬取。")
            continue  # 如果 IP 存在，则跳过

        base_url = f"http://tonkiang.us/allllist.php?s={ip}&c=false"
        headers = {
            "User-Agent": get_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Referer": f"http://tonkiang.us/hotellist.html?s={ip}&Submit=+",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        print(f"爬取：{ip}")
        try:
            response = requests.get(base_url, headers=headers)
            response.raise_for_status()  # 检查请求是否成功

            soup = BeautifulSoup(response.content, 'html.parser')
            results = []
            seen_urls = set()  # 用于存储已存在的 URL

            for result in soup.find_all("div", class_="result"):
                channel_div = result.find("div", style="float: left;")
                if channel_div:  # 确保找到 channel_div
                    channel_name = channel_div.text.strip()
                    url_tag = result.find("td", style="padding-left: 6px;")

                    if url_tag:
                        url = url_tag.text.strip()

                        # 过滤掉包含 'udp' 的 URL
                        if 'udp' not in url and url not in seen_urls:
                            seen_urls.add(url)
                            results.append((channel_name, url))

            # 输出当前 IP 的结果，并保存到文件
            with open('itv.txt', 'a', encoding='utf-8') as f:
                for channel_name, url in results:
                    line = f"{channel_name},{url},0\n"
                    f.write(line)  # 写入文件

            all_results.extend(results)  # 将当前 IP 的结果添加到总结果中

        except requests.exceptions.RequestException as e:
            print(f"无法访问: {base_url}, 错误: {e}")

    return all_results  # 返回所有 IP 的结果

def filter_channels():
    """对频道名称过滤和修改，同时保留速度信息"""
    # 保留关键词列表
    keywords = ["CCTV", "卫视", "凤凰", "影院", "剧场", "CHC", "娱乐", "淘", "星影", "光影", "经典电影", "精选"]
    
    # 需要放弃的关键词列表
    discard_keywords = ["广告", "测试", "购物", "复刻", "空白"]
    
    unique_channels = {}
    filtered_out = []

    replace_keywords = {
        'HD': '', '-': '', 'IPTV': '', '[': '', ']' : '', '超清': '', '高清': '', '标清': '', "上海东方": "东方",
        '中文国际': '', 'BRTV': '北京', '北京北京': '北京', ' ': '', '北京淘': '', '⁺': '+', "R": "", "4K": "", "奥林匹克": "",
        "内蒙古": "内蒙"
    }

    try:
        with open("itv.txt", 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    parts = line.strip().split(',')
                    channel_name = parts[0].strip()
                    url = parts[1].strip()
                    speed = parts[2].strip()

                    # 对url进行关键词替换为空
                    url = url.replace("#", "").replace(" ", "")

                    # 替换频道名称中的关键词
                    for key, value in replace_keywords.items():
                        channel_name = channel_name.replace(key, value)

                    # 如果频道名称包含 discard_keywords 中的关键词，跳过该频道
                    if any(discard_keyword in channel_name for discard_keyword in discard_keywords):
                        filtered_out.append((channel_name, url, speed))  # 记录被过滤掉的频道及速度
                        continue  # 跳过该频道

                    # 如果频道名称包含 "CCTV" 且不是 "CCTV4"，删除所有汉字
                    if "CCTV" in channel_name and channel_name != "CCTV4":
                        channel_name = re.sub(r'[\u4e00-\u9fa5]', '', channel_name)  # 删除所有汉字
                        channel_name = re.sub(r'\W', '', channel_name)  # 删除非字母和数字的字符

                    # 如果频道 URL 不在 unique_channels 中且包含关键词列表的内容，则保存
                    if url not in unique_channels:
                        if any(keyword in channel_name for keyword in keywords):
                            unique_channels[url] = (channel_name, speed)  # 保留频道名称和速度信息
                        else:
                            filtered_out.append((channel_name, url, speed))  # 记录被过滤掉的频道及速度

        # 对频道名称进行自然排序
        def natural_sort_key(channel):
            match = re.match(r"CCTV(\d+)", channel)
            if match:
                return (0, int(match.group(1)))
            return (1, channel)

        # 保存过滤后的频道信息
        with open('itv.txt', 'w', encoding='utf-8') as f:
            sorted_channels = sorted(unique_channels.items(), key=lambda item: natural_sort_key(item[1][0]))  # 基于名称排序
            for index, (url, (channel_name, speed)) in enumerate(sorted_channels, start=123):
                f.write(f"{channel_name},{url},{speed}\n")  

        # 保存被过滤掉的频道信息
        with open('filtered_out_itv.txt', 'w', encoding='utf-8') as f:
            for channel_name, url, speed in filtered_out:
                f.write(f"{channel_name},{url},{speed}\n") 
        print("名称筛选和替换完成！")
        return True  # 返回成功
    except Exception as e:
        print(f"处理失败: {e}")
        return False  # 返回失败


def read_channels(filename):
    """读取频道信息，并根据 URL 去重"""
    channels = []
    seen_urls = set()  # 用于存储已处理的 URL

    with open(filename, 'r', encoding='utf-8') as file:
        for line in file:
            parts = line.strip().split(',')
            name, url, speed = parts[0], parts[1], float(parts[2]) if parts[2].replace('.', '', 1).isdigit() else None
            if url not in seen_urls:
                channels.append((name, url, speed))
                seen_urls.add(url)

    return channels

def test_download_speed(url, test_duration=5):
    """
    测试下载速度
    """
    try:
        start_time = time.time()
        response = requests.get(url, timeout=test_duration + 5, stream=True)
        response.raise_for_status()

        downloaded = 0
        elapsed_time = 0  # 初始化 elapsed_time
        for chunk in response.iter_content(chunk_size=4096):
            downloaded += len(chunk)
            elapsed_time = time.time() - start_time
            if elapsed_time > test_duration:
                break

        speed = downloaded / elapsed_time if elapsed_time > 0 else 0  # 防止除以零
        return speed / (1024 * 1024)  # 转换为 MB/s

    except requests.RequestException:
        return 0

def measure_download_speed_parallel(channels, max_threads=5):
    """
    并行测量下载速度
    """
    results = []
    queue = Queue()
    processed_count = 0  # 记录处理的频道数

    for channel in channels:
        queue.put(channel)

    def worker():
        nonlocal processed_count  # 使用 nonlocal 声明变量
        while not queue.empty():
            channel = queue.get()
            name, url, _ = channel
            speed = test_download_speed(url)
            results.append((name, url, speed))
            processed_count += 1  # 增加已处理的频道数
            if processed_count % (len(channels) // 20) == 0:  # 每处理 5% 的频道打印一次
                print(f"已处理 {processed_count} 个频道")
            queue.task_done()

    threads = []
    for _ in range(max_threads):
        thread = threading.Thread(target=worker)
        thread.start()
        threads.append(thread)

    queue.join()

    for thread in threads:
        thread.join()

    return results

def natural_key(string):
    """生成自然排序的键"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', string)]

def group_and_sort_channels(channels):
    """根据规则分组并排序频道信息，并保存到itvlist"""
    groups = {
        '央视频道,#genre#': [],
        '卫视频道,#genre#': [],
        '其他频道,#genre#': []
    }

    for name, url, speed in channels:
        if 'cctv' in name.lower():
            groups['央视频道,#genre#'].append((name, url, speed))
        elif '卫视' in name:
            groups['卫视频道,#genre#'].append((name, url, speed))
        else:
            groups['其他频道,#genre#'].append((name, url, speed))

    # 对每组进行排序
    for group in groups.values():
        group.sort(key=lambda x: (
            natural_key(x[0]),  # 名称自然排序
            -x[2] if x[2] is not None else float('-inf')  # 速度从高到低排序
        ))

    # 筛选相同名称的频道，只保存前8个
    filtered_groups = {}
    overflow_groups = {}

    for group_name, channel_list in groups.items():
        seen_names = {}
        filtered_list = []
        overflow_list = []

        for channel in channel_list:
            name = channel[0]
            if name not in seen_names:
                seen_names[name] = 0

            if seen_names[name] < 8:
                filtered_list.append(channel)
                seen_names[name] += 1
            else:
                overflow_list.append(channel)

        filtered_groups[group_name] = filtered_list
        overflow_groups[group_name] = overflow_list

    # 保存到文件
    with open('itvlist.txt', 'w', encoding='utf-8') as file:
        for group_name, channel_list in filtered_groups.items():
            file.write(f"{group_name}:\n")
            for name, url, speed in channel_list:
                file.write(f"{name},{url}\n")
            file.write("\n")  # 打印空行分隔组

    # 保存超过8个的频道到新文件
    with open('fil_itvlist.txt', 'w', encoding='utf-8') as file:
        for group_name, channel_list in overflow_groups.items():
            if channel_list:  # 只写入非空组
                file.write(f"{group_name}\n")
                for name, url, speed in channel_list:
                    file.write(f"{name},{url}\n")
                file.write("\n")  # 打印空行分隔组

    return groups

def upload_file_to_github(token, repo_name, file_path, branch='main'):
    """
    将结果上传到 GitHub
    """
    g = Github(token)
    repo = g.get_user().get_repo(repo_name)
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    git_path = file_path.split('/')[-1]
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

    ip_list = set()
    ip_list.update(get_ip("上海"))
    ip_list.update(get_ip("北京"))
    ip_list.update(get_ip("广东"))
    if ip_list:
        iptv_list = get_iptv(ip_list)
        if iptv_list:
            if filter_channels():
                channels = read_channels('itv.txt')
                results = measure_download_speed_parallel(channels, max_threads=5)
                # 保存结果
                with open('itv.txt', 'w', encoding='utf-8') as file:
                    for name, url, speed in results:
                        if speed > 0.01:
                            file.write(f"{name},{url},{speed}\n")  # 保留两位小数
                print("已经完成测速！")
                channels = read_channels('itv.txt')
                if channels:
                    grouped_channels = group_and_sort_channels(channels)
                    print("分组后的频道信息已保存到 itvlist.txt.")
                    token = os.getenv("GITHUB_TOKEN")
                    if token :
                        upload_file_to_github(token, "IPTV", "itvlist.txt")