# Arona Fintech – Secure Banking & Investment


Fully developped and deployed Application Website: https://securefund.aronagaye.me/



## A modern full stack fintech web app that combines secure banking, smart investing, Portfolio Management, KYC onboarding, and a full ledger system. Designed to make digital banking and investing smarter, faster, and more secure.

Features Overview

 KYC (Know Your Customer) & Compliance
- Secure document upload system
- Admin-side approval/rejection workflow
- Document versioning & status tracking

Secure login with 2FA (email-based OTP)

User profiling with automatic portfolio recommendation

Manual and automatic rebalancing tools

Stripe-powered deposit system with confirmation flow

Complete transaction history with downloadable PDF statements

Simulated trading system with portfolio tracking

Real-time stock data from Yahoo Finance

Role-based admin dashboard with account/user/KYC control

Chat system between users and administrators

Cloud Storage Via AWS

---

## Issues this project Tackles

### 1. Traditional Banking Limitations
- Problem: Outdated interfaces and disconnected financial data.
- My Solution: Responsive UI with modern dashboard and real-time stock insights.

### 2. Security & Compliance Gaps
- Problem: Weak authentication and no identity verification.
- My Solution: Email-based 2FA,  document review, and admin role separation.

### 3. Lack of Financial Intelligence
- Problem: No personalized investment options or risk analysis.
- My Solution: Investor profiling, auto-matched portfolios, and drift alerts.

### 4. Transaction Inaccuracies
- Problem: Poor balance tracking and missing audit trails.
- My Solution: Double-entry ledger system with full transaction history.

### 5. Disconnected Customer Support
- Problem: No internal messaging or conversation tracking.
- My Solution: Built-in chat between users and admins with history tracking.

### 6. Payment Integration Challenges
- Problem: Insecure or manual payment handling.
- My Solution: Stripe Checkout with proper redirection and confirmation views.

### 7. Missing Financial Education Tools
- Problem: Users can't learn investing through the app.
- My Solution: Simulated trading, asset visualization, and portfolio tracking.

### 8. Operational Inefficiencies for Admins
- Problem: No centralized admin control.
- My Solution: Admin dashboard with account control, user messaging, and  tools.

---

## APIs and External Services Used

| Purpose                         | Tool / API                   | Description                                                             |
| ------------------------------- | ---------------------------- | ----------------------------------------------------------------------- |
| Stock Prices                    | `yfinance`                   | Real-time and historical data from Yahoo Finance                        |
| Payments                        | `Stripe Checkout`            | PCI-compliant card payments and redirection flow                        |
| 2FA via Email                   | `Django Email + SMTP`        | Sends one-time passwords (OTP) for secure login via email               |
| PDF Statements                  | `ReportLab`                  | Generates downloadable PDF transaction statements                       |
| Data Visualizations             | `Chart.js`                   | Displays asset allocation and stock trend charts                        |
| **KYC File Storage (Optional)** | **Amazon Web Services (S3)** | Optional storage for KYC document uploads — app runs fully without this |


---
## Tech Stack
Backend: Python, Django

Frontend: HTML, CSS, JavaScript, Bootstrap

Database: SQLite (easily migratable to PostgreSQL)
Database: Currenyly migratinb to PostgreSQL

Cloud & Storage: Amazon Web Services (AWS)

## Run the app fully deployed here
If you do not want to run it locally you can run it directly on my personal website (App will need around 30 seconds to start running):
```bash
https://securefund.aronagaye.me/
```
## How to Run Locally

To run this application locally you need to configure environment variables in the .env file at the root of the project 

| Variable Group         | Where to Get It                                                                   | Helpful Links                                                                                     |
| ---------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `DJANGO_SECRET_KEY`    | Generate securely                                                                 | [djecrety.ir](https://djecrety.ir/)                                                               |
| Stripe Keys            | From your Stripe Dashboard                                                        | [Stripe API Keys](https://dashboard.stripe.com/apikeys)                                           |
| Gmail App Password     | Required for sending OTPs via Gmail                                               | [Google App Password Guide](https://support.google.com/accounts/answer/185833)                    |
| Alpha Vantage API Key  | For stock/financial data (used alongside Yahoo Finance)                           | [Get API Key](https://www.alphavantage.co/support/#api-key)                                       |
| **AWS S3 Credentials** | **Only needed if you want to store KYC files on AWS** – app works fine without it | [AWS IAM Guide](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html) |


### 1. Clone the Repository

```bash
git clone https://github.com/GAYEA78/Secure-Fund.git
cd Secure-Fund
```

### 2. Set Up Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate   # On Windows
source venv/bin/activate  # On macOS/Linux
```
### 3. .env File configuration
Edit the .env file in your preferred editor.

```bash
vim .env  #Replace each placeholder value (e.g., your_stripe_secret_key) with your actual credentials.
```
Save and close the file.


### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Apply Migrations

```bash
python manage.py migrate
```

### 6. Create a Superuser (Admin Account)

```bash
python manage.py createsuperuser
```

### 7. Run the Server
```bash
python manage.py runserver
```
