/**
 * ServerInventory — Main Application JavaScript
 * Complete client-side logic for all tabs, auth, and interactions.
 */

(function () {
    'use strict';

    // ═══════════════════════════════════════════════════════════════════════
    // STATE
    // ═══════════════════════════════════════════════════════════════════════

    const state = {
        token: localStorage.getItem('si_token') || null,
        user: JSON.parse(localStorage.getItem('si_user') || 'null'),
        currentTab: 'dashboard',
        currentPath: '/',
        refreshTimer: null,
        liveTimer: null,
        socket: null,
        terminal: null,
        terminalFit: null,
        terminalConnected: false,
        sidebarCollapsed: localStorage.getItem('si_sidebar') === 'collapsed'
    };

    // ═══════════════════════════════════════════════════════════════════════
    // API HELPERS
    // ═══════════════════════════════════════════════════════════════════════

    function apiHeaders() {
        const h = { 'Content-Type': 'application/json' };
        if (state.token) h['Authorization'] = `Bearer ${state.token}`;
        return h;
    }

    async function api(path, options = {}) {
        const url = `/api${path}`;
        const config = {
            headers: apiHeaders(),
            ...options
        };
        try {
            const res = await fetch(url, config);
            if (res.status === 401) {
                // Try refresh
                const refreshed = await refreshToken();
                if (refreshed) {
                    config.headers = apiHeaders();
                    const retry = await fetch(url, config);
                    return await retry.json();
                } else {
                    logout();
                    return null;
                }
            }
            if (!res.ok) {
                const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
                throw new Error(err.error || `HTTP ${res.status}`);
            }
            return await res.json();
        } catch (err) {
            if (err.message !== 'Failed to fetch') {
                console.error(`API Error (${path}):`, err);
            }
            throw err;
        }
    }

    async function refreshToken() {
        try {
            const res = await fetch('/api/auth/refresh', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include'
            });
            if (res.ok) {
                const data = await res.json();
                if (data.token) {
                    state.token = data.token;
                    state.user = data.user;
                    localStorage.setItem('si_token', data.token);
                    localStorage.setItem('si_user', JSON.stringify(data.user));
                    return true;
                }
            }
        } catch (e) { /* ignore */ }
        return false;
    }

    // ═══════════════════════════════════════════════════════════════════════
    // TOAST NOTIFICATIONS
    // ═══════════════════════════════════════════════════════════════════════

    function toast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
        const el = document.createElement('div');
        el.className = `toast ${type}`;
        el.innerHTML = `
            <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
            <span class="toast-message">${escapeHtml(message)}</span>
            <button class="toast-close">&times;</button>
        `;
        el.querySelector('.toast-close').onclick = () => el.remove();
        el.onclick = () => el.remove();
        container.appendChild(el);
        setTimeout(() => {
            if (el.parentNode) {
                el.style.animation = 'fadeIn 0.3s ease reverse';
                setTimeout(() => el.remove(), 300);
            }
        }, 5000);
    }

    // ═══════════════════════════════════════════════════════════════════════
    // UTILITY FUNCTIONS
    // ═══════════════════════════════════════════════════════════════════════

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function formatBytes(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
    }

    function timeAgo(dateStr) {
        const date = new Date(dateStr);
        const now = new Date();
        const diff = Math.floor((now - date) / 1000);
        if (diff < 60) return 'just now';
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        return date.toLocaleDateString();
    }

    function $(id) { return document.getElementById(id); }
    function $$(sel) { return document.querySelectorAll(sel); }

    // ═══════════════════════════════════════════════════════════════════════
    // AUTHENTICATION
    // ═══════════════════════════════════════════════════════════════════════

    async function checkAuth() {
        if (!state.token) {
            showLogin();
            return;
        }
        try {
            const data = await api('/auth/verify');
            if (data && data.authenticated) {
                state.user = data.user;
                localStorage.setItem('si_user', JSON.stringify(data.user));
                showApp();
            } else {
                showLogin();
            }
        } catch (e) {
            showLogin();
        }
    }

    function showLogin() {
        state.token = null;
        localStorage.removeItem('si_token');
        localStorage.removeItem('si_user');
        $('login-screen').style.display = 'flex';
        $('app').style.display = 'none';
        stopTimers();
    }

    function showApp() {
        $('login-screen').style.display = 'none';
        $('app').style.display = 'flex';
        updateUserInfo();
        initSidebar();
        loadTab('dashboard');
        startLiveUpdates();
    }

    function updateUserInfo() {
        if (state.user) {
            $('user-name').textContent = state.user.username;
            $('user-role').textContent = state.user.is_root ? 'root' : 'user';
            $('user-avatar').textContent = state.user.username.charAt(0).toUpperCase();
        }
    }

    async function login(username, password) {
        const btnText = $('btn-login').querySelector('.btn-text');
        const btnLoader = $('btn-login').querySelector('.btn-loader');
        const errorEl = $('login-error');

        btnText.style.display = 'none';
        btnLoader.style.display = 'block';
        errorEl.style.display = 'none';

        try {
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
                credentials: 'include'
            });
            const data = await res.json();

            if (res.ok && data.success) {
                state.token = data.token;
                state.user = data.user;
                localStorage.setItem('si_token', data.token);
                localStorage.setItem('si_user', JSON.stringify(data.user));
                toast('Logged in successfully', 'success');
                showApp();
            } else {
                errorEl.textContent = data.error || 'Login failed';
                errorEl.style.display = 'block';
            }
        } catch (err) {
            errorEl.textContent = 'Cannot connect to server. Is the service running?';
            errorEl.style.display = 'block';
        } finally {
            btnText.style.display = 'inline';
            btnLoader.style.display = 'none';
        }
    }

    async function logout() {
        try {
            await fetch('/api/auth/logout', {
                method: 'POST',
                headers: apiHeaders(),
                credentials: 'include'
            });
        } catch (e) { /* ignore */ }

        disconnectTerminal();
        stopTimers();
        state.token = null;
        state.user = null;
        localStorage.removeItem('si_token');
        localStorage.removeItem('si_user');
        showLogin();
        toast('Logged out', 'info');
    }

    // ═══════════════════════════════════════════════════════════════════════
    // SIDEBAR & NAVIGATION
    // ═══════════════════════════════════════════════════════════════════════

    function initSidebar() {
        const sidebar = $('sidebar');
        if (state.sidebarCollapsed) sidebar.classList.add('collapsed');
    }

    function toggleSidebar() {
        const sidebar = $('sidebar');
        sidebar.classList.toggle('collapsed');
        state.sidebarCollapsed = sidebar.classList.contains('collapsed');
        localStorage.setItem('si_sidebar', state.sidebarCollapsed ? 'collapsed' : 'expanded');

        // Resize terminal if visible
        if (state.currentTab === 'terminal' && state.terminalFit) {
            setTimeout(() => state.terminalFit.fit(), 300);
        }
    }

    function loadTab(tabName) {
        state.currentTab = tabName;

        // Update nav
        $$('.nav-item').forEach(el => {
            el.classList.toggle('active', el.dataset.tab === tabName);
        });

        // Update content
        $$('.tab-content').forEach(el => {
            el.classList.toggle('active', el.id === `tab-${tabName}`);
        });

        // Update title
        const titles = {
            dashboard: 'Dashboard', hardware: 'Hardware Info',
            software: 'Software', network: 'Network',
            storage: 'Storage', services: 'Services',
            files: 'File Explorer', terminal: 'Terminal',
            settings: 'Settings'
        };
        $('page-title').textContent = titles[tabName] || tabName;

        // Close mobile sidebar
        $('sidebar').classList.remove('mobile-open');

        // Load tab data
        switch (tabName) {
            case 'dashboard': loadDashboard(); break;
            case 'hardware': loadHardware(); break;
            case 'software': loadSoftwarePackages(); break;
            case 'network': loadNetworkInterfaces(); break;
            case 'storage': loadStorage(); break;
            case 'services': loadServices(); break;
            case 'files': loadFiles(); break;
            case 'terminal': initTerminal(); break;
            case 'settings': loadSettings(); break;
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // DASHBOARD
    // ═══════════════════════════════════════════════════════════════════════

    async function loadDashboard() {
        try {
            const data = await api('/system/dashboard');
            if (!data) return;

            // CPU
            $('dash-cpu-value').textContent = `${data.cpu.percent}%`;
            $('dash-cpu-bar').style.width = `${data.cpu.percent}%`;
            $('dash-cpu-detail').textContent = `${data.cpu.cores} cores · Load: ${data.cpu.load_avg.join(', ')}`;

            // Memory
            $('dash-mem-value').textContent = `${data.memory.percent}%`;
            $('dash-mem-bar').style.width = `${data.memory.percent}%`;
            $('dash-mem-detail').textContent = `${data.memory.used_human} / ${data.memory.total_human}`;

            // Disk
            $('dash-disk-value').textContent = `${data.disk.percent}%`;
            $('dash-disk-bar').style.width = `${data.disk.percent}%`;
            $('dash-disk-detail').textContent = `${data.disk.used_human} / ${data.disk.total_human}`;

            // Network
            $('dash-net-value').textContent = `↑${data.network.sent_human}`;
            $('dash-net-detail').textContent = `↓ ${data.network.recv_human} received`;

            // Hostname
            $('topbar-host').textContent = data.hostname;

            // System Info
            $('dash-sysinfo').innerHTML = `
                <div class="info-grid">
                    <div class="info-row"><span class="info-label">Hostname</span><span class="info-value">${escapeHtml(data.hostname)}</span></div>
                    <div class="info-row"><span class="info-label">OS</span><span class="info-value">${escapeHtml(data.os)}</span></div>
                    <div class="info-row"><span class="info-label">Kernel</span><span class="info-value">${escapeHtml(data.kernel)}</span></div>
                    <div class="info-row"><span class="info-label">Uptime</span><span class="info-value">${data.uptime.formatted}</span></div>
                    <div class="info-row"><span class="info-label">Processes</span><span class="info-value">${data.processes}</span></div>
                    <div class="info-row"><span class="info-label">Users Online</span><span class="info-value">${data.users_logged_in}</span></div>
                </div>
            `;

            // Services Summary
            $('dash-services-summary').innerHTML = `
                <div class="info-grid">
                    <div class="info-row"><span class="info-label">Active</span><span class="info-value"><span class="badge active">${data.services.active}</span></span></div>
                    <div class="info-row"><span class="info-label">Failed</span><span class="info-value"><span class="badge ${data.services.failed > 0 ? 'failed' : 'active'}">${data.services.failed}</span></span></div>
                </div>
            `;

            // Top processes
            loadDashboardProcesses();

        } catch (err) {
            toast('Failed to load dashboard: ' + err.message, 'error');
        }
    }

    async function loadDashboardProcesses() {
        try {
            const data = await api('/software/processes?sort=cpu&limit=10');
            if (!data) return;

            $('dash-proc-count').textContent = data.processes.length;
            $('dash-processes-body').innerHTML = data.processes.map(p => `
                <tr>
                    <td class="mono">${p.pid}</td>
                    <td>${escapeHtml(p.name)}</td>
                    <td>${escapeHtml(p.user)}</td>
                    <td><span class="${p.cpu_percent > 50 ? 'badge warning' : ''}">${p.cpu_percent}%</span></td>
                    <td>${p.memory_percent}%</td>
                    <td><span class="badge ${p.status === 'running' ? 'running' : p.status === 'sleeping' ? 'active' : 'inactive'}">${p.status}</span></td>
                </tr>
            `).join('');
        } catch (e) { /* ignore */ }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // HARDWARE
    // ═══════════════════════════════════════════════════════════════════════

    async function loadHardware() {
        try {
            const data = await api('/hardware/all');
            if (!data) return;

            let html = '';

            // CPU
            html += createAccordion('cpu', '🔲 CPU', `${data.cpu.model || 'Unknown'}`, `
                <div class="info-grid">
                    <div class="info-row"><span class="info-label">Model</span><span class="info-value">${escapeHtml(data.cpu.model)}</span></div>
                    <div class="info-row"><span class="info-label">Vendor</span><span class="info-value">${escapeHtml(data.cpu.vendor)}</span></div>
                    <div class="info-row"><span class="info-label">Architecture</span><span class="info-value">${data.cpu.architecture}</span></div>
                    <div class="info-row"><span class="info-label">Physical Cores</span><span class="info-value">${data.cpu.cores_physical}</span></div>
                    <div class="info-row"><span class="info-label">Logical Cores</span><span class="info-value">${data.cpu.cores_logical}</span></div>
                    <div class="info-row"><span class="info-label">Frequency</span><span class="info-value">${data.cpu.frequency_mhz} MHz</span></div>
                    <div class="info-row"><span class="info-label">Max Frequency</span><span class="info-value">${data.cpu.frequency_max_mhz} MHz</span></div>
                    <div class="info-row"><span class="info-label">Cache</span><span class="info-value">${data.cpu.cache_size || 'N/A'}</span></div>
                    <div class="info-row"><span class="info-label">Usage</span><span class="info-value">${data.cpu.usage_percent}%</span></div>
                    ${data.cpu.temperature ? `<div class="info-row"><span class="info-label">Temperature</span><span class="info-value">${data.cpu.temperature.current}°C</span></div>` : ''}
                    <div class="info-row"><span class="info-label">Load Average</span><span class="info-value">${data.cpu.load_average.map(l => l.toFixed(2)).join(' / ')}</span></div>
                </div>
                <div class="accordion-description">The CPU (Central Processing Unit) is the brain of the computer. It executes instructions and performs calculations for all running programs and the operating system.</div>
            `);

            // Memory
            html += createAccordion('memory', '💾 Memory', `${formatBytes(data.memory.ram.total)} RAM`, `
                <div class="info-grid">
                    <div class="info-row"><span class="info-label">Total RAM</span><span class="info-value">${formatBytes(data.memory.ram.total)}</span></div>
                    <div class="info-row"><span class="info-label">Used</span><span class="info-value">${formatBytes(data.memory.ram.used)} (${data.memory.ram.percent}%)</span></div>
                    <div class="info-row"><span class="info-label">Available</span><span class="info-value">${formatBytes(data.memory.ram.available)}</span></div>
                    <div class="info-row"><span class="info-label">Free</span><span class="info-value">${formatBytes(data.memory.ram.free)}</span></div>
                    <div class="info-row"><span class="info-label">Buffers</span><span class="info-value">${formatBytes(data.memory.ram.buffers)}</span></div>
                    <div class="info-row"><span class="info-label">Cached</span><span class="info-value">${formatBytes(data.memory.ram.cached)}</span></div>
                    <div class="info-row"><span class="info-label">Swap Total</span><span class="info-value">${formatBytes(data.memory.swap.total)}</span></div>
                    <div class="info-row"><span class="info-label">Swap Used</span><span class="info-value">${formatBytes(data.memory.swap.used)} (${data.memory.swap.percent}%)</span></div>
                </div>
                <div class="accordion-description">RAM (Random Access Memory) is the computer's short-term memory used by running processes. Swap is disk space used as overflow when RAM is full.</div>
            `);

            // Motherboard
            if (data.motherboard) {
                html += createAccordion('motherboard', '🖥️ Motherboard / System', data.motherboard.product || 'Unknown', `
                    <div class="info-grid">
                        <div class="info-row"><span class="info-label">Manufacturer</span><span class="info-value">${escapeHtml(data.motherboard.manufacturer || 'N/A')}</span></div>
                        <div class="info-row"><span class="info-label">Product</span><span class="info-value">${escapeHtml(data.motherboard.product || 'N/A')}</span></div>
                        <div class="info-row"><span class="info-label">System Vendor</span><span class="info-value">${escapeHtml(data.motherboard.system_vendor || 'N/A')}</span></div>
                        <div class="info-row"><span class="info-label">System Product</span><span class="info-value">${escapeHtml(data.motherboard.system_product || 'N/A')}</span></div>
                        <div class="info-row"><span class="info-label">BIOS Vendor</span><span class="info-value">${escapeHtml(data.motherboard.bios_vendor || 'N/A')}</span></div>
                        <div class="info-row"><span class="info-label">BIOS Version</span><span class="info-value">${escapeHtml(data.motherboard.bios_version || 'N/A')}</span></div>
                        <div class="info-row"><span class="info-label">BIOS Date</span><span class="info-value">${escapeHtml(data.motherboard.bios_date || 'N/A')}</span></div>
                    </div>
                    <div class="accordion-description">The motherboard is the main circuit board that connects all hardware components. BIOS (Basic Input/Output System) is the firmware that initializes hardware during boot.</div>
                `);
            }

            // GPU
            if (data.gpu && data.gpu.length > 0) {
                const gpuContent = data.gpu.map((g, i) => `
                    <div class="info-grid" style="margin-bottom:12px">
                        <div class="info-row"><span class="info-label">GPU ${i + 1}</span><span class="info-value">${escapeHtml(g.name)}</span></div>
                        ${g.driver ? `<div class="info-row"><span class="info-label">Driver</span><span class="info-value">${g.driver}</span></div>` : ''}
                        ${g.memory_total_mb ? `<div class="info-row"><span class="info-label">Memory</span><span class="info-value">${g.memory_used_mb}/${g.memory_total_mb} MB</span></div>` : ''}
                        ${g.temperature != null ? `<div class="info-row"><span class="info-label">Temperature</span><span class="info-value">${g.temperature}°C</span></div>` : ''}
                        ${g.utilization != null ? `<div class="info-row"><span class="info-label">Utilization</span><span class="info-value">${g.utilization}%</span></div>` : ''}
                    </div>
                `).join('');
                html += createAccordion('gpu', '🎮 GPU', `${data.gpu.length} device(s)`, gpuContent +
                    `<div class="accordion-description">The GPU (Graphics Processing Unit) handles graphics rendering and is also used for parallel computing tasks like machine learning and video encoding.</div>`);
            }

            // System / Kernel
            if (data.system) {
                html += createAccordion('kernel', '🐧 Operating System', data.system.os_pretty || data.system.os_name || 'Linux', `
                    <div class="info-grid">
                        <div class="info-row"><span class="info-label">OS</span><span class="info-value">${escapeHtml(data.system.os_pretty || 'N/A')}</span></div>
                        <div class="info-row"><span class="info-label">Kernel</span><span class="info-value">${escapeHtml(data.system.kernel)}</span></div>
                        <div class="info-row"><span class="info-label">Hostname</span><span class="info-value">${escapeHtml(data.system.hostname)}</span></div>
                        <div class="info-row"><span class="info-label">FQDN</span><span class="info-value">${escapeHtml(data.system.fqdn || 'N/A')}</span></div>
                    </div>
                    <div class="accordion-description">The Linux kernel is the core of the operating system that manages hardware resources and provides essential services to software applications.</div>
                `);
            }

            // Uptime
            if (data.uptime) {
                html += createAccordion('uptime', '⏱️ Uptime', data.uptime.formatted, `
                    <div class="info-grid">
                        <div class="info-row"><span class="info-label">Uptime</span><span class="info-value">${data.uptime.formatted}</span></div>
                        <div class="info-row"><span class="info-label">Boot Time</span><span class="info-value">${new Date(data.uptime.boot_time * 1000).toLocaleString()}</span></div>
                    </div>
                `);
            }

            // USB
            if (data.usb && data.usb.length > 0) {
                const usbContent = data.usb.map(d => `<div class="info-row"><span class="info-value">${escapeHtml(d)}</span></div>`).join('');
                html += createAccordion('usb', '🔌 USB Devices', `${data.usb.length} device(s)`, usbContent +
                    `<div class="accordion-description">USB (Universal Serial Bus) devices connected to this system, including keyboards, mice, storage devices, and other peripherals.</div>`);
            }

            $('hardware-list').innerHTML = html;
            attachAccordionListeners($('hardware-list'));

        } catch (err) {
            $('hardware-list').innerHTML = `<div class="info-row"><span class="info-value">Failed to load hardware info: ${escapeHtml(err.message)}</span></div>`;
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // SOFTWARE
    // ═══════════════════════════════════════════════════════════════════════

    async function loadSoftwarePackages(search = '', offset = 0) {
        try {
            let url = `/software/packages?limit=50&offset=${offset}`;
            if (search) url += `&search=${encodeURIComponent(search)}`;
            const data = await api(url);
            if (!data) return;

            $('packages-body').innerHTML = data.packages.map(p => `
                <tr>
                    <td><strong>${escapeHtml(p.name)}</strong></td>
                    <td class="mono">${escapeHtml(p.version)}</td>
                    <td>${escapeHtml(p.size)}</td>
                    <td>${escapeHtml(p.description || '-')}</td>
                </tr>
            `).join('') || '<tr><td colspan="4" style="text-align:center;color:var(--text-muted)">No packages found</td></tr>';

            // Pagination
            const totalPages = Math.ceil(data.total / 50);
            const currentPage = Math.floor(offset / 50) + 1;
            let pagHtml = '';
            if (totalPages > 1) {
                pagHtml += `<button ${currentPage === 1 ? 'disabled' : ''} onclick="window.__si.loadPkgs('${search}', ${(currentPage - 2) * 50})">&lt;</button>`;
                for (let i = Math.max(1, currentPage - 2); i <= Math.min(totalPages, currentPage + 2); i++) {
                    pagHtml += `<button class="${i === currentPage ? 'active' : ''}" onclick="window.__si.loadPkgs('${search}', ${(i - 1) * 50})">${i}</button>`;
                }
                pagHtml += `<button ${currentPage === totalPages ? 'disabled' : ''} onclick="window.__si.loadPkgs('${search}', ${currentPage * 50})">&gt;</button>`;
                pagHtml += `<span style="color:var(--text-muted);font-size:0.8rem;margin-left:8px">${data.total} packages</span>`;
            }
            $('packages-pagination').innerHTML = pagHtml;

        } catch (err) {
            $('packages-body').innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--accent-red)">${escapeHtml(err.message)}</td></tr>`;
        }
    }

    async function loadProcesses(sort = 'cpu') {
        try {
            const data = await api(`/software/processes?sort=${sort}&limit=100`);
            if (!data) return;

            $('processes-body').innerHTML = data.processes.map(p => `
                <tr>
                    <td class="mono">${p.pid}</td>
                    <td><strong>${escapeHtml(p.name)}</strong>${p.description ? `<br><small style="color:var(--text-muted)">${escapeHtml(p.description)}</small>` : ''}</td>
                    <td>${escapeHtml(p.user)}</td>
                    <td>${p.cpu_percent}%</td>
                    <td>${p.memory_percent}%</td>
                    <td><span class="badge ${p.status === 'running' ? 'running' : 'inactive'}">${p.status}</span></td>
                    <td>
                        <div class="file-actions-cell">
                            <button class="btn-sm danger" onclick="window.__si.killProcess(${p.pid}, '${escapeHtml(p.name)}', false)" title="Terminate">Stop</button>
                            <button class="btn-sm danger" onclick="window.__si.killProcess(${p.pid}, '${escapeHtml(p.name)}', true)" title="Force Kill">Kill</button>
                        </div>
                    </td>
                </tr>
            `).join('');
        } catch (err) {
            toast('Failed to load processes: ' + err.message, 'error');
        }
    }

    async function killProcess(pid, name, force) {
        if (!confirm(`${force ? 'Force kill' : 'Terminate'} process "${name}" (PID: ${pid})?`)) return;
        try {
            const data = await api(`/software/processes/${pid}/kill`, {
                method: 'POST',
                body: JSON.stringify({ force })
            });
            toast(data.message, 'success');
            loadProcesses($('proc-sort').value);
        } catch (err) {
            toast('Failed: ' + err.message, 'error');
        }
    }

    async function loadStartup() {
        try {
            const data = await api('/software/startup');
            if (!data) return;

            $('startup-list').innerHTML = data.programs.map(p => createAccordion(
                `startup-${p.name}`, `${p.state === 'enabled' ? '🟢' : '⚪'} ${p.name}`,
                `<span class="badge ${p.state === 'enabled' ? 'active' : 'inactive'}">${p.state}</span>`,
                `<div class="info-grid">
                    <div class="info-row"><span class="info-label">Type</span><span class="info-value">${p.type}</span></div>
                    <div class="info-row"><span class="info-label">State</span><span class="info-value">${p.state}</span></div>
                </div>
                ${p.description ? `<div class="accordion-description">${escapeHtml(p.description)}</div>` : ''}`
            )).join('') || '<p style="color:var(--text-muted);text-align:center;padding:20px">No startup programs found</p>';

            attachAccordionListeners($('startup-list'));
        } catch (err) { toast('Failed to load startup programs', 'error'); }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // NETWORK
    // ═══════════════════════════════════════════════════════════════════════

    async function loadNetworkInterfaces() {
        try {
            const data = await api('/network/interfaces');
            if (!data) return;

            $('interfaces-list').innerHTML = data.interfaces.map(iface => {
                const ipv4 = iface.addresses.find(a => a.type === 'IPv4');
                const mac = iface.addresses.find(a => a.type === 'MAC');

                return createAccordion(`iface-${iface.name}`,
                    `${iface.is_up ? '🟢' : '🔴'} ${iface.name}`,
                    `${ipv4 ? ipv4.address : 'No IP'} · ${iface.speed_mbps > 0 ? iface.speed_mbps + ' Mbps' : ''}`,
                    `<div class="info-grid">
                        <div class="info-row"><span class="info-label">Status</span><span class="info-value"><span class="badge ${iface.is_up ? 'online' : 'offline'}">${iface.is_up ? 'UP' : 'DOWN'}</span></span></div>
                        <div class="info-row"><span class="info-label">Speed</span><span class="info-value">${iface.speed_mbps} Mbps</span></div>
                        <div class="info-row"><span class="info-label">MTU</span><span class="info-value">${iface.mtu}</span></div>
                        ${ipv4 ? `<div class="info-row"><span class="info-label">IPv4</span><span class="info-value">${ipv4.address}/${ipv4.netmask}</span></div>` : ''}
                        ${mac ? `<div class="info-row"><span class="info-label">MAC</span><span class="info-value">${mac.address}</span></div>` : ''}
                        ${iface.io ? `
                            <div class="info-row"><span class="info-label">TX</span><span class="info-value">${formatBytes(iface.io.bytes_sent)} (${iface.io.packets_sent} pkts)</span></div>
                            <div class="info-row"><span class="info-label">RX</span><span class="info-value">${formatBytes(iface.io.bytes_recv)} (${iface.io.packets_recv} pkts)</span></div>
                            <div class="info-row"><span class="info-label">Errors</span><span class="info-value">In: ${iface.io.errors_in} / Out: ${iface.io.errors_out}</span></div>
                        ` : ''}
                    </div>
                    <div class="accordion-description">A network interface connects your server to the network. Each interface can have one or more IP addresses assigned to it.</div>`
                );
            }).join('');

            attachAccordionListeners($('interfaces-list'));
        } catch (err) {
            $('interfaces-list').innerHTML = `<p style="color:var(--accent-red)">${escapeHtml(err.message)}</p>`;
        }
    }

    async function loadPorts() {
        try {
            const data = await api('/network/ports');
            if (!data) return;
            $('ports-body').innerHTML = data.ports.map(p => `
                <tr>
                    <td class="mono"><strong>${p.port}</strong></td>
                    <td class="mono">${escapeHtml(p.address)}</td>
                    <td>${escapeHtml(p.process || '-')}</td>
                    <td class="mono">${p.pid || '-'}</td>
                    <td>${escapeHtml(p.description || '-')}</td>
                </tr>
            `).join('') || '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">No listening ports</td></tr>';
        } catch (err) { toast('Failed to load ports', 'error'); }
    }

    async function loadConnections() {
        try {
            const data = await api('/network/connections');
            if (!data) return;
            $('connections-body').innerHTML = data.connections.slice(0, 100).map(c => `
                <tr>
                    <td class="mono">${escapeHtml(c.local_addr)}</td>
                    <td class="mono">${escapeHtml(c.remote_addr || '-')}</td>
                    <td><span class="badge ${c.status === 'ESTABLISHED' ? 'active' : c.status === 'LISTEN' ? 'running' : 'inactive'}">${c.status}</span></td>
                    <td>${escapeHtml(c.process || '-')}</td>
                    <td class="mono">${c.pid || '-'}</td>
                </tr>
            `).join('');
        } catch (err) { toast('Failed to load connections', 'error'); }
    }

    async function loadDns() {
        try {
            const data = await api('/network/dns');
            if (!data) return;
            $('dns-info').innerHTML = `
                <div class="info-row"><span class="info-label">Hostname</span><span class="info-value">${escapeHtml(data.hostname)}</span></div>
                <div class="info-row"><span class="info-label">FQDN</span><span class="info-value">${escapeHtml(data.fqdn)}</span></div>
                <div class="info-row"><span class="info-label">Nameservers</span><span class="info-value">${data.nameservers.map(n => escapeHtml(n)).join(', ') || 'None'}</span></div>
                <div class="info-row"><span class="info-label">Search Domains</span><span class="info-value">${data.search_domains.map(d => escapeHtml(d)).join(', ') || 'None'}</span></div>
            `;
        } catch (err) { toast('Failed to load DNS info', 'error'); }
    }

    async function loadFirewall() {
        try {
            const data = await api('/network/firewall');
            if (!data) return;
            $('firewall-rules').textContent = data.rules.length > 0
                ? `[${data.tool || 'firewall'}]\n\n${data.rules.join('\n')}`
                : 'No firewall rules found or no firewall is active.';
        } catch (err) { toast('Failed to load firewall rules', 'error'); }
    }

    async function loadNetworkServices() {
        try {
            const data = await api('/network/services');
            if (!data) return;
            $('net-services-list').innerHTML = data.services.map(s => createAccordion(
                `netsvc-${s.name}`,
                `${s.status === 'active' ? '🟢' : '🔴'} ${s.name}`,
                `<span class="badge ${s.status === 'active' ? 'active' : 'inactive'}">${s.status}</span>`,
                `<div class="info-grid">
                    <div class="info-row"><span class="info-label">Status</span><span class="info-value">${s.status}</span></div>
                    <div class="info-row"><span class="info-label">Enabled</span><span class="info-value">${s.enabled ? 'Yes' : 'No'}</span></div>
                </div>
                ${s.description ? `<div class="accordion-description">${escapeHtml(s.description)}</div>` : ''}
                <div class="service-controls">
                    <button class="btn-sm success" onclick="window.__si.controlService('${s.name}', 'start')">▶ Start</button>
                    <button class="btn-sm danger" onclick="window.__si.controlService('${s.name}', 'stop')">⏹ Stop</button>
                    <button class="btn-sm" onclick="window.__si.controlService('${s.name}', 'restart')">🔄 Restart</button>
                </div>`
            )).join('') || '<p style="color:var(--text-muted);text-align:center;padding:20px">No network services detected</p>';
            attachAccordionListeners($('net-services-list'));
        } catch (err) { toast('Failed to load network services', 'error'); }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // STORAGE
    // ═══════════════════════════════════════════════════════════════════════

    async function loadStorage() {
        try {
            const data = await api('/storage/overview');
            if (!data) return;

            // Draw pie chart
            drawStorageChart(data.disks);

            // Disk list
            $('storage-list').innerHTML = data.disks.map(d => createAccordion(
                `disk-${d.device.replace(/\//g, '-')}`,
                `💾 ${d.device}`,
                `${d.mountpoint} · ${d.percent}% used`,
                `<div class="info-grid">
                    <div class="info-row"><span class="info-label">Mount</span><span class="info-value">${escapeHtml(d.mountpoint)}</span></div>
                    <div class="info-row"><span class="info-label">Filesystem</span><span class="info-value">${d.fstype}</span></div>
                    <div class="info-row"><span class="info-label">Total</span><span class="info-value">${d.total_human}</span></div>
                    <div class="info-row"><span class="info-label">Used</span><span class="info-value">${d.used_human} (${d.percent}%)</span></div>
                    <div class="info-row"><span class="info-label">Free</span><span class="info-value">${d.free_human}</span></div>
                    <div class="info-row"><span class="info-label">Options</span><span class="info-value">${escapeHtml(d.opts || '-')}</span></div>
                </div>
                <div style="margin-top:12px">
                    <div class="stat-bar" style="height:8px"><div class="stat-bar-fill disk" style="width:${d.percent}%;${d.percent > 90 ? 'background:var(--gradient-red)' : ''}"></div></div>
                </div>
                <div class="accordion-description">This partition stores files on your server. When usage exceeds 90%, consider cleaning up or expanding storage to prevent service disruptions.</div>`
            )).join('');

            attachAccordionListeners($('storage-list'));
        } catch (err) {
            toast('Failed to load storage info: ' + err.message, 'error');
        }
    }

    function drawStorageChart(disks) {
        const canvas = $('storage-chart');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const size = 220;
        canvas.width = size * 2;
        canvas.height = size * 2;
        canvas.style.width = size + 'px';
        canvas.style.height = size + 'px';
        ctx.scale(2, 2);

        const colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#ec4899'];
        const center = size / 2;
        const radius = size / 2 - 10;
        const innerRadius = radius * 0.65;

        let totalUsed = 0, totalSize = 0;
        disks.forEach(d => { totalUsed += d.used; totalSize += d.total; });

        // Draw segments
        let startAngle = -Math.PI / 2;
        const legendEl = $('storage-legend');
        let legendHtml = '';

        disks.forEach((d, i) => {
            const portion = totalSize > 0 ? d.total / totalSize : 0;
            const endAngle = startAngle + (portion * 2 * Math.PI);

            ctx.beginPath();
            ctx.arc(center, center, radius, startAngle, endAngle);
            ctx.arc(center, center, innerRadius, endAngle, startAngle, true);
            ctx.closePath();
            ctx.fillStyle = colors[i % colors.length];
            ctx.fill();

            // Used portion (darker)
            const usedPortion = d.total > 0 ? d.used / d.total : 0;
            const usedAngle = startAngle + (portion * 2 * Math.PI * usedPortion);

            ctx.beginPath();
            ctx.arc(center, center, radius, startAngle, usedAngle);
            ctx.arc(center, center, innerRadius, usedAngle, startAngle, true);
            ctx.closePath();
            ctx.fillStyle = colors[i % colors.length] + 'aa';
            ctx.fill();

            legendHtml += `
                <div class="legend-item">
                    <span class="legend-color" style="background:${colors[i % colors.length]}"></span>
                    <span class="legend-label">${escapeHtml(d.mountpoint)}</span>
                    <span class="legend-value">${d.percent}%</span>
                    <span class="legend-size">${d.used_human} / ${d.total_human}</span>
                </div>
            `;

            startAngle = endAngle;
        });

        legendEl.innerHTML = legendHtml;

        // Center text
        const overallPercent = totalSize > 0 ? Math.round(totalUsed / totalSize * 100) : 0;
        $('storage-chart-center').innerHTML = `
            <span class="chart-value">${overallPercent}%</span>
            <span class="chart-label">Used</span>
        `;
    }

    // ═══════════════════════════════════════════════════════════════════════
    // SERVICES
    // ═══════════════════════════════════════════════════════════════════════

    let allServices = [];

    async function loadServices(filter = 'all', search = '') {
        try {
            const data = await api('/services/list');
            if (!data) return;

            allServices = data.services;
            renderServices(filter, search);
        } catch (err) {
            toast('Failed to load services: ' + err.message, 'error');
        }
    }

    function renderServices(filter = 'all', search = '') {
        let filtered = allServices;

        if (filter !== 'all') {
            filtered = filtered.filter(s => s.active === filter);
        }
        if (search) {
            const q = search.toLowerCase();
            filtered = filtered.filter(s => s.name.toLowerCase().includes(q) || (s.description_short || '').toLowerCase().includes(q));
        }

        $('services-list').innerHTML = filtered.map(s => createAccordion(
            `svc-${s.name}`,
            `${s.active === 'active' ? '🟢' : s.active === 'failed' ? '🔴' : '⚪'} ${s.name}`,
            `<span class="badge ${s.active}">${s.active}</span>`,
            `<div class="info-grid">
                <div class="info-row"><span class="info-label">Status</span><span class="info-value"><span class="badge ${s.active}">${s.active} (${s.sub})</span></span></div>
                <div class="info-row"><span class="info-label">Load State</span><span class="info-value">${s.load}</span></div>
                ${s.description_short ? `<div class="info-row"><span class="info-label">Description</span><span class="info-value">${escapeHtml(s.description_short)}</span></div>` : ''}
            </div>
            ${s.description ? `<div class="accordion-description">${escapeHtml(s.description)}</div>` : ''}
            <div class="service-controls">
                <button class="btn-sm success" onclick="window.__si.controlService('${s.name}', 'start')">▶ Start</button>
                <button class="btn-sm danger" onclick="window.__si.controlService('${s.name}', 'stop')">⏹ Stop</button>
                <button class="btn-sm" onclick="window.__si.controlService('${s.name}', 'restart')">🔄 Restart</button>
                <button class="btn-sm" onclick="window.__si.controlService('${s.name}', 'reload')">♻️ Reload</button>
                <button class="btn-sm success" onclick="window.__si.controlService('${s.name}', 'enable')">Enable</button>
                <button class="btn-sm danger" onclick="window.__si.controlService('${s.name}', 'disable')">Disable</button>
                <button class="btn-sm" onclick="window.__si.viewServiceLogs('${s.name}')">📋 Logs</button>
            </div>`
        )).join('') || '<p style="color:var(--text-muted);text-align:center;padding:20px">No services match your filter</p>';

        attachAccordionListeners($('services-list'));
    }

    async function controlService(name, action) {
        if (['stop', 'disable'].includes(action)) {
            if (!confirm(`Are you sure you want to ${action} "${name}"?`)) return;
        }
        try {
            const data = await api(`/services/${name}/control`, {
                method: 'POST',
                body: JSON.stringify({ action })
            });
            if (data.success) {
                toast(`${name}: ${action} successful`, 'success');
                setTimeout(() => loadServices(), 1000);
            } else {
                toast(`${name}: ${data.error}`, 'error');
            }
        } catch (err) {
            toast(`Failed to ${action} ${name}: ${err.message}`, 'error');
        }
    }

    async function viewServiceLogs(name) {
        try {
            const data = await api(`/services/${name}/logs?lines=50`);
            showModal(`Logs: ${name}`, `<pre class="code-block">${data.logs.map(l => escapeHtml(l)).join('\n') || 'No logs available'}</pre>`);
        } catch (err) {
            toast('Failed to load logs: ' + err.message, 'error');
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FILE EXPLORER
    // ═══════════════════════════════════════════════════════════════════════

    async function loadFiles(path) {
        if (path) state.currentPath = path;
        const showHidden = $('show-hidden')?.checked || false;

        try {
            const data = await api(`/files/browse?path=${encodeURIComponent(state.currentPath)}&hidden=${showHidden}`);
            if (!data) return;

            // Breadcrumb
            const parts = state.currentPath.split('/').filter(Boolean);
            let crumbPath = '/';
            let breadcrumbHtml = `<a href="#" class="crumb" data-fpath="/">/</a>`;
            parts.forEach(p => {
                crumbPath += p + '/';
                breadcrumbHtml += `<span class="crumb-separator">/</span><a href="#" class="crumb" data-fpath="${crumbPath}">${escapeHtml(p)}</a>`;
            });
            $('file-breadcrumb').innerHTML = breadcrumbHtml;

            // Add parent directory entry
            let entries = data.entries;
            if (state.currentPath !== '/') {
                entries = [{ name: '..', is_dir: true, path: data.parent, size_human: '-', modified: '', permissions: '', owner: '' }, ...entries];
            }

            // File list
            $('files-body').innerHTML = entries.map(f => {
                const icon = f.is_dir ? '📁' : getFileIcon(f.name);
                return `
                    <tr>
                        <td>
                            <span class="file-name ${f.is_dir ? 'dir' : ''}" data-fpath="${escapeHtml(f.path)}" data-isdir="${f.is_dir}">
                                ${icon} ${escapeHtml(f.name)}
                            </span>
                        </td>
                        <td>${f.size_human || '-'}</td>
                        <td>${f.modified ? timeAgo(f.modified) : ''}</td>
                        <td class="mono">${f.permissions || ''}</td>
                        <td>${escapeHtml(f.owner || '')}</td>
                        <td>
                            <div class="file-actions-cell">
                                ${!f.is_dir && f.name !== '..' ? `
                                    <button class="btn-sm" onclick="window.__si.downloadFile('${escapeHtml(f.path)}')" title="Download">⬇</button>
                                    <button class="btn-sm" onclick="window.__si.shareFile('${escapeHtml(f.path)}')" title="Share">🔗</button>
                                ` : ''}
                                ${f.name !== '..' ? `<button class="btn-sm danger" onclick="window.__si.deleteFile('${escapeHtml(f.path)}', '${escapeHtml(f.name)}')" title="Delete">🗑</button>` : ''}
                            </div>
                        </td>
                    </tr>
                `;
            }).join('') || '<tr><td colspan="6" style="text-align:center;color:var(--text-muted)">Empty directory</td></tr>';

            // Attach click handlers
            $$('.file-name').forEach(el => {
                el.addEventListener('click', () => {
                    const fpath = el.dataset.fpath;
                    if (el.dataset.isdir === 'true') {
                        loadFiles(fpath);
                    } else {
                        previewFile(fpath);
                    }
                });
            });

            $$('.crumb').forEach(el => {
                el.addEventListener('click', e => {
                    e.preventDefault();
                    loadFiles(el.dataset.fpath);
                });
            });

        } catch (err) {
            toast('Failed to browse files: ' + err.message, 'error');
        }
    }

    function getFileIcon(name) {
        const ext = (name.split('.').pop() || '').toLowerCase();
        const icons = {
            'py': '🐍', 'js': '📜', 'ts': '📘', 'html': '🌐', 'css': '🎨',
            'json': '📋', 'xml': '📋', 'yml': '📋', 'yaml': '📋',
            'md': '📝', 'txt': '📄', 'log': '📄', 'cfg': '⚙️', 'conf': '⚙️', 'ini': '⚙️',
            'sh': '🔧', 'bash': '🔧', 'zsh': '🔧',
            'jpg': '🖼', 'jpeg': '🖼', 'png': '🖼', 'gif': '🖼', 'svg': '🖼', 'webp': '🖼',
            'mp4': '🎬', 'mkv': '🎬', 'avi': '🎬',
            'mp3': '🎵', 'wav': '🎵', 'ogg': '🎵',
            'zip': '📦', 'tar': '📦', 'gz': '📦', 'bz2': '📦', 'xz': '📦', 'rar': '📦',
            'deb': '📦', 'rpm': '📦',
            'pdf': '📕', 'doc': '📘', 'docx': '📘', 'xls': '📗', 'xlsx': '📗',
            'key': '🔑', 'pem': '🔑', 'crt': '🔑', 'csr': '🔑',
            'db': '🗄', 'sql': '🗄', 'sqlite': '🗄',
            'c': '💻', 'cpp': '💻', 'h': '💻', 'java': '☕', 'go': '🔵', 'rs': '🦀',
            'rb': '💎', 'php': '🐘', 'pl': '🐪', 'r': '📊',
            'so': '⚙️', 'o': '⚙️', 'a': '⚙️'
        };
        return icons[ext] || '📄';
    }

    function downloadFile(path) {
        window.open(`/api/files/download?path=${encodeURIComponent(path)}&token=${state.token}`, '_blank');
    }

    async function shareFile(path) {
        try {
            const data = await api('/files/share', {
                method: 'POST',
                body: JSON.stringify({ path, expires_hours: 24 })
            });
            if (data.success) {
                const shareUrl = `${window.location.origin}${data.url}`;
                showModal('Share Link', `
                    <p>This link will expire in ${data.expires_in}:</p>
                    <div class="input-wrapper" style="margin-top:12px">
                        <input type="text" value="${shareUrl}" readonly style="width:100%;padding:10px;background:var(--bg-input);border:1px solid var(--border);border-radius:var(--radius-sm);color:var(--text-primary);font-family:var(--font-mono);font-size:0.8rem" onclick="this.select()">
                    </div>
                    <button class="btn-sm primary" style="margin-top:12px" onclick="navigator.clipboard.writeText('${shareUrl}');window.__si.toast('Link copied!','success')">📋 Copy Link</button>
                `);
            }
        } catch (err) {
            toast('Failed to create share link: ' + err.message, 'error');
        }
    }

    async function deleteFile(path, name) {
        if (!confirm(`Delete "${name}"? This cannot be undone.`)) return;
        try {
            const data = await api('/files/delete', {
                method: 'POST',
                body: JSON.stringify({ path })
            });
            toast(data.message, 'success');
            loadFiles();
        } catch (err) {
            toast('Failed to delete: ' + err.message, 'error');
        }
    }

    async function previewFile(path) {
        try {
            const data = await api(`/files/read?path=${encodeURIComponent(path)}`);
            const name = path.split('/').pop();
            showModal(`📄 ${name}`, `<pre class="code-block">${escapeHtml(data.content)}</pre>`);
        } catch (err) {
            toast('Cannot preview this file: ' + err.message, 'error');
        }
    }

    function uploadFiles() {
        const input = $('file-upload-input');
        input.onchange = async () => {
            const formData = new FormData();
            formData.append('path', state.currentPath);
            for (const file of input.files) {
                formData.append('files', file);
            }
            try {
                const res = await fetch('/api/files/upload', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${state.token}` },
                    body: formData
                });
                const data = await res.json();
                if (data.uploaded?.length > 0) {
                    toast(`Uploaded ${data.uploaded.length} file(s)`, 'success');
                    loadFiles();
                }
                if (data.errors?.length > 0) {
                    data.errors.forEach(e => toast(`Upload failed: ${e.file} - ${e.error}`, 'error'));
                }
            } catch (err) {
                toast('Upload failed: ' + err.message, 'error');
            }
            input.value = '';
        };
        input.click();
    }

    function createFolder() {
        const name = prompt('Enter folder name:');
        if (!name) return;
        api('/files/mkdir', {
            method: 'POST',
            body: JSON.stringify({ path: state.currentPath + '/' + name })
        }).then(data => {
            toast(data.message, 'success');
            loadFiles();
        }).catch(err => toast('Failed: ' + err.message, 'error'));
    }

    // ═══════════════════════════════════════════════════════════════════════
    // TERMINAL
    // ═══════════════════════════════════════════════════════════════════════

    function initTerminal() {
        if (state.terminalConnected) return;

        const container = $('terminal-view');
        container.innerHTML = '';

        if (typeof Terminal === 'undefined') {
            container.innerHTML = '<p style="color:var(--text-muted);padding:20px">Loading terminal...</p>';
            return;
        }

        state.terminal = new Terminal({
            cursorBlink: true,
            fontSize: 14,
            fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
            theme: {
                background: '#0d1117',
                foreground: '#c9d1d9',
                cursor: '#58a6ff',
                selectionBackground: '#264f78',
                black: '#0d1117',
                red: '#ff7b72',
                green: '#7ee787',
                yellow: '#d29922',
                blue: '#58a6ff',
                magenta: '#bc8cff',
                cyan: '#39c5cf',
                white: '#c9d1d9',
                brightBlack: '#484f58',
                brightRed: '#ffa198',
                brightGreen: '#56d364',
                brightYellow: '#e3b341',
                brightBlue: '#79c0ff',
                brightMagenta: '#d2a8ff',
                brightCyan: '#56d4dd',
                brightWhite: '#f0f6fc'
            },
            allowProposedApi: true
        });

        const fitAddon = new FitAddon.FitAddon();
        state.terminalFit = fitAddon;
        state.terminal.loadAddon(fitAddon);

        try {
            const webLinksAddon = new WebLinksAddon.WebLinksAddon();
            state.terminal.loadAddon(webLinksAddon);
        } catch (e) { /* ignore */ }

        state.terminal.open(container);
        setTimeout(() => fitAddon.fit(), 100);

        // Connect WebSocket
        connectTerminal();

        // Handle resize
        window.addEventListener('resize', () => {
            if (state.terminalFit && state.currentTab === 'terminal') {
                state.terminalFit.fit();
            }
        });
    }

    function connectTerminal() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        state.socket = io(window.location.origin, {
            transports: ['websocket'],
            reconnection: true,
            reconnectionDelay: 2000,
            reconnectionAttempts: 5
        });

        state.socket.on('connect', () => {
            const cols = state.terminal.cols;
            const rows = state.terminal.rows;
            state.socket.emit('terminal_connect', {
                token: state.token,
                cols: cols,
                rows: rows
            });
        });

        state.socket.on('terminal_ready', () => {
            state.terminalConnected = true;
            $('btn-terminal-reconnect').style.display = 'none';
            $('terminal-title').textContent = `Terminal — ${state.user?.username || 'user'}@${$('topbar-host')?.textContent || 'server'}`;

            // Send input to server
            state.terminal.onData(data => {
                if (state.socket && state.terminalConnected) {
                    state.socket.emit('terminal_input', { input: data });
                }
            });

            // Handle resize
            state.terminal.onResize(({ cols, rows }) => {
                if (state.socket && state.terminalConnected) {
                    state.socket.emit('terminal_resize', { cols, rows });
                }
            });
        });

        state.socket.on('terminal_output', (data) => {
            if (state.terminal) {
                state.terminal.write(data.output);
            }
        });

        state.socket.on('terminal_error', (data) => {
            toast('Terminal error: ' + data.error, 'error');
        });

        state.socket.on('terminal_exit', () => {
            state.terminalConnected = false;
            $('btn-terminal-reconnect').style.display = 'inline-block';
            if (state.terminal) {
                state.terminal.write('\r\n\x1b[31m[Session ended]\x1b[0m\r\n');
            }
        });

        state.socket.on('disconnect', () => {
            state.terminalConnected = false;
            $('btn-terminal-reconnect').style.display = 'inline-block';
        });
    }

    function disconnectTerminal() {
        if (state.socket) {
            state.socket.emit('terminal_disconnect');
            state.socket.disconnect();
            state.socket = null;
        }
        state.terminalConnected = false;
        if (state.terminal) {
            state.terminal.dispose();
            state.terminal = null;
        }
    }

    function reconnectTerminal() {
        disconnectTerminal();
        $('terminal-view').innerHTML = '';
        setTimeout(initTerminal, 300);
    }

    // ═══════════════════════════════════════════════════════════════════════
    // SETTINGS
    // ═══════════════════════════════════════════════════════════════════════

    async function loadSettings() {
        try {
            const data = await api('/settings/overview');
            if (!data) return;

            $('settings-general').innerHTML = `
                <div class="info-row"><span class="info-label">Hostname</span><span class="info-value">${escapeHtml(data.hostname.hostname)}</span></div>
                <div class="info-row"><span class="info-label">FQDN</span><span class="info-value">${escapeHtml(data.hostname.fqdn)}</span></div>
                <div class="info-row"><span class="info-label">Timezone</span><span class="info-value">${escapeHtml(data.timezone.timezone)}</span></div>
                <div class="info-row"><span class="info-label">Local Time</span><span class="info-value">${escapeHtml(data.timezone.local_time)}</span></div>
                <div class="info-row"><span class="info-label">NTP Synced</span><span class="info-value"><span class="badge ${data.timezone.ntp_synced ? 'active' : 'warning'}">${data.timezone.ntp_synced ? 'Yes' : 'No'}</span></span></div>
                ${Object.entries(data.locale || {}).slice(0, 5).map(([k, v]) => `<div class="info-row"><span class="info-label">${escapeHtml(k)}</span><span class="info-value">${escapeHtml(v)}</span></div>`).join('')}
            `;
        } catch (err) {
            toast('Failed to load settings: ' + err.message, 'error');
        }
    }

    async function loadUsers() {
        try {
            const data = await api('/settings/users');
            if (!data) return;
            $('users-body').innerHTML = data.users.map(u => `
                <tr>
                    <td><strong>${escapeHtml(u.username)}</strong>${u.is_root ? ' <span class="badge warning">root</span>' : ''}</td>
                    <td class="mono">${u.uid}</td>
                    <td class="mono">${escapeHtml(u.home)}</td>
                    <td class="mono">${escapeHtml(u.shell)}</td>
                    <td>${u.groups.slice(0, 5).map(g => `<span class="badge active">${escapeHtml(g)}</span>`).join(' ')}</td>
                    <td>${escapeHtml(u.last_login)}</td>
                </tr>
            `).join('');
        } catch (err) { toast('Failed to load users', 'error'); }
    }

    async function loadSecurity() {
        try {
            const data = await api('/settings/security');
            if (!data) return;
            $('security-info').innerHTML = `
                <div class="info-row"><span class="info-label">SELinux</span><span class="info-value">${escapeHtml(data.selinux)}</span></div>
                <div class="info-row"><span class="info-label">AppArmor</span><span class="info-value">${escapeHtml(data.apparmor)}</span></div>
                <div class="info-row"><span class="info-label">Firewall</span><span class="info-value">${escapeHtml(data.firewall)}</span></div>
                ${Object.entries(data.ssh_config || {}).map(([k, v]) => `<div class="info-row"><span class="info-label">SSH: ${escapeHtml(k)}</span><span class="info-value">${escapeHtml(v)}</span></div>`).join('')}
            `;
        } catch (err) { toast('Failed to load security info', 'error'); }
    }

    async function loadCron() {
        try {
            const data = await api('/settings/cron');
            if (!data) return;
            $('cron-list').innerHTML = data.jobs.map(j => createAccordion(
                `cron-${j.user}-${j.source.replace(/[^a-z0-9]/gi, '-')}`,
                `📅 ${j.user}`, `${j.entries.length} jobs · ${j.source}`,
                `<pre class="code-block">${j.entries.map(e => escapeHtml(e)).join('\n') || 'No entries'}</pre>
                <div class="accordion-description">Cron jobs are scheduled tasks that run automatically at specified intervals. They are commonly used for backups, log rotation, and system maintenance.</div>`
            )).join('') || '<p style="color:var(--text-muted);text-align:center;padding:20px">No cron jobs found</p>';
            attachAccordionListeners($('cron-list'));
        } catch (err) { toast('Failed to load cron jobs', 'error'); }
    }

    async function loadSysctl() {
        try {
            const data = await api('/settings/sysctl');
            if (!data) return;
            $('sysctl-info').innerHTML = Object.entries(data).map(([k, v]) =>
                `<div class="info-row"><span class="info-label" style="min-width:200px">${escapeHtml(k)}</span><span class="info-value">${escapeHtml(v)}</span></div>`
            ).join('') || '<p style="color:var(--text-muted)">No sysctl parameters available</p>';
        } catch (err) { toast('Failed to load kernel parameters', 'error'); }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // ACCORDION & MODAL HELPERS
    // ═══════════════════════════════════════════════════════════════════════

    function createAccordion(id, title, subtitle, body) {
        return `
            <div class="accordion-item" id="acc-${id}">
                <div class="accordion-header">
                    <svg class="accordion-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="9 18 15 12 9 6"/>
                    </svg>
                    <span class="accordion-title">${title}</span>
                    <span class="accordion-subtitle">${subtitle}</span>
                </div>
                <div class="accordion-body">${body}</div>
            </div>
        `;
    }

    function attachAccordionListeners(container) {
        container.querySelectorAll('.accordion-header').forEach(header => {
            header.addEventListener('click', () => {
                const item = header.parentElement;
                item.classList.toggle('open');
            });
        });
    }

    function showModal(title, bodyHtml, footerHtml = '') {
        $('modal-title').textContent = title;
        $('modal-body').innerHTML = bodyHtml;
        $('modal-footer').innerHTML = footerHtml;
        $('modal-overlay').style.display = 'flex';
    }

    function closeModal() {
        $('modal-overlay').style.display = 'none';
    }

    // ═══════════════════════════════════════════════════════════════════════
    // LIVE UPDATES
    // ═══════════════════════════════════════════════════════════════════════

    function startLiveUpdates() {
        stopTimers();
        state.liveTimer = setInterval(async () => {
            if (state.currentTab === 'dashboard') {
                try {
                    const data = await api('/system/live');
                    if (data) {
                        $('dash-cpu-value').textContent = `${data.cpu_percent}%`;
                        $('dash-cpu-bar').style.width = `${data.cpu_percent}%`;
                        $('dash-mem-value').textContent = `${data.memory_percent}%`;
                        $('dash-mem-bar').style.width = `${data.memory_percent}%`;
                    }
                } catch (e) { /* ignore */ }
            }
        }, 5000);
    }

    function stopTimers() {
        if (state.liveTimer) { clearInterval(state.liveTimer); state.liveTimer = null; }
        if (state.refreshTimer) { clearInterval(state.refreshTimer); state.refreshTimer = null; }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // EVENT LISTENERS
    // ═══════════════════════════════════════════════════════════════════════

    function initEventListeners() {
        // Login form
        $('login-form').addEventListener('submit', e => {
            e.preventDefault();
            login($('username').value, $('password').value);
        });

        // Toggle password
        $('toggle-password').addEventListener('click', () => {
            const input = $('password');
            input.type = input.type === 'password' ? 'text' : 'password';
        });

        // Logout
        $('btn-logout').addEventListener('click', logout);

        // Sidebar
        $('sidebar-collapse').addEventListener('click', toggleSidebar);
        $('mobile-menu').addEventListener('click', () => {
            $('sidebar').classList.toggle('mobile-open');
        });

        // Navigation
        $$('.nav-item').forEach(item => {
            item.addEventListener('click', e => {
                e.preventDefault();
                loadTab(item.dataset.tab);
            });
        });

        // Refresh
        $('btn-refresh').addEventListener('click', () => {
            $('btn-refresh').classList.add('spinning');
            loadTab(state.currentTab);
            setTimeout(() => $('btn-refresh').classList.remove('spinning'), 1000);
        });

        // Modal close
        $('modal-close').addEventListener('click', closeModal);
        $('modal-overlay').addEventListener('click', e => {
            if (e.target === $('modal-overlay')) closeModal();
        });

        // Sub-tabs
        $$('.sub-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const parent = tab.parentElement;
                const contentPrefix = tab.closest('.tab-content').id.replace('tab-', '');

                parent.querySelectorAll('.sub-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');

                const subtab = tab.dataset.subtab;
                tab.closest('.tab-content').querySelectorAll('.sub-tab-content').forEach(c => c.classList.remove('active'));
                const content = $(`subtab-content-${subtab}`);
                if (content) content.classList.add('active');

                // Load data for subtab
                switch (subtab) {
                    case 'packages': loadSoftwarePackages(); break;
                    case 'processes': loadProcesses(); break;
                    case 'startup': loadStartup(); break;
                    case 'interfaces': loadNetworkInterfaces(); break;
                    case 'ports': loadPorts(); break;
                    case 'connections': loadConnections(); break;
                    case 'dns': loadDns(); break;
                    case 'firewall': loadFirewall(); break;
                    case 'net-services': loadNetworkServices(); break;
                    case 'sys-general': loadSettings(); break;
                    case 'sys-users': loadUsers(); break;
                    case 'sys-security': loadSecurity(); break;
                    case 'sys-cron': loadCron(); break;
                    case 'sys-sysctl': loadSysctl(); break;
                }
            });
        });

        // Package search
        let pkgSearchTimeout;
        $('pkg-search')?.addEventListener('input', e => {
            clearTimeout(pkgSearchTimeout);
            pkgSearchTimeout = setTimeout(() => loadSoftwarePackages(e.target.value), 400);
        });

        // Process sort
        $('proc-sort')?.addEventListener('change', e => loadProcesses(e.target.value));

        // Service filter
        $$('.filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                btn.parentElement.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                renderServices(btn.dataset.filter, $('svc-search')?.value || '');
            });
        });

        // Service search
        let svcSearchTimeout;
        $('svc-search')?.addEventListener('input', e => {
            clearTimeout(svcSearchTimeout);
            svcSearchTimeout = setTimeout(() => {
                const activeFilter = document.querySelector('.filter-btn.active')?.dataset?.filter || 'all';
                renderServices(activeFilter, e.target.value);
            }, 300);
        });

        // File explorer
        $('btn-upload')?.addEventListener('click', uploadFiles);
        $('btn-mkdir')?.addEventListener('click', createFolder);
        $('show-hidden')?.addEventListener('change', () => loadFiles());

        // Terminal reconnect
        $('btn-terminal-reconnect')?.addEventListener('click', reconnectTerminal);

        // Keyboard shortcuts
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape') closeModal();
        });

        // Session activity monitor — refresh token periodically
        setInterval(async () => {
            if (state.token) {
                await refreshToken();
            }
        }, 15 * 60 * 1000); // Every 15 minutes

        // Visibility change — reload when returning to tab
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && state.token) {
                loadTab(state.currentTab);
            }
        });
    }

    // ═══════════════════════════════════════════════════════════════════════
    // EXPOSE GLOBAL API FOR INLINE HANDLERS
    // ═══════════════════════════════════════════════════════════════════════

    window.__si = {
        loadPkgs: loadSoftwarePackages,
        killProcess,
        controlService,
        viewServiceLogs,
        downloadFile,
        shareFile,
        deleteFile,
        toast
    };

    // ═══════════════════════════════════════════════════════════════════════
    // INITIALIZE
    // ═══════════════════════════════════════════════════════════════════════

    document.addEventListener('DOMContentLoaded', () => {
        initEventListeners();
        checkAuth();
    });

})();
