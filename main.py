from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, FileResponse
import requests
import os
import csv
from datetime import datetime
from typing import List, Dict
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

app = FastAPI(title="Boise Multi-Unit Cash Flow Analyzer")

# ========================= CONFIG =========================
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "YOUR_RAPIDAPI_KEY_HERE")
ATTOM_API_KEY = os.getenv("ATTOM_API_KEY", "YOUR_ATTOM_API_KEY_HERE")

EMAIL_TO = "misarija@msn.com"
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

MORTGAGE_RATE = 6.35          # May 2026 rate
DOWN_PAYMENT_PCT = 0.20

scheduler = BackgroundScheduler()

# =========================================================

def calculate_mortgage(principal: float) -> float:
    """Calculate 30-year fixed mortgage payment (P&I only)"""
    if principal <= 0:
        return 0.0
    monthly_rate = MORTGAGE_RATE / 12 / 100
    months = 360
    payment = principal * (monthly_rate * (1 + monthly_rate)**months) / ((1 + monthly_rate)**months - 1)
    return round(payment, 2)


def estimate_rental_income(units: int, price: int = 0) -> float:
    """Refined rental estimates for Boise multi-unit properties"""
    if units == 2:
        per_unit = 1650
    elif units == 3:
        per_unit = 1580
    elif units == 4:
        per_unit = 1520
    else:
        per_unit = 1550

    if price > 0 and price < 600000:
        per_unit += 80

    return round(units * per_unit)


def fetch_realtor_properties(max_price: int = 1000000) -> List[Dict]:
    """Primary: Realtor.com via RapidAPI"""
    url = "https://realtor-data1.p.rapidapi.com/property_list/"
    payload = {
        "query": {
            "city": "Boise",
            "state_code": "ID",
            "status": ["for_sale"],
            "price_max": max_price,
            "property_type": ["multi_family"]
        },
        "limit": 42,
        "sort": {"direction": "desc", "field": "list_date"}
    }
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "realtor-data1.p.rapidapi.com",
        "Content-Type": "application/json"
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        properties = []
        for item in data.get("properties", []):
            prop = {
                "id": item.get("property_id"),
                "address": item.get("location", {}).get("address", {}).get("line", "N/A"),
                "price": item.get("list_price") or item.get("price"),
                "units": item.get("description", {}).get("units") or 2,
                "beds": item.get("description", {}).get("beds"),
                "baths": item.get("description", {}).get("baths"),
                "sqft": item.get("description", {}).get("sqft"),
                "image": (item.get("photos") or [{}])[0].get("href") if item.get("photos") else None,
                "source": "Realtor.com"
            }
            if prop.get("price") and 0 < prop["price"] < max_price:
                properties.append(prop)
        return properties[:30]
    except Exception as e:
        print("Realtor API Error:", e)
        return []


def fetch_attom_fallback(max_price: int = 1000000) -> List[Dict]:
    """Fallback: ATTOM"""
    headers = {"Accept": "application/json", "apikey": ATTOM_API_KEY}
    params = {
        "postalcode": "83702|83704|83705|83706|83709",
        "propertyindicator": "21",
        "maxavmvalue": max_price,
        "pagesize": 50
    }
    try:
        resp = requests.get(
            "https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/snapshot",
            headers=headers, params=params, timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
        properties = []
        for item in data.get("property", []):
            prop = {
                "id": item.get("identifier", {}).get("attomId"),
                "address": item.get("address", {}).get("oneLine", "N/A"),
                "price": item.get("avm", {}).get("amount", {}).get("avmvalue", 0),
                "units": 2,
                "beds": 0, "baths": 0, "sqft": 0,
                "image": None,
                "source": "ATTOM"
            }
            if prop.get("price") and 0 < prop["price"] < max_price:
                properties.append(prop)
        return properties[:20]
    except:
        return []


def fetch_properties(max_price: int = 1000000) -> List[Dict]:
    props = fetch_realtor_properties(max_price)
    if not props:
        print("Falling back to ATTOM...")
        props = fetch_attom_fallback(max_price)
    return props


def enrich_with_financials(properties: List[Dict]) -> List[Dict]:
    enriched = []
    for p in properties:
        price = float(p.get("price", 0))
        units = max(int(p.get("units", 2)), 2)

        down_payment = price * DOWN_PAYMENT_PCT
        loan_amount = price - down_payment
        monthly_mortgage = calculate_mortgage(loan_amount)
        est_rental = estimate_rental_income(units, int(price))
        cash_flow = est_rental - monthly_mortgage

        p.update({
            "down_payment": round(down_payment),
            "loan_amount": round(loan_amount),
            "monthly_mortgage": monthly_mortgage,
            "est_monthly_rental": est_rental,
            "est_monthly_cash_flow": round(cash_flow, 0),
            "cash_flow_positive": cash_flow > 0,
            "per_unit_rent": round(est_rental / units, 0)
        })
        enriched.append(p)
    return enriched


def generate_csv(properties: List[Dict], filename="boise_multi_units_cashflow.csv"):
    if not properties:
        return None
    fieldnames = ["address", "price", "units", "down_payment", "loan_amount",
                  "monthly_mortgage", "est_monthly_rental", "est_monthly_cash_flow", "source"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in properties:
            row = {k: p.get(k) for k in fieldnames}
            writer.writerow(row)
    return filename


def send_email_with_csv():
    properties = fetch_properties()
    enriched = enrich_with_financials(properties)
    csv_file = generate_csv(enriched)
    if not csv_file:
        return

    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO
    msg["Subject"] = f"Boise Multi-Unit Cash Flow Report - {datetime.now().strftime('%Y-%m-%d')}"

    with open(csv_file, "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={csv_file}")
        msg.attach(part)

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"✅ Email sent successfully at {datetime.now()}")
    except Exception as e:
        print("Email failed:", e)
    finally:
        if os.path.exists(csv_file):
            os.remove(csv_file)


def generate_html(properties: List[Dict]) -> str:
    enriched = enrich_with_financials(properties)
    props_json = str(enriched).replace("'", '"')
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Boise Multi-Unit Cash Flow Analyzer</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    </head>
    <body class="bg-gray-50 p-6">
        <div class="max-w-7xl mx-auto">
            <h1 class="text-4xl font-bold text-center mb-2">🏠 Boise Multi-Unit Cash Flow</h1>
            <p class="text-center text-gray-600 mb-8">30yr Fixed @ {MORTGAGE_RATE}% • 20% Down • Refined Rental Estimates</p>
            
            <div class="text-center mb-8">
                <a href="/export-csv" 
                   class="inline-flex items-center bg-green-600 hover:bg-green-700 text-white px-8 py-4 rounded-2xl font-semibold text-lg shadow-md">
                    <i class="fa-solid fa-download mr-3"></i> Download CSV
                </a>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8" id="properties"></div>
        </div>

        <script>
            const properties = {props_json};
            document.getElementById('properties').innerHTML = properties.map(p => `
                <div class="bg-white rounded-3xl shadow-xl overflow-hidden hover:shadow-2xl transition">
                    <img src="${'https://picsum.photos/id/1015/800/400'}" class="w-full h-52 object-cover">
                    <div class="p-6">
                        <h3 class="text-3xl font-bold">$${Number(p.price).toLocaleString()}</h3>
                        <p class="text-gray-500">${p.address}</p>
                        <span class="inline-block mt-3 px-5 py-2 bg-emerald-100 text-emerald-700 rounded-full font-medium">${p.units}-unit</span>
                        
                        <div class="mt-6 space-y-3 text-sm">
                            <div class="flex justify-between"><span>20% Down</span><strong>$${Number(p.down_payment).toLocaleString()}</strong></div>
                            <div class="flex justify-between"><span>Monthly Mortgage</span><strong>$${p.monthly_mortgage}</strong></div>
                            <div class="flex justify-between"><span>Est. Rental Income</span><strong class="text-emerald-600">$${p.est_monthly_rental}</strong></div>
                        </div>
                        
                        <div class="mt-8 pt-6 border-t text-center">
                            <div class="text-3xl font-bold ${p.cash_flow_positive}">
                                $${p.est_monthly_cash_flow}/mo
                            </div>
                            <p class="text-sm text-gray-500">Estimated Monthly Cash Flow</p>
                        </div>
                    </div>
                </div>
            `).join('');
        </script>
    </body>
    </html>
    """


# ========================= ROUTES =========================
@app.get("/", response_class=HTMLResponse)
async def home():
    properties = fetch_properties()
    return HTMLResponse(content=generate_html(properties))


@app.get("/export-csv")
async def export_csv():
    properties = fetch_properties()
    enriched = enrich_with_financials(properties)
    csv_file = generate_csv(enriched)
    if not csv_file:
        return {"error": "No properties found"}
    return FileResponse(csv_file, media_type="text/csv", filename="boise_multi_units_cashflow.csv")


@app.get("/api/properties")
async def get_properties(max_price: int = Query(1000000, le=2000000)):
    properties = fetch_properties(max_price)
    return enrich_with_financials(properties)


# ========================= SCHEDULER =========================
scheduler.add_job(send_email_with_csv, 'cron', hour=8, minute=0)
scheduler.start()
print(f"✅ App running — Daily email scheduled for 8:00 AM to {EMAIL_TO}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
