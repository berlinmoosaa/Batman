# Batman - Telegram Multi-Account Manager

A powerful Flask-based web application for managing multiple Telegram accounts with a dark Batman theme. Send messages to multiple groups from multiple accounts with ease!

## Features

✨ **Dark Batman Theme** - Black & Red night theme with smooth animations

🔐 **Multi-Account Support** - Connect and manage multiple Telegram accounts

📱 **Group Management** - Load and manage all your joined groups

💬 **Bulk Messaging** - Send messages to multiple groups from multiple accounts simultaneously

⏱️ **Delay Control** - Configure delay between messages to avoid rate limiting

💾 **Auto-Save Credentials** - API credentials are saved securely after first entry

🎨 **Modern UI** - Beautiful animated interface with smooth transitions

⚡ **Fast Performance** - Optimized for speed on localhost

## Installation

### Prerequisites
- Python 3.8+
- pip (Python package manager)
- Chrome or Firefox browser

### Setup

1. **Clone or download this repository**

```bash
cd Batman
```

2. **Install dependencies**

```bash
pip install -r requirements.txt
```

3. **Get Telegram API Credentials**
   - Go to https://my.telegram.org/
   - Login with your Telegram account
   - Go to API Development Tools
   - Create a new app
   - Copy your API ID and API Hash

## Running the Application

1. **Start the Flask server**

```bash
python app.py
```

The server will start on `http://localhost:5000`

2. **Open in your browser**

Navigate to `http://localhost:5000` in Chrome or Firefox

## Usage Guide

### First Time Setup
1. Enter your Telegram API ID and API Hash
2. Click "Save Settings"
3. Settings are now permanently saved

### Adding Accounts
1. Go to "Accounts" page
2. Enter your phone number (with country code)
3. Click "Login"
4. Enter the verification code sent to your Telegram
5. Your account is now connected!

### Loading Groups
1. Go to "Groups" page
2. Select an account from the dropdown
3. Click "Load Groups"
4. All groups from that account will be loaded

### Sending Messages
1. Go to "Send Messages" page
2. Enter your message in the text area
3. Set delay between messages (in seconds)
4. Select accounts and groups using checkboxes
5. Click "Select All Accounts" and "Select All Groups" for quick selection
6. Click "Send Messages"
7. View the results in the summary

## Database

The application uses SQLite for local storage:
- `telegram_data.db` - Stores API credentials, accounts, and groups

## Security Notes

⚠️ **Important**: This application stores Telegram session files and credentials locally. Only use on trusted computers.

- Never share your API ID and Hash
- Session files are created in the application directory
- Keep your database secure

## Troubleshooting

### "API credentials not set" error
- Go to Settings page and save your API ID and Hash again

### Groups not loading
- Make sure the account is properly connected
- Check that your Telegram account has access to groups

### Messages not sending
- Verify the group IDs are correct
- Check Telegram rate limits (may need to increase delay)
- Ensure accounts are still connected

## File Structure

```
Batman/
├── app.py                 # Flask application
├── requirements.txt       # Python dependencies
├── telegram_data.db      # SQLite database
├── templates/
│   └── index.html        # Main HTML page
└── static/
    ├── css/
    │   └── style.css     # Styling
    └── js/
        └── app.js        # Frontend logic
```

## Technologies Used

- **Backend**: Flask, Telethon, SQLite
- **Frontend**: HTML5, CSS3, JavaScript
- **Styling**: Dark theme with red accents
- **Database**: SQLite3

## Credits

Created for managing Telegram accounts efficiently with a modern, user-friendly interface.

## License

This project is open source and available under the MIT License.
