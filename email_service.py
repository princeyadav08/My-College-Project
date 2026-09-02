import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random

# ==========================================
# GMAIL CONFIGURATION (Yahan apni details dalein)
# ==========================================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "yadavprince773899@gmail.com"        # <-- Apna Gmail yahan likhein
SENDER_PASSWORD = "zkxa sggk xyci rfdd"     # <-- Jo 16-digit App Password copy kiya hai wo yahan paste karein

def send_real_otp(receiver_email):
    """Real 6-digit OTP generate karke user ke email par bhejta hai"""
    otp = str(random.randint(100000, 999999))
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Your Verification OTP: {otp}"
    msg["From"] = f"Office Support Desk <{SENDER_EMAIL}>"
    msg["To"] = receiver_email

    html_content = f"""
    <div style="font-family: Arial, sans-serif; background-color: #0f172a; color: #ffffff; padding: 25px; border-radius: 12px; max-width: 480px; margin: auto;">
        <h2 style="color: #38bdf8; text-align: center;">Office Verification Portal</h2>
        <p style="color: #cbd5e1; font-size: 14px;">Aapka one-time verification password neeche diya gaya hai:</p>
        <div style="text-align: center; margin: 20px 0;">
            <span style="font-size: 30px; font-weight: bold; letter-spacing: 5px; color: #38bdf8; background: rgba(56, 189, 248, 0.1); padding: 8px 20px; border-radius: 8px; border: 1px dashed #38bdf8;">
                {otp}
            </span>
        </div>
        <p style="font-size: 12px; color: #94a3b8; text-align: center;">Yeh OTP agle 10 minute ke liye valid hai.</p>
    </div>
    """
    msg.attach(MIMEText(html_content, "html"))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
        server.quit()
        return True, otp
    except Exception as e:
        print(f"SMTP Error: {e}")
        return False, None


def send_inquiry_confirmation(receiver_email, user_name):
    """Inquiry lodge hote hi user ko confirmation acknowledgment bhejta hai"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Inquiry Received - Office Support Desk"
    msg["From"] = f"Office Support Desk <{SENDER_EMAIL}>"
    msg["To"] = receiver_email

    html_content = f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; color: #1e293b;">
        <h3 style="color: #0284c7;">Namaste {user_name},</h3>
        <p>Aapki inquiry hamare office dashboard par successfully receive ho chuki hai.</p>
        <p>Hamari team jaldi hi aapse phone ya email ke through sampark karegi.</p>
        <br>
        <p style="color: #64748b; font-size: 13px;">Regards,<br><b>Office Management Team</b></p>
    </div>
    """
    msg.attach(MIMEText(html_content, "html"))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"SMTP Error: {e}")
        return False
    