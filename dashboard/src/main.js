import Chart from 'chart.js/auto';
import { renderApp } from './app.js';

// Cargar datos y renderizar la aplicación
async function main() {
    try {
        const response = await fetch('/data/offers.json');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const offers = await response.json();

        // Inicializar tema oscuro si está guardado
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', savedTheme);

        // Renderizar la aplicación
        renderApp(offers);
    } catch (error) {
        console.error('Error loading offers:', error);
        const app = document.getElementById('app');
        app.innerHTML = `
            <div class="container">
                <div class="error-message">
                    <strong>Error al cargar ofertas:</strong> ${error.message}<br>
                    <small>Asegúrate de que dashboard/public/data/offers.json existe.</small>
                </div>
            </div>
        `;
    }
}

main();
