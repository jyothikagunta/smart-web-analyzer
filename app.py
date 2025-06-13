from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
app.secret_key = 'secret'

# -------------------- Database Config --------------------
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)

# -------------------- User Model --------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

# Create DB Tables
with app.app_context():
    db.create_all()

# -------------------- Homepage (redirects to url-input if logged in) --------------------
@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('url_input'))
    return redirect(url_for('login'))

# -------------------- URL Input Page --------------------
@app.route('/url-input')
def url_input():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('url_input.html')

# -------------------- Register --------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return render_template('register.html', error='Username already exists!')
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

# -------------------- Login --------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['username'] = username
            return redirect(url_for('url_input'))
        return render_template('login.html', error='Invalid username or password.')
    return render_template('login.html')

# -------------------- Logout --------------------
@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('url', None)
    session.pop('webpage_info', None)
    return redirect(url_for('login'))

# -------------------- Pricing Page --------------------
@app.route('/pricing')
def pricing():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('pricing.html')

# -------------------- Enterprise Page --------------------
@app.route('/features')
def features():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('features.html')

# -------------------- Documentation Page --------------------
@app.route('/documentation')
def documentation():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('documentation.html')

# -------------------- Extract Web Content --------------------
def extract_webpage_content(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        for script in soup(["script", "style"]):
            script.decompose()
        title = soup.find('title')
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        content = ' '.join(chunk for chunk in chunks if chunk)
        if len(content) > 3000:
            content = content[:3000] + "..."
        return {
            'title': title.get_text().strip() if title else "No title",
            'description': meta_desc.get('content', '') if meta_desc else '',
            'content': content,
            'url': url
        }
    except Exception as e:
        print(f"Error: {e}")
        return {
            'title': 'External webpage',
            'description': 'Could not extract content',
            'content': f'Viewing: {url}, but unable to read content.',
            'url': url
        }

# -------------------- Google Gemini Chat --------------------
API_KEY = "AIzaSyCr4wHLetcNe4NHyNjqheFK4TsVIt-Y9Wc"
MODEL = "gemini-1.5-flash"

@app.route('/start', methods=['POST'])
def start():
    if 'username' not in session:
        return redirect(url_for('login'))
    url = request.form['url']
    session['url'] = url
    session['webpage_info'] = extract_webpage_content(url)
    return redirect(url_for('chat'))

@app.route('/chat')
def chat():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html', url=session.get('url'), webpage_info=session.get('webpage_info'))

@app.route('/chat', methods=['POST'])
def get_reply():
    if 'username' not in session:
        return jsonify({"reply": "Session expired. Please log in again."})

    message = request.json['message']
    webpage_info = session.get('webpage_info', {})

    context_prompt = f"""
You are analyzing a webpage:

Title: {webpage_info.get('title')}
URL: {webpage_info.get('url')}
Description: {webpage_info.get('description')}
Content: {webpage_info.get('content')}

User Question: {message}
"""

    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}",
            json={"contents": [{"parts": [{"text": context_prompt}]}]}
        )
        data = response.json()
        reply = data['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        print(f"Gemini API Error: {e}")
        reply = "Sorry, I encountered an error."

    return jsonify({"reply": reply})

# -------------------- Start New Chat --------------------
@app.route('/new-chat')
def new_chat():
    session.pop('url', None)
    session.pop('webpage_info', None)
    return redirect(url_for('url_input'))

# -------------------- Run App --------------------
if __name__ == '__main__':
    app.run(debug=True)
