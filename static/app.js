// Music Sorter Frontend Application
let ws = null;
let currentPage = 1;
const filesPerPage = 100;

// Directory picker variables
let currentPickerTarget = null;
let currentPath = '';

// Create target directory
async function createTargetDirectory() {
    const targetPath = document.getElementById('target-path').value;
    if (!targetPath) {
        alert('Please enter a target directory path');
        return;
    }
    
    try {
        const response = await fetch('/api/create-directory', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: targetPath })
        });
        
        if (response.ok) {
            const result = await response.json();
            if (result.created) {
                alert(`Directory created: ${targetPath}`);
            } else if (result.exists) {
                alert(`Directory already exists: ${targetPath}`);
            }
        } else {
            const error = await response.json();
            alert(`Error creating directory: ${error.detail}`);
        }
    } catch (err) {
        console.error('Error creating directory:', err);
        alert('Failed to create directory');
    }
}

// Open directory picker modal
async function openDirectoryPicker(target) {
    currentPickerTarget = target;
    document.getElementById('dir-picker-modal').classList.remove('hidden');
    
    // Load root drives
    await browseDirectory('');
}

// Close directory picker
function closeDirectoryPicker() {
    document.getElementById('dir-picker-modal').classList.add('hidden');
    currentPickerTarget = null;
}

// Browse a directory
async function browseDirectory(path) {
    try {
        const response = await fetch(`/api/browse?path=${encodeURIComponent(path)}`);
        const data = await response.json();
        
        currentPath = data.current_path;
        document.getElementById('current-dir-path').value = currentPath || 'Select a drive:';
        
        const dirList = document.getElementById('dir-list');
        dirList.innerHTML = '';
        
        // Add directories/drives
        data.items.forEach(item => {
            const div = document.createElement('div');
            div.className = 'dir-item';
            
            const icon = item.type === 'drive' ? '💾' : '📁';
            div.innerHTML = `<span class="dir-icon">${icon}</span><span class="dir-name">${item.name}</span>`;
            
            div.onclick = () => {
                browseDirectory(item.path);
            };
            
            dirList.appendChild(div);
        });
        
        // Enable/disable up button
        document.getElementById('up-btn').disabled = !data.parent_path;
        
    } catch (error) {
        console.error('Error browsing directory:', error);
        showError('Failed to browse directory');
    }
}

// Navigate up one level
async function navigateUp() {
    if (currentPath) {
        const parentPath = currentPath.includes('\\') ? 
            currentPath.substring(0, currentPath.lastIndexOf('\\')) : '';
        await browseDirectory(parentPath);
    }
}

// Select current directory
function selectCurrentDirectory() {
    if (!currentPath) {
        showError('Please select a directory');
        return;
    }
    
    // Update the appropriate input field
    if (currentPickerTarget === 'source') {
        document.getElementById('source-path').value = currentPath;
    } else if (currentPickerTarget === 'target') {
        document.getElementById('target-path').value = currentPath;
    }
    
    closeDirectoryPicker();
}

// Initialize WebSocket connection
function initWebSocket() {
    const wsUrl = `ws://${window.location.host}/ws/progress`;
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        console.log('WebSocket connected');
        setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send('ping');
            }
        }, 30000); // Keep alive every 30 seconds
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
    
    ws.onclose = () => {
        console.log('WebSocket disconnected, reconnecting...');
        setTimeout(initWebSocket, 3000); // Reconnect after 3 seconds
    };
}

// Handle WebSocket messages
function handleWebSocketMessage(message) {
    if (message.type === 'progress') {
        updateProgress(message.operation, message.data);
    } else if (message.type === 'complete') {
        handleOperationComplete(message.operation, message.result);
    } else if (message.type === 'error') {
        showError(message.error);
    }
}

// Update progress displays
function updateProgress(operation, data) {
    const progressPercent = (data.progress / data.total * 100) || 0;
    
    switch(operation) {
        case 'scan':
            document.getElementById('scan-progress').style.display = 'block';
            document.getElementById('scan-progress-fill').style.width = progressPercent + '%';
            document.getElementById('scan-progress-text').textContent = data.message || '';
            break;
        
        case 'metadata':
            document.getElementById('analysis-progress').style.display = 'block';
            document.getElementById('metadata-progress-fill').style.width = progressPercent + '%';
            document.getElementById('metadata-progress-text').textContent = data.message || '';
            break;
        
        case 'duplicates':
            document.getElementById('duplicate-progress-fill').style.width = progressPercent + '%';
            document.getElementById('duplicate-progress-text').textContent = data.message || '';
            break;
        
        case 'classification':
            document.getElementById('classification-progress-fill').style.width = progressPercent + '%';
            document.getElementById('classification-progress-text').textContent = data.message || '';
            break;
        
        case 'migrate':
            document.getElementById('migration-progress').style.display = 'block';
            document.getElementById('migration-progress-fill').style.width = progressPercent + '%';
            document.getElementById('migration-progress-text').textContent = data.message || '';
            break;
        
        case 'audio':
            document.getElementById('audio-progress').style.display = 'block';
            document.getElementById('audio-progress-fill').style.width = progressPercent + '%';
            document.getElementById('audio-progress-text').textContent = data.message || '';
            break;
    }
}

// API Functions
async function apiCall(endpoint, method = 'GET', body = null) {
    try {
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        if (body) {
            options.body = JSON.stringify(body);
        }
        
        const response = await fetch(`/api${endpoint}`, options);
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'API request failed');
        }
        
        return await response.json();
    } catch (error) {
        showError(error.message);
        throw error;
    }
}

// Step 1: Scanning
async function startScan() {
    const sourcePath = document.getElementById('source-path').value;
    
    if (!sourcePath) {
        showError('Please enter a source directory path');
        return;
    }
    
    document.getElementById('scan-btn').style.display = 'none';
    document.getElementById('stop-scan-btn').style.display = 'inline-block';
    
    try {
        const result = await apiCall('/scan', 'POST', { path: sourcePath, resume: true });
        console.log('Scan started:', result);
        
        // Poll for status
        pollScanStatus();
    } catch (error) {
        document.getElementById('scan-btn').style.display = 'inline-block';
        document.getElementById('stop-scan-btn').style.display = 'none';
    }
}

async function stopScan() {
    await apiCall('/scan/stop', 'POST');
    document.getElementById('scan-btn').style.display = 'inline-block';
    document.getElementById('stop-scan-btn').style.display = 'none';
}

async function pollScanStatus() {
    const interval = setInterval(async () => {
        const status = await apiCall('/scan/status');
        
        if (status.status === 'completed') {
            clearInterval(interval);
            document.getElementById('scan-btn').style.display = 'inline-block';
            document.getElementById('stop-scan-btn').style.display = 'none';
            
            // Show results
            document.getElementById('scan-results').style.display = 'block';
            document.getElementById('scan-files-count').textContent = status.result.files_added || 0;
            document.getElementById('scan-files-skipped').textContent = status.result.files_skipped || 0;
            document.getElementById('scan-errors').textContent = status.result.errors || 0;
            document.getElementById('scan-time').textContent = Math.round(status.result.elapsed_time);
            document.getElementById('scan-speed').textContent = Math.round(status.result.files_per_second);
            
            // Enable next step
            document.getElementById('analysis-section').classList.add('active');
            
            // Update stats
            updateStats();
        } else if (status.status === 'error') {
            clearInterval(interval);
            showError(status.error);
            document.getElementById('scan-btn').style.display = 'inline-block';
            document.getElementById('stop-scan-btn').style.display = 'none';
        }
    }, 1000);
}

// Step 2: Analysis
async function startAnalysis() {
    document.getElementById('analyze-btn').disabled = true;
    
    try {
        const result = await apiCall('/analyze', 'POST');
        console.log('Analysis started:', result);
        
        // Poll for status
        pollAnalysisStatus();
    } catch (error) {
        document.getElementById('analyze-btn').disabled = false;
    }
}

async function pollAnalysisStatus() {
    const interval = setInterval(async () => {
        const status = await apiCall('/analyze/status');
        
        if (status.metadata.status === 'completed' && 
            status.duplicates.status === 'completed' && 
            status.classification && status.classification.status === 'completed') {
            clearInterval(interval);
            document.getElementById('analyze-btn').disabled = false;
            
            // Show results
            document.getElementById('analysis-results').style.display = 'block';
            document.getElementById('metadata-extracted').textContent = status.metadata.result.extracted;
            document.getElementById('metadata-failed').textContent = status.metadata.result.failed;
            document.getElementById('duplicate-groups').textContent = status.duplicates.result.total_groups;
            document.getElementById('space-savings').textContent = 
                (status.duplicates.result.space_savings / 1024 / 1024 / 1024).toFixed(2);
            
            // Show classification results
            if (status.classification && status.classification.result) {
                document.getElementById('songs-count').textContent = status.classification.result.songs || 0;
                document.getElementById('samples-count').textContent = status.classification.result.samples || 0;
                document.getElementById('stems-count').textContent = status.classification.result.stems || 0;
                document.getElementById('unknown-count').textContent = status.classification.result.unknown || 0;
            }
            
            // Load duplicate preview
            loadDuplicates();
            
            // Enable next step
            document.getElementById('migration-section').classList.add('active');
            
            // Update stats
            updateStats();
        }
    }, 1000);
}

// Load duplicate groups
async function loadDuplicates() {
    try {
        const data = await apiCall('/duplicates?limit=10');
        const container = document.getElementById('duplicate-items');
        container.innerHTML = '';
        
        data.duplicates.forEach(group => {
            const groupDiv = document.createElement('div');
            groupDiv.className = 'duplicate-group';
            
            const primary = group.files.find(f => f.is_primary);
            groupDiv.innerHTML = `
                <div class="duplicate-header">
                    <strong>Group (${group.count} files)</strong>
                    <span>Primary: ${primary.metadata.artist || 'Unknown'} - ${primary.metadata.title || 'Unknown'}</span>
                </div>
                <div class="duplicate-files">
                    ${group.files.map(f => `
                        <div class="duplicate-file ${f.is_primary ? 'primary' : ''}">
                            <span>${f.path}</span>
                            <span>${(f.size / 1024 / 1024).toFixed(2)} MB</span>
                            <span>Score: ${f.quality_score}</span>
                        </div>
                    `).join('')}
                </div>
            `;
            container.appendChild(groupDiv);
        });
    } catch (error) {
        console.error('Error loading duplicates:', error);
    }
}

// Step 3: Migration
async function testMigration() {
    document.getElementById('test-btn').disabled = true;
    
    try {
        const skipDuplicates = document.getElementById('skip-duplicates').checked;
        const result = await apiCall('/migrate', 'POST', {
            skip_duplicates: skipDuplicates,
            test_mode: true
        });
        
        // Show test results
        document.getElementById('test-results').style.display = 'block';
        const mappingsDiv = document.getElementById('test-mappings');
        mappingsDiv.innerHTML = '<h4>Sample Mappings (first 100)</h4>';
        
        result.mappings.forEach(mapping => {
            const div = document.createElement('div');
            div.className = 'mapping-item';
            div.innerHTML = `
                <div class="mapping-source">${mapping.source}</div>
                <div class="mapping-arrow">→</div>
                <div class="mapping-target">${mapping.target}</div>
            `;
            mappingsDiv.appendChild(div);
        });
        
        document.getElementById('test-btn').disabled = false;
    } catch (error) {
        document.getElementById('test-btn').disabled = false;
    }
}

async function startMigration() {
    const targetPath = document.getElementById('target-path').value;
    const skipDuplicates = document.getElementById('skip-duplicates').checked;
    
    if (!targetPath) {
        showError('Please enter a target directory path');
        return;
    }
    
    document.getElementById('migrate-btn').style.display = 'none';
    document.getElementById('stop-migrate-btn').style.display = 'inline-block';
    
    try {
        const result = await apiCall('/migrate', 'POST', {
            skip_duplicates: skipDuplicates,
            test_mode: false
        });
        
        // Poll for status
        pollMigrationStatus();
    } catch (error) {
        document.getElementById('migrate-btn').style.display = 'inline-block';
        document.getElementById('stop-migrate-btn').style.display = 'none';
    }
}

async function stopMigration() {
    await apiCall('/migrate/stop', 'POST');
    document.getElementById('migrate-btn').style.display = 'inline-block';
    document.getElementById('stop-migrate-btn').style.display = 'none';
}

async function pollMigrationStatus() {
    const interval = setInterval(async () => {
        const status = await apiCall('/migrate/status');
        
        if (status.status === 'completed') {
            clearInterval(interval);
            document.getElementById('migrate-btn').style.display = 'inline-block';
            document.getElementById('stop-migrate-btn').style.display = 'none';
            
            // Show results
            document.getElementById('migration-results').style.display = 'block';
            document.getElementById('files-migrated').textContent = status.result.migrated;
            document.getElementById('files-skipped').textContent = status.result.skipped;
            document.getElementById('files-failed').textContent = status.result.failed;
            
            // Enable audio analysis
            document.getElementById('audio-analysis-section').classList.add('active');
            
            // Update stats
            updateStats();
        }
    }, 1000);
}

// Step 4: Audio Analysis
async function startAudioAnalysis() {
    document.getElementById('audio-analyze-btn').style.display = 'none';
    document.getElementById('stop-audio-btn').style.display = 'inline-block';
    
    try {
        const result = await apiCall('/audio-analyze', 'POST', {
            use_migrated_paths: true
        });
        
        // Poll for status
        pollAudioStatus();
    } catch (error) {
        document.getElementById('audio-analyze-btn').style.display = 'inline-block';
        document.getElementById('stop-audio-btn').style.display = 'none';
    }
}

async function stopAudioAnalysis() {
    await apiCall('/audio-analyze/stop', 'POST');
    document.getElementById('audio-analyze-btn').style.display = 'inline-block';
    document.getElementById('stop-audio-btn').style.display = 'none';
}

async function pollAudioStatus() {
    const interval = setInterval(async () => {
        const status = await apiCall('/audio-analyze/status');
        
        if (status.status === 'completed') {
            clearInterval(interval);
            document.getElementById('audio-analyze-btn').style.display = 'inline-block';
            document.getElementById('stop-audio-btn').style.display = 'none';
            
            // Show results
            document.getElementById('audio-results').style.display = 'block';
            document.getElementById('audio-analyzed').textContent = status.result.analyzed;
            
            // Get and display statistics
            displayAudioStats();
        }
    }, 1000);
}

async function displayAudioStats() {
    try {
        const stats = await apiCall('/stats');
        
        if (stats.audio_analysis) {
            document.getElementById('avg-bpm').textContent = stats.audio_analysis.average_bpm || 0;
            
            // Display key distribution
            const keyDiv = document.getElementById('key-distribution');
            keyDiv.innerHTML = '';
            
            if (stats.audio_analysis.key_distribution) {
                Object.entries(stats.audio_analysis.key_distribution).forEach(([key, count]) => {
                    const div = document.createElement('div');
                    div.className = 'key-item';
                    div.textContent = `${key}: ${count}`;
                    keyDiv.appendChild(div);
                });
            }
        }
    } catch (error) {
        console.error('Error loading audio stats:', error);
    }
}

// Files browser
async function loadFiles() {
    document.getElementById('files-section').classList.add('active');
    
    try {
        const offset = (currentPage - 1) * filesPerPage;
        const fileType = document.getElementById('file-type-filter').value;
        
        let url = `/files?limit=${filesPerPage}&offset=${offset}`;
        if (fileType) {
            url += `&file_type=${fileType}`;
        }
        
        const data = await apiCall(url);
        
        const tbody = document.getElementById('files-tbody');
        tbody.innerHTML = '';
        
        data.files.forEach(file => {
            const tr = document.createElement('tr');
            const typeClass = file.classification ? `type-${file.classification.type}` : 'type-unclassified';
            tr.innerHTML = `
                <td>${file.metadata?.artist || '-'}</td>
                <td>${file.metadata?.title || '-'}</td>
                <td>${file.metadata?.album || '-'}</td>
                <td><span class="status-badge ${typeClass}">${file.classification?.type || 'unclassified'}</span></td>
                <td><span class="status-badge status-${file.status}">${file.status}</span></td>
                <td>${(file.size / 1024 / 1024).toFixed(2)} MB</td>
            `;
            tbody.appendChild(tr);
        });
        
        document.getElementById('page-info').textContent = `Page ${currentPage}`;
        
        // Update pagination buttons
        document.getElementById('prev-page').disabled = currentPage === 1;
        document.getElementById('next-page').disabled = offset + filesPerPage >= data.total;
    } catch (error) {
        console.error('Error loading files:', error);
    }
}

function previousPage() {
    if (currentPage > 1) {
        currentPage--;
        loadFiles();
    }
}

function nextPage() {
    currentPage++;
    loadFiles();
}

// Update statistics
async function updateStats() {
    try {
        const stats = await apiCall('/stats');
        
        if (stats.indexing) {
            document.getElementById('total-files').textContent = `Files: ${stats.indexing.total_files}`;
            document.getElementById('total-size').textContent = `Size: ${stats.indexing.total_size_gb.toFixed(2)} GB`;
        }
        
        if (stats.migration) {
            document.getElementById('migrated-count').textContent = `Migrated: ${stats.migration.migrated_files}`;
        }
    } catch (error) {
        console.error('Error updating stats:', error);
    }
}

// Modal functions
function closeModal() {
    document.getElementById('progress-modal').classList.add('hidden');
}

function closeErrorModal() {
    document.getElementById('error-modal').classList.add('hidden');
}

function showError(message) {
    document.getElementById('error-message').textContent = message;
    document.getElementById('error-modal').classList.remove('hidden');
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
    updateStats();
});