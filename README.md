# 基于大数据的空气质量预测系统（第一版）

这是一个按开题报告技术路线搭建的项目骨架，采用 `Python + Flask + MySQL（可切换） + ECharts`，并预留了 `爬虫采集 / 数据处理 / 预测展示 / 可视化大屏` 模块。

## 当前已完成

- 普通可视化页面：总览、趋势分析、空气质量预测
- 大屏页面：独立 `/screen` 展示
- 数据层：空气质量记录、预测结果、模型评估、爬虫日志、采集产物表
- 数据输入层：公开页面爬虫、真实小时数据采集器、历史区间采集器与城市主数据
- 文件导入链路：CSV / Excel 上传、字段清洗、AQI 自动计算、导入日志
- 预测模块：趋势基线 + 正式 XGBoost 训练 + 融合预测 + 验证结果落库
- 空库启动：应用首次启动只建表，不再自动写入演示数据

## 快速启动

1. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. 启动应用

```bash
python app.py
```

3. 打开页面

- 普通页面：`http://127.0.0.1:5001/`
- 趋势分析：`http://127.0.0.1:5001/trend`
- 预测分析：`http://127.0.0.1:5001/forecast`
- 大屏：`http://127.0.0.1:5001/screen`

如果你是 macOS，并且 `xgboost` 提示缺少 `libomp.dylib`，先执行：

```bash
brew install libomp
```

## MySQL 切换

默认使用 SQLite 便于本地开发；如果需要切到 MySQL，可参考 `.env.example` 设置 `DATABASE_URL`，并执行 [schema_mysql.sql](/Users/szz/xianyu/空气质量/sql/schema_mysql.sql)。

## 真实数据导入

预测页已经提供文件导入入口，也可以直接调用接口：

```bash
curl -X POST http://127.0.0.1:5001/api/imports \
  -F "mode=daily" \
  -F "file=@你的真实空气质量文件.csv"
```

导入模板路径：

- [air_quality_import_template.csv](/Users/szz/xianyu/空气质量/data/air_quality_import_template.csv)

AQI 计算采用生态环境部 `HJ 633—2026` 规则实现，标准页面：

- [环境空气质量指数（AQI）技术规定（HJ 633—2026）](https://www.mee.gov.cn/ywgz/fgbz/bz/bzwb/jcffbz/202602/t20260225_1144441.shtml)

## 真实小时数据采集

预测页里的“采集真实小时数据”按钮，会调用 Open-Meteo API 抓取最近 24 小时的空气质量与天气数据，自动生成 `CSV` 并直接入库。当前版本会优先读取 [china_city_master.csv](/Users/szz/xianyu/空气质量/data/china_city_master.csv) 里的全国城市主数据。

也可以在终端手动执行：

```bash
python scripts/run_realtime_collector.py
```

或直接调接口：

```bash
curl -X POST http://127.0.0.1:5001/api/collector/realtime/run
```

## 历史范围采集

预测页新增了“历史范围采集”表单，支持：

- 指定 `start_date` 与 `end_date`
- 按 `全部城市 / 指定省份 / 当前城市` 采集
- 自动生成历史 `CSV`
- 自动按小时数据导入数据库

也可以通过接口调用：

```bash
curl -X POST http://127.0.0.1:5001/api/collector/history/run \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2026-04-01",
    "end_date": "2026-04-07",
    "scope": "all"
  }'
```

如果只采某个省份：

```bash
curl -X POST http://127.0.0.1:5001/api/collector/history/run \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2026-04-01",
    "end_date": "2026-04-07",
    "scope": "province",
    "province": "江苏省"
  }'
```

命令行入口：

```bash
python scripts/run_history_collector.py
```

## 全国城市主数据

全国城市主数据保存在 [china_city_master.csv](/Users/szz/xianyu/空气质量/data/china_city_master.csv)，包含：

- 城市名称
- 省份
- 查询名
- 经纬度
- 时区
- 是否已完成坐标解析

如果需要重新生成或补全坐标：

```bash
python scripts/build_city_master.py
```

## 爬虫说明

当前网页爬虫入口位于 [mee_crawler.py](/Users/szz/xianyu/空气质量/app/crawlers/mee_crawler.py)，用于采集生态环境部公开月报列表。手动运行方式：

```bash
python scripts/run_crawler.py
```

或直接调用接口：

```bash
curl -X POST http://127.0.0.1:5001/api/crawler/run
```
