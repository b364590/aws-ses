import boto3
from botocore.exceptions import WaiterError, ClientError, ParamValidationError
import logging
import ssl
import smtplib
from hashlib import sha256
import hmac
import base64
import os
from dotenv import load_dotenv
import json

# 載入.env
load_dotenv()

# 取得環境變數
aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
aws_region = os.getenv("AWS_REGION")
smtp_username = os.getenv("SMTP_USERNAME")  # SMTP 用户名
smtp_password = os.getenv("SMTP_PASSWORD")  # SMTP 密码

class SesIdentity:
    def __init__(self, client):
        self.client = client

    def get_identity_status(self, email):
        try:
            response = self.client.get_identity_verification_attributes(
                Identities=[email]
            )
            status = response['VerificationAttributes'][email]['VerificationStatus']
            return status
        except Exception as e:
            print(f"Error getting identity status: {e}")
            return "Error"

    def verify_email_identity(self, email):
        try:
            self.client.verify_email_identity(EmailAddress=email)
        except Exception as e:
            print(f"Error verifying email identity: {e}")

    def wait_until_identity_exists(self, email):
        waiter = self.client.get_waiter('identity_exists')
        waiter.wait(Identities=[email])

    def delete_identity(self, email):
        try:
            self.client.delete_identity(Identity=email)
        except Exception as e:
            print(f"Error deleting identity: {e}")

class SesMailSender:
    def __init__(self, client):
        self.client = client

    def send_email(self, sender, destination, subject, text, html):
        try:
            response = self.client.send_email(
                Source=sender,
                Destination={'ToAddresses': destination.emails},
                Message={
                    'Subject': {'Data': subject},
                    'Body': {
                        'Text': {'Data': text},
                        'Html': {'Data': html}
                    }
                }
            )
            print(f"Email sent! Message ID: {response['MessageId']}")
        except ClientError as e:
            print(f"Error sending email: {e.response['Error']['Message']}")

    def send_templated_email(self, sender, destination, template_name, template_data):
        try:
            response = self.client.send_templated_email(
                Source=sender,
                Destination={'ToAddresses': destination.emails},
                Template=template_name,
                TemplateData=json.dumps(template_data)
            )
            print(f"Templated email sent! Message ID: {response['MessageId']}")
        except ClientError as e:
            print(f"Error sending templated email: {e.response['Error']['Message']}")

class SesDestination:
    def __init__(self, emails):
        self.emails = emails

class SesTemplate:
    def __init__(self, client):
        self.client = client
        self.template = None

    def create_template(self, name, subject, text, html):
        self.template = {
            'TemplateName': name,
            'SubjectPart': subject,
            'TextPart': text,
            'HtmlPart': html
        }
        try:
            self.client.create_template(Template=self.template)
        except ClientError as e:
            if e.response['Error']['Code'] == 'AlreadyExists':
                print(f"Template {name} already exists.")
            else:
                print(f"Error creating template: {e.response['Error']['Message']}")

    def delete_template(self):
        try:
            self.client.delete_template(TemplateName=self.template['TemplateName'])
            print("Template deleted.")
        except ClientError as e:
            print(f"Error deleting template: {e.response['Error']['Message']}")

    def name(self):
        return self.template['TemplateName']

    def verify_tags(self, tags):
        return all(key in tags for key in ['name', 'action'])

def usage_demo():
    print("-" * 88)
    print("Welcome to the Amazon Simple Email Service (Amazon SES) email demo!")
    print("-" * 88)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    #登入客戶端
    ses_client = boto3.client(
        "ses",
        region_name=aws_region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )
    ses_identity = SesIdentity(ses_client)
    ses_mail_sender = SesMailSender(ses_client)
    ses_template = SesTemplate(ses_client)
    email = input("Enter an email address to receive mail with Amazon SES: ")
    email_server = "ntutlab321projects@gmail.com" 
    status = ses_identity.get_identity_status(email)
    verified = status == "Success"
    
    #判斷郵件是否經ses驗證
    if not verified:
        answer = input(
            f"The address '{email}' is not verified with Amazon SES.\n"
            f"Do you want to verify this account for use with Amazon SES?\n"
            f"If yes, the address will receive a verification email (y/n):"
        )
        if answer.lower() == "y":
            ses_identity.verify_email_identity(email) #調用identity函式寄送驗證信
            print(f"Follow the steps in the email to {email} to complete verification.")
            print("Waiting for verification...")
            try:
                ses_identity.wait_until_identity_exists(email)
                print(f"Identity verified for {email}.")
                verified = True
            except WaiterError:
                print(
                    f"Verification timeout exceeded. You must complete the "
                    f"steps in the email sent to {email} to verify the address."
                )

    if verified:
        test_message_text = "Hello from the Amazon SES mail demo!"
        test_message_html = "<p>Hello!</p><p>From the <b>Amazon SES</b> mail demo!</p>"

        print(f"Sending mail from {email_server} to {email}.")
        ses_mail_sender.send_email(
            email_server,
            SesDestination([email]),
            "Amazon SES demo",
            test_message_text,
            test_message_html,
        )
        input("Mail sent. Check your inbox and press Enter to continue.")

        template = {
            "name": "doc-example-template",
            "subject": "Example of an email template.",
            "text": "This is what {{name}} will {{action}} if {{name}} can't display HTML.",
            "html": "<p><i>This</i> is what {{name}} will {{action}} if {{name}} <b>can</b> display HTML.</p>",
        }
        print("Creating a template and sending a templated email.")
        ses_template.create_template(**template)
        template_data = {"name": email.split("@")[0], "action": "read"}
        if ses_template.verify_tags(template_data):
            ses_mail_sender.send_templated_email(
                email_server, SesDestination([email]), ses_template.name(), template_data
            )
            input("Mail sent. Check your inbox and press Enter to continue.")

        print("Sending mail through the Amazon SES SMTP server.")
        port = 587
        smtp_server = f"email-smtp.{aws_region}.amazonaws.com"
        message = """Subject: Hi there\n\nThis message is sent from the Amazon SES SMTP mail demo."""
        context = ssl.create_default_context()
        try:
            with smtplib.SMTP(smtp_server, port) as server:
                server.starttls(context=context)
                server.login(smtp_username, smtp_password)
                server.sendmail(email_server, email, message)
            print("Mail sent. Check your inbox!")
        except smtplib.SMTPAuthenticationError as e:
            print(f"Error sending email through SMTP: {e}")

    if ses_template.template is not None:
        try:
            print("Deleting demo template.")
            ses_template.delete_template()
        except ClientError as e:
            print(f"Error deleting template: {e}")
    if verified:
        answer = input(f"Do you want to remove {email} from Amazon SES (y/n)? ")
        if answer.lower() == "y":
            ses_identity.delete_identity(email)
    print("Thanks for watching!")
    print("-" * 88)

if __name__ == "__main__":
     usage_demo()
