from flask import Flask, request, jsonify, session, redirect, url_for, render_template
from flask_limiter import Limiter
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
from flask_limiter.util import get_remote_address
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from google import genai
from flask_sqlalchemy import SQLAlchemy
from secrets import compare_digest
import secrets
import os

load_dotenv()

app= Flask(__name__)

csrf = CSRFProtect(app)

CORS(app, resources={
    r"/chat": {"origins": ["https://acme.com"], "supports_credentials": True},
    r"/history": {"origins": ["https://acme.com"], "supports_credentials": True}
})

def get_real_ip():
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        return forwarded.split(',')[-1].strip()
    return request.remote_addr

limiter = Limiter(
    app=app,
    key_func=get_real_ip,
    default_limits=['200 per day','50 per hour','8 per minute'],
    storage_uri='memory://'
)

app.secret_key = os.getenv('SECRET_KEY')
if not app.secret_key:
    raise RuntimeError('SECRET_KEY is not set')

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')         
if not ADMIN_PASSWORD:
    raise RuntimeError('ADMIN_PASSWORD is not set')

database_url = os.getenv('DATABASE_URL', 'sqlite:///chat.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://','postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url

app.config['SESSION_COOKIE_HTTPONLY']=True
app.config['SESSION_COOKIE_SECURE'] = os.getenv('RENDER') is not None
app.config['SESSION_COOKIE_SAMESITE']='None'


db = SQLAlchemy(app)

class message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(50))
    role = db.Column(db.String(10))
    
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

with app.app_context():
    db.create_all() 

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

system_prompt = """Instructions"""

@app.route('/chat', methods=['POST'])
@csrf.exempt
def chat():
    print(f'Real IP: {get_real_ip()}')
    print(f'X-Forwarded-For header: {request.headers.get("X-Forwarded-For")}')
    if 'session_id' not in session:
        session['session_id']=secrets.token_hex(8)
    session_id = session['session_id']

    data = request.get_json() or {}
    user_message = data.get('message','').strip()
    if not user_message:
        return jsonify({'error':'Please send a message'}), 400

    if len(user_message)>1500: 
        return jsonify({'error':'Message too long(max 1500 characters)'}), 400

    db.session.add(message(session_id=session_id, role='user', content=user_message))
    db.session.commit()

    recent_msg = message.query.filter_by(session_id=session_id).order_by(message.id.desc()).limit(10).all()
    recent_msg.reverse()

    conversation_context = ''
    for m in recent_msg:
        if m.role == 'user':
            conversation_context += f'\nUser: {m.content}'
        else:
            conversation_context += f'\nAssistant: {m.content}'

    BUSINESS_TIMEZONE = ZoneInfo('America/Los_Angeles')

    current_time = datetime.now(BUSINESS_TIMEZONE).strftime('%A, %B %d, %Y at %I:%M %p %Z')

    full_msg = system_prompt + f'\n\nCurrent date and time (clinic local time): {current_time}' + '\n\nConversation so far: ' + conversation_context + '\n\nUser: ' + user_message
    


    try:
        response = client.models.generate_content(model= 'gemini-3.1-flash-lite', contents= full_msg )
        if not response.text:
            return jsonify({'error': 'No response generated, please rephrase'}), 500
        reply = response.text
    except Exception as error:
        print(f'Gemini API error: {error}')
        return jsonify({'error':'Something went wrong. Please try again.'}), 500

    db.session.add(message(session_id=session_id, role='assistant', content=reply))
    db.session.commit()
    return jsonify({'response':reply})


@app.route('/history', methods=['GET'])
def history():
    if 'session_id' not in session:
        return jsonify({'messages':[]})
    session_id = session['session_id']
    messages = message.query.filter_by(session_id=session_id).all()

    result = []
    for m in messages:
        result.append({'role':m.role, 'content': m.content})
    return jsonify({'messages':result})


@app.route('/admin/chat/<session_id>')
def admin_conversation(session_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    messages = message.query.filter_by(session_id=session_id).order_by(message.id).all()

    return render_template('admin_conversation.html', messages=messages, session_id=session_id)

@app.route('/admin/login', methods=['GET', 'POST'])
@limiter.limit('5 per minute')
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password', '')
        if compare_digest(password.encode('utf-8'), ADMIN_PASSWORD.encode('utf-8')):
            session['is_admin'] = True
            return redirect(url_for('admin_chats'))
        else:
            return render_template('admin_login.html', error='Incorrect password')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/chats')
def admin_chats():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    from sqlalchemy import func
    sessions_data = db.session.query(
        message.session_id,
        func.count(message.id).label('msg_count'),
        func.max(message.created_at).label('last_time'),
        func.min(message.created_at).label('first_time')
    ).group_by(message.session_id).order_by(func.max(message.created_at).desc()).all()
    sessions_list = []
    for session_id, msg_count, last_time, first_time in sessions_data:
        first_msg = message.query.filter_by(
            session_id = session_id,
            role='user'
        ).order_by(message.id).first()

        preview = first_msg.content[:100] if first_msg else '(no message)'

        sessions_list.append({
            'session_id': session_id,
            'msg_count': msg_count,
            'preview':preview,
            'first_time':first_time,
            'last_time':last_time
        })
    return render_template('admin_chats.html', sessions=sessions_list)

@app.route('/admin/delete/<session_id>', methods=['POST'])
def admin_delete_conversation(session_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    message.query.filter_by(session_id=session_id).delete()
    db.session.commit()
    return redirect(url_for('admin_chats'))

@app.route('/admin/delete_all', methods=['POST'])
@limiter.limit('1 per hour')
def admin_delete_all():
    print(f"[ADMIN DELETE ALL] Triggered at {datetime.now()} from IP {get_real_ip()}")
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    message.query.delete()
    db.session.commit()

    return redirect(url_for('admin_chats'))

@app.errorhandler(429)
def rate_limit_exceeded(e):
    return jsonify({'error':'You are sending too many messages at once, please wait a moment.'}), 429



if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
