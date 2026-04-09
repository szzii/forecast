async function loadForecastPage() {
    const cityPayload = await AppUtils.getCitiesPayload();
    if (!cityPayload.cities.length) {
        return;
    }

    async function render() {
        const city = AppUtils.getCurrentCity();
        const payload = await AppUtils.fetchJSON(`/api/forecast?city=${encodeURIComponent(city)}`);
        const first = payload.hourly[0] || {};
        const forecastMessage = document.getElementById("forecastGenerateMessage");

        AppUtils.renderMetricCards("forecastSummaryCards", [
            { label: "预测城市", value: payload.city, extra: `生成时间：${payload.generated_at}` },
            { label: "未来 1 小时 AQI", value: first.ensemble_aqi ?? "--", extra: `趋势基线 ${first.lstm_aqi ?? "--"} / XGBoost ${first.xgboost_aqi ?? "--"}` },
            { label: "未来 1 小时 PM2.5", value: first.pm25_pred ?? "--", extra: `PM10 ${first.pm10_pred ?? "--"}` },
        ]);

        if (!payload.has_data) {
            forecastMessage.textContent = payload.message;
        } else {
            forecastMessage.textContent = `预测已生成：${payload.generated_at}。当前展示为“趋势基线 + 正式 XGBoost + 融合预测”结果。`;
        }

        AppUtils.mountChart("forecastHourChart").setOption({
            tooltip: { trigger: "axis" },
            legend: { data: ["融合预测", "趋势基线", "XGBoost"] },
            grid: { left: 44, right: 24, top: 48, bottom: 36 },
            xAxis: { type: "category", data: payload.hourly.map((item) => item.time) },
            yAxis: { type: "value" },
            dataZoom: [{ type: "inside" }, { type: "slider" }],
            graphic: payload.hourly.length ? [] : [{
                type: "text",
                left: "center",
                top: "middle",
                style: { text: payload.message, fill: "#6c7a89", fontSize: 16 },
            }],
            series: [
                { name: "融合预测", type: "line", smooth: true, data: payload.hourly.map((item) => item.ensemble_aqi), color: "#2784e8" },
                { name: "趋势基线", type: "line", smooth: true, data: payload.hourly.map((item) => item.lstm_aqi), color: "#20bf6b" },
                { name: "XGBoost", type: "line", smooth: true, data: payload.hourly.map((item) => item.xgboost_aqi), color: "#fa8231" },
            ],
        });

        AppUtils.mountChart("forecastModelChart").setOption({
            tooltip: { trigger: "axis" },
            legend: { data: ["MAE", "RMSE", "R²"] },
            grid: { left: 44, right: 24, top: 48, bottom: 36 },
            xAxis: { type: "category", data: payload.model_metrics.map((item) => item.model) },
            yAxis: [{ type: "value" }, { type: "value", min: 0, max: 1 }],
            graphic: payload.model_metrics.length ? [] : [{
                type: "text",
                left: "center",
                top: "middle",
                style: { text: payload.message, fill: "#6c7a89", fontSize: 16 },
            }],
            series: [
                { name: "MAE", type: "bar", data: payload.model_metrics.map((item) => item.mae), color: "#4b7bec" },
                { name: "RMSE", type: "bar", data: payload.model_metrics.map((item) => item.rmse), color: "#f7b731" },
                { name: "R²", type: "line", yAxisIndex: 1, smooth: true, data: payload.model_metrics.map((item) => item.r2), color: "#20bf6b" },
            ],
        });

        AppUtils.mountChart("forecastPmChart").setOption({
            tooltip: { trigger: "axis" },
            legend: { data: ["PM2.5 预测", "PM10 预测"] },
            grid: { left: 44, right: 24, top: 48, bottom: 36 },
            xAxis: { type: "category", data: payload.hourly.map((item) => item.time) },
            yAxis: { type: "value" },
            graphic: payload.hourly.length ? [] : [{
                type: "text",
                left: "center",
                top: "middle",
                style: { text: payload.message, fill: "#6c7a89", fontSize: 16 },
            }],
            series: [
                { name: "PM2.5 预测", type: "line", smooth: true, data: payload.hourly.map((item) => item.pm25_pred), color: "#20bf6b", areaStyle: { color: "rgba(32,191,107,0.10)" } },
                { name: "PM10 预测", type: "line", smooth: true, data: payload.hourly.map((item) => item.pm10_pred), color: "#4b7bec", areaStyle: { color: "rgba(75,123,236,0.08)" } },
            ],
        });

        AppUtils.mountChart("forecastValidationChart").setOption({
            tooltip: { trigger: "axis" },
            legend: { data: ["真实值", "趋势基线", "XGBoost", "融合预测", "误差"] },
            grid: { left: 44, right: 24, top: 48, bottom: 36 },
            xAxis: { type: "category", data: payload.validation.map((item) => item.date) },
            yAxis: [{ type: "value" }, { type: "value" }],
            graphic: payload.validation.length ? [] : [{
                type: "text",
                left: "center",
                top: "middle",
                style: { text: payload.message, fill: "#6c7a89", fontSize: 16 },
            }],
            series: [
                { name: "真实值", type: "line", smooth: true, data: payload.validation.map((item) => item.actual), color: "#eb3b5a" },
                { name: "趋势基线", type: "line", smooth: true, data: payload.validation.map((item) => item.trend), color: "#20bf6b" },
                { name: "XGBoost", type: "line", smooth: true, data: payload.validation.map((item) => item.xgboost), color: "#fa8231" },
                { name: "融合预测", type: "line", smooth: true, data: payload.validation.map((item) => item.predicted), color: "#2784e8" },
                { name: "误差", type: "bar", yAxisIndex: 1, data: payload.validation.map((item) => item.error), color: "#26de81" },
            ],
        });
    }

    document.getElementById("forecastGenerateButton").addEventListener("click", async () => {
        const city = AppUtils.getCurrentCity();
        const message = document.getElementById("forecastGenerateMessage");
        message.textContent = "正在训练 XGBoost 模型并生成未来 24 小时预测，请稍候...";
        try {
            const response = await fetch("/api/forecast/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ city }),
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.message || `请求失败: ${response.status}`);
            }
            message.textContent = result.message;
            await render();
        } catch (error) {
            message.textContent = `生成失败：${error.message}`;
        }
    });

    document.addEventListener("aq-city-change", render);
    await render();
}

document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("forecastGenerateButton")) {
        loadForecastPage();
    }
});
