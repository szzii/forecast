const STATUS_LABELS = {
    good:    { text: "适宜",   cls: "advice-status-good" },
    ok:      { text: "可以",   cls: "advice-status-ok" },
    caution: { text: "谨慎",   cls: "advice-status-caution" },
    bad:     { text: "不建议", cls: "advice-status-bad" },
    danger:  { text: "危险",   cls: "advice-status-danger" },
};

async function loadAdvicePage() {
    const cityPayload = await AppUtils.getCitiesPayload();
    if (!cityPayload.cities.length) return;

    function showRenderError(error) {
        const message = document.getElementById("adviceMessage");
        AppUtils.renderMetricCards("adviceSummaryCards", []);
        document.getElementById("bestHoursPanel").style.display = "none";
        document.getElementById("worstHoursPanel").style.display = "none";
        document.getElementById("advicePeriodList").innerHTML = "";
        document.getElementById("adviceActivityGrid").innerHTML = "";
        message.textContent = error.message || "出行建议加载失败。";
    }

    async function render() {
        const city = AppUtils.getCurrentCity();
        const payload = await AppUtils.fetchJSON(`/api/advice?city=${encodeURIComponent(city)}`);
        const message = document.getElementById("adviceMessage");

        if (!payload.has_data) {
            message.textContent = payload.message || '暂无预测数据，请先在"空气质量预测"页生成预测。';
            AppUtils.renderMetricCards("adviceSummaryCards", []);
            document.getElementById("bestHoursPanel").style.display = "none";
            document.getElementById("worstHoursPanel").style.display = "none";
            document.getElementById("advicePeriodList").innerHTML = "";
            document.getElementById("adviceActivityGrid").innerHTML = "";
            return;
        }

        message.textContent = `预测生成时间：${payload.generated_at}`;
        document.getElementById("bestHoursPanel").style.display = "";
        document.getElementById("worstHoursPanel").style.display = "";

        const s = payload.summary;

        // 顶部指标卡
        AppUtils.renderMetricCards("adviceSummaryCards", [
            {
                label: "全天综合评级",
                value: s.level,
                extra: `平均 AQI ${s.avg_aqi}`,
                valueStyle: `color:${s.color};font-weight:700`,
            },
            {
                label: "AQI 范围",
                value: `${s.min_aqi} – ${s.max_aqi}`,
                extra: "预测最低 – 最高",
            },
            {
                label: "出行总建议",
                value: "",
                extra: s.text,
            },
        ]);

        // 最佳 / 最差时段
        function renderHourList(containerId, hours) {
            const el = document.getElementById(containerId);
            el.innerHTML = hours.map((h, i) => `
                <div class="advice-hour-item">
                    <span class="advice-hour-rank">${i + 1}</span>
                    <span class="advice-hour-time">${h.time}</span>
                    <span class="advice-hour-badge" style="background:${h.color}20;color:${h.color};border-color:${h.color}40">
                        AQI ${h.aqi} · ${h.level}
                    </span>
                </div>
            `).join("");
        }
        renderHourList("bestHoursList", payload.best_hours);
        renderHourList("worstHoursList", payload.worst_hours);

        // 分时段
        const periodEl = document.getElementById("advicePeriodList");
        periodEl.innerHTML = payload.periods.map(p => `
            <div class="advice-period-item">
                <div class="advice-period-label">${p.label}</div>
                <div class="advice-period-bar-wrap">
                    <div class="advice-period-bar" style="width:${Math.min(100, p.avg_aqi / 3)}%;background:${p.color}"></div>
                </div>
                <div class="advice-period-meta">
                    <span style="color:${p.color};font-weight:600">${p.level}</span>
                    <span class="advice-period-aqi">AQI ${p.avg_aqi}</span>
                </div>
            </div>
        `).join("");

        // 活动建议
        const actEl = document.getElementById("adviceActivityGrid");
        actEl.innerHTML = payload.activities.map(a => {
            const st = STATUS_LABELS[a.status] || STATUS_LABELS.ok;
            return `
                <div class="advice-activity-card">
                    <div class="advice-activity-label">${a.label}</div>
                    <div class="advice-activity-status ${st.cls}">${st.text}</div>
                    <div class="advice-activity-text">${a.text}</div>
                </div>
            `;
        }).join("");
    }

    async function renderSafely() {
        try {
            await render();
        } catch (error) {
            showRenderError(error);
        }
    }

    document.getElementById("adviceRefreshBtn").addEventListener("click", async () => {
        const city = AppUtils.getCurrentCity();
        const message = document.getElementById("adviceMessage");
        message.textContent = "正在刷新预测与建议...";
        try {
            await fetch("/api/forecast/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ city }),
            });
        } catch (_) { /* ignore */ }
        await renderSafely();
    });

    document.addEventListener("aq-city-change", () => {
        void renderSafely();
    });
    await renderSafely();
}

document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("adviceRefreshBtn")) {
        loadAdvicePage();
    }
});
