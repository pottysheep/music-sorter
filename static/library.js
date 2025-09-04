// Library Browser JavaScript

// State management
let currentView = 'browse';
let currentPage = 1;
let pageSize = 50;
let searchResults = [];
let totalPages = 1;
let charts = {};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadStatistics();
    performSearch();
    loadGenres();
});

// Statistics
async function loadStatistics() {
    try {
        const response = await fetch('/api/library/statistics');
        const stats = await response.json();
        
        // Update dashboard
        document.getElementById('stat-total-files').textContent = stats.total_files || 0;
        document.getElementById('stat-total-size').textContent = `${stats.total_size_gb || 0} GB`;
        document.getElementById('stat-duplicates').textContent = stats.duplicates?.groups || 0;
        document.getElementById('stat-savings').textContent = `${stats.duplicates?.potential_savings_gb || 0} GB`;
        document.getElementById('stat-metadata').textContent = `${stats.metadata_coverage || 0}%`;
        document.getElementById('stat-analyzed').textContent = `${stats.analysis_coverage || 0}%`;
        
        // Store for later use
        window.libraryStats = stats;
    } catch (error) {
        console.error('Error loading statistics:', error);
    }
}

function refreshStats() {
    loadStatistics();
    performSearch();
}

// Search and filtering
function handleSearchKeyup(event) {
    if (event.key === 'Enter') {
        performSearch();
    }
}

async function performSearch(page = 1) {
    currentPage = page;
    
    const searchQuery = document.getElementById('search-input').value;
    const filters = collectFilters();
    
    const requestBody = {
        search_query: searchQuery || null,
        ...filters,
        sort_by: document.getElementById('sort-by').value,
        sort_order: document.getElementById('sort-order').value,
        limit: pageSize,
        offset: (page - 1) * pageSize
    };
    
    try {
        const response = await fetch('/api/library/search', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(requestBody)
        });
        
        const data = await response.json();
        searchResults = data.results;
        totalPages = data.total_pages;
        
        displaySearchResults();
        updatePagination(data);
        
    } catch (error) {
        console.error('Error performing search:', error);
    }
}

function collectFilters() {
    const filters = {};
    
    // Only collect if advanced filters are visible
    if (document.getElementById('advanced-filters').style.display !== 'none') {
        const artist = document.getElementById('filter-artist').value;
        const album = document.getElementById('filter-album').value;
        const genre = document.getElementById('filter-genre').value;
        const yearFrom = document.getElementById('filter-year-from').value;
        const yearTo = document.getElementById('filter-year-to').value;
        const bpmMin = document.getElementById('filter-bpm-min').value;
        const bpmMax = document.getElementById('filter-bpm-max').value;
        const key = document.getElementById('filter-key').value;
        const sizeMin = document.getElementById('filter-size-min').value;
        const sizeMax = document.getElementById('filter-size-max').value;
        const status = document.getElementById('filter-status').value;
        const duplicates = document.getElementById('filter-duplicates').value;
        
        if (artist) filters.artist = artist;
        if (album) filters.album = album;
        if (genre) filters.genre = genre;
        if (yearFrom) filters.year_from = parseInt(yearFrom);
        if (yearTo) filters.year_to = parseInt(yearTo);
        if (bpmMin) filters.bpm_min = parseFloat(bpmMin);
        if (bpmMax) filters.bpm_max = parseFloat(bpmMax);
        if (key) filters.key_signature = key;
        if (sizeMin) filters.size_min_mb = parseFloat(sizeMin);
        if (sizeMax) filters.size_max_mb = parseFloat(sizeMax);
        if (status) filters.status = status;
        if (duplicates) filters.has_duplicates = duplicates === 'true';
    }
    
    return filters;
}

function displaySearchResults() {
    const tbody = document.getElementById('files-tbody');
    const noResults = document.getElementById('no-results');
    const resultsCount = document.getElementById('results-count');
    
    resultsCount.textContent = `${searchResults.length} results found`;
    
    if (searchResults.length === 0) {
        tbody.innerHTML = '';
        noResults.style.display = 'block';
        document.getElementById('files-table').style.display = 'none';
    } else {
        noResults.style.display = 'none';
        document.getElementById('files-table').style.display = 'table';
        
        tbody.innerHTML = searchResults.map(file => {
            const metadata = file.metadata || {};
            const audio = file.audio_analysis || {};
            
            return `
                <tr>
                    <td>${metadata.artist || '-'}</td>
                    <td>${metadata.title || '-'}</td>
                    <td>${metadata.album || '-'}</td>
                    <td>${metadata.genre || '-'}</td>
                    <td>${metadata.year || '-'}</td>
                    <td>${audio.bpm ? Math.round(audio.bpm) : '-'}</td>
                    <td>${audio.key_signature || '-'}</td>
                    <td>${file.file_size_mb} MB</td>
                    <td><span class="status-badge status-${file.status}">${file.status}</span></td>
                    <td>
                        <button class="action-btn" onclick="showFileDetails(${file.id})">Details</button>
                    </td>
                </tr>
            `;
        }).join('');
    }
}

function updatePagination(data) {
    document.getElementById('current-page').textContent = data.page;
    document.getElementById('total-pages').textContent = data.total_pages;
    
    document.getElementById('prev-page').disabled = currentPage === 1;
    document.getElementById('next-page').disabled = currentPage >= totalPages;
}

function previousPage() {
    if (currentPage > 1) {
        performSearch(currentPage - 1);
    }
}

function nextPage() {
    if (currentPage < totalPages) {
        performSearch(currentPage + 1);
    }
}

function changePageSize() {
    pageSize = parseInt(document.getElementById('page-size').value);
    performSearch(1);
}

function clearSearch() {
    document.getElementById('search-input').value = '';
    resetFilters();
    performSearch(1);
}

function toggleFilters() {
    const filtersPanel = document.getElementById('advanced-filters');
    const toggleBtn = document.getElementById('toggle-filters');
    
    if (filtersPanel.style.display === 'none') {
        filtersPanel.style.display = 'block';
        toggleBtn.textContent = '▲ Advanced Filters';
    } else {
        filtersPanel.style.display = 'none';
        toggleBtn.textContent = '▼ Advanced Filters';
    }
}

function applyFilters() {
    performSearch(1);
}

function resetFilters() {
    document.getElementById('filter-artist').value = '';
    document.getElementById('filter-album').value = '';
    document.getElementById('filter-genre').value = '';
    document.getElementById('filter-year-from').value = '';
    document.getElementById('filter-year-to').value = '';
    document.getElementById('filter-bpm-min').value = '';
    document.getElementById('filter-bpm-max').value = '';
    document.getElementById('filter-key').value = '';
    document.getElementById('filter-size-min').value = '';
    document.getElementById('filter-size-max').value = '';
    document.getElementById('filter-status').value = '';
    document.getElementById('filter-duplicates').value = '';
}

// View switching
function switchView(view) {
    currentView = view;
    
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.getElementById(`tab-${view}`).classList.add('active');
    
    // Hide all views
    document.querySelectorAll('.view-content').forEach(content => {
        content.style.display = 'none';
    });
    
    // Show selected view
    document.getElementById(`view-${view}`).style.display = 'block';
    
    // Load view-specific data
    switch(view) {
        case 'artists':
            loadArtists();
            break;
        case 'albums':
            loadAlbums();
            break;
        case 'folders':
            loadFolders();
            break;
        case 'duplicates':
            loadDuplicates();
            break;
        case 'analytics':
            loadAnalytics();
            break;
    }
}

// Artists view
async function loadArtists() {
    try {
        const response = await fetch('/api/library/artists');
        const data = await response.json();
        
        const grid = document.getElementById('artists-grid');
        grid.innerHTML = data.artists.map(artist => `
            <div class="grid-item" onclick="filterByArtist('${artist.name}')">
                <h3>${artist.name}</h3>
                <p>${artist.track_count} tracks</p>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading artists:', error);
    }
}

function filterByArtist(artist) {
    document.getElementById('filter-artist').value = artist;
    document.getElementById('advanced-filters').style.display = 'block';
    switchView('browse');
    performSearch(1);
}

// Albums view
async function loadAlbums() {
    try {
        const response = await fetch('/api/library/albums');
        const data = await response.json();
        
        const grid = document.getElementById('albums-grid');
        grid.innerHTML = data.albums.map(album => `
            <div class="grid-item" onclick="filterByAlbum('${album.album}', '${album.artist}')">
                <h3>${album.album}</h3>
                <p>${album.artist}</p>
                <p>${album.track_count} tracks${album.year ? ` • ${album.year}` : ''}</p>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading albums:', error);
    }
}

function filterByAlbum(album, artist) {
    document.getElementById('filter-album').value = album;
    document.getElementById('filter-artist').value = artist;
    document.getElementById('advanced-filters').style.display = 'block';
    switchView('browse');
    performSearch(1);
}

// Folders view
async function loadFolders() {
    try {
        const response = await fetch('/api/library/folders');
        const data = await response.json();
        
        const tree = document.getElementById('folder-tree');
        tree.innerHTML = renderFolderTree(data.folders);
    } catch (error) {
        console.error('Error loading folders:', error);
    }
}

function renderFolderTree(folders, level = 0) {
    return folders.map(folder => {
        const padding = level * 20;
        let html = `
            <div class="folder-item" style="padding-left: ${padding}px" 
                 onclick="selectFolder('${folder.path}')">
                📁 ${folder.name}
            </div>
        `;
        
        if (folder.children && folder.children.length > 0) {
            html += renderFolderTree(folder.children, level + 1);
        }
        
        return html;
    }).join('');
}

function selectFolder(path) {
    document.querySelectorAll('.folder-item').forEach(item => {
        item.classList.remove('selected');
    });
    event.target.classList.add('selected');
    
    // Load folder contents
    loadFolderContents(path);
}

async function loadFolderContents(path) {
    // This would load files in the selected folder
    const contents = document.getElementById('folder-contents');
    contents.innerHTML = `<h3>Files in ${path}</h3><p>Loading...</p>`;
    
    // Perform search filtered by path
    document.getElementById('search-input').value = path;
    performSearch(1);
}

// Duplicates view
async function loadDuplicates() {
    try {
        const response = await fetch('/api/duplicates?limit=100');
        const data = await response.json();
        
        // Update summary
        if (window.libraryStats) {
            document.getElementById('dup-groups-count').textContent = 
                window.libraryStats.duplicates?.groups || 0;
            document.getElementById('dup-files-count').textContent = 
                window.libraryStats.duplicates?.total_files || 0;
            document.getElementById('dup-space').textContent = 
                `${window.libraryStats.duplicates?.space_used_gb || 0} GB`;
            document.getElementById('dup-savings').textContent = 
                `${window.libraryStats.duplicates?.potential_savings_gb || 0} GB`;
        }
        
        // Display duplicate groups
        const list = document.getElementById('duplicates-list');
        list.innerHTML = data.duplicates.map((group, index) => `
            <div class="duplicate-group">
                <h4>Duplicate Group ${index + 1} (${group.files.length} files)</h4>
                ${group.files.map((file, idx) => `
                    <div class="duplicate-file ${idx === 0 ? 'best' : ''}">
                        ${idx === 0 ? '✓ Best Quality: ' : ''}
                        ${file.path} (${(file.size / 1024 / 1024).toFixed(2)} MB)
                    </div>
                `).join('')}
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading duplicates:', error);
    }
}

// Analytics view
async function loadAnalytics() {
    if (!window.libraryStats) {
        await loadStatistics();
    }
    
    const stats = window.libraryStats;
    
    // Destroy existing charts
    Object.values(charts).forEach(chart => chart.destroy());
    charts = {};
    
    // Top Artists Chart
    if (stats.top_artists && stats.top_artists.length > 0) {
        const ctx1 = document.getElementById('chart-artists').getContext('2d');
        charts.artists = new Chart(ctx1, {
            type: 'bar',
            data: {
                labels: stats.top_artists.map(a => a.artist),
                datasets: [{
                    label: 'Track Count',
                    data: stats.top_artists.map(a => a.track_count),
                    backgroundColor: '#1db954'
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }
    
    // Genre Distribution
    const ctx2 = document.getElementById('chart-genres').getContext('2d');
    charts.genres = new Chart(ctx2, {
        type: 'doughnut',
        data: {
            labels: ['Rock', 'Electronic', 'Hip Hop', 'Jazz', 'Classical', 'Other'],
            datasets: [{
                data: [30, 25, 20, 10, 5, 10],
                backgroundColor: [
                    '#1db954', '#1aa34a', '#158a3c', 
                    '#10712e', '#0b5820', '#063f12'
                ]
            }]
        },
        options: {
            responsive: true
        }
    });
    
    // Format Distribution
    if (stats.format_distribution) {
        const ctx3 = document.getElementById('chart-formats').getContext('2d');
        const formats = Object.entries(stats.format_distribution);
        charts.formats = new Chart(ctx3, {
            type: 'pie',
            data: {
                labels: formats.map(f => f[0] || 'Unknown'),
                datasets: [{
                    data: formats.map(f => f[1]),
                    backgroundColor: [
                        '#1db954', '#ffa500', '#ff4444', 
                        '#4a9eff', '#9b59b6', '#e74c3c'
                    ]
                }]
            },
            options: {
                responsive: true
            }
        });
    }
    
    // Key Distribution
    if (stats.audio_stats?.key_distribution) {
        const ctx4 = document.getElementById('chart-keys').getContext('2d');
        const keys = Object.entries(stats.audio_stats.key_distribution);
        charts.keys = new Chart(ctx4, {
            type: 'bar',
            data: {
                labels: keys.map(k => k[0]),
                datasets: [{
                    label: 'Track Count',
                    data: keys.map(k => k[1]),
                    backgroundColor: '#4a9eff'
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }
    
    // BPM Distribution (simplified)
    const ctx5 = document.getElementById('chart-bpm').getContext('2d');
    charts.bpm = new Chart(ctx5, {
        type: 'line',
        data: {
            labels: ['60-80', '80-100', '100-120', '120-140', '140-160', '160+'],
            datasets: [{
                label: 'Track Count',
                data: [5, 15, 30, 25, 15, 10],
                borderColor: '#ffa500',
                backgroundColor: 'rgba(255, 165, 0, 0.1)'
            }]
        },
        options: {
            responsive: true
        }
    });
    
    // Year Distribution (simplified)
    const ctx6 = document.getElementById('chart-years').getContext('2d');
    charts.years = new Chart(ctx6, {
        type: 'line',
        data: {
            labels: ['2010', '2012', '2014', '2016', '2018', '2020', '2022', '2024'],
            datasets: [{
                label: 'Releases',
                data: [10, 15, 22, 30, 28, 35, 40, 25],
                borderColor: '#9b59b6',
                backgroundColor: 'rgba(155, 89, 182, 0.1)'
            }]
        },
        options: {
            responsive: true
        }
    });
}

// Load genres for filter dropdown
async function loadGenres() {
    try {
        const response = await fetch('/api/library/genres');
        const data = await response.json();
        
        const select = document.getElementById('filter-genre');
        select.innerHTML = '<option value="">All Genres</option>' +
            data.genres.map(genre => 
                `<option value="${genre.name}">${genre.name} (${genre.track_count})</option>`
            ).join('');
    } catch (error) {
        console.error('Error loading genres:', error);
    }
}

// File details modal
async function showFileDetails(fileId) {
    // This would fetch and display detailed file information
    const modal = document.getElementById('file-modal');
    const details = document.getElementById('file-details');
    
    // Find file in current results
    const file = searchResults.find(f => f.id === fileId);
    
    if (file) {
        details.innerHTML = `
            <div class="detail-row">
                <div class="detail-label">Source Path:</div>
                <div class="detail-value">${file.source_path}</div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Target Path:</div>
                <div class="detail-value">${file.target_path || 'Not migrated'}</div>
            </div>
            <div class="detail-row">
                <div class="detail-label">File Size:</div>
                <div class="detail-value">${file.file_size_mb} MB</div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Status:</div>
                <div class="detail-value">
                    <span class="status-badge status-${file.status}">${file.status}</span>
                </div>
            </div>
            ${file.metadata ? `
                <div class="detail-row">
                    <div class="detail-label">Artist:</div>
                    <div class="detail-value">${file.metadata.artist || '-'}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Title:</div>
                    <div class="detail-value">${file.metadata.title || '-'}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Album:</div>
                    <div class="detail-value">${file.metadata.album || '-'}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Genre:</div>
                    <div class="detail-value">${file.metadata.genre || '-'}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Year:</div>
                    <div class="detail-value">${file.metadata.year || '-'}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Duration:</div>
                    <div class="detail-value">${file.metadata.duration ? 
                        `${Math.floor(file.metadata.duration / 60)}:${(file.metadata.duration % 60).toString().padStart(2, '0')}` : 
                        '-'}</div>
                </div>
            ` : ''}
            ${file.audio_analysis ? `
                <div class="detail-row">
                    <div class="detail-label">BPM:</div>
                    <div class="detail-value">${file.audio_analysis.bpm ? 
                        Math.round(file.audio_analysis.bpm) : '-'}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Key Signature:</div>
                    <div class="detail-value">${file.audio_analysis.key_signature || '-'}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Energy:</div>
                    <div class="detail-value">${file.audio_analysis.energy || '-'}</div>
                </div>
            ` : ''}
            <div class="detail-row">
                <div class="detail-label">Indexed At:</div>
                <div class="detail-value">${file.indexed_at ? 
                    new Date(file.indexed_at).toLocaleString() : '-'}</div>
            </div>
            ${file.migrated_at ? `
                <div class="detail-row">
                    <div class="detail-label">Migrated At:</div>
                    <div class="detail-value">${new Date(file.migrated_at).toLocaleString()}</div>
                </div>
            ` : ''}
        `;
        
        modal.classList.remove('hidden');
    }
}

function closeFileModal() {
    document.getElementById('file-modal').classList.add('hidden');
}