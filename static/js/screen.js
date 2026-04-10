function renderScreenSummary(summary) {
    const container = document.getElementById("screenSummaryCards");
    container.innerHTML = [
        { label: "城市平均 AQI", value: summary.avg_aqi, desc: "基于当前示例城市最新记录" },
        { label: "空气最佳城市", value: summary.best_city, desc: "当前空气质量表现最优" },
        { label: "空气最差城市", value: summary.worst_city, desc: "当前需要重点关注" },
        { label: "优良率", value: `${summary.excellent_rate}%`, desc: `预警城市 ${summary.alarm_count} 个` },
    ].map((item) => `
        <article class="screen-summary-card">
            <div class="label">${item.label}</div>
            <div class="value">${item.value}</div>
            <div class="desc">${item.desc}</div>
        </article>
    `).join("");
}

async function loadScreenPage() {
    const storageKey = "aq_screen_city";
    const cityPayload = await AppUtils.getCitiesPayload();
    const cityInput = document.getElementById("screenCitySearch");
    const cityOptions = document.getElementById("screenCityOptions");
    const savedCity = (() => {
        try {
            return window.localStorage.getItem(storageKey) || "";
        } catch (error) {
            return "";
        }
    })();
    const defaultCity = cityPayload.cities.includes(savedCity)
        ? savedCity
        : (AppUtils.getCurrentCity() || cityPayload.default_city);

    function fillCityOptions(values) {
        cityOptions.innerHTML = values.map((city) => `<option value="${city}"></option>`).join("");
    }

    fillCityOptions(cityPayload.cities);
    cityInput.value = defaultCity;

    async function render() {
        const city = cityInput.value.trim();
        const payload = await AppUtils.fetchJSON(`/api/screen?city=${encodeURIComponent(city)}`);
        try {
            window.localStorage.setItem(storageKey, payload.selected_city || city);
        } catch (error) {
            // ignore local storage failures on demo page
        }
        cityInput.value = payload.selected_city || city;
        document.getElementById("screenUpdatedAt").textContent = `更新时间：${payload.updated_at}`;
        document.getElementById("screenTrendTitle").textContent = `${payload.selected_city} ${payload.selected_year} 年度趋势监测`;
        document.getElementById("screenForecastTitle").textContent = `${payload.selected_city} 未来 12 小时预测波动`;
        renderScreenSummary(payload.summary);

        const ranking = [...payload.ranking].reverse();
        AppUtils.mountChart("screenRankingChart").setOption({
            grid: { left: 60, right: 32, top: 18, bottom: 18 },
            xAxis: { type: "value", axisLabel: { color: "#cde7ff" }, splitLine: { lineStyle: { color: "rgba(125,180,220,.12)" } } },
            yAxis: { type: "category", axisLabel: { color: "#cde7ff" }, data: ranking.map((item) => item.city) },
            dataZoom: ranking.length > 1 ? [{
                type: "slider",
                yAxisIndex: 0,
                orient: "vertical",
                right: 4,
                start: 0,
                end: 100,
                width: 14,
                borderColor: "rgba(77,184,255,0.2)",
                fillerColor: "rgba(77,184,255,0.15)",
                handleStyle: { color: "#4db8ff" },
                textStyle: { color: "transparent" },
            }, {
                type: "inside",
                yAxisIndex: 0,
                orient: "vertical",
            }] : [],
            series: [{
                type: "bar",
                barWidth: 12,
                data: ranking.map((item) => item.aqi),
                itemStyle: {
                    color: new echarts.graphic.LinearGradient(1, 0, 0, 0, [
                        { offset: 0, color: "#4db8ff" },
                        { offset: 1, color: "#0fd9a7" },
                    ]),
                },
            }],
        });

        AppUtils.mountChart("screenTrendChart").setOption({
            tooltip: { trigger: "axis" },
            legend: { textStyle: { color: "#cde7ff" }, data: ["AQI 平均值", "PM2.5"] },
            grid: { left: 44, right: 18, top: 42, bottom: 28 },
            xAxis: { type: "category", axisLabel: { color: "#cde7ff" }, data: payload.trend.map((item) => item.month) },
            yAxis: { type: "value", axisLabel: { color: "#cde7ff" }, splitLine: { lineStyle: { color: "rgba(125,180,220,.12)" } } },
            series: [
                { name: "AQI 平均值", type: "line", smooth: true, data: payload.trend.map((item) => item.aqi_avg), color: "#4db8ff", areaStyle: { color: "rgba(77,184,255,.12)" } },
                { name: "PM2.5", type: "line", smooth: true, data: payload.trend.map((item) => item.pm25_avg), color: "#f9ca24" },
            ],
        });

        const distributionMap = new Map();
        payload.distribution.forEach((item) => {
            distributionMap.set(item.name, (distributionMap.get(item.name) || 0) + item.value);
        });
        AppUtils.mountChart("screenDistributionChart").setOption({
            tooltip: { trigger: "item" },
            legend: { bottom: 0, textStyle: { color: "#cde7ff" } },
            series: [{
                type: "pie",
                radius: ["42%", "72%"],
                center: ["50%", "44%"],
                label: { color: "#dff3ff" },
                data: [...distributionMap.entries()].map(([name, value]) => ({ name, value })),
            }],
        });

        AppUtils.mountChart("screenForecastChart").setOption({
            tooltip: { trigger: "axis" },
            grid: { left: 44, right: 18, top: 28, bottom: 28 },
            xAxis: { type: "category", axisLabel: { color: "#cde7ff" }, data: payload.forecast_wave.map((item) => item.time) },
            yAxis: { type: "value", axisLabel: { color: "#cde7ff" }, splitLine: { lineStyle: { color: "rgba(125,180,220,.12)" } } },
            series: [{
                type: "line",
                smooth: true,
                data: payload.forecast_wave.map((item) => item.ensemble_aqi),
                color: "#ff9f43",
                areaStyle: { color: "rgba(255,159,67,.15)" },
            }],
        });

        document.getElementById("screenAlertTable").innerHTML = payload.alerts
            .map((item) => `
                <tr>
                    <td>${item.city}</td>
                    <td>${item.aqi}</td>
                    <td>${item.level}</td>
                    <td>${item.primary_pollutant}</td>
                </tr>
            `)
            .join("");

        document.getElementById("screenCrawlerTable").innerHTML = payload.crawler
            .map((item) => `
                <tr>
                    <td>${item.task_name}</td>
                    <td>${item.status}</td>
                    <td>${item.run_at}</td>
                </tr>
            `)
            .join("");
    }

    cityInput.addEventListener("input", () => {
        const keyword = cityInput.value.trim();
        const matchedCities = keyword
            ? cityPayload.cities.filter((city) => city.includes(keyword))
            : cityPayload.cities;
        fillCityOptions(matchedCities.length ? matchedCities : cityPayload.cities);
    });

    async function applyCitySearch() {
        const keyword = cityInput.value.trim();
        if (!keyword) {
            cityInput.value = defaultCity;
            await render();
            return;
        }
        if (cityPayload.cities.includes(keyword)) {
            await render();
            return;
        }
        const matchedCities = cityPayload.cities.filter((city) => city.includes(keyword));
        if (matchedCities.length === 1) {
            cityInput.value = matchedCities[0];
            await render();
            return;
        }
        fillCityOptions(matchedCities.length ? matchedCities : cityPayload.cities);
    }

    cityInput.addEventListener("change", applyCitySearch);
    cityInput.addEventListener("search", applyCitySearch);
    cityInput.addEventListener("blur", applyCitySearch);
    cityInput.addEventListener("keydown", async (event) => {
        if (event.key !== "Enter") {
            return;
        }
        event.preventDefault();
        await applyCitySearch();
    });

    await render();
    setInterval(render, 60000);
}

document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("screenSummaryCards")) {
        loadScreenPage();
    }
});
