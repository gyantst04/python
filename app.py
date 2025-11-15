from flask import Flask,render_template,request,jsonify,redirect,url_for,session
import subprocess
import os 
import tempfile 
import requests
import json
import uuid
from dotenv import load_dotenv
from functools import wraps

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

# Server data storage
SERVERS_FILE = 'servers.json'

# Decorator to require login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Redirect to dashboard if already logged in
def redirect_if_logged_in(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' in session:
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Load servers from file
def load_servers():
    if os.path.exists(SERVERS_FILE):
        with open(SERVERS_FILE, 'r') as f:
            return json.load(f)
    return {}

# Save servers to file
def save_servers(servers):
    with open(SERVERS_FILE, 'w') as f:
        json.dump(servers, f, indent=2)

# Get user servers
def get_user_servers(user_id):
    servers = load_servers()
    return servers.get(user_id, {})

# Add server for user
def add_user_server(user_id, server_name):
    servers = load_servers()
    if user_id not in servers:
        servers[user_id] = {}
    
    server_id = str(uuid.uuid4())
    servers[user_id][server_id] = {
        'id': server_id,
        'name': server_name,
        'status': 'stopped',
        'startup_file': '',
        'logs': [],
        'files': {}
    }
    
    save_servers(servers)
    return server_id

# Update server
def update_server(user_id, server_id, data):
    servers = load_servers()
    if user_id in servers and server_id in servers[user_id]:
        servers[user_id][server_id].update(data)
        save_servers(servers)
        return True
    return False

# Delete server
def delete_server(user_id, server_id):
    servers = load_servers()
    if user_id in servers and server_id in servers[user_id]:
        del servers[user_id][server_id]
        save_servers(servers)
        return True
    return False

@app.route('/')
@redirect_if_logged_in
def home():
    return render_template('login.html')

@app.route('/login')
@redirect_if_logged_in
def login():
    return render_template('login.html')

@app.route('/discord-login')
@redirect_if_logged_in
def discord_login():
    return redirect(DISCORD_OAUTH_URL)

@app.route('/callback')
@redirect_if_logged_in
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
@login_required
def dashboard():
    user_id = session['user']['id']
    servers = get_user_servers(user_id)
    return render_template('dashboard.html', user=session['user'], servers=servers)

@app.route('/servers')
@login_required
def servers():
    user_id = session['user']['id']
    servers = get_user_servers(user_id)
    return render_template('servers.html', user=session['user'], servers=servers)

@app.route('/server/<server_id>')
@login_required
def server_detail(server_id):
    user_id = session['user']['id']
    servers = get_user_servers(user_id)
    if server_id not in servers:
        return redirect(url_for('servers'))
    server = servers[server_id]
    return render_template('server_detail.html', user=session['user'], server=server)

@app.route('/server/<server_id>/files')
@login_required
def server_files(server_id):
    user_id = session['user']['id']
    servers = get_user_servers(user_id)
    if server_id not in servers:
        return redirect(url_for('servers'))
    server = servers[server_id]
    return render_template('server_files.html', user=session['user'], server=server)

@app.route('/server/<server_id>/files/create', methods=['POST'])
@login_required
def create_file(server_id):
    user_id = session['user']['id']
    file_name = request.form.get('file_name')
    file_content = request.form.get('file_content', '')
    
    servers = load_servers()
    if user_id in servers and server_id in servers[user_id]:
        server = servers[user_id][server_id]
        if 'files' not in server:
            server['files'] = {}
        server['files'][file_name] = {
            'content': file_content
        }
        save_servers(servers)
    
    return redirect(url_for('server_files', server_id=server_id))

@app.route('/server/<server_id>/files/edit', methods=['POST'])
@login_required
def edit_file(server_id):
    user_id = session['user']['id']
    file_name = request.form.get('file_name')
    file_content = request.form.get('file_content')
    
    servers = load_servers()
    if user_id in servers and server_id in servers[user_id]:
        server = servers[user_id][server_id]
        if 'files' in server and file_name in server['files']:
            server['files'][file_name]['content'] = file_content
            save_servers(servers)
    
    return jsonify({'status': 'success'})

@app.route('/server/<server_id>/files/delete', methods=['POST'])
@login_required
def delete_file(server_id):
    user_id = session['user']['id']
    file_name = request.form.get('file_name')
    
    servers = load_servers()
    if user_id in servers and server_id in servers[user_id]:
        server = servers[user_id][server_id]
        if 'files' in server and file_name in server['files']:
            del server['files'][file_name]
            save_servers(servers)
    
    return jsonify({'status': 'success'})

@app.route('/server/<server_id>/files/rename', methods=['POST'])
@login_required
def rename_file(server_id):
    user_id = session['user']['id']
    old_name = request.form.get('old_name')
    new_name = request.form.get('new_name')
    
    servers = load_servers()
    if user_id in servers and server_id in servers[user_id]:
        server = servers[user_id][server_id]
        if 'files' in server and old_name in server['files']:
            # Move file content to new name
            server['files'][new_name] = server['files'][old_name]
            del server['files'][old_name]
            save_servers(servers)
    
    return jsonify({'status': 'success'})

@app.route('/server/<server_id>/console')
@login_required
def server_console(server_id):
    user_id = session['user']['id']
    servers = get_user_servers(user_id)
    if server_id not in servers:
        return redirect(url_for('servers'))
    server = servers[server_id]
    return render_template('server_console.html', user=session['user'], server=server)

@app.route('/server/<server_id>/settings')
@login_required
def server_settings(server_id):
    user_id = session['user']['id']
    servers = get_user_servers(user_id)
    if server_id not in servers:
        return redirect(url_for('servers'))
    server = servers[server_id]
    return render_template('server_settings.html', user=session['user'], server=server)

@app.route('/create_server', methods=['POST'])
@login_required
def create_server():
    user_id = session['user']['id']
    server_name = request.form.get('server_name')
    if server_name:
        server_id = add_user_server(user_id, server_name)
    return redirect(url_for('servers'))

@app.route('/server/<server_id>/start', methods=['POST'])
@login_required
def start_server(server_id):
    user_id = session['user']['id']
    servers = load_servers()
    if user_id in servers and server_id in servers[user_id]:
        server = servers[user_id][server_id]
        if server['startup_file'] and server['startup_file'] in server['files']:
            # Add log entry
            if 'logs' not in server:
                server['logs'] = []
            server['logs'].append(f"Starting server {server['name']}...")
            server['status'] = 'running'
            save_servers(servers)
    return jsonify({'status': 'success'})

@app.route('/server/<server_id>/stop', methods=['POST'])
@login_required
def stop_server(server_id):
    user_id = session['user']['id']
    servers = load_servers()
    if user_id in servers and server_id in servers[user_id]:
        server = servers[user_id][server_id]
        server['status'] = 'stopped'
        if 'logs' not in server:
            server['logs'] = []
        server['logs'].append(f"Stopping server {server['name']}...")
        save_servers(servers)
    return jsonify({'status': 'success'})

@app.route('/server/<server_id>/update_settings', methods=['POST'])
@login_required
def update_server_settings(server_id):
    user_id = session['user']['id']
    name = request.form.get('name')
    startup_file = request.form.get('startup_file')
    
    data = {}
    if name:
        data['name'] = name
    if startup_file is not None:
        data['startup_file'] = startup_file
    
    update_server(user_id, server_id, data)
    return redirect(url_for('server_settings', server_id=server_id))

@app.route('/server/<server_id>/delete', methods=['POST'])
@login_required
def delete_server_route(server_id):
    user_id = session['user']['id']
    delete_server(user_id, server_id)
    return redirect(url_for('servers'))

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html', user=session['user'])

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/execute',methods=['POST','GET'])
@login_required
def code_editor():
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