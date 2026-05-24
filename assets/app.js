// ==================== 全局状态 ====================
let currentStoreId = 'all';
let currentPeriod = 'month';
let currentPage = 'dashboard';
let uploadedImageUrl = null;
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

// ==================== API 基础路径 ====================
const API_BASE = window.location.origin;

// ==================== 初始化 ====================
document.addEventListener('DOMContentLoaded', () => {
    console.log('页面初始化...');
    initNavigation();
    initDashboard();
    initVoiceRecord();
    initImageUpload();
    initStoreSelector();
    initDateFilter();
    initRefreshButton();
    loadStores();
});

// ==================== 导航功能 ====================
function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const page = item.dataset.page;
            if (page) {
                switchPage(page);
            }
        });
    });
}

function switchPage(page) {
    currentPage = page;
    
    // 更新导航状态
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.page === page) {
            item.classList.add('active');
        }
    });
    
    // 切换页面内容
    document.querySelectorAll('.page').forEach(content => {
        content.classList.remove('active');
    });
    
    const targetPage = document.getElementById(`${page}Page`);
    if (targetPage) {
        targetPage.classList.add('active');
    }
    
    // 更新页面标题
    const titles = {
        'dashboard': { title: '数据看板', subtitle: '实时查看门店经营数据' },
        'voice': { title: '语音报账', subtitle: '通过语音快速录入交易信息' },
        'camera': { title: '拍照录入', subtitle: '上传单据图片自动识别' },
        'history': { title: '历史记录', subtitle: '查看所有交易记录' },
        'reports': { title: '报告中心', subtitle: '生成经营分析报告' }
    };
    
    const pageInfo = titles[page] || { title: '服装连锁记账助手', subtitle: '' };
    const pageTitleEl = document.getElementById('pageTitle');
    const pageSubtitleEl = document.getElementById('pageSubtitle');
    if (pageTitleEl) pageTitleEl.textContent = pageInfo.title;
    if (pageSubtitleEl) pageSubtitleEl.textContent = pageInfo.subtitle;
    
    // 页面特定初始化
    if (page === 'dashboard') {
        loadDashboardData();
    } else if (page === 'history') {
        loadHistoryRecords();
    }
}

// ==================== 门店选择器 ====================
function initStoreSelector() {
    const storeSelect = document.getElementById('storeSelect');
    if (storeSelect) {
        storeSelect.addEventListener('change', (e) => {
            currentStoreId = e.target.value;
            console.log('选择门店:', currentStoreId);
            // 如果在看板页面，重新加载数据
            if (currentPage === 'dashboard') {
                loadDashboardData();
            }
        });
    }
}

// ==================== 日期筛选 ====================
function initDateFilter() {
    // 使用正确的类名 .date-btn
    document.querySelectorAll('.date-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            // 更新按钮状态
            document.querySelectorAll('.date-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // 更新当前时间段
            currentPeriod = btn.dataset.period;
            console.log('选择时间段:', currentPeriod);
            
            // 重新加载数据
            loadDashboardData();
        });
    });
}

// ==================== 刷新按钮 ====================
function initRefreshButton() {
    const refreshBtn = document.querySelector('.refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            loadDashboardData();
            showToast('数据已刷新');
        });
    }
}

// ==================== 数据看板 ====================
function initDashboard() {
    loadDashboardData();
}

async function loadDashboardData() {
    const period = currentPeriod || 'month';
    console.log('加载看板数据, 时间段:', period);
    
    try {
        showLoading();
        
        const response = await fetch(`${API_BASE}/api/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                input_type: 'query',
                query_type: period,
                store_id: currentStoreId
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        console.log('看板数据:', result);
        
        updateDashboard(result.dashboard_data || {});
        updateAnomalyAlerts(result.anomaly_alerts || []);
        
    } catch (error) {
        console.error('加载看板数据失败:', error);
        showError('加载看板数据失败: ' + error.message);
    } finally {
        hideLoading();
    }
}

function updateDashboard(data) {
    const summary = data.summary || {};
    
    // 更新核心指标
    updateElement('totalRevenue', `¥${(summary.total_revenue || 0).toLocaleString()}`);
    updateElement('totalCost', `¥${(summary.total_cost || 0).toLocaleString()}`);
    updateElement('grossProfit', `¥${(summary.gross_profit || 0).toLocaleString()}`);
    updateElement('grossMargin', `${(summary.gross_margin || 0).toFixed(1)}%`);
    updateElement('transactionCount', (summary.transaction_count || 0).toLocaleString());
    
    // 更新时间段显示
    updateElement('dataPeriod', `数据周期: ${data.period || '本月'}`);
}

function updateElement(id, value) {
    const el = document.getElementById(id);
    if (el) {
        el.textContent = value;
    }
}

function updateAnomalyAlerts(alerts) {
    const container = document.getElementById('alertContainer');
    if (!container) return;
    
    if (!alerts || alerts.length === 0) {
        container.innerHTML = '';
        return;
    }
    
    container.innerHTML = alerts.map(alert => `
        <div class="alert-item ${alert.level || 'warning'}">
            <i class="fas fa-exclamation-triangle"></i>
            <span>${alert.message}</span>
        </div>
    `).join('');
}

// ==================== 门店管理 ====================
async function loadStores() {
    try {
        const response = await fetch(`${API_BASE}/api/stores`);
        const result = await response.json();
        
        const storeSelect = document.getElementById('storeSelect');
        if (storeSelect && result.stores) {
            storeSelect.innerHTML = '<option value="all">全部门店</option>' +
                result.stores.map(store => 
                    `<option value="${store.id}">${store.name}</option>`
                ).join('');
        }
    } catch (error) {
        console.error('加载门店列表失败:', error);
    }
}

// ==================== 语音报账 ====================
function initVoiceRecord() {
    const recordBtn = document.getElementById('recordBtn');
    
    if (recordBtn) {
        recordBtn.addEventListener('click', toggleRecording);
    }
}

async function toggleRecording() {
    const recordBtn = document.getElementById('recordBtn');
    const recordStatus = document.getElementById('recordStatus');
    const recordWave = document.getElementById('waveContainer');
    
    if (!isRecording) {
        // 开始录音
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            
            mediaRecorder.ondataavailable = (event) => {
                audioChunks.push(event.data);
            };
            
            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/mp3' });
                await uploadAndRecognizeAudio(audioBlob);
                
                // 停止所有音轨
                stream.getTracks().forEach(track => track.stop());
            };
            
            mediaRecorder.start();
            isRecording = true;
            
            // 更新UI
            if (recordBtn) recordBtn.classList.add('recording');
            if (recordStatus) recordStatus.textContent = '正在录音...点击停止';
            if (recordWave) recordWave.classList.add('active');
            
        } catch (error) {
            console.error('录音失败:', error);
            showError('无法访问麦克风，请检查权限设置');
        }
    } else {
        // 停止录音
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }
        isRecording = false;
        
        // 更新UI
        if (recordBtn) recordBtn.classList.remove('recording');
        if (recordStatus) recordStatus.textContent = '点击开始录音';
        if (recordWave) recordWave.classList.remove('active');
    }
}

async function uploadAndRecognizeAudio(audioBlob) {
    try {
        showLoading('正在识别语音...');
        
        // 创建表单数据
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.mp3');
        formData.append('store_id', currentStoreId);
        
        const response = await fetch(`${API_BASE}/api/voice`, {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        console.log('语音识别结果:', result);
        
        if (result.extracted_data) {
            showRecognitionResult(result);
        } else {
            showError('未能识别出有效信息，请重新录音');
        }
        
    } catch (error) {
        console.error('语音识别失败:', error);
        showError('语音识别失败: ' + error.message);
    } finally {
        hideLoading();
    }
}

// ==================== 图片上传 ====================
function initImageUpload() {
    const dropZone = document.getElementById('dropZone');
    const imageInput = document.getElementById('imageInput');
    
    if (dropZone) {
        dropZone.addEventListener('click', () => {
            if (imageInput) imageInput.click();
        });
        
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        });
        
        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('drag-over');
        });
        
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleImageUpload(files[0]);
            }
        });
    }
    
    if (imageInput) {
        imageInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleImageUpload(e.target.files[0]);
            }
        });
    }
}

async function handleImageUpload(file) {
    if (!file.type.startsWith('image/')) {
        showError('请上传图片文件');
        return;
    }
    
    try {
        showLoading('正在识别图片...');
        
        // 显示预览
        const preview = document.getElementById('imagePreview');
        if (preview) {
            preview.src = URL.createObjectURL(file);
            preview.style.display = 'block';
        }
        
        // 上传识别
        const formData = new FormData();
        formData.append('image', file);
        formData.append('store_id', currentStoreId);
        
        const response = await fetch(`${API_BASE}/api/image`, {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        console.log('图片识别结果:', result);
        
        if (result.extracted_data) {
            showRecognitionResult(result);
        } else {
            showError('未能识别出有效信息，请上传清晰的票据图片');
        }
        
    } catch (error) {
        console.error('图片识别失败:', error);
        showError('图片识别失败: ' + error.message);
    } finally {
        hideLoading();
    }
}

// ==================== 模态框操作 ====================
function closeModal() {
    const modal = document.getElementById('resultModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

function confirmRecord() {
    // TODO: 将记录保存到数据库
    showSuccess('记录已保存');
    closeModal();
}

// ==================== 显示识别结果 ====================
function showRecognitionResult(result) {
    const modal = document.getElementById('resultModal');
    const resultContent = document.getElementById('modalBody');
    
    if (!modal || !resultContent) {
        console.error('模态框元素未找到');
        alert('识别成功！\n' + JSON.stringify(result.extracted_data, null, 2));
        return;
    }
    
    const data = result.extracted_data;
    const fields = data.extracted_fields || {};
    const items = fields.items || [];
    
    resultContent.innerHTML = `
        <div class="result-section">
            <div class="result-header">
                <span class="confidence">识别置信度: ${(data.confidence * 100 || 85).toFixed(0)}%</span>
            </div>
            
            <div class="result-item">
                <label>交易类型:</label>
                <span>${data.data_type === 'revenue' ? '销售收入' : '支出'}</span>
            </div>
            
            ${items.length > 0 ? `
                <div class="result-item">
                    <label>商品明细:</label>
                    <div class="items-list">
                        ${items.map(item => `
                            <div class="item-row">
                                <span>${item.name || '未知商品'}</span>
                                <span>×${item.quantity || 1}</span>
                                <span>¥${item.price || 0}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            ` : ''}
            
            <div class="result-item">
                <label>总金额:</label>
                <span class="amount">¥${fields.total_amount || 0}</span>
            </div>
            
            ${fields.description ? `
                <div class="result-item">
                    <label>备注:</label>
                    <span>${fields.description}</span>
                </div>
            ` : ''}
        </div>
        
        <div class="result-actions">
            <button class="btn-secondary" onclick="closeResultModal()">重新录入</button>
            <button class="btn-primary" onclick="confirmSubmit()">确认提交</button>
        </div>
    `;
    
    modal.style.display = 'flex';
}

function closeResultModal() {
    const modal = document.getElementById('resultModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

async function confirmSubmit() {
    showToast('提交成功！');
    closeResultModal();
    
    // 刷新看板数据
    if (currentPage === 'dashboard') {
        loadDashboardData();
    }
}

// ==================== 历史记录 ====================
async function loadHistoryRecords() {
    try {
        const response = await fetch(`${API_BASE}/api/records?limit=20`);
        const result = await response.json();
        
        const recordsList = document.getElementById('recordsList');
        if (recordsList && result.records) {
            recordsList.innerHTML = result.records.map(record => `
                <div class="record-item">
                    <div class="record-info">
                        <span class="record-type">${record.type}</span>
                        <span class="record-desc">${record.description}</span>
                    </div>
                    <div class="record-amount">¥${record.amount}</div>
                    <div class="record-time">${record.time}</div>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('加载历史记录失败:', error);
    }
}

// ==================== 辅助函数 ====================
function showLoading(message = '加载中...') {
    const loadingEl = document.getElementById('loadingOverlay');
    const loadingText = document.getElementById('loadingText');
    if (loadingEl) {
        loadingEl.style.display = 'flex';
        if (loadingText) loadingText.textContent = message;
    }
}

function hideLoading() {
    const loadingEl = document.getElementById('loadingOverlay');
    if (loadingEl) {
        loadingEl.style.display = 'none';
    }
}

function showError(message) {
    console.error('Error:', message);
    showToast(message, 'error');
}

function showToast(message, type = 'info') {
    // 创建toast元素
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 24px;
        border-radius: 8px;
        background: ${type === 'error' ? '#ef4444' : '#10b981'};
        color: white;
        z-index: 9999;
        animation: slideIn 0.3s ease;
    `;
    
    document.body.appendChild(toast);
    
    // 3秒后移除
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// 刷新数据函数（全局可调用）
function refreshData() {
    loadDashboardData();
    showToast('数据已刷新');
}

// 显示识别结果模态框
function showResultModal(data) {
    // 移除已存在的模态框
    const existingModal = document.getElementById('resultModal');
    if (existingModal) existingModal.remove();
    
    // 提取数据
    const extracted = data.extracted_data || {};
    const fields = extracted.extracted_fields || {};
    const items = fields.items || [];
    const confidence = extracted.confidence || data.confidence || 0.85;
    
    // 构建商品列表HTML
    let itemsHtml = '';
    if (items.length > 0) {
        itemsHtml = items.map(item => `
            <div class="result-item">
                <span class="result-label">商品</span>
                <span class="result-value">${item.name || '未知'} x${item.quantity || 1}</span>
            </div>
            ${item.price ? `<div class="result-item"><span class="result-label">单价</span><span class="result-value">¥${item.price}</span></div>` : ''}
        `).join('');
    }
    
    // 创建模态框
    const modal = document.createElement('div');
    modal.id = 'resultModal';
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3><i class="fas fa-check-circle"></i> 识别结果</h3>
                <button class="modal-close" onclick="closeResultModal()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                <div class="result-item">
                    <span class="result-label">置信度</span>
                    <span class="result-value">${(confidence * 100).toFixed(0)}%</span>
                </div>
                <div class="result-item">
                    <span class="result-label">交易类型</span>
                    <span class="result-value">${fields.data_type === 'expense' ? '支出' : '销售'}</span>
                </div>
                ${itemsHtml}
                ${fields.total_amount ? `<div class="result-item"><span class="result-label">总金额</span><span class="result-value">¥${fields.total_amount}</span></div>` : ''}
                ${fields.description ? `<div class="result-item"><span class="result-label">备注</span><span class="result-value">${fields.description}</span></div>` : ''}
            </div>
            <div class="modal-footer">
                <button class="btn-secondary" onclick="closeResultModal()">
                    <i class="fas fa-redo"></i> 重新录入
                </button>
                <button class="btn-primary" onclick="confirmSubmit()">
                    <i class="fas fa-check"></i> 确认提交
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // 点击背景关闭
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeResultModal();
    });
}

function closeResultModal() {
    const modal = document.getElementById('resultModal');
    if (modal) modal.remove();
}

function confirmSubmit() {
    closeResultModal();
    showToast('数据已保存成功！', 'success');
    refreshData();
}
