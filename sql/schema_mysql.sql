CREATE TABLE IF NOT EXISTS air_quality_records (
    id INT PRIMARY KEY AUTO_INCREMENT,
    city VARCHAR(50) NOT NULL,
    province VARCHAR(50) NOT NULL,
    record_time DATETIME NOT NULL,
    aqi INT NOT NULL,
    level VARCHAR(20) NOT NULL,
    primary_pollutant VARCHAR(30) NOT NULL,
    pm25 DECIMAL(8,2) NOT NULL,
    pm10 DECIMAL(8,2) NOT NULL,
    so2 DECIMAL(8,2) NOT NULL,
    no2 DECIMAL(8,2) NOT NULL,
    co DECIMAL(8,2) NOT NULL,
    o3 DECIMAL(8,2) NOT NULL,
    temperature DECIMAL(8,2) NOT NULL,
    humidity DECIMAL(8,2) NOT NULL,
    wind_speed DECIMAL(8,2) NOT NULL,
    pressure DECIMAL(8,2) NOT NULL,
    source_name VARCHAR(60) DEFAULT 'system-seed',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_city_time (city, record_time)
);

CREATE TABLE IF NOT EXISTS prediction_records (
    id INT PRIMARY KEY AUTO_INCREMENT,
    city VARCHAR(50) NOT NULL,
    forecast_time DATETIME NOT NULL,
    generated_at DATETIME NOT NULL,
    actual_aqi DECIMAL(8,2) NOT NULL,
    lstm_aqi DECIMAL(8,2) NOT NULL,
    xgboost_aqi DECIMAL(8,2) NOT NULL,
    ensemble_aqi DECIMAL(8,2) NOT NULL,
    pm25_pred DECIMAL(8,2) NOT NULL,
    pm10_pred DECIMAL(8,2) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_city_forecast_time (city, forecast_time)
);

CREATE TABLE IF NOT EXISTS model_metrics (
    id INT PRIMARY KEY AUTO_INCREMENT,
    city VARCHAR(50) NOT NULL,
    model_name VARCHAR(30) NOT NULL,
    mae DECIMAL(8,2) NOT NULL,
    rmse DECIMAL(8,2) NOT NULL,
    r2 DECIMAL(8,4) NOT NULL,
    updated_at DATETIME NOT NULL,
    KEY idx_city_model (city, model_name)
);

CREATE TABLE IF NOT EXISTS crawl_task_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    task_name VARCHAR(80) NOT NULL,
    source_name VARCHAR(80) NOT NULL,
    target_url VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL,
    records_count INT NOT NULL DEFAULT 0,
    message VARCHAR(255) NOT NULL DEFAULT '',
    run_at DATETIME NOT NULL,
    KEY idx_run_at (run_at)
);

CREATE TABLE IF NOT EXISTS crawl_artifacts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    source_name VARCHAR(80) NOT NULL,
    category VARCHAR(40) NOT NULL,
    title VARCHAR(255) NOT NULL,
    article_url VARCHAR(255) NOT NULL,
    published_at VARCHAR(30) NOT NULL DEFAULT '',
    crawled_at DATETIME NOT NULL,
    KEY idx_crawled_at (crawled_at)
);

CREATE TABLE IF NOT EXISTS data_import_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    file_name VARCHAR(255) NOT NULL,
    mode VARCHAR(20) NOT NULL,
    source_name VARCHAR(80) NOT NULL DEFAULT 'manual-upload',
    status VARCHAR(20) NOT NULL,
    total_rows INT NOT NULL DEFAULT 0,
    success_rows INT NOT NULL DEFAULT 0,
    inserted_rows INT NOT NULL DEFAULT 0,
    updated_rows INT NOT NULL DEFAULT 0,
    message VARCHAR(255) NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_created_at (created_at)
);
