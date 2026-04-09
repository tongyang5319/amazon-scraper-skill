Amazon 榜单统一爬虫 (amazon-unified-scraper)
================================================================================

功能说明
--------------------------------------------------------------------------------
本工具用于抓取 Amazon 新品排行榜 / 畅销榜 商品信息，支持列表页 + 详情页
双重抓取，输出结构化 CSV 文件。

【列表页抓取（Selenium）】
  - 商品排名、标题、URL、ASIN、图片、价格、评分、评论数
  - 自动识别新品榜(New Releases)和标准搜索页面
  - 支持分页，自动滚动触发懒加载（抓满100个商品）

【详情页抓取（requests + BeautifulSoup）】
  - 品牌、月销量、优惠券、产品尺寸、产品重量
  - 五点描述（bullet_point_1 ~ bullet_point_5，横向展开）
  - 细分类目名称、细分类目排名、A+页面标识
  - 用户评论（优先抓取低于3星的差评，最多5条，
    每条包含 rating + text，横向展开为 review_1_rating/text ~ review_5_rating/text）

【国家定位】
  - 通过 --postal-code 参数指定邮政编码，Amazon 返回对应国家/地区的榜单内容
  - 例如：10001（美国纽约）、E1 8AN（英国伦敦）、10115（德国柏林）
  - 注意：货币币种由 IP 地理位置决定，--postal-code 无法改变货币显示
  - 如需抓取目标国货币（如美国站 USD），需要使用目标国 IP 进行抓取

【反检测】
  - Chrome WebDriver 伪装（navigator.webdriver 清除）
  - User-Agent 轮换（26组 Windows Chrome UA）
  - 详情页请求间隔 8~15 秒随机延迟

输出文件
--------------------------------------------------------------------------------
  data/新品榜_{细分类目名}_{日期}.csv   （始终生成）
  data/新品榜_{细分类目名}_{日期}.xlsx  （使用 --format xlsx 时生成，带产品图片）

  CSV 列说明：
    list_rank          榜单排名
    title              商品标题
    url                商品页面链接
    asin_code          ASIN编码
    image_url          产品图片URL
    price              价格（含币种）
    rating             评分（如 4.2）
    review_count       评论数
    brand              品牌
    bought_in_past_month  月销量（如 300+ bought in past month）
    has_coupon         是否有优惠券（True/False）
    coupon_text        优惠券描述
    product_size       产品尺寸
    product_weight     产品重量
    sub_category_name  细分类目名称
    sub_category_rank  细分类目排名（如 #3,731 in Automotive）
    has_a_plus         是否有A+页面（True/False）
    bullet_point_1~5   五点描述（横向5列）
    review_1_rating/text ~ review_5_rating/text  用户评论（横向10列）

运行依赖
--------------------------------------------------------------------------------
  Python 3.11+
  Poetry（包管理工具）
  Chrome / ChromeDriver（需与浏览器版本匹配）
  Pillow（图片嵌入，支持 --format xlsx）

安装步骤
--------------------------------------------------------------------------------
  1. 安装 Python 3.11+
  2. 安装 Poetry
     pip install poetry
  3. 进入项目目录
     cd C:\Users\Administrator\amazon-unified-scraper
  4. 安装依赖（自动包含 Pillow）
     poetry install

  5. 下载 ChromeDriver（需与本机 Chrome 版本匹配）
     访问 https://googlechromelabs.github.io/chrome-for-testing/
     下载对应版本的 chromedriver-win64.zip
     解压后将 chromedriver.exe 放入项目 drivers\chromedriver-win64\ 目录

使用方法
--------------------------------------------------------------------------------
【单类目】
  poetry run python -m amazon_unified_scraper -u "URL"

【指定抓取数量（默认100）】
  poetry run python -m amazon_unified_scraper -u "URL" --max-list 50

【单类目+图片嵌入（XLSX）】
  poetry run python -m amazon_unified_scraper -u "URL" --format xlsx

【多类目（逐个指定）】
  poetry run python -m amazon_unified_scraper -u "URL1" -u "URL2"

【多类目（从文件读取）】
  poetry run python -m amazon_unified_scraper -f urls.txt

【交互式输入】
  poetry run python -m amazon_unified_scraper -i

【ASIN 复查（补抓缺失字段）】
  poetry run python -m amazon_unified_scraper ^
    --retry-asin B0FH1L3LM1 ^
    --retry-asin B0G48MHVYV

  可单独复查某个 ASIN 的详情页数据（品牌、月销量、评分等），
  不需要提供类目 URL，适合补抓 CSV 中缺失的 bought_in_past_month 等字段。

【完整参数示例】
  poetry run python -m amazon_unified_scraper ^
    -u "https://www.amazon.com/gp/new-releases/automotive/2201763011/" ^
    --max-list 100 ^
    --max-detail 100 ^
    --max-reviews 5 ^
    --postal-code 10001 ^
    --delay-min 8 ^
    --delay-max 15 ^
    --format xlsx
举例：poetry run python -m amazon_unified_scraper -u "https://www.amazon.com/Best-Sellers-Automotive-Car-Care/zgbs/automotive/15718271/ref=zg_bs_nav_automotive_1" --max-list 50

参数说明
--------------------------------------------------------------------------------
  -u / --url         类目URL（可多次使用）
  -f / --file        URL列表文件（每行一个URL）
  -i / --interactive 交互式输入模式
  --max-list         列表页抓取商品数（默认100）
  --max-detail       详情页抓取商品数（默认=列表数）
  --max-reviews      每商品抓取评论数（默认10）
  --delay-min        详情页最小延迟秒数（默认8.0）
  --delay-max        详情页最大延迟秒数（默认15.0）
  --postal-code      目标国家邮政编码（仅影响榜单内容，不改变货币）
  --format           输出格式：xlsx（默认，含嵌入式图片）或 csv
  --retry-asin       复查指定 ASIN 的详情页（补抓缺失字段，不需要 URL）
  --auto-retry       自动复查缺失字段（默认开启，--no-auto-retry 可关闭）
  --output-dir       输出目录（默认 data/）

常用邮编示例（--postal-code 参数）
--------------------------------------------------------------------------------
  10001   美国（New York）
  90210   美国（Los Angeles）
  E1 8AN  英国（London）
  10115   德国（Berlin）
  75001   法国（Paris）
  1000001 日本（Tokyo）

  注：邮编仅影响榜单内容显示，货币由 IP 地理位置决定

注意事项
--------------------------------------------------------------------------------
  1. 详情页请求有8~15秒随机延迟，抓取50个商品约需 8~12 分钟
  2. 建议每次运行不超过3个类目，避免 IP 被封禁
  3. CSV 文件在抓取过程中会被锁定，运行前确保文件未被 Excel 打开
  4. ChromeDriver 版本必须与本机 Chrome 版本匹配，否则无法启动
  5. 货币说明：价格货币由访问 IP 的地理位置决定，与 --postal-code 参数无关
     - 中国 IP → 显示人民币（CNY）
     - 日本 IP → 显示日元（JPY）
     - 美国 IP → 显示美元（USD）
     如需抓取目标国货币，需要使用目标国的代理 IP 或 VPN 进行抓取
