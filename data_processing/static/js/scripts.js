// ==================== CORE MODULES ====================
(() => {
    const BaseModule = (() => {
        // Navbar scroll behavior
        const initNavbarScroll = () => {
            const navbar = document.querySelector('.main-header');
            if (!navbar) return;

            let lastScroll = 0;
            const freezeThreshold = 50;

            window.addEventListener('scroll', () => {
                const currentScroll = window.scrollY;
                
                if (currentScroll > freezeThreshold) {
                    navbar.classList.add('frozen');
                    navbar.style.animation = 'smoothFreeze 0.3s forwards';
                    
                    if (currentScroll > lastScroll) {
                        navbar.style.transform = 'translateY(-100%)';
                    } else {
                        navbar.style.transform = 'translateY(0)';
                    }
                } else {
                    navbar.classList.remove('frozen');
                    navbar.style.transform = 'translateY(0)';
                }
                
                lastScroll = currentScroll;
            });
        };

        // Sidebar toggle
        const initSidebar = () => {
            const toggleBtn = document.querySelector('.sidebar-toggle');
            if (toggleBtn) {
                toggleBtn.addEventListener('click', () => {
                    document.querySelector('.just-sidebar').classList.toggle('collapsed');
                });
            }
        };

        // Toast notification
        const showToast = (message, type = 'success') => {
            const bgColor = type === 'success' ? '#28a745' : '#dc3545';
            Toastify({
                text: message,
                duration: 3000,
                gravity: "top",
                backgroundColor: bgColor
            }).showToast();
        };

        return {
            init: () => {
                initNavbarScroll();
                initSidebar();
            },
            showToast
        };
    })();

    // ==================== DASHBOARD MODULE V1 ====================
    //Production Chart
    document.addEventListener('DOMContentLoaded', function() {
        // Initialize charts only if elements exist
        if (document.getElementById('productionChart')) {
            initializeProductionChart();
        }
        
        if (document.getElementById('utilizationChart')) {
            initializeUtilizationChart();
        }
    });

    let productionChart = null;

    function initializeProductionChart() {
        // Check if Chart.js is loaded

        const chartElement = document.getElementById('productionChart');
        if (!chartElement) return;
        
        if (typeof Chart === "undefined") {
            console.error("Chart.js is not loaded");
            return;
        }

        // Get chart elements
        const ctx = chartElement.getContext('2d');
        if (!ctx) {
            console.error("Production chart canvas context not found");
            return;
        }

        // Get data from Django
        const labelsElement = document.getElementById('chart-labels');
        const valuesElement = document.getElementById('chart-values');
        
        if (!labelsElement || !valuesElement) {
            console.error("Chart data elements not found");
            return;
        }

        try {
            const labels = JSON.parse(labelsElement.textContent);
            const values = JSON.parse(valuesElement.textContent);

            // Create gradient
            const gradient = ctx.createLinearGradient(0, 0, 0, ctx.canvas.height);
            gradient.addColorStop(0, "rgba(13, 110, 253, 0.7)");
            gradient.addColorStop(1, "rgba(13, 110, 253, 0.2)");

            // Destroy previous chart if exists
            if (productionChart) {
                productionChart.destroy();
            }

            // Create new chart
            productionChart = new Chart(ctx, {
                type: "line",
                data: {
                    labels: labels,
                    datasets: [{
                        label: "Production Output (Tonnage)",
                        data: values,
                        borderColor: "#0d6efd",
                        backgroundColor: gradient,
                        pointBackgroundColor: "#ffffff",
                        pointBorderColor: "#0d6efd",
                        pointRadius: 1,
                        fill: true,
                        tension: 0.4,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { 
                            display: true, 
                            position: "top", 
                            labels: { 
                                color: "#333", 
                                font: { size: 14 } 
                            } 
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return ` ${context.raw.toLocaleString()} Tonnage`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            title: { display: true, text: "Time", color: "#666" },
                            ticks: { color: "#555", autoSkip: true, maxTicksLimit: 10 },
                            grid: { color: "rgba(255, 255, 255, 0.1)" }
                        },
                        y: {
                            title: { display: true, text: "Tonnage", color: "#666" },
                            beginAtZero: true,
                            ticks: { color: "#555" },
                            grid: { color: "rgba(0, 0, 0, 0.06)" }
                        }
                    }
                }
            });
        } catch (error) {
            console.error("Error initializing production chart:", error);
        }
    }

    function initializeUtilizationChart() {
        const chartElement = document.getElementById('utilizationChart'); 
        if (!chartElement) return;
        if (!utilizationDataElement) {
            console.error("Utilization data element not found");
            return;
        }

        const ctx = chartElement.getContext('2d');
        if (!ctx) {
            console.error("Utilization chart canvas context not found");
            return;
        }

        try {
            let utilizationData = JSON.parse(utilizationDataElement.textContent);
            
            new Chart(ctx, {
                type: "doughnut",
                data: {
                    labels: ["Operational Hours", "Idle Hours"],
                    datasets: [{
                        data: [utilizationData.operational_hours, utilizationData.idle_hours],
                        backgroundColor: [
                            // Gradient for operational hours (blue)
                            (() => {
                                let gradient = ctx.createLinearGradient(0, 0, 0, ctx.canvas.height);
                                gradient.addColorStop(0, "rgba(76, 0, 255, 0.62)");
                                gradient.addColorStop(1, "rgba(8, 120, 241, 0.8)");
                                return gradient;
                            })(),
                            // Gradient for idle hours (green)
                            (() => {
                                let gradient = ctx.createLinearGradient(0, 0, 0, ctx.canvas.height);
                                gradient.addColorStop(0, "rgba(13, 74, 4, 0.99)");
                                gradient.addColorStop(1, "rgba(88, 130, 4, 0.85)");
                                return gradient;
                            })()
                        ],
                        borderColor: "#fff",
                        borderWidth: 2,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'top' },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return `${context.label}: ${context.raw.toFixed(2)} hours`;
                                }
                            }
                        }
                    }
                }
            });
        } catch (error) {
            console.error("Error initializing utilization chart:", error);
        }
    }



    function updateUtilizationChart(utilizationData) {
        const utilizationChart = Chart.getChart("utilizationChart");
        if (utilizationChart) {
            utilizationChart.data.datasets[0].data = [
                utilizationData.operational_hours,
                utilizationData.idle_hours
            ];
            utilizationChart.update();
        }
    }

    // ==================== NEW WIDGETS & TABLE FUNCTIONALITY ====================
    function updateWidgets() {
        // const widgetData = JSON.parse(document.getElementById('widget-data').textContent);
        const widgetDataElement = document.getElementById('widget-data');
        if (!widgetDataElement) return;

        try {
            const widgetData = JSON.parse(widgetDataElement.textContent);
            
            //  Production Widget if exists
            const productionElement = document.querySelector('.production-data');
            if (productionElement && widgetData.total_production !== undefined) {
                productionElement.textContent = widgetData.total_production;
            }
            
            //  RAP Consumption Widget if exists
            const rapElements = document.querySelectorAll('.small-box h3');
            if (rapElements.length > 1 && widgetData.rap_consumption !== undefined) {
                rapElements[1].textContent = widgetData.rap_consumption;
            }

            // Electricity Consumption Widget if exists
            const electricityElement = document.querySelector('.electricity-data');
            if (electricityElement && widgetData.electricity_consumption !== undefined) {
                electricityElement.textContent = widgetData.electricity_consumption;
            }
        } catch (error) {
            console.error('Error updating widgets:', error);
        }

    }

    function initializeMaterialTable() {
        const materialData = JSON.parse(document.getElementById('material-data').textContent);
        const tbody = document.getElementById('materialTableBody');
        
        materialData.forEach(item => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${item.date}</td>
                <td>${item.MaterialName}</td>
                <td class="text-end">${item.Quantity}</td>
            `;
            tbody.appendChild(row);
        });
    }

    // Initialize new features when DOM loads
    document.addEventListener('DOMContentLoaded', () => {
        updateWidgets();
        initializeMaterialTable();
    });


    // ==================== DATA TABLES MODULE ====================

    const DataTablesModule = (() => {
        const commonConfig = {
            dom: 'B<"clear">lfrtip',
            buttons: ['copy', 'csv', 'excel', 'pdf', 'print'],
            responsive: true,
            language: {
                search: "_INPUT_",
                searchPlaceholder: "Search...",
                paginate: {
                    first: "<i class='fas fa-angle-double-left'></i>",
                    previous: "<i class='fas fa-chevron-left'></i>",
                    next: "<i class='fas fa-chevron-right'></i>",
                    last: "<i class='fas fa-angle-double-right'></i>"
                }
            },
            pagingType: "full_numbers"
        };

        return {
            init: () => {
                if (document.getElementById('batchTable')) {
                    $('#batchTable').DataTable($.extend({}, commonConfig, {
                        scrollX: true,
                        autoWidth: false
                    }));
                }

                if (document.getElementById('processedFilesTable')) {
                    $('#processedFilesTable').DataTable($.extend({}, commonConfig, {
                        pageLength: 10,
                        lengthMenu: [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]]
                    }));
                }
            }
        };
    })();

    // ==================== SCHEDULE LIST MODULE ====================

    const ScheduleListModule = (() => {
        return {
            init: () => {
                if (!document.getElementById('scheduleTable')) return;

                // Toggle schedule status
                document.querySelectorAll('.toggle-schedule').forEach(btn => {
                    btn.addEventListener('change', async function() {
                        const scheduleId = this.dataset.scheduleId;
                        const isActive = this.checked;
                        
                        try {
                            const response = await fetch(`/api/schedules/${scheduleId}/toggle/`, {
                                method: 'POST',
                                headers: {
                                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                                    'Content-Type': 'application/json'
                                },
                                body: JSON.stringify({ is_active: isActive })
                            });
                            
                            const data = await response.json();
                            if (!response.ok) throw new Error(data.message || 'Failed to toggle schedule');
                            
                            BaseModule.showToast(`Schedule ${isActive ? 'activated' : 'deactivated'}`, 'success');
                        } catch (error) {
                            console.error('Error toggling schedule:', error);
                            this.checked = !isActive; // Revert UI on error
                            BaseModule.showToast(error.message, 'error');
                        }
                    });
                });
            }
        };
    })();

    // ==================== FILTER CONTROLS ==================== 
    // (DITO ILALAGAY ANG NUMBER 3)
    const initFilters = () => {
        document.querySelectorAll('[data-filter]').forEach(btn => {
            btn.addEventListener('click', function() {
                const filter = this.dataset.filter;
                
                // 1. Update active button styles
                document.querySelectorAll('[data-filter]').forEach(b => {
                    b.classList.remove('active', 'btn-primary');
                    b.classList.add('btn-outline-secondary');
                });
                this.classList.add('active', 'btn-primary');
                this.classList.remove('btn-outline-secondary');
                
                // 2. Filter the list items
                document.querySelectorAll('#processedFilesList li').forEach(item => {
                    item.style.display = (filter === 'all' || item.dataset.status === filter) 
                        ? '' 
                        : 'none';
                });
            });
        });
    };


    // ==================== PARSING MODULE ====================
    const ParsingModule = (() => {
        let socket = null;
        let progressInterval = null;

        // WebSocket connection
        const connectWebSocket = (taskId = null) => {
            const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
            const wsPath = taskId ? `ws/parsing_progress/${taskId}/` : 'ws/parsing_progress/';
            
            socket = new WebSocket(protocol + window.location.host + `/ws/${wsPath}`

            );

            socket.onmessage = (e) => {
                const data = JSON.parse(e.data);
                updateProgressUI(data);
                
                if (data.state === 'COMPLETED' || data.state === 'FAILED') {
                    updateParsingComplete();
                }
            };

            socket.onclose = (e) => {
                if (document.getElementById('parsingStatus')) { // Only reconnect if needed
                    console.log('WebSocket closed, reconnecting...', e.reason);
                    setTimeout(() => connectWebSocket(taskId), 5000);
                }
            };

            socket.onerror = (err) => {
                console.error('WebSocket error:', err);
            };
        };

        // Update progress UI with counts
        function updateProgressUI(data) {
            // Progress bar
            const progress = data.progress || 0;
            document.getElementById('progressBar').style.width = `${progress}%`;
            document.getElementById('progressText').textContent = `${progress}%`;
            
            // File and batch counters
            if (data.files_processed !== undefined) {
                document.getElementById('filesProcessed').textContent = data.files_processed;
            }
            if (data.batches_processed !== undefined) {
                document.getElementById('batchesProcessed').textContent = data.batches_processed;
            }
            
            // Current file info
            if (data.current_file) {
                document.getElementById('currentFile').textContent = `Processing: ${data.current_file}`;
            }
            
            if (data.description) {
                document.getElementById('currentStatus').textContent = data.description;
            }
        }

        // Handle parsing completion
        const updateParsingComplete = () => {
            document.getElementById('parsingStatus').textContent = "Status: Ready";
            document.getElementById('startBtn').disabled = false;
            document.getElementById('pauseBtn').disabled = true;
            document.getElementById('pauseBtn').innerHTML = '<i class="bi bi-pause-circle"></i> Pause';
            fetchProcessedFiles();
        };

        // Fetch processed files
        const fetchProcessedFiles = async () => {
            try {
                const response = await fetch('/api/get-processed-files/');
                const data = await response.json();
                updateFileList(data.files);
            } catch (error) {
                console.error('Error fetching processed files:', error);
            }
        };

        
        // Enhanced file list update with counts
        function updateFileList(files) {
            const fileList = document.getElementById('processedFilesList');
            fileList.innerHTML = '';
            
            // Counters
            let successCount = 0;
            let errorCount = 0;
            let totalBatches = 0;

            files.forEach(file => {
                if (file.status === 'success') successCount++;
                if (file.status === 'error') errorCount++;
                if (file.batches) totalBatches += file.batches;
                
                const li = document.createElement('li');
                li.className = `list-group-item d-flex justify-content-between align-items-center py-2 
                            ${file.status === 'error' ? 'list-group-item-danger' : 
                                file.status === 'skipped' ? 'list-group-item-warning' : ''}`;
                li.dataset.status = file.status;
                
                li.innerHTML = `
                    <div>
                        <span class="badge ${file.status === 'success' ? 'bg-success' : 
                                        file.status === 'skipped' ? 'bg-warning' : 'bg-danger'} me-2">
                            ${file.status === 'success' ? '<i class="bi bi-check-circle"></i>' :
                            file.status === 'skipped' ? '<i class="bi bi-skip-forward"></i>' : 
                            '<i class="bi bi-exclamation-triangle"></i>'}
                        </span>
                        <span class="file-name">${file.file_name}</span>
                        ${file.schedule ? `<span class="badge bg-info ms-2">${file.schedule}</span>` : ''}
                    </div>
                    <small class="text-muted">${file.export_time}</small>
                `;
                fileList.appendChild(li);
            });

            // Update counters in the UI
            document.getElementById('filesProcessed').textContent = files.length;
            document.getElementById('batchesProcessed').textContent = totalBatches;
            
            // Update filter buttons
            updateFilterButtons(successCount, errorCount, files.length);
        }

        // Update filter buttons with counts
        function updateFilterButtons(success, error, total) {
            const buttons = {
                all: total,
                success: success,
                error: error
            };
            
            document.querySelectorAll('[data-filter]').forEach(btn => {
                const filter = btn.dataset.filter;
                btn.innerHTML = `${filter.charAt(0).toUpperCase() + filter.slice(1)} 
                                <span class="badge bg-dark ms-1">${buttons[filter]}</span>`;
            });
        }

        // Initialize parsing functionality
        const initParsing = () => {
            // File filtering
            document.querySelectorAll('[data-filter]').forEach(btn => {
                btn.addEventListener('click', function() {
                    const filter = this.dataset.filter;
                    document.querySelectorAll('#processedFilesList li').forEach(item => {
                        item.style.display = (filter === 'all' || item.dataset.status === filter) 
                            ? '' 
                            : 'none';
                    });
                    document.querySelectorAll('[data-filter]').forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                });
            });

            // Start Parsing Button
            document.getElementById('startBtn').addEventListener('click', async function() {
                const scheduleSelect = document.getElementById('scheduleSelect');
                const scheduleId = scheduleSelect ? scheduleSelect.value : '';
                
                try {
                    const url = scheduleId ? 
                        `/api/trigger-parsing/?schedule_id=${scheduleId}` : 
                        '/api/trigger-parsing/';
                    
                    const response = await fetch(url, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                            'Content-Type': 'application/x-www-form-urlencoded',
                        }
                    });

                    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

                    const data = await response.json();
                    
                    if (data.status === 'started') {
                        BaseModule.showToast("Parsing started successfully!", "success");
                        document.getElementById('parsingStatus').textContent = "Status: Parsing in progress";
                        document.getElementById('startBtn').disabled = true;
                        document.getElementById('pauseBtn').disabled = false;
                        connectWebSocket(data.task_id);
                    } else {
                        BaseModule.showToast(data.message || "Failed to start parsing", "error");
                    }
                } catch (error) {
                    BaseModule.showToast("Error: " + error.message, "error");
                    document.getElementById('startBtn').disabled = false;
                }
            });

            // Pause/Resume Button
            document.getElementById('pauseBtn').addEventListener('click', async function() {
                try {
                    const response = await fetch("/api/toggle-parsing/", {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                            'Content-Type': 'application/json'
                        }
                    });
                    
                    const data = await response.json();
                    
                    if (data.status === 'paused' || data.status === 'resumed') {
                        BaseModule.showToast(`Parsing ${data.status}`, data.status === 'paused' ? 'warning' : 'success');
                        this.innerHTML = data.status === 'paused' 
                            ? '<i class="bi bi-play-circle"></i> Resume' 
                            : '<i class="bi bi-pause-circle"></i> Pause';
                    }
                } catch (error) {
                    BaseModule.showToast("Error: " + error.message, "error");
                }
            });

            // Initial load and check for interrupted tasks
            fetchProcessedFiles();
            fetch('/api/check-interrupted/')
                .then(response => response.json())
                .then(data => {
                    if (data.found) {
                        BaseModule.showToast(`Found interrupted task for file: ${data.last_file}`, 'warning');
                    }
                })
                .catch(error => console.error('Error checking interrupted tasks:', error));
        };

        return {
            init: initParsing
        };
    })();


    // ==================== INITIALIZATION ====================
    // ==================== MODIFIED INITIALIZATION ====================
    document.addEventListener('DOMContentLoaded', () => {
        BaseModule.init();
        ParsingModule.init();
        initFilters();
        
        // Only call fetchProcessedFiles if the required elements exist
        if (document.getElementById('processedFilesList')) {
            fetchProcessedFiles();
            setTimeout(fetchProcessedFiles, 0);
            setInterval(fetchProcessedFiles, 30000);
        }
        
        // Only update widgets if on a page that has them
        if (document.getElementById('widget-data')) {
            updateWidgets();
        }

        // Initialize modules based on current page
        if (document.body.classList.contains('dashboard-page')) {
            initializeProductionChart();
            initializeUtilizationChart();
            initializeMaterialTable();
        }
        
        if (document.getElementById('batchTable') || document.getElementById('processedFilesTable')) {
            DataTablesModule.init();
        }
        
        if (document.getElementById('scheduleTable')) {
            ScheduleListModule.init();
        }
    });
})(); 