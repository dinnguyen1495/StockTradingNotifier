"""
Stock Trading Alerter
    This script will automatically send stock information via SMS.
"""

import requests
import re
from datetime import datetime, timedelta
from pytz import timezone
from twilio.rest import Client
import config

# Stocks that are interested and their companies
STOCKS = ["TSLA", "FB", "SIEGY", "AAPL", "AMZN"]
COMPANIES = ["Tesla Inc", "Facebook Inc", "SIEMENS AG", "Apple Inc", "Amazon.com Inc"]


def __get_stock_time(stock_tz: timezone) -> datetime:
    """
    Convert local time to stock time.
    :param stock_tz: Timezone of company that the stock belongs to.
    :return: date and time of stock
    """
    return datetime.now().astimezone(stock_tz)


def __get_date_days_shift(stock_time: datetime, days: int) -> datetime:
    """
    Get the date of yesterday or the day before yesterday in stock market.
    Noted here that stock market is closed at the weekend and date should be shifted 1 or 2 days accordingly
    Can't be use to get date that is further than 2 days in stock market.
    :param stock_time: current stock time
    :param days: number of days to shift
    :return: the shifted date
    """
    if days < 1 or days > 2:
        raise ValueError("This function can only shift for maximum 2 days")
    if (2 <= stock_time.weekday() <= 5) or (stock_time.weekday() == 1 and days == 1):
        return stock_time - timedelta(days=days)
    if stock_time.weekday() == 0 or stock_time.weekday() == 1:
        return stock_time - timedelta(days=days + 2)
    if stock_time.weekday() == 6:
        return stock_time - timedelta(days=days + 1)


def get_stock_difference(stock_symbol: str) -> float:
    """
    Get the difference between stock price of yesterday and the day before yesterday.
    Information is gotten from Alpha Vantage API.
    :return: difference in percentage
    """
    av_params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": stock_symbol,
        "apikey": config.AV_API_KEY
    }
    response = requests.get("https://www.alphavantage.co/query", params=av_params)
    response.raise_for_status()

    stock_daily_data = response.json()
    stock_timezone = timezone(stock_daily_data["Meta Data"]["5. Time Zone"])
    print(stock_daily_data)
    stock_t = __get_stock_time(stock_timezone)
    yesterday_stock_t = __get_date_days_shift(stock_t, 1)
    two_days_ago_stock_t = __get_date_days_shift(stock_t, 2)

    yesterday_close = float(
        stock_daily_data["Time Series (Daily)"][yesterday_stock_t.strftime("%Y-%m-%d")]["4. close"]
    )
    two_days_ago_close = float(
        stock_daily_data["Time Series (Daily)"][two_days_ago_stock_t.strftime("%Y-%m-%d")]["4. close"]
    )
    different = round(yesterday_close - two_days_ago_close, 2)
    return round(different * 100 / yesterday_close, 2)


def get_news(company_name: str) -> list[dict]:
    """
    Get the first 3 news pieces that relates to the interested stock.
    NewsAPI is used here.
    :return:
        list of dictionaries that contains news
    """
    news_params = {
        "q": company_name,
        "apiKey": config.NEWS_API_KEY
    }
    response = requests.get("https://newsapi.org/v2/everything", params=news_params)
    response.raise_for_status()
    news_data = response.json()
    return news_data["articles"][:3]


def create_sms(stock_difference: float, stock_highlights: list[dict], company_name: str) -> str:
    """
    Create the SMS message like this:
        TSLA: 🔺2.07%
        Headline: Were Hedge Funds Right About Piling Into Tesla Inc.
        Brief: We at Insider Monkey have gone over 821 13F filings that hedge funds and prominent investors are required to
        file by the SEC The 13F filings show the funds' and investors' portfolio positions as of March 31st, near the height
        of the coronavirus market crash.
    """
    a_tags_regex = re.compile("<.*?>")
    sms = f"{company_name}: {'🔺' if stock_difference > 0 else '🔻'}{stock_difference}%\n\n"
    for highlight in stock_highlights:
        headline = f"Headline: {highlight['title']}\n"
        brief = re.sub(a_tags_regex, '', f"Brief: {highlight['description']}\n")
        url = f"Link: {highlight['url']}\n"
        sms += headline + brief + url + "\n"
    return sms


def send_message(message: str) -> None:
    """
    Send a message with the percentage change and each article's title and description to your phone number.
    Twilio API will send the message via SMS.
    :param message:
        Piece of information about the stock
    """
    if message == "":
        return
    client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
    sms = client.messages.create(
        from_=config.TWILIO_SENDER_NUMBER,
        to=config.TWILIO_RECEIVER_NUMBER,
        body=message
    )
    print(sms.status)


def main():
    """
    Main method to wrap everything up.
    """
    for stock_symbol, company_name in zip(STOCKS, COMPANIES):
        stock_difference = get_stock_difference(stock_symbol)
        stock_highlights = get_news(company_name)
        sms = create_sms(stock_difference, stock_highlights, company_name)
        send_message(sms)


main()
