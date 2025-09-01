// Settings and Dashboard Management Module
// Handles settings modal, dashboard charts, and usage statistics

class SettingsManager {
    constructor(app) {
        this.app = app;
        this.charts = {};
    }

    // Open settings modal and load dashboard data
    async openSettingsModal() {
        const modal = document.getElementById('settings-modal');
        modal.style.display = 'flex';
        try {
            // Load all dashboard data in parallel
            await Promise.all([
                this.renderQuickStats(),
                this.renderUsageChart(),
                this.renderActivityTimelineChart(),
                this.renderModelPerformanceTable(),
                this.renderActivityLog()
            ]);
        } catch (e) {
            console.error('Error loading dashboard data:', e);
        }
    }

    // Close settings modal
    closeSettingsModal() {
        document.getElementById('settings-modal').style.display = 'none';
    }

    // Render quick statistics
    async renderQuickStats() {
        try {
            const response = await fetch('/llm-usage-stats');
            const data = await response.json();
            
            if (data.stats) {
                const activeModels = data.stats.length;
                const totalRequests = data.stats.reduce((sum, r) => sum + r.calls, 0);
                const totalTokens = data.stats.reduce((sum, r) => sum + r.total_tokens, 0);
                
                // Format large numbers
                const formatNumber = (num) => {
                    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
                    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
                    return num.toString();
                };
                
                // Update stats
                document.getElementById('stat-active-models').textContent = activeModels;
                document.getElementById('stat-total-requests').textContent = formatNumber(totalRequests);
                document.getElementById('stat-avg-response').textContent = '245ms'; // Mock data for now
                document.getElementById('stat-success-rate').textContent = '99.8%'; // Mock data for now
            }
        } catch (error) {
            console.error('Error loading quick stats:', error);
        }
    }

    // Render usage chart
    async renderUsageChart() {
        try {
            const response = await fetch('/llm-usage-stats');
            const data = await response.json();
            
            if (data.stats && data.stats.length > 0) {
                const ctx = document.getElementById('llm-usage-chart').getContext('2d');
                if (this.charts.usageChart) this.charts.usageChart.destroy();
                
                this.charts.usageChart = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: data.stats.map(r => r.model.replace('gpt-', 'GPT-').replace('claude-', 'Claude-')),
                        datasets: [{
                            label: 'API Calls (K)',
                            data: data.stats.map(r => Math.round(r.calls / 1000)),
                            backgroundColor: '#3b82f6',
                            borderRadius: 4,
                            categoryPercentage: 0.8,
                            barPercentage: 0.9
                        }, {
                            label: 'Tokens (M)',
                            data: data.stats.map(r => Math.round(r.total_tokens / 1000000)),
                            backgroundColor: '#8b5cf6',
                            borderRadius: 4,
                            categoryPercentage: 0.8,
                            barPercentage: 0.9
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom',
                                labels: {
                                    usePointStyle: true,
                                    padding: 20
                                }
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                grid: {
                                    color: '#f3f4f6'
                                },
                                ticks: {
                                    color: '#6b7280'
                                }
                            },
                            x: {
                                grid: {
                                    display: false
                                },
                                ticks: {
                                    color: '#6b7280'
                                }
                            }
                        }
                    }
                });
            }
        } catch (error) {
            console.error('Error loading usage chart:', error);
        }
    }

    // Render activity timeline chart
    async renderActivityTimelineChart() {
        try {
            const response = await fetch('/llm-usage-stats');
            const data = await response.json();
            
            if (data.timeseries && data.timeseries.length > 0) {
                const allDates = [...new Set(data.timeseries.map(r => r.date))].sort();
                const allModels = [...new Set(data.timeseries.map(r => r.model))];
                
                const modelColors = {
                    'claude-3.5-sonnet': '#10b981',
                    'gpt-4': '#3b82f6',
                    'gemini-pro': '#f59e0b',
                    'gpt-3.5-turbo': '#8b5cf6'
                };
                
                const datasets = allModels.map((model) => {
                    const color = modelColors[model] || '#6b7280';
                    return {
                        label: model.replace('gpt-', 'GPT-').replace('claude-', 'Claude-').replace('gemini-', 'Gemini-'),
                        data: allDates.map(date => {
                            const rec = data.timeseries.find(r => r.model === model && r.date === date);
                            return rec ? rec.calls : 0;
                        }),
                        borderColor: color,
                        backgroundColor: color + '20',
                        fill: false,
                        tension: 0.3,
                        pointRadius: 3,
                        pointHoverRadius: 6,
                        borderWidth: 3
                    };
                });
                
                const ctx = document.getElementById('activity-timeline-chart').getContext('2d');
                if (this.charts.activityChart) this.charts.activityChart.destroy();
                
                this.charts.activityChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: allDates.map(date => new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })),
                        datasets: datasets
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom',
                                labels: {
                                    usePointStyle: true,
                                    padding: 20
                                }
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                grid: {
                                    color: '#f3f4f6'
                                },
                                ticks: {
                                    color: '#6b7280'
                                }
                            },
                            x: {
                                grid: {
                                    color: '#f3f4f6'
                                },
                                ticks: {
                                    color: '#6b7280'
                                }
                            }
                        },
                        interaction: {
                            intersect: false,
                            mode: 'index'
                        }
                    }
                });
            }
        } catch (error) {
            console.error('Error loading activity timeline chart:', error);
        }
    }

    // Render model performance table
    async renderModelPerformanceTable() {
        try {
            const response = await fetch('/llm-usage-stats');
            const data = await response.json();
            
            if (data.stats && data.stats.length > 0) {
                const modelInfo = {
                    'claude-3.5-sonnet': { provider: 'Anthropic', status: 'active', costPer1k: 0.0015 },
                    'claude-3-sonnet': { provider: 'Anthropic', status: 'active', costPer1k: 0.0030 },
                    'claude-3-haiku': { provider: 'Anthropic', status: 'active', costPer1k: 0.0003 },
                    'gpt-4': { provider: 'OpenAI', status: 'active', costPer1k: 0.0300 },
                    'gpt-4-turbo': { provider: 'OpenAI', status: 'active', costPer1k: 0.0100 },
                    'gpt-3.5-turbo': { provider: 'OpenAI', status: 'deprecated', costPer1k: 0.0005 },
                    'gemini-pro': { provider: 'Google', status: 'limited', costPer1k: 0.0010 }
                };
                
                let tableHtml = `
                    <table>
                        <thead>
                            <tr>
                                <th>Model</th>
                                <th>LLM</th>
                                <th>Tokens</th>
                                <th>Cost per K</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                
                data.stats.forEach(row => {
                    const info = modelInfo[row.model] || { provider: 'Unknown', status: 'active', costPer1k: 0.001 };
                    const statusClass = info.status.toLowerCase();
                    const formattedTokens = row.total_tokens >= 1000000 ? 
                        (row.total_tokens / 1000000).toFixed(1) + 'M' : 
                        (row.total_tokens / 1000).toFixed(0) + 'K';
                    
                    tableHtml += `
                        <tr>
                            <td><strong>${row.model}</strong></td>
                            <td>${info.provider}</td>
                            <td>${formattedTokens}</td>
                            <td>$${info.costPer1k.toFixed(4)}</td>
                            <td><span class="status-badge ${statusClass}">${info.status}</span></td>
                        </tr>
                    `;
                });
                
                tableHtml += '</tbody></table>';
                document.getElementById('model-performance-table').innerHTML = tableHtml;
            }
        } catch (error) {
            console.error('Error loading model performance table:', error);
        }
    }

    // Render activity log
    async renderActivityLog() {
        try {
            const [errResponse, statsResponse] = await Promise.all([
                fetch('/llm-error-log'),
                fetch('/llm-usage-stats')
            ]);
            
            const errData = await errResponse.json();
            const statsData = await statsResponse.json();
            
            let activities = [];
            
            // Add error logs as warning activities
            if (errData.errors && errData.errors.length > 0) {
                errData.errors.slice(0, 3).forEach(error => {
                    activities.push({
                        type: 'warning',
                        icon: 'fas fa-exclamation-triangle',
                        title: `${error.model} API error`,
                        description: error.error_message,
                        time: new Date(error.timestamp).toLocaleString(),
                        badge: 'Warning'
                    });
                });
            }
            
            // Add recent successful activities (mock data for demonstration)
            if (statsData.timeseries && statsData.timeseries.length > 0) {
                const recentActivity = statsData.timeseries.slice(-3);
                recentActivity.forEach(activity => {
                    activities.push({
                        type: 'success',
                        icon: 'fas fa-check-circle',
                        title: `${activity.model} API request completed`,
                        description: `Successfully processed request with token usage: ${activity.tokens} tokens. Response time: 342ms. Cost: $${activity.cost.toFixed(5)}`,
                        time: new Date(activity.date).toLocaleString(),
                        badge: 'Success'
                    });
                });
            }
            
            // Add deployment update (mock)
            activities.push({
                type: 'info',
                icon: 'fas fa-sync-alt',
                title: 'Model deployment updated',
                description: 'GPT-4-Turbo model successfully updated to latest version. Performance improvements: 15% faster response time.',
                time: new Date(Date.now() - 2 * 60 * 60 * 1000).toLocaleString(),
                badge: 'Info'
            });
            
            let logHtml = '';
            activities.slice(0, 5).forEach(activity => {
                logHtml += `
                    <div class="activity-item">
                        <div class="activity-icon ${activity.type}">
                            <i class="${activity.icon}"></i>
                        </div>
                        <div class="activity-content">
                            <div class="activity-title">${activity.title}</div>
                            <div class="activity-description">${activity.description}</div>
                            <div class="activity-meta">
                                <span class="activity-badge ${activity.type}">${activity.badge}</span>
                            </div>
                        </div>
                        <div class="activity-time">${activity.time}</div>
                    </div>
                `;
            });
            
            if (activities.length === 0) {
                logHtml = '<div class="activity-item"><div class="activity-content">No recent activity</div></div>';
            }
            
            document.getElementById('activity-log').innerHTML = logHtml;
        } catch (error) {
            console.error('Error loading activity log:', error);
        }
    }

    // Render monthly token chart
    async renderMonthlyTokenChart() {
        try {
            const response = await fetch('/monthly-token-usage');
            const data = await response.json();
            
            if (data.monthly_stats && data.monthly_stats.length > 0) {
                // Organize data by month and model
                const months = [...new Set(data.monthly_stats.map(r => r.month))].sort();
                const models = [...new Set(data.monthly_stats.map(r => r.model))];
                
                const datasets = models.map((model, i) => {
                    const colors = ['#36a2eb', '#ff6384', '#4bc0c0', '#9966ff', '#ff9f40', '#ffcd56', '#c9cbcf'];
                    const color = colors[i % colors.length];
                    return {
                        label: model,
                        data: months.map(month => {
                            const record = data.monthly_stats.find(r => r.model === model && r.month === month);
                            return record ? record.total_tokens : 0;
                        }),
                        backgroundColor: color + '80', // Add transparency
                        borderColor: color,
                        borderWidth: 2,
                        tension: 0.2
                    };
                });
                
                const ctx = document.getElementById('monthly-tokens-chart').getContext('2d');
                if (this.charts.monthlyTokensChart) this.charts.monthlyTokensChart.destroy();
                this.charts.monthlyTokensChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: months,
                        datasets: datasets
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { 
                                display: true,
                                position: 'top'
                            },
                            title: { 
                                display: false
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                title: {
                                    display: true,
                                    text: 'Tokens'
                                }
                            }
                        },
                        interaction: {
                            intersect: false,
                            mode: 'index'
                        }
                    }
                });
            } else {
                document.getElementById('monthly-tokens-chart').style.display = 'none';
            }
        } catch (error) {
            console.error('Error rendering monthly token chart:', error);
        }
    }

    // Render session token chart
    async renderSessionTokenChart() {
        try {
            const response = await fetch('/session-token-usage');
            const data = await response.json();
            
            if (data.session_stats && data.session_stats.length > 0) {
                const models = data.session_stats.map(r => r.model);
                const tokens = data.session_stats.map(r => r.total_tokens);
                const colors = ['#36a2eb', '#ff6384', '#4bc0c0', '#9966ff', '#ff9f40', '#ffcd56', '#c9cbcf'];
                
                const ctx = document.getElementById('session-tokens-chart').getContext('2d');
                if (this.charts.sessionTokensChart) this.charts.sessionTokensChart.destroy();
                this.charts.sessionTokensChart = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: models,
                        datasets: [{
                            data: tokens,
                            backgroundColor: models.map((_, i) => colors[i % colors.length] + '80'),
                            borderColor: models.map((_, i) => colors[i % colors.length]),
                            borderWidth: 2
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: true,
                                position: 'right'
                            },
                            title: {
                                display: false
                            }
                        },
                        cutout: '50%'
                    }
                });
            } else {
                // Show placeholder text when no data
                const canvas = document.getElementById('session-tokens-chart');
                const parent = canvas.parentElement;
                if (!parent.querySelector('.no-data-message')) {
                    const message = document.createElement('div');
                    message.className = 'no-data-message';
                    message.style.cssText = 'text-align: center; color: #666; padding: 50px; font-style: italic;';
                    message.textContent = 'No token usage data for current session';
                    parent.appendChild(message);
                    canvas.style.display = 'none';
                }
            }
        } catch (error) {
            console.error('Error rendering session token chart:', error);
        }
    }

    // Cleanup charts when module is destroyed
    destroy() {
        Object.values(this.charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
        this.charts = {};
    }
}

// Export for use in main app
window.SettingsManager = SettingsManager;
