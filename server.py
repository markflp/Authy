"""
Flask server που χειρίζεται το Discord OAuth2 callback.
Αποθηκεύει τα access tokens ώστε να μπορείς να προσθέτεις χρήστες σε servers.
"""

import json
import os
import requests
from flask import Flask, request, jsonify
import asyncio

bot_loop = None
verify_callback = None

def setup_bot_bridge(loop, callback):
    global bot_loop, verify_callback
    bot_loop = loop
    verify_callback = callback


# ─────────────────────────────────────────────
#  ΡΥΘΜΙΣΕΙΣ - άλλαξε μόνο αυτά
# ─────────────────────────────────────────────
CLIENT_ID     = '1514732749586694234'
CLIENT_SECRET = 'OmAhv7isnByWkMYVLKl7R07pvJRWhKdW' 
REDIRECT_URI  = 'http://localhost:5000/callback'
TOKENS_FILE   = 'tokens.json'   # Εδώ αποθηκεύονται τα tokens
# ─────────────────────────────────────────────

app = Flask(__name__)


def load_tokens() -> dict:
    """Φορτώνει τα αποθηκευμένα tokens από αρχείο."""
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_token(user_id: str, data: dict):
    """Αποθηκεύει το token ενός χρήστη."""
    tokens = load_tokens()
    tokens[user_id] = data
    with open(TOKENS_FILE, 'w') as f:
        json.dump(tokens, f, indent=2)
    print(f'💾 Αποθηκεύτηκε token για user {user_id}')


@app.route('/callback')
def callback():
    """
    Το Discord ανακατευθύνει εδώ μετά την εξουσιοδότηση.
    Ανταλλάσσουμε το 'code' για access_token.
    """
    code = request.args.get('code')

    if not code:
        return '❌ Δεν βρέθηκε authorization code.', 400

    # Ανταλλαγή code → access_token
    token_response = requests.post(
        'https://discord.com/api/oauth2/token',
        data={
            'client_id':     CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type':    'authorization_code',
            'code':          code,
            'redirect_uri':  REDIRECT_URI,
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )

    if token_response.status_code != 200:
        print(f'Token error: {token_response.text}')
        return '❌ Αποτυχία λήψης token. Δοκίμασε ξανά.', 500

    token_data = token_response.json()
    access_token = token_data.get('access_token')

    # Παίρνουμε τα στοιχεία του χρήστη
    user_response = requests.get(
        'https://discord.com/api/users/@me',
        headers={'Authorization': f'Bearer {access_token}'}
    )

    if user_response.status_code != 200:
        return '❌ Αποτυχία λήψης στοιχείων χρήστη.', 500

    user_data = user_response.json()
    user_id   = user_data['id']
    username  = user_data.get('username', 'Unknown')

    # Αποθηκεύουμε: user_id → token_data + user_info
    save_token(user_id, {
        'access_token':  access_token,
        'refresh_token': token_data.get('refresh_token'),
        'token_type':    token_data.get('token_type'),
        'expires_in':    token_data.get('expires_in'),
        'scope':         token_data.get('scope'),
        'username':      username,
    })

    print(f'✅ Χρήστης {username} ({user_id}) εξουσιοδότησε επιτυχώς!')

    # Εμφανίζουμε μήνυμα επιτυχίας στον χρήστη
    return f'''
    <!DOCTYPE html>
    <html lang="el">
    <head>
        <meta charset="UTF-8">
        <title>Επαλήθευση Επιτυχής</title>
        <style>
            body {{
                font-family: -apple-system, sans-serif;
                background: #36393f;
                color: #dcddde;
                display: flex;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
            }}
            .card {{
                background: #2f3136;
                border-radius: 12px;
                padding: 40px;
                text-align: center;
                max-width: 400px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            }}
            .icon {{ font-size: 64px; margin-bottom: 16px; }}
            h1 {{ color: #43b581; margin: 0 0 8px; }}
            p {{ color: #b9bbbe; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">✅</div>
            <h1>Επιτυχής Επαλήθευση!</h1>
            <p>Γεια σου, <strong>{username}</strong>!</p>
            <p>Η εξουσιοδότησή σου ολοκληρώθηκε. Μπορείς να κλείσεις αυτό το παράθυρο.</p>
        </div>
    </body>
    </html>
    '''


@app.route('/add_to_guild', methods=['POST'])
def add_to_guild():
    """
    API endpoint για να προσθέσεις χρήστη σε guild.

    POST body (JSON):
    {
        "user_id":   "123456789",
        "guild_id":  "987654321",
        "bot_token": "ΤΟ_BOT_TOKEN_ΣΟΥ"
    }
    """
    data      = request.json
    user_id   = data.get('user_id')
    guild_id  = data.get('guild_id')
    bot_token = data.get('bot_token')

    if not all([user_id, guild_id, bot_token]):
        return jsonify({'error': 'Λείπουν παράμετροι (user_id, guild_id, bot_token)'}), 400

    tokens = load_tokens()
    if user_id not in tokens:
        return jsonify({'error': f'Δεν βρέθηκε token για user {user_id}'}), 404

    access_token = tokens[user_id]['access_token']

    # Προσθέτουμε τον χρήστη στο guild
    response = requests.put(
        f'https://discord.com/api/guilds/{guild_id}/members/{user_id}',
        json={'access_token': access_token},
        headers={
            'Authorization': f'Bot {bot_token}',
            'Content-Type':  'application/json',
        }
    )

    if response.status_code in (200, 201):
        return jsonify({'success': True, 'message': f'Χρήστης {user_id} προστέθηκε στο guild {guild_id}!'})
    elif response.status_code == 204:
        return jsonify({'success': True, 'message': 'Ο χρήστης είναι ήδη μέλος!'})
    else:
        return jsonify({'error': response.json()}), response.status_code


@app.route('/users')
def list_users():
    """Δείχνει όλους τους χρήστες που έχουν κάνει authorize (για debugging)."""
    tokens = load_tokens()
    users  = [{'user_id': uid, 'username': d.get('username')} for uid, d in tokens.items()]
    return jsonify({'count': len(users), 'users': users})


def run_server():
    """Εκκινεί τον Flask server."""
    app.run(host='0.0.0.0', port=5000, debug=False)


if __name__ == '__main__':
    run_server()
