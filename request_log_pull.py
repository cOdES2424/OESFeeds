
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import csv

# Function to scrape the additional page for request statuses
def scrape_request_statuses(session):
    request_statuses = []
    search_url = 'https://apps.occ.ok.gov/LicenseePortal/SearchWorkRequests.aspx'
    search_page = session.get(search_url)
    soup = BeautifulSoup(search_page.content, 'html.parser')
    
    table = soup.find('table', {'class': 'rptGridView'})  # Adjust the class as necessary
    if not table:
        raise ValueError("Table not found on the page")
    
    rows = table.find_all('tr')[1:]  # Skip the header row
    for row in rows:
        cells = row.find_all('td')
        if cells:
            request_number = cells[5].text.strip()
            status = cells[13].text.strip()  # Adjust index based on actual table structure
            submission_date = cells[7].text.strip()  # Adjust index based on actual table structure
            request_statuses.append({
                'request_number': request_number,
                'status': status,
                'submission_date': submission_date
            })
    
    return request_statuses

# Function to save request statuses to a log file
def save_request_statuses_to_log(request_statuses, log_file):
    with open(log_file, mode='a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=['request_number', 'status', 'submission_date'])
        if file.tell() == 0:
            writer.writeheader()
        for status in request_statuses:
            writer.writerow(status)

# Load login information from environment variables
login_data = {
    'UserName': os.getenv('USERNAME'),
    'Password': os.getenv('PASSWORD')
}

# Load the path to the CSV file from an environment variable
csv_file_path = os.getenv('CSV_FILE_PATH')

# Check if the environment variable is set
if not csv_file_path:
    print("CSV_FILE_PATH environment variable is not set")
    exit()

# Step 1: Open the login page and get the login form
login_url = 'https://apps.occ.ok.gov/PSTPortal/Account/Login'
session = requests.Session()
login_page = session.get(login_url)
soup = BeautifulSoup(login_page.content, 'html.parser')

# Find the hidden input fields and add them to login_data
hidden_inputs = soup.find_all('input', type='hidden')
for hidden_input in hidden_inputs:
    login_data[hidden_input['name']] = hidden_input['value']

# Step 3: Submit the login form
response = session.post(login_url, data=login_data)

# Verify login was successful
if response.url == login_url:
    raise ValueError("Login failed. Please check your credentials.")

# Step 4: Navigate to the intermediary page
intermediate_url = 'https://apps.occ.ok.gov/PSTPortal/CorrectiveAction/Forward?Length=16'
session.get(intermediate_url)

# Step 5: Navigate to the Search Work Requests page
search_work_requests_url = 'https://apps.occ.ok.gov/LicenseePortal/SearchWorkRequests.aspx'
search_work_requests_page = session.get(search_work_requests_url)

# Step 6: Scrape request statuses from the Search Work Requests page
request_statuses = scrape_request_statuses(session)

# Save request statuses to log file
log_file_path = 'request_log.csv'
save_request_statuses_to_log(request_statuses, log_file_path)

print("Request statuses logged successfully")
