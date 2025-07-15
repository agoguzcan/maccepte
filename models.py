from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class MatchResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team1 = db.Column(db.String(50))
    team2 = db.Column(db.String(50))
    date = db.Column(db.String(20))
    time = db.Column(db.String(10))  # Maç saati eklendi

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(128))
    is_super = db.Column(db.Boolean, default=False)  # Baş admin
    is_founder = db.Column(db.Boolean, default=False)  # Kurucu
    name = db.Column(db.String(50))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    # ...kartvizit için ek alanlar eklenebilir...

class LoginAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    success = db.Column(db.Boolean)
    timestamp = db.Column(db.DateTime)

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    team_id = db.Column(db.Integer, db.ForeignKey('match_result.id'))
    team_name = db.Column(db.String(50))  # Takım adı ekleniyor

class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(255))

class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(255))

class AdminChat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin.id'))
    username = db.Column(db.String(50))
    role = db.Column(db.String(20))  # "Kurucu", "Baş Admin", "Admin"
    message = db.Column(db.String(512))
    timestamp = db.Column(db.DateTime)

class AboutBox(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    content = db.Column(db.Text)
