document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const actionBar = document.getElementById('action-bar');
    const pendingSection = document.getElementById('pending-section');
    const completedSection = document.getElementById('completed-section');
    const pendingList = document.getElementById('pending-list');
    const completedList = document.getElementById('completed-list');
    const selectAllCheckbox = document.getElementById('select-all');
    const batchDownloadBtn = document.getElementById('batch-download-btn');
    const startConvertBtn = document.getElementById('start-convert-btn');
    const pauseConvertBtn = document.getElementById('pause-convert-btn');
    const queueStatus = document.getElementById('queue-status');

    let conversionQueue = []; // Store { file, id, status, element }
    let isPaused = false;
    let isProcessing = false;

    // Drag & Drop events
    function handleDragEnter(e) {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.add('drag-over');
    }

    function handleDragOver(e) {
        e.preventDefault();
        e.stopPropagation();
        e.dataTransfer.dropEffect = 'copy';
        dropZone.classList.add('drag-over');
    }

    function handleDragLeave(e) {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('drag-over');
    }

    function handleDrop(e) {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('drag-over');
        
        const dt = e.dataTransfer;
        const files = dt.files;
        
        if (files && files.length > 0) {
            handleFiles(files);
        }
    }

    dropZone.addEventListener('dragenter', handleDragEnter, false);
    dropZone.addEventListener('dragover', handleDragOver, false);
    dropZone.addEventListener('dragleave', handleDragLeave, false);
    dropZone.addEventListener('drop', handleDrop, false);
    
    dropZone.addEventListener('click', () => fileInput.click());
    
    fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleFiles(e.target.files);
        }
    });

    function handleFiles(fileListObj) {
        const files = Array.from(fileListObj);
        
        if (files.length > 0) {
            actionBar.style.display = 'flex';
            pendingSection.style.display = 'block';
        }
        
        files.forEach(addFileToQueue);
        updateQueueStatus();
        fileInput.value = ''; // Allow re-uploading same file
    }

    // Batch Operations
    selectAllCheckbox.addEventListener('change', (e) => {
        const checkboxes = document.querySelectorAll('.file-checkbox:not(:disabled)');
        checkboxes.forEach(cb => cb.checked = e.target.checked);
    });

    batchDownloadBtn.addEventListener('click', () => {
        const selectedFiles = [];
        document.querySelectorAll('.file-checkbox:checked').forEach(cb => {
            selectedFiles.push(cb.dataset.filename);
        });

        if (selectedFiles.length === 0) {
            alert('请至少选择一个已完成的文件');
            return;
        }

        const originalText = batchDownloadBtn.textContent;
        batchDownloadBtn.textContent = '打包中...';
        batchDownloadBtn.disabled = true;

        fetch('/download_batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filenames: selectedFiles })
        })
        .then(resp => {
            if (!resp.ok) throw new Error('打包失败');
            return resp.blob();
        })
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = 'ebooks_bundle.zip';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            batchDownloadBtn.textContent = originalText;
            batchDownloadBtn.disabled = false;
        })
        .catch(err => {
            alert('下载失败: ' + err.message);
            batchDownloadBtn.textContent = originalText;
            batchDownloadBtn.disabled = false;
        });
    });

    // Manual Conversion Logic
    startConvertBtn.addEventListener('click', () => {
        isPaused = false;
        if (!isProcessing) {
            startProcessing();
        }
        toggleButtons(true);
    });

    pauseConvertBtn.addEventListener('click', () => {
        isPaused = true;
        toggleButtons(false);
        queueStatus.textContent = '已暂停，等待当前任务完成...';
    });

    function toggleButtons(isRunning) {
        if (isRunning) {
            startConvertBtn.style.display = 'none';
            pauseConvertBtn.style.display = 'flex';
        } else {
            startConvertBtn.style.display = 'flex';
            pauseConvertBtn.style.display = 'none';
        }
    }

    function startProcessing() {
        const pendingItems = conversionQueue.filter(item => item.status === 'pending');
        if (pendingItems.length === 0) {
            alert('没有待转换的文件');
            toggleButtons(false);
            return;
        }
        
        isProcessing = true;
        processNextInQueue();
    }

    function processNextInQueue() {
        if (isPaused) {
            isProcessing = false;
            toggleButtons(false);
            queueStatus.textContent = '已暂停';
            return;
        }

        const nextItem = conversionQueue.find(item => item.status === 'pending');
        
        if (!nextItem) {
            isProcessing = false;
            toggleButtons(false);
            queueStatus.textContent = '所有任务已完成';
            return;
        }
        
        updateQueueStatus();
        processItem(nextItem).then(() => {
            processNextInQueue();
        });
    }

    function processItem(item) {
        return new Promise((resolve) => {
            item.status = 'converting';
            const statusEl = document.getElementById(`status-${item.id}`);
            
            if (statusEl) {
                statusEl.textContent = '转换中...';
                statusEl.className = 'status converting';
            }
            
            const formData = new FormData();
            formData.append('file', item.file);
            
            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    item.status = 'done';
                    moveToCompleted(item, data);
                } else {
                    throw new Error(data.error || '未知错误');
                }
            })
            .catch(error => {
                item.status = 'error';
                if (statusEl) {
                    statusEl.textContent = '失败: ' + error.message;
                    statusEl.className = 'status error';
                }
                console.error('Error:', error);
            })
            .finally(() => {
                resolve();
            });
        });
    }

    function moveToCompleted(item, data) {
        // Move DOM element to completed list
        const element = document.getElementById(`item-${item.id}`);
        if (element) {
            // Remove from pending list
            element.remove();
            
            // Update content for completed view
            element.innerHTML = `
                <div class="file-info">
                    <input type="checkbox" class="file-checkbox" id="cb-${item.id}" data-filename="${data.filename}" checked style="margin-right: 15px; transform: scale(1.2);">
                    <div class="file-icon">✅</div>
                    <div class="file-name" title="${data.filename}">${data.filename}</div> <!-- Use converted filename -->
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                     <div class="status success">完成</div>
                     <a href="${data.download_url}" class="action-btn" style="display: inline-block; background-color: #007bff;">下载 TXT</a>
                </div>
            `;
            
            // Append to completed list
            completedList.appendChild(element);
            completedSection.style.display = 'block';
        }
        
        // Check if pending list is empty
        if (pendingList.children.length === 0) {
            pendingSection.style.display = 'none';
        }
    }

    function addFileToQueue(file) {
        const fileId = 'file-' + Math.random().toString(36).substr(2, 9);
        
        const item = document.createElement('div');
        item.className = 'file-item';
        item.id = `item-${fileId}`;
        
        item.innerHTML = `
            <div class="file-info">
                <div class="file-icon">📄</div>
                <div class="file-name" title="${file.name}">${file.name}</div>
            </div>
            <div class="status" id="status-${fileId}" style="color: #666;">等待开始...</div>
        `;
        
        pendingList.appendChild(item);
        
        conversionQueue.push({
            file: file,
            id: fileId,
            status: 'pending'
        });
    }

    function updateQueueStatus() {
        const pendingCount = conversionQueue.filter(i => i.status === 'pending').length;
        const convertingCount = conversionQueue.filter(i => i.status === 'converting').length;
        queueStatus.textContent = `待处理: ${pendingCount} | 进行中: ${convertingCount}`;
    }
});
