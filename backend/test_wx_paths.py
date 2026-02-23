
import os
import sys
import time

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

from quant.services.auto_analyzer import send_wechat_message

def test_send():
    print("Testing WeChat send...")
    # send_wechat_message("Test message from Trae AI")
    # I won't actually send it to avoid spamming, but I will check if the function can locate images.
    # To do this properly without actual sending, I would need to modify the function or mock pyautogui.
    # But the user wants to fix the error "wx.png not found".
    # So I should check if the paths are correct.
    
    from quant.services.auto_analyzer import WX_IMAGE, AVATAR_IMAGE, AVATAR1_IMAGE, SEND_IMAGE
    
    print(f"WX_IMAGE: {WX_IMAGE}")
    print(f"Exists: {os.path.exists(WX_IMAGE)}")
    
    print(f"AVATAR_IMAGE: {AVATAR_IMAGE}")
    print(f"Exists: {os.path.exists(AVATAR_IMAGE)}")
    
    print(f"AVATAR1_IMAGE: {AVATAR1_IMAGE}")
    print(f"Exists: {os.path.exists(AVATAR1_IMAGE)}")
    
    print(f"SEND_IMAGE: {SEND_IMAGE}")
    print(f"Exists: {os.path.exists(SEND_IMAGE)}")

if __name__ == "__main__":
    test_send()
