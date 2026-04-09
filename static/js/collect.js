const collectState = {
    taskPage: 1,
    pageSize: 8,
    activeHistoryTaskId: "",
    historyPollTimer: null,
    activeRealtimeTaskId: "",
    realtimePollTimer: null,
};
const historyTaskStorageKey = "aq_history_task_id";
const realtimeTaskStorageKey = "aq_realtime_task_id";

function formatAutoStatus(status) {
    const mapping = {
        idle: "未执行",
        running: "执行中",
        success: "成功",
        failed: "失败",
    };
    return mapping[status] || status || "--";
}

function renderAutoCollectorSummary(payload) {
    const lastRunNode = document.getElementById("autoCollectorLastRun");
    if (!lastRunNode) {
        return;
    }
    const statusText = formatAutoStatus(payload.last_status);
    const lastRunAt = payload.last_run_at || "--";
    const lastMessage = payload.last_message ? `；最近状态：${statusText}` : "";
    lastRunNode.textContent = `上次执行时间：${lastRunAt}${lastMessage}`;
}

async function loadAutoCollectorSettings() {
    const payload = await AppUtils.fetchJSON("/api/collector/auto-settings");
    const enabledInput = document.getElementById("autoCollectorEnabled");
    const intervalInput = document.getElementById("autoCollectorInterval");
    const hoursInput = document.getElementById("autoCollectorHours");
    if (!enabledInput || !intervalInput || !hoursInput) {
        return;
    }

    enabledInput.checked = Boolean(payload.enabled);
    intervalInput.value = payload.interval_seconds || 1800;
    hoursInput.value = payload.collection_hours || 24;
    renderAutoCollectorSummary(payload);
}

function showStatusMessage(elementId, text) {
    const element = document.getElementById(elementId);
    if (!element) {
        return;
    }
    element.textContent = text || "";
    element.classList.toggle("status-message-hidden", !text);
}

function saveRealtimeTaskId(taskId) {
    try {
        if (taskId) {
            window.localStorage.setItem(realtimeTaskStorageKey, taskId);
        } else {
            window.localStorage.removeItem(realtimeTaskStorageKey);
        }
    } catch (error) {
        console.warn("保存实时采集任务状态失败", error);
    }
}

function loadSavedRealtimeTaskId() {
    try {
        return window.localStorage.getItem(realtimeTaskStorageKey) || "";
    } catch (error) {
        return "";
    }
}

function saveHistoryTaskId(taskId) {
    try {
        if (taskId) {
            window.localStorage.setItem(historyTaskStorageKey, taskId);
        } else {
            window.localStorage.removeItem(historyTaskStorageKey);
        }
    } catch (error) {
        console.warn("保存历史采集任务状态失败", error);
    }
}

function loadSavedHistoryTaskId() {
    try {
        return window.localStorage.getItem(historyTaskStorageKey) || "";
    } catch (error) {
        return "";
    }
}

function setHistorySubmitButtonState(isRunning) {
    const button = document.getElementById("historyCollectSubmitButton");
    if (!button) {
        return;
    }
    button.disabled = isRunning;
    button.textContent = isRunning ? "历史采集中..." : "采集历史数据";
}

function setRealtimeSubmitButtonState(isRunning) {
    const button = document.getElementById("runAutoCollectorNowButton");
    if (!button) {
        return;
    }
    button.disabled = isRunning;
    button.textContent = isRunning ? "采集中..." : "立即采集真实小时数据";
}

function renderHistoryTask(task) {
    const statusText = document.getElementById("historyTaskStatusText");
    const percentText = document.getElementById("historyTaskPercent");
    const progressBar = document.getElementById("historyTaskProgressBar");
    const taskMeta = document.getElementById("historyTaskMeta");
    const taskLogList = document.getElementById("historyTaskLogList");

    if (!task) {
        statusText.textContent = "当前没有正在执行的历史采集任务";
        percentText.textContent = "0%";
        progressBar.style.width = "0%";
        taskMeta.textContent = "点击上方“采集历史数据”后，这里会显示执行中状态和分批进度。";
        taskLogList.innerHTML = "";
        setHistorySubmitButtonState(false);
        return;
    }

    statusText.textContent = `${task.status_label || task.status}：${task.message || "任务正在准备中..."}`;
    percentText.textContent = `${task.progress || 0}%`;
    progressBar.style.width = `${task.progress || 0}%`;
    taskMeta.textContent = `任务开始时间：${task.started_at || "--"}${task.finished_at ? `；结束时间：${task.finished_at}` : ""}`;
    taskLogList.innerHTML = (task.logs || [])
        .slice()
        .reverse()
        .map((item) => `
            <div class="history-task-log-item history-task-log-${item.level || "info"}">
                <span class="history-task-log-time">${item.time}</span>
                <span class="history-task-log-message">${item.message}</span>
            </div>
        `)
        .join("");

    setHistorySubmitButtonState(task.status === "running" || task.status === "pending");
}

function renderRealtimeTask(task) {
    const statusText = document.getElementById("autoTaskStatusText");
    const percentText = document.getElementById("autoTaskPercent");
    const progressBar = document.getElementById("autoTaskProgressBar");
    const taskMeta = document.getElementById("autoTaskMeta");
    const taskLogList = document.getElementById("autoTaskLogList");

    if (!task) {
        statusText.textContent = "当前没有正在执行的立即采集任务";
        percentText.textContent = "0%";
        progressBar.style.width = "0%";
        taskMeta.textContent = "点击“立即采集真实小时数据”后，这里会显示执行中状态和详细日志。";
        taskLogList.innerHTML = "";
        setRealtimeSubmitButtonState(false);
        return;
    }

    statusText.textContent = `${task.status_label || task.status}：${task.message || "任务正在准备中..."}`;
    percentText.textContent = `${task.progress || 0}%`;
    progressBar.style.width = `${task.progress || 0}%`;
    taskMeta.textContent = `任务开始时间：${task.started_at || "--"}${task.finished_at ? `；结束时间：${task.finished_at}` : ""}`;
    taskLogList.innerHTML = (task.logs || [])
        .slice()
        .reverse()
        .map((item) => `
            <div class="history-task-log-item history-task-log-${item.level || "info"}">
                <span class="history-task-log-time">${item.time}</span>
                <span class="history-task-log-message">${item.message}</span>
            </div>
        `)
        .join("");

    setRealtimeSubmitButtonState(task.status === "running" || task.status === "pending");
}

async function pollHistoryTask(taskId) {
    try {
        const task = await AppUtils.fetchJSON(`/api/collector/history/tasks/${taskId}`);
        renderHistoryTask(task);
        const isRunning = task.status === "running" || task.status === "pending";
        if (!isRunning) {
            collectState.activeHistoryTaskId = taskId;
            saveHistoryTaskId(taskId);
            if (collectState.historyPollTimer) {
                window.clearTimeout(collectState.historyPollTimer);
                collectState.historyPollTimer = null;
            }
            await Promise.all([loadCrawlerStatus(1), loadCollectorMetadata()]);
            return;
        }
        collectState.historyPollTimer = window.setTimeout(() => {
            pollHistoryTask(taskId);
        }, 1200);
    } catch (error) {
        renderHistoryTask({
            status: "failed",
            status_label: "失败",
            progress: 0,
            message: `任务状态获取失败：${error.message}`,
            logs: [],
        });
        collectState.activeHistoryTaskId = "";
        saveHistoryTaskId("");
        if (collectState.historyPollTimer) {
            window.clearTimeout(collectState.historyPollTimer);
            collectState.historyPollTimer = null;
        }
    }
}

async function pollRealtimeTask(taskId) {
    try {
        const task = await AppUtils.fetchJSON(`/api/collector/realtime/tasks/${taskId}`);
        renderRealtimeTask(task);
        const isRunning = task.status === "running" || task.status === "pending";
        if (!isRunning) {
            collectState.activeRealtimeTaskId = taskId;
            saveRealtimeTaskId(taskId);
            if (collectState.realtimePollTimer) {
                window.clearTimeout(collectState.realtimePollTimer);
                collectState.realtimePollTimer = null;
            }
            await Promise.all([loadCrawlerStatus(1), loadCollectorMetadata(), loadAutoCollectorSettings()]);
            return;
        }
        collectState.realtimePollTimer = window.setTimeout(() => {
            pollRealtimeTask(taskId);
        }, 1200);
    } catch (error) {
        renderRealtimeTask({
            status: "failed",
            status_label: "失败",
            progress: 0,
            message: `任务状态获取失败：${error.message}`,
            logs: [],
        });
        collectState.activeRealtimeTaskId = "";
        saveRealtimeTaskId("");
        if (collectState.realtimePollTimer) {
            window.clearTimeout(collectState.realtimePollTimer);
            collectState.realtimePollTimer = null;
        }
    }
}

async function loadCrawlerStatus(page = collectState.taskPage) {
    collectState.taskPage = page;
    const payload = await AppUtils.fetchJSON(`/api/crawler?page=${page}&page_size=${collectState.pageSize}`);
    const taskBody = document.getElementById("crawlerTaskTable");
    const paginationBar = document.getElementById("crawlerTaskPagination");

    taskBody.innerHTML = payload.tasks
        .map(
            (item) => `
                <tr>
                    <td>${item.task_name}</td>
                    <td>${item.source_name}</td>
                    <td>${item.status_label || item.status}</td>
                    <td>${item.records_count}</td>
                    <td>${item.message || "--"}</td>
                    <td>${item.run_at}</td>
                </tr>
            `
        )
        .join("");

    const { page: currentPage, total_pages: totalPages, total } = payload.pagination;
    paginationBar.innerHTML = `
        <div class="pagination-summary">第 ${currentPage} / ${totalPages} 页，共 ${total} 条任务日志</div>
        <div class="pagination-actions">
            <button type="button" class="btn-secondary pagination-button" data-page="${Math.max(currentPage - 1, 1)}" ${currentPage <= 1 ? "disabled" : ""}>上一页</button>
            <button type="button" class="btn-secondary pagination-button" data-page="${Math.min(currentPage + 1, totalPages)}" ${currentPage >= totalPages ? "disabled" : ""}>下一页</button>
        </div>
    `;

    paginationBar.querySelectorAll(".pagination-button").forEach((button) => {
        button.addEventListener("click", () => {
            loadCrawlerStatus(Number(button.dataset.page));
        });
    });
}

async function loadCollectorMetadata() {
    const collectorMeta = await AppUtils.fetchJSON("/api/collector/metadata");
    const currentCity = AppUtils.getCurrentCity();
    AppUtils.fillSelect("historyProvinceSelect", collectorMeta.provinces, collectorMeta.provinces[0] || "");
    AppUtils.renderMetricCards("collectSummaryCards", [
        { label: "全国城市总数", value: collectorMeta.total_cities, extra: "全国城市主数据规模" },
        { label: "已解析坐标", value: collectorMeta.resolved_cities, extra: "可直接参与实时/历史采集" },
        { label: "当前采集城市", value: currentCity || "--", extra: `待补全 ${collectorMeta.unresolved_cities} 个城市坐标` },
    ]);

    const collectorMetaMessage = document.getElementById("collectorMetaMessage");
    collectorMetaMessage.textContent = `全国城市主数据共 ${collectorMeta.total_cities} 个城市，已完成 ${collectorMeta.resolved_cities} 个城市坐标解析，待补全 ${collectorMeta.unresolved_cities} 个。`;
}

async function loadCollectPage() {
    const cityPayload = await AppUtils.getCitiesPayload();
    if (!cityPayload.cities.length) {
        return;
    }

    const historyScopeSelect = document.getElementById("historyScopeSelect");
    const historyProvinceSelect = document.getElementById("historyProvinceSelect");
    const historyStartDate = document.getElementById("historyStartDate");
    const historyEndDate = document.getElementById("historyEndDate");
    const historyRangeHint = document.getElementById("historyRangeHint");
    renderHistoryTask(null);
    renderRealtimeTask(null);

    function updateHistoryRangeHint() {
        if (!historyStartDate.value || !historyEndDate.value) {
            historyRangeHint.textContent = "请选择完整的开始日期和结束日期";
            return;
        }
        const startDateValue = new Date(historyStartDate.value);
        const endDateValue = new Date(historyEndDate.value);
        const diff = Math.floor((endDateValue - startDateValue) / (24 * 60 * 60 * 1000)) + 1;
        historyRangeHint.textContent = `当前采集区间：${diff > 0 ? diff : 0} 天`;
    }

    function applyQuickRange(days) {
        const endDate = new Date();
        const startDateValue = new Date(endDate);
        startDateValue.setDate(startDateValue.getDate() - (days - 1));
        historyStartDate.value = startDateValue.toISOString().slice(0, 10);
        historyEndDate.value = endDate.toISOString().slice(0, 10);
        updateHistoryRangeHint();
    }

    const now = new Date();
    const endDateText = now.toISOString().slice(0, 10);
    const startDate = new Date(now);
    startDate.setDate(startDate.getDate() - 6);
    const startDateText = startDate.toISOString().slice(0, 10);
    historyStartDate.value = startDateText;
    historyEndDate.value = endDateText;
    updateHistoryRangeHint();

    historyScopeSelect.addEventListener("change", () => {
        historyProvinceSelect.disabled = historyScopeSelect.value !== "province";
    });
    historyStartDate.addEventListener("change", updateHistoryRangeHint);
    historyEndDate.addEventListener("change", updateHistoryRangeHint);

    document.querySelectorAll(".range-shortcut").forEach((button) => {
        button.addEventListener("click", () => {
            applyQuickRange(Number(button.dataset.days));
        });
    });

    document.getElementById("autoCollectorForm").addEventListener("submit", async (event) => {
        event.preventDefault();
        const enabled = document.getElementById("autoCollectorEnabled").checked;
        const intervalSeconds = Number(document.getElementById("autoCollectorInterval").value || 0);
        const collectionHours = Number(document.getElementById("autoCollectorHours").value || 0);

        if (intervalSeconds < 60) {
            showStatusMessage("autoCollectorMessage", "采集间隔不能小于 60 秒。");
            return;
        }
        if (collectionHours < 1) {
            showStatusMessage("autoCollectorMessage", "单次回补时长不能小于 1 小时。");
            return;
        }

        showStatusMessage("autoCollectorMessage", "正在保存自动采集定时任务设置，请稍候...");
        try {
            const result = await AppUtils.fetchJSON("/api/collector/auto-settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    enabled,
                    interval_seconds: intervalSeconds,
                    collection_hours: collectionHours,
                }),
            });
            renderAutoCollectorSummary(result);
            showStatusMessage(
                "autoCollectorMessage",
                `保存成功：自动采集已${result.enabled ? "开启" : "关闭"}，采集间隔 ${result.interval_seconds} 秒，单次回补 ${result.collection_hours} 小时。`
            );
        } catch (error) {
            showStatusMessage("autoCollectorMessage", `保存失败：${error.message}`);
        }
    });

    document.getElementById("runAutoCollectorNowButton").addEventListener("click", async () => {
        showStatusMessage("autoCollectorMessage", "正在立即执行一次真实小时数据采集，请稍候...");
        setRealtimeSubmitButtonState(true);
        try {
            const response = await fetch("/api/collector/realtime/start", { method: "POST" });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.message || `请求失败: ${response.status}`);
            }
            collectState.activeRealtimeTaskId = result.task_id;
            saveRealtimeTaskId(result.task_id);
            renderRealtimeTask(result);
            showStatusMessage("autoCollectorMessage", "立即采集任务已提交，系统正在后台执行，可在下方查看执行中状态和详细日志。");
            if (collectState.realtimePollTimer) {
                window.clearTimeout(collectState.realtimePollTimer);
            }
            pollRealtimeTask(result.task_id);
        } catch (error) {
            showStatusMessage("autoCollectorMessage", `立即采集失败：${error.message}`);
            setRealtimeSubmitButtonState(false);
        }
    });

    document.getElementById("historyCollectorForm").addEventListener("submit", async (event) => {
        event.preventDefault();
        const message = document.getElementById("historyCollectorMessage");
        const scope = historyScopeSelect.value;
        const startDateValue = historyStartDate.value;
        const endDateValue = historyEndDate.value;
        if (!startDateValue || !endDateValue) {
            showStatusMessage("historyCollectorMessage", "请先选择开始日期和结束日期。");
            return;
        }

        const payload = {
            start_date: startDateValue,
            end_date: endDateValue,
            scope,
        };
        if (scope === "province") {
            payload.province = historyProvinceSelect.value;
        }
        if (scope === "city") {
            payload.cities = [AppUtils.getCurrentCity()];
        }

        showStatusMessage("historyCollectorMessage", "正在创建历史采集任务，请稍候...");
        setHistorySubmitButtonState(true);
        try {
            const response = await fetch("/api/collector/history/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.message || `请求失败: ${response.status}`);
            }
            collectState.activeHistoryTaskId = result.task_id;
            saveHistoryTaskId(result.task_id);
            renderHistoryTask(result);
            showStatusMessage("historyCollectorMessage", "历史采集任务已提交，系统正在后台执行，可在下方查看执行中状态和进度日志。");
            if (collectState.historyPollTimer) {
                window.clearTimeout(collectState.historyPollTimer);
            }
            pollHistoryTask(result.task_id);
        } catch (error) {
            showStatusMessage("historyCollectorMessage", `历史采集失败：${error.message}`);
            setHistorySubmitButtonState(false);
        }
    });

    document.addEventListener("aq-city-change", () => {
        loadCollectorMetadata();
    });

    const savedTaskId = loadSavedHistoryTaskId();
    if (savedTaskId) {
        collectState.activeHistoryTaskId = savedTaskId;
        pollHistoryTask(savedTaskId);
    }
    const savedRealtimeTaskId = loadSavedRealtimeTaskId();
    if (savedRealtimeTaskId) {
        collectState.activeRealtimeTaskId = savedRealtimeTaskId;
        pollRealtimeTask(savedRealtimeTaskId);
    }

    await Promise.all([loadCrawlerStatus(1), loadCollectorMetadata(), loadAutoCollectorSettings()]);
}

document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("historyCollectorForm")) {
        loadCollectPage();
    }
});
