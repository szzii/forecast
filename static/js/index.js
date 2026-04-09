async function loadOverviewPage() {
    const cityPayload = await AppUtils.getCitiesPayload();
    AppUtils.fillSelect("overviewYearSelect", (cityPayload.years || []).map(String), String(cityPayload.default_year));

    if (!cityPayload.cities.length) {
        AppUtils.renderMetricCards("overviewCards", [
            { label: "数据状态", value: "--", extra: "暂无城市数据，请先导入真实数据。" },
        ]);
        document.getElementById("overviewSuggestion").textContent = "提示：暂无空气质量数据，请先在预测页导入 CSV / Excel。";
        return;
    }

    async function render() {
        const city = AppUtils.getCurrentCity();
        const year = document.getElementById("overviewYearSelect").value;
        const [overview, trend] = await Promise.all([
            AppUtils.fetchJSON(`/api/overview?city=${encodeURIComponent(city)}`),
            AppUtils.fetchJSON(`/api/trend?city=${encodeURIComponent(city)}&year=${year}`),
        ]);

        AppUtils.renderMetricCards("overviewCards", [
            { label: "实时 AQI", value: overview.metrics.aqi ?? "--", extra: `${overview.city} · ${overview.record_time}` },
            { label: "PM2.5", value: overview.metrics.pm25 ?? "--", extra: "单位 μg/m³" },
            { label: "PM10", value: overview.metrics.pm10 ?? "--", extra: "单位 μg/m³" },
            { label: "温湿度", value: overview.metrics.temperature == null ? "--" : `${overview.metrics.temperature}° / ${overview.metrics.humidity}%`, extra: overview.metrics.wind_speed == null ? overview.message : `风速 ${overview.metrics.wind_speed} m/s` },
        ]);

        document.getElementById("overviewLevel").textContent = `空气质量等级：${overview.level}`;
        document.getElementById("overviewPrimaryPollutant").textContent = `首要污染物：${overview.primary_pollutant}`;
        document.getElementById("overviewSuggestion").textContent = `提示：${overview.has_data ? overview.suggestion : overview.message}`;

        const months = trend.monthly.map((item) => item.month);
        const trendChart = AppUtils.mountChart("overviewTrendChart");
        trendChart.setOption({
            tooltip: { trigger: "axis" },
            legend: { data: ["AQI 最大值", "AQI 最小值", "AQI 平均值"] },
            grid: { left: 40, right: 24, top: 48, bottom: 36 },
            xAxis: { type: "category", data: months },
            yAxis: { type: "value" },
            graphic: trend.has_data ? [] : [{
                type: "text",
                left: "center",
                top: "middle",
                style: { text: trend.message, fill: "#6c7a89", fontSize: 16 },
            }],
            series: [
                { name: "AQI 最大值", type: "line", smooth: true, data: trend.monthly.map((item) => item.aqi_max), color: "#d65b6a" },
                { name: "AQI 最小值", type: "line", smooth: true, data: trend.monthly.map((item) => item.aqi_min), color: "#5c8be0" },
                { name: "AQI 平均值", type: "line", smooth: true, data: trend.monthly.map((item) => item.aqi_avg), color: "#2784e8" },
            ],
        });

        const pollutantChart = AppUtils.mountChart("overviewPollutantChart");
        pollutantChart.setOption({
            tooltip: { trigger: "axis" },
            legend: { data: ["PM2.5", "PM10", "NO2", "O3"] },
            grid: { left: 44, right: 24, top: 48, bottom: 36 },
            xAxis: { type: "category", data: months },
            yAxis: { type: "value" },
            graphic: trend.has_data ? [] : [{
                type: "text",
                left: "center",
                top: "middle",
                style: { text: trend.message, fill: "#6c7a89", fontSize: 16 },
            }],
            series: [
                { name: "PM2.5", type: "bar", data: trend.monthly.map((item) => item.pm25_avg), color: "#4b7bec" },
                { name: "PM10", type: "bar", data: trend.monthly.map((item) => item.pm10_avg), color: "#26de81" },
                { name: "NO2", type: "bar", data: trend.monthly.map((item) => item.no2_avg), color: "#f7b731" },
                { name: "O3", type: "bar", data: trend.monthly.map((item) => item.o3_avg), color: "#eb3b5a" },
            ],
        });

        const ranking = [...trend.ranking].reverse();
        const rankChart = AppUtils.mountChart("overviewRankChart");
        rankChart.setOption({
            tooltip: { trigger: "axis" },
            grid: { left: 72, right: 24, top: 24, bottom: 24 },
            xAxis: { type: "value" },
            yAxis: { type: "category", data: ranking.map((item) => item.city) },
            graphic: trend.ranking.length ? [] : [{
                type: "text",
                left: "center",
                top: "middle",
                style: { text: "暂无城市排名数据", fill: "#6c7a89", fontSize: 16 },
            }],
            series: [{
                type: "bar",
                data: ranking.map((item) => ({
                    value: item.aqi,
                    itemStyle: { color: item.color },
                })),
                barWidth: 16,
            }],
        });

        const pieChart = AppUtils.mountChart("overviewQualityPie");
        pieChart.setOption({
            tooltip: { trigger: "item" },
            legend: { bottom: 0 },
            graphic: trend.distribution.length ? [] : [{
                type: "text",
                left: "center",
                top: "middle",
                style: { text: "暂无等级分布数据", fill: "#6c7a89", fontSize: 16 },
            }],
            series: [{
                type: "pie",
                radius: ["42%", "70%"],
                center: ["50%", "44%"],
                data: trend.distribution.map((item) => ({
                    value: item.value,
                    name: item.name,
                    itemStyle: { color: item.color },
                })),
                label: { formatter: "{b}\n{d}%" },
            }],
        });
    }

    document.getElementById("overviewQueryButton").addEventListener("click", render);
    document.addEventListener("aq-city-change", render);
    await render();
}

document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("overviewYearSelect")) {
        loadOverviewPage();
    }
});
