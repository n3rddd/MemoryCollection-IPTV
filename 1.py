from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re

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

    # 返回去重后的 IP:端口 列表
    return {'ip_list': list(ip_list), 'error': None}

# 示例调用
areas = ["北京", "上海", "广州", "北京"]  # 输入包含重复地区的示例
result = selenium_get_ip(areas)
print(result)
