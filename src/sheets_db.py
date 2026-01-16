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

        self.userWs = self.sh.worksheet('Users')
        self.transWs = self.sh.worksheet('Transactions')
        self.balWs = self.sh.worksheet('Balances')


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

    def add_new_user(self, user_id, username):
        """Appends a new row to Users DB"""
        users_worksheet = self.userWs
        bals_worksheet = self.balWs
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Data to append 
        new_row = [user_id, username, date] 
        if user_id in [user['User_ID'] for user in users_worksheet.get_all_records()]:
            return False
        else:
            users_worksheet.append_row(new_row)
            bal_row = [user_id, 0.0, date, "", "", ""]
            bals_worksheet.append_row(bal_row)
            return True
    
    def add_transaction(self, user_id, trans_type, amount, category, description):
        """Adds a transaction to the Transactions sheet."""
        transaction_id = generate_uuid_transaction()
        worksheet = self.transWs
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_row = [transaction_id,
                    str(user_id),
                    date,
                    trans_type,
                    category,
                    description,
                    amount]
        worksheet.append_row(new_row)

        self.update_balance(user_id,transaction_id)
        return True

    def update_balance(self, user_id, transaction_id = ""):
        """Updates the balance for a user in the Balances sheet."""
        worksheet = self.balWs
        records = worksheet.get_all_records()
        for idx, record in enumerate(records, start=2):  # start=2 to account for header row
            if record['User_ID'] == user_id:
                latest_balance = record.get('Latest_1 Transaction_ID', "")
                latest_balance_2 = record.get('Latest_2 Transaction_ID',"")

                balance = self.calculate_balance(user_id)
                worksheet.update_cell(idx, 2, balance)
                if transaction_id == "":
                    break
                worksheet.update_cell(idx, 5, latest_balance_2)
                worksheet.update_cell(idx, 4, latest_balance)
                worksheet.update_cell(idx, 3, transaction_id) 
                break
    
    def calculate_balance(self, user_id):
        """Calculates the current balance for a user."""
        worksheet = self.transWs
        records = worksheet.get_all_records()
        balance = 0
        for record in records:
            if record['User_ID'] == user_id:
                type = record['Type']
                if type == 'income':
                    balance += float(record.get('Amount',0))
                elif type == 'expense':
                    balance -= float(record.get('Amount',0))
        return balance
    
    def get_balance(self, user_id):
        """Fetches the current balance for a user."""
        worksheet = self.balWs
        records = worksheet.get_all_records()
        self.update_balance(user_id)
        for record in records:
            if record['User_ID'] == user_id:
                return record['Balance']
        return 0.0

    def get_monthly_stats(self, user_id, month):
        worksheet = self.transWs
        records = worksheet.get_all_records()
        records_filtered = [rec for rec in records if rec.get('User_ID') == user_id and str(rec.get('Date')).startswith(str(month))]
        income = sum(float(rec.get('Amount',0)) for rec in records_filtered if rec.get('Type') == 'income')
        expense = sum(float(rec.get('Amount',0)) for rec in records_filtered if rec.get('Type') == 'expense')
        
        results = {'income': income, 'expense': expense}
        return results

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