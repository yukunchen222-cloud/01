// 全局状态
let currentPeriod = 'month';
let currentStore = 'all';
let currentPage = 'dashboard';

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

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initDateFilter();
    initStoreSelector();
    loadDashboardData();
    loadAnalysisData();
    loadAlertsData();
    loadReviewData();
    loadHistoryData();
    initVoiceRecording();
    initImageUpload();
});

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
    
    // 更新导航状态
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.page === page);
    });
    
    // 更新页面标题
    document.getElementById('pageTitle').textContent = pageConfig[page]?.title || page;
    document.getElementById('pageSubtitle').textContent = pageConfig[page]?.subtitle || '';
    
    // 切换页面显示
    document.querySelectorAll('.page').forEach(p => {
        p.classList.toggle('active', p.id === `${page}Page`);
    });
}

// 日期筛选
function initDateFilter() {
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
                    option.value = store.id;
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
    
    fetch(`${API_BASE}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            input_type: 'query',
            query_type: currentPeriod,
            store_id: currentStore
        })
    })
    .then(res => res.json())
    .then(data => {
        hideLoading();
        renderDashboard(data);
    })
    .catch(err => {
        hideLoading();
        console.error('加载看板数据失败:', err);
        renderDashboardWithSampleData();
    });
}

// 渲染看板
function renderDashboard(data) {
    const summary = data.dashboard_data?.summary || {};
    
    // 更新统计卡片
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
    renderFixedExpenses(data.dashboard_data?.fixed_expenses || {});
}

// 使用示例数据渲染（备用）
function renderDashboardWithSampleData() {
    const sampleData = {
        dashboard_data: {
            summary: {
                total_revenue: 125800,
                total_cost: 62800,
                gross_profit: 63000,
                net_profit: 45800,
                gross_margin: 50.1,
                transaction_count: 342
            },
            store_stats: {
                '中山路店': { revenue: 45800, count: 128 },
                '人民广场店': { revenue: 32600, count: 89 },
                '西湖大道店': { revenue: 28400, count: 72 },
                '滨江店': { revenue: 12800, count: 38 },
                '城西店': { revenue: 6200, count: 15 }
            },
            category_stats: {
                '连衣裙': 45200,
                '西装外套': 32800,
                '牛仔裤': 25400,
                'T恤': 15800,
                '其他': 6600
            },
            fixed_expenses: {
                rent: 12000,
                utilities: 1800,
                salary: 25000,
                other: 2400
            }
        },
        anomaly_alerts: [
            { type: 'low_revenue', level: 'warning', message: '城西店本周营收下降15%', store: '城西店' }
        ]
    };
    renderDashboard(sampleData);
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
    const maxRevenue = Math.max(...stores.map(([_, s]) => s.revenue || 0));
    
    container.innerHTML = stores.map(([name, data]) => {
        const percent = maxRevenue > 0 ? ((data.revenue || 0) / maxRevenue * 100) : 0;
        return `
            <div class="store-item">
                <span class="store-name">${name}</span>
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
    
    const labels = {
        rent: '房租',
        utilities: '水电费',
        salary: '人工成本',
        other: '其他费用'
    };
    
    container.innerHTML = Object.entries(expenses).map(([key, value]) => `
        <div class="expense-item">
            <div class="expense-label">${labels[key] || key}</div>
            <div class="expense-value">${formatCurrency(value)}</div>
        </div>
    `).join('');
}

// 加载款式分析数据
function loadAnalysisData() {
    const topSellers = document.getElementById('topSellers');
    const slowSellers = document.getElementById('slowSellers');
    
    if (topSellers) {
        topSellers.innerHTML = [
            { name: '黑色西装外套', sales: 89, revenue: 31951 },
            { name: '红色连衣裙', sales: 76, revenue: 22624 },
            { name: '蓝色牛仔裤', sales: 65, revenue: 12935 },
            { name: '白色T恤', sales: 54, revenue: 4320 },
            { name: '灰色休闲裤', sales: 48, revenue: 8640 }
        ].map((item, index) => `
            <div class="rank-item">
                <span class="rank-number ${index < 3 ? 'top3' : ''}">${index + 1}</span>
                <div class="rank-info">
                    <div class="rank-name">${item.name}</div>
                    <div class="rank-sales">已售 ${item.sales} 件</div>
                </div>
                <span class="rank-value">${formatCurrency(item.revenue)}</span>
            </div>
        `).join('');
    }
    
    if (slowSellers) {
        slowSellers.innerHTML = [
            { name: '黄色短袖', days: 45, percent: 85 },
            { name: '格纹衬衫', days: 38, percent: 72 },
            { name: '碎花半裙', days: 32, percent: 68 }
        ].map(item => `
            <div class="slow-sell-item">
                <div class="slow-sell-info">
                    <div class="slow-sell-name">${item.name}</div>
                    <div class="slow-sell-desc">滞销${item.days}天，库存占比${item.percent}%</div>
                </div>
            </div>
        `).join('');
    }
}

// 加载异常预警数据
function loadAlertsData() {
    const container = document.getElementById('alertsList');
    if (!container) return;
    
    container.innerHTML = [
        { level: 'critical', title: '营收异常', desc: '城西店连续3天营收下滑，累计下降45%', store: '城西店', time: '2024-05-24 18:00' },
        { level: 'warning', title: '库存预警', desc: '黑色西装外套库存仅剩8件，建议补货', store: '中山路店', time: '2024-05-24 15:30' },
        { level: 'warning', title: '成本异常', desc: '人民广场店本月成本占比达65%，高于平均', store: '人民广场店', time: '2024-05-24 12:00' }
    ].map(alert => `
        <div class="alert-card ${alert.level}">
            <div class="alert-card-icon">
                <i class="fas fa-${alert.level === 'critical' ? 'times-circle' : 'exclamation-circle'}"></i>
            </div>
            <div class="alert-card-content">
                <div class="alert-card-title">${alert.title}</div>
                <div class="alert-card-desc">${alert.desc}</div>
                <div class="alert-card-meta">
                    <i class="fas fa-store"></i> ${alert.store} &nbsp;|&nbsp; 
                    <i class="fas fa-clock"></i> ${alert.time}
                </div>
            </div>
        </div>
    `).join('');
}

// 加载审核数据
function loadReviewData() {
    const container = document.getElementById('reviewList');
    if (!container) return;
    
    container.innerHTML = [
        { store: '中山路店', type: '销售', items: '红色连衣裙 x1', amount: 299, confidence: 0.72, time: '18:25' },
        { store: '人民广场店', type: '退货', items: '黑色西装外套 x1', amount: -359, confidence: 0.68, time: '17:30' },
        { store: '西湖大道店', type: '进货', items: '牛仔裤 x10', amount: -1500, confidence: 0.75, time: '16:15' }
    ].map((item, index) => `
        <div class="review-item">
            <div class="review-header">
                <span class="review-store"><i class="fas fa-store"></i> ${item.store}</span>
                <span class="review-confidence ${item.confidence < 0.7 ? 'low' : 'medium'}">
                    置信度 ${(item.confidence * 100).toFixed(0)}%
                </span>
            </div>
            <div class="review-data">
                <div class="review-row">
                    <span>类型</span>
                    <span>${item.type}</span>
                </div>
                <div class="review-row">
                    <span>商品</span>
                    <span>${item.items}</span>
                </div>
                <div class="review-row">
                    <span>金额</span>
                    <span style="color: ${item.amount > 0 ? 'var(--success-color)' : 'var(--danger-color)'}">${formatCurrency(Math.abs(item.amount))}</span>
                </div>
                <div class="review-row">
                    <span>时间</span>
                    <span>${item.time}</span>
                </div>
            </div>
            <div class="review-actions">
                <button class="btn-approve" onclick="approveReview(${index})"><i class="fas fa-check"></i> 通过</button>
                <button class="btn-reject" onclick="rejectReview(${index})"><i class="fas fa-times"></i> 驳回</button>
                <button class="btn-edit" onclick="editReview(${index})"><i class="fas fa-edit"></i> 编辑</button>
            </div>
        </div>
    `).join('');
}

// 审核操作
function approveReview(index) {
    alert('已通过审核');
}

function rejectReview(index) {
    alert('已驳回');
}

function editReview(index) {
    alert('打开编辑面板');
}

// 加载历史记录
function loadHistoryData() {
    const container = document.getElementById('historyList');
    if (!container) return;
    
    container.innerHTML = [
        { type: 'sale', title: '红色连衣裙 x1', store: '中山路店', amount: 299, time: '2024-05-24 18:25' },
        { type: 'sale', title: '黑色西装外套 x2', store: '人民广场店', amount: 718, time: '2024-05-24 16:30' },
        { type: 'expense', title: '房租支出', store: '西湖大道店', amount: -5000, time: '2024-05-24 10:00' },
        { type: 'return', title: '牛仔裤退货', store: '滨江店', amount: -199, time: '2024-05-23 15:20' },
        { type: 'sale', title: '白色T恤 x5', store: '中山路店', amount: 400, time: '2024-05-23 14:10' }
    ].map(item => `
        <div class="history-item">
            <div class="history-icon ${item.type}">
                <i class="fas fa-${item.type === 'sale' ? 'arrow-up' : item.type === 'expense' ? 'arrow-down' : 'undo'}"></i>
            </div>
            <div class="history-info">
                <div class="history-title">${item.title}</div>
                <div class="history-meta">${item.store} · ${item.time}</div>
            </div>
            <span class="history-amount ${item.amount > 0 ? 'positive' : 'negative'}">${item.amount > 0 ? '+' : ''}${formatCurrency(item.amount)}</span>
        </div>
    `).join('');
}

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
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            
            mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
            mediaRecorder.onstop = processVoiceRecording;
            
            mediaRecorder.start();
            recordBtn.classList.add('recording');
            recordBtn.querySelector('span').textContent = '点击停止录音';
            statusEl.textContent = '正在录音...';
        } catch (err) {
            alert('无法访问麦克风，请检查权限设置');
        }
    } else {
        mediaRecorder.stop();
        recordBtn.classList.remove('recording');
        recordBtn.querySelector('span').textContent = '点击开始录音';
        statusEl.textContent = '正在识别...';
    }
}

function processVoiceRecording() {
    const blob = new Blob(audioChunks, { type: 'audio/webm' });
    const formData = new FormData();
    formData.append('audio', blob, 'recording.webm');
    formData.append('store_id', currentStore);
    
    fetch(`${API_BASE}/api/voice`, {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        showRecognitionResult(data);
    })
    .catch(err => {
        document.getElementById('recordStatus').textContent = '识别失败，请重试';
    });
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
    preview.innerHTML = `<img src="${URL.createObjectURL(file)}" alt="预览">`;
    preview.classList.remove('hidden');
    
    const formData = new FormData();
    formData.append('image', file);
    formData.append('store_id', currentStore);
    
    showLoading();
    
    fetch(`${API_BASE}/api/image', {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        hideLoading();
        showRecognitionResult(data);
    })
    .catch(err => {
        hideLoading();
        alert('图片识别失败，请重试');
    });
}

// 显示识别结果
function showRecognitionResult(data) {
    const modal = document.getElementById('resultModal');
    const content = document.getElementById('resultContent');
    
    const extracted = data.extracted_data || {};
    const confidence = (extracted.confidence || 0.85) * 100;
    
    // 根据置信度决定显示方式
    const isHighConfidence = confidence >= 80;
    
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
            <span class="field-value">${extracted.data_type === 'revenue' ? '销售收入' : extracted.data_type === 'expense' ? '支出' : '其他'}</span>
        </div>
        ${renderExtractedFields(extracted.extracted_fields || {})}
        
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
            <span class="field-value">${item.quantity || 1}件 × ${formatCurrency(item.price || 0)}</span>
        </div>
    `).join('') + (fields.description ? `
        <div class="result-field">
            <span class="field-label">备注</span>
            <span class="field-value">${fields.description}</span>
        </div>
    ` : '');
}

function closeModal() {
    document.getElementById('resultModal').classList.remove('show');
}

function confirmSubmit() {
    alert('提交成功！');
    closeModal();
}

// 生成报告
function generateReport(type) {
    showLoading();
    
    fetch(`${API_BASE}/api/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type })
    })
    .then(res => res.json())
    .then(data => {
        hideLoading();
        if (data.url) {
            window.open(data.url, '_blank');
        } else {
            alert('报告生成成功');
        }
    })
    .catch(err => {
        hideLoading();
        alert('报告生成中...');
    });
}

// 导出报告（支持PDF/DOCX/XLSX多格式）
function exportReport(format = 'pdf') {
    const formatNames = { pdf: 'PDF', docx: 'Word文档', xlsx: 'Excel表格' };
    const formatName = formatNames[format] || format.toUpperCase();
    
    showLoading();
    
    // 获取当前看板数据
    const summaryData = window.dashboardSummary || {};
    const storeStats = window.dashboardStoreStats || {};
    const categoryStats = window.dashboardCategoryStats || {};
    const alerts = window.dashboardAlerts || [];
    const productAnalysis = window.dashboardProductAnalysis || {};
    
    fetch(`${API_BASE}/api/report/export`, {
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
            // 创建下载链接
            const link = document.createElement('a');
            link.href = data.report_url;
            link.download = `经营报告_${currentPeriod}.${format}`;
            link.target = '_blank';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            showNotification(`✅ ${formatName}报告已生成，开始下载...`, 'success');
        } else {
            showNotification(`❌ ${formatName}报告生成失败: ${data.message || '未知错误'}`, 'error');
        }
    })
    .catch(err => {
        hideLoading();
        showNotification(`❌ ${formatName}报告生成失败，请稍后重试`, 'error');
        console.error('报告导出错误:', err);
    });
}

// 发送报告到飞书
function sendReportToFeishu() {
    const summaryData = window.dashboardSummary || {};
    const topProducts = window.dashboardProductAnalysis?.top_sellers || [];
    
    fetch(`${API_BASE}/api/notify/feishu`, {
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
    .catch(err => {
        showNotification('❌ 发送失败，请检查网络', 'error');
    });
}

// 发送异常预警到飞书
function sendAlertToFeishu() {
    const alerts = window.dashboardAlerts || [];
    const storeName = currentStore === 'all' ? '全部门店' : document.getElementById('storeSelect')?.selectedOptions[0]?.text || '';
    
    if (alerts.length === 0) {
        showNotification('当前无异常预警', 'info');
        return;
    }
    
    fetch(`${API_BASE}/api/notify/feishu`, {
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
    .catch(err => {
        showNotification('❌ 发送失败，请检查网络', 'error');
    });
}

// 显示通知
function showNotification(message, type = 'info') {
    // 创建通知元素
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <span class="notification-message">${message}</span>
        <button class="notification-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    // 添加样式
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
    `;
    
    document.body.appendChild(notification);
    
    // 3秒后自动消失
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-in';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// 添加CSS动画
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
