// ==================== 全局状态 ====================
let currentPage = 'dashboard';
let currentPeriod = 'month';
let isRecording = false;
let currentStoreId = 'all';

// ==================== 初始化 ====================
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initDateFilter();
    initStoreSelector();
    loadDashboardData();
    loadRecords();
});

// ==================== 导航切换 ====================
function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const page = item.dataset.page;
            switchPage(page);
        });
    });
}

function switchPage(page) {
    // 更新导航状态
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`[data-page="${page}"]`).classList.add('active');
    
    // 更新页面显示
    document.querySelectorAll('.page').forEach(p => {
        p.classList.remove('active');
    });
    document.getElementById(`${page}Page`).classList.add('active');
    
    // 更新标题
    const titles = {
        dashboard: { title: '数据看板', subtitle: '实时查看门店经营数据' },
        voice: { title: '语音报账', subtitle: '语音识别自动录入交易信息' },
        camera: { title: '拍照录入', subtitle: '拍摄单据自动识别录入' },
        records: { title: '历史记录', subtitle: '查看所有交易记录' },
        reports: { title: '报告中心', subtitle: '生成经营分析报告' }
    };
    
    document.getElementById('pageTitle').textContent = titles[page].title;
    document.getElementById('pageSubtitle').textContent = titles[page].subtitle;
    
    currentPage = page;
    
    // 加载页面数据
    if (page === 'dashboard') {
        loadDashboardData();
    } else if (page === 'records') {
        loadRecords();
    }
}

// ==================== 日期筛选 ====================
function initDateFilter() {
    const dateBtns = document.querySelectorAll('.date-btn');
    dateBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            dateBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentPeriod = btn.dataset.period;
            loadDashboardData();
        });
    });
}

// ==================== 门店选择 ====================
function initStoreSelector() {
    document.getElementById('storeSelect').addEventListener('change', (e) => {
        currentStoreId = e.target.value;
        loadDashboardData();
    });
}

// ==================== 数据加载 ====================
async function loadDashboardData() {
    showLoading();
    
    try {
        const response = await fetch('/api/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                input_type: 'query',
                query_type: currentPeriod,
                store_id: currentStoreId === 'all' ? null : currentStoreId
            })
        });
        
        const result = await response.json();
        updateDashboard(result);
        hideLoading();
    } catch (error) {
        console.error('加载数据失败:', error);
        hideLoading();
        showError('加载数据失败，请重试');
    }
}

function updateDashboard(data) {
    const dashboardData = data.dashboard_data || {};
    const summary = dashboardData.summary || {};
    
    // 更新统计卡片
    document.getElementById('totalRevenue').textContent = formatCurrency(summary.total_revenue || 0);
    document.getElementById('totalCost').textContent = formatCurrency(summary.total_cost || 0);
    document.getElementById('grossProfit').textContent = formatCurrency(summary.gross_profit || 0);
    document.getElementById('grossMargin').textContent = (summary.gross_margin || 0) + '%';
    document.getElementById('transactionCount').textContent = summary.transaction_count || 0;
    
    // 更新预警
    updateAlerts(data.anomaly_alerts || []);
}

function updateAlerts(alerts) {
    const container = document.getElementById('alertContainer');
    container.innerHTML = '';
    
    alerts.forEach(alert => {
        const alertEl = document.createElement('div');
        alertEl.className = `alert ${alert.level === 'critical' ? 'danger' : 'warning'}`;
        alertEl.innerHTML = `
            <i class="fas fa-exclamation-triangle"></i>
            <div class="alert-content">
                <div class="alert-title">${getAlertTitle(alert.type)}</div>
                <div class="alert-message">${alert.message}</div>
            </div>
        `;
        container.appendChild(alertEl);
    });
}

function getAlertTitle(type) {
    const titles = {
        negative_margin: '毛利率预警',
        high_expense: '支出异常',
        low_revenue: '营收下滑',
        inventory_warning: '库存预警'
    };
    return titles[type] || '经营预警';
}

// ==================== 刷新数据 ====================
function refreshData() {
    loadDashboardData();
    showSuccess('数据已刷新');
}

// ==================== 语音报账 ====================
function toggleVoiceRecording() {
    const btn = document.getElementById('voiceBtn');
    const waveContainer = document.getElementById('waveContainer');
    const statusText = document.getElementById('voiceStatusText');
    
    if (!isRecording) {
        // 开始录音
        isRecording = true;
        btn.classList.add('recording');
        btn.querySelector('span').textContent = '正在录音...';
        waveContainer.classList.remove('hidden');
        statusText.textContent = '请说出您的交易信息';
        
        // 模拟录音（实际应用中调用真实ASR）
        simulateVoiceRecording();
    } else {
        // 停止录音
        stopRecording();
    }
}

function simulateVoiceRecording() {
    // 5秒后自动停止
    setTimeout(() => {
        if (isRecording) {
            stopRecording();
            // 模拟识别结果
            showVoiceResult({
                text: '今天卖出一件红色连衣裙，售价299元，成本120元',
                confidence: 0.92,
                data: {
                    type: '销售',
                    product: '红色连衣裙',
                    quantity: 1,
                    price: 299,
                    cost: 120,
                    profit: 179
                }
            });
        }
    }, 3000);
}

function stopRecording() {
    isRecording = false;
    const btn = document.getElementById('voiceBtn');
    const waveContainer = document.getElementById('waveContainer');
    
    btn.classList.remove('recording');
    btn.querySelector('span').textContent = '点击开始录音';
    waveContainer.classList.add('hidden');
    document.getElementById('voiceStatusText').textContent = '准备就绪';
}

function showVoiceResult(result) {
    const resultPanel = document.getElementById('voiceResult');
    const resultBody = document.getElementById('voiceResultBody');
    
    document.getElementById('voiceConfidence').textContent = `置信度: ${(result.confidence * 100).toFixed(0)}%`;
    
    resultBody.innerHTML = `
        <div class="result-item">
            <span class="result-label">识别文本</span>
            <span class="result-value">${result.text}</span>
        </div>
        <div class="result-item">
            <span class="result-label">交易类型</span>
            <span class="result-value">${result.data.type}</span>
        </div>
        <div class="result-item">
            <span class="result-label">商品名称</span>
            <span class="result-value">${result.data.product}</span>
        </div>
        <div class="result-item">
            <span class="result-label">销售数量</span>
            <span class="result-value">${result.data.quantity}件</span>
        </div>
        <div class="result-item">
            <span class="result-label">售价</span>
            <span class="result-value">¥${result.data.price}</span>
        </div>
        <div class="result-item">
            <span class="result-label">成本</span>
            <span class="result-value">¥${result.data.cost}</span>
        </div>
        <div class="result-item">
            <span class="result-label">利润</span>
            <span class="result-value" style="color: #22c55e">¥${result.data.profit}</span>
        </div>
    `;
    
    resultPanel.classList.remove('hidden');
}

function fillVoiceExample(text) {
    showLoading();
    setTimeout(() => {
        hideLoading();
        showVoiceResult({
            text: text,
            confidence: 0.95,
            data: {
                type: '销售',
                product: '红色连衣裙',
                quantity: 1,
                price: 299,
                cost: 120,
                profit: 179
            }
        });
    }, 1000);
}

function retryVoice() {
    document.getElementById('voiceResult').classList.add('hidden');
}

async function confirmVoiceRecord() {
    showLoading();
    
    try {
        const response = await fetch('/api/voice', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                input_type: 'voice',
                store_id: currentStoreId
            })
        });
        
        const result = await response.json();
        hideLoading();
        showSuccess('账目已成功录入');
        document.getElementById('voiceResult').classList.add('hidden');
    } catch (error) {
        hideLoading();
        showError('录入失败，请重试');
    }
}

// ==================== 拍照录入 ====================
function handleImageUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (e) => {
        document.getElementById('previewImg').src = e.target.result;
        document.getElementById('imagePreview').classList.remove('hidden');
        document.getElementById('uploadArea').style.display = 'none';
        
        // 模拟OCR识别
        simulateOcrRecognition();
    };
    reader.readAsDataURL(file);
}

function simulateOcrRecognition() {
    showLoading();
    
    setTimeout(() => {
        hideLoading();
        showOcrResult({
            confidence: 0.88,
            data: {
                document_type: '销售单',
                store: '中山路店',
                date: new Date().toLocaleDateString(),
                items: [
                    { name: '蓝色牛仔裤', quantity: 2, price: 199, amount: 398 }
                ],
                total: 398
            }
        });
    }, 2000);
}

function showOcrResult(result) {
    const resultPanel = document.getElementById('ocrResult');
    const resultBody = document.getElementById('ocrResultBody');
    
    document.getElementById('ocrConfidence').textContent = `置信度: ${(result.confidence * 100).toFixed(0)}%`;
    
    resultBody.innerHTML = `
        <div class="result-item">
            <span class="result-label">单据类型</span>
            <span class="result-value">${result.data.document_type}</span>
        </div>
        <div class="result-item">
            <span class="result-label">门店</span>
            <span class="result-value">${result.data.store}</span>
        </div>
        <div class="result-item">
            <span class="result-label">日期</span>
            <span class="result-value">${result.data.date}</span>
        </div>
        <div class="result-item">
            <span class="result-label">商品</span>
            <span class="result-value">${result.data.items[0].name}</span>
        </div>
        <div class="result-item">
            <span class="result-label">数量</span>
            <span class="result-value">${result.data.items[0].quantity}件</span>
        </div>
        <div class="result-item">
            <span class="result-label">单价</span>
            <span class="result-value">¥${result.data.items[0].price}</span>
        </div>
        <div class="result-item">
            <span class="result-label">总金额</span>
            <span class="result-value" style="color: #22c55e">¥${result.data.total}</span>
        </div>
    `;
    
    resultPanel.classList.remove('hidden');
}

function removeImage() {
    document.getElementById('imageInput').value = '';
    document.getElementById('imagePreview').classList.add('hidden');
    document.getElementById('uploadArea').style.display = 'block';
    document.getElementById('ocrResult').classList.add('hidden');
}

function retryOcr() {
    removeImage();
}

async function confirmOcrRecord() {
    showLoading();
    
    try {
        const response = await fetch('/api/image', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                input_type: 'image',
                store_id: currentStoreId
            })
        });
        
        const result = await response.json();
        hideLoading();
        showSuccess('账目已成功录入');
        removeImage();
    } catch (error) {
        hideLoading();
        showError('录入失败，请重试');
    }
}

// ==================== 历史记录 ====================
function loadRecords() {
    const tbody = document.getElementById('recordsTableBody');
    
    // 模拟数据
    const records = [
        { time: '2026-05-24 14:30', type: 'sale', product: '红色连衣裙', store: '中山路店', amount: 299 },
        { time: '2026-05-24 11:20', type: 'sale', product: '蓝色牛仔裤 x2', store: '人民广场店', amount: 398 },
        { time: '2026-05-24 09:15', type: 'purchase', product: '新款T恤 x50', store: '中山路店', amount: -2500 },
        { time: '2026-05-23 16:45', type: 'expense', product: '门店租金', store: '中山路店', amount: -5000 },
        { time: '2026-05-23 14:10', type: 'sale', product: '运动鞋', store: '万达广场店', amount: 459 },
    ];
    
    tbody.innerHTML = records.map(record => `
        <tr>
            <td>${record.time}</td>
            <td><span class="type-badge ${record.type}">${getTypeLabel(record.type)}</span></td>
            <td>${record.product}</td>
            <td>${record.store}</td>
            <td class="amount ${record.amount > 0 ? 'positive' : 'negative'}">${formatCurrency(record.amount)}</td>
            <td><button class="action-btn" onclick="viewRecordDetail('${record.time}')">查看</button></td>
        </tr>
    `).join('');
}

function getTypeLabel(type) {
    const labels = {
        sale: '销售',
        purchase: '进货',
        expense: '支出'
    };
    return labels[type] || type;
}

function viewRecordDetail(time) {
    showSuccess('查看详情: ' + time);
}

// ==================== 报告生成 ====================
async function generateReport(period) {
    showLoading();
    
    try {
        const response = await fetch('/api/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                input_type: 'query',
                query_type: period
            })
        });
        
        const result = await response.json();
        hideLoading();
        
        // 添加到历史报告列表
        addReportToList(period, result.report_url);
        showSuccess(`${getPeriodLabel(period)}报告已生成`);
    } catch (error) {
        hideLoading();
        showError('报告生成失败，请重试');
    }
}

function addReportToList(period, url) {
    const list = document.getElementById('reportsList');
    const emptyState = list.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }
    
    const reportItem = document.createElement('div');
    reportItem.className = 'report-list-item';
    reportItem.style.cssText = 'display: flex; justify-content: space-between; align-items: center; padding: 16px 24px; border-bottom: 1px solid var(--border-color);';
    reportItem.innerHTML = `
        <div>
            <div style="font-weight: 500; margin-bottom: 4px;">${getPeriodLabel(period)}报告</div>
            <div style="font-size: 13px; color: var(--text-secondary);">${new Date().toLocaleString()}</div>
        </div>
        <button class="btn-secondary" onclick="downloadReport('${url}')">
            <i class="fas fa-download"></i> 下载
        </button>
    `;
    
    list.insertBefore(reportItem, list.firstChild);
}

function getPeriodLabel(period) {
    const labels = {
        day: '日报',
        week: '周报',
        month: '月报',
        year: '年报'
    };
    return labels[period] || period;
}

function downloadReport(url) {
    window.open(url, '_blank');
}

// ==================== 工具函数 ====================
function formatCurrency(value) {
    const absValue = Math.abs(value);
    if (absValue >= 10000) {
        return '¥' + (value / 10000).toFixed(1) + '万';
    }
    return '¥' + value.toFixed(0);
}

function showLoading() {
    document.getElementById('loadingOverlay').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.add('hidden');
}

function showSuccess(message) {
    const toast = document.getElementById('successToast');
    document.getElementById('successMessage').textContent = message;
    toast.classList.remove('hidden');
    
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3000);
}

function showError(message) {
    const toast = document.getElementById('errorToast');
    document.getElementById('errorMessage').textContent = message;
    toast.classList.remove('hidden');
    
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3000);
}
