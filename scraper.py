import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import re
from playwright.async_api import async_playwright

async def parse_tender(url: str):
    url = url.replace("/provider/bid/new/", "/lot/")
    source_site = "noma'lum"
    if "xt-xarid.uz" in url:
        source_site = "xt-xarid.uz"
    elif "tender.mc.uz" in url:
        source_site = "tender.mc.uz"
    elif "xarid.uzex.uz" in url:
        source_site = "xarid.uzex.uz"
    elif "uzex.uz" in url:
        source_site = "uzex.uz"
        
    delivery_term = "Noma'lum"
        
    try:
        civil_match = re.search(r'civil-detail/(\d+)', url)
        if civil_match:
            tender_id = civil_match.group(1)
            api_url = f"https://apietender.uzex.uz/api/CivilContracts/Get/{tender_id}"
            
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(api_url)
                if response.status_code == 200:
                    data = response.json()
                    
                    title = data.get('name', 'Noma\'lum lot nomi')
                    company = data.get('customer_name', 'Noma\'lum tashkilot')
                    
                    cost = data.get('cost', 0)
                    total_sum = f"{cost:,.0f} UZS".replace(',', ' ')
                    
                    pledge = data.get('pledge_sum', 0)
                    deposit_sum = f"{pledge:,.0f} UZS (Zakalat)".replace(',', ' ')
                    
                    start_str = data.get('start_date', '')
                    end_str = data.get('end_date', '')
                    
                    js_products = data.get('js_products', '[]')
                    items_list = []
                    try:
                        products = json.loads(js_products)
                        if isinstance(products, list) and len(products) > 0:
                            dl = products[0].get('Delivery_Term')
                            if dl: delivery_term = f"{dl} Kun"
                            for idx, p in enumerate(products):
                                p_name = p.get('Product_Name', 'Tovar')
                                p_qty = p.get('Quantity', 1)
                                p_unit = p.get('Measure_Name', 'sht')
                                items_list.append(f"{idx+1}. {p_name} — {p_qty} {p_unit}")
                    except: pass
                    
                    items_str = ""
                    if items_list:
                        items_str = "\n\n📦 <b>Tovarlar:</b>\n" + "\n".join(items_list)
                    
                    start_date = datetime.strptime(start_str.split('.')[0], "%Y-%m-%dT%H:%M:%S") if start_str else datetime.now()
                    deadline = datetime.strptime(end_str.split('.')[0], "%Y-%m-%dT%H:%M:%S") if end_str else (datetime.now() + timedelta(days=3))
                    
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
        print("API orqali o'qishda xatolik:", e)
        
    # Playwright orqali o'qish (ko'rinmas brauzer) barcha saytlar uchun
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--single-process',
                    '--disable-gpu'
                ]
            )
            context = await browser.new_context(locale="uz-UZ")
            page = await context.new_page()
            
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            if "xt-xarid.uz" in url:
                await page.wait_for_timeout(5000)
            
            try:
                await page.click("text=O'Z", timeout=2000)
                await page.wait_for_timeout(1000)
            except: pass
            
            try:
                await page.click("text=O'ZBEKCHA", timeout=2000)
                await page.wait_for_timeout(1000)
            except: pass
            
            page_text = await page.evaluate("document.body.innerText")
            page_html = await page.content()
            
            title = "Noma'lum lot"
            company = "Noma'lum tashkilot"
            total_sum = "0 UZS"
            deposit_sum = "0 UZS"
            delivery_term = "Noma'lum"
            
            start_date = datetime.now()
            deadline = datetime.now() + timedelta(days=3)
            
            # Xarid.uzex.uz uchun
            if "xarid.uzex.uz" in url:
                sum_matches = re.findall(r"Boshlang.*?ich summa\s*([\d\s\xa0]+)", page_text, re.IGNORECASE)
                if sum_matches:
                    total_sum = sum_matches[0].strip() + " UZS"
                
                cat_matches = re.findall(r"(?:Tovar kategoriyasi|Toifa):\s*(.+?)\n", page_text, re.IGNORECASE)
                if cat_matches:
                    title = cat_matches[0].strip()
                    
                del_matches = re.findall(r"muddati[^\d]*(\d+)", page_text, re.IGNORECASE)
                if del_matches:
                    delivery_term = f"{del_matches[0].strip()} Kun"
                    
                start_matches = re.findall(r"Boshlanish sanasi:\n+(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2})", page_text)
                if start_matches:
                    start_date = datetime.strptime(start_matches[0], "%d.%m.%Y %H:%M")
                    
                end_matches = re.findall(r"Tugash sanasi:\n+(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2})", page_text)
                if end_matches:
                    deadline = datetime.strptime(end_matches[0], "%d.%m.%Y %H:%M")
                    
                company = "Buyurtmachi yashiringan (xarid.uzex)"
                
            # xt-xarid.uz uchun
            elif "xt-xarid.uz" in url:
                title = "Xarid protsedurasi (xt-xarid)"
                
                # HTML dan input title orqali Lot nomini izlaymiz
                name_html = re.findall(r'<input[^>]+name="name"[^>]+title="([^"]+)"', page_html, re.IGNORECASE)
                if name_html:
                    title = name_html[0].strip()
                    
                # Yetkazib berish muddatini izlaymiz
                del_html = re.findall(r'<label>[^<]*(?:етказиб бериш муддати|muddat|muddati)[^<]*</label>[^>]*<input[^>]+title="([^"]+)"', page_html, re.IGNORECASE)
                if del_html:
                    delivery_term = f"{del_html[0].strip()} Kun"
                
                # HTML dan input title orqali summa izlaymiz (Auksion uchun)
                sum_html = re.findall(r'name="totalcost_clone"[^>]+title="([^"]+)"', page_html)
                if sum_html:
                    total_sum = sum_html[0].strip() + " UZS"
                else:
                    # Takliflar so'rovi va boshqalar uchun (HTML matni orqali)
                    import bs4
                    plain_text = bs4.BeautifulSoup(page_html, 'html.parser').text
                    # 'narx' yoki 'summa' so'ziga yaqin raqamlarni qidiramiz
                    val_matches = re.findall(r'(?:нархи|narx|summa|narxi)[^\d]{0,80}?(\d{1,3}(?: \d{3})*(?:\.\d{2})?)\s*(?:UZS|СУМ|сўм|so\'m)', plain_text, re.IGNORECASE)
                    if val_matches:
                        # Topilgan summalar ichidan eng kattasini olamiz (Jami summa)
                        max_val = 0
                        max_str = "0"
                        for v in val_matches:
                            num = float(v.replace(" ", ""))
                            if num > max_val:
                                max_val = num
                                max_str = v
                        total_sum = max_str + " UZS"
                        
                company = "Buyurtmachi (xt-xarid)"
                
            # Qolgan standart (etender)
            else:
                # 1. Jami summa
                sum_matches = re.findall(r"(?:Jami boshlang.*?narx|Jami summa|Boshlang.*?ich narx)[^\d]*([\d\s,\.]+UZS)", page_text, re.IGNORECASE)
                if sum_matches:
                    total_sum = sum_matches[0].strip()
                    
                # 2. Tashkilot nomi
                org_matches = re.findall(r"Buyurtmachi nomi:\n+(.+?)\n", page_text, re.IGNORECASE)
                if org_matches:
                    company = org_matches[0].strip()
                    
                # 3. Lot nomi
                lot_name_matches = re.findall(r"(?:Lot nomi|Qo.*?shimcha ma.*?lumotlar|Texnik tavsif):\n+(.+?)\n", page_text, re.IGNORECASE)
                if lot_name_matches:
                    title = lot_name_matches[0].strip()
                    if title == "-":
                        if len(lot_name_matches) > 1: title = lot_name_matches[1].strip()
                    
                # 4. Zakalat
                zakalat_matches = re.findall(r"Zakalat(?: summasi| miqdori):\n+(.+?)\n", page_text, re.IGNORECASE)
                if zakalat_matches:
                    deposit_sum = zakalat_matches[0].strip()
                else:
                    zakalat_matches = re.findall(r"Zakalat:\n+(.+?)\n", page_text, re.IGNORECASE)
                    if zakalat_matches: deposit_sum = zakalat_matches[0].strip()
                    
                # Foizli zakalatni hisoblash
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
                    
                # 5. Sanalar
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
                
                # 6. Yetkazib berish muddati
                delivery_matches = re.findall(r"Yetkazib berish muddati\s*(\d+\s*Kun)", page_text, re.IGNORECASE)
                if not delivery_matches:
                    delivery_matches = re.findall(r"(\d+\s*Kun)", page_text, re.IGNORECASE)
                if delivery_matches:
                    delivery_term = delivery_matches[0].strip()
            
            # Extract products for xarid.uzex.uz via JS
            items_str = ""
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
                extracted_items = await page.evaluate(js_extract)
                if extracted_items:
                    items_str = "\n\n📦 <b>Tovarlar:</b>\n" + "\n".join(extracted_items)
            
            await browser.close()
            
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
        pass
        
    dummy_deadline = datetime.now() + timedelta(days=2, hours=5)
    dummy_start = datetime.now() - timedelta(days=1)
    
    return {
        "link": url,
        "title": "Kechirasiz, ma'lumotni to'g'ridan-to'g'ri o'qib bo'lmadi",
        "company_name": "Tashkilot nomi yashiringan",
        "total_sum": "0 UZS",
        "deposit_sum": "0 UZS",
        "delivery_term": "Noma'lum",
        "start_date": dummy_start,
        "deadline": dummy_deadline,
        "source_site": source_site
    }
