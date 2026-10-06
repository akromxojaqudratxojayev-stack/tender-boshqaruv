import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import re
from playwright.sync_api import sync_playwright

def format_money(val):
    try:
        return f"{float(val):,.0f} UZS".replace(',', ' ')
    except:
        return f"{val} UZS"

def parse_tender(url: str):
    url = url.replace("/provider/bid/new/", "/lot/")
    source_site = "noma'lum"
    if "xt-xarid.uz" in url:
        source_site = "xt-xarid.uz"
    elif "tender.mc.uz" in url:
        source_site = "tender.mc.uz"
    elif "etender.uzex.uz" in url:
        source_site = "etender.uzex.uz"
    elif "xarid.uzex.uz" in url:
        source_site = "xarid.uzex.uz"
    elif "uzex.uz" in url:
        source_site = "uzex.uz"
        
    delivery_term = "Noma'lum"
    
    # 1) ETENDER.UZEX.UZ API
    if "etender.uzex.uz/lot/" in url or "etender.uzex.uz/civil-detail/" in url:
        match = re.search(r'/(?:lot|civil-detail)/(\d+)', url)
        if not match:
            raise Exception("Tender ID topilmadi")
        tender_id = match.group(1)
        api_url = f"https://apietender.uzex.uz/api/common/GetTrade/{tender_id}/0"
        
        with httpx.Client(verify=False, timeout=15.0) as client:
            resp = client.get(api_url)
            if resp.status_code != 200:
                raise Exception(f"Sayt API ishlamadi (xato {resp.status_code})")
            data = resp.json()
            
        title = data.get('addon_description') or data.get('name') or "Noma'lum"
        company = data.get('customer_name') or "Noma'lum"
        
        start_cost = data.get('start_cost', 0)
        total_sum = format_money(start_cost)
        
        pledge_val = data.get('pledge_value', 0)
        if pledge_val and start_cost:
            deposit_amount = (start_cost * pledge_val) / 100
            deposit_sum = f"{pledge_val}% — {format_money(deposit_amount)}"
        else:
            deposit_sum = "0 UZS"
        
        start_date = datetime.now()
        deadline = datetime.now() + timedelta(days=5)
        if data.get('start_date'):
            start_date = datetime.strptime(data.get('start_date')[:16], "%Y-%m-%dT%H:%M")
        if data.get('end_date'):
            deadline = datetime.strptime(data.get('end_date')[:16], "%Y-%m-%dT%H:%M")
            
        items_str = ""
        delivery_term = "Noma'lum"
        try:
            budget_products = json.loads(data.get('budget_products') or '[]')
            
            if budget_products and isinstance(budget_products, list):
                days = budget_products[0].get('Delivery_Term')
                if days:
                    delivery_term = f"{days} Kun"
            
            extracted_items = []
            for i, p in enumerate(budget_products, 1):
                p_name = p.get('Product_Name', '')
                qty = p.get('Quantity', '')
                unit_price = format_money(p.get('Price', 0))
                total_price = format_money(p.get('Cost', 0))
                desc = p.get('Description', '')
                
                item_text = f"🔹 <b>{i} - {p_name}</b>\n📦 Miqdori: {qty}\n💵 1 dona narxi: {unit_price}\n💰 Jami: {total_price}"
                if desc:
                    item_text += f"\n📝 Batafsil: {desc}"
                extracted_items.append(item_text)
                
            if extracted_items:
                items_str = "\n\n🛒 <b>Tovarlar:</b>\n\n" + "\n\n".join(extracted_items)
        except Exception as e:
            print("Products parse xato:", e)
            
        return {
            "link": url,
            "title": title,
            "company_name": company,
            "total_sum": total_sum,
            "deposit_sum": deposit_sum,
            "delivery_term": delivery_term,
            "start_date": start_date,
            "deadline": deadline,
            "source_site": source_site,
            "items_str": items_str
        }

    # 2) PLAYWRIGHT FOR OTHER SITES
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                timeout=30000,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu'
                ]
            )
            context = browser.new_context(locale="uz-UZ")
            page = context.new_page()
            
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            if "xt-xarid.uz" in url:
                page.wait_for_timeout(5000)
                
            page_html = page.content()
            
            # --- START OLD PARSING CODE ---
            soup = BeautifulSoup(page_html, 'html.parser')
            page_text = soup.get_text(separator="\n").strip()
            page_text = re.sub(r'\n+', '\n', page_text)
            
            title = "Noma'lum tender"
            company = "Noma'lum tashkilot"
            total_sum = "Noma'lum"
            deposit_sum = "0 UZS"
            delivery_term = "Noma'lum"
            start_date = datetime.now()
            deadline = datetime.now() + timedelta(days=5)
            items_str = ""
            
            if "xt-xarid.uz" in url:
                sum_matches = re.findall(r"Kutilayotgan narx:\s+([\d\s\.,]+(?:UZS)?)", page_text)
                if sum_matches:
                    total_sum = sum_matches[0].strip()
                    
                title_matches = re.findall(r"(?:Xarid jurnali raqami|Loyiha nomi):\s+(.+)", page_text)
                if title_matches:
                    title = title_matches[0].strip()
                    
                company = "Buyurtmachi (xt-xarid)"
                
            else:
                sum_matches = re.findall(r"(?:Jami boshlang.*?narx|Jami summa|Boshlang.*?ich narx)[^\d]*([\d\s,\.]+UZS)", page_text, re.IGNORECASE)
                if sum_matches:
                    total_sum = sum_matches[0].strip()
                    
                org_matches = re.findall(r"Buyurtmachi nomi:\n+(.+?)\n", page_text, re.IGNORECASE)
                if org_matches:
                    company = org_matches[0].strip()
                    
                lot_name_matches = re.findall(r"(?:Lot nomi|Qo.*?shimcha ma.*?lumotlar|Texnik tavsif):\n+(.+?)\n", page_text, re.IGNORECASE)
                if lot_name_matches:
                    title = lot_name_matches[0].strip()
                    if title == "-":
                        if len(lot_name_matches) > 1: title = lot_name_matches[1].strip()
                    
                zakalat_matches = re.findall(r"Zakalat(?: summasi| miqdori):\n+(.+?)\n", page_text, re.IGNORECASE)
                if zakalat_matches:
                    deposit_sum = zakalat_matches[0].strip()
                else:
                    zakalat_matches = re.findall(r"Zakalat:\n+(.+?)\n", page_text, re.IGNORECASE)
                    if zakalat_matches: deposit_sum = zakalat_matches[0].strip()
                    
                if "%" in deposit_sum and "UZS" in total_sum:
                    try:
                        percent_match = re.search(r"(\d+(?:\.\d+)?)%", deposit_sum)
                        if percent_match:
                            percent = float(percent_match.group(1))
                            clean_sum = re.sub(r"[^\d\.]", "", total_sum)
                            if clean_sum:
                                numeric_sum = float(clean_sum)
                                calculated_deposit = (numeric_sum * percent) / 100
                                formatted_deposit = f"{calculated_deposit:,.0f} UZS".replace(',', ' ')
                                deposit_sum = f"{deposit_sum} ≈ {formatted_deposit}"
                    except: pass
                    
                try:
                    start_matches = re.findall(r"Boshlanish sanasi:\n+(\d{2}-\d{2}-\d{4} \d{2}:\d{2})", page_text)
                    if start_matches:
                        start_date = datetime.strptime(start_matches[0], "%d-%m-%Y %H:%M")
                        
                    end_matches = re.findall(r"Tugash sanasi:\n+(\d{2}-\d{2}-\d{4} \d{2}:\d{2})", page_text)
                    if end_matches:
                        deadline = datetime.strptime(end_matches[0], "%d-%m-%Y %H:%M")
                    
                    if not end_matches:
                        alt_end = re.findall(r"Ochilish sanasi:\n+([A-Za-z]+ \d{1,2}, \d{4})", page_text)
                        if alt_end:
                            deadline = datetime.strptime(alt_end[0], "%b %d, %Y")
                except: pass
                
                delivery_matches = re.findall(r"Yetkazib berish muddati\s*(\d+\s*Kun)", page_text, re.IGNORECASE)
                if not delivery_matches:
                    delivery_matches = re.findall(r"(\d+\s*Kun)", page_text, re.IGNORECASE)
                if delivery_matches:
                    delivery_term = delivery_matches[0].strip()
            
            if "xarid.uzex.uz" in url:
                js_extract = '''() => {
                    let res = [];
                    document.querySelectorAll('.lot__products__item').forEach((item, index) => {
                        let nameEl = item.querySelector('h5');
                        if (nameEl) {
                            let name = nameEl.innerText.replace(/^[0-9]+\s*/, '').trim();
                            let trs = item.querySelectorAll('tbody tr');
                            if (trs.length > 0) {
                                let tds = trs[0].querySelectorAll('td');
                                if (tds.length >= 2) {
                                    let qty = tds[0].innerText.trim();
                                    let unit = tds[1].innerText.trim();
                                    res.push((index + 1) + '. ' + name + ' — ' + qty + ' ' + unit);
                                }
                            }
                        }
                    });
                    return res;
                }'''
                extracted_items = page.evaluate(js_extract)
                if extracted_items:
                    items_str = "\n\n🛒 <b>Tovarlar:</b>\n" + "\n".join(extracted_items)
            
            browser.close()
            
            return {
                "link": url,
                "title": title,
                "company_name": company,
                "total_sum": total_sum,
                "deposit_sum": deposit_sum,
                "delivery_term": delivery_term,
                "start_date": start_date,
                "deadline": deadline,
                "source_site": source_site,
                "items_str": items_str
            }
            
    except Exception as e:
        print("Playwright bilan xatolik:", e)
        raise Exception(f"Ma'lumotlarni o'qib bo'lmadi. Xato: {str(e)[:100]}")
