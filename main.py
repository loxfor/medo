import json
import base64
import requests
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.core.image import Image as CoreImage
from io import BytesIO
import os

class EvolutionController(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', padding=15, spacing=12, **kwargs)
        
        # Status Label
        self.status_label = Label(text='Status: Disconnected / Ready', size_hint_y=None, height=45, color=(0.2, 0.8, 0.2, 1))
        self.add_widget(self.status_label)
        
        # Input fields
        self.url_input = TextInput(hint_text='Evolution API URL (e.g., http://192.168.1.100:8080)', multiline=False, size_hint_y=None, height=45)
        self.key_input = TextInput(hint_text='API Key (apikey)', multiline=False, password=True, size_hint_y=None, height=45)
        self.instance_input = TextInput(hint_text='Instance Name (e.g., main)', multiline=False, size_hint_y=None, height=45)
        
        self.add_widget(self.url_input)
        self.add_widget(self.key_input)
        self.add_widget(self.instance_input)
        
        # Load pre-saved configuration if it exists
        self.load_settings()
        
        # Control Buttons
        self.save_btn = Button(text='Save Settings', size_hint_y=None, height=50, background_color=(0.1, 0.5, 0.8, 1))
        self.save_btn.bind(on_press=self.save_settings)
        
        self.connect_btn = Button(text='Fetch & Show QR Code', size_hint_y=None, height=50, background_color=(0.2, 0.7, 0.3, 1))
        self.connect_btn.bind(on_press=self.get_qr)
        
        self.stop_btn = Button(text='Stop Bot (Logout)', size_hint_y=None, height=50, background_color=(0.8, 0.2, 0.2, 1))
        self.stop_btn.bind(on_press=self.stop_bot)
        
        self.add_widget(self.save_btn)
        self.add_widget(self.connect_btn)
        self.add_widget(self.stop_btn)
        
        # Area to display the QR Code
        self.qr_image = Image(allow_stretch=True)
        self.add_widget(self.qr_image)

    def load_settings(self):
        if os.path.exists('config.json'):
            try:
                with open('config.json', 'r') as f:
                    config = json.load(f)
                    self.url_input.text = config.get('url', '')
                    self.key_input.text = config.get('key', '')
                    self.instance_input.text = config.get('instance', '')
            except Exception as e:
                pass

    def save_settings(self, instance):
        url = self.url_input.text.strip().rstrip('/')
        key = self.key_input.text.strip()
        inst = self.instance_input.text.strip()
        
        config = {'url': url, 'key': key, 'instance': inst}
        with open('config.json', 'w') as f:
            json.dump(config, f)
        self.status_label.text = 'Status: Settings Saved Locally!'

    def get_qr(self, instance):
        url = f"{self.url_input.text.strip().rstrip('/')}/instance/connect/{self.instance_input.text.strip()}"
        headers = {"apikey": self.key_input.text.strip()}
        self.status_label.text = 'Status: Fetching QR Code from Server...'
        
        try:
            response = requests.get(url, headers=headers, timeout=12)
            if response.status_code in [200, 201]:
                data = response.json()
                if 'base64' in data:
                    qr_base64 = data['base64']
                    if ',' in qr_base64:
                        qr_base64 = qr_base64.split(',')[1]
                    img_data = BytesIO(base64.b64decode(qr_base64))
                    self.qr_image.texture = CoreImage(img_data, ext='png').texture
                    self.status_label.text = 'Status: QR Loaded Successfully! Scan now.'
                else:
                    self.status_label.text = 'Status: Connected or Instance is already active.'
            else:
                self.status_label.text = f'Status: Server Error ({response.status_code})'
        except Exception as e:
            self.status_label.text = 'Status: Failed to connect to API server.'

    def stop_bot(self, instance):
        url = f"{self.url_input.text.strip().rstrip('/')}/instance/logout/{self.instance_input.text.strip()}"
        headers = {"apikey": self.key_input.text.strip()}
        self.status_label.text = 'Status: Sending Logout Command...'
        
        try:
            response = requests.delete(url, headers=headers, timeout=12)
            if response.status_code in [200, 201]:
                self.status_label.text = 'Status: Bot Disconnected & Logged Out.'
                self.qr_image.texture = None
            else:
                self.status_label.text = f'Status: Action failed ({response.status_code})'
        except Exception as e:
            self.status_label.text = 'Status: Server communication error.'

class WhatsAppControlApp(App):
    def build(self):
        self.title = 'Evolution API Control Panel'
        return EvolutionController()

if __name__ == '__main__':
    WhatsAppControlApp().run()
