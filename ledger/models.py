from django.db import models
from django.contrib.auth.models import User
import random
from django.utils import timezone
from django.conf import settings

class OtpCode(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return (timezone.now() - self.created_at).total_seconds() > 300  # 5 min
    @staticmethod
    def generate_for(user):
        code = f"{random.randint(0, 999999):06d}"
        otp = OtpCode.objects.create(user=user, code=code)
        return otp

class KycDocument(models.Model):
    PENDING = 'P'; APPROVED = 'A'; REJECTED = 'R'
    STATUS_CHOICES = [(PENDING,'Pending'),(APPROVED,'Approved'),(REJECTED,'Rejected')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    document = models.FileField(upload_to='kyc/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default=PENDING)

    def __str__(self):
        return f"KYC for {self.user.username}: {self.get_status_display()}"


class Account(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    auto_rebalance_enabled = models.BooleanField(default=False)
    two_factor_enabled = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username}'s Account"


class Transaction(models.Model):
    CREDIT = 'CR'
    DEBIT = 'DB'
    TRANSACTION_TYPES = [
        (CREDIT, 'Credit'),
        (DEBIT, 'Debit'),
    ]
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=2, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_transaction_type_display()} of {self.amount} on {self.timestamp.strftime('%Y-%m-%d')}"


class RiskProfile(models.Model):
    EXPERIENCE_CHOICES = [
        ('none',      'No experience'),
        ('some',      'Some experience'),
        ('experienced','Experienced'),
    ]
    GOALS_CHOICES = [
        ('preservation','Capital preservation'),
        ('income',      'Steady income'),
        ('growth',      'Growth'),
    ]
    RISK_CHOICES = [
        ('low',       'Low'),
        ('moderate',  'Moderate'),
        ('high',      'High'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    experience     = models.CharField(max_length=12, choices=EXPERIENCE_CHOICES)
    goals          = models.CharField(max_length=12, choices=GOALS_CHOICES)
    time_horizon   = models.IntegerField(help_text="Years you plan to invest")
    risk_tolerance = models.CharField(max_length=8, choices=RISK_CHOICES)

    investor_type = models.CharField(
        max_length=12,
        blank=True,
        help_text="Aggressive / Growth / Income"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}: {self.investor_type}"


def determine_investor_type(experience, goals, time_horizon, risk_tolerance):
    if risk_tolerance == 'high' and time_horizon >= 10:
        return 'Aggressive'
    if risk_tolerance == 'moderate' and time_horizon >= 5:
        return 'Growth'
    return 'Income'



class Holding(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ticker = models.CharField(max_length=10)
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    avg_price = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.user.username} - {self.ticker}: {self.quantity} shares"


class Trade(models.Model):
    BUY = 'BUY'
    SELL = 'SELL'
    TRADE_TYPES = [(BUY, 'Buy'), (SELL, 'Sell')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    trade_type = models.CharField(max_length=4, choices=TRADE_TYPES)
    ticker = models.CharField(max_length=10)
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.trade_type} {self.quantity} of {self.ticker} at ${self.price}"



class Message(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='sent_messages', on_delete=models.CASCADE)
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='received_messages', on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

