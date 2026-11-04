from collections import defaultdict
from datetime import timedelta

import yfinance as yf
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone

from .models import Trade


def daily_closes(ticker, start, end):
    try:
        history = yf.Ticker(ticker).history(
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            interval="1d",
        )
    except Exception:
        return {}
    if history is None or history.empty or "Close" not in history:
        return {}
    closes = {}
    for stamp, close in history["Close"].items():
        if close == close:
            closes[stamp.date()] = float(close)
    return closes


@login_required
def performance_data(request):
    trades = list(Trade.objects.filter(user=request.user).order_by("timestamp"))
    if not trades:
        return JsonResponse({"labels": [], "gain": [], "value": [], "invested": [], "since": None})

    today = timezone.localdate()
    trade_days = [timezone.localtime(t.timestamp).date() for t in trades]
    start = trade_days[0]
    tickers = sorted({t.ticker for t in trades})
    closes = {ticker: daily_closes(ticker, start, today) for ticker in tickers}

    days = {start, today}
    for series in closes.values():
        days.update(day for day in series if start <= day <= today)

    shares = defaultdict(float)
    last_price = {}
    spent = 0.0
    received = 0.0
    labels, gain, value, invested = [], [], [], []
    index = 0

    for day in sorted(days):
        while index < len(trades) and trade_days[index] <= day:
            trade = trades[index]
            quantity = float(trade.quantity)
            price = float(trade.price)
            if trade.trade_type == Trade.BUY:
                shares[trade.ticker] += quantity
                spent += quantity * price
            else:
                shares[trade.ticker] -= quantity
                received += quantity * price
            last_price.setdefault(trade.ticker, price)
            index += 1

        for ticker in tickers:
            if day in closes[ticker]:
                last_price[ticker] = closes[ticker][day]

        held = sum(
            shares[ticker] * last_price.get(ticker, 0.0)
            for ticker in tickers
            if shares[ticker] > 0
        )
        labels.append(day.isoformat())
        value.append(round(held, 2))
        invested.append(round(spent - received, 2))
        gain.append(round(held + received - spent, 2))

    return JsonResponse({
        "labels": labels,
        "gain": gain,
        "value": value,
        "invested": invested,
        "since": start.isoformat(),
    })