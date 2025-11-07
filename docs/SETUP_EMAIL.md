# Email Notification Setup Guide

Quick guide to configure email notifications for the Job-ETL pipeline.

## Gmail Configuration

### Step 1: Get Gmail App Password

If you haven't already, create a Gmail App Password:

1. Go to your Google Account: https://myaccount.google.com/
2. Security → 2-Step Verification (must be enabled)
3. App passwords → Select app: "Mail" → Select device: "Other" → Enter "Job-ETL"
4. Copy the 16-character password (format: `xxxxxxxxxxxxxxxx`)

**Note**: You cannot use your regular Gmail password. Gmail requires App Passwords for SMTP.

### Step 2: Configure Environment Variables

Add these to your `.env` file (or set as environment variables):

```bash
# Gmail SMTP Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_FROM=your-email@gmail.com
SMTP_PASSWORD=your-app-password-here
NOTIFY_TO=recipient@example.com
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

### Step 3: Alternative - Use Docker Secret (Recommended for Production)

For better security, store the password in a Docker secret file:

```bash
# Create the directory if it doesn't exist
mkdir -p secrets/notifications

# Create the secret file (replace with your actual App Password)
echo "your-app-password-here" > secrets/notifications/smtp_password.txt

# Set permissions (Linux/Mac)
chmod 600 secrets/notifications/smtp_password.txt
```

Then in your `.env` file, **omit** `SMTP_PASSWORD`:

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_FROM=your-email@gmail.com
# SMTP_PASSWORD is read from secrets/notifications/smtp_password.txt
NOTIFY_TO=recipient@example.com
SMTP_USE_TLS=true
```

### Step 4: Test the Configuration

Test the email configuration:

```bash
# From within the Airflow container or locally
python -m services.notifier.main \
    --subject "Test Email" \
    --text "This is a test email from Job-ETL"
```

Or trigger the DAG and check if the notification email is sent.

## Multiple Recipients

To send to multiple recipients, use comma-separated emails:

```bash
NOTIFY_TO=recipient1@example.com,recipient2@example.com,recipient3@example.com
```

## Troubleshooting

### "Authentication failed" error
- Make sure you're using an **App Password**, not your regular Gmail password
- Verify 2-Step Verification is enabled on your Google account
- Check that `SMTP_USER` matches the email that generated the App Password

### "Connection refused" error
- Verify `SMTP_HOST=smtp.gmail.com` and `SMTP_PORT=587`
- Check firewall/network settings
- Try `SMTP_USE_TLS=true` (required for Gmail)

### Email not received
- Check spam folder
- Verify `NOTIFY_TO` email address is correct
- Check Airflow task logs for errors
- Ensure the DAG task `notify_daily` completed successfully

## Security Best Practices

1. **Use Docker Secrets** instead of environment variables for passwords
2. **Never commit** `.env` files or secret files to git
3. **Rotate App Passwords** periodically
4. **Use separate App Passwords** for different environments (dev/prod)

## Other Email Providers

### SendGrid
```bash
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your-sendgrid-api-key
SMTP_FROM=noreply@yourdomain.com
NOTIFY_TO=recipient@example.com
```

### Outlook/Office 365
```bash
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=your-email@outlook.com
SMTP_PASSWORD=your-password
SMTP_FROM=your-email@outlook.com
NOTIFY_TO=recipient@example.com
```

### Local Development (MailHog)
```bash
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_FROM=test@localhost
NOTIFY_TO=dev@localhost
SMTP_USE_TLS=false
# No authentication needed
```

