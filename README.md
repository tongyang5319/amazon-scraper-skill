# Amazon 新品榜爬虫 - 使用说明

## 功能概述

本工具用于抓取 Amazon 新品排行榜 / 畅销榜 商品信息，支持列表页 + 详情页双重抓取，输出含产品图片的 XLSX 文件。

**核心功能：**
- 列表页抓取：排名、标题、URL、ASIN、图片、价格、评分、评论数
- 详情页抓取：品牌、月销量、优惠券（含折扣金额）、产品尺寸/重量、五点描述（横向5列）
- 细分类目排名、A+页面标识
- 用户评论（优先抓取低于3星的差评，最多5条，横向显示）
- 自动滚动加载（Amazon懒加载，100商品全覆盖）
- XLSX 嵌入式产品缩略图
- ASIN复查模式（补抓缺失字段）

---

## 安装

```bash
# 1. 进入项目目录
cd C:\Users\Administrator\openclaw-amazon-scraper

# 2. 安装依赖
poetry install
```

---

## 快速开始

### 1. 单类目抓取（默认50个）
```bash
poetry run python -m amazon_unified_scraper -u "URL"
```

### 2. 指定抓取数量
```bash
# 抓取20个商品
poetry run python -m amazon_unified_scraper -u "URL" --max-list 20

# 抓取100个商品
poetry run python -m amazon_unified_scraper -u "URL" --max-list 100
```

### 3. 输出格式
```bash
# XLSX（默认，含产品图片）
poetry run python -m amazon_unified_scraper -u "URL" --format xlsx

# CSV（无图片）
poetry run python -m amazon_unified_scraper -u "URL" --format csv
```

---

## 批量抓取

### 多类目逐个指定
```bash
poetry run python -m amazon_unified_scraper -u "URL1" -u "URL2" -u "URL3"
```

### 从文件读取URL列表
```bash
# 先创建 urls.txt（每行一个URL）
poetry run python -m amazon_unified_scraper -f urls.txt
```

### 交互式输入
```bash
poetry run python -m amazon_unified_scraper -i
```

---

## 复查缺失字段

抓取结果中某些商品可能缺失月销量（bought_in_past_month）等字段，可用 ASIN 复查功能单独补抓：

```bash
# 单个ASIN复查
poetry run python -m amazon_unified_scraper --retry-asin B0FH1L3LM1

# 多个ASIN复查
poetry run python -m amazon_unified_scraper --retry-asin B0FH1L3LM1 --retry-asin B0G48MHVYV
```

---

## 完整参数示例

```bash
poetry run python -m amazon_unified_scraper ^
  -u "https://www.amazon.com/gp/new-releases/automotive/2201763011/" ^
  --max-list 100 ^
  --max-detail 100 ^
  --max-reviews 5 ^
  --postal-code 10001 ^
  --delay-min 8 ^
  --delay-max 15 ^
  --format xlsx
```

---

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-u / --url` | 类目URL（可多次使用） | 必填 |
| `-f / --file` | URL列表文件（每行一个） | - |
| `-i / --interactive` | 交互式输入模式 | - |
| `--max-list` | 列表页抓取商品数 | 50 |
| `--max-detail` | 详情页抓取商品数（默认=列表数） | 50 |
| `--max-reviews` | 每商品抓取评论数 | 5 |
| `--format` | 输出格式：xlsx（含图片）或 csv | xlsx |
| `--postal-code` | 目标国邮编（仅影响内容，不改货币） | - |
| `--delay-min` | 详情页最小延迟（秒） | 8 |
| `--delay-max` | 详情页最大延迟（秒） | 15 |
| `--retry-asin` | 复查指定ASIN（不需要URL） | - |
| `--auto-retry / --no-auto-retry` | 自动复查缺失字段（默认开启） | 默认开启 |

---

## 输出文件

- `data/新品榜_类目名_日期.xlsx`（XLSX格式，含产品缩略图）
- `data/新品榜_类目名_日期.csv`（仅CSV格式）

**XLSX 表格结构：**
| 列 | 内容 |
|---|------|
| A列 | 产品缩略图（80×80像素） |
| B列 | 榜单排名 |
| C列 | 商品标题 |
| D列 | ASIN编码 |
| E~ | 价格、评分、评论数、品牌、月销量等 |
| 描述1~5 | 五点描述（横向5列） |
| 评论1评分~5 | 5条评论（评分+内容，横向10列） |

---

## 常用目标国邮编

| 邮编 | 国家/地区 |
|------|---------|
| 10001 | 美国（New York） |
| 90210 | 美国（Los Angeles） |
| E1 8AN | 英国（London） |
| 10115 | 德国（Berlin） |
| 75001 | 法国（Paris） |
| 1000001 | 日本（Tokyo） |

> **注意：** 货币由IP地理位置决定，与邮编参数无关。如需抓取目标国货币，需要使用目标国IP。

---

## 注意事项

1. 详情页请求有8~15秒随机延迟，抓取50个商品约需 8~12 分钟
2. 建议每次运行不超过3个类目，避免IP被封禁
3. CSV/XLSX文件在抓取过程中会被锁定，运行前确保文件未被Excel/WPS打开
4. ChromeDriver已包含在drivers目录，无需额外下载
5. 如果某些商品月销量显示为空，说明Amazon页面本身未提供该数据，非抓取失败

---

## ChromeDriver 与 drivers 目录

**本地运行**（必须）：
ChromeDriver 文件存放在 `drivers/` 目录，由项目自动识别系统加载。

| 系统 | 目录 | 说明 |
|------|------|------|
| Windows | `drivers/chromedriver-win64/chromedriver.exe` | 已包含 |
| macOS ARM (M1/M2/M3) | `drivers/chromedriver-mac-arm64/chromedriver` | 需手动下载 |
| macOS Intel | `drivers/chromedriver-mac-x64/chromedriver` | 需手动下载 |
| Linux | `drivers/chromedriver-linux64/chromedriver` | 需手动下载 |

**下载 Mac/Linux chromedriver**：
访问 [https://googlechromelabs.github.io/chrome-for-testing/](https://googlechromelabs.github.io/chrome-for-testing/)，下载对应版本的 `chromedriver_mac_arm64.zip` 或 `chromedriver_linux64.zip`，解压后将文件放入对应目录。

**上传 ClawHub**：
ClawHub 对单个文件大小有限制（10MB），chromedriver.exe（约12MB）不得上传。上传前需排除 drivers 目录：

```bash
# 打包时排除 drivers 目录
tar --exclude='drivers' -czf amazon-scraper.tar.gz .

# 上传成功后，本地运行前恢复 drivers
cp -r /path/to/amazon-unified-scraper/drivers /path/to/openclaw-amazon-scraper/
```

ClawHub 上传包只含源码，chromedriver 需用户在本地补齐。

---

## 常见问题

**Q: 抓取数量只有60个？**
A: Amazon页面需要滚动才能触发懒加载，已添加自动滚动逻辑，100个商品可全覆盖。

**Q: 价格显示日本币（JPY）？**
A: 价格货币由访问IP决定，中国IP显示CNY，日本IP显示JPY。如需USD，需要使用美国IP。

**Q: 怎么在WPS/Excel中显示产品图片？**
A: 使用 `--format xlsx` 输出，XLSX文件在WPS/Excel中打开后，A列会显示产品缩略图。

**Q: 优惠券字段没有内容？**
A: 只有提供具体折扣的优惠券才显示金额（如"Save 5%"），无折扣提示的不显示。
