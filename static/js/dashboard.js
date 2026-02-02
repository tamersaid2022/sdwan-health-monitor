/**
 * SD-WAN Health Monitor - Dashboard JavaScript
 * Author: Tamer Khalifa (CCIE #68867)
 */

// WebSocket connection for real-time updates
const socket = io ? io() : null;

// API fetch helper
async function apiGet(endpoint) {
    const resp = await fetch(`/api${endpoint}`);
    return resp.json();
}

// Update dashboard stats
async function refreshStats() {
    try {
        const health = await apiGet('/health');
        document.getElementById('total-devices').textContent = health.total_devices || '--';
        document.getElementById('devices-up').textContent = health.reachable || '--';
        document.getElementById('devices-down').textContent = health.unreachable || '--';
        document.getElementById('total-tunnels').textContent = health.active_tunnels || '--';
        document.getElementById('active-alerts').textContent = health.active_alerts || '--';
    } catch (err) {
        console.error('Failed to refresh stats:', err);
    }
}

// Update alerts table
async function refreshAlerts() {
    try {
        const data = await apiGet('/alerts?limit=10');
        const tbody = document.getElementById('alerts-table');
        if (!tbody) return;

        if (!data.alerts || data.alerts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="px-4 py-4 text-center text-gray-500">No active alerts</td></tr>';
            return;
        }

        tbody.innerHTML = data.alerts.map(a => {
            const severityClass = {
                'critical': 'bg-red-600',
                'warning': 'bg-yellow-600',
                'info': 'bg-blue-600'
            }[a.severity] || 'bg-gray-600';

            return `<tr class="border-b border-gray-700 data-row fade-in">
                <td class="px-4 py-3 text-sm text-gray-400">${new Date(a.timestamp).toLocaleString()}</td>
                <td class="px-4 py-3 font-mono">${a.device || '-'}</td>
                <td class="px-4 py-3"><span class="px-2 py-1 rounded-full text-xs ${severityClass}">${a.severity}</span></td>
                <td class="px-4 py-3">${a.message}</td>
            </tr>`;
        }).join('');
    } catch (err) {
        console.error('Failed to refresh alerts:', err);
    }
}

// Initialize CPU chart
function initCPUChart(data) {
    const chartDiv = document.getElementById('cpu-chart');
    if (!chartDiv) return;

    const trace = {
        x: data.map(d => d.hostname),
        y: data.map(d => d.cpu),
        type: 'bar',
        marker: {
            color: data.map(d => d.cpu > 90 ? '#dc2626' : d.cpu > 70 ? '#f59e0b' : '#34d399')
        }
    };

    Plotly.newPlot(chartDiv, [trace], {
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#9ca3af' },
        margin: { t: 20, b: 60, l: 40, r: 20 },
        yaxis: { title: 'CPU %', gridcolor: '#374151', range: [0, 100] },
        xaxis: { gridcolor: '#374151' }
    }, { responsive: true, displayModeBar: false });
}

// WebSocket event handlers
if (socket) {
    socket.on('stats_update', (data) => {
        document.getElementById('total-devices').textContent = data.total_devices || '--';
        document.getElementById('devices-up').textContent = data.reachable || '--';
        document.getElementById('devices-down').textContent = data.unreachable || '--';
    });

    socket.on('new_alert', (alert) => {
        refreshAlerts();
    });
}

// Initial load and auto-refresh
document.addEventListener('DOMContentLoaded', () => {
    refreshStats();
    refreshAlerts();
    setInterval(refreshStats, 30000);
    setInterval(refreshAlerts, 60000);
});
