// ============================================================
// SiloGenius — Main JavaScript
// ============================================================

// --- Sidebar Toggle ---
const sidebar = document.getElementById('sidebar');
const mainWrapper = document.getElementById('mainWrapper');
const hamburger = document.getElementById('hamburger');

hamburger.addEventListener('click', () => {
    sidebar.classList.toggle('collapsed');
    mainWrapper.classList.toggle('collapsed');
});

// --- Page Navigation ---
const navItems = document.querySelectorAll('.nav-item[data-page]');
const pages = document.querySelectorAll('.page');
const topbarTitle = document.querySelector('.topbar-title');

const pageTitles = {
    'silo': 'Silo Generator',
    'outlines': 'Outlines',
    'articles': 'Article Writer',
    'media': 'Media',
    'publisher': 'Publisher',
    'projects': 'My Projects',
    'settings': 'Settings'
};

navItems.forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const page = item.dataset.page;

        // Update active nav
        navItems.forEach(n => n.classList.remove('active'));
        item.classList.add('active');

        // Show correct page
        pages.forEach(p => p.classList.remove('active'));
        const targetPage = document.getElementById(`page-${page}`);
        if (targetPage) targetPage.classList.add('active');

        // Update topbar title
        if (pageTitles[page]) topbarTitle.textContent = pageTitles[page];
    });
});

// --- Pass Selector Pills ---
const pills = document.querySelectorAll('.pill');
let selectedPasses = 1;

pills.forEach(pill => {
    pill.addEventListener('click', () => {
        pills.forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        selectedPasses = parseInt(pill.dataset.value);
    });
});

// --- Table State ---
let tableColumns = [];
let tableData = [];

// --- Generate Silo ---
const generateBtn = document.getElementById('generateBtn');
const keyword = document.getElementById('keyword');
const resultsCard = document.getElementById('resultsCard');
const tableHeaders = document.getElementById('tableHeaders');
const tableBody = document.getElementById('tableBody');
const tableCount = document.getElementById('tableCount');

generateBtn.addEventListener('click', async () => {
    const kw = keyword.value.trim();
    if (!kw) {
        keyword.focus();
        return;
    }

    generateBtn.disabled = true;
    generateBtn.innerHTML = '<span>Generating...</span>';

    // Clear previous results
    tableColumns = [];
    tableData = [];
    tableHeaders.innerHTML = '';
    tableBody.innerHTML = '';
    tableCount.textContent = '0 articles';
    resultsCard.style.display = 'none';

    try {
        const response = await fetch('/generate-silo', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keyword: kw, passes: selectedPasses })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        handleStreamEvent(data);
                    } catch (e) {}
                }
            }
        }
    } catch (err) {
        console.error('Generate error:', err);
    }

    generateBtn.disabled = false;
    generateBtn.innerHTML = '<span>Generate Silo</span>';
});

function handleStreamEvent(data) {
    if (data.type === 'headers') {
        tableColumns = data.columns;
        buildTableHeaders(data.columns);
        resultsCard.style.display = 'block';
    }

    if (data.type === 'row') {
        tableData.push(data.row);
        addTableRow(data.row, tableData.length - 1);
        tableCount.textContent = `${tableData.length} article${tableData.length !== 1 ? 's' : ''}`;
    }

    if (data.type === 'done') {
        tableCount.textContent = `${tableData.length} articles — complete`;
    }
}

function buildTableHeaders(columns) {
    tableHeaders.innerHTML = '';

    columns.forEach(col => {
        const th = document.createElement('th');
        th.textContent = col;
        tableHeaders.appendChild(th);
    });

    // Delete column header
    const thDel = document.createElement('th');
    thDel.textContent = '';
    tableHeaders.appendChild(thDel);
}

function addTableRow(rowData, index) {
    const tr = document.createElement('tr');
    tr.dataset.index = index;

    tableColumns.forEach(col => {
        const td = document.createElement('td');
        td.contentEditable = 'true';
        td.textContent = rowData[col] || '';
        td.addEventListener('blur', () => {
            tableData[index][col] = td.textContent.trim();
        });
        tr.appendChild(td);
    });

    // Delete button
    const tdDel = document.createElement('td');
    const delBtn = document.createElement('button');
    delBtn.className = 'delete-row-btn';
    delBtn.textContent = '✕';
    delBtn.title = 'Delete row';
    delBtn.addEventListener('click', () => {
        tableData.splice(index, 1);
        tr.remove();
        tableCount.textContent = `${tableData.length} articles`;
    });
    tdDel.appendChild(delBtn);
    tr.appendChild(tdDel);

    tableBody.appendChild(tr);
}

// --- Add Row ---
document.getElementById('addRowBtn').addEventListener('click', () => {
    if (tableColumns.length === 0) return;
    const emptyRow = {};
    tableColumns.forEach(col => emptyRow[col] = '');
    tableData.push(emptyRow);
    addTableRow(emptyRow, tableData.length - 1);
    tableCount.textContent = `${tableData.length} articles`;
});

// --- Load CSV ---
document.getElementById('loadCsvBtn').addEventListener('click', () => {
    document.getElementById('csvFileInput').click();
});

document.getElementById('csvFileInput').addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (evt) => {
        const text = evt.target.result;
        parseCSV(text);
    };
    reader.readAsText(file);
});

function parseCSV(text) {
    const lines = text.trim().split('\n').filter(l => l.trim() && !l.match(/^[\|\-\s]+$/));
    if (lines.length < 2) return;

    const delimiter = '|';
    const headers = lines[0].split(delimiter).map(h => h.trim()).filter(h => h);

    tableColumns = headers;
    tableData = [];
    tableHeaders.innerHTML = '';
    tableBody.innerHTML = '';

    buildTableHeaders(headers);

    lines.slice(1).forEach(line => {
        const values = line.split(delimiter).map(v => v.trim());
        const row = {};
        headers.forEach((h, i) => row[h] = values[i] || '');
        tableData.push(row);
        addTableRow(row, tableData.length - 1);
    });

    tableCount.textContent = `${tableData.length} articles — loaded`;
    resultsCard.style.display = 'block';
}

// --- Export CSV ---
document.getElementById('exportBtn').addEventListener('click', () => {
    if (tableData.length === 0) return;

    const lines = [tableColumns.join('|')];
    tableData.forEach(row => {
        lines.push(tableColumns.map(col => row[col] || '').join('|'));
    });

    const blob = new Blob([lines.join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `silogenius-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
});

// ============================================================
// Settings Page
// ============================================================

let selectedProvider = 'openrouter';
let retrievedModels = [];

const providerKeys = {
    openrouter: 'openrouter_key',
    anthropic: 'anthropic_key',
    openai: 'openai_key',
    google: 'google_key'
};

const providerLabels = {
    openrouter: 'OpenRouter API Key',
    anthropic: 'Anthropic API Key',
    openai: 'OpenAI API Key',
    google: 'Google API Key'
};

// Load current settings when settings page opens
async function loadSettings() {
    try {
        const response = await fetch('/get-settings');
        const settings = await response.json();

        // Store settings globally
        window.currentSettings = settings;

        // Populate WordPress fields
        if (document.getElementById('wpUrl')) {
            document.getElementById('wpUrl').value = settings.wp_url || '';
            document.getElementById('wpUsername').value = settings.wp_username || '';
            document.getElementById('wpPassword').value = settings.wp_app_password || '';
        }

        // Set current provider key field
        updateProviderKeyField(selectedProvider, settings);

        // Set model dropdowns if we have saved values
        if (settings.silo_model) setSavedModel('siloModel', settings.silo_model);
        if (settings.article_model) setSavedModel('articleModel', settings.article_model);
        if (settings.image_model) setSavedModel('imageModel', settings.image_model);

    } catch (e) {
        console.error('Could not load settings:', e);
    }
}

function setSavedModel(selectId, value) {
    const select = document.getElementById(selectId);
    if (!select) return;
    // Check if option exists, if not add it
    let found = false;
    for (let opt of select.options) {
        if (opt.value === value) { opt.selected = true; found = true; break; }
    }
    if (!found && value) {
        const opt = document.createElement('option');
        opt.value = value;
        opt.textContent = value;
        opt.selected = true;
        select.appendChild(opt);
    }
}

function updateProviderKeyField(provider, settings) {
    const keyInput = document.getElementById('currentApiKey');
    const keyLabel = document.getElementById('apiKeyLabel');
    if (!keyInput || !keyLabel) return;
    keyLabel.textContent = providerLabels[provider] || 'API Key';
    const settingsKey = providerKeys[provider];
    keyInput.value = settings ? (settings[settingsKey] || '') : '';
}

// Provider pill selection
document.addEventListener('click', (e) => {
    const providerPill = e.target.closest('#providerSelector .pill');
    if (providerPill) {
        document.querySelectorAll('#providerSelector .pill').forEach(p => p.classList.remove('active'));
        providerPill.classList.add('active');
        selectedProvider = providerPill.dataset.provider;
        updateProviderKeyField(selectedProvider, window.currentSettings);
    }
});

// Retrieve Models button
document.addEventListener('click', async (e) => {
    if (e.target.closest('#retrieveModelsBtn')) {
        const btn = document.getElementById('retrieveModelsBtn');
        const apiKey = document.getElementById('currentApiKey').value.trim();

        if (!apiKey) {
            alert('Please enter an API key first');
            return;
        }

        btn.textContent = '⏳ Retrieving...';
        btn.disabled = true;

        try {
            const response = await fetch('/get-models', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider: selectedProvider, api_key: apiKey })
            });
            const data = await response.json();

            if (data.error) {
                alert(`Error: ${data.error}`);
            } else {
                retrievedModels = data.models;
                populateModelDropdowns(data.models);
                btn.textContent = `✅ ${data.models.length} models loaded`;
            }
        } catch (err) {
            alert('Failed to retrieve models');
        }

        btn.disabled = false;
        setTimeout(() => { btn.textContent = '🔍 Retrieve Models'; }, 3000);
    }
});

function populateModelDropdowns(models) {
    const selects = ['siloModel', 'articleModel', 'imageModel'];
    const savedValues = {
        siloModel: window.currentSettings?.silo_model || '',
        articleModel: window.currentSettings?.article_model || '',
        imageModel: window.currentSettings?.image_model || ''
    };

    selects.forEach(id => {
        const select = document.getElementById(id);
        if (!select) return;
        const currentVal = select.value || savedValues[id];
        select.innerHTML = '<option value="">— select a model —</option>';
        models.forEach(model => {
            const opt = document.createElement('option');
            opt.value = model;
            opt.textContent = model;
            if (model === currentVal) opt.selected = true;
            select.appendChild(opt);
        });
    });
}

// Test WordPress Connection
document.addEventListener('click', async (e) => {
    if (e.target.closest('#testWpBtn')) {
        const btn = document.getElementById('testWpBtn');
        const status = document.getElementById('wpStatus');

        btn.textContent = '⏳ Testing...';
        btn.disabled = true;
        status.textContent = '';
        status.className = 'connection-status';

        try {
            const response = await fetch('/test-wordpress', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    wp_url: document.getElementById('wpUrl').value,
                    wp_username: document.getElementById('wpUsername').value,
                    wp_app_password: document.getElementById('wpPassword').value
                })
            });
            const data = await response.json();

            if (data.success) {
                status.textContent = '✅ ' + data.message;
                status.className = 'connection-status success';
            } else {
                status.textContent = '❌ ' + data.error;
                status.className = 'connection-status error';
            }
        } catch (err) {
            status.textContent = '❌ Connection failed';
            status.className = 'connection-status error';
        }

        btn.disabled = false;
        btn.textContent = '🔌 Test Connection';
    }
});

// Save Settings
document.addEventListener('click', async (e) => {
    if (e.target.closest('#saveSettingsBtn')) {
        const btn = document.getElementById('saveSettingsBtn');
        const status = document.getElementById('saveStatus');

        btn.textContent = '⏳ Saving...';
        btn.disabled = true;

        // Build settings object
        const settingsData = {
            wp_url: document.getElementById('wpUrl')?.value || '',
            wp_username: document.getElementById('wpUsername')?.value || '',
            wp_app_password: document.getElementById('wpPassword')?.value || '',
            silo_model: document.getElementById('siloModel')?.value || '',
            article_model: document.getElementById('articleModel')?.value || '',
            image_model: document.getElementById('imageModel')?.value || '',
        };

        // Save current provider key
        const keyInput = document.getElementById('currentApiKey');
        if (keyInput && keyInput.value) {
            settingsData[providerKeys[selectedProvider]] = keyInput.value;
        }

        try {
            const response = await fetch('/save-settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settingsData)
            });
            const data = await response.json();

            if (data.success) {
                status.textContent = '✅ Settings saved!';
                setTimeout(() => { status.textContent = ''; }, 3000);
            } else {
                status.textContent = '❌ ' + data.error;
            }
        } catch (err) {
            status.textContent = '❌ Save failed';
        }

        btn.disabled = false;
        btn.textContent = '💾 Save Settings';
    }
});

// Load settings when navigating to settings page
document.addEventListener('click', (e) => {
    const navItem = e.target.closest('.nav-item[data-page="settings"]');
    if (navItem) {
        setTimeout(loadSettings, 100);
    }
});

// ============================================================
// Article Writer Page
// ============================================================

let loadedCsvPath = '';
let loadedArticles = [];

// Load CSV button
document.addEventListener('click', (e) => {
    if (e.target.closest('#loadArticleCsvBtn')) {
        document.getElementById('articleCsvInput').click();
    }
});

document.addEventListener('change', (e) => {
    if (e.target.id === 'articleCsvInput') {
        const file = e.target.files[0];
        if (!file) return;

        // Store the file path hint and read contents
        loadedCsvPath = file.name;
        const reader = new FileReader();
        reader.onload = (evt) => {
            parseArticleCSV(evt.target.result, file.name);
        };
        reader.readAsText(file);
    }
});

function parseArticleCSV(text, filename) {
    const lines = text.trim().split('\n').filter(l => l.trim() && !l.match(/^[\|\-\s]+$/));
    if (lines.length < 2) return;

    const headers = lines[0].split('|').map(h => h.trim()).filter(h => h);
    loadedArticles = [];

    lines.slice(1).forEach(line => {
        const values = line.split('|').map(v => v.trim());
        const row = {};
        headers.forEach((h, i) => row[h] = values[i] || '');
        loadedArticles.push(row);
    });

    // Show loaded filename
    const nameEl = document.getElementById('csvLoadedName');
    nameEl.textContent = `✅ ${filename} — ${loadedArticles.length} articles`;

    // Store full path for backend — use silogenius silos folder
    loadedCsvPath = `${window.location.origin}/get-csv-path?name=${encodeURIComponent(filename)}`;

    renderArticleList(loadedArticles);
}

function renderArticleList(articles) {
    const list = document.getElementById('articleList');
    const countEl = document.getElementById('articleCount');
    const card = document.getElementById('articleListCard');

    list.innerHTML = '';
    countEl.textContent = `${articles.length} articles`;
    card.style.display = 'block';

    articles.forEach((row, i) => {
        const title = row['Title'] || row['title'] || `Article ${i + 1}`;
        const type = row['Article Type'] || row['article_type'] || '';
        const size = row['Article Size'] || row['article_size'] || '';
        const sizeShort = size.split(' ')[0] || '';

        const item = document.createElement('div');
        item.className = 'article-item';
        item.innerHTML = `
            <input type="checkbox" class="article-checkbox" value="${title}" checked>
            <span class="article-type-badge">${type}</span>
            <span class="article-title-text">${title}</span>
            <span class="article-size-text">${sizeShort}</span>
        `;
        list.appendChild(item);
    });
}

// Select All
document.addEventListener('change', (e) => {
    if (e.target.id === 'selectAllArticles') {
        document.querySelectorAll('.article-checkbox').forEach(cb => {
            cb.checked = e.target.checked;
        });
    }
});

function getSelectedTitles() {
    return Array.from(document.querySelectorAll('.article-checkbox:checked')).map(cb => cb.value);
}

function getSilosCsvPath(filename) {
    // Map filename to full path in silogenius/silos/
    const base = filename.replace(/^.*[\\\/]/, '');
    return `/home/${location.hostname === 'localhost' ? 'greg' : 'user'}/silogenius/silos/${base}`;
}

// Action buttons
document.addEventListener('click', async (e) => {
    if (e.target.closest('#genOutlinesBtn')) {
        await runArticleAction('outlines');
    }
    if (e.target.closest('#writeArticlesBtn')) {
        await runArticleAction('articles');
    }
    if (e.target.closest('#fullPipelineBtn')) {
        await runArticleAction('full');
    }
});

async function runArticleAction(mode) {
    const selected = getSelectedTitles();
    if (selected.length === 0) {
        alert('Please select at least one article');
        return;
    }

    // Find the actual CSV path in silos folder
    const csvFilename = document.getElementById('csvLoadedName').textContent.split('—')[0].replace('✅', '').trim();
    const csvPath = getSilosCsvPath(csvFilename);

    const progressCard = document.getElementById('progressCard');
    const progressLog = document.getElementById('progressLog');
    const progressBar = document.getElementById('progressBar');

    progressCard.style.display = 'block';
    progressLog.innerHTML = '';
    progressBar.style.width = '0%';

    progressCard.scrollIntoView({ behavior: 'smooth' });

    if (mode === 'outlines' || mode === 'full') {
        await streamAction('/generate-outlines', csvPath, selected, progressLog, progressBar, mode === 'full' ? 0.5 : 1);
    }

    if (mode === 'articles' || mode === 'full') {
        await streamAction('/write-articles', csvPath, selected, progressLog, progressBar, 1);
    }
}

async function streamAction(endpoint, csvPath, selected, logEl, barEl, barMultiplier) {
    const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ csv_path: csvPath, selected: selected })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                try {
                    const data = JSON.parse(line.slice(6));
                    handleProgressEvent(data, logEl, barEl, barMultiplier);
                } catch (e) {}
            }
        }
    }
}

function handleProgressEvent(data, logEl, barEl, barMultiplier) {
    if (data.type === 'progress') {
        const pct = Math.round((data.current / data.total) * 100 * barMultiplier);
        barEl.style.width = `${pct}%`;

        const statusMap = {
            'generating': '⠋ Generating outline...',
            'writing': '⠋ Writing article...',
            'generating outline': '⠋ Generating outline first...',
            'done': data.words ? `✅ Done — ${data.words.toLocaleString()} words` : '✅ Done',
            'failed': '❌ Failed'
        };

        const item = document.createElement('div');
        item.className = `progress-item ${data.status === 'done' ? 'done' : data.status === 'failed' ? 'failed' : data.status === 'writing' ? 'writing' : 'generating'}`;
        item.innerHTML = `
            <span class="progress-num">[${data.current}/${data.total}]</span>
            <span class="progress-title">${data.title}</span>
            <span class="progress-meta">${statusMap[data.status] || data.status}</span>
        `;
        logEl.appendChild(item);
        logEl.scrollTop = logEl.scrollHeight;
    }

    if (data.type === 'done') {
        barEl.style.width = '100%';
    }
}

// ============================================================
// Publisher Page
// ============================================================

let publisherArticles = [];
let publisherCsvPath = '';
let publishStatus = 'draft';

// Load CSV
document.addEventListener('click', (e) => {
    if (e.target.closest('#loadPublisherCsvBtn')) {
        document.getElementById('publisherCsvInput').click();
    }
});

document.addEventListener('change', (e) => {
    if (e.target.id === 'publisherCsvInput') {
        const file = e.target.files[0];
        if (!file) return;
        publisherCsvPath = file.name;
        const reader = new FileReader();
        reader.onload = (evt) => parsePublisherCSV(evt.target.result, file.name);
        reader.readAsText(file);
    }
});

function parsePublisherCSV(text, filename) {
    const lines = text.trim().split('\n').filter(l => l.trim() && !l.match(/^[\|\-\s]+$/));
    if (lines.length < 2) return;

    const headers = lines[0].split('|').map(h => h.trim()).filter(h => h);
    publisherArticles = [];

    lines.slice(1).forEach(line => {
        const values = line.split('|').map(v => v.trim());
        const row = {};
        headers.forEach((h, i) => row[h] = values[i] || '');
        publisherArticles.push(row);
    });

    document.getElementById('publisherCsvName').textContent = `✅ ${filename} — ${publisherArticles.length} articles`;
    publisherCsvPath = getSilosCsvPath(filename);

    checkAndRenderPublisherList();
}

async function checkAndRenderPublisherList() {
    const nameEl = document.getElementById('publisherCsvName');
    nameEl.textContent = nameEl.textContent.replace('✅', '⏳ Checking status...');

    const titles = publisherArticles.map(r => r['Title'] || r['title'] || '').filter(t => t);

    try {
        const response = await fetch('/check-publish-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ articles: titles })
        });
        const statuses = await response.json();
        renderPublisherList(statuses);
        nameEl.textContent = nameEl.textContent.replace('⏳ Checking status...', '✅');
    } catch (e) {
        renderPublisherList({});
    }
}

function renderPublisherList(statuses) {
    const list = document.getElementById('publisherList');
    const countEl = document.getElementById('publisherCount');
    const card = document.getElementById('publisherListCard');

    list.innerHTML = '';
    card.style.display = 'block';

    let readyCount = 0;

    publisherArticles.forEach((row, i) => {
        const title = row['Title'] || row['title'] || `Article ${i + 1}`;
        const type = row['Article Type'] || '';
        const articleStatus = statuses[title] || { status: 'missing' };

        const isReady = articleStatus.status === 'ready';
        const isPublished = articleStatus.status === 'published';
        const isMissing = articleStatus.status === 'missing';

        if (isReady) readyCount++;

        const badgeClass = isPublished ? 'published' : isReady ? 'ready' : 'missing';
        const badgeText = isPublished ? '🌐 Published' : isReady ? '✅ Ready' : '⚠️ No Draft';
        const disabled = !isReady ? 'disabled' : '';
        const disabledClass = !isReady ? 'disabled' : '';
        const postLink = isPublished && articleStatus.post_url
            ? `<a href="${articleStatus.post_url}" target="_blank" class="post-link">View →</a>`
            : '';

        const item = document.createElement('div');
        item.className = `article-item ${disabledClass}`;
        item.innerHTML = `
            <input type="checkbox" class="publisher-checkbox" value="${title}" ${isReady ? 'checked' : ''} ${disabled}>
            <span class="article-type-badge">${type}</span>
            <span class="article-title-text">${title}</span>
            ${postLink}
            <span class="publish-status-badge ${badgeClass}">${badgeText}</span>
        `;
        list.appendChild(item);
    });

    countEl.textContent = `${publisherArticles.length} articles — ${readyCount} ready`;
}

// Select All Ready
document.addEventListener('change', (e) => {
    if (e.target.id === 'selectAllPublisher') {
        document.querySelectorAll('.publisher-checkbox:not([disabled])').forEach(cb => {
            cb.checked = e.target.checked;
        });
    }
});

// Publish status pills
document.addEventListener('click', (e) => {
    const pill = e.target.closest('#publishStatusSelector .pill');
    if (pill) {
        document.querySelectorAll('#publishStatusSelector .pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        publishStatus = pill.dataset.value;
    }
});

// Publish button
document.addEventListener('click', async (e) => {
    if (e.target.closest('#publishBtn')) {
        const selected = Array.from(document.querySelectorAll('.publisher-checkbox:checked')).map(cb => cb.value);

        if (selected.length === 0) {
            alert('Please select at least one article to publish');
            return;
        }

        if (publishStatus === 'publish') {
            if (!confirm(`You are about to publish ${selected.length} article(s) LIVE to WordPress. Are you sure?`)) {
                return;
            }
        }

        const progressCard = document.getElementById('publisherProgressCard');
        const progressLog = document.getElementById('publisherProgressLog');
        const progressBar = document.getElementById('publisherProgressBar');

        progressCard.style.display = 'block';
        progressLog.innerHTML = '';
        progressBar.style.width = '0%';
        progressCard.scrollIntoView({ behavior: 'smooth' });

        const response = await fetch('/publish-articles', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                csv_path: publisherCsvPath,
                selected: selected,
                publish_status: publishStatus
            })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        handlePublishEvent(data, progressLog, progressBar);
                    } catch (e) {}
                }
            }
        }

        // Refresh status after publishing
        checkAndRenderPublisherList();
    }
});

function handlePublishEvent(data, logEl, barEl) {
    if (data.type === 'progress') {
        const pct = Math.round((data.current / data.total) * 100);
        barEl.style.width = `${pct}%`;

        const item = document.createElement('div');
        const isDone = data.status === 'done';
        const isFailed = data.status === 'failed';
        item.className = `progress-item ${isDone ? 'done' : isFailed ? 'failed' : 'writing'}`;

        let meta = '';
        if (isDone && data.post_url) {
            meta = `<a href="${data.post_url}" target="_blank" class="post-link">View Post →</a>`;
        } else if (isFailed) {
            meta = `❌ ${data.error || 'Failed'}`;
        } else {
            meta = '⠋ Publishing...';
        }

        item.innerHTML = `
            <span class="progress-num">[${data.current}/${data.total}]</span>
            <span class="progress-title">${data.title}</span>
            <span class="progress-meta">${meta}</span>
        `;
        logEl.appendChild(item);
        logEl.scrollTop = logEl.scrollHeight;
    }

    if (data.type === 'done') {
        barEl.style.width = '100%';
    }
}

// ============================================================
// Media Page
// ============================================================

let mediaArticles = [];
let mediaCsvPath = '';
let mediaLayout = 'every2';

// Load image model from settings on page load
async function loadMediaSettings() {
    try {
        const response = await fetch('/get-settings');
        const settings = await response.json();
        const modelEl = document.getElementById('imageModelDisplay');
        if (modelEl) {
            modelEl.textContent = settings.image_model || '— set in Settings —';
        }
    } catch (e) {}
}

// Navigate to media page
document.addEventListener('click', (e) => {
    const navItem = e.target.closest('.nav-item[data-page="media"]');
    if (navItem) setTimeout(loadMediaSettings, 100);
});

// Layout selector
document.addEventListener('click', (e) => {
    const pill = e.target.closest('#layoutSelector .pill');
    if (pill) {
        document.querySelectorAll('#layoutSelector .pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        mediaLayout = pill.dataset.value;
        updatePromptPreview();
    }
});

// Prompt preview updater
function updatePromptPreview() {
    const preview = document.getElementById('promptPreview');
    if (!preview) return;

    const sampleTitle = mediaArticles.length > 0
        ? (mediaArticles[0]['Title'] || 'Your Article Title')
        : 'Your Article Title';

    const size = document.getElementById('featuredSize')?.value || '1344x768';
    const [w, h] = size.split('x');
    const ar = `${w}:${h}`;
    const style = document.getElementById('customStyle')?.value ||
                  document.getElementById('imageStyle')?.value || 'None';
    const additional = document.getElementById('additionalInstructions')?.value || '';
    const brand = document.getElementById('brandName')?.value || '';

    let prompt = `${sampleTitle} AR ${ar}`;
    if (style && style.toLowerCase() !== 'none') prompt += ` in ${style} style`;
    if (additional) prompt += ` ${additional}`;
    if (brand) prompt += ` with ${brand} stylish brand`;

    preview.textContent = prompt;
}

// Update preview on any settings change
['featuredSize', 'inlineSize', 'imageStyle', 'customStyle', 'additionalInstructions', 'brandName'].forEach(id => {
    document.addEventListener('input', (e) => {
        if (e.target.id === id) updatePromptPreview();
    });
    document.addEventListener('change', (e) => {
        if (e.target.id === id) updatePromptPreview();
    });
});

// Load CSV
document.addEventListener('click', (e) => {
    if (e.target.closest('#loadMediaCsvBtn')) {
        document.getElementById('mediaCsvInput').click();
    }
});

document.addEventListener('change', (e) => {
    if (e.target.id === 'mediaCsvInput') {
        const file = e.target.files[0];
        if (!file) return;
        mediaCsvPath = getSilosCsvPath(file.name);
        const reader = new FileReader();
        reader.onload = (evt) => parseMediaCSV(evt.target.result, file.name);
        reader.readAsText(file);
    }
});

function parseMediaCSV(text, filename) {
    const lines = text.trim().split('\n').filter(l => l.trim() && !l.match(/^[\|\-\s]+$/));
    if (lines.length < 2) return;

    const headers = lines[0].split('|').map(h => h.trim()).filter(h => h);
    mediaArticles = [];

    lines.slice(1).forEach(line => {
        const values = line.split('|').map(v => v.trim());
        const row = {};
        headers.forEach((h, i) => row[h] = values[i] || '');
        mediaArticles.push(row);
    });

    document.getElementById('mediaCsvName').textContent = `✅ ${filename} — ${mediaArticles.length} articles`;
    checkAndRenderMediaList();
    updatePromptPreview();
}

async function checkAndRenderMediaList() {
    const titles = mediaArticles.map(r => r['Title'] || '').filter(t => t);
    let statuses = {};

    try {
        const response = await fetch('/check-publish-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ articles: titles })
        });
        statuses = await response.json();
    } catch (e) {}

    const list = document.getElementById('mediaArticleList');
    const countEl = document.getElementById('mediaArticleCount');
    const wrapper = document.getElementById('mediaArticleListWrapper');

    list.innerHTML = '';
    wrapper.style.display = 'block';

    let draftCount = 0;

    mediaArticles.forEach((row, i) => {
        const title = row['Title'] || `Article ${i + 1}`;
        const type = row['Article Type'] || '';
        const size = (row['Article Size'] || '').split(' ')[0];
        const articleStatus = statuses[title] || { status: 'missing' };
        const hasDraft = articleStatus.status === 'ready' || articleStatus.status === 'published';

        if (hasDraft) draftCount++;

        const item = document.createElement('div');
        item.className = `article-item ${!hasDraft ? 'disabled' : ''}`;
        item.innerHTML = `
            <input type="checkbox" class="media-checkbox" value="${title}" ${hasDraft ? 'checked' : 'disabled'}>
            <span class="article-type-badge">${type}</span>
            <span class="article-title-text">${title}</span>
            <span class="article-size-text">${size}</span>
            <span class="publish-status-badge ${hasDraft ? 'ready' : 'missing'}">${hasDraft ? '✅ Has Draft' : '⚠️ No Draft'}</span>
        `;
        list.appendChild(item);
    });

    countEl.textContent = `${mediaArticles.length} articles — ${draftCount} with drafts`;
}

// Select all with drafts
document.addEventListener('change', (e) => {
    if (e.target.id === 'selectAllMedia') {
        document.querySelectorAll('.media-checkbox:not([disabled])').forEach(cb => {
            cb.checked = e.target.checked;
        });
    }
});

// Process media button
document.addEventListener('click', async (e) => {
    if (e.target.closest('#processMediaBtn')) {
        const selected = Array.from(document.querySelectorAll('.media-checkbox:checked')).map(cb => cb.value);

        if (selected.length === 0) {
            alert('Please select at least one article');
            return;
        }

        const style = document.getElementById('customStyle')?.value ||
                      document.getElementById('imageStyle')?.value || 'None';

        const payload = {
            csv_path: mediaCsvPath,
            selected: selected,
            featured_size: document.getElementById('featuredSize')?.value || '1344x768',
            inline_size: document.getElementById('inlineSize')?.value || '1344x768',
            style: style,
            additional: document.getElementById('additionalInstructions')?.value || '',
            brand: document.getElementById('brandName')?.value || '',
            alt_mode: document.querySelector('input[name="altMode"]:checked')?.value || 'keyword',
            layout: mediaLayout
        };

        const progressCard = document.getElementById('mediaProgressCard');
        const progressLog = document.getElementById('mediaProgressLog');
        const progressBar = document.getElementById('mediaProgressBar');

        progressCard.style.display = 'block';
        progressLog.innerHTML = '';
        progressBar.style.width = '0%';
        progressCard.scrollIntoView({ behavior: 'smooth' });

        const response = await fetch('/process-media', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        handleMediaProgressEvent(data, progressLog, progressBar);
                    } catch (err) {}
                }
            }
        }
    }
});

function handleMediaProgressEvent(data, logEl, barEl) {
    if (data.type === 'progress') {
        const pct = Math.round((data.current / data.total) * 100);
        barEl.style.width = `${pct}%`;

        const statusLabels = {
            'starting': '⠋ Starting...',
            'featured image': '🖼️ Generating featured image...',
            'featured done': `✅ Featured image uploaded (ID: ${data.media_id})`,
            'done': `✅ Done — ${data.images || 0} images uploaded`,
            'failed': `❌ ${data.error || 'Failed'}`
        };

        // Handle inline image status
        let label = statusLabels[data.status] || data.status;
        if (data.status && data.status.startsWith('inline image')) {
            label = `🖼️ Generating ${data.status}...`;
        }

        const item = document.createElement('div');
        const isDone = data.status === 'done';
        const isFailed = data.status === 'failed';
        item.className = `progress-item ${isDone ? 'done' : isFailed ? 'failed' : 'generating'}`;
        item.innerHTML = `
            <span class="progress-num">[${data.current}/${data.total}]</span>
            <span class="progress-title">${data.title}</span>
            <span class="progress-meta">${label}</span>
        `;
        logEl.appendChild(item);
        logEl.scrollTop = logEl.scrollHeight;
    }

    if (data.type === 'done') {
        barEl.style.width = '100%';
    }
}

// ============================================================
// Projects Page
// ============================================================

// Load projects when navigating to projects page
document.addEventListener('click', (e) => {
    const navItem = e.target.closest('.nav-item[data-page="projects"]');
    if (navItem) setTimeout(loadProjects, 100);
});

// Refresh button
document.addEventListener('click', (e) => {
    if (e.target.closest('#refreshProjectsBtn')) loadProjects();
});

async function loadProjects() {
    const grid = document.getElementById('projectsGrid');
    if (!grid) return;
    grid.innerHTML = '<div class="projects-loading">Loading projects...</div>';

    try {
        const response = await fetch('/get-projects');
        const data = await response.json();

        if (data.error) {
            grid.innerHTML = `<div class="projects-empty">Error: ${data.error}</div>`;
            return;
        }

        if (data.projects.length === 0) {
            grid.innerHTML = `<div class="projects-empty">No projects yet — generate a silo to get started!</div>`;
            return;
        }

        grid.innerHTML = '';
        data.projects.forEach(project => {
            grid.appendChild(createProjectCard(project));
        });

    } catch (e) {
        grid.innerHTML = '<div class="projects-empty">Failed to load projects</div>';
    }
}

function createProjectCard(project) {
    const card = document.createElement('div');
    card.className = 'project-card';

    const writtenPct = project.total > 0 ? (project.written / project.total * 100) : 0;
    const publishedPct = project.total > 0 ? (project.published / project.total * 100) : 0;

    card.innerHTML = `
        <div class="project-card-header">
            <div class="project-keyword">${project.keyword}</div>
        </div>
        <div class="project-filename">📁 ${project.filename}</div>

        <div class="project-stats">
            <div class="project-stat">
                <div class="project-stat-number">${project.total}</div>
                <div class="project-stat-label">Total</div>
            </div>
            <div class="project-stat">
                <div class="project-stat-number written">${project.written}</div>
                <div class="project-stat-label">Written</div>
            </div>
            <div class="project-stat">
                <div class="project-stat-number published">${project.published}</div>
                <div class="project-stat-label">Live</div>
            </div>
            <div class="project-stat">
                <div class="project-stat-number missing">${project.missing}</div>
                <div class="project-stat-label">Missing</div>
            </div>
        </div>

        <div class="project-progress-bar-wrapper">
            <div class="project-progress-written" style="width:${writtenPct}%"></div>
            <div class="project-progress-published" style="width:${publishedPct}%"></div>
        </div>

        <div class="project-actions">
            <button class="btn-secondary" onclick="loadProjectIntoPage('${project.path}', '${project.filename}', 'articles')">✍️ Write</button>
            <button class="btn-secondary" onclick="loadProjectIntoPage('${project.path}', '${project.filename}', 'media')">🖼️ Media</button>
            <button class="btn-primary" onclick="loadProjectIntoPage('${project.path}', '${project.filename}', 'publisher')">🚀 Publish</button>
            <button class="project-delete-btn" onclick="deleteProject('${project.filename}', this)" title="Delete project">🗑️</button>
        </div>
    `;

    return card;
}

function loadProjectIntoPage(csvPath, filename, targetPage) {
    // Navigate to target page
    const navItem = document.querySelector(`.nav-item[data-page="${targetPage}"]`);
    if (navItem) navItem.click();

    // Load CSV into the correct page after navigation
    setTimeout(() => {
        fetch(csvPath.startsWith('/') ? `/read-csv?path=${encodeURIComponent(csvPath)}` : csvPath)
            .then(r => r.text())
            .then(text => {
                if (targetPage === 'articles') {
                    parseArticleCSV(text, filename);
                } else if (targetPage === 'media') {
                    mediaCsvPath = csvPath;
                    parseMediaCSV(text, filename);
                } else if (targetPage === 'publisher') {
                    publisherCsvPath = csvPath;
                    parsePublisherCSV(text, filename);
                }
            })
            .catch(e => console.error('Failed to load CSV:', e));
    }, 150);
}

async function deleteProject(filename, btn) {
    if (!confirm(`Delete ${filename}? This only removes the CSV file — drafts and outlines are kept.`)) return;

    try {
        const response = await fetch('/delete-project', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        });
        const data = await response.json();
        if (data.success) {
            btn.closest('.project-card').remove();
        } else {
            alert('Delete failed: ' + data.error);
        }
    } catch (e) {
        alert('Delete failed');
    }
}
