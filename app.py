from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from telethon.sync import TelegramClient
from telethon.errors import SessionPasswordNeededError
import json
import os
import sqlite3
from datetime import datetime
import hashlib

app = Flask(__name__)
app.secret_key = 'batman_secret_key_2026'
CORS(app)

# Database setup
DB_FILE = 'telegram_data.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                (id INTEGER PRIMARY KEY, api_id TEXT, api_hash TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS accounts
                (id INTEGER PRIMARY KEY, phone TEXT, session_name TEXT, created_at TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS groups
                (id INTEGER PRIMARY KEY, account_id INTEGER, group_id INTEGER, group_name TEXT, 
                 group_username TEXT, members_count INTEGER, created_at TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

def get_api_credentials():
    """Get API credentials from database"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT api_id, api_hash FROM settings LIMIT 1')
    result = c.fetchone()
    conn.close()
    return result if result else (None, None)

def save_api_credentials(api_id, api_hash):
    """Save API credentials to database"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM settings')
    c.execute('INSERT INTO settings (api_id, api_hash) VALUES (?, ?)', (api_id, api_hash))
    conn.commit()
    conn.close()

def get_all_accounts():
    """Get all registered accounts"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT id, phone, session_name, created_at FROM accounts')
    accounts = c.fetchall()
    conn.close()
    return accounts

def save_account(phone, session_name):
    """Save account to database"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('INSERT INTO accounts (phone, session_name, created_at) VALUES (?, ?, ?)',
              (phone, session_name, datetime.now()))
    conn.commit()
    account_id = c.lastrowid
    conn.close()
    return account_id

def get_groups_for_account(account_id):
    """Get all groups for a specific account"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT id, group_id, group_name, group_username, members_count FROM groups WHERE account_id = ?',
              (account_id,))
    groups = c.fetchall()
    conn.close()
    return groups

def save_groups(account_id, groups_list):
    """Save groups for account"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM groups WHERE account_id = ?', (account_id,))
    for group in groups_list:
        c.execute('INSERT INTO groups (account_id, group_id, group_name, group_username, members_count, created_at) '
                  'VALUES (?, ?, ?, ?, ?, ?)',
                  (account_id, group.get('id'), group.get('title'), group.get('username', 'N/A'), 
                   group.get('members_count', 0), datetime.now()))
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/check-settings', methods=['GET'])
def check_settings():
    api_id, api_hash = get_api_credentials()
    return jsonify({
        'has_credentials': api_id is not None and api_hash is not None,
        'api_id': api_id
    })

@app.route('/api/save-settings', methods=['POST'])
def save_settings():
    data = request.json
    api_id = data.get('api_id')
    api_hash = data.get('api_hash')
    
    if not api_id or not api_hash:
        return jsonify({'error': 'API ID and Hash required'}), 400
    
    save_api_credentials(api_id, api_hash)
    return jsonify({'success': True, 'message': 'Settings saved successfully'})

@app.route('/api/login', methods=['POST'])
def login_account():
    data = request.json
    phone = data.get('phone')
    
    if not phone:
        return jsonify({'error': 'Phone number required'}), 400
    
    api_id, api_hash = get_api_credentials()
    if not api_id or not api_hash:
        return jsonify({'error': 'API credentials not set'}), 400
    
    try:
        session_name = f'session_{hashlib.md5(phone.encode()).hexdigest()}'
        client = TelegramClient(session_name, int(api_id), api_hash)
        client.connect()
        
        if not client.is_user_authorized():
            client.send_code_request(phone)
            return jsonify({
                'success': True,
                'status': 'code_required',
                'phone': phone,
                'session_name': session_name
            })
        else:
            account_id = save_account(phone, session_name)
            client.disconnect()
            return jsonify({
                'success': True,
                'status': 'logged_in',
                'account_id': account_id,
                'phone': phone
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/verify-code', methods=['POST'])
def verify_code():
    data = request.json
    phone = data.get('phone')
    code = data.get('code')
    session_name = data.get('session_name')
    
    api_id, api_hash = get_api_credentials()
    
    try:
        client = TelegramClient(session_name, int(api_id), api_hash)
        client.connect()
        
        try:
            client.sign_in(phone, code)
        except SessionPasswordNeededError:
            return jsonify({
                'status': 'password_required',
                'session_name': session_name,
                'phone': phone
            })
        
        account_id = save_account(phone, session_name)
        client.disconnect()
        
        return jsonify({
            'success': True,
            'status': 'verified',
            'account_id': account_id,
            'phone': phone
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    accounts = get_all_accounts()
    return jsonify({
        'accounts': [
            {'id': acc[0], 'phone': acc[1], 'session_name': acc[2], 'created_at': acc[3]}
            for acc in accounts
        ]
    })

@app.route('/api/load-groups', methods=['POST'])
def load_groups():
    data = request.json
    account_id = data.get('account_id')
    
    if not account_id:
        return jsonify({'error': 'Account ID required'}), 400
    
    accounts = get_all_accounts()
    account = next((acc for acc in accounts if acc[0] == account_id), None)
    
    if not account:
        return jsonify({'error': 'Account not found'}), 404
    
    api_id, api_hash = get_api_credentials()
    session_name = account[2]
    
    try:
        client = TelegramClient(session_name, int(api_id), api_hash)
        client.connect()
        
        groups = []
        async def fetch_groups():
            async for dialog in client.get_dialogs():
                if dialog.is_group or dialog.is_channel:
                    groups.append({
                        'id': dialog.id,
                        'title': dialog.title,
                        'username': dialog.entity.username if hasattr(dialog.entity, 'username') else None,
                        'members_count': dialog.entity.participants_count if hasattr(dialog.entity, 'participants_count') else 0
                    })
        
        client.loop.run_until_complete(fetch_groups())
        
        save_groups(account_id, groups)
        client.disconnect()
        
        return jsonify({
            'success': True,
            'groups': groups,
            'count': len(groups)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/groups/<int:account_id>', methods=['GET'])
def get_account_groups(account_id):
    groups = get_groups_for_account(account_id)
    return jsonify({
        'groups': [
            {'id': g[0], 'group_id': g[1], 'name': g[2], 'username': g[3], 'members': g[4]}
            for g in groups
        ]
    })

@app.route('/api/send-message', methods=['POST'])
def send_message():
    data = request.json
    account_ids = data.get('account_ids', [])
    group_ids = data.get('group_ids', [])
    message = data.get('message', '')
    delay = data.get('delay', 0)
    
    if not account_ids or not group_ids or not message:
        return jsonify({'error': 'Missing required parameters'}), 400
    
    api_id, api_hash = get_api_credentials()
    accounts = get_all_accounts()
    results = []
    
    try:
        for account_id in account_ids:
            account = next((acc for acc in accounts if acc[0] == account_id), None)
            if not account:
                continue
            
            session_name = account[2]
            client = TelegramClient(session_name, int(api_id), api_hash)
            client.connect()
            
            for group_id in group_ids:
                try:
                    import time
                    time.sleep(delay)
                    client.send_message(int(group_id), message)
                    results.append({
                        'account_id': account_id,
                        'group_id': group_id,
                        'status': 'sent'
                    })
                except Exception as e:
                    results.append({
                        'account_id': account_id,
                        'group_id': group_id,
                        'status': 'failed',
                        'error': str(e)
                    })
            
            client.disconnect()
        
        return jsonify({
            'success': True,
            'results': results,
            'total_sent': sum(1 for r in results if r['status'] == 'sent')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5000)
