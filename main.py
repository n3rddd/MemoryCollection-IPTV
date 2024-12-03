import json
import os
import re
import time
import asyncio
from datetime import datetime
import threading
import requests
import aiohttp
from datetime import timedelta
from github import Github


def should_run():
    time_file_path = 'data/time.txt'

    # 如果时间文件不存在，说明需要执行
    if not os.path.exists(time_file_path):
        return True

    # 读取时间文件的内容
    with open(time_file_path, 'r') as file:
        last_run_time_str = file.read().strip()
        last_run_time = datetime.strptime(last_run_time_str, '%Y-%m-%d %H:%M:%S')

    # 获取当前时间
    current_time = datetime.now()

    # 判断当前时间与上次执行时间的差异是否大于等于三天
    if current_time - last_run_time >= timedelta(days=1):
        return True

    return False


def update_run_time():
    time_file_path = 'data/time.txt'
    current_time = datetime.now()
    with open(time_file_path, 'w') as file:
        file.write(current_time.strftime('%Y-%m-%d %H:%M:%S'))


def read_json_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        return data
    except FileNotFoundError:
        print(f"文件 {file_path} 未找到，请检查路径！")
        return {}  # 返回空字典而不是 None
    except json.JSONDecodeError as e:
        print(f"JSON 文件解析错误：{e}")
        return {}  # 返回空字典而不是 None


def write_json_file(file_path, data):
    """
    将数据写入 JSON 文件。

    :param file_path: JSON 文件的路径
    :param data: 要写入的数据（通常是字典或列表）
    """

    data = merge_and_deduplicate(data,read_json_file(file_path))

    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        print(f"数据已成功写入文件：{file_path}")
        return data
    except Exception as e:
        print(f"写入 JSON 文件时出错：{e}")


def remove_duplicate_ips(json_data):
    """对每个省份的 IP 地址列表去重"""
    for key, value in json_data.items():
        # 去重：通过 set 保留唯一的 IP 地址
        json_data[key] = list(set(value))
    return json_data


def merge_and_deduplicate(json1, json2):
    """
    合并两个相同格式的 JSON 数据，并对列表中的值去重。

    :param json1: 第一个 JSON 数据（字典）
    :param json2: 第二个 JSON 数据（字典）
    :return: 合并并去重后的 JSON 数据（字典）
    """
    # 合并两个字典
    merged_json = {}

    # 遍历两个 JSON 数据的键值对
    for key in set(json1.keys()).union(set(json2.keys())):  # 使用 set 确保处理所有键
        list1 = json1.get(key, [])
        list2 = json2.get(key, [])
        # 合并列表并去重
        merged_json[key] = list(set(list1 + list2))  # 合并后直接去重

    return merged_json


def get_ip(city_list,token, size=20):
    """
    根据城市和运营商信息，从 API 获取对应 IP 和端口，并返回整理后的字典格式。

    :param city_list: 可用的城市列表
    :param token：360token
    :param size: 每个城市限制获取的结果数量
    :return: 返回包含城市和对应服务地址的字典
    """

    isp_list = ["联通"]  # 默认运营商列表

    result_data = {}
    headers = {
        "X-QuakeToken": token,  # 替换为有效的 Token
        "Content-Type": "application/json"
    }

    for city in city_list:
        for isp in isp_list:
            query = f'((country: "china" AND app:"udpxy") AND province_cn: "{city}") AND isp: "中国{isp}"'
            data = {
                "query": query,
                "start": 0,
                "size": size,  # 每个城市限制获取结果数量
                "ignore_cache": False,
                "latest": True,
                "shortcuts": ["610ce2adb1a2e3e1632e67b1"]
            }

            try:
                # 发起 POST 请求
                response = requests.post(
                    url="https://quake.360.net/api/v3/search/quake_service",
                    headers=headers,
                    json=data,
                    timeout=10
                )

                if response.status_code == 200:
                    ip_data = response.json().get("data", [])
                    # 构建结果列表
                    urls = [f"http://{entry.get('ip')}:{entry.get('port')}" for entry in ip_data]
                    if urls:
                        result_data[f"{city}{isp}"] = urls
                else:
                    print(f"城市 {city}, 运营商 {isp} 查询失败，状态码：{response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"查询城市 {city}, 运营商 {isp} 时出错：{e}")
    print(result_data)
    return result_data


async def test_and_get_ip_info(province_ips):
    """
    测试 UDPxy 代理是否可用，仅返回可用 IP 的省份信息。

    :param province_ips: 包含省份和对应 IP 列表的字典
    :return: 更新后的省份字典，仅包含可用的 IP 地址
    """
    print("测试 UDPxy 代理（异步）")

    # 存储每个省份对应的可用 IP 地址
    working_ips = {}

    async def check_ip(province, ip):
        """
        异步测试每个 IP 是否可用并包含 'udpxy' 页面标识。
        """
        try:
            test_url = f"{ip}/status/"
            async with aiohttp.ClientSession() as session:
                async with session.get(test_url, timeout=3) as response:
                    if response.status == 200:
                        page_content = await response.text()
                        if 'udpxy' in page_content:
                            print(f"IP 可用：{ip} (省份: {province})")  # 成功通知
                            return province, ip  # 返回省份和 IP
        except:
            pass  # 直接跳过失败的 IP
        return None, None

    # 异步检查 IP 可用性
    tasks = []
    for province, ip_list in province_ips.items():
        for ip in ip_list:
            task = check_ip(province, ip)
            tasks.append(task)

    # 执行所有任务并筛选出可用的 IP 地址
    available_ips = await asyncio.gather(*tasks)

    # 将可用的 IP 地址按省份分类
    for province, ip in filter(lambda x: x[0] is not None, available_ips):
        if province not in working_ips:
            working_ips[province] = []
        working_ips[province].append(ip)

    # 去重处理，更新并返回最终结果
    return remove_duplicate_ips(working_ips)


def process_ip_list(ip_list, data_folder='udp'):
    """拼接组播 URL 并返回数据"""
    output_data = {}

    def process_channels(ip_url, channels, speed=0):
        """处理单个 IP 地址的所有频道，并拼接组播 URL"""
        combined_results = []
        for name, multicast_url in channels:
            combined_info = f"{name},{ip_url}{multicast_url},{speed}"
            combined_results.append(combined_info)
        return combined_results

    # 遍历所有 IP 地址和组播文件
    for province, ip_urls in ip_list.items():
        multicast_file_path = os.path.join(data_folder, f"{province}.txt")
        if os.path.exists(multicast_file_path):
            with open(multicast_file_path, 'r', encoding='utf-8') as multicast_file:
                # 提取组播信息
                channels = []
                for line in multicast_file:
                    channel_info = line.strip().split(',')
                    if len(channel_info) == 2:  # 确保每行有名称和 URL
                        name, multicast_url = channel_info
                        channels.append((name, multicast_url))

                # 拼接 URL 并保存结果
                for ip_url in ip_urls:
                    output_data[ip_url] = process_channels(ip_url, channels)

    # 返回拼接的组播信息数据
    return output_data


def group_and_sort_channels(channel_data):
    """根据规则分组并排序频道信息，并保存到 itvlist.txt"""

    def natural_key(s):
        """将字符串转换为自然排序的 key"""
        return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

    groups = {
        '央视频道': [],
        '卫视频道': [],
        '其他频道': [],
        '未分组': []  # 增加未分组项
    }

    # 遍历所有 IP 地址及其对应的频道数据
    for channel_info in channel_data:
        # 如果是列表形式的数据（可能是 [name, url, speed]），将其转为字符串
        if isinstance(channel_info, list):
            channel_info = ','.join(map(str, channel_info))  # 将列表转换为 "name,url,speed" 字符串

        # 确保channel_info是字符串格式
        if isinstance(channel_info, str):
            parts = channel_info.split(',')
            if len(parts) == 3:
                name, url, speed = parts[0], parts[1], float(parts[2])
            else:
                print(f"无效数据格式：{channel_info}，跳过该频道")
                continue

            if speed < 0.1:
                continue  # 忽略速度小于0.1的频道

            # 根据名称分组
            if 'cctv' in name.lower():
                groups['央视频道'].append((name, url, speed))
            elif '卫视' in name or '凤凰' in name:
                groups['卫视频道'].append((name, url, speed))
            else:
                groups['其他频道'].append((name, url, speed))

    # 对每个分组中的频道进行排序
    for group_name, group in groups.items():
        if group_name == '央视频道':
            # 央视频道按名称自然排序，然后按速度排序
            group.sort(key=lambda x: (natural_key(x[0]), -x[2] if x[2] is not None else float('-inf')))
        else:
            # 其他频道先按名称长度排序，再按自然排序，最后按速度降序
            group.sort(key=lambda x: (len(x[0]), natural_key(x[0]), -x[2] if x[2] is not None else float('-inf')))

    # 将分组后的频道写入文件
    with open('itvlist.txt', 'w', encoding='utf-8') as file:
        for group_name, channel_list in groups.items():
            file.write(f"{group_name},#genre#\n")
            for name, url, speed in channel_list:
                file.write(f"{name},{url},{speed}\n")
            file.write("\n")

        # 在文件末尾添加当前时间和链接
        current_time_str = datetime.now().strftime("%m-%d-%H+8")
        new_time = datetime.now() + timedelta(hours=8)
        new_time_str = new_time.strftime("%m-%d-%H")
        file.write(
            f"{new_time_str},#genre#:\n{new_time_str},https://raw.gitmirror.com/MemoryCollection/IPTV/main/TB/mv.mp4\n"
        )

    print("分组后的频道信息已保存到 itvlist.txt ")
    return groups



def download_speed_test(ip_list):
    # 下载文件并测量速度
    def download_file(url):
        try:
            start_time = time.time()
            response = requests.get(url, stream=True, timeout=3)
            total_data = 0
            for chunk in response.iter_content(1024):
                total_data += len(chunk)
                if time.time() - start_time >= 3:  # 限制下载时间为3秒
                    break
            return total_data / 3 / (1024 * 1024)  # 计算速度，单位为 MB/s
        except Exception:
            return 0  # 下载失败返回 0

    # 对单个键的 前4个 URL 进行测速
    def test_single_ip(ip, channels):
        speeds = []
        for channel in channels[:4]:  # 仅取前 4 个 URL
            _, url, _ = channel.split(",")
            speed = download_file(url)
            speeds.append(speed)
        return speeds

    # 处理所有键
    def process_ip(ip, channels):
        speeds = test_single_ip(ip, channels)
        if speeds.count(0) > 2:
            avg_speed = 0  # 前 4 个中超过 2 个为 0，则平均速度为 0
        else:
            avg_speed = sum(speeds) / len(speeds) if speeds else 0
        # 将平均速度写入键下所有频道的速度字段
        updated_channels = [
            f"{name},{url},{avg_speed:.2f}" for channel in channels
            for name, url, _ in [channel.split(",")]
        ]
        return updated_channels

    # 并发处理
    results = {}
    lock = threading.Lock()
    progress = [0]

    def worker(ip, channels):
        updated_channels = process_ip(ip, channels)
        with lock:
            results[ip] = updated_channels
            progress[0] += 1
            print(f"Progress: {progress[0]} / {len(ip_list)}")

    threads = []
    for ip, channels in ip_list.items():
        while len(threads) >= 6:  # 限制并发线程数为 6
            threads = [t for t in threads if t.is_alive()]
            time.sleep(0.1)
        thread = threading.Thread(target=worker, args=(ip, channels))
        thread.start()
        threads.append(thread)

    # 等待所有线程完成
    for thread in threads:
        thread.join()

    # 筛选速度大于等于 0.2 的频道
    filtered_channels = []
    for ip, channels in results.items():
        for channel in channels:
            name, url, speed = channel.split(",")
            if float(speed) >= 0.2:  # 仅保留速度大于等于 0.2 的频道
                filtered_channels.append(channel)

    # 写入文件
    os.makedirs("data", exist_ok=True)
    with open("data/itv.txt", "w", encoding="utf-8") as file:
        file.write("\n".join(filtered_channels))

    return filtered_channels


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


def main():
    """主程序"""

    token = os.getenv("token_360")
    # token = "XXXXXXXXXXXXXXXXXXXXXX"

    if not token :
        print("未设置：token_360，程序无法执行")
        return True

    if should_run():
        update_run_time()
        city_list = ["辽宁", "北京", "河北"]
        ip_list = get_ip(city_list,token)
        ip_list = merge_and_deduplicate(ip_list, read_json_file("data/iplist.json"))
    else:
        ip_list = read_json_file("data/iplist.json")
    ip_list = asyncio.run(test_and_get_ip_info(ip_list))
    ip_list = write_json_file("data/iplist.json", ip_list)
    ip_list = process_ip_list(ip_list)
    ip_list = download_speed_test(ip_list)
    group_and_sort_channels(ip_list)
    token = os.getenv("GITHUB_TOKEN")
    if token:
        upload_file_to_github(token, "IPTV", "itvlist.txt")

if __name__ == "__main__":
    main()
