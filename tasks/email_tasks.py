from celery_app import celery_app
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

# Email configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@funnelaudit.ai")

@celery_app.task
def send_audit_completion_email(user_email: str, audit_id: str):
    """Send audit completion notification email"""
    try:
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Your Funnel Audit is Complete! 🎉"
        msg["From"] = FROM_EMAIL
        msg["To"] = user_email
        
        # HTML email content
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Audit Complete</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .button {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .stats {{ background: white; padding: 20px; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Your Audit is Complete!</h1>
                    <p>We've found some interesting insights about your website</p>
                </div>
                
                <div class="content">
                    <h2>Your Revenue Leak Report is Ready</h2>
                    
                    <p>Great news! We've completed a comprehensive analysis of your website and identified several opportunities to boost your conversions.</p>
                    
                    <div class="stats">
                        <h3>Quick Preview:</h3>
                        <ul>
                            <li>✅ Full website crawl completed</li>
                            <li>🔍 Interactive elements tested</li>
                            <li>📊 Performance analysis done</li>
                            <li>💰 Revenue impact calculated</li>
                        </ul>
                    </div>
                    
                    <p>Click below to view your detailed report with actionable recommendations:</p>
                    
                    <a href="https://app.funnelaudit.ai/reports/{audit_id}" class="button">
                        View Your Report
                    </a>
                    
                    <p><strong>What's Next?</strong></p>
                    <ol>
                        <li>Review your audit results</li>
                        <li>Prioritize the critical issues</li>
                        <li>Implement our recommendations</li>
                        <li>Watch your conversions improve!</li>
                    </ol>
                    
                    <p>Need help implementing the fixes? Reply to this email and we'll connect you with our optimization experts.</p>
                </div>
                
                <div class="footer">
                    <p>© 2024 Funnel Audit AI. All rights reserved.</p>
                    <p>You received this email because you requested an audit on our platform.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text version
        text_content = f"""
        Your Funnel Audit is Complete!
        
        Great news! We've completed a comprehensive analysis of your website and identified several opportunities to boost your conversions.
        
        Quick Preview:
        - Full website crawl completed
        - Interactive elements tested  
        - Performance analysis done
        - Revenue impact calculated
        
        View your detailed report: https://app.funnelaudit.ai/reports/{audit_id}
        
        What's Next?
        1. Review your audit results
        2. Prioritize the critical issues
        3. Implement our recommendations
        4. Watch your conversions improve!
        
        Need help? Reply to this email and we'll connect you with our optimization experts.
        
        © 2024 Funnel Audit AI
        """
        
        # Attach parts
        part1 = MIMEText(text_content, "plain")
        part2 = MIMEText(html_content, "html")
        
        msg.attach(part1)
        msg.attach(part2)
        
        # Send email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Audit completion email sent to {user_email}")
        
    except Exception as e:
        logger.error(f"Failed to send email to {user_email}: {str(e)}")
        raise e

@celery_app.task
def send_audit_failed_email(user_email: str, audit_id: str, error_message: str):
    """Send audit failure notification email"""
    try:
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Audit Issue - We're Looking Into It"
        msg["From"] = FROM_EMAIL
        msg["To"] = user_email
        
        # HTML content
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Audit Issue</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #f44336; color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .button {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>⚠️ Audit Issue</h1>
                    <p>We encountered an issue with your website audit</p>
                </div>
                
                <div class="content">
                    <h2>Don't Worry - We're On It!</h2>
                    
                    <p>We encountered a technical issue while analyzing your website. Our team has been automatically notified and we're working to resolve it.</p>
                    
                    <p><strong>What happens next?</strong></p>
                    <ul>
                        <li>We'll automatically retry your audit</li>
                        <li>Our team will investigate the issue</li>
                        <li>You'll receive your results as soon as possible</li>
                    </ul>
                    
                    <p>If you continue to experience issues, please don't hesitate to contact our support team.</p>
                    
                    <a href="mailto:support@funnelaudit.ai" class="button">
                        Contact Support
                    </a>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text version
        text_content = f"""
        Audit Issue - We're Looking Into It
        
        We encountered a technical issue while analyzing your website. Our team has been automatically notified and we're working to resolve it.
        
        What happens next?
        - We'll automatically retry your audit
        - Our team will investigate the issue  
        - You'll receive your results as soon as possible
        
        If you continue to experience issues, please contact: support@funnelaudit.ai
        
        © 2024 Funnel Audit AI
        """
        
        # Attach parts
        part1 = MIMEText(text_content, "plain")
        part2 = MIMEText(html_content, "html")
        
        msg.attach(part1)
        msg.attach(part2)
        
        # Send email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Audit failure email sent to {user_email}")
        
    except Exception as e:
        logger.error(f"Failed to send failure email to {user_email}: {str(e)}")

@celery_app.task
def send_welcome_email(user_email: str):
    """Send welcome email to new users"""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Welcome to Funnel Audit AI! 🚀"
        msg["From"] = FROM_EMAIL
        msg["To"] = user_email
        
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Welcome</title>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
                .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
                .button { display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚀 Welcome to Funnel Audit AI!</h1>
                    <p>Start finding revenue leaks in your marketing funnels</p>
                </div>
                
                <div class="content">
                    <h2>Ready to Boost Your Conversions?</h2>
                    
                    <p>Thanks for joining Funnel Audit AI! You now have access to powerful tools that can help you identify and fix conversion killers in your marketing funnels.</p>
                    
                    <p><strong>What you can do:</strong></p>
                    <ul>
                        <li>🔍 Run comprehensive website audits</li>
                        <li>📊 Get detailed performance reports</li>
                        <li>💰 See estimated revenue impact</li>
                        <li>🛠️ Receive actionable recommendations</li>
                    </ul>
                    
                    <a href="https://app.funnelaudit.ai/dashboard" class="button">
                        Start Your First Audit
                    </a>
                    
                    <p>Questions? Just reply to this email - we're here to help!</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = """
        Welcome to Funnel Audit AI!
        
        Thanks for joining! You now have access to powerful tools that can help you identify and fix conversion killers in your marketing funnels.
        
        What you can do:
        - Run comprehensive website audits
        - Get detailed performance reports  
        - See estimated revenue impact
        - Receive actionable recommendations
        
        Start your first audit: https://app.funnelaudit.ai/dashboard
        
        Questions? Just reply to this email - we're here to help!
        """
        
        part1 = MIMEText(text_content, "plain")
        part2 = MIMEText(html_content, "html")
        
        msg.attach(part1)
        msg.attach(part2)
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Welcome email sent to {user_email}")
        
    except Exception as e:
        logger.error(f"Failed to send welcome email to {user_email}: {str(e)}")