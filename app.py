#!/usr/bin/env python3
"""
Flask Web Application for Batman - Telegram Manager
Replaces PyQt6 with a simple, easy-to-use web interface
"""

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import asyncio
import threading
from datetime import datetime
from config import config
from account_manager import account_manager
from group_manager import group_manager

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'batman-secret-key-2024'
socketio = SocketIO(app, cors_allowed_origins="*")

# Store async loop
loop = None

def start_asyncio_loop():
    """Start asyncio event loop in background thread"""
    global loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    def run_loop():
        loop.run_forever()
    
    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()
    return loop

def emit_log(message):
    """Emit log message to all connected clients"""
    socketio.emit('log', {
        'message': message,
        'timestamp': datetime.now().strftime('%H:%M:%S')
    }, broadcast=True)

def run_async(coro):
    """Run async coroutine in the background loop"""
    return asyncio.run_coroutine_threadsafe(coro, loop)

# ==================== WEB ROUTES ====================

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    """Get application status"""
    return jsonify({
        'configured': config.is_configured(),
        'accounts': len(account_manager.get_accounts())
    })

@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    """Get or save configuration"""
    if request.method == 'GET':
        return jsonify({
            'configured': config.is_configured(),
            'api_id': config.api_id if config.is_configured() else None
        })
    
    elif request.method == 'POST':
        data = request.json
        api_id = data.get('api_id', '').strip()
        api_hash = data.get('api_hash', '').strip()
        
        if not api_id or not api_hash:
            return jsonify({'success': False, 'error': 'Missing API credentials'}), 400
        
        try:
            api_id = int(api_id)
            config.save_config(api_id, api_hash)
            emit_log(f"✓ Configuration saved successfully")
            return jsonify({'success': True})
        except ValueError:
            return jsonify({'success': False, 'error': 'API ID must be a number'}), 400
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts', methods=['GET', 'POST'])
def api_accounts():
    """Get or add accounts"""
    if request.method == 'GET':
        accounts = account_manager.get_accounts()
        return jsonify({'accounts': accounts})
    
    elif request.method == 'POST':
        data = request.json
        phone = data.get('phone', '').strip()
        
        if not phone:
            return jsonify({'success': False, 'error': 'Phone number required'}), 400
        
        if not config.is_configured():
            return jsonify({'success': False, 'error': 'Please configure API credentials first'}), 400
        
        success, message = account_manager.add_account(phone)
        if success:
            emit_log(f"✓ Account added: {phone}")
            # Start async connection
            run_async(account_manager.connect_account(phone))
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'error': message}), 400

@app.route('/api/accounts/<phone>', methods=['DELETE'])
def delete_account(phone):
    """Delete an account"""
    try:
        account_manager.remove_account(phone)
        emit_log(f"✗ Account removed: {phone}")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts/<phone>/verify', methods=['POST'])
def verify_code(phone):
    """Verify authentication code"""
    data = request.json
    code = data.get('code', '').strip()
    
    if not code:
        return jsonify({'success': False, 'error': 'Code required'}), 400
    
    future = run_async(account_manager.verify_code(phone, code))
    try:
        success, message = future.result(timeout=30)
        if success:
            emit_log(f"✓ {phone} verified successfully")
            return jsonify({'success': True, 'message': message})
        else:
            emit_log(f"✗ {phone}: {message}")
            return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts/<phone>/verify-password', methods=['POST'])
def verify_password(phone):
    """Verify 2FA password"""
    data = request.json
    password = data.get('password', '').strip()
    
    if not password:
        return jsonify({'success': False, 'error': 'Password required'}), 400
    
    future = run_async(account_manager.verify_password(phone, password))
    try:
        success, message = future.result(timeout=30)
        if success:
            emit_log(f"✓ {phone} 2FA verified")
            return jsonify({'success': True, 'message': message})
        else:
            emit_log(f"✗ {phone}: {message}")
            return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts/<phone>/disconnect', methods=['POST'])
def disconnect_account(phone):
    """Disconnect account"""
    try:
        run_async(account_manager.disconnect_account(phone))
        emit_log(f"✗ Disconnected: {phone}")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/groups/load', methods=['POST'])
def load_groups():
    """Load groups for an account"""
    data = request.json
    phone = data.get('phone', '').strip()
    
    if not phone:
        return jsonify({'success': False, 'error': 'Phone required'}), 400
    
    async def async_load():
        emit_log(f"⏳ Loading groups from {phone}...")
        client = await account_manager.get_client(phone)
        
        if not client:
            emit_log(f"✗ Cannot connect to {phone}")
            return []
        
        groups = await group_manager.load_groups(client)
        emit_log(f"✓ Loaded {len(groups)} groups from {phone}")
        return groups
    
    future = run_async(async_load())
    try:
        groups = future.result(timeout=120)
        return jsonify({'success': True, 'groups': groups})
    except Exception as e:
        emit_log(f"✗ Error loading groups: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/groups/save', methods=['POST'])
def save_groups():
    """Save selected groups for an account"""
    data = request.json
    phone = data.get('phone', '').strip()
    groups = data.get('groups', [])
    
    if not phone:
        return jsonify({'success': False, 'error': 'Phone required'}), 400
    
    try:
        account_manager.update_groups(phone, groups)
        emit_log(f"✓ Saved {len(groups)} groups for {phone}")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/broadcast', methods=['POST'])
def broadcast():
    """Broadcast message to all selected groups"""
    data = request.json
    message = data.get('message', '').strip()
    delay = int(data.get('delay', 3))
    use_markdown = data.get('markdown', True)
    
    if not message:
        return jsonify({'success': False, 'error': 'Message required'}), 400
    
    if delay < 1:
        delay = 1
    if delay > 3600:
        delay = 3600
    
    async def async_broadcast():
        accounts = account_manager.get_accounts()
        total_sent = 0
        
        for account in accounts:
            phone = account['phone']
            client = await account_manager.get_client(phone)
            
            if not client:
                emit_log(f"⊘ Skipping {phone}: Not connected")
                continue
            
            for group in account.get('groups', []):
                try:
                    parse_mode = 'markdown' if use_markdown else None
                    await group_manager.send_message(
                        client, 
                        group['entity'], 
                        message,
                        parse_mode=parse_mode
                    )
                    total_sent += 1
                    emit_log(f"✓ {group['title']} ({phone})")
                    await asyncio.sleep(delay)
                
                except Exception as e:
                    emit_log(f"✗ Error {group['title']}: {str(e)}")
        
        emit_log(f"\n🎉 Broadcast complete! {total_sent} messages sent 🎉")
        return total_sent
    
    run_async(async_broadcast())
    return jsonify({'success': True, 'message': 'Broadcast started'})

# ==================== WEBSOCKET EVENTS ====================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    emit_log(f"🔗 Client connected")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnected"""
    emit_log(f"🔌 Client disconnected")

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Server error'}), 500

# ==================== MAIN ====================

if __name__ == '__main__':
    # Start asyncio loop
    start_asyncio_loop()
    
    # Check if configured
    if not config.is_configured():
        print("\n" + "="*60)
        print("🦇 BATMAN - Telegram Multi-Account Manager")
        print("="*60)
        print("⚠️  First run detected - Please configure API credentials")
        print("\n📡 Open http://localhost:5000 in your browser")
        print("="*60 + "\n")
    else:
        print("\n" + "="*60)
        print("🦇 BATMAN - Telegram Multi-Account Manager")
        print("="*60)
        print("✓ Configured and ready to use")
        print("📡 Open http://localhost:5000 in your browser")
        print("="*60 + "\n")
    
    print("Press Ctrl+C to stop\n")
    
    socketio.run(app, debug=False, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
