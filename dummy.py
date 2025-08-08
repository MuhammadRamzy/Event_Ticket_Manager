import pandas as pd
import uuid

# Create dummy data for ticket verification system
data = {
    'name': [
        'John Smith',
        'Emma Johnson',
        'Michael Davis',
        'Sarah Wilson',
        'Robert Brown',
        'Jennifer Taylor',
        'David Martinez',
        'Amanda Thomas',
        'James Anderson',
        'Elizabeth Jackson',
        'Daniel White',
        'Michelle Harris',
        'Christopher Lee',
        'Laura Clark',
        'Matthew Lewis'
    ],
    'email': [
        'john.smith@example.com',
        'emma.johnson@example.com',
        'michael.davis@example.com',
        'sarah.wilson@example.com',
        'robert.brown@example.com',
        'jennifer.taylor@example.com',
        'david.martinez@example.com',
        'amanda.thomas@example.com',
        'james.anderson@example.com',
        'elizabeth.jackson@example.com',
        'daniel.white@example.com',
        'michelle.harris@example.com',
        'christopher.lee@example.com',
        'laura.clark@example.com',
        'matthew.lewis@example.com'
    ],
    'ticket_type': [
        'VIP',
        'Standard',
        'Standard',
        'VIP',
        'Standard',
        'Standard',
        'Standard',
        'VIP',
        'Standard',
        'Standard',
        'VIP',
        'Standard',
        'Standard',
        'Standard',
        'VIP'
    ],
    'registration_date': [
        '2025-01-15',
        '2025-01-16',
        '2025-01-16',
        '2025-01-17',
        '2025-01-18',
        '2025-01-19',
        '2025-01-20',
        '2025-01-21',
        '2025-01-22',
        '2025-01-23',
        '2025-01-24',
        '2025-01-25',
        '2025-01-26',
        '2025-01-27',
        '2025-01-28'
    ],
    'payment_status': [
        'Paid',
        'Paid',
        'Paid',
        'Paid',
        'Pending',
        'Paid',
        'Paid',
        'Paid',
        'Paid',
        'Pending',
        'Paid',
        'Paid',
        'Paid',
        'Pending',
        'Paid'
    ],
    'uuid': [str(uuid.uuid4()) for _ in range(15)],
    'scanned': [False] * 15,
    'scan_time': [None] * 15
}

# Create DataFrame
df = pd.DataFrame(data)

# Save to Excel
df.to_excel('dummy_tickets.xlsx', index=False)

# Save to CSV
df.to_csv('dummy_tickets.csv', index=False)

print("Dummy data files created: dummy_tickets.xlsx and dummy_tickets.csv")