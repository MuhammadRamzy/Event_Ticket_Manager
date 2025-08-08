from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import csv
import uuid
import os
import datetime
import qrcode
from io import BytesIO
import base64
from flask_socketio import SocketIO
import json
import logging
from werkzeug.utils import secure_filename

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = uuid.uuid4().hex
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Configure SocketIO for better performance
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

CSV_PATH = None
stats = {
    'scanned': 0,
    'valid': 0,
    'invalid': 0,
    'total_tickets': 0,
    'scanned_today': 0,
    'last_scan_time': None,
    'scanner_status': 'offline'
}

# Store recent scans for better monitoring
recent_scans = []
MAX_RECENT_SCANS = 50

def read_csv_data():
    """Read CSV data and return as list of dictionaries"""
    if not CSV_PATH or not os.path.exists(CSV_PATH):
        return []
    
    try:
        with open(CSV_PATH, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            return list(reader)
    except Exception as e:
        logger.error(f"Error reading CSV: {e}")
        return []

def write_csv_data(data):
    """Write data to CSV file"""
    if not CSV_PATH:
        return False
    
    try:
        fieldnames = data[0].keys() if data else ['name', 'email', 'uuid', 'scanned', 'scan_time']
        with open(CSV_PATH, 'w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        return True
    except Exception as e:
        logger.error(f"Error writing CSV: {e}")
        return False

def update_stats():
    """Update statistics from CSV file"""
    global stats, CSV_PATH
    if CSV_PATH and os.path.exists(CSV_PATH):
        try:
            data = read_csv_data()
            if data:
                stats['total_tickets'] = len(data)
                stats['valid'] = sum(1 for row in data if row.get('scanned') == 'True')
                stats['scanned'] = stats['valid'] + stats['invalid']
                
                # Calculate today's scans
                today = datetime.datetime.now().date()
                today_scans = 0
                for row in data:
                    scan_time = row.get('scan_time', '')
                    if scan_time:
                        try:
                            scan_date = datetime.datetime.strptime(scan_time, "%Y-%m-%d %H:%M:%S").date()
                            if scan_date == today:
                                today_scans += 1
                        except:
                            pass
                stats['scanned_today'] = today_scans
        except Exception as e:
            logger.error(f"Error updating stats: {e}")

def add_recent_scan(scan_data):
    """Add scan to recent scans list"""
    global recent_scans
    scan_data['timestamp'] = datetime.datetime.now().isoformat()
    recent_scans.insert(0, scan_data)
    if len(recent_scans) > MAX_RECENT_SCANS:
        recent_scans.pop()

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
        
        # Enhanced authentication with better security
        if username == 'admin' and password == 'admin':
            session['logged_in'] = True
            session['is_admin'] = True
            session['username'] = username
            session['login_time'] = datetime.datetime.now().isoformat()
            logger.info(f"Admin login: {username}")
            return redirect(url_for('admin'))
        elif username == 'scanner' and password == 'scanner':
            session['logged_in'] = True
            session['is_admin'] = False
            session['username'] = username
            session['login_time'] = datetime.datetime.now().isoformat()
            logger.info(f"Scanner login: {username}")
            return redirect(url_for('scanner'))
        else:
            flash('Invalid credentials')
            logger.warning(f"Failed login attempt: {username}")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    username = session.get('username', 'unknown')
    logger.info(f"Logout: {username}")
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin')
def admin():
    if not session.get('logged_in') or not session.get('is_admin'):
        return redirect(url_for('login'))
    
    global stats, CSV_PATH
    update_stats()
    
    # Get system info
    system_info = {
        'server_time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'uptime': 'Running',
        'file_uploaded': CSV_PATH is not None and os.path.exists(CSV_PATH)
    }
    
    return render_template('admin.html', stats=stats, excel_path=CSV_PATH, system_info=system_info)

@app.route('/scanner')
def scanner():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    # Update scanner status
    stats['scanner_status'] = 'online'
    socketio.emit('scanner_status_update', {'status': 'online'})
    
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
    
    if file and (file.filename.endswith('.csv') or file.filename.endswith('.xlsx')):
        try:
            # Secure filename
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, 'tickets.csv')
            file.save(filepath)
            
            global CSV_PATH
            CSV_PATH = filepath
            
            # Validate the uploaded file
            data = read_csv_data()
            if not data:
                return jsonify({
                    'success': False, 
                    'message': 'Invalid file format or empty file'
                })
            
            required_columns = ['name', 'email']
            missing_columns = [col for col in required_columns if col not in data[0].keys()]
            
            if missing_columns:
                return jsonify({
                    'success': False, 
                    'message': f'Missing required columns: {", ".join(missing_columns)}'
                })
            
            # Update stats
            update_stats()
            
            logger.info(f"CSV file uploaded successfully: {len(data)} records")
            return jsonify({
                'success': True, 
                'message': f'File uploaded successfully - {len(data)} participants loaded'
            })
        
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return jsonify({'success': False, 'message': f'Error processing file: {str(e)}'})
    
    return jsonify({'success': False, 'message': 'Invalid file format. Please upload .csv or .xlsx file'})

@app.route('/verify', methods=['POST'])
def verify():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    global CSV_PATH, stats
    
    if not CSV_PATH or not os.path.exists(CSV_PATH):
        return jsonify({'success': False, 'message': 'No CSV file uploaded'})
    
    ticket_id = request.json.get('ticket_id')
    
    if not ticket_id:
        return jsonify({'success': False, 'message': 'No ticket ID provided'})
    
    try:
        data = read_csv_data()
        
        if not data:
            return jsonify({'success': False, 'message': 'No data found in CSV'})
        
        # Find ticket by UUID
        ticket_row = None
        for row in data:
            if row.get('uuid') == ticket_id:
                ticket_row = row
                break
        
        stats['scanned'] += 1
        stats['last_scan_time'] = datetime.datetime.now().isoformat()
        
        if ticket_row:
            if ticket_row.get('scanned') == 'True':
                scan_data = {
                    'ticket_id': ticket_id,
                    'name': ticket_row.get('name', 'N/A'),
                    'email': ticket_row.get('email', 'N/A'),
                    'status': 'already_scanned',
                    'scan_time': ticket_row.get('scan_time', 'N/A')
                }
                add_recent_scan(scan_data)
                socketio.emit('stats_update', stats)
                
                return jsonify({
                    'success': True,
                    'valid': False,
                    'message': 'Ticket already scanned',
                    'data': scan_data
                })
            
            # Mark as scanned
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ticket_row['scanned'] = 'True'
            ticket_row['scan_time'] = current_time
            
            # Update CSV file
            write_csv_data(data)
            
            stats['valid'] += 1
            update_stats()
            
            scan_data = {
                'ticket_id': ticket_id,
                'name': ticket_row.get('name', 'N/A'),
                'email': ticket_row.get('email', 'N/A'),
                'status': 'valid',
                'scan_time': current_time
            }
            add_recent_scan(scan_data)
            socketio.emit('stats_update', stats)
            socketio.emit('new_scan', scan_data)
            
            logger.info(f"Valid ticket scanned: {ticket_id} - {scan_data['name']}")
            
            return jsonify({
                'success': True,
                'valid': True,
                'message': 'Ticket valid',
                'data': scan_data
            })
        else:
            stats['invalid'] += 1
            socketio.emit('stats_update', stats)
            
            scan_data = {
                'ticket_id': ticket_id,
                'name': 'N/A',
                'email': 'N/A',
                'status': 'invalid',
                'scan_time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            add_recent_scan(scan_data)
            
            logger.warning(f"Invalid ticket attempted: {ticket_id}")
            
            return jsonify({
                'success': True,
                'valid': False,
                'message': 'Invalid ticket',
                'data': scan_data
            })
    
    except Exception as e:
        logger.error(f"Error verifying ticket {ticket_id}: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/generate_tickets', methods=['POST'])
def generate_tickets():
    if not session.get('logged_in') or not session.get('is_admin'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    global CSV_PATH
    
    if not CSV_PATH:
        return jsonify({'success': False, 'message': 'No CSV file uploaded'})
    
    try:
        data = read_csv_data()
        
        if not data:
            return jsonify({'success': False, 'message': 'No data found in CSV'})
        
        # Generate UUIDs if not present
        for row in data:
            if 'uuid' not in row or not row['uuid']:
                row['uuid'] = str(uuid.uuid4())
            if 'scanned' not in row:
                row['scanned'] = 'False'
            if 'scan_time' not in row:
                row['scan_time'] = ''
        
        # Generate QR codes
        qr_codes = []
        
        for row in data:
            ticket_id = row['uuid']
            img = qrcode.make(ticket_id)
            buffered = BytesIO()
            img.save(buffered, format='PNG')
            img_str = base64.b64encode(buffered.getvalue()).decode()
            qr_codes.append({
                'ticket_id': ticket_id,
                'qr_code': img_str,
                'name': row.get('name', 'Unknown'),
                'email': row.get('email', 'N/A')
            })
        
        # Write updated data back to CSV
        write_csv_data(data)
        update_stats()
        
        logger.info(f"Generated {len(qr_codes)} tickets")
        
        return jsonify({
            'success': True, 
            'message': f'{len(qr_codes)} tickets generated successfully', 
            'qr_codes': qr_codes
        })
    
    except Exception as e:
        logger.error(f"Error generating tickets: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/get_stats')
def get_stats():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    global stats
    update_stats()
    
    return jsonify({'success': True, 'stats': stats})

@app.route('/get_recent_scans')
def get_recent_scans():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    return jsonify({'success': True, 'scans': recent_scans[:20]})

@app.route('/export_data')
def export_data():
    if not session.get('logged_in') or not session.get('is_admin'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    global CSV_PATH
    
    if not CSV_PATH or not os.path.exists(CSV_PATH):
        return jsonify({'success': False, 'message': 'No data to export'})
    
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        export_path = os.path.join(UPLOAD_FOLDER, f'export_{timestamp}.csv')
        
        # Copy the current CSV file
        import shutil
        shutil.copy2(CSV_PATH, export_path)
        
        return jsonify({
            'success': True, 
            'message': 'Data exported successfully',
            'file_path': export_path
        })
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.datetime.now().isoformat(),
        'stats': stats
    })

if __name__ == '__main__':
    # Enhanced configuration for production use
    print("🚀 Starting Ticket Manager Server...")
    print("📱 Access the scanner from any device on the network using:")
    print("   http://[YOUR_IP_ADDRESS]:5000")
    print("")
    print("🔐 Login Credentials:")
    print("   Admin: username=admin, password=admin")
    print("   Scanner: username=scanner, password=scanner")
    print("")
    print("📊 Admin Dashboard: http://[YOUR_IP_ADDRESS]:5000/admin")
    print("📱 Scanner Interface: http://[YOUR_IP_ADDRESS]:5000/scanner")
    print("")
    
    # Run with enhanced configuration
    socketio.run(
        app, 
        host='0.0.0.0',  # Allow external connections
        port=5000, 
        debug=False,  # Disable debug for production
        allow_unsafe_werkzeug=True  # Allow external access
    )
