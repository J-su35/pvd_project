import os, json
import gspread
from google.oauth2.service_account import Credentials

SHEET_KEY = os.getenv("SHEET_KEY")        
GCP_SA_JSON = os.getenv("GCP_SA_JSON") 

def append_to_sheet(values):
    sheet_key = SHEET_KEY
    sa_json = GCP_SA_JSON
    if not sheet_key or not sa_json:
        print("[SKIP] SHEET_KEY or GCP_SA_JSON is not set — skip writing sheet")
        raise RuntimeError(f"Missing env: {sheet_key} or {sa_json}")

    try:
        creds_info = json.loads(sa_json)  # ถ้าเก็บแบบ base64 ให้ decode ก่อน
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(creds_info, scopes=scopes)

        gc = gspread.authorize(creds)
        sh = gc.open_by_key(sheet_key)

        try:
            ws = sh.worksheet("2568")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title="returns", rows=1000, cols=10)

        ws.append_row(values, value_input_option="USER_ENTERED")
        print("[OK] Appended to Sheet:", values)
        return True

    except Exception as e:
        print("[ERROR] append_to_sheet:", e)
        return False