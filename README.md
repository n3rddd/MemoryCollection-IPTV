itvlist.txt每9个小时测速一次，使用北京服务器测速

个人使用效果还不错。

### 电视直播
    https://raw.3zx.top/MemoryCollection/IPTV/main/itvlist.txt
### tvbox接口
    https://raw.3zx.top/MemoryCollection/IPTV/main/tv.json

### 壳子
- FongMi  https://tv.xn--yhqu5zs87a.top/
- 影视仓 https://wwqo.lanzouo.com/iTW1629kktlc 密码:4ofa
``
### 酒店源搜索

- http://tonkiang.us/?
- http://www.foodieguide.com/iptvsearch/hoteliptv.php





    {
        "详情": {
            "iptv": 6,
            "ip": ["117.72.36.109:9099", "59.47.118.242:801", "60.16.18.243:4949"]
        },
        "直播": {
            "117.72.36.109:9099": [
                ["CCTV2", "http://cdnzxrrs.gz.chinamobile.com:6060/PLTV/88888888/224/3221225706/10000100000000060000000000146027_0.smil/index.m3u8", 0],
                ["CCTV3", "http://39.135.16.142:6060/PLTV/88888888/224/3221226008/372609400.smil/index.m3u8", 0]
            ],
            "59.47.118.242:801": [
                ["CCTV1", "http://udp://239.3.3.72:10001", 0],
                ["CCTV1", "http://59.47.118.242:801/hls/72/index.m3u8", 0]
            ],
            "60.16.18.243:4949": [
                ["CCTV1", "http://hls/1/index.m3u8", 0],
                ["CCTV2", "http://hls/2/index.m3u8", 0]
            ]
        }
    }

### Dockerfile 

```
# 使用 Python 3.13 作为基础镜像
FROM python:3.13-slim

# 设置工作目录
WORKDIR /app

# 复制本地代码到容器内
COPY . /app

# 设置环境变量，避免 pip 安装时进行交互
ENV PYTHONUNBUFFERED=1

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Chrome 浏览器和 ChromeDriver
RUN wget https://storage.googleapis.com/chrome-for-testing-public/133.0.6836.0/linux64/chrome-linux64.zip -O chrome.zip && \
    unzip chrome.zip && \
    mv chrome-linux64 /opt/google/chrome && \
    rm chrome.zip

RUN wget https://storage.googleapis.com/chrome-for-testing-public/133.0.6836.0/linux64/chromedriver-linux64.zip -O chromedriver.zip && \
    unzip chromedriver.zip && \
    mv chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver && \
    rm chromedriver.zip

# 设置 Chrome 和 ChromeDriver 路径
ENV CHROME_BIN=/opt/google/chrome/chrome
ENV CHROMEDRIVER=/usr/local/bin/chromedriver

# 使用清华大学镜像源安装 pip 包
RUN pip install --no-cache-dir --timeout=600 -i https://pypi.tuna.tsinghua.edu.cn/simple --upgrade pip

# 安装 Python 包
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple requests beautifulsoup4 selenium PyGithub

# 设置容器启动时保持运行
CMD ["tail", "-f", "/dev/null"]

```
