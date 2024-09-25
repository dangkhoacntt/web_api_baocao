import os

class Config:
    MAIL_SERVER = 'smtp.gmail.com'  # Máy chủ SMTP của Gmail
    MAIL_PORT = 587  # Cổng SMTP với TLS
    MAIL_USERNAME = 'cubom882001@gmail.com'  # Địa chỉ email của bạn
    MAIL_PASSWORD = 'wrgq yadb jivf nbhm'  # Mật khẩu ứng dụng Gmail (app password)
    MAIL_USE_TLS = True  # Sử dụng TLS để mã hóa kết nối
    MAIL_USE_SSL = False  # Không sử dụng SSL
    MAIL_DEFAULT_SENDER = 'cubom882001@gmail.com'  # Địa chỉ email người gửi mặc định
    SECRET_KEY = os.urandom(24)  # Khóa bí mật ngẫu nhiên
    WTF_CSRF_ENABLED = True 
    DATABASE = os.path.join(os.path.dirname(__file__), 'database.db')
