from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.secret_key = "diecast_gizli_anahtar_123"

# Veritabanı ayarları
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///diecast.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Dosya yükleme ayarları
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# ------------------- VERİTABANI MODELLERİ -------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    arabalar = db.relationship("Araba", backref="sahip", lazy=True)

class Araba(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    isim = db.Column(db.String(100), nullable=False)
    marka = db.Column(db.String(50), nullable=False)  # YENİ: Hot Wheels / Matchbox / Diğer
    renk = db.Column(db.String(50), nullable=False)
    resim_yolu = db.Column(db.String(200), nullable=False)
    tarih = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

# ------------------- YARDIMCI FONKSİYONLAR -------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ------------------- STATİK DOSYALAR İÇİN -------------------
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory('uploads', filename)

# ------------------- ROTALAR (SAYFALAR) -------------------
@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Bu kullanıcı adı zaten alınmış!", "danger")
            return redirect(url_for("register"))
        
        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash("Kayıt başarılı! Şimdi giriş yapabilirsin.", "success")
        return redirect(url_for("login"))
    
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash(f"Hoş geldin, {username}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Kullanıcı adı veya şifre hatalı!", "danger")
    
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Çıkış yapıldı.", "info")
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    arabalar = Araba.query.filter_by(user_id=current_user.id).order_by(Araba.tarih.desc()).all()
    
    toplam_araba = len(arabalar)
    renkler = [araba.renk for araba in arabalar]
    renk_sayilari = {}
    for renk in renkler:
        renk_sayilari[renk] = renk_sayilari.get(renk, 0) + 1
    
    # YENİ: Marka istatistikleri
    markalar = [araba.marka for araba in arabalar]
    marka_sayilari = {}
    for marka in markalar:
        marka_sayilari[marka] = marka_sayilari.get(marka, 0) + 1
    
    return render_template("dashboard.html", 
                         arabalar=arabalar, 
                         toplam_araba=toplam_araba,
                         renk_sayilari=renk_sayilari,
                         marka_sayilari=marka_sayilari)

@app.route("/araba_ekle", methods=["GET", "POST"])
@login_required
def araba_ekle():
    if request.method == "POST":
        isim = request.form["isim"]
        marka = request.form["marka"]  # YENİ
        renk = request.form["renk"]
        
        if "resim" not in request.files:
            flash("Resim seçmediniz!", "danger")
            return redirect(request.url)
        
        dosya = request.files["resim"]
        
        if dosya.filename == "":
            flash("Resim seçmediniz!", "danger")
            return redirect(request.url)
        
        if not allowed_file(dosya.filename):
            flash("Sadece resim dosyaları yüklenebilir (png, jpg, jpeg, gif, webp)", "danger")
            return redirect(request.url)
        
        filename = secure_filename(f"{current_user.id}_{datetime.now().timestamp()}_{dosya.filename}")
        dosya_yolu = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        dosya.save(dosya_yolu)
        
        yeni_araba = Araba(
            isim=isim,
            marka=marka,  # YENİ
            renk=renk,
            resim_yolu=dosya_yolu,
            user_id=current_user.id
        )
        db.session.add(yeni_araba)
        db.session.commit()
        
        flash(f"{isim} başarıyla eklendi!", "success")
        return redirect(url_for("dashboard"))
    
    return render_template("araba_ekle.html")

@app.route("/araba_sil/<int:araba_id>")
@login_required
def araba_sil(araba_id):
    araba = Araba.query.get_or_404(araba_id)
    
    if araba.user_id != current_user.id:
        flash("Bu arabayı silme yetkiniz yok!", "danger")
        return redirect(url_for("dashboard"))
    
    if os.path.exists(araba.resim_yolu):
        os.remove(araba.resim_yolu)
    
    db.session.delete(araba)
    db.session.commit()
    
    flash(f"{araba.isim} silindi.", "info")
    return redirect(url_for("dashboard"))

# ------------------- UYGULAMAYI BAŞLAT -------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="0.0.0.0", port=5000)
