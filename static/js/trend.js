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

        AppUtils.mountChart("trendPrimaryPollutantChart").setOption({
            tooltip: { trigger: "axis" },
            legend: { data: ["PM2.5", "PM10", "NO2", "O3", "SO2", "CO"] },
            grid: { left: 48, right: 56, top: 48, bottom: 36 },
            xAxis: { type: "category", data: months },
            yAxis: [
                { type: "value", name: "μg/m³", nameTextStyle: { color: "#6c7a89" } },
                { type: "value", name: "CO mg/m³", position: "right", nameTextStyle: { color: "#0fb9b1" } },
            ],
            graphic: trend.has_data ? [] : [{
                type: "text",
                left: "center",
                top: "middle",
                style: { text: trend.message, fill: "#6c7a89", fontSize: 16 },
            }],
            series: [
                { name: "PM2.5", type: "line", smooth: true, data: trend.monthly.map((item) => item.pm25_avg), color: "#2784e8" },
                { name: "PM10", type: "line", smooth: true, data: trend.monthly.map((item) => item.pm10_avg), color: "#26de81" },
                { name: "NO2", type: "line", smooth: true, data: trend.monthly.map((item) => item.no2_avg), color: "#f7b731" },
                { name: "O3", type: "line", smooth: true, data: trend.monthly.map((item) => item.o3_avg), color: "#eb3b5a" },
                { name: "SO2", type: "line", smooth: true, data: trend.monthly.map((item) => item.so2_avg), color: "#8854d0" },
                { name: "CO", type: "line", yAxisIndex: 1, smooth: true, data: trend.monthly.map((item) => item.co_avg), color: "#0fb9b1" },
            ],
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
