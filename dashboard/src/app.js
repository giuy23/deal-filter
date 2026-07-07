import Chart from 'chart.js/auto';

export function renderApp(offers) {
    const app = document.getElementById('app');

    // Estado filtrado
    let filteredOffers = offers;

    // Crear interfaz
    const html = `
        <header>
            <div class="container">
                <h1>JobDistiller</h1>
                <p>Ofertas laborales filtradas y puntuadas según tu perfil</p>
                <div class="header-controls">
                    <div style="color: var(--color-muted); font-size: 0.9rem;">
                        Última actualización: ${new Date().toLocaleString('es-ES')}
                    </div>
                    <button class="theme-toggle" id="themeToggle">🌙 Tema oscuro</button>
                </div>
            </div>
        </header>

        <div class="container">
            <div class="stats">
                <div class="stat-card">
                    <div class="value">${offers.length}</div>
                    <div class="label">Ofertas totales</div>
                </div>
                <div class="stat-card">
                    <div class="value">${(offers.reduce((s, o) => s + o.score, 0) / offers.length).toFixed(1)}</div>
                    <div class="label">Score promedio</div>
                </div>
                <div class="stat-card">
                    <div class="value">${new Set(offers.map(o => o.source)).size}</div>
                    <div class="label">Fuentes</div>
                </div>
                <div class="stat-card">
                    <div class="value">${new Set(offers.flatMap(o => o.stack)).size}</div>
                    <div class="label">Tecnologías</div>
                </div>
            </div>

            <div class="filters">
                <h3>Filtros</h3>
                <div class="filter-group">
                    <div class="filter-item">
                        <label>Búsqueda</label>
                        <input type="text" id="searchInput" placeholder="Título, empresa, tecnología...">
                    </div>
                    <div class="filter-item">
                        <label>Score mínimo</label>
                        <input type="range" id="minScoreInput" min="0" max="100" value="0" style="cursor: pointer;">
                        <small id="minScoreValue">0</small>
                    </div>
                    <div class="filter-item">
                        <label>Modalidad</label>
                        <select id="remoteInput">
                            <option value="">Todas</option>
                            <option value="remote">Remota</option>
                            <option value="hybrid">Híbrida</option>
                            <option value="onsite">Presencial</option>
                        </select>
                    </div>
                    <div class="filter-item">
                        <label>Fuente</label>
                        <select id="sourceInput">
                            <option value="">Todas</option>
                            ${[...new Set(offers.map(o => o.source))].map(s =>
                                `<option value="${s}">${s}</option>`
                            ).join('')}
                        </select>
                    </div>
                </div>
            </div>

            <div class="charts-grid">
                <div class="chart-container">
                    <h3>Distribución de scores</h3>
                    <canvas id="scoreChart"></canvas>
                </div>
                <div class="chart-container">
                    <h3>Ofertas por fuente</h3>
                    <canvas id="sourceChart"></canvas>
                </div>
                <div class="chart-container">
                    <h3>Tecnologías demandadas</h3>
                    <canvas id="stackChart"></canvas>
                </div>
                <div class="chart-container">
                    <h3>Distribución por seniority</h3>
                    <canvas id="seniorityChart"></canvas>
                </div>
            </div>

            <div class="table-wrapper">
                <table id="offersTable">
                    <thead>
                        <tr>
                            <th style="width: 30%;">Oferta</th>
                            <th style="width: 15%;">Empresa</th>
                            <th style="width: 10%;">Score</th>
                            <th style="width: 15%;">Stack</th>
                            <th style="width: 15%;">Modalidad</th>
                            <th style="width: 15%;">Acción</th>
                        </tr>
                    </thead>
                    <tbody id="offersTableBody">
                    </tbody>
                </table>
            </div>
        </div>
    `;

    app.innerHTML = html;

    // Event listeners
    document.getElementById('themeToggle').addEventListener('click', toggleTheme);
    document.getElementById('searchInput').addEventListener('input', applyFilters);
    document.getElementById('minScoreInput').addEventListener('input', applyFilters);
    document.getElementById('remoteInput').addEventListener('change', applyFilters);
    document.getElementById('sourceInput').addEventListener('change', applyFilters);

    // Actualizar label del score slider
    document.getElementById('minScoreInput').addEventListener('input', (e) => {
        document.getElementById('minScoreValue').textContent = e.target.value;
    });

    // Renderizar gráficos
    renderCharts(offers);

    // Renderizar tabla
    function applyFilters() {
        const search = document.getElementById('searchInput').value.toLowerCase();
        const minScore = parseFloat(document.getElementById('minScoreInput').value);
        const remote = document.getElementById('remoteInput').value;
        const source = document.getElementById('sourceInput').value;

        filteredOffers = offers.filter(offer => {
            const matchSearch = !search ||
                offer.title.toLowerCase().includes(search) ||
                offer.company.toLowerCase().includes(search) ||
                offer.stack.some(s => s.includes(search));
            const matchScore = offer.score >= minScore;
            const matchRemote = !remote || offer.remote === remote;
            const matchSource = !source || offer.source === source;

            return matchSearch && matchScore && matchRemote && matchSource;
        });

        renderTable(filteredOffers);
    }

    function renderTable(data) {
        const tbody = document.getElementById('offersTableBody');

        if (data.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="no-data">No hay ofertas que coincidan con los filtros</td></tr>`;
            return;
        }

        tbody.innerHTML = data
            .sort((a, b) => b.score - a.score)
            .map((offer, idx) => {
                const scoreClass = offer.score >= 80 ? 'high' : offer.score >= 60 ? 'medium' : 'low';
                const stackDisplay = offer.stack.slice(0, 3).join(', ') + (offer.stack.length > 3 ? '...' : '');
                const remoteClass = offer.remote;
                const remoteLabel = {
                    'remote': 'Remota',
                    'hybrid': 'Híbrida',
                    'onsite': 'Presencial',
                    'unknown': 'Desconocida'
                }[offer.remote] || offer.remote;

                return `
                    <tr>
                        <td>
                            <div class="offer-title">
                                <a href="${offer.url}" target="_blank">${offer.title}</a>
                            </div>
                            <div id="breakdown-${idx}" class="breakdown-detail">
                                ${Object.entries(offer.score_breakdown)
                                    .sort(([,a], [,b]) => b - a)
                                    .map(([key, val]) => `
                                        <div class="breakdown-item">
                                            <span>${key}:</span>
                                            <strong>${val.toFixed(1)}</strong>
                                        </div>
                                    `).join('')}
                            </div>
                        </td>
                        <td>${offer.company}</td>
                        <td>
                            <span class="score ${scoreClass}" onclick="document.getElementById('breakdown-${idx}').classList.toggle('show')" style="cursor: pointer;">
                                ${offer.score.toFixed(1)}
                            </span>
                        </td>
                        <td>${stackDisplay}</td>
                        <td>
                            <span class="remote-badge ${remoteClass}">${remoteLabel}</span>
                        </td>
                        <td>
                            <a href="${offer.url}" target="_blank" style="color: var(--color-primary); text-decoration: none;">
                                Postular →
                            </a>
                        </td>
                    </tr>
                `;
            })
            .join('');
    }

    // Inicial
    applyFilters();
}

function renderCharts(offers) {
    const chartCtx = (id) => document.getElementById(id).getContext('2d');

    // Distribución de scores
    const scoreRanges = ['0-20', '20-40', '40-60', '60-80', '80-100'];
    const scoreCounts = [
        offers.filter(o => o.score < 20).length,
        offers.filter(o => o.score >= 20 && o.score < 40).length,
        offers.filter(o => o.score >= 40 && o.score < 60).length,
        offers.filter(o => o.score >= 60 && o.score < 80).length,
        offers.filter(o => o.score >= 80).length,
    ];
    new Chart(chartCtx('scoreChart'), {
        type: 'bar',
        data: {
            labels: scoreRanges,
            datasets: [{
                label: 'Cantidad',
                data: scoreCounts,
                backgroundColor: '#0066cc'
            }]
        },
        options: { responsive: true, maintainAspectRatio: false }
    });

    // Ofertas por fuente
    const sources = [...new Set(offers.map(o => o.source))];
    const sourceCounts = sources.map(s => offers.filter(o => o.source === s).length);
    new Chart(chartCtx('sourceChart'), {
        type: 'doughnut',
        data: {
            labels: sources,
            datasets: [{
                data: sourceCounts,
                backgroundColor: ['#0066cc', '#fd7e14', '#28a745', '#dc3545', '#6c757d']
            }]
        },
        options: { responsive: true, maintainAspectRatio: false }
    });

    // Tecnologías demandadas
    const stackFreq = {};
    offers.forEach(o => {
        o.stack.forEach(tag => {
            stackFreq[tag] = (stackFreq[tag] || 0) + 1;
        });
    });
    const topStack = Object.entries(stackFreq)
        .sort(([,a], [,b]) => b - a)
        .slice(0, 10);
    new Chart(chartCtx('stackChart'), {
        type: 'bar',
        data: {
            labels: topStack.map(([tag]) => tag),
            datasets: [{
                label: 'Demanda',
                data: topStack.map(([,count]) => count),
                backgroundColor: '#fd7e14'
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false
        }
    });

    // Seniority
    const seniorityLevels = ['junior', 'mid', 'senior', 'lead', 'unknown'];
    const senorityCounts = seniorityLevels.map(s =>
        offers.filter(o => o.seniority === s).length
    );
    new Chart(chartCtx('seniorityChart'), {
        type: 'pie',
        data: {
            labels: seniorityLevels,
            datasets: [{
                data: senorityCounts,
                backgroundColor: ['#17a2b8', '#ffc107', '#28a745', '#dc3545', '#6c757d']
            }]
        },
        options: { responsive: true, maintainAspectRatio: false }
    });
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    const newTheme = current === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    document.getElementById('themeToggle').textContent = newTheme === 'light' ? '🌙 Tema oscuro' : '☀️ Tema claro';
}
