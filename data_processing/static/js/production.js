document.addEventListener('DOMContentLoaded', function() {
    // Initialize Toastify
    const showToast = (message, background = '#28a745') => {
        Toastify({
            text: message,
            duration: 3000,
            newWindow: true,
            close: true,
            gravity: "top",
            position: "right",
            backgroundColor: background,
            stopOnFocus: true,
        }).showToast();
    };

    // Get initial data from Django
    const chartLabels = JSON.parse(document.getElementById('chart-labels').textContent);
    const chartData = JSON.parse(document.getElementById('chart-data').textContent);
    const initialUnit = JSON.parse(document.getElementById('unit-json').textContent);
    const initialTimeRange = JSON.parse(document.getElementById('time-range-json').textContent);
    const initialRecipe = JSON.parse(document.getElementById('selected-recipe-json').textContent);

    // Chart initialization
    let productionChart = null;
    
    const initializeChart = () => {
        const ctx = document.getElementById('productionChart').getContext('2d');
        
        if (productionChart) {
            productionChart.destroy();
        }

        productionChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartLabels.map(label => new Date(label)),
                datasets: [{
                    label: `Daily Production (${initialUnit})`,
                    data: chartData,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.05)',
                    borderWidth: 2,
                    tension: 0.1,
                    fill: true,
                    pointRadius: 3,
                    pointHoverRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            title: (context) => new Date(context[0].label).toLocaleDateString('en-GB'),
                            label: (context) => `${context.dataset.label}: ${context.parsed.y.toLocaleString()}`
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: { unit: 'day', tooltipFormat: 'dd MMM yyyy' },
                        title: { display: true, text: 'Production Date' },
                        grid: { display: false }
                    },
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: `Production (${initialUnit})` },
                        ticks: { callback: (value) => `${value.toLocaleString()} ${initialUnit}` },
                        grid: { color: '#f3f4f6' }
                    }
                }
            }
        });
    };

    // Initialize chart if data exists
    if (chartLabels.length > 0 && chartData.length > 0) {
        initializeChart();
    }

    // Apply filters handler
    document.getElementById('applyFilters').addEventListener('click', function() {
        const params = new URLSearchParams();
        const timeRange = document.getElementById('timeRangeSelect').value;
        const recipe = document.getElementById('recipeSelect').value;
        const unit = document.getElementById('unitSelect').value;

        params.set('time_range', timeRange);
        if (recipe) params.set('recipe', recipe);
        params.set('unit', unit);

        // Show loading state
        const btn = this;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Applying...';
        btn.disabled = true;

        // Reload with new params
        setTimeout(() => {
            window.location.search = params.toString();
            showToast('Filters applied successfully!');
        }, 500);
    });
});