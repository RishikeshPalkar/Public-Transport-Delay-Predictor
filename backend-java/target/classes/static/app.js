// App Configuration
const API_BASE = ""; // Empty string triggers relative requests to the same host/port

// App State
let activeStationUic = "";
let refreshIntervalId = null;

// DOM Elements
const stationSelect = document.getElementById("station-select");
const refreshToggle = document.getElementById("refresh-toggle");
const manualRefreshBtn = document.getElementById("manual-refresh");
const healthIndicator = document.getElementById("health-indicator");
const healthText = document.getElementById("health-text");
const weatherContent = document.getElementById("weather-content");
const departuresBody = document.getElementById("departures-body");
const arrivalsBody = document.getElementById("arrivals-body");
const tabButtons = document.querySelectorAll(".tab-btn");
const tabContents = document.querySelectorAll(".tab-content");

// Weather Code mapping to Swiss icon
const WEATHER_CODES = {
    0: { desc: "Clear sky", icon: "☀️" },
    1: { desc: "Mainly clear", icon: "🌤️" },
    2: { desc: "Partly cloudy", icon: "⛅" },
    3: { desc: "Overcast", icon: "☁️" },
    45: { desc: "Foggy", icon: "🌫️" },
    48: { desc: "Depositing rime fog", icon: "🌫️" },
    51: { desc: "Light drizzle", icon: "🌦️" },
    53: { desc: "Moderate drizzle", icon: "🌦️" },
    55: { desc: "Dense drizzle", icon: "🌦️" },
    61: { desc: "Slight rain", icon: "🌧️" },
    63: { desc: "Moderate rain", icon: "🌧️" },
    65: { desc: "Heavy rain", icon: "🌧️" },
    71: { desc: "Slight snow fall", icon: "❄️" },
    73: { desc: "Moderate snow fall", icon: "❄️" },
    75: { desc: "Heavy snow fall", icon: "❄️" },
    77: { desc: "Snow grains", icon: "❄️" },
    80: { desc: "Slight rain showers", icon: "🌧️" },
    81: { desc: "Moderate rain showers", icon: "🌧️" },
    82: { desc: "Violent rain showers", icon: "⛈️" },
    85: { desc: "Slight snow showers", icon: "❄️" },
    86: { desc: "Heavy snow showers", icon: "❄️" },
    95: { desc: "Thunderstorm", icon: "⛈️" }
};

function getWeatherMeta(code) {
    return WEATHER_CODES[code] || { desc: "Unknown", icon: "🌡️" };
}

// 1. Initialize API Connection
async function checkApiHealth() {
    try {
        const response = await fetch(`${API_BASE}/api/health`);
        const data = await response.json();
        if (response.ok && data.status === "HEALTHY") {
            healthIndicator.className = "indicator healthy";
            healthText.textContent = "API: Connected & Loaded";
            return true;
        } else {
            healthIndicator.className = "indicator unhealthy";
            healthText.textContent = "API: Degrading/Error";
            return false;
        }
    } catch (error) {
        healthIndicator.className = "indicator unhealthy";
        healthText.textContent = "API: Offline";
        return false;
    }
}

// 2. Fetch Stations and Populate Dropdown
async function loadStations() {
    try {
        const response = await fetch(`${API_BASE}/api/stations`);
        if (!response.ok) throw new Error("Failed to load stations list");
        
        const stations = await response.json();
        
        stationSelect.innerHTML = '<option value="" disabled selected>Choose a Swiss Hub...</option>';
        stations.forEach(station => {
            const option = document.createElement("option");
            option.value = station.uicCode; // Match Java POJO field name camelCase: uicCode instead of uic_code
            option.textContent = `${station.name} (${station.canton})`;
            stationSelect.appendChild(option);
        });
    } catch (error) {
        console.error(error);
        stationSelect.innerHTML = '<option value="" disabled>Error loading stations</option>';
    }
}

// 3. Fetch Dashboard Data (Weather + Schedules + Predictions)
async function fetchDashboardData(stationUic) {
    if (!stationUic) return;
    
    // Show loading states
    weatherContent.innerHTML = '<div class="loading-spinner">Fetching weather...</div>';
    departuresBody.innerHTML = '<tr><td colspan="4" class="loading-spinner">Retrieving schedules & predicting...</td></tr>';
    arrivalsBody.innerHTML = '<tr><td colspan="4" class="loading-spinner">Retrieving schedules & predicting...</td></tr>';
    
    try {
        const response = await fetch(`${API_BASE}/api/dashboard/data?station_uic=${stationUic}`);
        if (!response.ok) throw new Error("Failed to load dashboard data");
        
        const data = await response.json();
        renderWeather(data.weather);
        renderSchedules(data.departures, data.arrivals);
    } catch (error) {
        console.error(error);
        weatherContent.innerHTML = '<div class="empty-message">Error updating weather</div>';
        departuresBody.innerHTML = '<tr><td colspan="4" class="empty-message">Error loading departures</td></tr>';
        arrivalsBody.innerHTML = '<tr><td colspan="4" class="empty-message">Error loading arrivals</td></tr>';
    }
}

// 4. Render Weather sidebar
function renderWeather(weather) {
    if (!weather) {
        weatherContent.innerHTML = '<div class="empty-message">No weather info available</div>';
        return;
    }
    
    const weatherMeta = getWeatherMeta(weather.weather_code);
    
    weatherContent.innerHTML = `
        <div class="weather-card">
            <span style="font-size: 3.5rem;">${weatherMeta.icon}</span>
            <div class="weather-temp">${weather.temperature_c.toFixed(1)}°C</div>
            <div class="weather-desc">${weatherMeta.desc}</div>
            
            <div class="weather-grid">
                <div class="weather-item">
                    <span class="weather-label">Rain</span>
                    <span class="weather-val">${weather.precipitation_mm.toFixed(1)} mm</span>
                </div>
                <div class="weather-item">
                    <span class="weather-label">Snow</span>
                    <span class="weather-val">${weather.snow_depth_cm.toFixed(0)} cm</span>
                </div>
            </div>
        </div>
    `;
}

// 5. Helper to Format Delay Badge
function getDelayBadge(delayMin) {
    const rounded = Math.round(delayMin * 10) / 10;
    if (rounded <= 0.2) {
        return `<span class="badge badge-ok">On Time</span>`;
    } else if (rounded < 3.0) {
        return `<span class="badge badge-warn">+${rounded} min</span>`;
    } else {
        return `<span class="badge badge-error">+${rounded} min</span>`;
    }
}

// Helper to Format Time
function formatTime(isoString) {
    if (!isoString) return "--:--";
    // Spring Boot returns standard LocalDateTime string like "2026-06-14T08:30" or ISO format
    const date = new Date(isoString);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// 6. Render Departures and Arrivals tables
function renderSchedules(departures, arrivals) {
    // Render Departures
    if (!departures || departures.length === 0) {
        departuresBody.innerHTML = '<tr><td colspan="4" class="empty-message">No scheduled departures found.</td></tr>';
    } else {
        departuresBody.innerHTML = departures.map(trip => `
            <tr>
                <td style="font-weight: 600;">${formatTime(trip.scheduled_time)}</td>
                <td><span style="font-weight: 500; color: var(--accent-blue);">${trip.linien_text}</span></td>
                <td>${trip.route}</td>
                <td>${getDelayBadge(trip.predicted_delay_min)}</td>
            </tr>
        `).join('');
    }

    // Render Arrivals
    if (!arrivals || arrivals.length === 0) {
        arrivalsBody.innerHTML = '<tr><td colspan="4" class="empty-message">No scheduled arrivals found.</td></tr>';
    } else {
        arrivalsBody.innerHTML = arrivals.map(trip => `
            <tr>
                <td style="font-weight: 600;">${formatTime(trip.scheduled_time)}</td>
                <td><span style="font-weight: 500; color: var(--accent-blue);">${trip.linien_text}</span></td>
                <td>${trip.route}</td>
                <td>${getDelayBadge(trip.predicted_delay_min)}</td>
            </tr>
        `).join('');
    }
}

// 7. Auto Refresh Management
function startAutoRefresh() {
    stopAutoRefresh();
    if (refreshToggle.checked) {
        console.log("[Auto-Refresh] Started (30s interval)");
        refreshIntervalId = setInterval(() => {
            console.log("[Auto-Refresh] Triggered reload");
            fetchDashboardData(activeStationUic);
        }, 30000);
    }
}

// Event Listeners
stationSelect.addEventListener("change", (e) => {
    activeStationUic = e.target.value;
    fetchDashboardData(activeStationUic);
    startAutoRefresh();
});

refreshToggle.addEventListener("change", () => {
    if (refreshToggle.checked) {
        startAutoRefresh();
    } else {
        stopAutoRefresh();
    }
});

manualRefreshBtn.addEventListener("click", () => {
    fetchDashboardData(activeStationUic);
    // Visual click effect
    manualRefreshBtn.style.transform = "scale(0.95)";
    setTimeout(() => manualRefreshBtn.style.transform = "scale(1)", 100);
});

// Tab Switch Logic
tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
        tabButtons.forEach(b => b.classList.remove("active"));
        tabContents.forEach(c => c.classList.remove("active"));
        
        btn.classList.add("active");
        const tabName = btn.dataset.tab;
        document.getElementById(`${tabName}-tab`).classList.add("active");
    });
});

// Startup Execution
async function init() {
    const isHealthy = await checkApiHealth();
    if (isHealthy) {
        await loadStations();
        
        // Auto-select first station if available after brief delay
        setTimeout(() => {
            if (stationSelect.options.length > 1) {
                stationSelect.selectedIndex = 1;
                activeStationUic = stationSelect.value;
                fetchDashboardData(activeStationUic);
                startAutoRefresh();
            }
        }, 500);
    }
}

function stopAutoRefresh() {
    if (refreshIntervalId) {
        clearInterval(refreshIntervalId);
        refreshIntervalId = null;
        console.log("[Auto-Refresh] Stopped");
    }
}

init();
