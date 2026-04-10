const AppUtils = (() => {
    const chartInstances = new Map();
    const currentCityStorageKey = "aq_current_city";
    let cityPayloadPromise = null;
    let currentCity = "";
    let allCities = [];

    async function fetchJSON(url, options = {}) {
        const response = await fetch(url, options);
        if (!response.ok) {
            throw new Error(`请求失败: ${response.status}`);
        }
        return response.json();
    }

    function mountChart(id) {
        const element = document.getElementById(id);
        if (!element) {
            return null;
        }
        if (!chartInstances.has(id)) {
            chartInstances.set(id, echarts.init(element));
        }
        return chartInstances.get(id);
    }

    function fillSelect(selectId, values, selectedValue) {
        const select = document.getElementById(selectId);
        if (!select) {
            return;
        }
        select.innerHTML = values
            .map((value) => `<option value="${value}" ${value === selectedValue ? "selected" : ""}>${value}</option>`)
            .join("");
    }

    function fillDatalist(listId, values) {
        const list = document.getElementById(listId);
        if (!list) {
            return;
        }
        list.innerHTML = values.map((value) => `<option value="${value}"></option>`).join("");
    }

    function renderMetricCards(containerId, cards) {
        const container = document.getElementById(containerId);
        if (!container) {
            return;
        }
        container.innerHTML = cards
            .map(
                (card) => `
                    <article class="metric-card">
                        <div class="label">${card.label}</div>
                        <div class="value">${card.value}</div>
                        <div class="extra">${card.extra || ""}</div>
                    </article>
                `
            )
            .join("");
    }

    function highlightNav() {
        const page = document.body.dataset.page;
        document.querySelectorAll("[data-nav]").forEach((node) => {
            if (node.dataset.nav === page) {
                node.classList.add("active");
            }
        });
    }

    async function getCitiesPayload() {
        if (!cityPayloadPromise) {
            cityPayloadPromise = fetchJSON("/api/cities").then((payload) => {
                allCities = payload.cities || [];
                if (!currentCity && payload.cities.length) {
                    const storedCity = (() => {
                        try {
                            return window.localStorage.getItem(currentCityStorageKey);
                        } catch (error) {
                            return "";
                        }
                    })();
                    currentCity = payload.cities.includes(storedCity) ? storedCity : payload.default_city;
                }
                return payload;
            });
        }
        return cityPayloadPromise;
    }

    function dispatchCityChange(city) {
        document.dispatchEvent(new CustomEvent("aq-city-change", { detail: { city } }));
    }

    function setCurrentCity(city, options = {}) {
        if (!city || city === currentCity) {
            const input = document.getElementById("headerCitySearch");
            if (input && city) {
                input.value = city;
            }
            return;
        }

        currentCity = city;
        try {
            window.localStorage.setItem(currentCityStorageKey, city);
        } catch (error) {
            console.warn("保存当前城市失败", error);
        }

        const input = document.getElementById("headerCitySearch");
        if (input) {
            input.value = city;
        }

        if (!options.silent) {
            dispatchCityChange(city);
        }
    }

    async function initGlobalCitySelect() {
        const input = document.getElementById("headerCitySearch");
        if (!input) {
            return;
        }

        const payload = await getCitiesPayload();
        const storedCity = (() => {
            try {
                return window.localStorage.getItem(currentCityStorageKey);
            } catch (error) {
                return "";
            }
        })();
        const selectedCity = payload.cities.includes(storedCity) ? storedCity : payload.default_city;

        fillDatalist("headerCityOptions", payload.cities);
        currentCity = selectedCity || "";
        input.value = currentCity;

        function applySearchValue() {
            const keyword = input.value.trim();
            if (!keyword) {
                fillDatalist("headerCityOptions", allCities);
                input.value = currentCity;
                return;
            }
            const matchedCities = allCities.filter((city) => city.includes(keyword));
            fillDatalist("headerCityOptions", matchedCities.length ? matchedCities : allCities);
            if (allCities.includes(keyword)) {
                setCurrentCity(keyword);
                return;
            }
            if (matchedCities.length === 1) {
                setCurrentCity(matchedCities[0]);
            }
        }

        input.addEventListener("input", () => {
            const keyword = input.value.trim();
            const matchedCities = keyword
                ? allCities.filter((city) => city.includes(keyword))
                : allCities;
            fillDatalist("headerCityOptions", matchedCities);
        });
        input.addEventListener("change", applySearchValue);
        input.addEventListener("search", applySearchValue);
        input.addEventListener("blur", applySearchValue);
    }

    function getCurrentCity() {
        return currentCity;
    }

    window.addEventListener("resize", () => {
        chartInstances.forEach((chart) => chart.resize());
    });

    return {
        fetchJSON,
        mountChart,
        fillSelect,
        renderMetricCards,
        highlightNav,
        getCitiesPayload,
        initGlobalCitySelect,
        getCurrentCity,
        setCurrentCity,
    };
})();

document.addEventListener("DOMContentLoaded", async () => {
    AppUtils.highlightNav();
    await AppUtils.initGlobalCitySelect();
});
