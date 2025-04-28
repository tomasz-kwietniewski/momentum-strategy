import pandas as pd
import requests
import smtplib
from email.message import EmailMessage
import ssl
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import os
import json



# Konfiguracja
ETF_LIST = {
    "SP500": "US.SPY",
    "BTC": "BTCUSD",
    "GOTÓWKA": "US.SHG"
}
START_DATE = "2021-01-01"
INITIAL_CAPITAL = 100000
DATA_FILE = "data.json"
HTML_FILE = "momentum.html"

SMTP_SERVER = "h57.seohost.pl"
SMTP_PORT = 465
SMTP_USER = "srv84712"
SMTP_PASS = "asHfjpaDOQXB"
MAIL_FROM = "news@tomaszkwietniewski.pl"
MAIL_TO = "tomasz.kwietniewski@gmail.com"

def fetch_change(symbol):
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    r = requests.get(url)
    lines = r.text.strip().split("\n")[1:]  # pomiń nagłówek
    prices = [float(line.split(",")[4]) for line in lines if line]
    if len(prices) < 63:  # około 3 miesiące
        return None
    pct_change = ((prices[-1] / prices[-63]) - 1) * 100
    return pct_change

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    else:
        return {
            "history": [],
            "current_signal": None,
            "capital": INITIAL_CAPITAL
        }

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def send_email(subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = MAIL_FROM
    msg["To"] = MAIL_TO
    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

def update_html(data):
    today = datetime.now().strftime("%d.%m.%Y")
    current_signal = data.get("current_signal", "Brak sygnału")
    capital = data.get("capital", 0)

    history_rows = ""
    for record in data.get("history", []):
        history_rows += f"<tr><td>{record['date']}</td><td>{record['signal']}</td><td>{record['capital']:.2f} zł</td></tr>\n"

    # Wczytaj szablon HTML
    with open("template.html", "r", encoding="utf-8") as f:
        template = f.read()

    html = template.replace("{{CURRENT_SIGNAL}}", current_signal)\
                   .replace("{{UPDATE_DATE}}", today)\
                   .replace("{{CAPITAL}}", f"{capital:.2f}")\
                   .replace("{{HISTORY_ROWS}}", history_rows)

    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)



def main():
    today = datetime.now()
    data = load_data()

    changes = {}
    for name, symbol in ETF_LIST.items():
        change = fetch_change(symbol)
        if change is not None:
            changes[name] = change

    best_signal = max(changes, key=changes.get)

    if today.day == 15:
        # 15-tego tylko wysyłka ostrzeżenia
        if best_signal != data["current_signal"]:
            send_email(
                "Momentum: możliwa zmiana sygnału",
                f"Obecny sygnał: {data['current_signal']}\nNowy sugerowany sygnał: {best_signal}"
            )
    elif (today.day >= 28 and today.month != (today + timedelta(days=4)).month) or today.day == 31:
        # Ostatni dzień miesiąca
        if best_signal != data["current_signal"]:
            data["current_signal"] = best_signal
            data["history"].append({
                "date": today.strftime("%Y-%m-%d"),
                "signal": best_signal,
                "capital": data["capital"]
            })
            send_email(
                "Momentum: zmiana sygnału",
                f"Nowy sygnał: {best_signal}\nZmiana została dokonana."
            )
        else:
            data["history"].append({
                "date": today.strftime("%Y-%m-%d"),
                "signal": data["current_signal"],
                "capital": data["capital"]
            })
        # Zmieniamy wartość kapitału zgodnie z miesięcznym wynikiem
        monthly_change = changes[data["current_signal"]]
        data["capital"] *= (1 + monthly_change / 100)

    update_html(data)
    save_data(data)

if __name__ == "__main__":
    main()
