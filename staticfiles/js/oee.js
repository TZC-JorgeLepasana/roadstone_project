document.addEventListener('DOMContentLoaded', function() {
    let runtimeChart = null;
    let currentDays = 30;

    // Initialize dashboard
    initDashboard();

    // Date range button handlers
    document.querySelectorAll('.date-range-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            // Remove active class from all buttons
            document.querySelectorAll('.date-range-btn').forEach(b => {
                b.classList.remove('active');
            });
            // Add active class to clicked button
            this.classList.add('active');
            // Update current days
            currentDays = parseInt(this.dataset.days);
            // Reload data
            loadData();
        });
    });

    

    async function initDashboard() {
        await loadData();
    }


    async function loadData() {
        showLoading();
        
        try {
            const response = await fetch(`/api/oee/?days=${currentDays}`);
            if (!response.ok) throw new Error('Network response was not ok');
            
            const data = await response.json();
            
            updateKPIs(data);
            updateRuntimeChart(data.runtime_data);
            updateDryingTable(data.drying_efficiency);
        } catch (error) {
            console.error('Error loading data:', error);
            showError('Failed to load data');
        } finally {
            hideLoading();
        }
    }

    function updateKPIs(data) {
        document.getElementById('total-production').textContent = 
            data.total_production.toLocaleString();
        document.getElementById('total-emptyout').textContent = 
            data.total_emptyout.toLocaleString();

        // Format electricity consumption with comma separators and 2 decimal places
        const electricityValue = data.total_consumption.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
        document.getElementById('total-electricity').textContent = 
            `${electricityValue} kWh`;
    }

    function updateRuntimeChart(runtimeData) {
        const ctx = document.getElementById('runtimeChart').getContext('2d');
        
        // Destroy existing chart
        if (runtimeChart) {
            runtimeChart.destroy();
        }

        // Prepare data
        const labels = [];
        const values = [];
        const colors = [];
        
        Object.entries(runtimeData).forEach(([key, value]) => {
            if (value > 0) {
                labels.push(key);
                values.push(value);
                colors.push(getRandomColor());
            }
        });

        // Create new chart
        runtimeChart = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: colors,
                    borderColor: '#ffffff',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            boxWidth: 20,
                            padding: 15
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.raw || 0;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((value / total) * 100).toFixed(1);
                                return `${label}: ${secondsToHMS(value)} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

    function updateDryingTable(data) {
        document.getElementById('avg-drying').textContent = 
            data.avg_drying_rate.toFixed(2);
        document.getElementById('total-materials').textContent = 
            data.total_materials.toFixed(2);
        document.getElementById('total-rap').textContent = 
            data.total_rap.toFixed(2);
        document.getElementById('total-bitumen').textContent = 
            data.total_bitumen.toFixed(2);
        document.getElementById('total-mixer-hours').textContent = 
            data.total_mixer_hours.toFixed(2);
    }

    // Helper functions
    function secondsToHMS(seconds) {
        const hrs = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }

    function getRandomColor() {
        return `hsl(${Math.random() * 360}, 70%, 50%)`;
    }

    function showLoading() {
        document.getElementById('loading-overlay').style.display = 'flex';
    }

    function hideLoading() {
        document.getElementById('loading-overlay').style.display = 'none';
    }

    function showError(message) {
        // Implement your error display logic here
        console.error(message);
    }
    
});