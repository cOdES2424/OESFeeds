import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

# Step 1: Open the login page and get the login form
login_url = 'https://apps.occ.ok.gov/PSTPortal/Account/Login'
session = requests.Session()
login_page = session.get(login_url)
print('Login page fetched')
soup = BeautifulSoup(login_page.content, 'html.parser')

# Step 2: Fill in the login form with correct field locators
login_data = {
    'UserName': 'bolzmi@hotmail.com',
    'Password': 'redfred4'
}

# Find the hidden input fields and add them to login_data
hidden_inputs = soup.find_all('input', type='hidden')
for hidden_input in hidden_inputs:
    login_data[hidden_input['name']] = hidden_input['value']

# Step 3: Submit the login form
session.post(login_url, data=login_data)
print('Logged in successfully')

# Step 4: Navigate to the target page with search parameters
date_14_days_ago = (datetime.now() - timedelta(days=14)).strftime('%m/%d/%Y')
target_url = f'https://apps.occ.ok.gov/PSTPortal/PublicImaging/Home?indexName=DateRange&DateRangeFrom={date_14_days_ago}&DateRangeTo={date_14_days_ago}&btnSubmitDateSearch=Search+by+Date+Range&pageNumber=0'
response = session.get(target_url)
print('Navigated to target page')
soup = BeautifulSoup(response.content, 'html.parser')

# Step 5: Confirm table presence and print first few rows for verification
table = soup.find('table', {'id': 'tablePublicImagingSearchResults'})
print(f'Table found: {table is not None}')

if table:
    tbody = table.find('tbody')
    rows = tbody.find_all('tr') if tbody else []
    for row in rows[:3]:  # Print first 3 rows
        columns = row.find_all('td')
        print(f'Row columns: {[col.text.strip() for col in columns]}')

    results = []
    for row in rows:
        columns = row.find_all('td')
        if columns and len(columns) > 3:
            description = columns[2].text.strip()
            print(f'Description: {description}')  # Debug column content
            if any(keyword in description for keyword in ['NOV', 'NOCR', 'SOR']):
                entry = {
                    'id': columns[1].text.strip(),
                    'description': description,
                    'date': columns[3].text.strip()
                }
                results.append(entry)

print(f'Initial data scraped: {results}')
