from flask import Flask, request, render_template, redirect, url_for, flash
from text2img_model import create_pipeline, text2img
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
import random
import glob
import time
from datetime import datetime, date
from functools import wraps

# Khởi tạo Flask app
app = Flask(__name__)

# Cấu hình database SQLite và secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'your_secret_key'

# Khởi tạo các thành phần hỗ trợ
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Kiểm tra thư mục static
if not os.path.exists("static"):
    os.makedirs("static")

# Định nghĩa model User để lưu thông tin người dùng
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    is_vip = db.Column(db.Boolean, default=False)
    vip_since = db.Column(db.DateTime, nullable=True)
    is_admin = db.Column(db.Boolean, default=False)

# Model lưu lịch sử ảnh sinh ra
class ImageHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='images')
    prompt = db.Column(db.String(500), nullable=False)
    image_url = db.Column(db.String(200), nullable=False)
    size = db.Column(db.String(20), nullable=False)
    style = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)  # Thêm nullable=False

# Load user từ ID
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Khởi tạo pipeline
pipeline = create_pipeline()

# Decorator kiểm tra quyền admin
def admin_required(f):
    @wraps(f)  # Đảm bảo giữ nguyên metadata của hàm gốc
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash("Bạn không có quyền truy cập!", "danger")
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# Quản lý người dùng
@app.route("/admin_manage_users")
@admin_required
def admin_manage_users():
    users = User.query.all()
    images = ImageHistory.query.all()
    return render_template("admin_manage_users.html", users=users, images=images)

# Xóa tài khoản
@app.route("/admin_delete_user/<int:user_id>", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("Xóa người dùng thành công", "success")
    return redirect(url_for("admin_manage_users"))

# Duyệt hoặc hủy VIP của người dùng
@app.route("/admin_toggle_vip/<int:user_id>", methods=["POST"])
@admin_required
def admin_toggle_vip(user_id):
    user = User.query.get_or_404(user_id)
    user.is_vip = not user.is_vip  # Đảo trạng thái VIP
    db.session.commit()
    flash(f"Đã cập nhật trạng thái VIP cho {user.username}.", "success")
    return redirect(url_for("admin_manage_users"))


@app.route("/")
def home_redirect():
    return redirect(url_for("home"))

@app.route("/home")
def home():
    sample_images = glob.glob("static/*.jpg")
    selected_images = random.sample(sample_images, min(len(sample_images), 10))
    return render_template("home.html", suggested_images=selected_images,
                           username=current_user.username if current_user.is_authenticated else None)


@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash("Tài khoản đã tồn tại!", "danger")
            return redirect(url_for('register'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash("Đăng ký thành công! Vui lòng đăng nhập.", "success")
        return redirect(url_for('login'))

    return render_template("register.html")


@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('generate'))
        else:
            flash("Sai tài khoản hoặc mật khẩu!", "danger")
            return redirect(url_for('login'))
    return render_template("login.html")


# @app.route("/logout")
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route("/generate", methods=['GET', 'POST'])
@login_required
def generate():
    image_path = None

    # Kiểm tra số ảnh đã tạo hôm nay
    today = date.today()
    images_today = ImageHistory.query.filter_by(user_id=current_user.id).filter(
        ImageHistory.created_at >= datetime(today.year, today.month, today.day)).count()

    if not current_user.is_vip and images_today >= 1:
        flash("Tài khoản thường chỉ có thể tạo 1 ảnh mỗi ngày. Nâng cấp VIP để không giới hạn!", "warning")
        return redirect(url_for('upgradeVIP'))

    if request.method == "POST":
        user_input = request.form.get("prompt", "")
        size = request.form.get("size", "512x512")
        style = request.form.get("style", "realistic")

        size_mapping = {"512x512": (512, 512), "1024x1024": (1024, 1024), "1280x720": (1280, 720)}
        height, width = size_mapping.get(size, (512, 512))

        im = text2img(user_input, pipeline, height, width, style)
        timestamp = int(time.time())
        image_path = f"static/generated_{current_user.id}_{timestamp}.jpg"
        im.save(image_path)

        history_entry = ImageHistory(user_id=current_user.id, prompt=user_input, image_url=image_path, size=size,
                                     style=style)
        db.session.add(history_entry)
        db.session.commit()

    history = ImageHistory.query.filter_by(user_id=current_user.id).order_by(ImageHistory.id.desc()).all()
    return render_template("generate.html", history=history, username=current_user.username, image_url=image_path)


@app.route("/upgradeVIP", methods=["GET", "POST"])
@login_required
def upgradeVIP():
    if request.method == "POST":
        if current_user.vip_since is None:  # Chỉ cập nhật nếu chưa có ngày đăng ký VIP
            current_user.vip_since = datetime.utcnow()  # Cập nhật ngày đăng ký VIP
            db.session.commit()
            flash("Yêu cầu nâng cấp VIP đã được ghi nhận. Vui lòng chờ quản trị viên xét duyệt!", "success")
        else:
            flash(f"Bạn đã gửi yêu cầu nâng cấp VIP vào ngày {current_user.vip_since.strftime('%d-%m-%Y %H:%M:%S')}!", "info")
        return redirect(url_for('generate'))
    return render_template("upgradeVIP.html", vip_since=current_user.vip_since)

@app.route("/profile")
@login_required
def profile():
    history = ImageHistory.query.filter_by(user_id=current_user.id).order_by(ImageHistory.id.desc()).all()
    return render_template("profile.html", user=current_user, history=history)

# # Tạo tài khoản admin mặc định nếu chưa có
# with app.app_context():
#     if not User.query.filter_by(username="admin").first():
#         hashed_password = bcrypt.generate_password_hash("admin123").decode('utf-8')
#         admin_user = User(username="admin", password=hashed_password, is_admin=True, is_vip=True)
#         db.session.add(admin_user)
#         db.session.commit()
#         print("Tài khoản admin đã được tạo! Đăng nhập với username: admin, password: admin123")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("Database & tables created!")  # In ra để kiểm tra
    app.run(debug=False, host='0.0.0.0', port=8888, use_reloader=False)

