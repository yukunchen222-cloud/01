// ==================== 全局状态 ====================
let currentStoreId = 'store_001';
let currentPage = 'dashboard';
let uploadedImageUrl = null;
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

// ==================== 初始化 ====================
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initDashboard();
    initVoiceRecord();
    initImageUpload();
    loadStores();
});

// ==================== 导航功能 ====================
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
    currentPage = page;
    
    // 更新导航状态
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.page === page) {
            item.classList.add('active');
        }
    });
    
    // 切换页面内容
    document.querySelectorAll('.page-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${page}Page`).classList.add('active');
    
    // 页面特定初始化
    if (page === 'dashboard') {
        loadDashboardData();
    }
}

// ==================== 数据看板 ====================
function initDashboard() {
    loadDashboardData();
    
    // 时间维度切换
    document.querySelectorAll('.period-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            loadDashboardData(btn.dataset.period);
        });
    });
}

async function loadDashboardData(period = 'month') {
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
        updateDashboard(result.dashboard_data || {});
        updateAnomalyAlerts(result.anomaly_alerts || []);
    } catch (error) {
        console.error('加载看板数据失败:', error);
        showError('加载看板数据失败');
    }
}

function updateDashboard(data) {
    const summary = data.summary || {};
    
    document.getElementById('totalRevenue').textContent = `¥${(summary.total_revenue || 0).toLocaleString()}`;
    document.getElementById('totalCost').textContent = `¥${(summary.total_cost || 0).toLocaleString()}`;
    document.getElementById('grossProfit').textContent = `¥${(summary.gross_profit || 0).toLocaleString()}`;
    document.getElementById('grossMargin').textContent = `${(summary.gross_margin || 0)}%`;
    document.getElementById('transactionCount').textContent = summary.transaction_count || 0;
}

function updateAnomalyAlerts(alerts) {
    const container = document.getElementById('anomalyAlerts');
    if (!container) return;
    
    if (alerts.length === 0) {
        container.innerHTML = '<p class="no-data">暂无异常</p>';
        return;
    }
    
    container.innerHTML = alerts.map(alert => `
        <div class="alert-item ${alert.level}">
            <i class="fas fa-exclamation-triangle"></i>
            <span>${alert.message}</span>
        </div>
    `).join('');
}

// ==================== 门店管理 ====================
async function loadStores() {
    try {
        const response = await fetch('/api/stores');
        const result = await response.json();
        
        const storeSelect = document.getElementById('storeSelect');
        if (storeSelect && result.stores) {
            storeSelect.innerHTML = result.stores.map(store => 
                `<option value="${store.id}">${store.name}</option>`
            ).join('');
            
            storeSelect.addEventListener('change', (e) => {
                currentStoreId = e.target.value;
            });
        }
    } catch (error) {
        console.error('加载门店列表失败:', error);
    }
}

// ==================== 语音报账 ====================
function initVoiceRecord() {
    const recordBtn = document.getElementById('recordBtn');
    const recordWave = document.getElementById('recordWave');
    
    if (recordBtn) {
        recordBtn.addEventListener('click', toggleRecording);
    }
}

async function toggleRecording() {
    const recordBtn = document.getElementById('recordBtn');
    const recordWave = document.getElementById('recordWave');
    
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
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                await processAudio(audioBlob);
                
                // 停止所有音轨
                stream.getTracks().forEach(track => track.stop());
            };
            
            mediaRecorder.start();
            isRecording = true;
            recordBtn.classList.add('recording');
            recordBtn.innerHTML = '<i class="fas fa-stop"></i> 点击停止';
            recordWave.classList.add('active');
            showInfo('录音中... 请说出交易信息');
            
        } catch (error) {
            console.error('无法访问麦克风:', error);
            showError('无法访问麦克风，请检查权限设置');
        }
    } else {
        // 停止录音
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
        }
        isRecording = false;
        recordBtn.classList.remove('recording');
        recordBtn.innerHTML = '<i class="fas fa-microphone"></i> 点击录音';
        recordWave.classList.remove('active');
    }
}

async function processAudio(audioBlob) {
    showLoading();
    
    try {
        // 上传音频文件
        const formData = new FormData();
        formData.append('file', audioBlob, 'recording.webm');
        formData.append('store_id', currentStoreId);
        
        // 上传音频到服务器
        const uploadResponse = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        const uploadResult = await uploadResponse.json();
        
        if (!uploadResult.success) {
            throw new Error(uploadResult.error || '音频上传失败');
        }
        
        const audioUrl = uploadResult.url;
        
        // 调用语音识别API
        const voiceResponse = await fetch('/api/voice', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                input_type: 'voice',
                audio_file: {
                    url: audioUrl,
                    file_type: 'audio'
                },
                store_id: currentStoreId
            })
        });
        
        const voiceResult = await voiceResponse.json();
        hideLoading();
        
        if (voiceResult.extracted_data) {
            showVoiceResult(voiceResult);
        } else {
            showError('未能识别到有效信息，请重新录音');
        }
        
    } catch (error) {
        console.error('语音识别失败:', error);
        hideLoading();
        showError('语音识别失败: ' + error.message);
    }
}

function showVoiceResult(result) {
    const resultPanel = document.getElementById('voiceResult');
    const resultBody = document.getElementById('voiceResultBody');
    
    const data = result.extracted_data || {};
    const fields = data.extracted_fields || {};
    const items = fields.items || [];
    const firstItem = items[0] || {};
    
    const confidence = (result.confidence || 0.85) * 100;
    document.getElementById('voiceConfidence').textContent = `置信度: ${confidence.toFixed(0)}%`;
    
    // 获取原始识别文本
    const rawText = result.raw_text || fields.description || '识别完成';
    document.getElementById('voiceText').textContent = rawText;
    
    // 构建识别结果HTML
    let html = '';
    
    // 交易类型
    const dataType = data.data_type || 'revenue';
    const typeText = dataType === 'revenue' ? '销售' : (dataType === 'expense' ? '支出' : '收入');
    html += `
        <div class="result-item">
            <span class="result-label">交易类型</span>
            <span class="result-value">${typeText}</span>
        </div>
    `;
    
    // 商品信息
    if (firstItem.name) {
        html += `
            <div class="result-item">
                <span class="result-label">商品名称</span>
                <span class="result-value">${firstItem.name}</span>
            </div>
        `;
    }
    
    // 数量
    if (firstItem.quantity) {
        html += `
            <div class="result-item">
                <span class="result-label">数量</span>
                <span class="result-value">${firstItem.quantity}件</span>
            </div>
        `;
    }
    
    // 单价
    if (firstItem.price) {
        html += `
            <div class="result-item">
                <span class="result-label">单价</span>
                <span class="result-value">¥${firstItem.price}</span>
            </div>
        `;
    }
    
    // 总金额
    if (fields.total_amount) {
        html += `
            <div class="result-item">
                <span class="result-label">总金额</span>
                <span class="result-value">¥${fields.total_amount}</span>
            </div>
        `;
    }
    
    resultBody.innerHTML = html;
    resultPanel.classList.remove('hidden');
}

function retryVoice() {
    document.getElementById('voiceResult').classList.add('hidden');
}

async function confirmVoiceRecord() {
    showLoading();
    showSuccess('账目已成功录入');
    hideLoading();
    document.getElementById('voiceResult').classList.add('hidden');
}

// ==================== 拍照录入 ====================
function initImageUpload() {
    const imageInput = document.getElementById('imageInput');
    const uploadArea = document.getElementById('uploadArea');
    
    if (imageInput) {
        imageInput.addEventListener('change', handleImageUpload);
    }
    
    // 拖拽上传
    if (uploadArea) {
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('drag-over');
        });
        
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('drag-over');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('drag-over');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleImageUpload({ target: { files: files } });
            }
        });
    }
}

async function handleImageUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    // 显示预览
    const reader = new FileReader();
    reader.onload = (e) => {
        document.getElementById('previewImg').src = e.target.result;
        document.getElementById('imagePreview').classList.remove('hidden');
        document.getElementById('uploadArea').style.display = 'none';
    };
    reader.readAsDataURL(file);
    
    // 上传图片并识别
    showLoading();
    
    try {
        // 创建FormData上传图片
        const formData = new FormData();
        formData.append('file', file);
        formData.append('store_id', currentStoreId);
        
        // 上传图片到服务器
        const uploadResponse = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        const uploadResult = await uploadResponse.json();
        
        if (!uploadResult.success) {
            throw new Error(uploadResult.error || '图片上传失败');
        }
        
        uploadedImageUrl = uploadResult.url;
        
        // 调用OCR识别API
        const ocrResponse = await fetch('/api/image', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                input_type: 'image',
                image_file: {
                    url: uploadedImageUrl,
                    file_type: 'image'
                },
                store_id: currentStoreId
            })
        });
        
        const ocrResult = await ocrResponse.json();
        hideLoading();
        
        if (ocrResult.extracted_data) {
            showOcrResult(ocrResult);
        } else {
            showError('未能识别到有效信息，请上传更清晰的图片');
        }
    } catch (error) {
        console.error('图片上传识别失败:', error);
        hideLoading();
        showError('图片上传识别失败: ' + error.message);
    }
}

function showOcrResult(result) {
    const resultPanel = document.getElementById('ocrResult');
    const resultBody = document.getElementById('ocrResultBody');
    
    const data = result.extracted_data || {};
    const fields = data.extracted_fields || {};
    const items = fields.items || [];
    const firstItem = items[0] || {};
    
    const confidence = (result.confidence || 0.85) * 100;
    document.getElementById('ocrConfidence').textContent = `置信度: ${confidence.toFixed(0)}%`;
    
    // 构建识别结果HTML
    let html = '';
    
    // 交易类型
    const dataType = data.data_type || 'revenue';
    const typeText = dataType === 'revenue' ? '销售' : (dataType === 'expense' ? '支出' : '收入');
    html += `
        <div class="result-item">
            <span class="result-label">交易类型</span>
            <span class="result-value">${typeText}</span>
        </div>
    `;
    
    // 商品信息
    if (firstItem.name) {
        html += `
            <div class="result-item">
                <span class="result-label">商品名称</span>
                <span class="result-value">${firstItem.name}</span>
            </div>
        `;
    }
    
    // 数量
    if (firstItem.quantity) {
        html += `
            <div class="result-item">
                <span class="result-label">数量</span>
                <span class="result-value">${firstItem.quantity}件</span>
            </div>
        `;
    }
    
    // 单价
    if (firstItem.price) {
        html += `
            <div class="result-item">
                <span class="result-label">单价</span>
                <span class="result-value">¥${firstItem.price}</span>
            </div>
        `;
    }
    
    // 总金额
    if (fields.total_amount) {
        html += `
            <div class="result-item">
                <span class="result-label">总金额</span>
                <span class="result-value">¥${fields.total_amount}</span>
            </div>
        `;
    }
    
    // 原始识别文本
    if (data.ocr_text) {
        html += `
            <div class="result-item full-width">
                <span class="result-label">识别原文</span>
                <span class="result-value">${data.ocr_text}</span>
            </div>
        `;
    }
    
    resultBody.innerHTML = html;
    resultPanel.classList.remove('hidden');
}

function retryOcr() {
    document.getElementById('ocrResult').classList.add('hidden');
    document.getElementById('imagePreview').classList.add('hidden');
    document.getElementById('uploadArea').style.display = 'block';
}

async function confirmOcrResult() {
    showLoading();
    showSuccess('账目已成功录入');
    hideLoading();
    document.getElementById('ocrResult').classList.add('hidden');
    document.getElementById('imagePreview').classList.add('hidden');
    document.getElementById('uploadArea').style.display = 'block';
}

// ==================== 历史记录 ====================
async function loadRecords() {
    try {
        const response = await fetch('/api/records?limit=20');
        const result = await response.json();
        displayRecords(result.records || []);
    } catch (error) {
        console.error('加载历史记录失败:', error);
    }
}

function displayRecords(records) {
    const container = document.getElementById('recordsList');
    if (!container) return;
    
    if (records.length === 0) {
        container.innerHTML = '<p class="no-data">暂无记录</p>';
        return;
    }
    
    container.innerHTML = records.map(record => `
        <div class="record-item">
            <div class="record-info">
                <span class="record-type">${record.type === 'sale' ? '销售' : '进货'}</span>
                <span class="record-product">${record.product}</span>
            </div>
            <div class="record-amount">¥${record.amount}</div>
            <div class="record-time">${record.time}</div>
        </div>
    `).join('');
}

// ==================== 报告中心 ====================
async function generateReport(type) {
    showLoading();
    try {
        const response = await fetch('/api/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                input_type: 'query',
                query_type: type
            })
        });
        
        const result = await response.json();
        hideLoading();
        
        if (result.report_url) {
            showSuccess('报告生成成功！');
            // 可以添加下载链接
        }
    } catch (error) {
        hideLoading();
        showError('报告生成失败');
    }
}

// ==================== 工具函数 ====================
function showLoading() {
    document.getElementById('loadingOverlay').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.add('hidden');
}

function showSuccess(message) {
    const toast = document.createElement('div');
    toast.className = 'toast success';
    toast.innerHTML = `<i class="fas fa-check-circle"></i> ${message}`;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

function showError(message) {
    const toast = document.createElement('div');
    toast.className = 'toast error';
    toast.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

function showInfo(message) {
    const toast = document.createElement('div');
    toast.className = 'toast info';
    toast.innerHTML = `<i class="fas fa-info-circle"></i> ${message}`;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}
