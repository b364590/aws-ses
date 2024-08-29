import queue
import threading
import time
from ses_mail_sender import SesMailSender, SesDestination
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

class MessageQueue:
    def __init__(self, ses_client):
        self.queue = queue.Queue() #FIFO
        self.ses_sender = SesMailSender(ses_client)
        self.ses_client = ses_client
        self.is_running = False
        self.worker_thread = None
        # self.last_send_time = 0
        # self.min_interval = 0.5  # 500ms        
    
        
    def add_message(self, sender, recipients, subject, body_text, body_html): #一般訊息
        self.queue.put(('regular', sender, recipients, subject, body_text, body_html))

    def add_templated_message(self, sender, recipients, template_name, template_data): #模板
        self.queue.put(('templated', sender, recipients, template_name, template_data))

    def add_message_with_attachment(self, sender, recipients, subject, body_text, body_html, image_path): #附件
        self.queue.put(('attachment', sender, recipients, subject, body_text, body_html, image_path))

    def start_processing(self):
        if not self.is_running:
            self.is_running = True
            self.worker_thread = threading.Thread(target=self._process_queue)
            self.worker_thread.start()

    # def start_processing(self, num_workers=5):
    #     if not self.is_running:
    #         self.is_running = True
    #         self.worker_threads = []

        
    def stop_processing(self):
        self.is_running = False
        if self.worker_thread:
            self.worker_thread.join()
            
    #等待多線完成
    # def stop_processing(self):
    #     self.is_running = False
    #     for worker_thread in self.worker_threads:
    #         worker_thread.join() 
        

    def _process_queue(self):
        while self.is_running:
            try:
                message_type, *args = self.queue.get(timeout=1)
                if message_type == 'regular':
                    sender, recipients, subject, body_text, body_html = args
                    destination = SesDestination(recipients)
                    self.ses_sender.send_email(sender, destination, subject, body_text, body_html)
                elif message_type == 'templated':
                    sender, recipients, template_name, template_data = args
                    destination = SesDestination(recipients)
                    self.ses_sender.send_templated_email(sender, destination, template_name, template_data)
                elif message_type == 'attachment':
                    sender, recipients, subject, body_text, body_html, image_path = args
                    self._send_email_with_attachment(sender, recipients, subject, body_text, body_html, image_path)
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error sending email: {e}")
            time.sleep(1)  # Avoid sending too quickly

    # def _process_queue(self):
    #     while self.is_running:
    #         try:
    #             message_type, *args = self.queue.get(timeout=1)
                
    #             # 计算从上次发送到现在的时间间隔
    #             current_time = time.time()
    #             time_since_last_send = current_time - self.last_send_time

    #             # 如果间隔时间小于最小间隔时间，休眠剩余的时间
    #             if time_since_last_send < self.min_interval:
    #                 time.sleep(self.min_interval - time_since_last_send)

    #             # 发送邮件
    #             if message_type == 'regular':
    #                 sender, recipients, subject, body_text, body_html = args
    #                 destination = SesDestination(recipients)
    #                 self.ses_sender.send_email(sender, destination, subject, body_text, body_html)
    #             elif message_type == 'templated':
    #                 sender, recipients, template_name, template_data = args
    #                 destination = SesDestination(recipients)
    #                 self.ses_sender.send_templated_email(sender, destination, template_name, template_data)
    #             elif message_type == 'attachment':
    #                 sender, recipients, subject, body_text, body_html, image_path = args
    #                 self._send_email_with_attachment(sender, recipients, subject, body_text, body_html, image_path)

    #             self.queue.task_done()

    #             # 更新最后发送时间
    #             self.last_send_time = time.time()
                
    #         except queue.Empty:
    #             continue
    #         except Exception as e:
    #             print(f"Error sending email: {e}")
                
                
    def _send_email_with_attachment(self, sender, recipients, subject, body_text, body_html, image_path):
        msg = MIMEMultipart('related')
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = ', '.join(recipients)

        text_part = MIMEMultipart('alternative')
        text_part.attach(MIMEText(body_text, 'plain'))
        text_part.attach(MIMEText(body_html, 'html'))
        msg.attach(text_part)

        with open(image_path, 'rb') as img:
            img_part = MIMEImage(img.read())
            img_part.add_header('Content-ID', '<instai_web_image>')
            img_part.add_header('Content-Disposition', 'inline', filename='InstAI-Web v0.7.png')
            msg.attach(img_part)

        try:
            self.ses_client.send_raw_email(
                Source=sender,
                Destinations=recipients,
                RawMessage={'Data': msg.as_string()}
            )
            print(f"Email with attachment sent to {', '.join(recipients)}")
        except Exception as e:
            print(f"Error sending email with attachment: {e}")

    def wait_for_completion(self):
        self.queue.join()