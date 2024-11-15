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


### json 
```

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

```

### Dockerfile 

```
# 使用 selenium/standalone-chrome 镜像作为基础镜像
FROM selenium/standalone-chrome:latest

# 设置工作目录
WORKDIR /aap

# 切换为 root 用户，确保有权限操作系统文件
USER root

# 修复权限问题，清理 APT 缓存并更新
RUN rm -rf /var/lib/apt/lists/* && \
    apt-get update --allow-releaseinfo-change && \
    apt-get install -y python3 python3-pip && \
    apt-get clean

# 强制安装 Python 包
# 使用 selenium/standalone-chrome 镜像作为基础镜像
FROM selenium/standalone-chrome:latest

# 设置工作目录
WORKDIR /aap

# 切换为 root 用户，确保有权限操作系统文件
USER root

# 修复权限问题，清理 APT 缓存并更新
RUN rm -rf /var/lib/apt/lists/* && \
    apt-get update --allow-releaseinfo-change && \
    apt-get install -y python3 python3-pip && \
    apt-get clean

# 强制安装 Python 包
RUN pip3 install --no-cache-dir --break-system-packages -i https://pypi.tuna.tsinghua.edu.cn/simple requests beautifulsoup4 selenium PyGithub


# 设置容器启动时的默认命令
CMD ["tail", "-f", "/dev/null"]

```
