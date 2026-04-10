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

function showStatusMessage(elementId, text) {
    const element = document.getElementById(elementId);
    if (!element) {
        return;
    }
    element.textContent = text || "";
    element.classList.toggle("status-message-hidden", !text);
}

function renderAutoCollectorSummary(payload) {
    const lastRunNode = document.getElementById("autoCollectorLastRun");
    if (!lastRunNode) {
        return;
    }
    const statusText = formatAutoStatus(payload.last_status);
    const lastRunAt = payload.last_run_at || "--";
    const lastStatus = payload.last_message ? `；最近状态：${statusText}` : "";
    lastRunNode.textContent = `上次执行：${lastRunAt}${lastStatus}`;
}

async function loadAutoCollectorSettings() {
    const payload = await AppUtils.fetchJSON("/api/collector/auto-settings");
    const intervalInput = document.getElementById("autoCollectorInterval");
    const hoursInput = document.getElementById("autoCollectorHours");
    if (!intervalInput || !hoursInput) {
        return;
    }

    intervalInput.value = payload.interval_seconds || 1800;
    hoursInput.value = payload.collection_hours || 24;
    renderAutoCollectorSummary(payload);
}

function saveRealtimeTaskId(taskId) {
    try {
        if (taskId) {
            window.localStorage.setItem(realtimeTaskStorageKey, taskId);
        } else {
            window.localStorage.removeItem(realtimeTaskStorageKey);
        }
    } catch (error) {
        console.warn("保存实时任务 ID 失败", error);
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
        console.warn("保存历史任务 ID 失败", error);
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
    button.textContent = isRunning ? "采集中..." : "采集历史数据";
}

function setRealtimeSubmitButtonState(isRunning) {
    const button = document.getElementById("runAutoCollectorNowButton");
    if (!button) {
        return;
    }
    button.disabled = isRunning;
    button.textContent = isRunning ? "采集中..." : "立即采集真实小时数据";
}

function renderTaskCommon(task, elements, emptyText) {
    const { statusText, percentText, progressBar, taskMeta, taskLogList, updateButtonState } = elements;

    if (!task) {
        statusText.textContent = emptyText;
        percentText.textContent = "0%";
        progressBar.style.width = "0%";
        taskMeta.textContent = "这里显示任务状态和日志。";
        taskLogList.innerHTML = "";
        updateButtonState(false);
        return;
    }

    statusText.textContent = `${task.status_label || task.status}：${task.message || "任务开始执行中..."}`;
    percentText.textContent = `${task.progress || 0}%`;
    progressBar.style.width = `${task.progress || 0}%`;
    taskMeta.textContent = `开始时间：${task.started_at || "--"}${task.finished_at ? `；结束时间：${task.finished_at}` : ""}`;
    taskLogList.innerHTML = (task.logs || [])
        .slice()
        .reverse()
        .map(
            (item) => `
                <div class="history-task-log-item history-task-log-${item.level || "info"}">
                    <span class="history-task-log-time">${item.time}</span>
                    <span class="history-task-log-message">${item.message}</span>
                </div>
            `
        )
        .join("");

    updateButtonState(task.status === "running" || task.status === "pending");
}

function renderHistoryTask(task) {
    renderTaskCommon(
        task,
        {
            statusText: document.getElementById("historyTaskStatusText"),
            percentText: document.getElementById("historyTaskPercent"),
            progressBar: document.getElementById("historyTaskProgressBar"),
            taskMeta: document.getElementById("historyTaskMeta"),
            taskLogList: document.getElementById("historyTaskLogList"),
            updateButtonState: setHistorySubmitButtonState,
        },
        "当前没有历史采集任务"
    );
}

function renderRealtimeTask(task) {
    renderTaskCommon(
        task,
        {
            statusText: document.getElementById("autoTaskStatusText"),
            percentText: document.getElementById("autoTaskPercent"),
            progressBar: document.getElementById("autoTaskProgressBar"),
            taskMeta: document.getElementById("autoTaskMeta"),
            taskLogList: document.getElementById("autoTaskLogList"),
            updateButtonState: setRealtimeSubmitButtonState,
        },
        "当前没有实时采集任务"
    );
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
        if (String(error.message || "").includes("404")) {
            collectState.activeHistoryTaskId = "";
            saveHistoryTaskId("");
            renderHistoryTask(null);
            showStatusMessage("historyCollectorMessage", "服务重启后，之前的历史任务记录已失效。");
            if (collectState.historyPollTimer) {
                window.clearTimeout(collectState.historyPollTimer);
                collectState.historyPollTimer = null;
            }
            return;
        }
        renderHistoryTask({
            status: "failed",
            status_label: "失败",
            progress: 0,
            message: `获取任务状态失败：${error.message}`,
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
        if (String(error.message || "").includes("404")) {
            collectState.activeRealtimeTaskId = "";
            saveRealtimeTaskId("");
            renderRealtimeTask(null);
            showStatusMessage("autoCollectorMessage", "服务重启后，之前的实时任务记录已失效。");
            if (collectState.realtimePollTimer) {
                window.clearTimeout(collectState.realtimePollTimer);
                collectState.realtimePollTimer = null;
            }
            return;
        }
        renderRealtimeTask({
            status: "failed",
            status_label: "失败",
            progress: 0,
            message: `获取任务状态失败：${error.message}`,
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
        <div class="pagination-summary">第 ${currentPage} / ${totalPages} 页，共 ${total} 条日志</div>
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
    AppUtils.fillSelect("historyProvinceSelect", collectorMeta.provinces, collectorMeta.provinces[0] || "");
}

function toDateInputValue(date) {
    const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return localDate.toISOString().slice(0, 10);
}

async function loadCollectPage() {
    await AppUtils.getCitiesPayload();

    const historyScopeSelect = document.getElementById("historyScopeSelect");
    const historyProvinceSelect = document.getElementById("historyProvinceSelect");
    const historyStartDate = document.getElementById("historyStartDate");
    const historyEndDate = document.getElementById("historyEndDate");
    const historyRangeHint = document.getElementById("historyRangeHint");

    renderHistoryTask(null);
    renderRealtimeTask(null);

    function updateHistoryRangeHint() {
        if (!historyStartDate.value || !historyEndDate.value) {
            historyRangeHint.textContent = "请选择开始日期和结束日期";
            return;
        }
        const startDateValue = new Date(`${historyStartDate.value}T00:00:00`);
        const endDateValue = new Date(`${historyEndDate.value}T00:00:00`);
        const diff = Math.floor((endDateValue - startDateValue) / (24 * 60 * 60 * 1000)) + 1;
        historyRangeHint.textContent = `当前范围：${diff > 0 ? diff : 0} 天`;
    }

    function normalizeHistoryDates() {
        if (historyStartDate.value && historyEndDate.value && historyStartDate.value > historyEndDate.value) {
            historyEndDate.value = historyStartDate.value;
        }
        updateHistoryRangeHint();
    }

    function applyQuickRange(days) {
        const endDate = new Date();
        const startDateValue = new Date(endDate);
        startDateValue.setDate(startDateValue.getDate() - (days - 1));
        historyStartDate.value = toDateInputValue(startDateValue);
        historyEndDate.value = toDateInputValue(endDate);
        updateHistoryRangeHint();
    }

    const now = new Date();
    const endDateText = toDateInputValue(now);
    const startDate = new Date(now);
    startDate.setDate(startDate.getDate() - 6);
    const startDateText = toDateInputValue(startDate);

    historyStartDate.max = endDateText;
    historyEndDate.max = endDateText;
    historyStartDate.value = startDateText;
    historyEndDate.value = endDateText;
    updateHistoryRangeHint();

    historyScopeSelect.addEventListener("change", () => {
        historyProvinceSelect.disabled = historyScopeSelect.value !== "province";
    });
    historyStartDate.addEventListener("change", normalizeHistoryDates);
    historyEndDate.addEventListener("change", () => {
        if (historyStartDate.value && historyEndDate.value < historyStartDate.value) {
            historyStartDate.value = historyEndDate.value;
        }
        updateHistoryRangeHint();
    });

    document.querySelectorAll(".range-shortcut").forEach((button) => {
        button.addEventListener("click", () => {
            if (button.dataset.days === "year") {
                const now = new Date();
                historyStartDate.value = `${now.getFullYear()}-01-01`;
                historyEndDate.value = toDateInputValue(now);
                updateHistoryRangeHint();
            } else {
                applyQuickRange(Number(button.dataset.days));
            }
        });
    });

    document.getElementById("autoCollectorForm").addEventListener("submit", async (event) => {
        event.preventDefault();
        const intervalSeconds = Number(document.getElementById("autoCollectorInterval").value || 0);
        const collectionHours = Number(document.getElementById("autoCollectorHours").value || 0);

        if (intervalSeconds < 60) {
            showStatusMessage("autoCollectorMessage", "采集间隔不能小于 60 秒。");
            return;
        }
        if (collectionHours < 1) {
            showStatusMessage("autoCollectorMessage", "采集小时数不能小于 1。");
            return;
        }

        showStatusMessage("autoCollectorMessage", "正在保存自动采集设置...");
        try {
            const result = await AppUtils.fetchJSON("/api/collector/auto-settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    enabled: true,
                    interval_seconds: intervalSeconds,
                    collection_hours: collectionHours,
                }),
            });
            renderAutoCollectorSummary(result);
            showStatusMessage(
                "autoCollectorMessage",
                `保存成功：采集间隔 ${result.interval_seconds} 秒，采集小时数 ${result.collection_hours} 小时。`
            );
        } catch (error) {
            showStatusMessage("autoCollectorMessage", `保存失败：${error.message}`);
        }
    });

    document.getElementById("runAutoCollectorNowButton").addEventListener("click", async () => {
        showStatusMessage("autoCollectorMessage", "正在启动实时采集任务...");
        setRealtimeSubmitButtonState(true);
        try {
            const response = await fetch("/api/collector/realtime/start", { method: "POST" });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.message || `Request failed: ${response.status}`);
            }
            collectState.activeRealtimeTaskId = result.task_id;
            saveRealtimeTaskId(result.task_id);
            renderRealtimeTask(result);
            showStatusMessage("autoCollectorMessage", "实时采集任务已提交。");
            if (collectState.realtimePollTimer) {
                window.clearTimeout(collectState.realtimePollTimer);
            }
            pollRealtimeTask(result.task_id);
        } catch (error) {
            showStatusMessage("autoCollectorMessage", `实时采集失败：${error.message}`);
            setRealtimeSubmitButtonState(false);
        }
    });

    document.getElementById("historyCollectorForm").addEventListener("submit", async (event) => {
        event.preventDefault();
        const scope = historyScopeSelect.value;
        const startDateValue = historyStartDate.value;
        const endDateValue = historyEndDate.value;
        if (!startDateValue || !endDateValue) {
            showStatusMessage("historyCollectorMessage", "请选择开始日期和结束日期。");
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
            const currentCity = AppUtils.getCurrentCity();
            if (!currentCity) {
                showStatusMessage("historyCollectorMessage", "当前还没有可用城市，请先导入或采集数据，或改用全部城市/指定省份。");
                setHistorySubmitButtonState(false);
                return;
            }
            payload.cities = [currentCity];
        }

        showStatusMessage("historyCollectorMessage", "正在启动历史采集任务...");
        setHistorySubmitButtonState(true);
        try {
            const response = await fetch("/api/collector/history/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.message || `Request failed: ${response.status}`);
            }
            collectState.activeHistoryTaskId = result.task_id;
            saveHistoryTaskId(result.task_id);
            renderHistoryTask(result);
            showStatusMessage("historyCollectorMessage", "历史采集任务已提交。");
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
