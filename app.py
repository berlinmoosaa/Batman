from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from telethon.sync import TelegramClient
from telethon.errors import SessionPasswordNeededError
import json
import os
import sqlite3
from datetime import datetime
import hashlib
import sys

app = Flask(__name__)
app.secret_key = 'batman_secret_key_2026'
CORS(app)

# Database setup
DB_FILE = 'telegram_data.db'

def init_db():
    """Initialize database with all tables"""
    try:
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
        print("[DB] Database initialized successfully")
    except Exception as e:
        print(f"[DB ERROR] Failed to initialize database: {str(e)}")
        sys.exit(1)

init_db()

def get_api_credentials():
    """Get API credentials from database"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT api_id, api_hash FROM settings LIMIT 1')
        result = c.fetchone()
        conn.close()
        
        if result:
            print(f"[DB] Retrieved credentials: api_id={result[0]}, api_hash={result[1][:10]}...")
            return result
        else:
            print("[DB] No credentials found in database")
            return (None, None)
    except Exception as e:
        print(f"[DB ERROR] Error getting credentials: {str(e)}")
        return (None, None)

def save_api_credentials(api_id, api_hash):
    """Save API credentials to database"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM settings')
        c.execute('INSERT INTO settings (api_id, api_hash) VALUES (?, ?)', (api_id, api_hash))
        conn.commit()
        conn.close()
        print(f"[DB] Credentials saved successfully: api_id={api_id}, api_hash={api_hash[:10]}...")
        return True
    except Exception as e:
        print(f"[DB ERROR] Error saving credentials: {str(e)}")
        return False

def get_all_accounts():
    """Get all registered accounts"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT id, phone, session_name, created_at FROM accounts')
        accounts = c.fetchall()
        conn.close()
        print(f"[DB] Retrieved {len(accounts)} accounts")
        return accounts
    except Exception as e:
        print(f"[DB ERROR] Error getting accounts: {str(e)}")
        return []

def save_account(phone, session_name):
    """Save account to database"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO accounts (phone, session_name, created_at) VALUES (?, ?, ?)',
                  (phone, session_name, datetime.now()))
        conn.commit()
        account_id = c.lastrowid
        conn.close()
        print(f"[DB] Account saved: phone={phone}, id={account_id}")
        return account_id
    except Exception as e:
        print(f"[DB ERROR] Error saving account: {str(e)}")
        return None

def get_groups_for_account(account_id):
    """Get all groups for a specific account"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT id, group_id, group_name, group_username, members_count FROM groups WHERE account_id = ?',
                  (account_id,))
        groups = c.fetchall()
        conn.close()
        print(f"[DB] Retrieved {len(groups)} groups for account {account_id}")
        return groups
    except Exception as e:
        print(f"[DB ERROR] Error getting groups: {str(e)}")
        return []

def save_groups(account_id, groups_list):
    """Save groups for account"""
    try:
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
        print(f"[DB] Saved {len(groups_list)} groups for account {account_id}")
    except Exception as e:
        print(f"[DB ERROR] Error saving groups: {str(e)}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/check-settings', methods=['GET'])
def check_settings():
    print("[API] check-settings called")
    api_id, api_hash = get_api_credentials()
    has_creds = api_id is not None and api_hash is not None
    print(f"[API] Credentials present: {has_creds}")
    return jsonify({
        'has_credentials': has_creds,
        'api_id': api_id
    })

@app.route('/api/save-settings', methods=['POST'])
def save_settings():
    print("[API] save-settings called")
    data = request.json
    api_id = data.get('api_id')
    api_hash = data.get('api_hash')
    
    print(f"[API] Received: api_id={api_id}, api_hash={api_hash[:10] if api_hash else 'None'}...")
    
    if not api_id or not api_hash:
        print("[API] ERROR: Missing api_id or api_hash")
        return jsonify({'error': 'API ID and Hash required'}), 400
    
    if save_api_credentials(api_id, api_hash):
        return jsonify({'success': True, 'message': 'Settings saved successfully'})
    else:
        return jsonify({'error': 'Failed to save settings'}), 500

@app.route('/api/login', methods=['POST'])
def login_account():
    print("\n[API] login called")
    data = request.json
    phone = data.get('phone')
    
    print(f"[API] Phone received: {phone}")
    
    if not phone:
        print("[API] ERROR: No phone provided")
        return jsonify({'error': 'Phone number required'}), 400
    
    api_id, api_hash = get_api_credentials()
    print(f"[API] API Credentials: api_id={api_id}, api_hash={api_hash[:10] if api_hash else 'None'}...")
    
    if not api_id or not api_hash:
        print("[API] ERROR: API credentials not set in database")
        return jsonify({'error': 'API credentials not set. Please save them in Settings first.'}), 400
    
    try:
        print("[API] Creating Telethon client...")
        session_name = f'session_{hashlib.md5(phone.encode()).hexdigest()}'
        print(f"[API] Session name: {session_name}")
        
        # Convert api_id to integer
        try:
            api_id_int = int(api_id)
        except ValueError:
            print(f"[API] ERROR: Invalid api_id format: {api_id}")
            return jsonify({'error': f'Invalid API ID format: {api_id}. Must be a number.'}), 400
        
        client = TelegramClient(session_name, api_id_int, api_hash)
        print("[API] Connecting to Telegram...")
        client.connect()
        print("[API] Connected successfully")
        
        if not client.is_user_authorized():
            print("[API] User not authorized, sending code request...")
            client.send_code_request(phone)
            print("[API] Code sent successfully")
            return jsonify({
                'success': True,
                'status': 'code_required',
                'phone': phone,
                'session_name': session_name
            })
        else:
            print("[API] User already authorized, saving account...")
            account_id = save_account(phone, session_name)
            client.disconnect()
            print(f"[API] Account saved with ID: {account_id}")
            return jsonify({
                'success': True,
                'status': 'logged_in',
                'account_id': account_id,
                'phone': phone
            })
    except Exception as e:
        print(f"[API] EXCEPTION: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Login error: {str(e)}'}), 400

@app.route('/api/verify-code', methods=['POST'])
def verify_code():
    print("\n[API] verify-code called")
    data = request.json
    phone = data.get('phone')
    code = data.get('code')
    session_name = data.get('session_name')
    
    print(f"[API] Verify: phone={phone}, code={code}, session={session_name}")
    
    api_id, api_hash = get_api_credentials()
    
    if not api_id or not api_hash:
        print("[API] ERROR: API credentials not set")
        return jsonify({'error': 'API credentials not set'}), 400
    
    try:
        print("[API] Creating client for verification...")
        api_id_int = int(api_id)
        client = TelegramClient(session_name, api_id_int, api_hash)
        client.connect()
        print("[API] Connected")
        
        try:
            print("[API] Signing in...")
            client.sign_in(phone, code)
            print("[API] Signed in successfully")
        except SessionPasswordNeededError:
            print("[API] Password required")
            return jsonify({
                'status': 'password_required',
                'session_name': session_name,
                'phone': phone
            })
        
        print("[API] Saving account...")
        account_id = save_account(phone, session_name)
        client.disconnect()
        print(f"[API] Account verified and saved: {account_id}")
        
        return jsonify({
            'success': True,
            'status': 'verified',
            'account_id': account_id,
            'phone': phone
        })
    except Exception as e:
        print(f"[API] EXCEPTION: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Verification error: {str(e)}'}), 400

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    print("[API] get_accounts called")
    accounts = get_all_accounts()
    return jsonify({
        'accounts': [
            {'id': acc[0], 'phone': acc[1], 'session_name': acc[2], 'created_at': acc[3]}
            for acc in accounts
        ]
    })

@app.route('/api/load-groups', methods=['POST'])
def load_groups():
    print("\n[API] load_groups called")
    data = request.json
    account_id = data.get('account_id')
    
    print(f"[API] Account ID: {account_id}")
    
    if not account_id:
        print("[API] ERROR: No account_id provided")
        return jsonify({'error': 'Account ID required'}), 400
    
    accounts = get_all_accounts()
    account = next((acc for acc in accounts if acc[0] == account_id), None)
    
    if not account:
        print(f"[API] ERROR: Account {account_id} not found")
        return jsonify({'error': 'Account not found'}), 404
    
    api_id, api_hash = get_api_credentials()
    session_name = account[2]
    
    try:
        print(f"[API] Loading groups for session: {session_name}")
        api_id_int = int(api_id)
        client = TelegramClient(session_name, api_id_int, api_hash)
        client.connect()
        print("[API] Connected to Telegram")
        
        groups = []
        
        def fetch_groups():
            count = 0
            for dialog in client.get_dialogs():
                if dialog.is_group or dialog.is_channel:
                    group_data = {
                        'id': dialog.id,
                        'title': dialog.title,
                        'username': dialog.entity.username if hasattr(dialog.entity, 'username') else None,
                        'members_count': dialog.entity.participants_count if hasattr(dialog.entity, 'participants_count') else 0
                    }
                    groups.append(group_data)
                    count += 1
            print(f"[API] Found {count} groups")
            return count
        
        fetch_groups()
        save_groups(account_id, groups)
        client.disconnect()
        print(f"[API] Loaded and saved {len(groups)} groups")
        
        return jsonify({
            'success': True,
            'groups': groups,
            'count': len(groups)
        })
    except Exception as e:
        print(f"[API] EXCEPTION: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to load groups: {str(e)}'}), 400

@app.route('/api/groups/<int:account_id>', methods=['GET'])
def get_account_groups(account_id):
    print(f"[API] get_account_groups called for account {account_id}")
    groups = get_groups_for_account(account_id)
    return jsonify({
        'groups': [
            {'id': g[0], 'group_id': g[1], 'name': g[2], 'username': g[3], 'members': g[4]}
            for g in groups
        ]
    })

@app.route('/api/send-message', methods=['POST'])
def send_message():
    print("\n[API] send_message called")
    data = request.json
    account_ids = data.get('account_ids', [])
    group_ids = data.get('group_ids', [])
    message = data.get('message', '')
    delay = data.get('delay', 0)
    
    print(f"[API] Accounts: {account_ids}, Groups: {group_ids}, Delay: {delay}s")
    
    if not account_ids or not group_ids or not message:
        print("[API] ERROR: Missing required parameters")
        return jsonify({'error': 'Missing required parameters'}), 400
    
    api_id, api_hash = get_api_credentials()
    accounts = get_all_accounts()
    results = []
    
    try:
        for account_id in account_ids:
            account = next((acc for acc in accounts if acc[0] == account_id), None)
            if not account:
                print(f"[API] WARNING: Account {account_id} not found")
                continue
            
            session_name = account[2]
            print(f"[API] Processing account {account_id} ({session_name})")
            
            api_id_int = int(api_id)
            client = TelegramClient(session_name, api_id_int, api_hash)
            client.connect()
            
            for group_id in group_ids:
                try:
                    import time
                    time.sleep(delay)
                    print(f"[API] Sending message to group {group_id}")
                    client.send_message(int(group_id), message)
                    results.append({
                        'account_id': account_id,
                        'group_id': group_id,
                        'status': 'sent'
                    })
                    print(f"[API] Message sent successfully")
                except Exception as e:
                    print(f"[API] ERROR sending to group {group_id}: {str(e)}")
                    results.append({
                        'account_id': account_id,
                        'group_id': group_id,
                        'status': 'failed',
                        'error': str(e)
                    })
            
            client.disconnect()
        
        total_sent = sum(1 for r in results if r['status'] == 'sent')
        print(f"[API] Message sending complete: {total_sent}/{len(results)} sent")
        
        return jsonify({
            'success': True,
            'results': results,
            'total_sent': total_sent
        })
    except Exception as e:
        print(f"[API] EXCEPTION: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error sending messages: {str(e)}'}), 400

if __name__ == '__main__':
    print("\n" + "="*60)
    print("BATMAN - Telegram Multi-Account Manager")
    print("="*60)
    print("Starting Flask server...")
    app.run(debug=True, host='localhost', port=5000)
