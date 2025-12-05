import gspread
import json
import pandas as pd
import traceback
from gspread.exceptions import SpreadsheetNotFound

# --- Configuration ---
JSON_FILE_PATH = 'output.json'

# Spreadsheet ID of your target Google Sheet (the long string between /d/ and /edit in the URL)
SPREADSHEET_ID = '1CoKQb_ZzukyQvoWdWF4zPH5kFfzqyD3HLwi5gH_8fac'

# Name of the tab/worksheet to create/use inside that spreadsheet
WORKSHEET_TITLE = 'Sheet2'
# ---------------------

def get_sheet_data():
    """Reads the JSON file and prepares the data structure for upload."""
    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"Error: {JSON_FILE_PATH} not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in {JSON_FILE_PATH}.")
        return None

def process_data(data):
    """Flattens the nested JSON structure for Google Sheet compatibility."""
    processed_records = []
    
    for item in data:
        # Core fields – map from your JSON schema
        # {
        #   "subject": "JEE Advanced 2023 Paper - 1",
        #   "question_no": 1,
        #   "question_type": "MCQ",
        #   "question": "<p>...</p>",
        #   "options": { "A": "...", "B": "...", "C": "...", "D": "..." },
        #   "correct_answer": "D",
        #   "solution": "<p>...</p>"
        # }
        record = {
            'Subject': item.get('subject'),
            'Question_No': item.get('question_no'),
            'Question_Type': item.get('question_type'),
            'Question_HTML': item.get('question'),
            'Correct_Answer': item.get('correct_answer'),
        }
        
        # Process Options (up to 4 options)
        options = item.get('options', {})

        # Case 1: options is a dict like {"A": "text", "B": "text", ...}
        if isinstance(options, dict):
            for key in ['A', 'B', 'C', 'D']:
                text = options.get(key, '')
                record[f'Option_{key}_Text'] = text

        # Case 2: options is a list of objects with index/text/is_correct (older format)
        elif isinstance(options, list):
            for i, option in enumerate(options[:4]):
                idx = option.get("index", chr(65 + i))
                record[f'Option_{idx}_Text'] = option.get('text', '')
        
        # Process Solution – prefer "solution" from your new JSON, fallback to "solution_text"
        solution_value = item.get('solution', item.get('solution_text', ''))
        if isinstance(solution_value, list):
            # Join list of lines into a single string
            record['Solution_HTML'] = '\n'.join(str(s) for s in solution_value)
        else:
            record['Solution_HTML'] = str(solution_value)
        
        processed_records.append(record)
        
    return processed_records

def upload_to_google_sheets(processed_data):
    """Authenticates and uploads the processed data to Google Sheets."""
    try:
        # Authenticate using the service account file
        gc = gspread.service_account(filename='credentials.json')

        # Open the spreadsheet by ID
        try:
            spreadsheet = gc.open_by_key(SPREADSHEET_ID)
            print(f"Successfully opened spreadsheet with ID: {SPREADSHEET_ID}")
        except SpreadsheetNotFound:
            print(f"Error: Spreadsheet with ID '{SPREADSHEET_ID}' not found or not shared with this service account.")
            return
            
        # Select or create the worksheet
        try:
            worksheet = spreadsheet.worksheet(WORKSHEET_TITLE)
        except gspread.WorksheetNotFound:
            # Delete default 'Sheet1' if it exists and is empty, then create new one
            default_sheet = spreadsheet.worksheet('Sheet1')
            if default_sheet.row_count == 1 and default_sheet.col_count == 26: # Typical empty sheet size
                spreadsheet.del_worksheet(default_sheet)
            worksheet = spreadsheet.add_worksheet(title=WORKSHEET_TITLE, rows="1000", cols="50")
            print(f"Created new worksheet: {WORKSHEET_TITLE}")


        # Convert list of dicts to pandas DataFrame for easy processing
        df = pd.DataFrame(processed_data)

        # Replace NaN/None with empty strings so the payload is valid JSON
        df = df.fillna("")

        # Get the headers and data rows
        headers = df.columns.tolist()
        values = df.values.tolist()
        
        # Clear existing content (optional, but good practice for fresh upload)
        worksheet.clear()
        
        # Upload headers and data
        all_data = [headers] + values
        # Use named arguments to avoid deprecation warning and keep API clear
        worksheet.update(range_name='A1', values=all_data)
        
        # Format (optional)
        worksheet.resize(rows=len(all_data), cols=len(headers))
        
        print(f"\n✅ Data successfully uploaded to: {spreadsheet.url}")
        print(f"Total {len(processed_data)} records uploaded.")

    except Exception as e:
        print(f"\n❌ An error occurred during Google Sheets interaction: {e}")
        # Print full traceback for easier debugging
        traceback.print_exc()

if __name__ == '__main__':
    raw_data = get_sheet_data()
    if raw_data:
        processed_data = process_data(raw_data)
        if processed_data:
            upload_to_google_sheets(processed_data)