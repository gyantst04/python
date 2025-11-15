from flask import Flask,render_template,request,jsonify,redirect,url_for,session
import subprocess
import os 
import tempfile 
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'fallback_secret_key')

# Discord OAuth Configuration
DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
DISCORD_REDIRECT_URI = os.getenv('DISCORD_REDIRECT_URI')
DISCORD_API_BASE_URL = 'https://discord.com/api/v10'
DISCORD_OAUTH_URL = f'https://discord.com/api/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&redirect_uri={DISCORD_REDIRECT_URI}&response_type=code&scope=identify'

@app.route('/')
def home():
    # If user is logged in, redirect to dashboard
    if 'user' in session:
        return redirect(url_for('dashboard'))
    # Otherwise, show the main IDE page
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/discord-login')
def discord_login():
    return redirect(DISCORD_OAUTH_URL)

@app.route('/callback')
def callback():
    # Get the authorization code from the request
    code = request.args.get('code')
    
    # Exchange the code for an access token
    token_url = f'{DISCORD_API_BASE_URL}/oauth2/token'
    token_data = {
        'client_id': DISCORD_CLIENT_ID,
        'client_secret': DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': DISCORD_REDIRECT_URI
    }
    
    token_response = requests.post(token_url, data=token_data)
    token_json = token_response.json()
    
    if 'access_token' not in token_json:
        return "Error getting access token", 400
    
    access_token = token_json['access_token']
    
    # Use the access token to get user information
    user_url = f'{DISCORD_API_BASE_URL}/users/@me'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    
    user_response = requests.get(user_url, headers=headers)
    user_json = user_response.json()
    
    # Store user info in session
    session['user'] = {
        'id': user_json['id'],
        'username': user_json['username'],
        'discriminator': user_json['discriminator'],
        'avatar': user_json.get('avatar')
    }
    
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    # Check if user is logged in
    if 'user' not in session:
        return redirect(url_for('login'))
    
    return render_template('dashboard.html', user=session['user'])

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))

@app.route('/execute',methods=['POST','GET'])
def code_editor():
    # Check if user is logged in to use the editor
    if 'user' not in session:
        return redirect(url_for('login'))
    
    language = request.form.get('language')
    code = request.form.get('code')
    
    with tempfile.NamedTemporaryFile(delete=False,suffix=f'.py') as temp_file:
        temp_file.write(code.encode())
        tempfile_path = temp_file.name
    
    output=''
    try:
        output = subprocess.check_output(['python',tempfile_path],stderr=subprocess.STDOUT).decode()
    
    except subprocess.CalledProcessError as e:
        output = e.output.decode() if e.output else str(e)
        
    finally:
        # clean up the temp files
        os.remove(tempfile_path)
    
    return jsonify({'output':output})

if __name__ == '__main__':
    app.run(debug=True)