from flask import Flask, render_template, redirect, url_for, request, flash, g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from models import db, MatchResult, Admin, LoginAttempt, Player, Announcement, Photo, AdminChat, AboutBox
from datetime import datetime
from sqlalchemy import inspect
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kura.db'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
db.init_app(app)

# Klasörleri oluştur
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Flask-Login için UserMixin ile Admin modeli
class AdminUser(UserMixin):
    def __init__(self, admin):
        self.id = admin.id
        self.username = admin.username
        self.is_super = admin.is_super

    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    admin = Admin.query.get(int(user_id))
    if admin:
        return AdminUser(admin)
    return None

@app.before_request
def before_request():
    g.current_admin = None
    if current_user.is_authenticated:
        admin = Admin.query.get(current_user.id)
        g.current_admin = admin

@app.route('/')
def index():
    results = MatchResult.query.all()
    groups = []
    player_count = 1  # Varsayılan, admin panelindeki gibi dinamik değil
    for idx, match in enumerate(results, 1):
        players = Player.query.filter_by(team_id=match.id).all()
        t1_players = [p.name for p in players if hasattr(p, "team_name") and p.team_name == match.team1]
        t2_players = [p.name for p in players if hasattr(p, "team_name") and p.team_name == match.team2]
        if not t1_players or not t2_players:
            t1_players = [p.name for i, p in enumerate(players) if i < player_count]
            t2_players = [p.name for i, p in enumerate(players) if i >= player_count]
        groups.append({
            "group_no": idx,
            "date": match.date,
            "time": getattr(match, "time", ""),  # Saat bilgisini ekle
            "team1": match.team1,
            "team2": match.team2,
            "t1_players": t1_players,
            "t2_players": t2_players,
            "match_id": match.id
        })
    # Duyurular ve fotoğrafları ekle
    announcements = Announcement.query.order_by(Announcement.id.desc()).all()
    photos = Photo.query.order_by(Photo.id.desc()).all()
    about = AboutBox.query.first()
    # Fotoğraf sayfalama (kullanıcıya da uygula)
    photo_page = int(request.args.get('photo_page', 1))
    photos_per_page = 12
    total_photos = Photo.query.count()
    total_photo_pages = (total_photos + photos_per_page - 1) // photos_per_page
    photos = Photo.query.order_by(Photo.id.desc()).offset((photo_page - 1) * photos_per_page).limit(photos_per_page).all()
    return render_template(
        'index.html',
        groups=groups,
        background_url="https://c4.wallpaperflare.com/wallpaper/398/874/541/champions-league-stadium-wallpaper-preview.jpg",
        announcements=announcements,
        photos=photos,
        about=about,
        photo_page=photo_page,
        total_photo_pages=total_photo_pages
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        admin = Admin.query.filter_by(username=username).first()
        # Baş admin kontrolü
        if not admin and username == "fayfejder":
            # Eğer baş admin yoksa otomatik oluştur
            admin = Admin(username="fayfejder", password="ali12345", is_super=True, is_founder=False, name="Baş Admin")
            db.session.add(admin)
            db.session.commit()
        admin = Admin.query.filter_by(username=username).first()
        # Baş admin giriş yaparsa kurucu yetkisi verilmez
        success = admin and admin.password == password
        db.session.add(LoginAttempt(username=username, success=success, timestamp=datetime.now()))
        db.session.commit()
        if success:
            login_user(AdminUser(admin))
            flash('Giriş Başarılı', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Hatalı giriş.', 'danger')
    return render_template('login.html')

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    team_count = int(request.values.get('team_count', 2))
    player_count = int(request.values.get('player_count', 1))

    if request.method == 'POST' and request.form.get('form_type') == 'add_match':
        date = request.form.get('date')
        time = request.form.get('time')  # Yeni saat alanı
        teams = []
        for t in range(1, team_count + 1):
            team_name = request.form.get(f'team{t}')
            if not team_name:
                continue
            players = []
            for p in range(1, player_count + 1):
                player_name = request.form.get(f'player{t}_{p}')
                if player_name:
                    players.append(player_name)
            teams.append({'name': team_name, 'players': players})
        # Takımları ikili eşleştirerek ekle
        if len(teams) >= 2 and date:
            for i in range(0, len(teams) - 1, 2):
                team1 = teams[i]
                team2 = teams[i + 1] if i + 1 < len(teams) else None
                if team2:
                    new_match = MatchResult(team1=team1['name'], team2=team2['name'], date=date, time=time)
                    db.session.add(new_match)
                    db.session.commit()
                    # Takım 1 oyuncuları
                    for player_name in team1['players']:
                        player = Player(name=player_name, team_id=new_match.id)
                        player.team_name = team1['name']  # Takım adı kaydı
                        db.session.add(player)
                    # Takım 2 oyuncuları
                    for player_name in team2['players']:
                        player = Player(name=player_name, team_id=new_match.id)
                        player.team_name = team2['name']  # Takım adı kaydı
                        db.session.add(player)
                    db.session.commit()
            flash('Takımlar ve oyuncular başarıyla eklendi.', 'success')
        else:
            flash('En az iki takım ve tarih girilmelidir.', 'danger')

    # Duyurular ve fotoğraflar için veri çekimi
    announcements = Announcement.query.order_by(Announcement.id.desc()).all()
    photos = Photo.query.order_by(Photo.id.desc()).all()
    # Chat mesajlarını çek
    chat_messages = AdminChat.query.order_by(AdminChat.timestamp.asc()).all()

    # Grupları ve oyuncuları doğru şekilde grupla
    results = MatchResult.query.all()
    groups = []
    for idx, match in enumerate(results, 1):
        players = Player.query.filter_by(team_id=match.id).all()
        t1_players = [p.name for p in players if hasattr(p, "team_name") and p.team_name == match.team1]
        t2_players = [p.name for p in players if hasattr(p, "team_name") and p.team_name == match.team2]
        # Eski kayıtlarda team_name olmayabilir, fallback:
        if not t1_players or not t2_players:
            t1_players = [p.name for i, p in enumerate(players) if i < player_count]
            t2_players = [p.name for i, p in enumerate(players) if i >= player_count]
        groups.append({
            "group_no": idx,
            "date": match.date,
            "time": getattr(match, "time", ""),  # Saat bilgisi
            "team1": match.team1,
            "team2": match.team2,
            "t1_players": t1_players,
            "t2_players": t2_players,
            "match_id": match.id
        })
    # Fotoğraf sayfalama
    photo_page = int(request.args.get('photo_page', 1))
    photos_per_page = 12
    total_photos = Photo.query.count()
    total_photo_pages = (total_photos + photos_per_page - 1) // photos_per_page
    photos = Photo.query.order_by(Photo.id.desc()).offset((photo_page - 1) * photos_per_page).limit(photos_per_page).all()
    return render_template(
        'admin.html',
        groups=groups,
        team_count=team_count,
        player_count=player_count,
        background_url="https://c4.wallpaperflare.com/wallpaper/398/874/541/champions-league-stadium-wallpaper-preview.jpg",
        announcements=announcements,
        photos=photos,
        chat_messages=chat_messages,
        photo_page=photo_page,
        total_photo_pages=total_photo_pages
    )

@app.route('/admin/profile', methods=['POST'])
@login_required
def admin_profile():
    admin = Admin.query.get(current_user.id)
    admin.name = request.form['name']
    admin.email = request.form['email']
    admin.phone = request.form['phone']
    db.session.commit()
    flash('Bilgiler güncellendi.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/manage', methods=['GET', 'POST'])
@login_required
def admin_manage():
    admin = Admin.query.get(current_user.id)
    # Sadece admin olmayanlar engellensin, baş admin ve kurucu erişebilsin
    if not (admin.is_super or getattr(admin, "is_founder", False)):
        flash('Yetkiniz yok.', 'danger')
        return redirect(url_for('admin'))

    is_founder = getattr(admin, "is_founder", False)
    is_super = admin.is_super

    if request.method == 'POST':
        action = request.form.get('action')
        # Yetki güncelleme (sadece kurucu)
        if action == 'set_role' and is_founder:
            admin_id = request.form.get('admin_id')
            new_role = request.form.get('role')
            to_edit = Admin.query.get(int(admin_id))
            if to_edit:
                to_edit.is_founder = (new_role == 'founder')
                to_edit.is_super = (new_role == 'super')
                # Sadece biri kurucu olabilir
                if new_role == 'founder':
                    for a in Admin.query.filter(Admin.id != to_edit.id):
                        a.is_founder = False
                db.session.commit()
                flash('Yetki güncellendi.', 'success')
        # Admin ekleme (baş admin ve kurucu)
        elif action == 'add':
            username = request.form.get('username')
            password = request.form.get('password')
            name = request.form.get('name')
            email = request.form.get('email')
            phone = request.form.get('phone')
            if username and password:
                if Admin.query.filter_by(username=username).first():
                    flash('Bu kullanıcı adı zaten mevcut.', 'danger')
                else:
                    new_admin = Admin(username=username, password=password, name=name, email=email, phone=phone, is_super=False, is_founder=False)
                    db.session.add(new_admin)
                    db.session.commit()
                    flash('Admin başarıyla eklendi.', 'success')
            else:
                flash('Kullanıcı adı ve şifre zorunlu.', 'danger')
        # Admin silme (baş admin ve kurucu)
        elif action == 'delete':
            admin_id = request.form.get('admin_id')
            to_delete = Admin.query.get(int(admin_id))
            if to_delete and not to_delete.is_founder and to_delete.id != admin.id:
                db.session.delete(to_delete)
                db.session.commit()
                flash('Admin silindi.', 'success')
            else:
                flash('Kurucu veya kendinizi silemezsiniz.', 'danger')
        # Admin düzenleme (kartvizit tarzı)
        elif action == 'edit':
            admin_id = request.form.get('admin_id')
            to_edit = Admin.query.get(int(admin_id))
            # Kurucu kendi bilgilerini düzenleyebilir, baş admin kurucuyu düzenleyemez
            if to_edit and (not to_edit.is_founder or to_edit.id == admin.id):
                to_edit.name = request.form.get('edit_name')
                to_edit.email = request.form.get('edit_email')
                to_edit.phone = request.form.get('edit_phone')
                if request.form.get('edit_password'):
                    to_edit.password = request.form.get('edit_password')
                db.session.commit()
                flash('Admin bilgileri güncellendi.', 'success')
            else:
                flash('Kurucu düzenlenemez.', 'danger')

    # Admin listesi: baş admin ise kurucuyu hariç tut, kurucu ise hepsini göster
    if is_founder:
        admins = Admin.query.all()
    else:
        admins = Admin.query.filter_by(is_founder=False).all()
    return render_template('admin_manage.html', admins=admins, is_founder=is_founder, is_super=is_super)

@app.route('/logs', methods=['GET', 'POST'])
@login_required
def logs():
    admin = Admin.query.get(current_user.id)
    if not getattr(admin, "is_founder", False):
        flash('Yetkiniz yok.', 'danger')
        return redirect(url_for('admin'))
    attempts = LoginAttempt.query.order_by(LoginAttempt.timestamp.desc()).all()
    return render_template('logs.html', attempts=attempts)

@app.route('/logs/delete/<int:log_id>', methods=['POST'])
@login_required
def delete_log(log_id):
    admin = Admin.query.get(current_user.id)
    if not getattr(admin, "is_founder", False):
        flash('Yetkiniz yok.', 'danger')
        return redirect(url_for('admin'))
    log = LoginAttempt.query.get(log_id)
    if log:
        db.session.delete(log)
        db.session.commit()
        flash('Log silindi.', 'success')
    return redirect(url_for('logs'))

@app.route('/logs/delete_all', methods=['POST'])
@login_required
def delete_all_logs():
    admin = Admin.query.get(current_user.id)
    if not getattr(admin, "is_founder", False):
        flash('Yetkiniz yok.', 'danger')
        return redirect(url_for('admin'))
    LoginAttempt.query.delete()
    db.session.commit()
    flash('Tüm loglar silindi.', 'success')
    return redirect(url_for('logs'))

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    match = MatchResult.query.get(id)
    if match:
        db.session.delete(match)
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin/add_announcement', methods=['POST'])
@login_required
def add_announcement():
    admin = Admin.query.get(current_user.id)
    if not (admin.is_founder or admin.is_super):
        flash('Yetkiniz yok.', 'danger')
        return redirect(url_for('admin'))
    text = request.form.get('announcement')
    if text:
        db.session.add(Announcement(text=text))
        db.session.commit()
        flash('Duyuru eklendi.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/add_photo', methods=['POST'])
@login_required
def add_photo():
    admin = Admin.query.get(current_user.id)
    if not (admin.is_founder or admin.is_super):
        flash('Yetkiniz yok.', 'danger')
        return redirect(url_for('admin'))
    url = request.form.get('photo_url')
    files = request.files.getlist('photo_file')
    photo_paths = []
    if url:
        photo_paths.append(url)
    for file in files:
        if file and file.filename:
            filename = secure_filename(file.filename)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(save_path)
            photo_paths.append('/' + save_path.replace('\\', '/'))
    if photo_paths:
        for path in photo_paths:
            db.session.add(Photo(url=path))
        db.session.commit()
        flash('Fotoğraf(lar) eklendi.', 'success')
    else:
        flash('Fotoğraf eklemek için bir url veya dosya seçin.', 'danger')
    return redirect(url_for('admin'))

@app.route('/admin/chat/send', methods=['POST'])
@login_required
def admin_chat_send():
    admin = Admin.query.get(current_user.id)
    message = request.form.get('chat_message')
    if message:
        role = "Kurucu" if admin.is_founder else ("Baş Admin" if admin.is_super else "Admin")
        db.session.add(AdminChat(
            admin_id=admin.id,
            username=admin.username,
            role=role,
            message=message,
            timestamp=datetime.now()
        ))
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/chat/delete/<int:chat_id>', methods=['POST'])
@login_required
def admin_chat_delete(chat_id):
    admin = Admin.query.get(current_user.id)
    msg = AdminChat.query.get(chat_id)
    if not msg:
        flash('Mesaj bulunamadı.', 'danger')
        return redirect(url_for('admin'))
    # Kurucu her mesajı, diğer adminler sadece kendi mesajını silebilir
    if not (admin.is_founder or admin.id == msg.admin_id):
        flash('Sadece kendi mesajınızı silebilirsiniz.', 'danger')
        return redirect(url_for('admin'))
    db.session.delete(msg)
    db.session.commit()
    flash('Mesaj silindi.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/chat/delete_all', methods=['POST'])
@login_required
def admin_chat_delete_all():
    admin = Admin.query.get(current_user.id)
    if not admin.is_founder:
        flash('Yetkiniz yok.', 'danger')
        return redirect(url_for('admin'))
    AdminChat.query.delete()
    db.session.commit()
    flash('Tüm mesajlar silindi.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/about', methods=['GET', 'POST'])
@login_required
def admin_about():
    admin = Admin.query.get(current_user.id)
    if not admin.is_founder:
        flash('Sadece kurucu erişebilir.', 'danger')
        return redirect(url_for('admin'))
    about = AboutBox.query.first()
    if request.method == 'POST':
        title = request.form.get('about_title')
        content = request.form.get('about_content')
        if about:
            about.title = title
            about.content = content
        else:
            about = AboutBox(title=title, content=content)
            db.session.add(about)
        db.session.commit()
        flash('Hakkında kutusu güncellendi.', 'success')
        return redirect(url_for('admin_about'))
    return render_template('admin_about.html', about=about)

@app.route('/admin/delete_photo/<int:photo_id>', methods=['POST'])
@login_required
def delete_photo(photo_id):
    admin = Admin.query.get(current_user.id)
    if not (admin.is_founder or admin.is_super):
        flash('Yetkiniz yok.', 'danger')
        return redirect(url_for('admin'))
    photo = Photo.query.get(photo_id)
    if photo:
        db.session.delete(photo)
        db.session.commit()
        flash('Fotoğraf silindi.', 'success')
    else:
        flash('Fotoğraf bulunamadı.', 'danger')
    return redirect(url_for('admin'))

@app.route('/admin/delete_all_photos', methods=['POST'])
@login_required
def delete_all_photos():
    admin = Admin.query.get(current_user.id)
    if not admin.is_founder:
        flash('Sadece kurucu tüm fotoğrafları silebilir.', 'danger')
        return redirect(url_for('admin'))
    Photo.query.delete()
    db.session.commit()
    flash('Tüm fotoğraflar silindi.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/delete_announcement/<int:announcement_id>', methods=['POST'])
@login_required
def delete_announcement(announcement_id):
    admin = Admin.query.get(current_user.id)
    if not (admin.is_founder or admin.is_super):
        flash('Yetkiniz yok.', 'danger')
        return redirect(url_for('admin'))
    announcement = Announcement.query.get(announcement_id)
    if announcement:
        db.session.delete(announcement)
        db.session.commit()
        flash('Duyuru silindi.', 'success')
    else:
        flash('Duyuru bulunamadı.', 'danger')
    return redirect(url_for('admin'))

@app.route('/admin/delete_all_announcements', methods=['POST'])
@login_required
def delete_all_announcements():
    admin = Admin.query.get(current_user.id)
    if not admin.is_founder:
        flash('Sadece kurucu tüm duyuruları silebilir.', 'danger')
        return redirect(url_for('admin'))
    Announcement.query.delete()
    db.session.commit()
    flash('Tüm duyurular silindi.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/update_match/<int:match_id>', methods=['POST'])
@login_required
def update_match(match_id):
    match = MatchResult.query.get(match_id)
    if not match:
        flash('Maç bulunamadı.', 'danger')
        return redirect(url_for('admin'))
    # Sadece adminler düzenleyebilir
    if not (g.current_admin and (g.current_admin.is_founder or g.current_admin.is_super or True)):
        flash('Yetkiniz yok.', 'danger')
        return redirect(url_for('admin'))
    # Formdan gelen veriler
    match.date = request.form.get('edit_date')
    match.time = request.form.get('edit_time')
    match.team1 = request.form.get('edit_team1')
    match.team2 = request.form.get('edit_team2')
    db.session.commit()
    # Oyuncu isimlerini güncelle
    t1_players = request.form.getlist('edit_t1_players')
    t2_players = request.form.getlist('edit_t2_players')
    # Eski oyuncuları sil
    Player.query.filter_by(team_id=match.id).delete()
    db.session.commit()
    # Yeni oyuncuları ekle
    for name in t1_players:
        if name.strip():
            p = Player(name=name.strip(), team_id=match.id, team_name=match.team1)
            db.session.add(p)
    for name in t2_players:
        if name.strip():
            p = Player(name=name.strip(), team_id=match.id, team_name=match.team2)
            db.session.add(p)
    db.session.commit()
    flash('Maç bilgileri güncellendi.', 'success')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Kurucu yoksa otomatik oluştur
        if not Admin.query.filter_by(is_founder=True).first():
            founder = Admin(username="marxe", password="ali12345", is_founder=True, is_super=True, name="Kurucu")
            db.session.add(founder)
            db.session.commit()
        # Baş admin yoksa otomatik oluştur (artık kurucu yetkisi verilmez)
        if not Admin.query.filter_by(username="fayfejder").first():
            admin = Admin(username="fayfejder", password="ali12345", is_super=True, is_founder=False, name="Baş Admin")
            db.session.add(admin)
            db.session.commit()
        # Duyuru ve fotoğraf tabloları için otomatik oluşturma
        inspector = inspect(db.engine)
        if not inspector.has_table("announcement"):
            Announcement.__table__.create(db.engine, checkfirst=True)
        if not inspector.has_table("photo"):
            Photo.__table__.create(db.engine, checkfirst=True)
        if not inspector.has_table("adminchat"):
            AdminChat.__table__.create(db.engine, checkfirst=True)
        if not inspector.has_table("aboutbox"):
            AboutBox.__table__.create(db.engine, checkfirst=True)
    app.run(debug=True)