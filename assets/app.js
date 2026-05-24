// 全局状态
let currentPeriod = 'month';
let currentStore = 'all';
let currentPage = 'dashboard';
let authToken = localStorage.getItem('token') || '';
let currentUser = JSON.parse(localStorage.getItem('user') || 'null');
let dashboardCache = null;

// 页面配置
const pageConfig = {
    dashboard: { title: '数据看板', subtitle: '实时查看门店经营数据' },
    analysis: { title: '款式分析', subtitle: '销量排行与滞销预警' },
    alerts: { title: '异常预警', subtitle: '智能识别异常经营状况' },
    review: { title: '审核中心', subtitle: '低置信度条目二次确认' },
    voice: { title: '语音报账', subtitle: '语音录入交易信息' },
    camera: { title: '拍照录入', subtitle: '上传单据自动识别' },
    history: { title: '历史记录', subtitle: '查看所有交易记录' },
    reports: { title: '报告中心', subtitle: '生成各类经营报告' }
};

// API基础地址
const API_BASE = '';

// 带Token的fetch
function authFetch(url, options = {}) {
    if (authToken) {
        options.headers = options.headers || {};
        options.headers['Authorization'] = `Bearer ${authToken}`;
    }
    return fetch(url, options);
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    initNavigation();
    initDateFilter();
    initStoreSelector();
    initHistoryFilters();
    loadDashboardData();
    initVoiceRecording();
    initImageUpload();
});

// 检查登录状态
function checkAuth() {
    if (!currentUser) return;
    const nameEl = document.querySelector('.user-name');
    const roleEl = document.querySelector('.user-role');
    if (nameEl) nameEl.textContent = currentUser.name || currentUser.username;
    if (roleEl) roleEl.textContent = {owner:'连锁店总管',manager:'门店店长',accountant:'财务会计'}[currentUser.role] || currentUser.role;
    
    // 会计隐藏审核中心、语音报账、拍照录入
    if (currentUser.role === 'accountant') {
        document.querySelectorAll('.nav-item').forEach(item => {
            const page = item.dataset.page;
            if (['review', 'voice', 'camera'].includes(page)) {
                item.style.display = 'none';
            }
        });
    }
}

// 导航初始化
function initNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const page = item.dataset.page;
            switchPage(page);
        });
    });
}

// 页面切换
function switchPage(page) {
    currentPage = page;
    
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.page === page);
    });
    
    document.getElementById('pageTitle').textContent = pageConfig[page]?.title || page;
    document.getElementById('pageSubtitle').textContent = pageConfig[page]?.subtitle || '';
    
    document.querySelectorAll('.page').forEach(p => {
        p.classList.toggle('active', p.id === `${page}Page`);
    });
    
    // 按需加载页面数据
    if (page === 'dashboard') loadDashboardData();
    else if (page === 'analysis') loadAnalysisData();
    else if (page === 'alerts') loadAlertsData();
    else if (page === 'review') loadReviewData();
    else if (page === 'history') loadHistoryData();
}

// 日期筛选
function initDateFilter() {
    // 设置默认日期为当月第一天
    const dateFilter = document.getElementById('dateFilter');
    if (dateFilter) {
        const now = new Date();
        dateFilter.value = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-01';
    }

    document.querySelectorAll('.date-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.date-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentPeriod = btn.dataset.period;
            loadDashboardData();
        });
    });
}

// 门店选择器
function initStoreSelector() {
    fetch(`${API_BASE}/api/stores`)
        .then(res => res.json())
        .then(data => {
            const select = document.getElementById('storeSelect');
            if (select && data.stores) {
                data.stores.forEach(store => {
                    const option = document.createElement('option');
                    option.value = store.id || store.store_id;
                    option.textContent = store.name;
                    select.appendChild(option);
                });
            }
        })
        .catch(err => console.error('加载门店失败:', err));
}

// 加载看板数据
function loadDashboardData() {
    showLoading();
    
    authFetch(`${API_BASE}/api/dashboard?period=${currentPeriod}&store_id=${currentStore}`)
        .then(res => res.json())
        .then(data => {
            hideLoading();
            if (data.success) {
                dashboardCache = data;
                renderDashboard(data);
            } else {
                hideLoading();
                showNotification('加载数据失败', 'error');
            }
        })
        .catch(err => {
            hideLoading();
            console.error('加载看板数据失败:', err);
        });
}

// 渲染看板
function renderDashboard(data) {
    const summary = data.dashboard_data?.summary || {};
    
    document.getElementById('totalRevenue').textContent = formatCurrency(summary.total_revenue || 0);
    document.getElementById('totalCost').textContent = formatCurrency(summary.total_cost || 0);
    document.getElementById('grossProfit').textContent = formatCurrency(summary.gross_profit || 0);
    document.getElementById('netProfit').textContent = formatCurrency(summary.net_profit || 0);
    document.getElementById('grossMargin').textContent = (summary.gross_margin || 0).toFixed(1) + '%';
    document.getElementById('transactionCount').textContent = summary.transaction_count || 0;
    
    // 渲染预警
    renderAlerts(data.anomaly_alerts || []);
    
    // 渲染门店对比
    renderStoreComparison(data.dashboard_data?.store_stats || {});
    
    // 渲染品类分布
    renderCategoryStats(data.dashboard_data?.category_stats || {});
    
    // 渲染固定费用
    renderFixedExpenses(summary.fixed_expenses || {});

    // 渲染图表（延迟渲染确保Canvas存在）
    setTimeout(() => {
        renderTrendChart(data.dashboard_data?.trend_data || [], data.dashboard_data?.store_stats || {});
        renderCategoryPieChart(data.dashboard_data?.category_stats || {});
    }, 200);

    // 缓存供报告导出使用
    window.dashboardSummary = summary;
    window.dashboardStoreStats = data.dashboard_data?.store_stats || {};
    window.dashboardCategoryStats = data.dashboard_data?.category_stats || {};
    window.dashboardAlerts = data.anomaly_alerts || [];
    window.dashboardProductAnalysis = data.dashboard_data?.product_analysis || {};
}

// Chart.js 实例缓存
let trendChartInstance = null;
let categoryChartInstance = null;

// 渲染营收趋势图
function renderTrendChart(trendData, storeStats) {
    const canvas = document.getElementById('trendChart');
    if (!canvas) return;

    if (trendChartInstance) {
        trendChartInstance.destroy();
        trendChartInstance = null;
    }

    const ctx = canvas.getContext('2d');

    // 优先使用日趋势数据
    if (trendData && trendData.length > 0) {
        const labels = trendData.map(d => d.date.substring(5));  // MM-DD
        const revenues = trendData.map(d => d.revenue || 0);
        const costs = trendData.map(d => d.cost || 0);
        const profits = trendData.map(d => d.profit || 0);

        trendChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: '营收',
                        data: revenues,
                        borderColor: '#667eea',
                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                        fill: true,
                        tension: 0.3
                    },
                    {
                        label: '成本',
                        data: costs,
                        borderColor: '#fa709a',
                        backgroundColor: 'rgba(250, 112, 154, 0.1)',
                        fill: true,
                        tension: 0.3
                    },
                    {
                        label: '利润',
                        data: profits,
                        borderColor: '#43e97b',
                        backgroundColor: 'rgba(67, 233, 123, 0.1)',
                        fill: true,
                        tension: 0.3
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#ccc' } }
                },
                scales: {
                    x: { ticks: { color: '#999' }, grid: { display: false } },
                    y: { ticks: { color: '#999', callback: v => v >= 10000 ? (v/10000).toFixed(1)+'万' : v }, grid: { color: 'rgba(255,255,255,0.05)' } }
                }
            }
        });
        return;
    }

    // 回退：使用门店对比柱状图
    const stores = Object.entries(storeStats || {});
    const hasData = stores.length > 0 && stores.some(([_, s]) => (s.revenue || 0) > 0);

    if (!hasData) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#999';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('暂无营收趋势数据', canvas.width / 2, canvas.height / 2);
        return;
    }

    const labels = stores.map(([sid, s]) => s.store_name || sid);
    const revenues = stores.map(([_, s]) => s.revenue || 0);
    const costs = stores.map(([_, s]) => s.cost || 0);

    const colors = ['#667eea', '#764ba2', '#f093fb', '#4facfe', '#43e97b', '#fa709a'];

    trendChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '营收',
                    data: revenues,
                    backgroundColor: colors.slice(0, labels.length),
                    borderRadius: 6
                },
                {
                    label: '成本',
                    data: costs,
                    backgroundColor: 'rgba(255, 99, 132, 0.3)',
                    borderColor: 'rgba(255, 99, 132, 0.8)',
                    borderWidth: 1,
                    borderRadius: 6
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: '#999', font: { size: 12 } } }
            },
            scales: {
                x: { ticks: { color: '#999' }, grid: { display: false } },
                y: { ticks: { color: '#999', callback: v => v >= 10000 ? (v/10000).toFixed(1)+'万' : v }, grid: { color: 'rgba(255,255,255,0.05)' } }
            }
        }
    });
}

// 渲染品类占比饼图
function renderCategoryPieChart(categoryStats) {
    const canvas = document.getElementById('categoryChart');
    if (!canvas) return;

    if (categoryChartInstance) {
        categoryChartInstance.destroy();
        categoryChartInstance = null;
    }

    const ctx = canvas.getContext('2d');
    const entries = Object.entries(categoryStats || {});
    // 兼容新旧格式：新格式{revenue:100,...}，旧格式直接是数字
    const parsed = entries.map(([name, v]) => {
        if (typeof v === 'object' && v !== null) {
            return [name, v.revenue || 0];
        }
        return [name, v || 0];
    });
    const total = parsed.reduce((sum, [_, v]) => sum + v, 0);

    if (total === 0) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#999';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('暂无品类销售数据', canvas.width / 2, canvas.height / 2);
        return;
    }

    const pieColors = ['#667eea', '#764ba2', '#f093fb', '#4facfe', '#43e97b', '#fa709a', '#f5576c', '#ff9800'];

    categoryChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: parsed.map(([name, _]) => name),
            datasets: [{
                data: parsed.map(([_, v]) => v),
                backgroundColor: pieColors.slice(0, entries.length),
                borderWidth: 2,
                borderColor: '#1a1a2e'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: { color: '#ccc', font: { size: 12 }, padding: 12 }
                }
            }
        }
    });
}

// 格式化货币
function formatCurrency(value) {
    if (value >= 10000) {
        return '¥' + (value / 10000).toFixed(1) + '万';
    }
    return '¥' + value.toLocaleString();
}

// 渲染预警
function renderAlerts(alerts) {
    const container = document.getElementById('alertList');
    if (!container) return;
    
    if (alerts.length === 0) {
        container.innerHTML = '<div style="padding:12px;color:var(--success-color);"><i class="fas fa-check-circle"></i> 暂无异常预警</div>';
        return;
    }
    
    container.innerHTML = alerts.map(alert => `
        <div class="alert-item ${alert.level === 'critical' ? '' : 'warning'}">
            <div class="alert-icon">
                <i class="fas fa-exclamation-triangle"></i>
            </div>
            <div class="alert-content">
                <div class="alert-title">${alert.level === 'critical' ? '严重警告' : '注意'}</div>
                <div class="alert-desc">${alert.message}</div>
            </div>
        </div>
    `).join('');
}

// 渲染门店对比
function renderStoreComparison(storeStats) {
    const container = document.getElementById('storeComparison');
    if (!container) return;
    
    const stores = Object.entries(storeStats);
    if (stores.length === 0) {
        container.innerHTML = '<div style="padding:12px;color:var(--text-secondary);">暂无门店数据</div>';
        return;
    }
    
    const maxRevenue = Math.max(...stores.map(([_, s]) => s.revenue || 0));
    
    container.innerHTML = stores.map(([sid, data]) => {
        const percent = maxRevenue > 0 ? ((data.revenue || 0) / maxRevenue * 100) : 0;
        return `
            <div class="store-item">
                <span class="store-name">${data.store_name || sid}</span>
                <div class="store-bar">
                    <div class="bar-fill" style="width: ${percent}%"></div>
                </div>
                <span class="store-value">${formatCurrency(data.revenue || 0)}</span>
            </div>
        `;
    }).join('');
}

// 渲染品类统计
function renderCategoryStats(categoryStats) {
    const container = document.getElementById('categoryStats');
    if (!container) return;
    
    const total = Object.values(categoryStats).reduce((a, b) => a + b, 0);
    if (total === 0) {
        container.innerHTML = '<div style="padding:12px;color:var(--text-secondary);">暂无品类数据</div>';
        return;
    }
    
    container.innerHTML = Object.entries(categoryStats).map(([name, value]) => {
        const percent = total > 0 ? (value / total * 100).toFixed(1) : 0;
        return `
            <div class="category-item">
                <div class="category-name">${name}</div>
                <div class="category-value">${formatCurrency(value)}</div>
                <div class="category-percent">${percent}%</div>
            </div>
        `;
    }).join('');
}

// 渲染固定费用
function renderFixedExpenses(expenses) {
    const container = document.getElementById('fixedExpenses');
    if (!container) return;
    
    const labels = { rent: '房租', utilities: '水电费', salary: '人工成本', other: '其他费用' };
    const total = Object.values(expenses).reduce((a, b) => a + (b || 0), 0);
    
    if (total === 0) {
        container.innerHTML = '<div style="padding:12px;color:var(--text-secondary);">暂无费用数据</div>';
        return;
    }
    
    container.innerHTML = Object.entries(expenses).map(([key, value]) => `
        <div class="expense-item">
            <div class="expense-label">${labels[key] || key}</div>
            <div class="expense-value">${formatCurrency(value || 0)}</div>
        </div>
    `).join('');
}

// 加载款式分析数据
function loadAnalysisData() {
    authFetch(`${API_BASE}/api/dashboard?period=${currentPeriod}&store_id=${currentStore}`)
        .then(res => res.json())
        .then(data => {
            if (!data.success) return;
            const analysis = data.dashboard_data?.product_analysis || {};
            
            // 畅销排行
            const topSellers = document.getElementById('topSellers');
            if (topSellers) {
                const sellers = analysis.top_sellers || [];
                if (sellers.length === 0) {
                    topSellers.innerHTML = '<div style="padding:20px;color:var(--text-secondary);text-align:center;">暂无销售数据</div>';
                } else {
                    topSellers.innerHTML = sellers.map((item, index) => `
                        <div class="rank-item">
                            <span class="rank-number ${index < 3 ? 'top3' : ''}">${index + 1}</span>
                            <div class="rank-info">
                                <div class="rank-name">${item.name}</div>
                                <div class="rank-sales">已售 ${item.quantity} 件 · ${item.category || ''}</div>
                            </div>
                            <span class="rank-value">${formatCurrency(item.revenue)}</span>
                        </div>
                    `).join('');
                }
            }
            
            // 滞销预警
            const slowSellers = document.getElementById('slowSellers');
            if (slowSellers) {
                const slows = analysis.slow_sellers || [];
                if (slows.length === 0) {
                    slowSellers.innerHTML = '<div style="padding:20px;color:var(--success-color);text-align:center;"><i class="fas fa-check-circle"></i> 暂无滞销商品</div>';
                } else {
                    slowSellers.innerHTML = slows.map(item => `
                        <div class="slow-sell-item">
                            <div class="slow-sell-info">
                                <div class="slow-sell-name">${item.name}</div>
                                <div class="slow-sell-desc">仅售${item.quantity}件 · ${item.category || ''}</div>
                            </div>
                        </div>
                    `).join('');
                }
            }
            
            // AI补货建议
            const replenish = document.getElementById('replenishSuggestions');
            if (replenish && sellers.length > 0) {
                replenish.innerHTML = sellers.slice(0, 5).map(item => {
                    const suggestQty = Math.max(5, Math.round(item.quantity * 0.3));
                    return `
                        <div class="suggestion-item">
                            <span class="product-name">${item.name}</span>
                            <span class="suggestion-text">建议补货 <strong>${suggestQty}件</strong>，当前销量趋势良好</span>
                        </div>
                    `;
                }).join('');
            }
        })
        .catch(err => console.error('加载款式分析失败:', err));
}

// 加载异常预警数据
function loadAlertsData() {
    authFetch(`${API_BASE}/api/dashboard?period=${currentPeriod}&store_id=${currentStore}`)
        .then(res => res.json())
        .then(data => {
            if (!data.success) return;
            const alerts = data.anomaly_alerts || [];
            const container = document.getElementById('alertsList');
            if (!container) return;
            
            if (alerts.length === 0) {
                container.innerHTML = '<div style="padding:40px;text-align:center;color:var(--success-color);"><i class="fas fa-check-circle" style="font-size:48px;"></i><p style="margin-top:16px;font-size:16px;">当前无异常预警，经营状况良好</p></div>';
                return;
            }
            
            container.innerHTML = alerts.map(alert => `
                <div class="alert-card ${alert.level}">
                    <div class="alert-card-icon">
                        <i class="fas fa-${alert.level === 'critical' ? 'times-circle' : 'exclamation-circle'}"></i>
                    </div>
                    <div class="alert-card-content">
                        <div class="alert-card-title">${alert.type === 'low_margin' ? '毛利率异常' : alert.type === 'no_revenue' ? '营收异常' : alert.type === 'high_cost' ? '成本异常' : alert.type === 'negative_margin' ? '亏损预警' : '经营异常'}</div>
                        <div class="alert-card-desc">${alert.message}</div>
                    </div>
                </div>
            `).join('');
        })
        .catch(err => console.error('加载异常预警失败:', err));
}

// 加载审核数据
function loadReviewData() {
    authFetch(`${API_BASE}/api/reviews`)
        .then(res => res.json())
        .then(data => {
            if (!data.success) return;
            
            const pending = data.pending || [];
            const stats = data.stats || {};
            const canReview = data.can_review !== false;
            
            // 更新统计
            const statsContainer = document.querySelector('.review-stats');
            if (statsContainer) {
                statsContainer.innerHTML = `
                    <div class="review-stat-item"><span class="stat-number">${stats.pending_count || 0}</span><span class="stat-label">待审核</span></div>
                    <div class="review-stat-item"><span class="stat-number">${stats.approved_count || 0}</span><span class="stat-label">已通过</span></div>
                    <div class="review-stat-item"><span class="stat-number">${stats.rejected_count || 0}</span><span class="stat-label">已驳回</span></div>
                `;
            }
            
            const container = document.getElementById('reviewList');
            if (!container) return;
            
            if (pending.length === 0) {
                container.innerHTML = '<div style="padding:40px;text-align:center;color:var(--success-color);"><i class="fas fa-check-circle" style="font-size:48px;"></i><p style="margin-top:16px;">所有记录已审核完毕</p></div>';
                return;
            }
            
            const typeNames = {revenue:'销售', expense:'支出', return:'退货', purchase:'进货', inventory:'盘点'};
            
            container.innerHTML = pending.map((item, index) => `
                <div class="review-item" id="review_${item.id}">
                    <div class="review-header">
                        <span class="review-store"><i class="fas fa-store"></i> ${item.store_name || item.store_id}</span>
                        <span class="review-confidence ${(item.confidence || 0) < 0.7 ? 'low' : 'medium'}">
                            置信度 ${((item.confidence || 0.8) * 100).toFixed(0)}%
                        </span>
                    </div>
                    <div class="review-data">
                        <div class="review-row"><span>类型</span><span>${typeNames[item.type] || item.type}</span></div>
                        <div class="review-row"><span>商品</span><span>${(item.items || []).map(i => i.name + (i.quantity > 1 ? ' x' + i.quantity : '')).join(', ') || '-'}</span></div>
                        <div class="review-row"><span>金额</span><span style="color: ${item.type === 'revenue' ? 'var(--success-color)' : 'var(--danger-color)'}">${formatCurrency(item.total_amount || 0)}</span></div>
                        <div class="review-row"><span>时间</span><span>${item.created_at || ''}</span></div>
                    </div>
                    ${canReview ? `
                    <div class="review-actions">
                        <button class="btn-approve" onclick="approveReview('${item.id}')"><i class="fas fa-check"></i> 通过</button>
                        <button class="btn-reject" onclick="rejectReview('${item.id}')"><i class="fas fa-times"></i> 驳回</button>
                        <button class="btn-edit" onclick="editReview('${item.id}')"><i class="fas fa-edit"></i> 编辑</button>
                    </div>` : '<div style="padding:8px;color:var(--text-secondary);font-size:13px;"><i class="fas fa-info-circle"></i> 您无权审核</div>'}
                </div>
            `).join('');
        })
        .catch(err => console.error('加载审核数据失败:', err));
}

// 审核操作 - 真实API调用
function approveReview(recordId) {
    authFetch(`${API_BASE}/api/records/${recordId}/approve`, { method: 'PUT' })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showNotification('✅ 审核通过', 'success');
                const el = document.getElementById('review_' + recordId);
                if (el) el.remove();
                loadReviewData();
            } else {
                showNotification('❌ 操作失败: ' + (data.message || ''), 'error');
            }
        })
        .catch(err => showNotification('❌ 网络错误', 'error'));
}

function rejectReview(recordId) {
    if (!confirm('确认驳回这条记录？')) return;
    authFetch(`${API_BASE}/api/records/${recordId}/reject`, { method: 'PUT' })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showNotification('已驳回', 'info');
                const el = document.getElementById('review_' + recordId);
                if (el) el.remove();
                loadReviewData();
            } else {
                showNotification('❌ 操作失败: ' + (data.message || ''), 'error');
            }
        })
        .catch(err => showNotification('❌ 网络错误', 'error'));
}

function editReview(recordId) {
    const el = document.getElementById('review_' + recordId);
    if (!el) return;
    const item = el.querySelector('.review-data');
    if (!item) return;
    
    // 简单的行内编辑
    const rows = item.querySelectorAll('.review-row');
    rows.forEach(row => {
        const valueSpan = row.querySelectorAll('span')[1];
        if (valueSpan) {
            valueSpan.contentEditable = true;
            valueSpan.style.background = 'var(--input-bg)';
            valueSpan.style.padding = '2px 6px';
            valueSpan.style.borderRadius = '4px';
            valueSpan.focus();
        }
    });
    
    // 添加保存按钮
    const actions = el.querySelector('.review-actions');
    if (actions) {
        actions.innerHTML = `
            <button class="btn-approve" onclick="saveEdit('${recordId}')"><i class="fas fa-save"></i> 保存</button>
            <button class="btn-retry" onclick="loadReviewData()"><i class="fas fa-undo"></i> 取消</button>
        `;
    }
}

function saveEdit(recordId) {
    const el = document.getElementById('review_' + recordId);
    if (!el) return;
    
    const rows = el.querySelectorAll('.review-row');
    const data = {};
    rows.forEach(row => {
        const spans = row.querySelectorAll('span');
        if (spans.length >= 2) {
            const label = spans[0].textContent.trim();
            const value = spans[1].textContent.trim();
            if (label === '金额') data.total_amount = parseFloat(value.replace(/[¥,万]/g, '')) || 0;
            if (label === '商品') data.items = [{name: value, quantity: 1, amount: data.total_amount || 0}];
        }
    });
    
    authFetch(`${API_BASE}/api/records/${recordId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(res => res.json())
    .then(result => {
        if (result.success) {
            showNotification('✅ 已保存，需重新审核', 'success');
            loadReviewData();
        } else {
            showNotification('❌ 保存失败', 'error');
        }
    })
    .catch(err => showNotification('❌ 网络错误', 'error'));
}

// 历史记录
let historyPage = 1;
let historyType = 'all';
let historyDate = '';

function initHistoryFilters() {
    const typeFilter = document.getElementById('typeFilter');
    const dateFilter = document.getElementById('dateFilter');
    
    if (typeFilter) {
        typeFilter.addEventListener('change', (e) => {
            historyType = e.target.value;
            historyPage = 1;
            loadHistoryData();
        });
    }
    if (dateFilter) {
        dateFilter.addEventListener('change', (e) => {
            historyDate = e.target.value;
            historyPage = 1;
            loadHistoryData();
        });
    }
}

function loadHistoryData() {
    let url = `${API_BASE}/api/records?page=${historyPage}&page_size=15&store_id=${currentStore}`;
    if (historyType !== 'all') url += `&record_type=${historyType}`;
    if (historyDate) url += `&start_date=${historyDate}&end_date=${historyDate}`;
    
    authFetch(url)
        .then(res => res.json())
        .then(data => {
            const container = document.getElementById('historyList');
            if (!container) return;
            
            const records = data.records || [];
            if (records.length === 0) {
                container.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-secondary);">暂无记录</div>';
                updatePagination(data);
                return;
            }
            
            const typeIcons = {revenue:'arrow-up', expense:'arrow-down', return:'undo', purchase:'truck', inventory:'clipboard-list'};
            const typeNames = {revenue:'销售', expense:'支出', return:'退货', purchase:'进货', inventory:'盘点'};
            
            container.innerHTML = records.map(item => {
                const icon = typeIcons[item.type] || 'receipt';
                const typeName = typeNames[item.type] || item.type;
                const amount = item.type === 'return' || item.type === 'expense' ? -(item.total_amount || 0) : (item.total_amount || 0);
                const itemDesc = (item.items || []).map(i => `${i.name}${i.quantity > 1 ? ' x' + i.quantity : ''}`).join(', ') || typeName;
                
                return `
                    <div class="history-item">
                        <div class="history-icon ${item.type}">
                            <i class="fas fa-${icon}"></i>
                        </div>
                        <div class="history-info">
                            <div class="history-title">${itemDesc} <span style="font-size:11px;color:var(--text-secondary);">${typeName}</span></div>
                            <div class="history-meta">${item.store_name || ''} · ${item.created_at || ''} ${item.status === 'pending' ? '<span style="color:var(--warning-color);">待审核</span>' : item.status === 'rejected' ? '<span style="color:var(--danger-color);">已驳回</span>' : ''}</div>
                        </div>
                        <span class="history-amount ${amount > 0 ? 'positive' : 'negative'}">${amount > 0 ? '+' : ''}${formatCurrency(Math.abs(amount))}</span>
                    </div>
                `;
            }).join('');
            
            updatePagination(data);
        })
        .catch(err => console.error('加载历史记录失败:', err));
}

function updatePagination(data) {
    const pageInfo = document.querySelector('.page-info');
    const prevBtn = document.querySelector('.page-btn:first-child');
    const nextBtn = document.querySelector('.page-btn:last-child');
    
    if (pageInfo) pageInfo.textContent = `第 ${data.page || 1} 页 / 共 ${data.total_pages || 1} 页`;
    if (prevBtn) prevBtn.disabled = (data.page || 1) <= 1;
    if (nextBtn) nextBtn.disabled = (data.page || 1) >= (data.total_pages || 1);
}

// 翻页
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('page-btn')) {
        if (e.target.textContent.includes('上一页') && historyPage > 1) {
            historyPage--;
            loadHistoryData();
        } else if (e.target.textContent.includes('下一页')) {
            historyPage++;
            loadHistoryData();
        }
    }
});

// 语音录制
let mediaRecorder = null;
let audioChunks = [];

function initVoiceRecording() {
    const recordBtn = document.getElementById('recordBtn');
    if (!recordBtn) return;
    recordBtn.addEventListener('click', toggleRecording);
}

async function toggleRecording() {
    const recordBtn = document.getElementById('recordBtn');
    const statusEl = document.getElementById('recordStatus');
    
    if (!mediaRecorder || mediaRecorder.state === 'inactive') {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mimeType = MediaRecorder.isTypeSupported('audio/mp4') 
                ? 'audio/mp4' 
                : MediaRecorder.isTypeSupported('audio/webm;codecs=opus') 
                    ? 'audio/webm;codecs=opus' 
                    : 'audio/webm';
            mediaRecorder = new MediaRecorder(stream, { mimeType });
            audioChunks = [];
            
            mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
            mediaRecorder.onstop = processVoiceRecording;
            
            mediaRecorder.start();
            recordBtn.classList.add('recording');
            recordBtn.querySelector('span').textContent = '点击停止录音';
            statusEl.textContent = '正在录音...';
        } catch (err) {
            showNotification('无法访问麦克风，请检查权限设置', 'error');
        }
    } else {
        mediaRecorder.stop();
        recordBtn.classList.remove('recording');
        recordBtn.querySelector('span').textContent = '点击开始录音';
        statusEl.textContent = '正在识别...';
    }
}

function processVoiceRecording() {
    const mimeType = mediaRecorder.mimeType || 'audio/webm';
    const blob = new Blob(audioChunks, { type: mimeType });
    const statusEl = document.getElementById('recordStatus');
    statusEl.textContent = '正在识别语音...';
    
    const reader = new FileReader();
    reader.onloadend = function() {
        const base64Audio = reader.result.split(',')[1];
        
        authFetch(`${API_BASE}/api/voice/base64`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                audio_base64: base64Audio,
                audio_format: mimeType.includes('mp4') ? 'm4a' : mimeType.includes('ogg') ? 'ogg' : 'webm',
                store_id: currentStore
            })
        })
        .then(res => res.json())
        .then(data => {
            statusEl.textContent = '识别完成';
            if (data.success) {
                showRecognitionResult(data);
            } else {
                showNotification('❌ 识别失败: ' + (data.error || '请重试'), 'error');
                statusEl.textContent = '识别失败，请重试';
            }
        })
        .catch(err => {
            statusEl.textContent = '识别失败，请重试';
            showNotification('❌ 网络错误', 'error');
        });
    };
    reader.readAsDataURL(blob);
}

// 图片上传
function initImageUpload() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    
    if (!uploadArea || !fileInput) return;
    
    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', e => {
        e.preventDefault();
        uploadArea.style.borderColor = 'var(--primary-color)';
    });
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.style.borderColor = 'var(--border-color)';
    });
    uploadArea.addEventListener('drop', e => {
        e.preventDefault();
        uploadArea.style.borderColor = 'var(--border-color)';
        if (e.dataTransfer.files.length) {
            handleImageUpload(e.dataTransfer.files[0]);
        }
    });
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) {
            handleImageUpload(fileInput.files[0]);
        }
    });
}

function handleImageUpload(file) {
    const preview = document.getElementById('imagePreview');
    const fileName = file.name.toLowerCase();
    const isPdf = fileName.endsWith('.pdf');
    const isImage = /\.(jpg|jpeg|png|gif|bmp|webp)$/i.test(fileName);
    
    if (isImage) {
        preview.innerHTML = `<img src="${URL.createObjectURL(file)}" alt="预览">`;
    } else if (isPdf) {
        preview.innerHTML = `<div style="padding:40px;text-align:center;color:var(--text-secondary);"><div style="font-size:48px;">📄</div><p>${file.name}</p><p style="font-size:12px;">PDF文件将提取文字内容进行识别</p></div>`;
    } else {
        preview.innerHTML = `<div style="padding:40px;text-align:center;color:var(--text-secondary);"><div style="font-size:48px;">📎</div><p>${file.name}</p></div>`;
    }
    preview.classList.remove('hidden');
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('store_id', currentStore);
    
    showLoading();
    
    fetch(`${API_BASE}/api/upload`, {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(uploadResult => {
        if (!uploadResult.success) {
            hideLoading();
            showNotification('❌ 文件上传失败：' + (uploadResult.error || '未知错误'), 'error');
            return;
        }
        
        const apiUrl = isPdf ? `${API_BASE}/api/document` : `${API_BASE}/api/image`;
        return authFetch(apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                file_url: uploadResult.url,
                store_id: currentStore
            })
        });
    })
    .then(res => res ? res.json() : null)
    .then(data => {
        hideLoading();
        if (!data) return;
        if (data.success) {
            showRecognitionResult(data);
        } else {
            showNotification('❌ 识别失败: ' + (data.error || ''), 'error');
        }
    })
    .catch(err => {
        hideLoading();
        showNotification('❌ 识别失败，请重试', 'error');
    });
}

// 显示识别结果
let lastRecognizedData = null;

function showRecognitionResult(data) {
    const modal = document.getElementById('resultModal');
    const content = document.getElementById('resultContent');
    
    const extracted = data.extracted_data || {};
    const confidence = (extracted.confidence || data.confidence || 0.85) * 100;
    const isHighConfidence = confidence >= 80;
    const typeNames = {revenue:'销售收入', expense:'支出', return:'退货', purchase:'进货', inventory:'盘点'};
    
    lastRecognizedData = data;
    
    content.innerHTML = `
        <div class="result-field">
            <span class="field-label">识别置信度</span>
            <span class="field-value">${confidence.toFixed(0)}%</span>
        </div>
        <div class="confidence-bar">
            <div class="confidence-fill" style="width: ${confidence}%; background: ${isHighConfidence ? 'var(--success-color)' : 'var(--warning-color)'}"></div>
        </div>
        ${isHighConfidence ? '' : '<p style="color: var(--warning-color); margin-top: 12px; font-size: 14px;"><i class="fas fa-info-circle"></i> 置信度较低，请仔细核对以下信息</p>'}
        
        <div class="result-field" style="margin-top: 16px">
            <span class="field-label">交易类型</span>
            <span class="field-value">${typeNames[extracted.data_type] || extracted.data_type || '未知'}</span>
        </div>
        ${renderExtractedFields(extracted.extracted_fields || {})}
        ${data.recognized_text ? `<div class="result-field"><span class="field-label">原文</span><span class="field-value" style="font-size:12px;color:var(--text-secondary);">${data.recognized_text}</span></div>` : ''}
        
        <div class="modal-actions">
            <button class="btn-confirm" onclick="confirmSubmit()">
                <i class="fas fa-check"></i> 确认提交
            </button>
            <button class="btn-retry" onclick="closeModal()">
                <i class="fas fa-redo"></i> 重新录入
            </button>
        </div>
    `;
    
    modal.classList.add('show');
}

function renderExtractedFields(fields) {
    if (!fields || !fields.items || fields.items.length === 0) {
        return `
            <div class="result-field">
                <span class="field-label">金额</span>
                <span class="field-value">${formatCurrency(fields.total_amount || 0)}</span>
            </div>
        `;
    }
    
    return fields.items.map(item => `
        <div class="result-field">
            <span class="field-label">${item.name || '商品'}</span>
            <span class="field-value">${item.quantity || 1}件 × ${formatCurrency(item.price || item.unit_price || 0)}</span>
        </div>
    `).join('') + `
        <div class="result-field">
            <span class="field-label">合计</span>
            <span class="field-value" style="font-weight:600;color:var(--primary-color);">${formatCurrency(fields.total_amount || 0)}</span>
        </div>
    ` + (fields.payment_method ? `
        <div class="result-field">
            <span class="field-label">支付方式</span>
            <span class="field-value">${{wechat:'微信',alipay:'支付宝',cash:'现金',card:'银行卡',transfer:'转账'}[fields.payment_method] || fields.payment_method}</span>
        </div>
    ` : '');
}

function closeModal() {
    document.getElementById('resultModal').classList.remove('show');
    lastRecognizedData = null;
}

// 确认提交 - 真正保存记录
function confirmSubmit() {
    if (!lastRecognizedData) return;
    
    const extracted = lastRecognizedData.extracted_data || {};
    const fields = extracted.extracted_fields || {};
    
    // 获取门店名称
    const storeSelect = document.getElementById('storeSelect');
    const storeName = storeSelect ? storeSelect.selectedOptions[0]?.text : '';
    
    const record = {
        org_id: 'org_default',
        store_id: currentStore === 'all' ? 'store_001' : currentStore,
        store_name: storeName || '默认门店',
        type: extracted.data_type || 'revenue',
        category: (fields.items && fields.items[0] && fields.items[0].category) || '',
        items: fields.items || [],
        total_amount: fields.total_amount || 0,
        payment_method: fields.payment_method || '',
        confidence: extracted.confidence || lastRecognizedData.confidence || 0.8,
        status: (extracted.confidence || 0.8) >= 0.9 ? 'approved' : 'pending',
        operator: currentUser ? currentUser.name : ''
    };
    
    authFetch(`${API_BASE}/api/records`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(record)
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            showNotification('✅ 提交成功！' + (record.status === 'pending' ? '需等待审核' : ''), 'success');
            closeModal();
            // 刷新看板
            if (currentPage === 'dashboard') loadDashboardData();
        } else {
            showNotification('❌ 提交失败: ' + (data.message || ''), 'error');
        }
    })
    .catch(err => {
        showNotification('❌ 提交失败，请重试', 'error');
    });
}

// 生成报告
function generateReport(type) {
    showLoading();
    
    authFetch(`${API_BASE}/api/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, period: currentPeriod, store_id: currentStore })
    })
    .then(res => res.json())
    .then(data => {
        hideLoading();
        if (data.url) {
            window.open(data.url, '_blank');
        } else if (data.report_url) {
            window.open(data.report_url, '_blank');
        } else {
            showNotification('报告生成成功', 'success');
        }
    })
    .catch(err => {
        hideLoading();
        showNotification('报告生成中，请稍后重试', 'info');
    });
}

// 导出报告
function exportReport(format = 'pdf') {
    const formatNames = { pdf: 'PDF', docx: 'Word文档', xlsx: 'Excel表格' };
    const formatName = formatNames[format] || format.toUpperCase();
    
    showLoading();
    
    const summaryData = window.dashboardSummary || {};
    const storeStats = window.dashboardStoreStats || {};
    const categoryStats = window.dashboardCategoryStats || {};
    const alerts = window.dashboardAlerts || [];
    const productAnalysis = window.dashboardProductAnalysis || {};
    
    authFetch(`${API_BASE}/api/report/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            report_type: format,
            period: currentPeriod,
            start_date: summaryData.start_date || '',
            end_date: summaryData.end_date || '',
            summary: summaryData,
            store_stats: storeStats,
            category_stats: categoryStats,
            anomaly_alerts: alerts,
            product_analysis: productAnalysis,
            org_name: '服装连锁'
        })
    })
    .then(res => res.json())
    .then(data => {
        hideLoading();
        if (data.success && data.report_url) {
            const link = document.createElement('a');
            link.href = data.report_url;
            link.download = `经营报告_${currentPeriod}.${format}`;
            link.target = '_blank';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            showNotification(`✅ ${formatName}报告已生成，开始下载...`, 'success');
        } else {
            showNotification(`❌ ${formatName}报告生成失败: ${data.message || data.error || '未知错误'}`, 'error');
        }
    })
    .catch(err => {
        hideLoading();
        showNotification(`❌ ${formatName}报告生成失败，请稍后重试`, 'error');
    });
}

// 发送报告到飞书
function sendReportToFeishu() {
    const summaryData = window.dashboardSummary || {};
    const topProducts = window.dashboardProductAnalysis?.top_sellers || [];
    
    authFetch(`${API_BASE}/api/notify/feishu`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            type: 'daily_report',
            store_name: currentStore === 'all' ? '全部门店' : document.getElementById('storeSelect')?.selectedOptions[0]?.text || '',
            summary: summaryData,
            top_products: topProducts.slice(0, 3)
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            showNotification('✅ 报告已发送到飞书群', 'success');
        } else {
            showNotification('❌ 发送失败: ' + (data.error || '未配置飞书机器人'), 'error');
        }
    })
    .catch(err => showNotification('❌ 发送失败，请检查网络', 'error'));
}

// 发送异常预警到飞书
function sendAlertToFeishu() {
    const alerts = window.dashboardAlerts || [];
    const storeName = currentStore === 'all' ? '全部门店' : document.getElementById('storeSelect')?.selectedOptions[0]?.text || '';
    
    if (alerts.length === 0) {
        showNotification('当前无异常预警', 'info');
        return;
    }
    
    authFetch(`${API_BASE}/api/notify/feishu`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            type: 'anomaly',
            store_name: storeName,
            alerts: alerts
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            showNotification('✅ 预警已发送到飞书群', 'success');
        } else {
            showNotification('❌ 发送失败: ' + (data.error || '未配置飞书机器人'), 'error');
        }
    })
    .catch(err => showNotification('❌ 发送失败，请检查网络', 'error'));
}

// 显示通知
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <span class="notification-message">${message}</span>
        <button class="notification-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    notification.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        padding: 16px 24px;
        background: ${type === 'success' ? '#4caf50' : type === 'error' ? '#f44336' : '#2196f3'};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 9999;
        display: flex;
        align-items: center;
        gap: 12px;
        animation: slideIn 0.3s ease-out;
        max-width: 400px;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-in';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// CSS动画
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
    .notification-close {
        background: none;
        border: none;
        color: white;
        font-size: 20px;
        cursor: pointer;
        padding: 0 0 0 8px;
    }
`;
document.head.appendChild(style);

// 加载状态
function showLoading() {
    document.getElementById('loadingOverlay')?.classList.add('show');
}

function hideLoading() {
    document.getElementById('loadingOverlay')?.classList.remove('show');
}

// 刷新按钮
document.getElementById('refreshBtn')?.addEventListener('click', () => {
    loadDashboardData();
});

// 门店选择变更
document.getElementById('storeSelect')?.addEventListener('change', (e) => {
    currentStore = e.target.value;
    loadDashboardData();
});
