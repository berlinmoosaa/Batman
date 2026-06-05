from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import sqlite3
from datetime import datetime
import hashlib
import asyncio
import threading
import sys
import logging
from concurrent.futures import ThreadPoolExecutor
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

# ==================== LOGGING SETUP ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== FLASK APP SETUP ====================
app = Flask(__name__)
app.secret_key = 'batman_secret_key_2026'
CORS(app)

DB_FILE = 'telegram_data.db'

# ==================== EXECUTOR FOR ASYNC TASKS ====================
# Use ThreadPoolExecutor to run async code in separate threads
executor = ThreadPoolExecutor(max_workers=5)

# ==================== WINDOWS ASYNCIO FIX ====================
def setup_asyncio():
    """Setup asyncio for Windows compatibility"""
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

setup_asyncio()

# ==================== DATABASE CONNECTION ====================
def get_db_connection(db_path):
    """Create a database connection with timeout"""
    conn = sqlite3.connect(db_path, timeout=20.0, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout = 5000')
    return conn

# ==================== ASYNC EXECUTOR WRAPPER ====================
def run_in_executor(async_func):
    """
    Run async function in a dedicated thread with its own event loop.
    This completely isolates async operations from Flask's threading.
    """
    def run_async_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(async_func)
        finally:
            loop.close()
    
    # Run in thread pool
    future = executor.submit(run_async_in_thread)
    return future.result(timeout=120)  # 120 second timeout

# ==================== INITIALIZE DATABASE ====================
def init_db():
    """Initialize database tables"""
    try:
        conn = get_db_connection(DB_FILE)
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, api_id TEXT, api_hash TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY, phone TEXT, session_name TEXT, created_at TIMESTAMP)')
        c.execute('CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY, account_id INTEGER, group_id INTEGER, group_name TEXT, group_username TEXT, members_count INTEGER, created_at TIMESTAMP)')
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")

init_db()

# ==================== DATABASE FUNCTIONS ====================
def get_api_credentials():
    """Get stored API credentials"""
    try:
        conn = get_db_connection(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT api_id, api_hash FROM settings LIMIT 1')
        result = c.fetchone()
        conn.close()
        return result if result else (None, None)
    except Exception as e:
        logger.error(f"Error getting API credentials: {e}")
        return (None, None)

def save_api_credentials(api_id, api_hash):
    """Save API credentials"""
    try:
        conn = get_db_connection(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM settings')
        c.execute('INSERT INTO settings (api_id, api_hash) VALUES (?, ?)', (str(api_id), str(api_hash)))
        conn.commit()
        conn.close()
        logger.info("API credentials saved")
    except Exception as e:
        logger.error(f"Error saving API credentials: {e}")
        raise

def get_all_accounts():
    """Get all registered accounts"""
    try:
        conn = get_db_connection(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT id, phone, session_name, created_at FROM accounts')
        accounts = c.fetchall()
        conn.close()
        return accounts
    except Exception as e:
        logger.error(f"Error getting accounts: {e}")
        return []

def save_account(phone, session_name):
    """Save a new account"""
    try:
        conn = get_db_connection(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO accounts (phone, session_name, created_at) VALUES (?, ?, ?)', 
                  (phone, session_name, datetime.now()))
        conn.commit()
        account_id = c.lastrowid
        conn.close()
        logger.info(f"Account saved: {phone}")
        return account_id
    except Exception as e:
        logger.error(f"Error saving account: {e}")
        raise

def get_groups_for_account(account_id):
    """Get groups for an account"""
    try:
        conn = get_db_connection(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT id, group_id, group_name, group_username, members_count FROM groups WHERE account_id = ?', 
                  (account_id,))
        groups = c.fetchall()
        conn.close()
        return groups
    except Exception as e:
        logger.error(f"Error getting groups: {e}")
        return []

def save_groups(account_id, groups_list):
    """Save groups for an account"""
    try:
        conn = get_db_connection(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM groups WHERE account_id = ?', (account_id,))
        for group in groups_list:
            c.execute('INSERT INTO groups (account_id, group_id, group_name, group_username, members_count, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                      (account_id, group.get('id'), group.get('title'), group.get('username', 'N/A'), 
                       group.get('members_count', 0), datetime.now()))
        conn.commit()
        conn.close()
        logger.info(f"Saved {len(groups_list)} groups for account {account_id}")
    except Exception as e:
        logger.error(f"Error saving groups: {e}")
        raise

# ==================== ASYNC TELEGRAM FUNCTIONS ====================
async def telegram_login(phone, api_id, api_hash, session_name):
    """Async function to login to Telegram"""
    client = TelegramClient(session_name, int(api_id), api_hash)
    await client.connect()
    
    if not await client.is_user_authorized():
        await client.send_code_request(phone)
        await client.disconnect()
        return {'success': True, 'status': 'code_required', 'phone': phone, 'session_name': session_name}
    else:
        account_id = save_account(phone, session_name)
        await client.disconnect()
        return {'success': True, 'status': 'logged_in', 'account_id': account_id, 'phone': phone}

async def telegram_verify(phone, code, api_id, api_hash, session_name):
    """Async function to verify code"""
    client = TelegramClient(session_name, int(api_id), api_hash)
    await client.connect()
    
    try:
        await client.sign_in(phone, code)
    except SessionPasswordNeededError:
        await client.disconnect()
        return {'error': '2FA not supported yet'}
    
    account_id = save_account(phone, session_name)
    await client.disconnect()
    return {'success': True, 'status': 'verified', 'account_id': account_id, 'phone': phone}

async def telegram_load_groups(session_name, api_id, api_hash, account_id):
    """Async function to load groups"""
    client = TelegramClient(session_name, int(api_id), api_hash)
    await client.connect()
    
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
    await client.disconnect()
    return {'success': True, 'groups': groups, 'count': len(groups)}

async def telegram_send_messages(account_ids, group_ids, message, delay, api_id, api_hash, accounts):
    """Async function to send messages"""
    results = []
    
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
                    logger.info(f"Message sent to group {group_id}")
                    results.append({'account_id': account_id, 'group_id': group_id, 'status': 'sent'})
                except Exception as e:
                    logger.error(f"Failed to send message: {e}")
                    results.append({'account_id': account_id, 'group_id': group_id, 'status': 'failed', 'error': str(e)})
            
            await client.disconnect()
        except Exception as e:
            logger.error(f"Send message error for account {account_id}: {e}")
            results.append({'account_id': account_id, 'group_id': 'all', 'status': 'failed', 'error': str(e)})
    
    return results

# ==================== FLASK ROUTES ====================
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
        logger.error(f"Save settings error: {e}")
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
        
        logger.info(f"Login attempt for phone: {phone}")
        
        try:
            # Run async code in executor
            result = run_in_executor(telegram_login(phone, api_id, api_hash, session_name))
            return jsonify(result)
        except Exception as e:
            logger.error(f"Login error: {e}")
            return jsonify({'error': f'Telegram error: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"General login error: {e}")
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
        
        logger.info(f"Verify attempt for phone: {phone}")
        
        try:
            result = run_in_executor(telegram_verify(phone, code, api_id, api_hash, session_name))
            if 'error' in result:
                return jsonify(result), 400
            return jsonify(result)
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return jsonify({'error': f'Verification failed: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"General verify error: {e}")
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
        
        logger.info(f"Loading groups for account {account_id}")
        
        try:
            result = run_in_executor(telegram_load_groups(session_name, api_id, api_hash, account_id))
            return jsonify(result)
        except Exception as e:
            logger.error(f"Load groups error: {e}")
            return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"General load groups error: {e}")
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
        
        logger.info(f"Sending message to {len(group_ids)} groups from {len(account_ids)} accounts")
        
        try:
            results = run_in_executor(telegram_send_messages(account_ids, group_ids, message, delay, api_id, api_hash, accounts))
            
            return jsonify({
                'success': True,
                'results': results,
                'total_sent': sum(1 for r in results if r['status'] == 'sent')
            })
        except Exception as e:
            logger.error(f"Send message error: {e}")
            return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"General send message error: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== ERROR HANDLERS ====================
@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
