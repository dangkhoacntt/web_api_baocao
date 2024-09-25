import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
from functools import wraps
from flask_wtf import FlaskForm
from db import get_db_connection
import hashlib
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email
import os
from models import create_user, get_user
from flask import jsonify


# Cấu hình logging
logging.basicConfig(level=logging.DEBUG)  # Cấu hình để ghi log ở mức độ DEBUG
logger = logging.getLogger(__name__)  # Tạo logger

def generate_api_key():
    return hashlib.md5(os.urandom(16)).hexdigest()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

admin_bp = Blueprint('admin', __name__)

def is_admin_user(email):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT is_admin FROM user WHERE email = ?", (email,))
    result = cursor.fetchone()
    conn.close()
    
    # Kiểm tra xem email có tồn tại và is_admin có phải là 1 không
    logger.debug(f"Checking if user {email} is admin.")
    return result is not None and result[0] == 1
@admin_bp.route('/chart')
def chart():
    # Lấy dữ liệu từ đâu đó (ví dụ từ database hoặc API)
    sales_data = [
        {"Product": "Wireless Headphones", "BuyerEmail": "john@test.com", "PurchaseDate": "2024-08-01", "Country": "USA", "Price": 99.0, "Refunded": "NO", "Currency": "USD", "Quantity": 2},
        # Các mục khác...
    ]
    
    return render_template('backend/chart.html', sales_data=sales_data)
@admin_bp.route('/admin')
def admin_dashboard():
    if 'admin_email' in session and is_admin_user(session['admin_email']):
        logger.info(f"Admin {session['admin_email']} accessed the dashboard.")
        return render_template('backend/home.html')
    
    logger.warning(f"Access denied for {session.get('admin_email', 'unknown')} to admin dashboard.")
    flash('Truy cập bị từ chối. Chỉ dành cho quản trị viên.', 'danger')
    return redirect(url_for('admin.login'))

class AdminLoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')

@admin_bp.route('/admin/login', methods=['GET', 'POST'])
def login():
    form = AdminLoginForm()  # Khởi tạo form đăng nhập admin

    if form.validate_on_submit():  # Kiểm tra dữ liệu hợp lệ
        email = form.email.data
        password = form.password.data
        remember_me = form.remember_me.data

        user = get_user(email, hash_password(password))
        if user and is_admin_user(email):
            session['admin_email'] = user['email']
            flash('Đăng nhập admin thành công!', 'success')
            logger.info(f"Admin {email} logged in successfully.")

            response = redirect(url_for('admin.admin_dashboard'))

            if remember_me:
                response.set_cookie('admin_email', user['email'], max_age=30*24*60*60)
            else:
                response.set_cookie('admin_email', '', expires=0)

            return response
        else:
            logger.warning(f"Failed login attempt for {email}.")
            flash('Tài khoản không phải là admin hoặc thông tin đăng nhập không chính xác.', 'danger')

    return render_template('backend/login.html', form=form)

class BlockUserForm(FlaskForm):
    submit = SubmitField('Khóa tài khoản', validators=[DataRequired()])

@admin_bp.route('/admin/block_user/<int:user_id>', methods=['POST'])
def block_user(user_id):
    if not is_admin_user(session.get('admin_email', None)):
        return jsonify({'success': False, 'message': 'Bạn không có quyền thực hiện thao tác này.'}), 403

    conn = get_db_connection()
    conn.execute('UPDATE user SET status = ? WHERE id = ?', ('banned', user_id))
    conn.commit()
    conn.close()

    logger.info(f'User {user_id} has been blocked by admin {session["admin_email"]}.')
    return jsonify({'success': True, 'message': f'Tài khoản người dùng {user_id} đã bị khóa.'})






def log_api_usage(user_id, key_api, link_api, action, success):
    conn = get_db_connection()
    conn.execute('INSERT INTO api_usage (user_id, key_api, link_api, action, success) VALUES (?, ?, ?, ?, ?)',
                 (user_id, key_api, link_api, action, success))
    conn.commit()
    conn.close()

def deduct_finances(email, amount):
    conn = get_db_connection()
    # Giảm số tiền trong tài khoản
    conn.execute('UPDATE user SET finances = finances - ? WHERE email = ?', (amount, email))
    conn.commit()
    conn.close()

def refund_finances(email, amount):
    conn = get_db_connection()
    # Hoàn tiền vào tài khoản
    conn.execute('UPDATE user SET finances = finances + ? WHERE email = ?', (amount, email))
    conn.commit()
    conn.close()

@admin_bp.route('/api/v1/resource', methods=['POST'])
  # Tắt CSRF cho route này
def resource():
    api_key = request.headers.get('API-Key')
    
    # Kiểm tra và xử lý các thao tác liên quan đến api_key
    user = get_user_from_key_api(api_key)
    if not user:
        return jsonify({"message": "Invalid API Key"}), 401

    finances = int(user['finances'])
    if finances <= 0:
        return jsonify({"message": "Insufficient balance"}), 400

    captcha_success = request.json.get('success')
    amount = 1

    deduct_finances(user['email'], amount)

    if captcha_success:
        log_api_usage(user['id'], api_key, request.path, request.method, True)
        return jsonify({"message": "CAPTCHA solved successfully", "finances": finances - amount}), 200
    else:
        refund_finances(user['email'], amount)
        log_api_usage(user['id'], api_key, request.path, request.method, False)
        return jsonify({"message": "CAPTCHA failed, finances refunded", "finances": finances}), 200


# Hàm để lấy chi tiết sử dụng API dựa trên key_api
def get_api_usage_details(key_api):
    conn = get_db_connection()
    usage_details = conn.execute(
        'SELECT link_api, action, success, usage_timestamp FROM api_usage WHERE key_api = ? ORDER BY usage_timestamp DESC',
        (key_api,)
    ).fetchall()
    conn.close()
    return usage_details
def get_user_from_key_api(key_api):
    if not key_api:
        return None  # Trả về None nếu không có key_api

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user WHERE key_api = ?", (key_api,))
    user = cursor.fetchone()
    conn.close()

    if user:
        return {
            'id': user[0],  # Giả sử cột 'id' là cột đầu tiên trong bảng `user`
            'email': user[1],  # Giả sử cột 'email' là cột thứ hai
            'finances': user[5],  # Giả sử cột 'finances' là cột thứ sáu
            'key_api': user[6],  # Giả sử cột 'key_api' là cột thứ bảy
            # Thêm các cột khác nếu cần
        }
    return None  # Trả về None nếu không tìm thấy người dùng

def log_api_usage(user_id, key_api, link_api, action, success):
    conn = get_db_connection()  # Mở kết nối
    try:
        print(f"Logging API usage: {user_id}, {key_api}, {link_api}, {action}, {success}")
        conn.execute('INSERT INTO api_usage (user_id, key_api, link_api, action, success) VALUES (?, ?, ?, ?, ?)',
                     (user_id, key_api, link_api, action, success))
        conn.commit()
        print("API usage logged successfully.")
    except sqlite3.Error as e:
        print(f"Error logging API usage: {e}")
    finally:
        conn.close()  # Đảm bảo đóng kết nối ở đây

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row  # Để truy cập dữ liệu như từ điển
    return conn

@admin_bp.route('/api/user/<key_api>/usage', methods=['GET'])
def get_api_usage(key_api):
    conn = get_db_connection()
    usage_details = conn.execute(
        'SELECT success, usage_timestamp FROM api_usage WHERE key_api = ? ORDER BY usage_timestamp ASC',
        (key_api,)
    ).fetchall()
    conn.close()

    # Chuyển đổi dữ liệu thành dạng list để dễ trả về JSON
    usage_data = [{'success': row[0], 'usage_timestamp': row[1]} for row in usage_details]

    return jsonify(usage_data)

def deduct_finances(user_id, amount):
    conn = get_db_connection()
    try:
        # Trừ tiền trong tài khoản người dùng
        conn.execute('UPDATE user SET finances = finances - ? WHERE id = ?', (amount, user_id))
        # Lưu giao dịch vào bảng transactions với loại 'withdraw'
        conn.execute('INSERT INTO transactions (user_id, transaction_type, amount) VALUES (?, ?, ?)', (user_id, 'withdraw', amount))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error updating finances and logging transaction for user {user_id}: {e}")
    finally:
        conn.close()
@admin_bp.route('/admin/used_funds_report', methods=['GET'])
def used_funds_report():
    if 'admin_email' not in session or not is_admin_user(session['admin_email']):
        flash('Truy cập bị từ chối. Chỉ dành cho quản trị viên.', 'danger')
        return redirect(url_for('admin.login'))

    conn = get_db_connection()

    # Tổng số tiền đã sử dụng (withdraw)
    total_used = conn.execute(
        'SELECT SUM(amount) FROM transactions WHERE transaction_type = "withdraw"'
    ).fetchone()[0] or 0

    # Lấy danh sách chi tiết các giao dịch rút tiền (withdraw)
    used_funds_details = conn.execute(
        '''
        SELECT u.email, t.amount, t.created_at
        FROM transactions t
        JOIN user u ON t.user_id = u.id
        WHERE t.transaction_type = "withdraw"
        ORDER BY t.created_at DESC
        '''
    ).fetchall()

    conn.close()

    return render_template('backend/used_funds_report.html', total_used=total_used, used_funds_details=used_funds_details)
