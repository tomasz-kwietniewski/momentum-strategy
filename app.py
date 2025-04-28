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
    "BTC": "BTCUSD"
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

def fetch_change(symbol):
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    r = requests.get(url)
    prices = pd.read_csv(io.StringIO(r.text))
    prices["Data"] = pd.to_datetime(prices["Data"])
    prices = prices.sort_values("Data")

    # Bierzemy dane od daty startowej
    prices = prices[prices["Data"] >= pd.to_datetime(START_DATE)]

    if len(prices) == 0:
        return None

    first_price = prices.iloc[0]["Zamknięcie"]
    last_price = prices.iloc[-1]["Zamknięcie"]
    pct_change = (last_price / first_price - 1) * 100
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
    current_signal = data["current_signal"] or "Brak sygnału"
    capital = data["capital"]

    history_rows = ""
    for record in data["history"]:
        history_rows += f"<tr><td>{record['date']}</td><td>{record['signal']}</td><td>{record['capital']:.2f} zł</td></tr>\n"

    # Wczytaj szablon HTML
    with open("template.html", "r", encoding="utf-8") as f:
        template = f.read()

    html = template.replace("{{CURRENT_SIGNAL}}", current_signal)\
                   .replace("{{UPDATE_DATE}}", today)\
                   .replace("{{CAPITAL}}", f"{capital:.2f}")\
                   .replace("{{HISTORY_ROWS}}", history_rows)

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)

def main():
    today = datetime.now()
    data = load_data()

    # Fetch data for all ETFs
    prices = {}
    for name, symbol in ETF_LIST.items():
        prices[name] = fetch_change(symbol)

    dates = prices["SP500"].index
    dates = dates[(dates >= START_DATE)]

    for date in dates:
        if date.day not in [15, date.days_in_month]:  # tylko 15-tego lub ostatniego dnia
            continue

        # Obliczamy 3M zmiany
        changes = {}
        for name in ETF_LIST.keys():
            try:
                current_price = prices[name].loc[date]
                three_months_ago = date - relativedelta(months=3)
                old_price = prices[name].loc[prices[name].index <= three_months_ago][-1]
                change = ((current_price / old_price) - 1) * 100
                changes[name] = change
            except:
                changes[name] = -9999  # Słaby wynik jeśli brak danych

        # "Gotówka" zawsze +0%, traktujemy jako safe haven
        changes["GOTÓWKA"] = 0

        best_signal = max(changes, key=changes.get)

        if date.day == 15:
            # 15-tego ostrzeżenie
            if best_signal != data["current_signal"]:
                send_email(
                    "Momentum: możliwa zmiana sygnału",
                    f"Obecny sygnał: {data['current_signal']}\nNowy sugerowany sygnał: {best_signal}"
                )
        else:
            # ostatni dzień miesiąca
            if best_signal != data["current_signal"]:
                data["current_signal"] = best_signal
                send_email(
                    "Momentum: zmiana sygnału",
                    f"Nowy sygnał: {best_signal}\nZmiana została dokonana."
                )

            # Zmieniamy kapitał
            monthly_change = changes.get(data["current_signal"], 0)
            data["capital"] *= (1 + monthly_change / 100)
            data["history"].append({
                "date": date.strftime("%Y-%m-%d"),
                "signal": data["current_signal"],
                "capital": data["capital"]
            })

    update_html(data)
    save_data(data)

if __name__ == "__main__":
    main()
