// VARIABLES GLOBALES PARA INSTANCIAS DE GRÁFICOS
let chartSolicitudes = null;
let chartDano = null;

// URL base de tu API Backend (Asegúrate de cambiar el puerto si usas otro)
const API_URL = "http://localhost:3000/api"; 

document.addEventListener("DOMContentLoaded", () => {
    // Inicializar los dos gráficos de manera segura
    initGraficoSolicitudes();
    initGraficoNivelDano();
    
    // Escuchar el evento de envío del formulario de registro de usuario
    const formRegistro = document.getElementById("formRegistroUsuario");
    if (formRegistro) {
        formRegistro.addEventListener("submit", registrarUsuario);
    }
});

/* ============================================================
   1. GRÁFICO: SOLICITUDES ÚLTIMOS 7 DÍAS (Línea o Barra)
   ============================================================ */
function initGraficoSolicitudes() {
    const ctx = document.getElementById("graficoSolicitudes");
    if (!ctx) return;

    // Si ya existía una instancia previa, la destruimos para evitar duplicaciones fatales
    if (chartSolicitudes) chartSolicitudes.destroy();

    chartSolicitudes = new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'],
            datasets: [{
                label: 'Solicitudes Recibidas',
                data: [12, 19, 3, 5, 2, 3, 10], // Datos de prueba
                borderColor: '#076da7',
                backgroundColor: 'rgba(7, 109, 167, 0.1)',
                borderWidth: 2,
                tension: 0.3,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false, // CRÍTICO: Detiene el bucle de redimensión infinita
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: { beginAtZero: true }
            }
        }
    });
}

/* ============================================================
   2. GRÁFICO: NIVEL DE DAÑO (Dona o Pie)
   ============================================================ */
function initGraficoNivelDano() {
    const ctx = document.getElementById("graficoDano");
    if (!ctx) return;

    if (chartDano) chartDano.destroy();

    chartDano = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Leve', 'Moderado', 'Grave', 'Colapsado'],
            datasets: [{
                data: [40, 35, 15, 10], // Porcentajes o totales de prueba
                backgroundColor: ['#4ADE80', '#FCD34D', '#F97316', '#EF4444'],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false, // CRÍTICO: Detiene el bucle de redimensión infinita
            plugins: {
                legend: { position: 'bottom' }
            }
        }
    });
}

/* ============================================================
   3. FUNCIÓN: REGISTRAR USUARIO (Manejo de conexión limpia)
   ============================================================ */
async function registrarUsuario(event) {
    event.preventDefault();
    
    // Captura de inputs (Asegúrate de que coincidan exactamente los 'id' en tu HTML)
    const nombre = document.getElementById("regNombre")?.value;
    const email = document.getElementById("regEmail")?.value;
    const password = document.getElementById("regPassword")?.value;
    const errorContainer = document.getElementById("registroErrorMsg");

    if (errorContainer) errorContainer.style.display = "none";

    try {
        const response = await fetch(`${API_URL}/usuarios/registrar`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ nombre, email, password })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || "Error al procesar el registro.");
        }

        alert("¡Usuario registrado exitosamente!");
        window.location.reload(); // Reiniciar o redirigir según tu flujo

    } catch (error) {
        console.error("Error en la petición:", error);
        
        // Corrección del aviso: si el fetch falla sin un código de estado HTTP, es un problema de red.
        if (errorContainer) {
            errorContainer.innerText = "No se pudo conectar al servidor. Verifica que el backend esté encendido y que la URL de la API sea correcta.";
            errorContainer.style.display = "block";
        } else {
            alert("No se pudo conectar al servidor. Asegúrate de que el backend esté ejecutándose.");
        }
    }
}