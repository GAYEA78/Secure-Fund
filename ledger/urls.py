from django.urls import path, include
from . import views
from . import performance

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('performance/', performance.performance_data, name='performance_data'),
    path('signup/', views.signup, name='signup'),
    path('pdf-statement/', views.StatementPDFView.as_view(), name='pdf_statement'),
    path('create-checkout-session/', views.create_checkout_session, name='create_checkout_session'),
    path('success/', views.payment_success, name='payment_success'),
    path('cancelled/', views.payment_cancelled, name='payment_cancelled'),
    path('kyc/upload/', views.kyc_upload, name='kyc_upload'),
    path('kyc/status/', views.kyc_status, name='kyc_status'),
    path('trade/', views.trade, name='trade'),
    path('inbox/', views.inbox, name='inbox'),
    path('send-message/', views.send_message, name='send_message'),


    # Staff/Admin routes
    path('staff/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('staff/kyc/', views.kyc_list, name='kyc_list'),
    path('staff/kyc/<int:pk>/edit/', views.kyc_edit, name='kyc_edit'),
    path('staff/accounts/', views.account_list, name='account_list'),
    path('staff/accounts/<int:pk>/edit/', views.account_edit, name='account_edit'),
    path('staff/users/', views.user_list, name='user_list'),
    path('staff/users/<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('staff/users/<int:pk>/delete/', views.user_delete, name='user_delete'),
    path('staff/inbox/', views.admin_inbox, name='admin_inbox'),
    path('staff/inbox/chat/<int:user_id>/', views.admin_chat, name='admin_chat'),
    path('message-admin/', views.message_admin_redirect, name='message_admin_redirect'),


    # User routes
    path('risk-profile/', views.risk_profile, name='risk_profile'),
    path('transactions/', views.transaction_list, name='transactions'),
    path('inbox/chat/<int:user_id>/', views.inbox_chat, name='inbox_chat'),

    # Portfolios routes
    path('portfolios/', include('portfolios.urls')),

    # Auto rebalance
    path('rebalance/auto/', views.enable_auto_rebalance, name='enable_auto_rebalance'),

    # Rebalancing
    path('rebalance/manual/', views.manual_rebalance, name='manual_rebalance'),
    path('rebalance/manual/apply/', views.apply_manual_rebalance, name='apply_manual_rebalance'),

]