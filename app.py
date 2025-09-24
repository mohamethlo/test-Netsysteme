import os
import logging
import atexit
from flask import Flask
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
from extensions import db, login_manager
from flask_mail import Mail
from apscheduler.schedulers.background import BackgroundScheduler
from routes import DailyAttendanceReport, notify_due_events


# Chargement des variables d'environnement
load_dotenv()

app = Flask(__name__)

# Configurations de base
app.secret_key = os.getenv("SECRET_KEY")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configuration email
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = os.getenv('MAIL_PORT')
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS')
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')

# Configuration base de données
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv('DATABASE_URL')
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True
}

# Configure upload settings
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'

# Initialize extensions
db.init_app(app)
login_manager.init_app(app)
mail = Mail(app)

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'
login_manager.login_message_category = 'info'

def init_scheduler():
    scheduler = BackgroundScheduler()
    report_generator = DailyAttendanceReport(app)
    
    # Générer le rapport tous les jours à 11h
    scheduler.add_job(
        report_generator.generate_report,
        'cron',
        hour=10,
        minute=00,
        id='daily_attendance_report'
    )

    # MODE TEST LOCAL : Nettoyer la corbeille chaque minute
    def clean_trash_job():
        with app.app_context():  # ⬅️ important
            from routes import clean_trash
            clean_trash()

    scheduler.add_job(
        func=clean_trash_job,
        trigger="interval",
        minutes=1,
        id="clean_trash_job"
    )

    scheduler.start()

    return scheduler

def start_scheduler(app):
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=lambda: notify_due_events(app), trigger="interval", minutes=1)
    scheduler.start()

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Register blueprints
from auth import auth_bp, check_login_time
from routes import main_bp, billing

app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(billing)

@app.before_request
def before_request():
    return check_login_time()

with app.app_context():
    # Import models to ensure tables are created
    import models
    #db.drop_all()
    db.create_all()
    
    # Create default admin user if none exists
    from models import User, Role
    from werkzeug.security import generate_password_hash
    
    if not Role.query.first():
        # Create default roles
        admin_role = Role(name='Administrateur', permissions='all')
        commercial_role = Role(name='Commercial', permissions='attendance,clients,interventions')
        technician_role = Role(name='Technicien', permissions='attendance,interventions')
        dev_administration_role = Role(name='Dev_administration', permissions='attendance')
        administration_role = Role(name='administration', permissions='attendance,interventions')
        
        db.session.add(admin_role)
        db.session.add(commercial_role)
        db.session.add(technician_role)
        db.session.add(dev_administration_role)
        db.session.add(administration_role)
        db.session.commit()
    
    if not User.query.filter_by(email='admin@entreprise.fr').first():
        admin_role = Role.query.filter_by(name='Administrateur').first()
        admin_user = User(
            username='admin',
            email='admin@entreprise.fr',
            nom='Administrateur',
            prenom='Système',
            password_hash=generate_password_hash('admin123'),
            role=admin_role,
            is_active=True
        )
        db.session.add(admin_user)
        db.session.commit()
        logging.info("Default admin user created: admin@entreprise.fr / admin123")

if __name__ == '__main__':
    #if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        # Initialize scheduler
    scheduler = init_scheduler()
    #start_scheduler(app)    
        # Register scheduler shutdown
    atexit.register(lambda: scheduler.shutdown())
        
    # Run the app
    app.run(host='localhost', port=5000, debug=True)