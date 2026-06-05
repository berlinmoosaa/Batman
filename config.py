import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration file paths
CONFIG_DIR = Path.home() / ".batman"
CONFIG_FILE = CONFIG_DIR / "config.json"
SESSIONS_DIR = CONFIG_DIR / "sessions"

# Create necessary directories
CONFIG_DIR.mkdir(exist_ok=True)
SESSIONS_DIR.mkdir(exist_ok=True)

class Config:
    """Base configuration"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'batman-secret-key-change-in-production')
    DEBUG = os.getenv('DEBUG', 'False') == 'True'
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))
    
    # Telegram API credentials
    API_ID = None
    API_HASH = None

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True

def get_config():
    """Get config based on environment"""
    env = os.getenv('FLASK_ENV', 'development')
    if env == 'production':
        return ProductionConfig()
    elif env == 'testing':
        return TestingConfig()
    return DevelopmentConfig()

class TelegramConfig:
    """Telegram configuration manager"""
    def __init__(self):
        self.api_id = None
        self.api_hash = None
        self.load_config()

    def load_config(self):
        """Load configuration from file"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    self.api_id = config.get('api_id')
                    self.api_hash = config.get('api_hash')
            except Exception as e:
                print(f"Error loading config: {e}")

    def save_config(self, api_id, api_hash):
        """Save configuration to file"""
        try:
            config = {
                'api_id': api_id,
                'api_hash': api_hash
            }
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
            self.api_id = api_id
            self.api_hash = api_hash
            return True, "Configuration saved successfully"
        except Exception as e:
            return False, f"Error saving config: {str(e)}"

    def is_configured(self):
        """Check if API credentials are configured"""
        return self.api_id is not None and self.api_hash is not None

    @staticmethod
    def get_session_path(phone_number):
        """Get session file path for a phone number"""
        # Sanitize phone number for filename
        safe_phone = phone_number.replace('+', '').replace(' ', '')
        return SESSIONS_DIR / f"{safe_phone}.session"

# Global config instances
app_config = get_config()
telegram_config = TelegramConfig()
