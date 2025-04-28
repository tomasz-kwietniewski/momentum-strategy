import pandas as pd
import smtplib
import ssl
import requests
from email.message import EmailMessage
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import os
import json
import io

# Konfiguracja
ETF_LIST = {
    "SP500": "US.SPY",
    "BTC": "BTCW.UK",
    "GOTÓWKA": "CASH"
}

START_DATE = "2021-01-01"
INITIAL_CAPITAL = 100000
DATA_FILE = "data.json"

SMTP_SERVER = "h57.seohost.pl"
SMTP_PORT = 465
SMTP_USER = "srv84712"
SMTP_PASS = "asHfjpaDOQXB"
MAIL_FROM = "news@tomaszkwietniewski.pl"
MAIL_TO = "tomasz.kwietniewski@gmail.com"

def fetch_data(symbol):
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    r = requests.get(url)
    df = pd.read_csv(io.StringIO(r.text))

    # Ustal pierwszą kolumnę jako datę
    first_col = df.columns[0]
    df = df.rename(columns={first_col: "Date"})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    df = df.set_index("Date").sort_index()

    # Odcinamy od daty START_DATE
    df = df[df.index >= pd.to_datetime(START_DATE)]

    # Ustalamy kolumnę zamknięcia
    if "Close" in df.columns:
        return df["Close"]
    elif "Zamknięcie" in df.columns:
        return df["Zamknięcie"]
    else:
        raise ValueError(f"Brak kolumny Close/Zamknięcie dla {symbol}")



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

def update_html(data, today_leader):
    today = datetime.now().strftime("%d.%m.%Y")
    current_signal = data["current_signal"] or "Brak sygnału"
    capital = data["capital"]

    history_rows = ""
    for record in data["history"]:
        history_rows += f"<tr><td>{record['date']}</td><td>{record['signal']}</td><td>{record['capital']:.2f} zł</td></tr>\n"

    with open("template.html", "r", encoding="utf-8") as f:
        template = f.read()

    html = template.replace("{{CURRENT_SIGNAL}}", current_signal)\
                   .replace("{{UPDATE_DATE}}", today)\
                   .replace("{{CAPITAL}}", f"{capital:.2f}")\
                   .replace("{{HISTORY_ROWS}}", history_rows)\
                   .replace("{{TODAY_LEADER}}", today_leader)

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)

def main():
    today = datetime.now()
    data = load_data()

    prices = {}
    for name, symbol in ETF_LIST.items():
        if name == "GOTÓWKA":
            continue
        prices[name] = fetch_data(symbol)

    # Wyznacz aktualnego lidera na dzisiaj
    changes_today = {}
    for name in ETF_LIST.keys():
        if name == "GOTÓWKA":
            changes_today[name] = 0
            continue
        df = prices[name]
        try:
            today_price = df.iloc[-1]
            three_months_ago = today_price.name - relativedelta(months=3)
            old_price = df[df.index <= three_months_ago].iloc[-1]
            change = ((today_price / old_price) - 1) * 100
            changes_today[name] = change
        except:
            changes_today[name] = -9999

    today_leader = max(changes_today, key=changes_today.get)

    # 15-tego: tylko rekonesans
    if today.day == 15:
        changes = {name: changes_today.get(name, -9999) for name in ETF_LIST.keys()}
        best_signal = max(changes, key=changes.get)

        if best_signal != data["current_signal"]:
            send_email(
                "Momentum: możliwa zmiana sygnału",
                f"Obecny sygnał: {data['current_signal']}\nNowy sugerowany sygnał: {best_signal}"
            )

    # Ostatni dzień miesiąca: zmiana sygnału + zmiana kapitału
    elif (today.day >= 28 and (today + timedelta(days=4)).month != today.month) or today.day == 31:
        changes = {name: changes_today.get(name, -9999) for name in ETF_LIST.keys()}
        best_signal = max(changes, key=changes.get)

        if best_signal != data["current_signal"]:
            data["current_signal"] = best_signal
            send_email(
                "Momentum: zmiana sygnału",
                f"Nowy sygnał: {best_signal}\nZmiana została dokonana."
            )

        monthly_change = changes.get(data["current_signal"], 0)
        data["capital"] *= (1 + monthly_change / 100)
        data["history"].append({
            "date": today.strftime("%Y-%m-%d"),
            "signal": data["current_signal"],
            "capital": data["capital"]
        })

    update_html(data, today_leader)
    save_data(data)

if __name__ == "__main__":
    main()
