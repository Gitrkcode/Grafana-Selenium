import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import smtplib
import ssl
import os
import time
import hashlib
import logging
from apscheduler.schedulers.background import BackgroundScheduler

# Configure logging
logging.basicConfig(
    filename="grafana_email.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Email sender configuration
EMAIL_SENDER = "rakeshkumar.ck01@gmail.com"  # Your Cisco email address
EMAIL_PASSWORD = st.secrets("EMAIL_APP_PASSWORD")  # Store your password securely in environment variables

# Cisco SMTP configuration
SMTP_SERVER = "smtp.gmail.com"  # Replace with the correct Cisco SMTP server address
SMTP_PORT = 587  # Usually 587 for TLS

# Grafana credentials (shared across all dashboards)
GRAFANA_USERNAME = "rakekum8"
GRAFANA_PASSWORD = "Produsapass@3"


def capture_screenshot(grafana_url):
    """Capture a screenshot of a Grafana dashboard."""
    try:
        logging.info(f"Launching Chrome to capture screenshot for {grafana_url}.")
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--window-size=1920x1080")
        driver = webdriver.Chrome(options=chrome_options)

        logging.info(f"Opening Grafana URL: {grafana_url}")
        driver.get(grafana_url)
        time.sleep(3)

        try:
            # Login if required
            user_input = driver.find_element(By.NAME, "user")
            password_input = driver.find_element(By.NAME, "password")
            login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            user_input.send_keys(GRAFANA_USERNAME)
            password_input.send_keys(GRAFANA_PASSWORD)
            login_button.click()
            logging.info("Login submitted.")
            time.sleep(5)
        except Exception as e:
            logging.warning("Login not required or failed: %s", e)

        time.sleep(30)  # Wait for full dashboard to load
        driver.execute_script("document.body.style.zoom='90%'")
        time.sleep(2)

        # Generate a unique, short filename
        # Use a hash of the URL to ensure uniqueness and reduce length
        filename_hash = hashlib.md5(grafana_url.encode()).hexdigest()
        filename = f"grafana_{filename_hash}.png"
        screenshot_path = os.path.join(os.getcwd(), filename)

        # Save the screenshot
        driver.save_screenshot(screenshot_path)
        driver.quit()
        logging.info(f"Screenshot captured for {grafana_url}. Saved as {filename}")
        return screenshot_path

    except Exception as e:
        logging.exception("Screenshot error")
        st.error(f"Error capturing screenshot for {grafana_url}: {e}")
        return None


def send_email(screenshots, recipient_email):
    """Send an email with screenshots attached."""
    try:
        # Create the email
        msg = MIMEMultipart('related')
        msg['From'] = EMAIL_SENDER
        msg['To'] = recipient_email
        msg['Subject'] = "Network Change Status Updates"

        # Email content
        html = """
        <html>
        <body style="font-family: Tahoma, sans-serif;">
            <p>Hi Team,</p>
            <p>Please find below the status updates for the network post-change.</p>
            {}
            <p>Thanks,<br>CiscoIoTNOC</p>
        </body>
        </html>
        """
        image_tags = ""
        for i, screenshot_path in enumerate(screenshots):
            image_tags += f'<p>Grafana Dashboard {i + 1}:<br><img src="cid:image{i}" style="border:1px solid #ccc; max-width:100%;" /></p>'
        html = html.format(image_tags)
        msg.attach(MIMEText(html, 'html'))

        # Attach each screenshot
        for i, screenshot_path in enumerate(screenshots):
            with open(screenshot_path, 'rb') as f:
                img = MIMEImage(f.read(), _subtype='png')
                img.add_header('Content-ID', f'<image{i}>')
                img.add_header('Content-Disposition', 'inline', filename=os.path.basename(screenshot_path))
                msg.attach(img)

        # Create secure connection with Cisco SMTP server
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.set_debuglevel(1)  # Enable debug output for troubleshooting
            server.starttls(context=context)  # Upgrade to secure TLS connection
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)  # Login using Cisco credentials
            server.send_message(msg)

        st.success(f"Email sent to {recipient_email}")
        logging.info(f"Email sent to {recipient_email}")

    except Exception as e:
        logging.exception("Email send error")
        st.error(f"Error sending email: {e}")


def capture_and_send_email(grafana_urls, recipient_email):
    """Capture screenshots for multiple Grafana URLs and send them via email."""
    logging.info("Scheduled job triggered.")
    screenshots = []
    for grafana_url in grafana_urls:
        screenshot = capture_screenshot(grafana_url)
        if screenshot:
            screenshots.append(screenshot)
    if screenshots:
        send_email(screenshots, recipient_email)


def parse_grafana_urls(input_text):
    """Parse multi-line input text to extract and sanitize Grafana URLs."""
    urls = []
    for line in input_text.splitlines():
        line = line.strip()  # Remove leading/trailing whitespace
        if line:  # Ignore empty lines
            urls.append(line)
    return urls


# Streamlit UI
st.title("Grafana Periodic Update Tool")

grafana_urls_input = st.text_area(
    "Enter Grafana Dashboard URLs (one URL per line)",
    placeholder="https://grafana.example.com/dashboard1\nhttps://grafana.example.com/dashboard2",
)
recipient_email = st.text_input("Enter recipient email address")

send_frequency = st.selectbox(
    "Select how often to send the screenshots",
    ["Once", "Hourly", "Bihourly", "Every 2 minutes", "Every 5 minutes"]
)
if email_password:
    st.write("Environment variable loaded successfully!")
else:
    st.write("EMAIL_PASSWORD is not set.")

if st.button("Start Scheduler"):
    if not grafana_urls_input.strip():
        st.error("Please enter at least one Grafana URL.")
    elif not recipient_email:
        st.error("Please enter a recipient email address.")
    elif not EMAIL_PASSWORD:
        st.error("CISCO_EMAIL_PASSWORD environment variable is missing.")
    else:
        try:
            grafana_urls = parse_grafana_urls(grafana_urls_input)
            if not grafana_urls:
                st.error("No valid Grafana URLs provided.")
            else:
                scheduler = BackgroundScheduler()
                job_args = (grafana_urls, recipient_email)

                if send_frequency == "Once":
                    scheduler.add_job(lambda: capture_and_send_email(*job_args), 'date')
                elif send_frequency == "Hourly":
                    scheduler.add_job(lambda: capture_and_send_email(*job_args), 'interval', hours=1)
                elif send_frequency == "Bihourly":
                    scheduler.add_job(lambda: capture_and_send_email(*job_args), 'interval', hours=2)
                elif send_frequency == "Every 2 minutes":
                    scheduler.add_job(lambda: capture_and_send_email(*job_args), 'interval', minutes=2)
                elif send_frequency == "Every 5 minutes":
                    scheduler.add_job(lambda: capture_and_send_email(*job_args), 'interval', minutes=5)

                scheduler.start()
                st.success("Scheduler started.")
                logging.info("Scheduler started: %s", send_frequency)

        except Exception as e:
            logging.exception("Scheduler failed")
            st.error(f"Scheduler error: {e}")
