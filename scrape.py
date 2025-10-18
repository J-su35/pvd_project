import os, asyncio, json, sys, traceback
import requests
import gspread
from datetime import datetime
from playwright.async_api import async_playwright
from google.oauth2.service_account import Credentials

LOGIN_URL = os.getenv("LOGIN_URL")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

SHEET_KEY = os.getenv("SHEET_KEY")        # Google Sheet ID (optional)
GCP_SA_JSON = os.getenv("GCP_SA_JSON")    # service account json string (optional)

# optional: LINE Notify token
# LINE_NOTIFY_TOKEN = os.getenv("LINE_NOTIFY_TOKEN")  

# helper: notify via LINE
# def line_notify(msg: str):
#     if not LINE_NOTIFY_TOKEN:
#         return
#     try:
#         requests.post(
#             "https://notify-api.line.me/api/notify",
#             headers={"Authorization": "Bearer " + LINE_NOTIFY_TOKEN},
#             data={"message": msg},
#             timeout=10
#         )
#     except Exception:
#         pass

async def accept_risk_popup_if_any(page):
    try:
        btn = page.get_by_role("button", name="ยอมรับ")
        await btn.wait_for(timeout=3000)
        await btn.click()
        await page.wait_for_load_state("networkidle")
        return
    except PWTimeout:
        pass

async def login_if_needed(page):
    """
    หน้านี้รองรับ 2 ทาง:
    - ถ้าเว็บจำบัญชีไว้แล้ว: มีปุ่ม 'เข้าสู่ระบบ' ให้กดได้ทันที
    - ถ้าไม่จำ: ต้องกรอก USERNAME/PASSWORD แล้วกดเข้าสู่ระบบ
    """
    # เคส 1: กด 'เข้าสู่ระบบ' ได้เลย
    try:
        # ปุ่มอาจเป็น <a> หรือ <button> ชื่อ 'เข้าสู่ระบบ'
        # ลองหาทั้ง role และข้อความ
        enter_btn = page.get_by_role("button", name="เข้าสู่ระบบการใช้งาน")
        await enter_btn.wait_for(timeout=2000)
        await enter_btn.click()
        await page.wait_for_load_state("networkidle")
        return
    except PWTimeout:
        # อาจจะเป็นลิงก์
        try:
            link_btn = page.get_by_role("link", name="เข้าสู่ระบบการใช้งาน")
            await link_btn.wait_for(timeout=1500)
            await link_btn.click()
            await page.wait_for_load_state("networkidle")
            return
        except PWTimeout:
            pass

    # เคส 2: ไม่มีปุ่มแบบ remember → กรอกฟอร์มล็อกอิน
    # NOTE: ปรับ selector ให้ตรงกับ DOM จริง (ใช้ Inspect element)
    await page.fill('input[name="username"]', USERNAME)
    await page.fill('input[name="password"]', PASSWORD)
    # ปุ่ม submit อาจเป็น id/class อื่น ลองแบบ generic ก่อน
    try:
        await page.click('button[type="submit"]')
    except:
        # กันไว้เผื่อปุ่มเป็น input[type=submit]
        await page.click('input[type="submit"]')

    await page.wait_for_load_state("networkidle")

async def extract_return_value(page):
    candidates = [
        "xpath=//p[contains(normalize-space(.),'อัตราผลตอบแทนรายบุคคล')]/following-sibling::h4[1]",
        "p.c-gray2:has-text('อัตราผลตอบแทนรายบุคคล') + h4",
        "div.border-card:has(p.c-gray2:has-text('อัตราผลตอบแทนรายบุคคล')) h4 >> nth=1",
        "xpath=//p[contains(.,'อัตราผลตอบแทน') and contains(.,'YTD')]/following-sibling::h4[1]",
    ]
    for sel in candidates:
        try:
            loc = page.locator(sel)
            await loc.first.wait_for(timeout=3000)
            txt = (await loc.first.text_content() or "").strip()
            if txt:
                return txt
        except PWTimeout:
            continue
    # ถ้ายังไม่เจอจริง ๆ ให้ screenshot ช่วยดีบัก
    await page.screenshot(path="debug_port.png", full_page=True)
    raise RuntimeError("ไม่พบตัวเลขผลตอบแทน: โปรดตรวจ selector บนหน้า port")

async def main():
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context()
            page = await context.new_page()

            # 1) เข้า Login
            await page.goto(LOGIN_URL, wait_until="networkidle")

            # 2) ถ้ามีป็อปอัปความเสี่ยง ให้กด 'ยอมรับ'
            await accept_risk_popup_if_any(page)

            # 3) จัดการล็อกอิน (จำรหัสแล้ว/หรือกรอกใหม่)
            await login_if_needed(page)

            # 4) ไปหน้า Port ตรง ๆ (กันกรณีอยู่หน้าหลักหลังล็อกอิน)
            await page.goto(PORT_URL, wait_until="networkidle")
            await page.wait_for_url("**/account/user/port*", timeout=15000)

            # 5) ดึงค่า 'ผลตอบแทน'
            ret_val = await extract_return_value(page)

            # 6) บันทึกลงไฟล์ log (หรือส่งต่อ Google Sheets ตามที่ทำไว้ก่อนหน้า)
            with open("PVD Rate of return.csv", "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat()},{ret_val}\n")

            await browser.close()

            # optional: LINE Notify
            # line_notify(f"Scrape success: {ret_val}")
            print("SUCCESS:", ret_val)

    except Exception as e:
        tb = traceback.format_exc()
        print("ERROR:", e, file=sys.stderr)
        print(tb, file=sys.stderr)
        # optional: LINE Notify
        # line_notify(f"Scrape ERROR: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
