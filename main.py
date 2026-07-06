import threading
import random
import requests
import paramiko
from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.core.window import Window

# === إعدادات الراوتر (قم بتغيير الباسورد الخاص براوترك هنا) ===
ROUTER_IP = "192.168.1.1"
ROUTER_USER = "root"
ROUTER_PASS = "admin" # <-- غير هذا إلى باسورد الراوتر الفعلي

# === إعدادات تليجرام ===
TELEGRAM_BOT_TOKEN = "8635550416:AAGsNM7mnjak80kQclTHdMJYKKvaiAJHNjI"
TELEGRAM_CHAT_ID = "5394550159"

KV_UI = '''
BoxLayout:
    orientation: 'vertical'
    padding: 30
    spacing: 20
    canvas.before:
        Color:
            rgba: 0.1, 0.1, 0.12, 1
        Rectangle:
            pos: self.pos
            size: self.size

    Label:
        text: "NetGuard Pro"
        font_size: '30sp'
        bold: True
        color: 0.2, 0.8, 1, 1
        size_hint_y: 0.1

    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: 0.15, 0.16, 0.2, 1
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [20]
        padding: 20
        size_hint_y: 0.3
        Label:
            text: "استهلاك الجهاز المستهدف"
            font_size: '18sp'
            color: 0.8, 0.8, 0.8, 1
        Label:
            id: usage_label
            text: "--- GB"
            font_size: '40sp'
            bold: True
            color: 1, 1, 1, 1
        Label:
            id: status_label
            text: "جاهز للاتصال"
            font_size: '16sp'
            color: 0.8, 0.8, 0.8, 1

    TextInput:
        id: target_ip
        hint_text: "IP الجهاز (مثال: 192.168.1.5)"
        multiline: False
        size_hint_y: 0.12
        font_size: '18sp'
        halign: 'center'

    TextInput:
        id: limit_gb
        hint_text: "الحد الأقصى (جيجابايت)"
        multiline: False
        input_type: 'number'
        size_hint_y: 0.12
        font_size: '18sp'
        halign: 'center'

    Button:
        id: check_btn
        text: "فحص وتطبيق القواعد"
        size_hint_y: 0.15
        font_size: '18sp'
        bold: True
        background_color: 0.1, 0.5, 0.8, 1
        on_press: app.start_check_thread()

    BoxLayout:
        id: reset_section
        orientation: 'vertical'
        spacing: 10
        opacity: 0
        disabled: True
        size_hint_y: 0.25
        TextInput:
            id: reset_code_input
            hint_text: "أدخل كود فك الحظر (من تليجرام)"
            multiline: False
            font_size: '18sp'
            halign: 'center'
        Button:
            text: "تفعيل الإنترنت"
            size_hint_y: 0.8
            font_size: '18sp'
            bold: True
            background_color: 0.2, 0.8, 0.2, 1
            on_press: app.verify_reset_code()
'''

class NetGuardApp(App):
    def build(self):
        Window.clearcolor = (0.1, 0.1, 0.12, 1)
        self.active_reset_code = None
        return Builder.load_string(KV_UI)

    def start_check_thread(self):
        ip = self.root.ids.target_ip.text.strip()
        limit = self.root.ids.limit_gb.text.strip()
        
        if not ip or not limit:
            self.update_ui("status", "يرجى إدخال الـ IP والحد الأقصى!", (1, 0.2, 0.2, 1))
            return

        self.update_ui("status", "جاري الاتصال بالراوتر...", (0.8, 0.8, 0.8, 1))
        self.root.ids.check_btn.disabled = True
        
        threading.Thread(target=self.process_logic, args=(ip, float(limit))).start()

    def process_logic(self, ip, limit):
        try:
            # 1. الاتصال بالراوتر وجلب الاستهلاك الفعلي عبر أداة wrtbwmon
            command = f"wrtbwmon read | grep {ip} | awk '{{print $5}}'"
            raw_usage = self.ssh_execute(command)
            
            # معالجة القيمة في حال كان الجهاز غير موجود في القائمة
            try:
                current_usage = float(raw_usage) if raw_usage else 0.0
            except ValueError:
                current_usage = 0.0

            Clock.schedule_once(lambda dt: self.update_ui("usage", f"{current_usage} GB"))

            # 2. مقارنة الاستهلاك بالحد المسموح به
            if current_usage >= limit:
                Clock.schedule_once(lambda dt: self.update_ui("status", "تم تجاوز الحد! جاري قطع الإنترنت...", (1, 0.2, 0.2, 1)))
                
                # إرسال أمر حظر الـ IP الحقيقي للراوتر
                self.ssh_execute(f"iptables -I FORWARD -s {ip} -j DROP")
                
                # إنشاء الكود وإرساله لتليجرام
                self.active_reset_code = str(random.randint(100000, 999999))
                self.send_telegram_alert(ip, current_usage, self.active_reset_code)
                
                Clock.schedule_once(lambda dt: self.show_reset_section())
            else:
                Clock.schedule_once(lambda dt: self.update_ui("status", "الاستهلاك في المعدل الآمن", (0.2, 1, 0.2, 1)))

        except Exception as e:
            Clock.schedule_once(lambda dt: self.update_ui("status", f"خطأ في الاتصال: تأكد من بيانات الراوتر", (1, 0.2, 0.2, 1)))
        
        finally:
            Clock.schedule_once(lambda dt: self.enable_button())

    def ssh_execute(self, command):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(ROUTER_IP, username=ROUTER_USER, password=ROUTER_PASS, timeout=5)
        stdin, stdout, stderr = client.exec_command(command)
        result = stdout.read().decode().strip()
        client.close()
        return result

    def send_telegram_alert(self, ip, usage, code):
        msg = f"🔴 **تنبيه قطع الإنترنت!** 🔴\n\n📱 **الـ IP المحظور:** {ip}\n📊 **الاستهلاك:** {usage} GB\n\n🔑 **كود إعادة التفعيل:**\n`{code}`"
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        try:
            requests.post(url, data=payload, timeout=5)
        except:
            pass

    def verify_reset_code(self):
        user_code = self.root.ids.reset_code_input.text.strip()
        if user_code == self.active_reset_code:
            ip = self.root.ids.target_ip.text.strip()
            self.update_ui("status", "الكود صحيح! جاري استرجاع الإنترنت...", (0.2, 1, 0.2, 1))
            
            # أمر فك الحظر الحقيقي
            threading.Thread(target=self.ssh_execute, args=(f"iptables -D FORWARD -s {ip} -j DROP",)).start()
            
            self.active_reset_code = None
            self.root.ids.reset_section.opacity = 0
            self.root.ids.reset_section.disabled = True
            self.root.ids.reset_code_input.text = ""
        else:
            self.update_ui("status", "الكود خاطئ!", (1, 0.2, 0.2, 1))

    def update_ui(self, element, text, color=None):
        if element == "status":
            self.root.ids.status_label.text = text
            if color: self.root.ids.status_label.color = color
        elif element == "usage":
            self.root.ids.usage_label.text = text

    def show_reset_section(self):
        self.root.ids.reset_section.opacity = 1
        self.root.ids.reset_section.disabled = False

    def enable_button(self):
        self.root.ids.check_btn.disabled = False

if __name__ == '__main__':
    NetGuardApp().run()
