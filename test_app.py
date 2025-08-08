#!/usr/bin/env python3

import csv
import uuid
import datetime
import qrcode
from io import BytesIO
import base64

def test_csv_operations():
    """Test CSV reading and writing operations"""
    print("Testing CSV operations...")
    
    # Create test data
    test_data = [
        {'name': 'John Smith', 'email': 'john@example.com', 'uuid': str(uuid.uuid4())},
        {'name': 'Emma Johnson', 'email': 'emma@example.com', 'uuid': str(uuid.uuid4())},
        {'name': 'Michael Davis', 'email': 'michael@example.com', 'uuid': str(uuid.uuid4())}
    ]
    
    # Write test data to CSV
    with open('test_tickets.csv', 'w', newline='', encoding='utf-8') as file:
        fieldnames = ['name', 'email', 'uuid', 'scanned', 'scan_time']
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in test_data:
            row['scanned'] = 'False'
            row['scan_time'] = ''
            writer.writerow(row)
    
    print("✅ Test CSV file created successfully")
    
    # Read test data
    with open('test_tickets.csv', 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        data = list(reader)
    
    print(f"✅ Read {len(data)} records from CSV")
    
    # Test QR code generation
    print("Testing QR code generation...")
    for row in data:
        ticket_id = row['uuid']
        img = qrcode.make(ticket_id)
        buffered = BytesIO()
        img.save(buffered, format='PNG')
        img_str = base64.b64encode(buffered.getvalue()).decode()
        print(f"✅ Generated QR code for {row['name']} - {ticket_id[:8]}...")
    
    print("✅ All QR codes generated successfully")
    
    # Clean up
    import os
    if os.path.exists('test_tickets.csv'):
        os.remove('test_tickets.csv')
        print("✅ Test file cleaned up")
    
    return True

def test_dependencies():
    """Test if all required dependencies are available"""
    print("Testing dependencies...")
    
    try:
        import flask
        print("✅ Flask available")
    except ImportError:
        print("❌ Flask not available")
        return False
    
    try:
        import flask_socketio
        print("✅ Flask-SocketIO available")
    except ImportError:
        print("❌ Flask-SocketIO not available")
        return False
    
    try:
        import qrcode
        print("✅ QRCode available")
    except ImportError:
        print("❌ QRCode not available")
        return False
    
    try:
        import werkzeug
        print("✅ Werkzeug available")
    except ImportError:
        print("❌ Werkzeug not available")
        return False
    
    return True

if __name__ == "__main__":
    print("🧪 Testing Ticket Manager Application")
    print("=" * 50)
    
    # Test dependencies
    if not test_dependencies():
        print("❌ Dependency test failed")
        exit(1)
    
    print()
    
    # Test CSV operations
    if test_csv_operations():
        print()
        print("🎉 All tests passed! The application should work correctly.")
        print()
        print("To run the application:")
        print("1. python app_simple.py")
        print("2. Access from browser: http://localhost:5000")
        print("3. Access from mobile: http://[YOUR_IP]:5000")
    else:
        print("❌ CSV operations test failed")
        exit(1)
