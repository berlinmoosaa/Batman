class TelegramManager {
    constructor() {
        this.currentAccount = null;
        this.accounts = [];
        this.groups = [];
        this.selectedAccounts = new Set();
        this.selectedGroups = new Set();
        this.init();
    }

    async init() {
        await this.checkSettings();
        this.setupEventListeners();
        await this.loadAccounts();
    }

    async checkSettings() {
        try {
            const response = await fetch('/api/check-settings');
            const data = await response.json();
            if (!data.has_credentials) {
                this.showPage('settings');
            } else {
                this.showPage('accounts');
            }
        } catch (error) {
            console.error('Error checking settings:', error);
        }
    }

    setupEventListeners() {
        // Navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const page = item.dataset.page;
                this.showPage(page);
                this.updateNavigation(item);
            });
        });

        // Settings
        document.getElementById('save-settings-btn').addEventListener('click', () => this.saveSettings());

        // Accounts
        document.getElementById('login-btn').addEventListener('click', () => this.loginAccount());
        document.getElementById('verify-code-btn').addEventListener('click', () => this.verifyCode());

        // Groups
        document.getElementById('account-select').addEventListener('change', (e) => {
            this.currentAccount = e.target.value ? parseInt(e.target.value) : null;
        });
        document.getElementById('load-groups-btn').addEventListener('click', () => this.loadGroups());

        // Messages
        document.getElementById('select-all-accounts-btn').addEventListener('click', () => this.selectAllAccounts());
        document.getElementById('select-all-groups-btn').addEventListener('click', () => this.selectAllGroups());
        document.getElementById('send-message-btn').addEventListener('click', () => this.sendMessages());
    }

    showPage(pageId) {
        document.querySelectorAll('.page').forEach(page => page.classList.remove('active'));
        const page = document.getElementById(`${pageId}-page`);
        if (page) {
            page.classList.add('active');
            if (pageId === 'messages') {
                this.populateMessagePage();
            } else if (pageId === 'groups') {
                this.populateGroupsPage();
            }
        }
    }

    updateNavigation(item) {
        document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
        item.classList.add('active');
    }

    async saveSettings() {
        const apiId = document.getElementById('api-id').value;
        const apiHash = document.getElementById('api-hash').value;

        if (!apiId || !apiHash) {
            alert('Please enter both API ID and Hash');
            return;
        }

        try {
            const response = await fetch('/api/save-settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_id: apiId, api_hash: apiHash })
            });
            const data = await response.json();

            if (response.ok) {
                document.getElementById('save-settings-btn').style.display = 'none';
                document.getElementById('api-id').disabled = true;
                document.getElementById('api-hash').disabled = true;
                document.getElementById('settings-status').classList.remove('hidden');
                setTimeout(() => this.showPage('accounts'), 1500);
            } else {
                alert('Error: ' + data.error);
            }
        } catch (error) {
            alert('Error saving settings: ' + error.message);
        }
    }

    async loginAccount() {
        const phone = document.getElementById('phone-input').value;
        if (!phone) {
            alert('Please enter phone number');
            return;
        }

        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ phone })
            });
            const data = await response.json();

            if (data.status === 'code_required') {
                document.getElementById('login-form').style.display = 'none';
                document.getElementById('code-form').classList.remove('hidden');
                this.currentPhone = phone;
                this.currentSessionName = data.session_name;
            } else if (data.status === 'logged_in') {
                alert('Account logged in successfully!');
                this.loadAccounts();
                document.getElementById('phone-input').value = '';
            }
        } catch (error) {
            alert('Login error: ' + error.message);
        }
    }

    async verifyCode() {
        const code = document.getElementById('code-input').value;
        if (!code) {
            alert('Please enter verification code');
            return;
        }

        try {
            const response = await fetch('/api/verify-code', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    phone: this.currentPhone,
                    code: code,
                    session_name: this.currentSessionName
                })
            });
            const data = await response.json();

            if (data.status === 'verified' || data.success) {
                alert('Account verified successfully!');
                this.loadAccounts();
                document.getElementById('code-form').classList.add('hidden');
                document.getElementById('login-form').style.display = 'flex';
                document.getElementById('code-input').value = '';
                document.getElementById('phone-input').value = '';
            } else {
                alert('Verification failed: ' + data.error);
            }
        } catch (error) {
            alert('Verification error: ' + error.message);
        }
    }

    async loadAccounts() {
        try {
            const response = await fetch('/api/accounts');
            const data = await response.json();
            this.accounts = data.accounts;
            this.renderAccounts();
            this.updateAccountSelects();
        } catch (error) {
            console.error('Error loading accounts:', error);
        }
    }

    renderAccounts() {
        const container = document.getElementById('accounts-list');
        container.innerHTML = '';

        if (this.accounts.length === 0) {
            container.innerHTML = '<p style="color: var(--text-secondary);">No accounts connected yet. Add one above!</p>';
            return;
        }

        this.accounts.forEach(acc => {
            const card = document.createElement('div');
            card.className = 'account-card';
            card.innerHTML = `
                <h4><i class="fas fa-user-circle"></i> ${acc.phone}</h4>
                <p>Connected: ${new Date(acc.created_at).toLocaleDateString()}</p>
                <p>Session: ${acc.session_name.substring(0, 20)}...</p>
            `;
            container.appendChild(card);
        });
    }

    updateAccountSelects() {
        const select = document.getElementById('account-select');
        const checkboxList = document.getElementById('accounts-checkbox-list');

        select.innerHTML = '<option value="">Select an account...</option>';
        checkboxList.innerHTML = '';

        this.accounts.forEach(acc => {
            const option = document.createElement('option');
            option.value = acc.id;
            option.textContent = acc.phone;
            select.appendChild(option);

            const checkboxItem = document.createElement('div');
            checkboxItem.className = 'checkbox-item';
            checkboxItem.innerHTML = `
                <input type="checkbox" id="account-${acc.id}" value="${acc.id}">
                <label for="account-${acc.id}">${acc.phone}</label>
            `;
            checkboxItem.querySelector('input').addEventListener('change', (e) => {
                if (e.target.checked) {
                    this.selectedAccounts.add(parseInt(acc.id));
                } else {
                    this.selectedAccounts.delete(parseInt(acc.id));
                }
            });
            checkboxList.appendChild(checkboxItem);
        });
    }

    async loadGroups() {
        if (!this.currentAccount) {
            alert('Please select an account');
            return;
        }

        const spinner = document.getElementById('loading-spinner');
        spinner.classList.remove('hidden');

        try {
            const response = await fetch('/api/load-groups', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ account_id: this.currentAccount })
            });
            const data = await response.json();
            spinner.classList.add('hidden');

            if (data.success) {
                this.groups = data.groups;
                this.renderGroups();
                alert(`Loaded ${data.count} groups successfully!`);
            } else {
                alert('Error: ' + data.error);
            }
        } catch (error) {
            spinner.classList.add('hidden');
            alert('Error loading groups: ' + error.message);
        }
    }

    renderGroups() {
        const container = document.getElementById('groups-list');
        container.innerHTML = '';

        if (this.groups.length === 0) {
            container.innerHTML = '<p style="color: var(--text-secondary);">No groups found</p>';
            return;
        }

        this.groups.forEach(group => {
            const card = document.createElement('div');
            card.className = 'group-card';
            card.innerHTML = `
                <h4>${group.title || 'Unknown'}</h4>
                <p><i class="fas fa-users"></i> Members: ${group.members_count || 0}</p>
                <p><i class="fas fa-link"></i> @${group.username || 'N/A'}</p>
            `;
            container.appendChild(card);
        });
    }

    populateGroupsPage() {
        const select = document.getElementById('account-select');
        if (select.value) {
            this.currentAccount = parseInt(select.value);
        }
    }

    populateMessagePage() {
        this.updateAccountSelects();
        const checkboxList = document.getElementById('groups-checkbox-list');
        checkboxList.innerHTML = '';

        if (this.groups.length === 0) {
            checkboxList.innerHTML = '<p style="color: var(--text-secondary);">No groups loaded. Load them in the Groups page first!</p>';
            return;
        }

        this.groups.forEach(group => {
            const checkboxItem = document.createElement('div');
            checkboxItem.className = 'checkbox-item';
            checkboxItem.innerHTML = `
                <input type="checkbox" id="group-${group.id}" value="${group.id}">
                <label for="group-${group.id}">${group.title || 'Unknown'}</label>
            `;
            checkboxItem.querySelector('input').addEventListener('change', (e) => {
                if (e.target.checked) {
                    this.selectedGroups.add(parseInt(group.id));
                } else {
                    this.selectedGroups.delete(parseInt(group.id));
                }
            });
            checkboxList.appendChild(checkboxItem);
        });
    }

    selectAllAccounts() {
        document.querySelectorAll('#accounts-checkbox-list input[type="checkbox"]').forEach(checkbox => {
            checkbox.checked = true;
            this.selectedAccounts.add(parseInt(checkbox.value));
        });
    }

    selectAllGroups() {
        document.querySelectorAll('#groups-checkbox-list input[type="checkbox"]').forEach(checkbox => {
            checkbox.checked = true;
            this.selectedGroups.add(parseInt(checkbox.value));
        });
    }

    async sendMessages() {
        const message = document.getElementById('message-text').value;
        const delay = parseInt(document.getElementById('delay-input').value) || 0;

        if (!message) {
            alert('Please enter a message');
            return;
        }

        if (this.selectedAccounts.size === 0) {
            alert('Please select at least one account');
            return;
        }

        if (this.selectedGroups.size === 0) {
            alert('Please select at least one group');
            return;
        }

        try {
            const response = await fetch('/api/send-message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    account_ids: Array.from(this.selectedAccounts),
                    group_ids: Array.from(this.selectedGroups),
                    message: message,
                    delay: delay
                })
            });
            const data = await response.json();

            if (data.success) {
                this.showResults(data.results, data.total_sent);
            } else {
                alert('Error: ' + data.error);
            }
        } catch (error) {
            alert('Error sending messages: ' + error.message);
        }
    }

    showResults(results, totalSent) {
        const resultsDiv = document.getElementById('send-results');
        const content = document.getElementById('results-content');
        content.innerHTML = '';

        const summary = document.createElement('div');
        summary.innerHTML = `<h4>Summary: ${totalSent}/${results.length} messages sent successfully</h4>`;
        content.appendChild(summary);

        results.forEach(result => {
            const item = document.createElement('div');
            item.className = `result-item ${result.status}`;
            item.innerHTML = `
                <i class="fas fa-${result.status === 'sent' ? 'check-circle' : 'times-circle'}"></i>
                <span>Account #${result.account_id} to Group #${result.group_id}: ${result.status.toUpperCase()}${result.error ? ' - ' + result.error : ''}</span>
            `;
            content.appendChild(item);
        });

        resultsDiv.classList.remove('hidden');
    }
}

const manager = new TelegramManager();
