import gspread
from .config import GSPREAD_SHEET_CREDENTIALS, SHEET_ID
import uuid
from datetime import datetime

# db.add_transaction_to_sheet(user_id, trans_type, amount, category, date)
# db.calculate_balance(user_id)
# db.get_monthly_stats(user_id, month)
def generate_uuid_transaction():
    short_uuid = str(uuid.uuid4()).split('-')[0]
    
    return f"TRX-{short_uuid.upper()}"

class SheetsDatabase:
    """Handles all interactions with the Google Sheet."""
    def __init__(self):
        # 1. Authenticate using the downloaded JSON key file
        self.gc = gspread.service_account(filename=(GSPREAD_SHEET_CREDENTIALS))
        
        # 2. Open the spreadsheet using its unique ID
        self.spreadsheet_id = SHEET_ID
        self.sh = self.gc.open_by_key(self.spreadsheet_id)
    
    def _get_worksheet(self, worksheet_name):
        try:
            return self.sh.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            print(f"Error: Worksheet '{worksheet_name}' not found.")
            return None

    def get_all_data(self, worksheet_name='Sheet1'):
        """Retrieves all data from a specified worksheet as a list of dictionaries."""
        try:
            worksheet = self.sh.worksheet(worksheet_name)
            # get_all_records() returns a list of dictionaries (keys are column headers)
            data = worksheet.get_all_records()
            return data
        except gspread.WorksheetNotFound:
            print(f"Error: Worksheet '{worksheet_name}' not found.")
            return []
        except Exception as e:
            print(f"An error occurred while fetching data: {e}")
            return []

    def add_new_user(self, user_id, username, date):
        """Appends a new row to the worksheet."""
        worksheet = self.sh.worksheet('Users')
        # Data to append (must be a list matching the column order)
        new_row = [user_id, username, date] 
        if user_id in [user['User_ID'] for user in worksheet.get_all_records()]:
            return False
        else:
            worksheet.append_row(new_row)
            return True
    
    def add_transaction(self, user_id, trans_type, amount, category, description):
        """Adds a transaction to the Transactions sheet."""
        transaction_id = generate_uuid_transaction()
        worksheet = self._get_worksheet('Transactions')
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_row = [transaction_id,
                    str(user_id),
                    date,
                    trans_type,
                    category,
                    description,
                    amount]
        worksheet.append_row(new_row)
        return True

    def calculate_balance(self, user_id):
        """Calculates the current balance for a user."""
        worksheet = self.sh.worksheet('Transactions')
        records = worksheet.get_all_records()
        balance = 0
        for record in records:
            if record['user_id'] == user_id:
                if record['type'] == 'income':
                    balance += float(record['amount'])
                elif record['type'] == 'expense':
                    balance -= float(record['amount'])
        return balance

    def get_monthly_stats(self, user_id, month):
        """Fetches monthly statistics for a user."""
        # Implementation goes here
        pass

    def get_monthly_breakdown(self, user_id, month):
        """Fetches monthly breakdown by category for a user."""
        # Implementation goes here
        pass

    def get_yearly_stats(self, user_id, year):
        """Fetches yearly statistics for a user."""
        # Implementation goes here
        pass

    def get_yearly_breakdown(self, user_id, year):
        """Fetches yearly breakdown by category for a user."""
        # Implementation goes here
        pass

    def get_balance_per_month(self, user_id, year):
        pass