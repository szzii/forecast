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
            { label: "城市", value: payload.city, extra: `生成时间：${payload.generated_at}` },
            { label: "AQI 预测（+1h）", value: first.ensemble_aqi ?? "--", extra: `趋势 ${first.lstm_aqi ?? "--"} / XGBoost ${first.xgboost_aqi ?? "--"}` },
            { label: "污染物（+1h）", value: `PM2.5 ${first.pm25_pred ?? "--"}`, extra: `PM10 ${first.pm10_pred ?? "--"} / NO2 ${first.no2_pred ?? "--"}` },
        ]);

        if (!payload.has_data) {
            forecastMessage.textContent = payload.message;
        } else {
            forecastMessage.textContent = `预测已生成：${payload.generated_at}，包含 AQI、PM2.5、PM10、SO2、NO2、CO、O3。`;
        }

        AppUtils.mountChart("forecastHourChart").setOption({
            tooltip: { trigger: "axis" },
            legend: {
                data: ["集成预测", "趋势模型", "XGBoost"],
                tooltip: {
                    show: true,
                    formatter: (name) => ({
                        "集成预测": "集成预测：综合趋势模型与 XGBoost 的加权平均结果，综合准确性更高",
                        "趋势模型": "趋势模型（LSTM）：基于时序深度学习，擅长捕捉长期变化趋势",
                        "XGBoost": "XGBoost：基于梯度提升树，擅长捕捉特征间的非线性关系",
                    })[name] || name,
                },
            },
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
                { name: "集成预测", type: "line", smooth: true, data: payload.hourly.map((item) => item.ensemble_aqi), color: "#2784e8" },
                { name: "趋势模型", type: "line", smooth: true, data: payload.hourly.map((item) => item.lstm_aqi), color: "#20bf6b" },
                { name: "XGBoost", type: "line", smooth: true, data: payload.hourly.map((item) => item.xgboost_aqi), color: "#fa8231" },
            ],
        });


        AppUtils.mountChart("forecastPrimaryPollutantChart").setOption({
            tooltip: { trigger: "axis" },
            legend: { data: ["PM2.5", "PM10", "NO2", "O3", "SO2", "CO"] },
            grid: { left: 48, right: 56, top: 48, bottom: 36 },
            xAxis: { type: "category", data: payload.hourly.map((item) => item.time) },
            yAxis: [
                { type: "value", name: "μg/m³", nameTextStyle: { color: "#6c7a89" } },
                { type: "value", name: "CO mg/m³", position: "right", nameTextStyle: { color: "#0fb9b1" } },
            ],
            graphic: payload.hourly.length ? [] : [{
                type: "text",
                left: "center",
                top: "middle",
                style: { text: payload.message, fill: "#6c7a89", fontSize: 16 },
            }],
            series: [
                { name: "PM2.5", type: "line", smooth: true, data: payload.hourly.map((item) => item.pm25_pred), color: "#20bf6b" },
                { name: "PM10", type: "line", smooth: true, data: payload.hourly.map((item) => item.pm10_pred), color: "#4b7bec" },
                { name: "NO2", type: "line", smooth: true, data: payload.hourly.map((item) => item.no2_pred), color: "#f7b731" },
                { name: "O3", type: "line", smooth: true, data: payload.hourly.map((item) => item.o3_pred), color: "#eb3b5a" },
                { name: "SO2", type: "line", smooth: true, data: payload.hourly.map((item) => item.so2_pred), color: "#8854d0" },
                { name: "CO", type: "line", yAxisIndex: 1, smooth: true, data: payload.hourly.map((item) => item.co_pred), color: "#0fb9b1" },
            ],
        });

        AppUtils.mountChart("forecastValidationChart").setOption({
            tooltip: { trigger: "axis" },
            legend: { data: ["实际值", "趋势模型", "XGBoost", "集成预测", "误差"] },
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
                { name: "实际值", type: "line", smooth: true, data: payload.validation.map((item) => item.actual), color: "#eb3b5a" },
                { name: "趋势模型", type: "line", smooth: true, data: payload.validation.map((item) => item.trend), color: "#20bf6b" },
                { name: "XGBoost", type: "line", smooth: true, data: payload.validation.map((item) => item.xgboost), color: "#fa8231" },
                { name: "集成预测", type: "line", smooth: true, data: payload.validation.map((item) => item.predicted), color: "#2784e8" },
                { name: "误差", type: "bar", yAxisIndex: 1, data: payload.validation.map((item) => item.error), color: "#26de81" },
            ],
        });
    }

    document.getElementById("forecastGenerateButton").addEventListener("click", async () => {
        const city = AppUtils.getCurrentCity();
        const message = document.getElementById("forecastGenerateMessage");
        message.textContent = "正在生成 24 小时预测...";
        try {
            const response = await fetch("/api/forecast/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ city }),
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.message || `请求失败：${response.status}`);
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
