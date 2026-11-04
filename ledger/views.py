import json
import os
import logging
from collections import defaultdict
from decimal import Decimal

import stripe
import yfinance as yf
from reportlab.pdfgen import canvas
from sib_api_v3_sdk import Configuration
from sib_api_v3_sdk.rest import ApiException

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from portfolios.models import ModelPortfolio
from portfolios.utils import fetch_nav

from .forms import (
    AdminAccountForm,
    AdminKycForm,
    AdminUserForm,
    CustomAuthForm,
    KycForm,
    OTPForm,
    RiskProfileForm,
    SignUpForm,
    TradeForm,
)
from .models import (
    Account,
    Holding,
    KycDocument,
    Message,
    OtpCode,
    RiskProfile,
    Trade,
    Transaction,
    determine_investor_type,
)


RISK_RECOMMENDATIONS = {
    'Aggressive': {
        'allocation': {
            'US Equities': '70%',
            'International Equities': '20%',
            'Bonds': '10%',
        },
        'products': ['SPY (S&P 500 ETF)', 'VEA (Developed Mkts ETF)', 'TLT (US 20+yr Treasury ETF)'],
        'description': 'High‐risk, high‐reward focus for long-term growth.'
    },
    'Growth': {
        'allocation': {
            'US Equities': '50%',
            'International Equities': '20%',
            'Bonds': '30%',
        },
        'products': ['VTI (Total US Market ETF)', 'IEFA (Intl Core ETF)', 'AGG (US Aggregate Bond ETF)'],
        'description': 'Moderate-to-high risk with a balanced bond sleeve.'
    },
    'Income': {
        'allocation': {
            'US Equities': '30%',
            'Bonds': '60%',
            'Cash': '10%',
        },
        'products': ['SCHD (US Dividend ETF)', 'LQD (Investment-Grade Corp Bond ETF)', 'BIL (Short-Term T-Bill ETF)'],
        'description': 'Capital preservation and steady yield focus.'
    },
}



@login_required
def risk_profile(request):
    if request.method == 'POST':
        form = RiskProfileForm(request.POST)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.investor_type = determine_investor_type(
                profile.experience,
                profile.goals,
                profile.time_horizon,
                profile.risk_tolerance
            )
            profile.save()

            # look up our recommendations
            rec = RISK_RECOMMENDATIONS.get(profile.investor_type, {})
            return render(request, 'ledger/risk_profile_result.html', {
                'profile': profile,
                'recommendations': rec
            })
    else:
        form = RiskProfileForm()

    return render(request, 'ledger/risk_profile_form.html', {
        'form': form
    })



stripe.api_key = settings.STRIPE_API_KEY




def home(request):
    return render(request, 'ledger/home.html')



def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            group, _ = Group.objects.get_or_create(name='customer')
            user.groups.add(group)

            # Create account and save 2FA preference
            account = Account.objects.create(
                user=user,
                balance=Decimal('0.00')
            )
            account.two_factor_enabled = form.cleaned_data.get('enable_2fa', False)
            account.save()

            if form.cleaned_data.get('enable_2fa'): 
                otp = OtpCode.generate_for(user)
                print(f"[Signup OTP for {user.email}] Code: {otp.code}")
                send_mail(
                    'Your Arona Bank Signup Code',
                    f'Your one-time signup code is: {otp.code}',
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                )
                request.session['pre_2fa_user'] = user.id
                return redirect('otp_verify')  
            else:
                login(request, user)
                return redirect('dashboard')
    else:
        form = SignUpForm()
    return render(request, 'ledger/signup.html', {'form': form})





def login_2fa(request):
    if request.method == 'POST':
        form = CustomAuthForm(request=request, data=request.POST)
        if form.is_valid():
            user = form.get_user()

            #  BYPASS 2FA FOR ADMIN USER
            if user.username == "admin":
                login(request, user)
                return redirect('dashboard')
            account = Account.objects.get(user=user)
            if not account.two_factor_enabled:
                login(request, user)
                return redirect('dashboard')
             
            # Otherwise, send OTP
            otp = OtpCode.generate_for(user)
            print(f"[In case email is invalid] Generated OTP for {user.email}: {otp.code}")

            send_mail(
                'Your Arona Bank Login Code',
                f'Your one-time login code is: {otp.code}',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )

            request.session['pre_2fa_user'] = user.id
            return redirect('otp_verify')
    else:
        form = CustomAuthForm()
    return render(request, 'registration/login.html', { 'form': form })





def otp_verify(request):
    user_id = request.session.get('pre_2fa_user')
    if not user_id:
        return redirect('login')
    user = get_user_model().objects.get(id=user_id)
    if request.method == 'POST':
        form = OTPForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            otp = OtpCode.objects.filter(user=user, code=code).order_by('-created_at').first()
            if otp and not otp.is_expired():
                login(request, user)
                otp.delete()
                return redirect('dashboard')
            form.add_error('code', 'Invalid or expired code')
    else:
        form = OTPForm()
    return render(request, 'registration/otp_verify.html', {'form': form})






@login_required
def dashboard(request):
    account, _ = Account.objects.get_or_create(
        user=request.user,
        defaults={'balance': Decimal('0.00')}
    )
    transactions = account.transactions.order_by('-timestamp')[:4]
    risk_profile = RiskProfile.objects.filter(user=request.user).order_by('-created_at').first()

    latest_doc = KycDocument.objects.filter(user=request.user).order_by('-uploaded_at').first()
    if not latest_doc or latest_doc.status != KycDocument.APPROVED:
        if not any("Your KYC is not submitted" in m.message for m in messages.get_messages(request)):
            messages.warning(request, "Your KYC is not submitted. Some features may be restricted. Upload it anytime.")

    search_result = None
    if request.GET.get('search'):
        user_ticker = request.GET['search'].upper()
        try:
            stock = yf.Ticker(user_ticker)
            price = stock.history(period='1d').tail(1)['Close'].iloc[0]
            search_result = {'symbol': user_ticker, 'price': round(price, 2)}
        except Exception:
            search_result = {'error': f"Could not find data for '{user_ticker}'."}

    default_tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
    stock_data = []
    for ticker in default_tickers:
        try:
            stock = yf.Ticker(ticker)
            price = stock.history(period='1d').tail(1)['Close'].iloc[0]
            stock_data.append({'symbol': ticker, 'price': round(price, 2)})
        except Exception:
            stock_data.append({'symbol': ticker, 'price': 'N/A'})

    rebalance_alert = None
    if risk_profile and account.balance > 0:
        portfolio = ModelPortfolio.objects.filter(name__icontains=risk_profile.investor_type).first()
        if portfolio:
            total_value = Decimal('0')
            current_values = {}
            for line in portfolio.lines.all():
                nav = fetch_nav(line.asset)
                if nav is None:
                    continue
                invested_amt = (line.target_pct / Decimal('100')) * account.balance
                shares = invested_amt / Decimal(nav)
                current_val = shares * Decimal(nav)
                current_values[line.asset] = current_val
                total_value += current_val
            if total_value > 0:
                for line in portfolio.lines.all():
                    if line.asset in current_values:
                        actual_val = current_values[line.asset]
                        actual_pct = (actual_val / total_value) * Decimal('100')
                        drift = abs(actual_pct - line.target_pct)
                        if drift >= 5:
                            rebalance_alert = {
                                'portfolio': portfolio.name,
                                'drift': round(drift, 2)
                            }
                            break

    trade_form = TradeForm()
    holdings = Holding.objects.filter(user=request.user)
    labels = []
    data = []
    gains = []
    asset_chart_data = []

    for h in holdings:
        nav = fetch_nav(h.ticker)
        if nav:
            current_value = h.quantity * Decimal(nav)
            cost_basis = h.quantity * h.avg_price
            gain = current_value - cost_basis
            gains.append({'ticker': h.ticker, 'gain': round(gain, 2)})
            labels.append(h.ticker)
            data.append(round(float(current_value), 2))
            asset_chart_data.append({
                'ticker': h.ticker,
                'quantity': float(h.quantity),
                'nav': float(nav),
                'value': float(current_value)
            })
        else:
            labels.append(h.ticker)
            data.append(0)
            gains.append({'ticker': h.ticker, 'gain': Decimal('0.00')})
            asset_chart_data.append({
                'ticker': h.ticker,
                'quantity': float(h.quantity),
                'nav': 0,
                'value': 0
            })

    price_history_data = {
        "labels": [],
        "datasets": []
    }
    ticker_prices = defaultdict(list)
    all_dates = set()

    for holding in holdings:
        trades = Trade.objects.filter(user=request.user, ticker=holding.ticker).order_by('timestamp')
        for trade in trades:
            date_str = trade.timestamp.strftime('%Y-%m-%d')
            all_dates.add(date_str)
            ticker_prices[holding.ticker].append({
                "date": date_str,
                "price": float(trade.price)
            })

    sorted_dates = sorted(all_dates)
    price_history_data["labels"] = sorted_dates

    for ticker, entries in ticker_prices.items():
        date_price_map = {e["date"]: e["price"] for e in entries}
        dataset = {
            "label": ticker,
            "data": []
        }
        last_price = 0
        for date in sorted_dates:
            if date in date_price_map:
                last_price = date_price_map[date]
            dataset["data"].append(last_price)
        price_history_data["datasets"].append(dataset)

    context = {
        'account': account,
        'transactions': transactions,
        'risk_profile': risk_profile,
        'recommendations': (
            RISK_RECOMMENDATIONS.get(risk_profile.investor_type, {})
            if risk_profile else {}
        ),
        'rebalance_alert': rebalance_alert,
        'stock_data': stock_data,
        'search_result': search_result,
        'trade_form': trade_form,
        'holdings': holdings,
        'labels': labels,
        'data': data,
        'gains': gains,
        'price_history_data': price_history_data,
        'asset_chart_data': asset_chart_data
    }

    return render(request, 'ledger/dashboard.html', context)




@login_required
def manual_rebalance(request):
    account = Account.objects.get(user=request.user)
    profile = RiskProfile.objects.filter(user=request.user).last()

    if not profile:
        messages.error(request, "Complete your risk profile first.")
        return redirect('dashboard')

    portfolio = ModelPortfolio.objects.filter(name__icontains=profile.investor_type).first()
    if not portfolio:
        messages.error(request, "No matching portfolio found.")
        return redirect('dashboard')

    current_allocations = []
    total_value = Decimal('0')

    for line in portfolio.lines.all():
        nav = fetch_nav(line.asset)
        if nav:
            invested_amt = (line.target_pct / Decimal('100')) * account.balance
            shares = invested_amt / Decimal(nav)
            current_val = shares * Decimal(nav)
            total_value += current_val
            current_allocations.append({
                'asset': line.asset,
                'actual_pct': round((current_val / account.balance) * 100, 2) if account.balance > 0 else 0
            })
        else:
            current_allocations.append({
                'asset': line.asset,
                'actual_pct': 0
            })

    paired_allocation = zip(portfolio.lines.all(), current_allocations)

    return render(request, 'ledger/manual_rebalance.html', {
        'paired_allocation': paired_allocation
    })


@require_POST
@login_required
def apply_manual_rebalance(request):
    account = Account.objects.get(user=request.user)
    profile = RiskProfile.objects.filter(user=request.user).last()

    if not profile:
        messages.error(request, "Complete your risk profile first.")
        return redirect('dashboard')

    portfolio = ModelPortfolio.objects.filter(name__icontains=profile.investor_type).first()
    if not portfolio:
        messages.error(request, "No matching portfolio found.")
        return redirect('dashboard')

    for line in portfolio.lines.all():
        key = f"target_{line.asset}"
        value = request.POST.get(key)
        try:
            if value:
                value = value.replace(',', '.')
                line.target_pct = round(Decimal(value), 2)
                line.save()
        except Exception:
            messages.error(request, f"Invalid input for {line.asset}")

    messages.success(request, "Manual changes saved.")
    return redirect('dashboard')




@login_required
def trade(request):
    account = Account.objects.get(user=request.user)
    form = TradeForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        trade_type = form.cleaned_data['trade_type']
        ticker = form.cleaned_data['ticker'].upper()
        qty = form.cleaned_data['quantity']
        raw_price = fetch_nav(ticker)

        if raw_price is None:
            trade_error = f"Could not fetch price for {ticker}"
            return render_dashboard_with_error(request, form, trade_error)

        price = Decimal(str(raw_price))
        total = qty * price

        if trade_type == 'BUY':
            if account.balance < total:
                trade_error = "Insufficient balance to complete the trade."
                return render_dashboard_with_error(request, form, trade_error)
            holding = Holding.objects.filter(user=request.user, ticker=ticker).first()
            if holding and holding.quantity > 0:
                new_total_qty = holding.quantity + qty
                holding.avg_price = (
                    ((holding.avg_price * holding.quantity) + (price * qty)) / new_total_qty
                )
                holding.quantity = new_total_qty
            else:
                holding = Holding(
                    user=request.user,
                    ticker=ticker,
                    quantity=qty,
                    avg_price=price
                )
            holding.save()
            account.balance -= total
            account.save()

            Transaction.objects.create(
                account=account,
                transaction_type=Transaction.DEBIT,
                amount=total,
                description=f"BUY: {qty} {ticker} at ${price}"
            )

        elif trade_type == 'SELL':
            try:
                holding = Holding.objects.get(user=request.user, ticker=ticker)
                if holding.quantity < qty:
                    trade_error = "Not enough shares to sell."
                    return render_dashboard_with_error(request, form, trade_error)
                holding.quantity -= qty
                if holding.quantity == 0:
                    holding.delete()
                else:
                    holding.save()
                account.balance += total
                account.save()

                Transaction.objects.create(
                    account=account,
                    transaction_type=Transaction.CREDIT,
                    amount=total,
                    description=f"SELL: {qty} {ticker} at ${price}"
                )
            except Holding.DoesNotExist:
                trade_error = "No holdings found for this stock."
                return render_dashboard_with_error(request, form, trade_error)

        Trade.objects.create(
            user=request.user,
            trade_type=trade_type,
            ticker=ticker,
            quantity=qty,
            price=price
        )

        messages.success(request, f"{trade_type} order executed for {qty} shares of {ticker} at ${price}")
        return redirect('dashboard')

    elif request.method == 'POST':
        trade_error = "There was an error with your trade form."
        return render_dashboard_with_error(request, form, trade_error)

    return redirect('dashboard')


def render_dashboard_with_error(request, form, trade_error):
    account, _ = Account.objects.get_or_create(user=request.user, defaults={'balance': Decimal('0.00')})
    transactions = account.transactions.order_by('-timestamp')[:4]
    risk_profile = RiskProfile.objects.filter(user=request.user).order_by('-created_at').first()
    latest_doc = KycDocument.objects.filter(user=request.user).order_by('-uploaded_at').first()

    search_result = None
    if request.GET.get('search'):
        user_ticker = request.GET['search'].upper()
        try:
            stock = yf.Ticker(user_ticker)
            price = stock.history(period='1d').tail(1)['Close'].iloc[0]
            search_result = {'symbol': user_ticker, 'price': round(price, 2)}
        except Exception:
            search_result = {'error': f"Could not find data for '{user_ticker}'."}

    default_tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
    stock_data = []
    for ticker in default_tickers:
        try:
            stock = yf.Ticker(ticker)
            price = stock.history(period='1d').tail(1)['Close'].iloc[0]
            stock_data.append({'symbol': ticker, 'price': round(price, 2)})
        except Exception:
            stock_data.append({'symbol': ticker, 'price': 'N/A'})

    holdings = Holding.objects.filter(user=request.user)
    labels = []
    data = []
    gains = []
    asset_chart_data = []

    for h in holdings:
        nav = fetch_nav(h.ticker)
        if nav:
            current_value = h.quantity * Decimal(nav)
            cost_basis = h.quantity * h.avg_price
            gain = current_value - cost_basis
            gains.append({'ticker': h.ticker, 'gain': round(gain, 2)})
            labels.append(h.ticker)
            data.append(round(float(current_value), 2))
            asset_chart_data.append({
                'ticker': h.ticker,
                'quantity': float(h.quantity),
                'nav': float(nav),
                'value': float(current_value)
            })
        else:
            labels.append(h.ticker)
            data.append(0)
            gains.append({'ticker': h.ticker, 'gain': Decimal('0.00')})
            asset_chart_data.append({
                'ticker': h.ticker,
                'quantity': float(h.quantity),
                'nav': 0,
                'value': 0
            })

    price_history_data = {
        "labels": [],
        "datasets": []
    }
    ticker_prices = defaultdict(list)
    all_dates = set()

    for holding in holdings:
        trades = Trade.objects.filter(user=request.user, ticker=holding.ticker).order_by('timestamp')
        for trade in trades:
            date_str = trade.timestamp.strftime('%Y-%m-%d')
            all_dates.add(date_str)
            ticker_prices[holding.ticker].append({
                "date": date_str,
                "price": float(trade.price)
            })

    sorted_dates = sorted(all_dates)
    price_history_data["labels"] = sorted_dates

    for ticker, entries in ticker_prices.items():
        date_price_map = {e["date"]: e["price"] for e in entries}
        dataset = {
            "label": ticker,
            "data": []
        }
        last_price = 0
        for date in sorted_dates:
            if date in date_price_map:
                last_price = date_price_map[date]
            dataset["data"].append(last_price)
        price_history_data["datasets"].append(dataset)

    rebalance_alert = None
    if risk_profile and account.balance > 0:
        portfolio = ModelPortfolio.objects.filter(name__icontains=risk_profile.investor_type).first()
        if portfolio:
            total_value = Decimal('0')
            current_values = {}
            for line in portfolio.lines.all():
                nav = fetch_nav(line.asset)
                if nav is None:
                    continue
                invested_amt = (line.target_pct / Decimal('100')) * account.balance
                shares = invested_amt / Decimal(nav)
                current_val = shares * Decimal(nav)
                current_values[line.asset] = current_val
                total_value += current_val
            if total_value > 0:
                for line in portfolio.lines.all():
                    if line.asset in current_values:
                        actual_val = current_values[line.asset]
                        actual_pct = (actual_val / total_value) * Decimal('100')
                        drift = abs(actual_pct - line.target_pct)
                        if drift >= 5:
                            rebalance_alert = {
                                'portfolio': portfolio.name,
                                'drift': round(drift, 2)
                            }
                            break

    context = {
        'account': account,
        'transactions': transactions,
        'risk_profile': risk_profile,
        'recommendations': (
            RISK_RECOMMENDATIONS.get(risk_profile.investor_type, {})
            if risk_profile else {}
        ),
        'rebalance_alert': rebalance_alert,
        'stock_data': stock_data,
        'search_result': search_result,
        'trade_form': form,
        'trade_error': trade_error,
        'holdings': holdings,
        'labels': labels,
        'data': data,
        'gains': gains,
        'price_history_data': price_history_data,
        'asset_chart_data': asset_chart_data
    }

    return render(request, 'ledger/dashboard.html', context)





@login_required
def inbox_chat(request, user_id):
    User = get_user_model()
    selected_user = get_object_or_404(User, id=user_id)

    if not selected_user.is_staff:
        raise PermissionDenied("You are only allowed to message admins.")

    if request.user == selected_user:
        raise PermissionDenied("You cannot message yourself.")

    all_admins = User.objects.filter(is_staff=True)

    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            Message.objects.create(sender=request.user, receiver=selected_user, content=content)
            return redirect('inbox_chat', user_id=selected_user.id)

    messages_qs = Message.objects.filter(
        Q(sender=request.user, receiver=selected_user) |
        Q(sender=selected_user, receiver=request.user)
    ).order_by('timestamp')

    return render(request, 'ledger/chat.html', {
        'all_admins': all_admins,
        'selected_admin': selected_user,
        'messages': messages_qs,
    })










@login_required
def kyc_upload(request):
    latest_doc = KycDocument.objects.filter(user=request.user).order_by('-uploaded_at').first()
    if latest_doc:
        if latest_doc.status == KycDocument.PENDING:
            messages.info(request, "Your previous document is still pending review by a moderator.")
            return redirect('kyc_status')
        elif latest_doc.status == KycDocument.APPROVED:
            messages.success(request, "Your KYC has been approved. No further uploads are needed.")
            return redirect('kyc_status')
        elif latest_doc.status == KycDocument.REJECTED:
            messages.warning(request, "Your previous document was denied. Please upload again.")

    if request.method == 'POST':
        form = KycForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.user = request.user
            doc.status = KycDocument.PENDING
            doc.save()
            messages.success(request, "Document uploaded successfully. Awaiting review.")
            return redirect('kyc_status')
    else:
        form = KycForm()

    return render(request, 'ledger/kyc_upload.html', {'form': form})





@login_required
def kyc_status(request):
    docs = KycDocument.objects.filter(user=request.user).order_by('-uploaded_at')
    return render(request, 'ledger/kyc_status.html', {'docs': docs})
class StatementPDFView(View):
    def get(self, request):
        account = Account.objects.get(user=request.user)
        transactions = account.transactions.order_by('-timestamp')
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="statement.pdf"'
        p = canvas.Canvas(response)
        p.drawString(100, 800, f"Statement for {request.user.username}")
        y = 750
        for tx in transactions:
            p.drawString(
                100, y,
                f"{tx.timestamp.strftime('%Y-%m-%d')} - "
                f"{tx.get_transaction_type_display()} - "
                f"${tx.amount} - {tx.description}"
            )
            y -= 20
            if y < 50:
                p.showPage()
                y = 800
        p.save()
        return response








def create_checkout_session(request):
    if request.method != 'POST':
        return redirect('dashboard')

    amt = request.POST.get('amount')
    try:
        dollars = float(amt)
        if dollars <= 0 or dollars > 100000:
            raise ValueError("Invalid amount")
    except (TypeError, ValueError):
        messages.error(request, "Deposit failed: maximum allowed is $100,000.")
        return redirect('dashboard')

    cents = int(dollars * 100)
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'usd',
                'product_data': {'name': f'Account Deposit - ${dollars:.2f}'},
                'unit_amount': cents,
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=request.build_absolute_uri('/success/') + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=request.build_absolute_uri('/cancelled/'),
    )
    return redirect(session.url, code=303)







def payment_success(request):
    session_id = request.GET.get('session_id')
    if not session_id:
        return redirect('dashboard')
    session = stripe.checkout.Session.retrieve(session_id)
    dollars = session.amount_total / 100
    account = Account.objects.get(user=request.user)
    account.balance += Decimal(str(dollars))
    account.save()
    Transaction.objects.create(
        account=account,
        transaction_type=Transaction.CREDIT,
        amount=Decimal(str(dollars)),
        description=f"Stripe deposit (${dollars:.2f})"
    )
    return render(request, 'ledger/success.html')








def payment_cancelled(request):
    return render(request, 'ledger/cancelled.html')






@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        raise PermissionDenied
    User      = get_user_model()
    total_users        = User.objects.count()
    accounts_count     = Account.objects.count()
    transactions_count = Transaction.objects.count()
    pending_kyc_count  = KycDocument.objects.filter(status=KycDocument.PENDING).count()


    recent_transactions = (
        Transaction.objects
        .select_related('account__user')
        .order_by('-timestamp')[:5]
    )

    return render(request, 'admin/dashboard.html', {
        'total_users': total_users,
        'accounts_count': accounts_count,
        'transactions_count': transactions_count,
        'pending_kyc_count': pending_kyc_count,
        'recent_transactions': recent_transactions,
    })


#ADMIN STUFFS


# KYC Management 




@login_required
def kyc_list(request):
    if not request.user.is_staff:
        raise PermissionDenied
    docs = KycDocument.objects.order_by('-uploaded_at')
    return render(request, 'admin/kyc_list.html', {'docs': docs})




@login_required
def kyc_edit(request, pk):
    if not request.user.is_staff:
        raise PermissionDenied
    doc = get_object_or_404(KycDocument, pk=pk)
    form = AdminKycForm(request.POST or None, instance=doc)
    if form.is_valid():
        form.save()
        return redirect('kyc_list')
    return render(request, 'admin/kyc_form.html', {'form': form, 'doc': doc})




@login_required
def message_admin_redirect(request):
    admin_user = get_user_model().objects.filter(is_staff=True).first()
    if not admin_user:
        raise PermissionDenied("No admin is available.")
    return redirect('inbox_chat', user_id=admin_user.id)





@login_required
def admin_inbox(request):
    if not request.user.is_staff:
        raise PermissionDenied

    User = get_user_model()
    all_users = User.objects.exclude(is_staff=True)

    if request.method == 'POST':
        content = request.POST.get('content')
        receiver_id = request.POST.get('receiver')
        receiver = get_object_or_404(User, pk=receiver_id, is_staff=False)
        if content:
            Message.objects.create(sender=request.user, receiver=receiver, content=content)
            return redirect('admin_inbox')

    grouped_conversations = []
    for user in all_users:
        convo = Message.objects.filter(
            (Q(sender=user, receiver=request.user) | Q(sender=request.user, receiver=user))
        ).order_by('timestamp')
        if convo.exists():
            grouped_conversations.append({
                'user': user,
                'messages': convo
            })

    return render(request, 'admin/inbox.html', {
        'users': all_users,
        'grouped_conversations': grouped_conversations
    })




@login_required
def admin_chat(request, user_id):
    if not request.user.is_staff:
        raise PermissionDenied

    User = get_user_model()
    selected_user = get_object_or_404(User, id=user_id, is_staff=False)

    all_users = User.objects.filter(is_staff=False)

    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            Message.objects.create(sender=request.user, receiver=selected_user, content=content)
            return redirect('admin_chat', user_id=selected_user.id)

    messages_qs = Message.objects.filter(
        Q(sender=request.user, receiver=selected_user) |
        Q(sender=selected_user, receiver=request.user)
    ).order_by('timestamp')

    return render(request, 'admin/chat.html', {
        'all_users': all_users,
        'selected_user': selected_user,
        'messages': messages_qs,
    })





#Account Management
@login_required
def account_list(request):
    if not request.user.is_staff:
        raise PermissionDenied
    accounts = Account.objects.select_related('user').all()
    return render(request, 'admin/account_list.html', {'accounts': accounts})




@login_required
def account_edit(request, pk):
    if not request.user.is_staff:
        raise PermissionDenied
    acct = get_object_or_404(Account, pk=pk)
    form = AdminAccountForm(request.POST or None, instance=acct)
    if form.is_valid():
        form.save()
        return redirect('account_list')
    return render(request, 'admin/account_form.html', {'form': form, 'account': acct})


User = get_user_model()






@login_required
def user_list(request):
    if not request.user.is_staff:
        raise PermissionDenied
    User = get_user_model()
    users = User.objects.all()
    return render(request, 'admin/user_list.html', {'users': users})






@login_required
def user_edit(request, pk):
    if not request.user.is_staff:
        raise PermissionDenied
    User = get_user_model()
    user = get_object_or_404(User, pk=pk)
    form = AdminUserForm(request.POST or None, instance=user)
    if form.is_valid():
        form.save()
        return redirect('user_list')
    return render(request, 'admin/user_form.html', {'form': form, 'user': user})






@login_required
def user_delete(request, pk):
    if not request.user.is_staff:
        raise PermissionDenied
    User = get_user_model()
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        user.delete()
        return redirect('user_list')
    return render(request, 'admin/user_confirm_delete.html', {'user': user})






def custom_permission_denied(request, exception=None):
    return render(request, '403.html', status=403)







@login_required
def transaction_list(request):
    account = Account.objects.get(user=request.user)
    transactions = account.transactions.order_by('-timestamp')
    return render(request, 'ledger/transactions.html', {
        'transactions': transactions
    })


# Rebalancing 





@require_POST
@login_required
def enable_auto_rebalance(request):
    account = Account.objects.get(user=request.user)
    account.auto_rebalance_enabled = True
    account.save()

    #rebalancing logic
    from portfolios.models import ModelPortfolio
    from portfolios.utils import fetch_nav

    profile = RiskProfile.objects.filter(user=request.user).last()
    if not profile:
        return redirect('dashboard')

    portfolio = ModelPortfolio.objects.filter(name__icontains=profile.investor_type).first()
    if not portfolio:
        return redirect('dashboard')

    total_value = Decimal('0')
    asset_values = {}

    for line in portfolio.lines.all():
        nav = fetch_nav(line.asset)
        if nav is None:
            continue
        invested_amt = (line.target_pct / Decimal('100')) * account.balance
        shares = invested_amt / Decimal(nav)
        current_val = shares * Decimal(nav)
        asset_values[line.asset] = current_val
        total_value += current_val

    for line in portfolio.lines.all():
        if line.asset in asset_values:
            actual_val = asset_values[line.asset]
            new_pct = (actual_val / total_value) * Decimal('100')
            line.target_pct = round(new_pct, 2)
            line.save()

    messages.success(request, "Auto-rebalancing applied: your portfolio has been realigned.")
    return redirect('dashboard')







@require_POST
@login_required
def disable_auto_rebalance(request):
    account = Account.objects.get(user=request.user)
    account.auto_rebalance_enabled = False
    account.save()
    return redirect('portfolio_list')








@login_required
def inbox(request):
    if request.user.is_staff:
        raise PermissionDenied

    User = get_user_model()
    admins = User.objects.filter(is_staff=True)

    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            for admin in admins:
                Message.objects.create(sender=request.user, receiver=admin, content=content)
            return redirect('inbox')

    grouped_conversations = []
    for admin in admins:
        convo = Message.objects.filter(
            Q(sender=request.user, receiver=admin) |
            Q(sender=admin, receiver=request.user)
        ).order_by('timestamp')
        if convo.exists():
            grouped_conversations.append({
                'admin': admin,
                'messages': convo
            })

    return render(request, 'ledger/inbox.html', {
        'grouped_conversations': grouped_conversations
    })








@login_required
def send_message(request):
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            admin_users = get_user_model().objects.filter(is_staff=True)
            for admin in admin_users:
                Message.objects.create(
                    sender=request.user,
                    receiver=admin,
                    content=content
                )
            return redirect('inbox')
    return redirect('inbox')

