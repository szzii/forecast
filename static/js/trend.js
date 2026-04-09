async function loadTrendPage() {
    const cityPayload = await AppUtils.getCitiesPayload();
    AppUtils.fillSelect("trendYearSelect", (cityPayload.years || []).map(String), String(cityPayload.default_year));

    if (!cityPayload.cities.length) {
        return;
    }

    async function render() {
        const city = AppUtils.getCurrentCity();
        const year = document.getElementById("trendYearSelect").value;
        const trend = await AppUtils.fetchJSON(`/api/trend?city=${encodeURIComponent(city)}&year=${year}`);
        const months = trend.monthly.map((item) => item.month);

        AppUtils.mountChart("trendAnnualChart").setOption({
            tooltip: { trigger: "axis" },
            legend: { data: ["AQI Max", "AQI Min"] },
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
                { name: "AQI Max", type: "line", smooth: true, data: trend.monthly.map((item) => item.aqi_max), color: "#c44569" },
                { name: "AQI Min", type: "line", smooth: true, data: trend.monthly.map((item) => item.aqi_min), color: "#3867d6" },
            ],
        });

        AppUtils.mountChart("trendPollutantChart").setOption({
            tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
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
                { name: "PM2.5", type: "bar", stack: "total", data: trend.monthly.map((item) => item.pm25_avg), color: "#2784e8" },
                { name: "PM10", type: "bar", stack: "total", data: trend.monthly.map((item) => item.pm10_avg), color: "#26de81" },
                { name: "NO2", type: "bar", stack: "total", data: trend.monthly.map((item) => item.no2_avg), color: "#f7b731" },
                { name: "O3", type: "bar", stack: "total", data: trend.monthly.map((item) => item.o3_avg), color: "#eb3b5a" },
            ],
        });

        const ranking = [...trend.ranking].reverse();
        AppUtils.mountChart("trendRankingChart").setOption({
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
                data: ranking.map((item) => ({ value: item.aqi, itemStyle: { color: item.color } })),
                barWidth: 18,
            }],
        });

        AppUtils.mountChart("trendDistributionChart").setOption({
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
                radius: ["34%", "72%"],
                center: ["50%", "44%"],
                data: trend.distribution.map((item) => ({
                    value: item.value,
                    name: item.name,
                    itemStyle: { color: item.color },
                })),
                label: { formatter: "{b}\n{c}" },
            }],
        });
    }

    document.getElementById("trendQueryButton").addEventListener("click", render);
    document.addEventListener("aq-city-change", render);
    await render();
}

document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("trendYearSelect")) {
        loadTrendPage();
    }
});
