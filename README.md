# tg-notifier

一个模块化的本地运行通知系统（Python），用于周期性轮询多个 API，按规则路由并推送到 Telegram 机器人/频道。可扩展为多种通知渠道与多种 API 轮询源，无需数据库（本地文件做去重/状态）。

## 特性
- 多轮询源（HTTP JSON 起步），易于扩展
- 多通知渠道（Telegram 起步），可扩展
- 路由与模板：按 `poller`→`notifier` 路由、模板化消息
- 无数据库：`.state/` 文件去重与进度记录
- 单文件配置：`config.yaml`

## 运行要求
- Python 3.10+

## 快速开始
1. 安装依赖：
```bash
pip install -r requirements.txt
```
2. 准备配置：
- 复制 `config.example.yaml` 为 `config.yaml` 并按需修改
- 准备 Telegram 机器人 token（可以放入环境变量 `TELEGRAM_BOT_TOKEN`）
3. 启动：
```bash
bash scripts/run.sh
```
或
```bash
python -m tg_notifier.app --config config.yaml
```

## 目录结构
```
src/tg_notifier/
  app.py             # 程序入口与调度
  types.py           # 基础类型定义
  utils.py           # 工具函数（路径取值、env 替换、模板渲染）
  pollers/           # 轮询器
  notifiers/         # 通知器
  routing/           # 路由
  state/             # 本地状态与去重
.state/               # 运行时状态文件
scripts/              # 启动脚本
```

## 部署建议（ARM 本地服务器）
- 建议使用 `tmux`/`screen` 或 systemd 作为守护进程
- 使用 `venv` 隔离依赖
- 定期备份 `.state/` 目录

## 扩展
- 新增一个 API 轮询器：在 `pollers/` 新建模块并在配置 `type` 指定
- 新增一个通知器：在 `notifiers/` 新建模块并在配置 `type` 指定
- 路由按 `routes` 配置进行事件到通知器的映射

## 生产部署（Ubuntu 22.04，systemd，使用系统 Python）

以下命令为在云服务器上已验证的部署与管理方式（使用系统自带 Python，不使用虚拟环境）。注意命令中的仓库绝对路径为：`/root/project/All-in-one-Telebot`。

### 1) 安装依赖
```bash
apt-get update -y
apt-get install -y python3-pip
pip3 install -r /root/project/All-in-one-Telebot/requirements.txt
```

### 2) 创建 systemd 服务
方式 A：直接写入服务文件
```bash
cat >/etc/systemd/system/tg-notifier.service <<'EOF'
[Unit]
Description=All-in-one Telebot Notifier
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/project/All-in-one-Telebot
Environment=PYTHONPATH=/root/project/All-in-one-Telebot/src
ExecStart=/usr/bin/python3 -m tg_notifier.app --config /root/project/All-in-one-Telebot/config.yaml
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

### 3) 启用并启动
```bash
systemctl daemon-reload
systemctl enable tg-notifier.service
systemctl start tg-notifier.service
```

### 4) 查看状态与日志
```bash
systemctl status tg-notifier | cat
journalctl -u tg-notifier -f --no-pager
```

### 5) 常用管理命令
```bash
# 重启/停止/启动
systemctl restart tg-notifier
systemctl stop tg-notifier
systemctl start tg-notifier

# 开机自启开关
systemctl enable tg-notifier
systemctl disable tg-notifier

# 查看最近日志
journalctl -u tg-notifier -n 100 --no-pager
```

### 6) 修改配置后生效
```bash
# 编辑配置
nano /root/project/All-in-one-Telebot/config.yaml
# 重启服务
systemctl restart tg-notifier
```

### 7) 路径与说明
- 服务文件：`/etc/systemd/system/tg-notifier.service`
- 工作目录：`/root/project/All-in-one-Telebot`
- 启动命令：`/usr/bin/python3 -m tg_notifier.app --config /root/project/All-in-one-Telebot/config.yaml`
- 环境变量：`PYTHONPATH=/root/project/All-in-one-Telebot/src`

> 安全提示：请妥善保管 `config.yaml` 中的敏感信息（如 Telegram Bot Token）。如需更换 Token，可在 BotFather 重新生成并更新配置，然后重启服务。 
