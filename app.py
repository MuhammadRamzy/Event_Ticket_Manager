from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import pandas as pd
import uuid
import os
import datetime
import qrcode
from io import BytesIO
import base64
from flask_socketio import SocketIO

app = Flask(__name__)
app.secret_key = uuid.uuid4().hex
socketio = SocketIO(app)

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

EXCEL_PATH = None
stats = {
    'scanned': 0,
    'valid': 0,
    'invalid': 0
}

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    if session.get('is_admin'):
        return redirect(url_for('admin'))
    else:
        return redirect(url_for('scanner'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == 'admin' and password == 'admin':
            session['logged_in'] = True
            session['is_admin'] = True
            return redirect(url_for('admin'))
        elif username == 'scanner' and password == 'scanner':
            session['logged_in'] = True
            session['is_admin'] = False
            return redirect(url_for('scanner'))
        else:
            flash('Invalid credentials')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin')
def admin():
    if not session.get('logged_in') or not session.get('is_admin'):
        return redirect(url_for('login'))
    
    global stats
    return render_template('admin.html', stats=stats, excel_path=EXCEL_PATH)

@app.route('/scanner')
def scanner():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return render_template('scanner.html')

@app.route('/upload_excel', methods=['POST'])
def upload_excel():
    if not session.get('logged_in') or not session.get('is_admin'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part'})
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file'})
    
    if file and file.filename.endswith('.xlsx'):
        filename = os.path.join(UPLOAD_FOLDER, 'tickets.xlsx')
        file.save(filename)
        global EXCEL_PATH
        EXCEL_PATH = filename
        return jsonify({'success': True, 'message': 'File uploaded successfully'})
    
    return jsonify({'success': False, 'message': 'Invalid file format'})

@app.route('/verify', methods=['POST'])
def verify():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    global EXCEL_PATH, stats
    
    if not EXCEL_PATH:
        return jsonify({'success': False, 'message': 'No Excel file uploaded'})
    
    ticket_id = request.json.get('ticket_id')
    
    if not ticket_id:
        return jsonify({'success': False, 'message': 'No ticket ID provided'})
    
    try:
        df = pd.read_excel(EXCEL_PATH)
        
        if 'uuid' not in df.columns:
            return jsonify({'success': False, 'message': 'UUID column not found in Excel'})
        
        stats['scanned'] += 1
        
        if ticket_id in df['uuid'].values:
            row_idx = df[df['uuid'] == ticket_id].index[0]
            
            if 'scanned' in df.columns and df.at[row_idx, 'scanned'] == True:
                return jsonify({
                    'success': True,
                    'valid': False,
                    'message': 'Ticket already scanned',
                    'data': {
                        'name': df.at[row_idx, 'name'] if 'name' in df.columns else 'N/A',
                        'email': df.at[row_idx, 'email'] if 'email' in df.columns else 'N/A',
                        'ticket_id': ticket_id,
                        'already_scanned': True,
                        'scan_time': df.at[row_idx, 'scan_time'] if 'scan_time' in df.columns else 'N/A'
                    }
                })
            
            if 'scanned' not in df.columns:
                df['scanned'] = False
            if 'scan_time' not in df.columns:
                df['scan_time'] = None
            
            df.at[row_idx, 'scanned'] = True
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            df.at[row_idx, 'scan_time'] = current_time
            
            df.to_excel(EXCEL_PATH, index=False)
            
            stats['valid'] += 1
            socketio.emit('stats_update', stats)
            
            return jsonify({
                'success': True,
                'valid': True,
                'message': 'Ticket valid',
                'data': {
                    'name': df.at[row_idx, 'name'] if 'name' in df.columns else 'N/A',
                    'email': df.at[row_idx, 'email'] if 'email' in df.columns else 'N/A',
                    'ticket_id': ticket_id,
                    'already_scanned': False,
                    'scan_time': current_time
                }
            })
        else:
            stats['invalid'] += 1
            socketio.emit('stats_update', stats)
            
            return jsonify({
                'success': True,
                'valid': False,
                'message': 'Invalid ticket',
                'data': {
                    'ticket_id': ticket_id
                }
            })
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/generate_tickets', methods=['POST'])
def generate_tickets():
    if not session.get('logged_in') or not session.get('is_admin'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    global EXCEL_PATH
    
    if not EXCEL_PATH:
        return jsonify({'success': False, 'message': 'No Excel file uploaded'})
    
    try:
        df = pd.read_excel(EXCEL_PATH)
        
        if 'uuid' not in df.columns:
            df['uuid'] = [str(uuid.uuid4()) for _ in range(len(df))]
        
        if 'scanned' not in df.columns:
            df['scanned'] = False
        
        if 'scan_time' not in df.columns:
            df['scan_time'] = None
        
        qr_codes = []
        
        for idx, row in df.iterrows():
            ticket_id = row['uuid']
            img = qrcode.make(ticket_id)
            buffered = BytesIO()
            img.save(buffered)
            img_str = base64.b64encode(buffered.getvalue()).decode()
            qr_codes.append({
                'ticket_id': ticket_id,
                'qr_code': img_str,
                'name': row['name'] if 'name' in df.columns else f"Attendee {idx+1}"
            })
        
        df.to_excel(EXCEL_PATH, index=False)
        
        return jsonify({'success': True, 'message': 'Tickets generated', 'qr_codes': qr_codes})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/get_stats')
def get_stats():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    global stats, EXCEL_PATH
    
    if EXCEL_PATH:
        try:
            df = pd.read_excel(EXCEL_PATH)
            if 'scanned' in df.columns:
                stats['valid'] = df['scanned'].sum()
                stats['scanned'] = stats['valid'] + stats['invalid']
        except:
            pass
    
    return jsonify({'success': True, 'stats': stats})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)