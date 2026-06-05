from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import sqlite3
from datetime import datetime
import hashlib
import time
import asyncio
import threading
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

app = Flask(__name__)
app.secret_key = 'batman_secret_key_2026'
CORS(app)

DB_FILE = 'telegram_data.db'

# ==================== DATABASE TIMEOUT FIX ====================
def get_db_connection(db_path):
    """Create a database connection with timeout and WAL mode enabled"""
    conn = sqlite3.connect(db_path, timeout=20.0, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout = 5000')
    return conn

# ==================== ASYNCIO EVENT LOOP FIX ====================
# Store event loop per thread using threading.local()
_thread_local = threading.local()

def get_event_loop():
    """Get or create event loop for current thread"""
    if not hasattr(_thread_local, 'loop'):
        _thread_local.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_thread_local.loop)
    
    loop = _thread_local.loop
    if loop.is_closed():
        _thread_local.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_thread_local.loop)
        loop = _thread_local.loop
    
    return loop

async def create_and_connect_client(session_name, api_id, api_hash):
    """Async function to create and connect Telegram client"""
    client = TelegramClient(session_name, int(api_id), api_hash)
    await client.connect()
    return client

async def disconnect_client(client):
    """Async function to disconnect Telegram client"""
    await client.disconnect()

def run_async(coro):
    """Run an async coroutine in the current thread"""
    loop = get_event_loop()
    return loop.run_until_complete(coro)

# Initialize database
conn = get_db_connection(DB_FILE)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, api_id TEXT, api_hash TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY, phone TEXT, session_name TEXT, created_at TIMESTAMP)')
c.execute('CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY, account_id INTEGER, group_id INTEGER, group_name TEXT, group_username TEXT, members_count INTEGER, created_at TIMESTAMP)')
conn.commit()
conn.close()

def get_api_credentials():
    conn = get_db_connection(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT api_id, api_hash FROM settings LIMIT 1')
    result = c.fetchone()
    conn.close()
    return result if result else (None, None)

def save_api_credentials(api_id, api_hash):
    conn = get_db_connection(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM settings')
    c.execute('INSERT INTO settings (api_id, api_hash) VALUES (?, ?)', (str(api_id), str(api_hash)))
    conn.commit()
    conn.close()

def get_all_accounts():
    conn = get_db_connection(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT id, phone, session_name, created_at FROM accounts')
    accounts = c.fetchall()
    conn.close()
    return accounts

def save_account(phone, session_name):
    conn = get_db_connection(DB_FILE)
    c = conn.cursor()
    c.execute('INSERT INTO accounts (phone, session_name, created_at) VALUES (?, ?, ?)', (phone, session_name, datetime.now()))
    conn.commit()
    account_id = c.lastrowid
    conn.close()
    return account_id

def get_groups_for_account(account_id):
    conn = get_db_connection(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT id, group_id, group_name, group_username, members_count FROM groups WHERE account_id = ?', (account_id,))
    groups = c.fetchall()
    conn.close()
    return groups

def save_groups(account_id, groups_list):
    conn = get_db_connection(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM groups WHERE account_id = ?', (account_id,))
    for group in groups_list:
        c.execute('INSERT INTO groups (account_id, group_id, group_name, group_username, members_count, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                  (account_id, group.get('id'), group.get('title'), group.get('username', 'N/A'), group.get('members_count', 0), datetime.now()))
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/check-settings', methods=['GET'])
def check_settings():
    api_id, api_hash = get_api_credentials()
    has_creds = api_id is not None and api_hash is not None
    return jsonify({'has_credentials': has_creds})

@app.route('/api/save-settings', methods=['POST'])
def save_settings():
    try:
        data = request.json
        api_id = data.get('api_id', '').strip()
        api_hash = data.get('api_hash', '').strip()
        
        if not api_id or not api_hash:
            return jsonify({'error': 'API ID and Hash are required'}), 400
        
        try:
            int(api_id)
        except:
            return jsonify({'error': 'API ID must be a number'}), 400
        
        save_api_credentials(api_id, api_hash)
        return jsonify({'success': True})
    except Exception as e:
        print(f"[ERROR] Save settings: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        phone = data.get('phone', '').strip()
        
        if not phone:
            return jsonify({'error': 'Phone number required'}), 400
        
        api_id, api_hash = get_api_credentials()
        
        if not api_id or not api_hash:
            return jsonify({'error': 'Please save API credentials first'}), 400
        
        session_name = f'session_{hashlib.md5(phone.encode()).hexdigest()}'
        
        try:
            print(f"[API] login called")
            print(f"[API] Phone received: {phone}")
            
            async def login_async():
                client = TelegramClient(session_name, int(api_id), api_hash)
                await client.connect()
                
                print(f"[API] Connected to Telegram")
                
                if not await client.is_user_authorized():
                    print(f"[API] Not authorized, sending code request")
                    await client.send_code_request(phone)
                    await client.disconnect()
                    return {
                        'success': True,
                        'status': 'code_required',
                        'phone': phone,
                        'session_name': session_name
                    }
                else:
                    print(f"[API] Already authorized")
                    account_id = save_account(phone, session_name)
                    await client.disconnect()
                    return {
                        'success': True,
                        'status': 'logged_in',
                        'account_id': account_id,
                        'phone': phone
                    }
            
            result = run_async(login_async())
            return jsonify(result)
            
        except Exception as e:
            print(f"[API] EXCEPTION: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Telegram error: {str(e)}'}), 400
    except Exception as e:
        print(f"[API] General error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/verify-code', methods=['POST'])
def verify():
    try:
        data = request.json
        phone = data.get('phone', '').strip()
        code = data.get('code', '').strip()
        session_name = data.get('session_name', '')
        
        api_id, api_hash = get_api_credentials()
        
        if not api_id or not api_hash:
            return jsonify({'error': 'API credentials not found'}), 400
        
        try:
            async def verify_async():
                client = TelegramClient(session_name, int(api_id), api_hash)
                await client.connect()
                
                try:
                    print(f"[API] Attempting to sign in with code")
                    await client.sign_in(phone, code)
                except SessionPasswordNeededError:
                    await client.disconnect()
                    return {'error': '2FA not supported yet'}
                
                account_id = save_account(phone, session_name)
                print(f"[API] Successfully verified account")
                await client.disconnect()
                
                return {
                    'success': True,
                    'status': 'verified',
                    'account_id': account_id,
                    'phone': phone
                }
            
            result = run_async(verify_async())
            if 'error' in result:
                return jsonify(result), 400
            return jsonify(result)
            
        except Exception as e:
            print(f"[API] Verification error: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Verification failed: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
    try:
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
            async def load_groups_async():
                client = TelegramClient(session_name, int(api_id), api_hash)
                await client.connect()
                
                print(f"[API] Loading groups for account {account_id}")
                groups = []
                async for dialog in client.get_dialogs():
                    if dialog.is_group or dialog.is_channel:
                        groups.append({
                            'id': dialog.id,
                            'title': dialog.title,
                            'username': dialog.entity.username if hasattr(dialog.entity, 'username') else None,
                            'members_count': dialog.entity.participants_count if hasattr(dialog.entity, 'participants_count') else 0
                        })
                
                save_groups(account_id, groups)
                print(f"[API] Loaded {len(groups)} groups")
                await client.disconnect()
                
                return {'success': True, 'groups': groups, 'count': len(groups)}
            
            result = run_async(load_groups_async())
            return jsonify(result)
        except Exception as e:
            print(f"[API] Load groups error: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
    try:
        data = request.json
        account_ids = data.get('account_ids', [])
        group_ids = data.get('group_ids', [])
        message = data.get('message', '')
        delay = data.get('delay', 0)
        
        if not account_ids or not group_ids or not message:
            return jsonify({'error': 'Missing parameters'}), 400
        
        api_id, api_hash = get_api_credentials()
        accounts = get_all_accounts()
        results = []
        
        async def send_messages_async():
            for account_id in account_ids:
                account = next((acc for acc in accounts if acc[0] == account_id), None)
                if not account:
                    continue
                
                session_name = account[2]
                
                try:
                    client = TelegramClient(session_name, int(api_id), api_hash)
                    await client.connect()
                    
                    for group_id in group_ids:
                        try:
                            await asyncio.sleep(delay)
                            await client.send_message(int(group_id), message)
                            print(f"[API] Message sent to group {group_id}")
                            results.append({
                                'account_id': account_id,
                                'group_id': group_id,
                                'status': 'sent'
                            })
                        except Exception as e:
                            print(f"[API] Failed to send message: {str(e)}")
                            results.append({
                                'account_id': account_id,
                                'group_id': group_id,
                                'status': 'failed',
                                'error': str(e)
                            })
                    
                    await client.disconnect()
                except Exception as e:
                    print(f"[API] Send message error for account {account_id}: {str(e)}")
                    results.append({
                        'account_id': account_id,
                        'group_id': 'all',
                        'status': 'failed',
                        'error': str(e)
                    })
        
        run_async(send_messages_async())
        
        return jsonify({
            'success': True,
            'results': results,
            'total_sent': sum(1 for r in results if r['status'] == 'sent')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5000, threaded=True)
