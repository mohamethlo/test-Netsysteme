
from flask import Blueprint, abort, render_template, request, flash, redirect, url_for, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from geopy.distance import geodesic
#from utils import send_orange_sms, is_valid_login_time
from twilio.rest import Client as TwilioClient

from models import *
from forms import *
from utils import *
import pandas as pd
import os
from datetime import datetime, date, timedelta, time
import json
from extensions import db
from sqlalchemy import or_
from sqlalchemy import func

from flask_mail import Message
from jinja2 import Template
from extensions import mail

main_bp = Blueprint('main', __name__)

# Nouveau blueprint pour la facturation
billing = Blueprint('billing', __name__)

@main_bp.route('/')
def index():
    
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')

def get_status_badge_class(statut):
    if statut == 'en_attente':
        return 'bg-warning text-dark'
    elif statut == 'approuve':
        return 'bg-success'
    elif statut == 'refuse':
        return 'bg-danger'
    return 'bg-secondary'

def client_to_dict(client):
    return {
        "id": client.id,
        "nom": client.nom,
        "prenom": client.prenom,
        "type_client": client.type_client,
        # Ajoute d'autres champs si besoin
    }

@main_bp.route('/dashboard')
@login_required
def dashboard():
    
    # Get dashboard statistics based on user role
    stats = {}

    # Statistiques commerciaux (pour admin ou commercial)
    if current_user.has_permission('all') or (current_user.role.name == 'Commercial'):
    # Récupère tous les commerciaux actifs
        commerciaux = User.query.join(Role).filter(Role.name == 'Commercial', User.is_active == True).all()
        stats_commerciaux = []
        for c in commerciaux:
            nb_prospects = Client.query.filter_by(assigned_to=c.id, type_client='prospect', is_blacklisted=False).count()
            nb_convertis = Client.query.filter_by(assigned_to=c.id, type_client='client', is_blacklisted=False).count()
            total = nb_prospects + nb_convertis
            taux = int((nb_convertis / total) * 100) if total > 0 else 0
            stats_commerciaux.append({
                "id": c.id,
                "prenom": c.prenom,
                "nom": c.nom,
                "nb_prospects": nb_prospects,
                "nb_convertis": nb_convertis,
                "taux": taux
            })
    # Pour admin : classement, pour commercial : ses stats uniquement
    if current_user.has_permission('all'):
        stats['stats_commerciaux'] = sorted(stats_commerciaux, key=lambda x: x['nb_convertis'], reverse=True)
    elif current_user.role.name == 'Commercial':
        stats['stats_commerciaux'] = [s for s in stats_commerciaux if s['id'] == current_user.id]
    
    # ...dans la fonction dashboard...
    if current_user.has_permission('all'):
        # Récupère tous les techniciens actifs
        techniciens = User.query.join(Role).filter(Role.name == 'Technicien', User.is_active == True).all()
        # Pour chaque technicien, calcule le taux de présence (jours pointés / jours ouvrés)

        # Période d'analyse (ex: ce mois)
        start_of_month = date.today().replace(day=1)
        today = date.today()
        total_days = (today - start_of_month).days + 1

        technicien_stats = []
        for t in techniciens:
            nb_presences = Attendance.query.filter(
                Attendance.user_id == t.id,
                Attendance.date >= start_of_month,
                Attendance.check_in.isnot(None)
            ).count()
            taux = int((nb_presences / total_days) * 100) if total_days > 0 else 0
            nb_interventions = Intervention.query.filter(
                Intervention.technicien_id == t.id,
                Intervention.statut == 'terminee'
            ).count()
            technicien_stats.append({
                "prenom": t.prenom,
                "nom": t.nom,
                "taux": taux,
                "interventions": nb_interventions
            })
        stats['technicien_stats'] = technicien_stats
    else:
        stats['technicien_stats'] = None    

    if current_user.has_permission('attendance'):
        # Today's attendance
        today_attendance = Attendance.query.filter_by(
            user_id=current_user.id,
            date=date.today()
        ).first()
        stats['today_attendance'] = today_attendance
        
        # This month's attendance
        start_of_month = date.today().replace(day=1)
        monthly_attendance = Attendance.query.filter(
            Attendance.user_id == current_user.id,
            Attendance.date >= start_of_month
        ).count()
        stats['monthly_attendance'] = monthly_attendance
    
    if current_user.has_permission('interventions'):
        if current_user.has_permission('all'):
            # Admin : toutes les interventions du jour
            today_interventions = Intervention.query.filter(
                Intervention.date_prevue >= datetime.combine(date.today(), datetime.min.time()),
                Intervention.date_prevue < datetime.combine(date.today() + timedelta(days=1), datetime.min.time())
            ).count()
            # Admin : toutes les interventions en attente
            pending_interventions = Intervention.query.filter(
                Intervention.statut == 'planifiee'
            ).count()
        else:
            # Technicien : seulement ses interventions
            today_interventions = Intervention.query.filter(
                Intervention.technicien_id == current_user.id,
                Intervention.date_prevue >= datetime.combine(date.today(), datetime.min.time()),
                Intervention.date_prevue < datetime.combine(date.today() + timedelta(days=1), datetime.min.time())
            ).count()
            pending_interventions = Intervention.query.filter(
                Intervention.technicien_id == current_user.id,
                Intervention.statut == 'planifiee'
            ).count()
        stats['today_interventions'] = today_interventions
        stats['pending_interventions'] = pending_interventions
    
    if current_user.has_permission('clients'):
        if current_user.role.name == 'Commercial':
            stats['total_clients'] = Client.query.filter_by(type_client='client', assigned_to=current_user.id, is_blacklisted=False).count()
            stats['prospects'] = Client.query.filter_by(type_client='prospect', assigned_to=current_user.id, is_blacklisted=False).count()
        else:
            stats['total_clients'] = Client.query.filter_by(type_client='client', is_blacklisted=False).count()
            stats['prospects'] = Client.query.filter_by(type_client='prospect', is_blacklisted=False).count()
    
    if current_user.has_permission('inventory'):
        low_stock_items = InventoryItem.query.filter(
            InventoryItem.quantity <= InventoryItem.seuil_alerte
        ).count()
        stats['low_stock_items'] = low_stock_items
    
    # Unread messages
    unread_messages = NotificationModel.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    stats['unread_messages'] = unread_messages

    # Classement des commerciaux par nombre de notes d'observation
    top_commerciaux = (
        db.session.query(User, func.count(Reminder.id).label('nb_notes'))
        .join(Reminder, Reminder.user_id == User.id)
        .group_by(User.id)
        .order_by(func.count(Reminder.id).desc())
        .all()
    )
    for user, nb_notes in top_commerciaux:
        user.notes = [
        {
            "texte": r.notes,
            "date": r.remind_at.strftime('%Y-%m-%d') if r.remind_at else "",
            "client": client_to_dict(r.client) if r.client else None
        }
        for r in Reminder.query.filter_by(user_id=user.id).order_by(Reminder.remind_at.desc()).all()
    ]
    return render_template('dashboard.html', stats=stats,top_commerciaux=top_commerciaux)
 
@main_bp.route('/attendance')
@login_required
def attendance():
    if not current_user.has_permission('attendance'):
        flash('Vous n\'avez pas accès à cette section.', 'error')
        return redirect(url_for('main.dashboard'))
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Nombre d'entrées par page   
    is_late = False
    need_justification = False
    # Récupérer le pointage du jour pour TOUS les utilisateurs (même admin)
    today_attendance = Attendance.query.filter_by(
        user_id=current_user.id,
        date=date.today()
    ).first()

    # Si admin ou Respo administration, voir tout l'historique de tous les utilisateurs
    if current_user.has_permission('all') or (current_user.role.name == 'administration'):
        pagination = Attendance.query.order_by(Attendance.date.desc()).paginate(page=page, per_page=per_page, error_out=False)
        attendances = pagination.items
        #today_attendance = None# Optionnel : tu peux afficher un résumé global ou rien
    else:
        pagination = Attendance.query.filter_by(user_id=current_user.id).order_by(Attendance.date.desc()).paginate(page=page, per_page=per_page, error_out=False)
        attendances = pagination.items
    
    if today_attendance and today_attendance.check_in:
        from datetime import time
        heure_limite = time(9, 15)
        if today_attendance.check_in.time() > heure_limite:
            is_late = True
                 # Vérifie si la justification existe déjà
            if not today_attendance.notes or not today_attendance.notes.strip():
                need_justification = True

    # Get work locations
    work_locations_data = []
    work_locations = WorkLocation.query.filter_by(is_active=True).all()
    for location in work_locations:
        work_locations_data.append({
            'id': location.id,
            'name': location.name,
            'latitude': location.latitude,
            'longitude': location.longitude,
            'radius': location.radius,
            'address': location.address
        })

    # Si admin ou Respo administration, calculer présents/absents/retards pour aujourd'hui
    presents = absents = retards = None
    if current_user.has_permission('all') or (current_user.role.name == 'administration'):
        from datetime import time
        heure_limite = time(9, 15)
        today = date.today()
        users = User.query.filter_by(is_active=True).all()
        attendances_today = {a.user_id: a for a in Attendance.query.filter_by(date=today).all()}
        presents = []
        absents = []
        retards = []
        for user in users:
            attendance = attendances_today.get(user.id)
            if attendance and attendance.check_in:
                presents.append(user)
                if attendance.check_in.time() > heure_limite:
                    retards.append(user)
            else:
                absents.append(user)

    return render_template(
        'attendance.html',
        attendances=attendances,
        pagination=pagination,
        today_attendance=today_attendance,
        is_late=is_late,
        need_justification=need_justification,
        work_locations=work_locations_data,
        get_status_badge_class=get_status_badge_class,
        presents=presents,
        absents=absents,
        current_date=date.today(),
        retards=retards
    )
     

@main_bp.route('/gestion_rh')
@login_required
def gestion_rh():
    """
    Page Gestion RH avec sidebar et onglets
    """
    if not (current_user.has_permission('attendance') or
            current_user.has_permission('salary_advances') or
            current_user.has_permission('work_locations') or
            current_user.has_permission('all')):
        flash("Vous n'avez pas accès à cette section.", "error")
        return redirect(url_for('main.dashboard'))

    # --- Données pour l'onglet Pointage ---
    page = request.args.get('page', 1, type=int)
    per_page = 10
    is_late = False
    need_justification = False

    today_attendance = Attendance.query.filter_by(
        user_id=current_user.id,
        date=date.today()
    ).first()

    if current_user.has_permission('all') or (current_user.role.name == 'administration'):
        pagination = Attendance.query.order_by(Attendance.date.desc()).paginate(page=page, per_page=per_page, error_out=False)
        attendances = pagination.items
    else:
        pagination = Attendance.query.filter_by(user_id=current_user.id).order_by(Attendance.date.desc()).paginate(page=page, per_page=per_page, error_out=False)
        attendances = pagination.items

    if today_attendance and today_attendance.check_in:
        from datetime import time
        heure_limite = time(9, 15)
        if today_attendance.check_in.time() > heure_limite:
            is_late = True
            if not today_attendance.notes or not today_attendance.notes.strip():
                need_justification = True

    presents = absents = retards = None
    if current_user.has_permission('all') or (current_user.role.name == 'administration'):
        from datetime import time
        heure_limite = time(9, 15)
        today = date.today()
        users = User.query.filter_by(is_active=True).all()
        attendances_today = {a.user_id: a for a in Attendance.query.filter_by(date=today).all()}
        presents = []
        absents = []
        retards = []
        for user in users:
            attendance = attendances_today.get(user.id)
            if attendance and attendance.check_in:
                presents.append(user)
                if attendance.check_in.time() > heure_limite:
                    retards.append(user)
            else:
                absents.append(user)

    return render_template(
        'gestion_rh.html',
        # Données Pointage
        attendances=attendances,
        pagination=pagination,
        today_attendance=today_attendance,
        is_late=is_late,
        need_justification=need_justification,
        presents=presents,
        absents=absents,
        retards=retards,
        current_date=date.today(),
        time=time
    )

@main_bp.route('/gestion_commercial')
@login_required
def gestion_commercial():
    # On pourra vérifier les permissions plus tard si besoin
    return render_template('gestion_commercial.html')


@main_bp.route('/gestion_comptable')
@login_required
def gestion_comptable():
    # On pourra vérifier les permissions plus tard si besoin
    return render_template('gestion_comptable.html')


@main_bp.route('/gestion_interventions')
@login_required
def gestion_interventions():
    return render_template('gestion_interventions.html')


@main_bp.route('/check_in', methods=['POST'])
@login_required
def check_in():
    if not current_user.has_permission('attendance'):
        return jsonify({'success': False, 'message': 'Accès refusé'})

    data = request.get_json()
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    location_name = data.get('location_name')  # Peut être None si zone déjà trouvée

    if latitude is None or longitude is None:
        return jsonify({'success': False, 'message': 'Coordonnées manquantes'})

    # Rayon fixe en mètres
    RAYON = 100

    # Cherche une zone existante dans le rayon
    work_locations = WorkLocation.query.filter_by(is_active=True).all()
    found_location = None
    for loc in work_locations:
        distance = geodesic((latitude, longitude), (loc.latitude, loc.longitude)).meters
        if distance <= RAYON:
            found_location = loc
            break

    # Si aucune zone trouvée, il faut un nom pour créer la zone
    if not found_location:
        if not location_name or not location_name.strip():
            return jsonify({'success': False, 'need_zone_name': True, 'message': 'Aucune zone trouvée, veuillez saisir un nom pour ce lieu.'})
        # Vérifie unicité du nom
        if WorkLocation.query.filter_by(name=location_name.strip()).first():
            return jsonify({'success': False, 'message': 'Ce nom de zone existe déjà, choisissez-en un autre.'})
        # Crée la nouvelle zone
        found_location = WorkLocation(
            name=location_name.strip(),
            latitude=latitude,
            longitude=longitude,
            radius=RAYON,
            is_active=True,
            type="chantier"  # ou "chantier", à adapter si tu veux demander le type
        )
        db.session.add(found_location)
        db.session.commit()

    # Check if user already checked in today
    today_attendance = Attendance.query.filter_by(
        user_id=current_user.id,
        date=date.today()
    ).first()

    if today_attendance and today_attendance.check_in:
        return jsonify({'success': False, 'message': 'Vous êtes déjà pointé aujourd\'hui'})

    # Enregistre le pointage
    if today_attendance:
        today_attendance.check_in = datetime.utcnow()
        today_attendance.check_in_location = found_location.name
        today_attendance.check_in_lat = latitude
        today_attendance.check_in_lng = longitude
        today_attendance.work_location_id = found_location.id
    else:
        today_attendance = Attendance(
            user_id=current_user.id,
            check_in=datetime.utcnow(),
            check_in_location=found_location.name,
            check_in_lat=latitude,
            check_in_lng=longitude,
            work_location_id=found_location.id
        )
        db.session.add(today_attendance)

    db.session.commit()

    return jsonify({'success': True, 'message': f'Pointage enregistré à {found_location.name}.'})
 
@main_bp.route('/check_out', methods=['POST'])
@login_required
def check_out():
    
    if not current_user.has_permission('attendance'):
        return jsonify({'success': False, 'message': 'Accès refusé'})
    
    data = request.get_json()
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    location_name = data.get('location', 'Position inconnue')
    
    # Get today's attendance
    today_attendance = Attendance.query.filter_by(
        user_id=current_user.id,
        date=date.today()
    ).first()
    
    if not today_attendance or not today_attendance.check_in:
        return jsonify({'success': False, 'message': 'Vous devez d\'abord pointer votre entrée'})
    
    if today_attendance.check_out:
        return jsonify({'success': False, 'message': 'Vous avez déjà pointé votre sortie aujourd\'hui'})
    # Vérification de la zone
    if location_name != today_attendance.check_in_location:
        return jsonify({'success': False, 'message': 'La zone de sortie ne correspond pas à celle de l\'entrée. Veuillez pointer votre sortie dans la même zone.'})
    
    # Update attendance record
    today_attendance.check_out = datetime.utcnow()
    today_attendance.check_out_location = location_name
    today_attendance.check_out_lat = latitude
    today_attendance.check_out_lng = longitude
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Pointage de sortie enregistré avec succès'})


@main_bp.route('/interventions')
@login_required
def interventions():
    if not current_user.has_permission('interventions'):
        flash('Vous n\'avez pas accès à cette section.', 'error')
        return redirect(url_for('main.dashboard'))

    # Base query with role-based filtering
    if current_user.role.name == 'Technicien':
        query = Intervention.query.filter_by(technicien_id=current_user.id)
    else:
        query = Intervention.query

    # Search and filters
    search = request.args.get('q', '')
    status = request.args.get('status', '')
    priority = request.args.get('priority', '')
    type_intervention = request.args.get('type', '')

    # Apply search filters
    if search:
        query = query.join(Client).filter(
            or_(
                Intervention.titre.ilike(f'%{search}%'),
                Intervention.description.ilike(f'%{search}%'),
                Client.nom.ilike(f'%{search}%'),
                Client.prenom.ilike(f'%{search}%'),
                Client.entreprise.ilike(f'%{search}%')
            )
        )

    # Apply status filter
    if status:
        query = query.filter(Intervention.statut == status)

    # Apply priority filter
    if priority:
        query = query.filter(Intervention.priorite == priority)

    # Apply type filter
    if type_intervention:
        query = query.filter(Intervention.type_intervention == type_intervention)
    
    date_filter = request.args.get('date', '')
    if date_filter == 'today':
        today = date.today()
        query = query.filter(
            Intervention.date_prevue >= datetime.combine(today, datetime.min.time()),
            Intervention.date_prevue < datetime.combine(today + timedelta(days=1), datetime.min.time())
        )
    # Order by date and paginate
    interventions= query.order_by(Intervention.date_prevue.desc()).all()
   # pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Get data for forms
    clients = Client.query.filter_by(type_client='client').all()
    technicians = User.query.join(Role).filter(Role.name == 'Technicien').all()
    articles = InventoryItem.query.filter(InventoryItem.quantity > 0).all()
    

    return render_template(
        'interventions.html',
        interventions=interventions,
        pagination=None,
        clients=clients,
        technicians=technicians,
        articles=articles,
        get_priority_badge_class=get_priority_badge_class,
        get_status_badge_class=get_status_badge_class
    )

@main_bp.route('/add_intervention', methods=['POST'])
@login_required
def add_intervention():
    if not current_user.has_permission('interventions'):
        flash('Vous n\'avez pas accès à cette fonctionnalité.', 'error')
        return redirect(url_for('main.interventions'))
    
    try:
        # Récupération des données du formulaire
        description = request.form.get('description')
        client_libre_toggle = request.form.get('client_libre_toggle')
        technicien_id = request.form.get('technicien_id')
        date_prevue = request.form.get('date_prevue')
        duree_estimee = request.form.get('duree_estimee')
        priorite = request.form.get('priorite', 'normale')
        adresse = request.form.get('adresse')
        type_intervention = request.form.get('type_intervention')
        
        # Création de l'intervention
        intervention_data = {
            'description': description,
            'technicien_id': int(technicien_id) if technicien_id else None,
            'date_prevue': datetime.fromisoformat(date_prevue),
            'duree_estimee': int(duree_estimee) if duree_estimee else None,
            'priorite': priorite,
            'adresse': adresse,
            'type_intervention': type_intervention,
            'created_by_id': current_user.id
        }

        # Gestion client libre ou existant
        if client_libre_toggle:
            intervention_data.update({
                'client_libre_nom': request.form.get('client_libre_nom'),
                'client_libre_telephone': request.form.get('client_libre_telephone'),
            })
            client_info = f"{request.form.get('client_libre_nom')} (Tél: {request.form.get('client_libre_telephone')})"
        else:
            client_id = request.form.get('client_id')
            if not client_id:
                flash('Veuillez sélectionner un client.', 'error')
                return redirect(url_for('main.interventions'))
            
            intervention_data['client_id'] = int(client_id)
            client = Client.query.get(int(client_id))
            client_info = f"{client.nom} {client.prenom or ''}"
            if client.entreprise:
                client_info += f" - {client.entreprise}"
            if client.telephone:
                client_info += f" (Tél: {client.telephone})"

        # Création et sauvegarde de l'intervention
        intervention = Intervention(**intervention_data)
        db.session.add(intervention)
        db.session.flush()

        # Gestion des matériels
        article_ids = request.form.getlist('articles')
        materiels_requis = []
        erreur_stock = False
        
        for article_id in article_ids:
            quantite = int(request.form.get(f'quantite_{article_id}', 0))
            article = InventoryItem.query.get(int(article_id))
            if article and quantite > 0:
                if quantite > article.quantity:
                    erreur_stock = True
                    flash(f"Stock insuffisant pour {article.name} (disponible : {article.quantity})", "error")
                    continue
                
                materiel = InterventionMaterial(
                    intervention_id=intervention.id,
                    article_id=article.id,
                    quantite=quantite
                )
                db.session.add(materiel)
                article.quantity -= quantite
                materiels_requis.append(f"- {article.name}: {quantite} {article.unit}")

        if erreur_stock:
            db.session.rollback()
            return redirect(url_for('main.interventions'))

        # Envoi de l'email au technicien
        if technicien_id:
            technicien = User.query.get(int(technicien_id))
            planificateur = f"{current_user.prenom} {current_user.nom}"

            # Construction du message
            message = f"""Bonjour {technicien.prenom},

            Une nouvelle intervention a été planifiée pour vous :

            Client : {client_info}
            Date prévue : {date_prevue}
            Type : {type_intervention}
            Priorité : {priorite}
            Adresse : {adresse}
            Description : {description}

            Durée estimée : {duree_estimee} minutes

            Matériel requis :
            {chr(10).join(materiels_requis)}

            Planifié par : {planificateur}"""

            # Envoi de l'email
            send_email(
                subject=f"Nouvelle intervention planifiée - {date_prevue}",
                recipients=[technicien.email, "diazfaye82@gmail.com"],
                body=message
            )
            # Envoi du SMS Orange au technicien
            if technicien.telephone:  
                sender_tel = current_user.telephone if current_user.telephone else "+221775561233"
                sms_result = send_orange_sms(
                    to=technicien.telephone,
                    message=message,
                    sender=sender_tel
                )
                if sms_result:
                    print(f"SMS Orange envoyé avec succès à {technicien.telephone}", flush=True)
                else:
                    print(f"Échec de l'envoi du SMS Orange à {technicien.telephone}", flush=True)

            # Création d'une notification interne
            notif = create_notification(
                user_id=technicien.id,
                message=f"Nouvelle intervention planifiée pour le {date_prevue}"
            )
            db.session.add(notif)

        db.session.commit()
        flash('Intervention créée avec succès.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Erreur lors de la création de l\'intervention.', 'error')
        #logging.error(f"Erreur création intervention: {str(e)}")
    
    return redirect(url_for('main.interventions'))
    


@main_bp.route('/intervention/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_intervention(id):
    intervention = Intervention.query.get_or_404(id)
    form = InterventionForm(obj=intervention)

    clients = Client.query.all()
    technicians = User.query.join(Role).filter(Role.name == 'Technicien').all()

    form.client_id.choices = [(c.id, f"{c.nom} {c.prenom or ''}") for c in clients]
    form.technicien_id.choices = [(u.id, f"{u.prenom} {u.nom}") for u in technicians]
    form.autres_intervenants.choices = [(u.id, f"{u.prenom} {u.nom}") for u in technicians]

    if form.validate_on_submit():
        autres_intervenants_data = form.autres_intervenants.data
        del form.autres_intervenants

        form.populate_obj(intervention)
        intervention.autres_intervenants = User.query.filter(User.id.in_(autres_intervenants_data or [])).all()
        
        # Gestion signature et heure de départ
        signature_data = request.form.get('signature_data')
        intervention.signature_data = signature_data
        
        # Si signature présente mais heure_depart non envoyée (cas où le formulaire est soumis par script)
        if signature_data and not form.heure_depart.data:
            now = datetime.now()
            intervention.heure_depart = now.time()
            intervention.date_realisation = now
        
        intervention.statut = 'terminee'
        
        # Calcul durée
        if intervention.heure_arrivee and intervention.heure_depart:
            arrivee = datetime.combine(intervention.date_realisation.date(), intervention.heure_arrivee)
            depart = datetime.combine(intervention.date_realisation.date(), intervention.heure_depart)
            
            if depart < arrivee:
                depart += timedelta(days=1)
            
            duree = depart - arrivee
            intervention.duree_intervention = (datetime.min + duree).time()
        
        db.session.commit()
        flash("Intervention terminée avec succès", "success")
        return redirect(url_for('main.interventions'))

    # Pré-remplir les intervenants
    if intervention.autres_intervenants:
        form.autres_intervenants.data = [u.id for u in intervention.autres_intervenants]

    return render_template(
        'edit_intervention.html',
        form=form,
        intervention=intervention,
        clients=clients,
        technicians=technicians
    )

@main_bp.route('/intervention/<int:id>/fiche')
@login_required
def intervention_detail(id):
    intervention = Intervention.query.get_or_404(id)
    # return render_template('intervention_detail.html',
    return render_template('fiche_intervention.html',
                            intervention=intervention,
                            get_status_badge_class=get_status_badge_class,
                            get_priority_badge_class=get_priority_badge_class)

@main_bp.route('/inventory')
@login_required
def inventory():
    
    if not current_user.has_permission('inventory'):
        flash('Vous n\'avez pas accès à cette section.', 'error')
        return redirect(url_for('main.dashboard'))
    
    items = InventoryItem.query.order_by(InventoryItem.name).all()
    categories = InventoryCategory.query.order_by(InventoryCategory.name).all()
    
    return render_template('inventory.html', items=items, categories=categories)

@main_bp.route('/add_inventory_item', methods=['POST'])
@login_required
def add_inventory_item():
    if not current_user.has_permission('inventory'):
        flash('Vous n\'avez pas accès à cette fonctionnalité.', 'error')
        return redirect(url_for('main.inventory'))

    # Gestion du fichier image
    image_path = None
    image_file = request.files['image']
    if image_file and image_file.filename:
            # Configuration du dossier d'upload
            static_path = current_app.static_folder
            upload_folder = os.path.join(static_path, 'uploads', 'inventory')
            os.makedirs(upload_folder, exist_ok=True)
            
            # Sécurisation et sauvegarde du fichier
            filename = secure_filename(image_file.filename)
            file_path = os.path.join(upload_folder, filename)
            
            try:
                image_file.save(file_path)
                image_path = f"uploads/inventory/{filename}"  # Chemin relatif
            except Exception as e:
                current_app.logger.error(f"Erreur sauvegarde image: {str(e)}")
                flash("Erreur lors de l'enregistrement de l'image", "error")

    try:
        item = InventoryItem(
            name=request.form.get('name'),
            description=request.form.get('description'),
            reference=request.form.get('reference'),
            category_id=int(request.form.get('category_id')) if request.form.get('category_id') else None,
            quantity=int(request.form.get('quantity', 0)),
            unit=request.form.get('unit', 'pièce'),
            prix_achat=float(request.form.get('prix_achat')) if request.form.get('prix_achat') else None,
            prix_vente=float(request.form.get('prix_vente')) if request.form.get('prix_vente') else None,
            seuil_alerte=int(request.form.get('seuil_alerte', 10)),
            fournisseur=request.form.get('fournisseur'),
            emplacement=request.form.get('emplacement'),
            image_path=image_path  # Ajout du chemin de l'image
        )

        db.session.add(item)
        db.session.commit()
        flash('Article ajouté avec succès.', 'success')
    except ValueError:
        db.session.rollback()
        flash('Erreur de format dans les données numériques.', 'error')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur ajout article: {str(e)}")
        flash('Erreur lors de l\'ajout de l\'article.', 'error')

    return redirect(url_for('main.inventory'))
@main_bp.route('/inventory/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_inventory_item(item_id):
    if not current_user.has_permission('inventory'):
        flash('Permission refusée', 'danger')
        return redirect(url_for('main.inventory'))

    item = InventoryItem.query.get_or_404(item_id)
    categories = InventoryCategory.query.order_by(InventoryCategory.name).all()

    if request.method == 'POST':
        try:
            image_file = request.files['image']
            if image_file and image_file.filename:
                    # Suppression ancienne image si elle existe
                    if item.image_path:
                        old_path = os.path.join(current_app.static_folder, item.image_path)
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    
                    # Sauvegarde nouvelle image
                    static_path = current_app.static_folder
                    upload_folder = os.path.join(static_path, 'uploads', 'inventory')
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    filename = secure_filename(image_file.filename)
                    file_path = os.path.join(upload_folder, filename)
                    image_file.save(file_path)
                    item.image_path = f"uploads/inventory/{filename}"
            item.name = request.form.get('name', item.name)
            item.reference = request.form.get('reference', item.reference)
            item.description = request.form.get('description', item.description)
            item.category_id = request.form.get('category_id') or None
            item.unit = request.form.get('unit', item.unit)
            item.prix_achat = float(request.form.get('prix_achat', 0)) if request.form.get('prix_achat') else None
            item.prix_vente = float(request.form.get('prix_vente', 0)) if request.form.get('prix_vente') else None
            item.seuil_alerte = int(request.form.get('seuil_alerte', item.seuil_alerte))
            item.fournisseur = request.form.get('fournisseur', item.fournisseur)
            item.emplacement = request.form.get('emplacement', item.emplacement)

            db.session.commit()
            flash('Article mis à jour avec succès', 'success')
            return redirect(url_for('main.inventory'))
        except ValueError as e:
            db.session.rollback()
            flash(f'Erreur de saisie: {str(e)}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la mise à jour: {str(e)}', 'danger')

    return render_template('edit_inventory_item.html', 
                         item=item, 
                         categories=categories)



@main_bp.route('/inventory/delete/<int:item_id>', methods=['POST'])
@login_required
def delete_inventory_item(item_id):
    if not current_user.has_permission('inventory'):
        return jsonify({'success': False, 'message': 'Permission refusée'}), 403

    item = InventoryItem.query.get_or_404(item_id)
    
    try:
        # Suppression de l'image associée si elle existe
        if item.image_path:
            image_path = os.path.join(current_app.static_folder, item.image_path)
            if os.path.exists(image_path):
                os.remove(image_path)
        
        db.session.delete(item)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Article supprimé avec succès'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur suppression article: {str(e)}")
        return jsonify({'success': False, 'message': 'Erreur lors de la suppression'}), 500

""" 
@main_bp.route('/expenses')
@login_required
def expenses():
    
    if not current_user.has_permission('expenses'):
        flash('Vous n\'avez pas accès à cette section.', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Get expenses based on user role
    if current_user.role.name == 'Administrateur' or (current_user.role.name == 'administration' and current_user.has_permission('expenses')):
        expenses = Expense.query.order_by(Expense.created_at.desc()).all()
        total_appro = db.session.query(db.func.sum(Approvisionnement.montant)).scalar() or 0
        total_depenses = db.session.query(db.func.sum(Expense.montant)).filter(Expense.statut == 'approuve').scalar() or 0
        montant_restant = total_appro - total_depenses
    else:
        expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.created_at.desc()).all()
    
    return render_template(
        'expenses.html',
        expenses=expenses,
        montant_restant=montant_restant,
        total_appro=total_appro,
        get_status_badge_class=get_status_badge_class  # <-- Ajoute ceci
    )
 """
@main_bp.route('/expenses')
@login_required
def expenses():
    if not current_user.has_permission('expenses'):
        flash('Vous n\'avez pas accès à cette section.', 'error')
        return redirect(url_for('main.dashboard'))

    # Administrateur général : voir tous les sites
    if current_user.role.name == 'Administrateur':
        expenses = Expense.query.filter(Expense.deleted_at.is_(None))\
                                .order_by(Expense.created_at.desc()).all()
        sites = ['Dakar', 'Mbour']
        site_stats = []
        for site in sites:
            total_appro = db.session.query(db.func.sum(Approvisionnement.montant))\
                                    .filter(Approvisionnement.site == site).scalar() or 0
            total_depenses = db.session.query(db.func.sum(Expense.montant))\
                                       .filter(Expense.statut == 'approuve',
                                               Expense.site == site,
                                               Expense.deleted_at.is_(None)).scalar() or 0
            montant_restant = total_appro - total_depenses
            site_stats.append({
                'site': site,
                'total_appro': total_appro,
                'total_depenses': total_depenses,
                'montant_restant': montant_restant
            })
        return render_template(
            'expenses.html',
            expenses=expenses,
            site_stats=site_stats,
            get_status_badge_class=get_status_badge_class
        )

    # Administration : voir uniquement son site
    elif current_user.role.name == 'administration' and current_user.has_permission('expenses'):
        expenses = Expense.query.filter_by(site=current_user.site)\
                                .filter(Expense.deleted_at.is_(None))\
                                .order_by(Expense.created_at.desc()).all()
        total_appro = db.session.query(db.func.sum(Approvisionnement.montant))\
                                .filter(Approvisionnement.site == current_user.site).scalar() or 0
        total_depenses = db.session.query(db.func.sum(Expense.montant))\
                                   .filter(Expense.statut == 'approuve',
                                           Expense.site == current_user.site,
                                           Expense.deleted_at.is_(None)).scalar() or 0
        montant_restant = total_appro - total_depenses
        return render_template(
            'expenses.html',
            expenses=expenses,
            montant_restant=montant_restant,
            total_depenses=total_depenses,
            site=current_user.site,
            get_status_badge_class=get_status_badge_class
        )

    # Employé : ne voit que ses propres dépenses
    else:
        expenses = Expense.query.filter_by(user_id=current_user.id)\
                                .filter(Expense.deleted_at.is_(None))\
                                .order_by(Expense.created_at.desc()).all()
        montant_restant = 0
        total_depenses = 0
        return render_template(
            'expenses.html',
            expenses=expenses,
            montant_restant=montant_restant,
            total_depenses=total_depenses,
            site=getattr(current_user, "site", None),
            get_status_badge_class=get_status_badge_class
        )
    
@main_bp.route('/add_expense/<site>', methods=['POST'])
@login_required
def add_expense(site):
    if not current_user.has_permission('expenses'):
        flash('Vous n\'avez pas accès à cette fonctionnalité.', 'error')
        return redirect(url_for('main.expenses_by_site', site=site))

    facture_file = request.files.get('facture')
    justificatif = None
    static_path = current_app.static_folder
    upload_folder = os.path.join(static_path, 'uploads', 'factures')
    os.makedirs(upload_folder, exist_ok=True)

    if facture_file and facture_file.filename:
        filename = secure_filename(facture_file.filename)
        file_path = os.path.join(upload_folder, filename)
        facture_file.save(file_path)
        justificatif = f"uploads/factures/{filename}"

    titre = request.form.get('titre')
    description = request.form.get('description')
    montant = request.form.get('montant')
    categorie = request.form.get('categorie')
    date_depense = request.form.get('date_depense')

    try:
        expense = Expense(
            user_id=current_user.id,
            titre=titre,
            description=description,
            montant=float(montant),
            categorie=categorie,
            date_depense=datetime.strptime(date_depense, '%Y-%m-%d').date() if date_depense else date.today(),
            justificatif=justificatif,
            site=site,
            statut='en_attente',
        )
        db.session.add(expense)
        db.session.commit()
        flash('Dépense ajoutée avec succès.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Erreur lors de l\'ajout de la dépense.', 'error')

    return redirect(url_for('main.expenses_by_site', site=site))

@main_bp.route('/clients')
@login_required
def clients():
    from sqlalchemy.orm import joinedload
    page = request.args.get('page', 1, type=int)
    per_page = 20 
    if not current_user.has_permission('clients'):
        flash('Vous n\'avez pas accès à cette section.', 'error')
        return redirect(url_for('main.dashboard'))
    assign_clients_by_notes()
    # Si l'utilisateur est commercial, il ne voit que ses clients
    if current_user.role.name == 'Commercial':
        clients = Client.query.filter_by(assigned_to=current_user.id, is_blacklisted=False).order_by(Client.created_at.desc(), Client.nom).all()
        query = Client.query.filter_by(assigned_to=current_user.id, is_blacklisted=False)
    else:
        clients = Client.query.filter_by(is_blacklisted=False).order_by(Client.created_at.desc(), Client.nom).all()
        query = Client.query.filter_by(is_blacklisted=False)
    pagination = query.order_by(Client.created_at.desc(), Client.nom).paginate(page=page, per_page=per_page, error_out=False)
    pageClients = pagination.items    
    start_of_month = datetime.today().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # Classement des commerciaux par nombre de notes d'observation
    top_commerciaux = (
        db.session.query(User, func.count(Reminder.id).label('nb_notes'))
        .join(Reminder, Reminder.user_id == User.id)
        .group_by(User.id)
        .order_by(func.count(Reminder.id).desc())
        .all()
    )
    
    flash("Les prospects ont été attribués à chaque commercial selon leurs notes.", "success")    
    return render_template('clients.html', pageClients=pageClients, clients=clients, pagination = pagination, start_of_month=start_of_month, top_commerciaux=top_commerciaux, now=datetime.utcnow())



""" from flask_caching import Cache
cache = Cache()
@main_bp.route('/clients')
@login_required
@cache.cached(timeout=300, key_prefix=lambda: f'client_stats_{current_user.id}')
def clients():
    from sqlalchemy.orm import selectinload
    page = request.args.get('page', 1, type=int)
    per_page = 50  # Nombre d'éléments par page augmenté

    # Vérification des permissions
    if not current_user.has_permission('clients'):
        flash('Vous n\'avez pas accès à cette section.', 'error')
        return redirect(url_for('main.dashboard'))

    # Requête de base optimisée
    base_query = Client.query.filter_by(is_blacklisted=False)
    
    # Filtre par commercial si nécessaire
    if current_user.role.name == 'Commercial':
        base_query = base_query.filter_by(assigned_to=current_user.id)

    # Pagination avec chargement anticipé
    pagination = base_query.options(
        selectinload(Client.next_reminder)  # Meilleure performance que joinedload pour les collections
    ).order_by(
        Client.created_at.desc(), 
        Client.nom
    ).paginate(page=page, per_page=per_page, error_out=False)

    # Calcul des statistiques via des requêtes optimisées
    start_of_month = datetime.today().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    stats = {
        'total': cache.get(f'client_total_{current_user.id}') or 
                base_query.count(),
        'clients': cache.get(f'client_clients_{current_user.id}') or 
                  base_query.filter_by(type_client='client').count(),
        'prospects': cache.get(f'client_prospects_{current_user.id}') or 
                    base_query.filter_by(type_client='prospect').count(),
        'monthly': cache.get(f'client_monthly_{current_user.id}') or 
                  base_query.filter(
                      Client.type_client == 'client',
                      Client.created_at >= start_of_month
                  ).count()
    }

    # Mise en cache des statistiques pour 5 minutes
    if not cache.get(f'client_total_{current_user.id}'):
        cache.set(f'client_total_{current_user.id}', stats['total'], timeout=300)
        cache.set(f'client_clients_{current_user.id}', stats['clients'], timeout=300)
        cache.set(f'client_prospects_{current_user.id}', stats['prospects'], timeout=300)
        cache.set(f'client_monthly_{current_user.id}', stats['monthly'], timeout=300)

    # Top commerciaux - requête optimisée et mise en cache
    cache_key = f'top_commerciaux_{current_user.id}'
    top_commerciaux = cache.get(cache_key) or db.session.query(
        User,
        func.count(Reminder.id).label('nb_notes')
    ).join(
        Reminder, Reminder.user_id == User.id
    ).group_by(
        User.id
    ).order_by(
        func.count(Reminder.id).desc()
    ).limit(5).all()  # Limité à 5 résultats
    
    if not cache.get(cache_key):
        cache.set(cache_key, top_commerciaux, timeout=300)

    return render_template(
        'clients.html',
        pageClients=pagination.items,
        pagination=pagination,
        stats=stats,
        top_commerciaux=top_commerciaux,
        now=datetime.utcnow(),
        start_of_month=start_of_month
    )

 """
@main_bp.route('/api/clients', methods=['POST'])
@login_required
def api_clients():
    # Récupération des paramètres DataTables
    draw = request.form.get('draw', type=int)
    start = request.form.get('start', type=int)
    length = request.form.get('length', type=int)
    search_value = request.form.get('search[value]')
    type_filter = request.form.get('type_filter')

    # Construction de la requête de base optimisée
    query = Client.query.filter_by(is_blacklisted=False)
    
    if current_user.role.name == 'Commercial':
        query = query.filter_by(assigned_to=current_user.id)
    
    # Filtrage par type
    if type_filter:
        query = query.filter_by(type_client=type_filter)
    
    # Filtrage par recherche
    if search_value:
        search = f'%{search_value}%'
        query = query.filter(
            or_(
                Client.nom.ilike(search),
                Client.prenom.ilike(search),
                Client.entreprise.ilike(search),
                Client.email.ilike(search),
                Client.telephone.ilike(search)
            )
        )
    
    # Comptage total (sans pagination)
    total_records = query.count()
    
    # Application de la pagination
    clients = query.options(
        selectinload(Client.next_reminder)
    ).order_by(
        Client.created_at.desc()
    ).offset(start).limit(length).all()
    
    # Formatage des données
    data = []
    for client in clients:
        data.append({
            'DT_RowId': f'client_{client.id}',
            'nom_complet': format_nom_complet(client),
            'entreprise': client.entreprise or '-',
            'contact': format_contact(client),
            'adresse': format_adresse(client),
            'type': format_type_client(client),
            'observation': format_observation(client.next_reminder),
            'actions': format_actions(client.id)
        })
    
    return jsonify({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })


# Fonctions utilitaires pour le formatage
def format_nom_complet(client):
    return f'<div class="d-flex align-items-center">\
                <div class="avatar-circle me-2">\
                    {client.nom[0].upper()}{client.prenom[0].upper() if client.prenom else ""}\
                </div>\
                <div>\
                    <strong>{client.nom}</strong>\
                    {client.prenom or ""}\
                </div>\
            </div>'

def format_contact(client):
    contact = []
    if client.email:
        contact.append(f'<div><i data-feather="mail" class="me-1"></i>{client.email}</div>')
    if client.telephone:
        contact.append(f'<div><i data-feather="phone" class="me-1"></i>{client.telephone}</div>')
    return '\n'.join(contact) if contact else '<span class="text-muted">Non renseigné</span>'

def format_adresse(client):
    if not client.adresse:
        return '<span class="text-muted">Non renseignée</span>'
    
    adresse = f'{client.adresse[:30]}{"..." if len(client.adresse) > 30 else ""}'
    if client.ville:
        adresse += f'<br><small class="text-muted">{client.ville}'
        if client.code_postal:
            adresse += f' ({client.code_postal})'
        adresse += '</small>'
    return adresse

def format_type_client(client):
    if client.type_client == 'client':
        return '<span class="badge bg-success">Client</span>'
    return '<span class="badge bg-info">Prospect</span>'

def format_observation(reminder):
    if not reminder:
        return '<span class="text-muted">Aucune observation</span>'
    
    status_class = 'text-warning' if reminder.remind_at and reminder.remind_at >= datetime.utcnow() else 'text-muted'
    
    observation = f'<span class="{status_class}">\
                    <i data-feather="clock"></i>'
    if reminder.remind_at:
        observation += f' Rappel : {reminder.remind_at.strftime("%d/%m/%Y %H:%M")}<br>'
    
    observation += f'<small><i data-feather="calendar"></i>\
                    {reminder.created_at.strftime("%d/%m/%Y %H:%M")}</small>'
    
    if reminder.notes:
        truncated = reminder.notes[:50]
        observation += f'<br><small class="text-muted">\
                        <i data-feather="file-text"></i> {truncated}'
        if len(reminder.notes) > 50:
            observation += ' <a href="#" class="ms-1" onclick="showFullNote(`{escape(reminder.notes)}`); return false;">Voir</a>'
        observation += '</small>'
    
    return observation + '</span>'

def format_actions(client_id):
    return f'<div class="btn-group btn-group-sm">\
                <button class="btn btn-outline-secondary" title="Modifier" onclick="editClient({client_id})">\
                    <i data-feather="edit"></i>\
                </button>\
                <a href="{url_for("main.client_suivi", client_id=client_id)}" \
                   class="btn btn-outline-warning btn-sm" title="Suivi client">\
                    <i data-feather="activity"></i>\
                </a>\
            </div>'



@main_bp.route('/add_client', methods=['POST'])
@login_required
def add_client():
    if not current_user.has_permission('clients'):
        flash('Vous n\'avez pas accès à cette fonctionnalité.', 'error')
        return redirect(url_for('main.clients'))
    
    nom = request.form.get('nom')
    prenom = request.form.get('prenom')
    entreprise = request.form.get('entreprise')
    email = request.form.get('email')
    telephone = request.form.get('telephone')
    adresse = request.form.get('adresse')
    ville = request.form.get('ville')
    code_postal = request.form.get('code_postal')
    type_client = request.form.get('type_client', 'prospect')
    
    try:
        # Vérifier si le téléphone existe déjà
        if telephone and Client.telephone_exists(telephone):
            flash('Un client avec ce numéro de téléphone existe déjà.', 'error')
            return redirect(url_for('main.clients'))
        
        client = Client(
            nom=nom,
            prenom=prenom,
            entreprise=entreprise,
            email=email,
            telephone=telephone,
            adresse=adresse,
            ville=ville,
            code_postal=code_postal,
            type_client=type_client
        )
        
        db.session.add(client)
        db.session.commit()
        
        flash('Client ajouté avec succès.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Erreur lors de l\'ajout du client.', 'error')
    
    return redirect(url_for('main.clients'))

""" @main_bp.route('/import_clients', methods=['POST'])
@login_required
def import_clients():
    if not current_user.has_permission('clients'):
        flash('Vous n\'avez pas accès à cette fonctionnalité.', 'error')
        return redirect(url_for('main.clients'))
    
    if 'file' not in request.files:
        flash('Aucun fichier sélectionné.', 'error')
        return redirect(url_for('main.clients'))
    
    file = request.files['file']
    print("Nom du fichier uploadé :", file.filename)
    if file.filename == '':
        flash('Aucun fichier sélectionné.', 'error')
        return redirect(url_for('main.clients'))
    
    if file and allowed_file(file.filename):
        try:
            # Read Excel file
            df = pd.read_excel(file)
            print("Colonnes du fichier Excel :", df.columns.tolist())
            print(df.head(2))
            required_columns = ['nom']
            if not all(col in df.columns for col in required_columns):
                flash('Le fichier doit contenir au minimum la colonne "nom".', 'error')
                return redirect(url_for('main.clients'))
            
            # Récupère tous les commerciaux
            commercials = User.query.filter(User.role.has(name='Commercial')).all()
            if not commercials:
                flash("Aucun commercial trouvé pour l'attribution.", "warning")
                return redirect(url_for('main.clients'))

            new_clients = []
            duplicate_phones = []
            skipped_rows = 0
            
            for _, row in df.iterrows():
                telephone = str(row.get('telephone', ''))
                
                # Vérifier si le téléphone existe déjà
                if telephone and Client.telephone_exists(telephone):
                    duplicate_phones.append(telephone)
                    skipped_rows += 1
                    continue
                
                client = Client(
                    nom=row.get('nom', ''),
                    prenom=row.get('prenom', ''),
                    entreprise=row.get('entreprise', ''),
                    email=row.get('email', ''),
                    telephone=telephone,
                    adresse=row.get('adresse', ''),
                    ville=row.get('ville', ''),
                    code_postal=row.get('code_postal', ''),
                    type_client=row.get('type_client', 'prospect')
                )
                new_clients.append(client)
                db.session.add(client)
            
            if new_clients:
                # Répartition équitable entre commerciaux
                for idx, client in enumerate(new_clients):
                    assigned_commercial = commercials[idx % len(commercials)]
                    client.assigned_to = assigned_commercial.id
                
                db.session.commit()
                success_msg = f'{len(new_clients)} clients importés et répartis entre les commerciaux.'
                if duplicate_phones:
                    success_msg += f' ({skipped_rows} lignes ignorées - numéros en double)'
                flash(success_msg, 'success')
            else:
                flash('Aucun nouveau client importé - tous les numéros existaient déjà.', 'warning')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de l\'importation du fichier : {str(e)}', 'error')
    else:
        flash('Type de fichier non autorisé. Utilisez un fichier Excel (.xlsx, .xls).', 'error')
    
    return redirect(url_for('main.clients'))
 """
@main_bp.route('/import_clients', methods=['POST'])
@login_required
def import_clients():
    if not current_user.has_permission('clients'):
        flash('Vous n\'avez pas accès à cette fonctionnalité.', 'error')
        return redirect(url_for('main.clients'))
    
    if 'file' not in request.files:
        flash('Aucun fichier sélectionné.', 'error')
        return redirect(url_for('main.clients'))
    
    file = request.files['file']
    if file.filename == '':
        flash('Aucun fichier sélectionné.', 'error')
        return redirect(url_for('main.clients'))
    
    if file and allowed_file(file.filename):
        try:
            df = pd.read_excel(file)
            required_columns = ['nom']
            if not all(col in df.columns for col in required_columns):
                flash('Le fichier doit contenir au minimum la colonne "nom".', 'error')
                return redirect(url_for('main.clients'))
            
            commercials = User.query.filter(User.role.has(name='Commercial')).all()
            if not commercials:
                flash("Aucun commercial trouvé pour l'attribution.", "warning")
                return redirect(url_for('main.clients'))

            # Crée l'historique d'import
            import_history = ClientImportHistory(
                filename=file.filename,
                imported_by_id=current_user.id
            )
            db.session.add(import_history)
            db.session.flush()  # Pour avoir l'ID

            new_clients = []
            duplicate_phones = []
            skipped_rows = 0
            
            for _, row in df.iterrows():
                telephone = str(row.get('telephone', ''))
                if telephone and Client.telephone_exists(telephone):
                    duplicate_phones.append(telephone)
                    skipped_rows += 1
                    continue
                
                client = Client(
                    nom=row.get('nom', ''),
                    prenom=row.get('prenom', ''),
                    entreprise=row.get('entreprise', ''),
                    email=row.get('email', ''),
                    telephone=telephone,
                    adresse=row.get('adresse', ''),
                    ville=row.get('ville', ''),
                    code_postal=row.get('code_postal', ''),
                    type_client=row.get('type_client', 'prospect'),
                    import_history_id=import_history.id  # Lien avec l'import
                )
                new_clients.append(client)
                db.session.add(client)
            
            if new_clients:
                for idx, client in enumerate(new_clients):
                    assigned_commercial = commercials[idx % len(commercials)]
                    client.assigned_to = assigned_commercial.id
                
                db.session.commit()
                success_msg = f'{len(new_clients)} clients importés et répartis entre les commerciaux.'
                if duplicate_phones:
                    success_msg += f' ({skipped_rows} lignes ignorées - numéros en double)'
                flash(success_msg, 'success')
            else:
                db.session.rollback()
                flash('Aucun nouveau client importé - tous les numéros existaient déjà.', 'warning')
                db.session.delete(import_history)
                db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de l\'importation du fichier : {str(e)}', 'error')
    else:
        flash('Type de fichier non autorisé. Utilisez un fichier Excel (.xlsx, .xls).', 'error')
    
    return redirect(url_for('main.clients'))

@main_bp.route('/import_history')
@login_required
def import_history():
    if not current_user.has_permission('clients'):
        flash('Accès refusé.', 'error')
        return redirect(url_for('main.clients'))
    history = ClientImportHistory.query.order_by(ClientImportHistory.imported_at.desc()).all()
    return render_template('import_history.html', history=history)

@main_bp.route('/delete_import/<int:import_id>', methods=['POST'])
@login_required
def delete_import(import_id):
    import_history = ClientImportHistory.query.get_or_404(import_id)
    # Supprime tous les clients liés à cet import
    for client in import_history.clients:
        db.session.delete(client)
    db.session.delete(import_history)
    db.session.commit()
    flash("Import et clients associés supprimés.", "success")
    return redirect(url_for('main.import_history'))

@main_bp.route('/users')
@login_required
def users():
   
    if not current_user.has_permission('all'):  # Only admins
        flash('Vous n\'avez pas accès à cette section.', 'error')
        return redirect(url_for('main.dashboard'))
    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = User.query.order_by(User.nom).paginate(page=page, per_page=per_page, error_out=False)
    page_users = pagination.items
    users = User.query.order_by(User.nom).all()
    roles = Role.query.all()
    return render_template('users.html', users=users, page_users=page_users, roles=roles, pagination=pagination)
@main_bp.route('/add_user', methods=['POST'])
@login_required
def add_user():
    if not current_user.has_permission('all'):
        flash('Vous n\'avez pas accès à cette fonctionnalité.', 'error')
        return redirect(url_for('main.users'))

    username = request.form.get('username')
    email = request.form.get('email')
    nom = request.form.get('nom')
    prenom = request.form.get('prenom')
    telephone = request.form.get('telephone')
    site = request.form.get('site', 'Dakar')  # Par défaut, site Dakar
    role_id = request.form.get('role_id')
    password = request.form.get('password')

    # Récupère le rôle sélectionné
    role = Role.query.get(int(role_id))
    # Récupère les permissions cochées (liste)
    permissions = request.form.getlist('permissions')

    # Si le rôle est administrateur, permissions = 'all'
    if role.permissions == 'all':
        permissions_str = 'all'
    else:
        # Fusionne les permissions du rôle et les permissions cochées (évite les doublons)
        role_perms = set(role.permissions.split(',')) if role.permissions else set()
        custom_perms = set(permissions)
        all_perms = role_perms.union(custom_perms)
        permissions_str = ','.join(sorted(all_perms))

    # Vérifie l'unicité
    existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
    if existing_user:
        flash('Nom d\'utilisateur ou email déjà utilisé.', 'error')
        return redirect(url_for('main.users'))

    try:
        user = User(
            username=username,
            email=email,
            nom=nom,
            prenom=prenom,
            telephone=telephone,
            role_id=int(role_id),
            password_hash=generate_password_hash(password),
            is_active=True,
            permissions=permissions_str,
            site=site
        )
        db.session.add(user)
        db.session.commit()
        
        # Suppression de la redistribution automatique des clients
        flash('Utilisateur créé avec succès.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la création de l\'utilisateur: {str(e)}', 'error')

    return redirect(url_for('main.users'))
""" @main_bp.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    roles = Role.query.all()
    if request.method == 'POST':
        
        role_id = request.form.get('role_id')
        role = Role.query.get(int(role_id))
        permissions = request.form.getlist('permissions')
        if role.permissions == 'all':
            user.permissions = 'all'
        else:
            role_perms = set(role.permissions.split(',')) if role.permissions else set()
            custom_perms = set(permissions)
            all_perms = role_perms.union(custom_perms)
            user.permissions = ','.join(sorted(all_perms))
        password = request.form.get('password')
        if password and len(password) >= 6:
            user.password_hash = generate_password_hash(password)
            flash('Mot de passe modifié avec succès.', 'success')
        db.session.commit()
        flash("Utilisateur modifié avec succès.", "success")
        return redirect(url_for('main.users'))
    return render_template('edit_user.html', user=user, roles=roles)
 """

@main_bp.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    roles = Role.query.all()

    if request.method == 'POST':
        modified = False  # 🔍 Flag pour détecter une modification

        # Récupérer les champs du formulaire
        role_id = request.form.get('role_id')
        role = Role.query.get(int(role_id))
        permissions = request.form.getlist('permissions')
        password = request.form.get('password')

        # Vérification rôle et permissions
        if role.permissions == 'all':
            if user.permissions != 'all':
                user.permissions = 'all'
                modified = True
        else:
            role_perms = set(role.permissions.split(',')) if role.permissions else set()
            custom_perms = set(permissions)
            all_perms = ','.join(sorted(role_perms.union(custom_perms)))
            if user.permissions != all_perms:
                user.permissions = all_perms
                modified = True

        # Vérifier mot de passe
        if password and len(password) >= 6:
            user.password_hash = generate_password_hash(password)
            flash('Mot de passe modifié avec succès.', 'success')
            modified = True

        # Vérifier champs standards (nom, prenom, email, etc.)
        for field in ['prenom', 'nom', 'email', 'username', 'telephone']:
            new_value = request.form.get(field)
            if getattr(user, field) != new_value:
                setattr(user, field, new_value)
                modified = True

        # Vérifier si rôle a changé
        if user.role_id != int(role_id):
            user.role_id = int(role_id)
            modified = True

        if modified:
            db.session.commit()
            flash("Utilisateur modifié avec succès.", "success")
        else:
            flash("Aucune modification détectée.", "info")

        return redirect(url_for('main.users'))

    return render_template('edit_user.html', user=user, roles=roles)


@main_bp.route('/user/<int:user_id>')
@login_required
def user_details(user_id):
    user = User.query.get_or_404(user_id)
    # Sécurité : seuls les admins peuvent voir les détails de tous les utilisateurs, sinon on limite à soi-même
    if not current_user.has_permission('all') and current_user.id != user.id:
        return "<div class='alert alert-danger'>Accès refusé.</div>"
    return render_template('partials/user_details.html', user=user)

@main_bp.route('/profile')
@login_required
def profile():
    
    return render_template('profile.html')

@main_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    from app import db
    current_user.nom = request.form.get('nom', current_user.nom)
    current_user.prenom = request.form.get('prenom', current_user.prenom)
    current_user.telephone = request.form.get('telephone', current_user.telephone)
    
    # Password change
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    
    if current_password and new_password:
        if check_password_hash(current_user.password_hash, current_password):
            current_user.password_hash = generate_password_hash(new_password)
            flash('Mot de passe mis à jour avec succès.', 'success')
        else:
            flash('Mot de passe actuel incorrect.', 'error')
            return redirect(url_for('main.profile'))
    
    try:
        db.session.commit()
        flash('Profil mis à jour avec succès.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Erreur lors de la mise à jour du profil.', 'error')
    
    return redirect(url_for('main.profile'))

@main_bp.route('/work_locations')
@login_required
def work_locations():
    
    if not current_user.has_permission('all'):  # Only admins
        flash('Vous n\'avez pas accès à cette section.', 'error')
        return redirect(url_for('main.dashboard'))
    
    locations = WorkLocation.query.filter_by(is_active=True).all()
    form = WorkLocationForm()
    return render_template('work_locations.html', locations=locations, form=form)

@main_bp.route('/add_work_location', methods=['POST'])
@login_required
def add_work_location():
    if not current_user.has_permission('all'):
        flash('Vous n\'avez pas accès à cette fonctionnalité.', 'error')
        return redirect(url_for('main.work_locations'))
    
    form = WorkLocationForm()
    if form.validate_on_submit():
        location = WorkLocation(
            name=form.name.data,
            address=form.address.data,
            latitude=form.latitude.data,
            longitude=form.longitude.data,
            radius=form.radius.data,
            type=form.type.data  # <-- Ajout du type ici
        )
        db.session.add(location)
        db.session.commit()
        flash('Zone de travail ajoutée avec succès.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{form[field].label.text}: {error}', 'error')
    
    return redirect(url_for('main.work_locations'))
   
   

# Détails client (pour affichage dans la modale)
@main_bp.route('/client/<int:client_id>')
@login_required
def client_details(client_id):
    client = Client.query.get_or_404(client_id)
    # Sécurité : un commercial ne peut voir que ses clients
    if current_user.role.name == 'Commercial' and client.assigned_to != current_user.id:
        return "<div class='alert alert-danger'>Accès refusé.</div>"
    return render_template('partials/client_details.html', client=client)



# Edition client (redirige vers une page d'édition)
@main_bp.route('/edit_client/<int:client_id>', methods=['GET', 'POST'])
@login_required
def edit_client(client_id):
    client = Client.query.get_or_404(client_id)
    
    # Verify permissions
    if current_user.role.name == 'Commercial' and client.assigned_to != current_user.id:
        flash("Accès refusé.", "error")
        return redirect(url_for('main.clients'))

    if request.method == 'POST':
        try:
            # Get form data
            telephone = request.form.get('telephone')
            
            # Check if phone number exists and belongs to another client
            if telephone and telephone != client.telephone:
                existing_client = Client.query.filter_by(telephone=telephone).first()
                if existing_client:
                    flash('Un client avec ce numéro de téléphone existe déjà.', 'error')
                    return render_template('edit_client.html', client=client)
            
            # Update client data
            client.nom = request.form.get('nom')
            client.prenom = request.form.get('prenom')
            client.entreprise = request.form.get('entreprise')
            client.email = request.form.get('email')
            client.telephone = telephone
            client.adresse = request.form.get('adresse')
            client.ville = request.form.get('ville')
            client.code_postal = request.form.get('code_postal')
            client.type_client = request.form.get('type_client')

            db.session.commit()
            flash('Client modifié avec succès.', 'success')
            return redirect(url_for('main.clients'))
            
        except Exception as e:
            db.session.rollback()
            flash('Erreur lors de la modification du client.', 'error')
            return render_template('edit_client.html', client=client)

    # GET request - display form
    return render_template('edit_client.html', client=client)


# Conversion prospect -> client (POST)
""" @main_bp.route('/convert_client/<int:client_id>', methods=['POST'])
@login_required
def convert_client(client_id):
    client = Client.query.get_or_404(client_id)
    if current_user.role.name == 'Commercial' and client.assigned_to != current_user.id:
        flash("Accès refusé.", "error")
        return redirect(url_for('main.clients'))
    if client.type_client == 'prospect':
        client.type_client = 'client'
        db.session.commit()
        flash("Le prospect a été converti en client.", "success")
    else:
        flash("Ce client est déjà un client.", "info")
    return redirect(url_for('main.clients'))

 """

@main_bp.route('/salary_advances', methods=['GET', 'POST'])
@login_required
def salary_advances():
    form = SalaryAdvanceForm()
    # Soumission d'une nouvelle demande
    if form.validate_on_submit():
        advance = SalaryAdvance(
            user_id=current_user.id,
            montant=form.montant.data,
            motif=form.motif.data,
            date_demande=date.today(),
            statut='en_attente',
            created_at=datetime.utcnow()
        )
        db.session.add(advance)
        db.session.commit()
        flash("Demande d'avance envoyée.", "success")
        return redirect(url_for('main.salary_advances'))

    # Affichage des demandes (admin voit tout, sinon que les siennes)
    if current_user.has_permission('all'):
        advances = SalaryAdvance.query.order_by(SalaryAdvance.created_at.desc()).all()
    else:
        advances = SalaryAdvance.query.filter_by(user_id=current_user.id).order_by(SalaryAdvance.created_at.desc()).all()
    return render_template('salary_advances.html', advances=advances, form=form)

@main_bp.route('/salary_advance/<int:advance_id>/approve', methods=['POST'])
@login_required
def approve_salary_advance(advance_id):
    if not current_user.has_permission('all'):
        flash("Accès refusé.", "danger")
        return redirect(url_for('main.salary_advances'))
    advance = SalaryAdvance.query.get_or_404(advance_id)
    advance.statut = 'approuve'
    advance.approved_at = datetime.utcnow()
    advance.approved_by_id = current_user.id
    advance.notes_admin = request.form.get('notes_admin', '')
    db.session.commit()
    flash("Avance approuvée.", "success")
    return redirect(url_for('main.salary_advances'))

@main_bp.route('/salary_advance/<int:advance_id>/refuse', methods=['POST'])
@login_required
def refuse_salary_advance(advance_id):
    if not current_user.has_permission('all'):
        flash("Accès refusé.", "danger")
        return redirect(url_for('main.salary_advances'))
    advance = SalaryAdvance.query.get_or_404(advance_id)
    advance.statut = 'refuse'
    advance.approved_at = datetime.utcnow()
    advance.approved_by_id = current_user.id
    advance.notes_admin = request.form.get('notes_admin', '')
    db.session.commit()
    flash("Avance refusée.", "warning")
    return redirect(url_for('main.salary_advances'))

@main_bp.route('/blacklist_client/<int:client_id>', methods=['POST'])
@login_required
def blacklist_client(client_id):
    client = Client.query.get_or_404(client_id)
    if current_user.role.name == 'Commercial' and client.assigned_to != current_user.id:
        flash("Accès refusé.", "error")
        return redirect(url_for('main.clients'))
    client.is_blacklisted = True
    client.date_blacklisted = datetime.utcnow()
    db.session.commit()
    flash("Client blacklisté.", "warning")
    return redirect(url_for('main.clients'))

def Notification(user_id, message):
    raise NotImplementedError

@main_bp.route('/convert_client/<int:client_id>', methods=['POST'])
@login_required
def convert_client(client_id):
    client = Client.query.get_or_404(client_id)
    if current_user.role.name == 'Commercial' and client.assigned_to != current_user.id:
        flash("Accès refusé.", "error")
        return redirect(url_for('main.clients'))

    note = request.form.get('note', '')
    if client.type_client == 'prospect':
        client.type_client = 'client'
        client.note_conversion = note
        client.converted_by_id = current_user.id 
        db.session.commit()
        admins = User.query.join(Role).filter(Role.name == 'Administrateur').all()
        sender = current_user.telephone if current_user.telephone else "N/A"
        commercial_nom = f"{current_user.nom} {current_user.prenom or ''}".strip()
        commercial_tel = current_user.telephone or 'N/A'
        admin_emails = []
        for admin in admins:
            print(f"Traitement admin: {admin.email}, téléphone: {admin.telephone}", flush=True)
            message = (
                f"Le prospect {client.prenom} {client.nom or ''} a été converti en client par {commercial_nom} "
                f"(Tél: {commercial_tel}).\n "
                f"Type d'intervention : {note}"
            )
            notif = create_notification(
                user_id=admin.id,
                message=message
            )
            db.session.add(notif)
            admin_emails.append(admin.email)
            admin_emails.append("diazfaye82@gmail.com")
            if admin.telephone:
                print(f"Tentative d'envoi SMS à {admin.telephone} via Orange...", flush=True)
                sms_result = send_orange_sms(
                    to=admin.telephone,
                    message=message,
                    sender="+221778721017"
                )
                if sms_result:
                    print(f"SMS Orange envoyé avec succès à {admin.telephone}", flush=True)
                else:
                    print(f"Échec de l'envoi du SMS Orange à {admin.telephone}", flush=True)
        send_email(
            subject="Conversion prospect en client",
            recipients=admin_emails,
            body=message
        )
        db.session.commit() 
        flash("Le prospect a été converti en client. L'administrateur sera notifié.", "success")
    else:
        flash("Ce client est déjà un client.", "info")
    return redirect(url_for('main.clients'))

@main_bp.route('/black_list')
@login_required
def black_list():
    clients = Client.query.filter_by(is_blacklisted=True).order_by(Client.nom).all()
    return render_template('black_list.html', clients=clients)

from models import Notification as NotificationModel

def create_notification(user_id, message):
    notif = NotificationModel(user_id=user_id, message=message)
    return notif

from flask_mail import Message as MailMessage
from flask import current_app

def send_email(subject, recipients, body=None, html=None):
    from app import mail
    msg = MailMessage(subject=subject, recipients=recipients)
    if html:
        msg.html = html
    if body:
        msg.body = body
    mail.send(msg)
""" def send_email(subject, recipients, body):
    from app import mail  
    msg = MailMessage(subject=subject, recipients=recipients, body=body)
    try:
        mail.send(msg)
        print("Mail envoyé pour le rapport de présence !")
    except RuntimeError:
        # Si pas de contexte, on en ouvre un
        with current_app.app_context():
            print(f"Erreur envoi mail mais çava quoi : {e}")
            mail.send(msg)         
 """

""" @main_bp.route('/justify_late', methods=['POST'])
@login_required
def justify_late():
    data = request.get_json()
    reason = data.get('reason')
    # Enregistre la justification 
    
    today_attendance = Attendance.query.filter_by(user_id=current_user.id, date=date.today()).first()
    if today_attendance:
        today_attendance.notes = reason
        db.session.commit()
        return jsonify(success=True)
    return jsonify(success=False)   """    

@main_bp.route('/justify_late', methods=['POST'])
@login_required
def justify_late():
    data = request.get_json()
    reason = data.get('reason')
    
    today_attendance = Attendance.query.filter_by(user_id=current_user.id, date=date.today()).first()
    if today_attendance:
        today_attendance.notes = reason
        db.session.commit()
        
        # Récupérer le lieu de pointage
        lieu_type = "Inconnu"
        lieu_nom = "Inconnu"
        if today_attendance.work_location_id:
            work_location = WorkLocation.query.get(today_attendance.work_location_id)
            if work_location:
                lieu_type = work_location.type.capitalize()  # "Bureau" ou "Chantier"
                lieu_nom = work_location.name

        # Envoyer l'email aux administrateurs
        admins = User.query.join(Role).filter(Role.name == 'Administrateur').all()
        
        # Construction du message
        employee_name = f"{current_user.prenom} {current_user.nom}"
        arrival_time = today_attendance.check_in.strftime("%H:%M") if today_attendance.check_in else "Non pointé"
        message = f"""
        Bonjour,

        Un justificatif de retard a été soumis :

        Employé : {employee_name}
        Date : {date.today().strftime('%d/%m/%Y')}
        Heure d'arrivée : {arrival_time}
        Lieu : {lieu_type} - {lieu_nom}
        Justification : {reason}

        Cordialement,
        Système de pointage
        """

        # Envoi de l'email
        send_email(
            subject=f"Justificatif de retard - {employee_name} - {date.today().strftime('%d/%m/%Y')}",
            recipients=["diazfaye82@gmail.com"],  # Ajoute d'autres destinataires si besoin
            body=message
        )

        # Création d'une notification interne pour chaque admin
        for admin in admins:
            notif = create_notification(
                user_id=admin.id,
                message=f"Nouveau justificatif de retard de {employee_name} ({lieu_type} - {lieu_nom}) : {reason}"
            )
            db.session.add(notif)
        
        db.session.commit()
        return jsonify(success=True, message="Justificatif enregistré et notification envoyée")
        
    return jsonify(success=False, message="Impossible de trouver le pointage du jour")
@main_bp.route('/client_track/<int:client_id>')
@login_required
def client_track(client_id):
    client = Client.query.get_or_404(client_id)
    return render_template('client_track.html', client=client)

@main_bp.route('/client_remind/<int:client_id>', methods=['POST'])
@login_required
def client_remind(client_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'Données manquantes'
            }), 400

        remind_date = data.get('remind_date')
        notes = data.get('notes')

        if not notes:
            return jsonify({
                'success': False,
                'message': 'Notes requises'
            }), 400

        # Créer le rappel
        reminder = Reminder(
            client_id=client_id,
            user_id=current_user.id,
            remind_at=datetime.fromisoformat(remind_date) if remind_date else None,
            notes=notes
        )

        db.session.add(reminder)
        db.session.flush()
        client = Client.query.get(client_id)
        client_name = f"{client.nom} {client.prenom or ''}".strip() if client else "Client"
        # Création de l'événement calendrier lié au rappel
        if remind_date:
            event_title = f"Rappel: {client_name} - {notes}"
            calendar_event = CalendarEvent(
                title=event_title,
                start=remind_date,
                allDay=False
            )
            db.session.add(calendar_event)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Rappel et événement enregistrés avec succès'
        })

    except Exception as e:
        db.session.rollback()
        print(f"Erreur lors de la création du rappel: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500

@main_bp.route('/client_send_catalogue/<int:client_id>', methods=['POST'])
@login_required
def client_send_catalogue(client_id):
    client = Client.query.get_or_404(client_id)
    # Ici, tu peux envoyer un email avec le catalogue (utilise Flask-Mail ou autre)
    # Pour la démo, on simule le succès
    try:
        # send_catalogue_email(client.email)  # À implémenter
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False), 500

@main_bp.route('/client_request_quote/<int:client_id>', methods=['POST'])
@login_required
def client_request_quote(client_id):
    data = request.get_json()
    details = data.get('details')

    try:
        # Enregistrement de la demande de devis
        quote = QuoteRequest(client_id=client_id, details=details, user_id=current_user.id, created_at=datetime.utcnow())
        db.session.add(quote)
        db.session.commit()

        # Récupération du client
        client = Client.query.get(client_id)

        # Récupération de l'admin
        admin_user = User.query.join(Role).filter(Role.name == 'Administrateur').first()
        # Récupération de "MARIE MME" (rôle administration)
        marie_mme = User.query.filter(
            User.prenom.ilike('%MARIE%'),
            User.nom.ilike('%DIOP%'),
            User.role.has(name='administration')
        ).first()

        recipients = []
        recipients.append('diazfaye82@gmail.com')  # L'utilisateur qui a fait la demande
        if admin_user and admin_user.email:
            recipients.append(admin_user.email)
        if marie_mme and marie_mme.email:
            recipients.append(marie_mme.email)

        # Envoi de l'email
        subject = f"Nouvelle demande de devis pour le client {client.nom} {client.prenom or ''}"
        body = f"""
        Bonjour,

        Une nouvelle demande de devis a été soumise par {current_user.prenom} {current_user.nom} pour le client {client.nom} {client.prenom or ''}.

        Détails de la demande : {details}

        Veuillez traiter cette demande dans le module Devis.

        Cordialement,
        NetSystème Informatique & Telecom
        """
        if recipients:
            send_email(subject=subject, recipients=recipients, body=body)

        return jsonify(success=True, message="Demande de devis enregistrée et notification envoyée.")
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message="Erreur lors de l'enregistrement ou de la notification."), 500 

@main_bp.route('/client_suivi/<int:client_id>')
@login_required
def client_suivi(client_id):
    page = request.args.get('page', 1, type=int)
    client = Client.query.get_or_404(client_id)
    return render_template('client_suivi.html', client=client, page=page)    



#import base64
import pdfkit
from flask import make_response
#from weasyprint import HTML

@main_bp.route('/intervention/<int:id>/pdf')
def export_pdf(id):
    config = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\bin\wkhtmltopdf.exe')
    intervention = Intervention.query.get_or_404(id)
    rendered = render_template("fiche_intervention.html", intervention=intervention)
    options = {
        'enable-local-file-access': None,
        'quiet': '',
    }
    try:
        pdf = pdfkit.from_string(rendered, False, configuration=config, options=options)
        # Génération du PDF avec WeasyPrint
        #pdf = HTML(string=rendered).write_pdf()
    except OSError as e:
        return f"Erreur de génération PDF : {e}", 500
    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers['Content-Disposition'] = f'inline; filename=fiche_intervention_{id}.pdf'
    return response 
    """ intervention = Intervention.query.get_or_404(id)
    return generate_fiche_pdf(intervention) """




from fpdf import FPDF
from flask import make_response
from io import BytesIO

class FicheInterventionPDF(FPDF):
    def header(self):
        # Logo plus petit (40mm de large au lieu de 60)
        self.image('static/img/logo_lgc.png', x=10, y=5, w=40)
        self.set_font('Arial', 'B', 11)  # Taille police réduite
        self.cell(0, 8, "FICHE D'INTERVENTION", ln=True, align='C')
        self.set_font('Arial', '', 10)  # Taille police réduite
        self.cell(0, 6, 'NETSYSTEME INFORMATIQUE & TELECOM', ln=True, align='C')
        self.ln(2)  # Espacement réduit

    def footer(self):
        self.set_y(-20)  # Remonté le pied de page
        self.set_font('Arial', '', 8)  # Police plus petite
        self.cell(0, 4, 'Whatsapp: 77 846 16 55 / Bureau: 33 883 42 42 - 33 827 28 45', ln=True, align='C')
        self.cell(0, 4, 'Ouest foire, route aéroport, immeuble Seigneurie', ln=True, align='C')
        self.cell(0, 4, 'R.C.SN/DKR-2010.A.7987 // NINEA: 004225464 // www.netsys-info.com', ln=True, align='C')
        self.cell(0, 4, f'Page {self.page_no()}/1', ln=True, align='C')
@main_bp.route('/intervention/<int:id>/fiche')
def generate_fiche_pdf(intervention):
    pdf = FicheInterventionPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)  # Marge réduite
    pdf.set_font('Arial', '', 10)  # Police plus petite

    # Informations client et intervention
    pdf.cell(0, 6, f"Société / Organisme : {intervention.client.entreprise or intervention.client.nom}", ln=True)
    pdf.cell(0, 6, f"Numéro intervention : {intervention.id}", ln=True)
    pdf.cell(0, 6, f"Technicien : {intervention.technicien.prenom} {intervention.technicien.nom}", ln=True)
    pdf.ln(3)

    # Nature de l'intervention
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 6, "Nature de l'intervention", ln=True)
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 6, f"- Type : {intervention.type_intervention or 'Non défini'}")
    pdf.multi_cell(0, 6, f"- Description : {intervention.description or '-'}")
    pdf.ln(3)

    # Observations technicien
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 6, "Observations et suite donnée par le technicien :", ln=True)
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 6, intervention.observations_technicien or '-')
    pdf.ln(3)

    # Horaires
    pdf.cell(0, 6, f"Heure d'arrivée : {intervention.heure_arrivee.strftime('%H:%M') if intervention.heure_arrivee else '--:--'}", ln=True)
    pdf.cell(0, 6, f"Heure de départ : {intervention.heure_depart.strftime('%H:%M') if intervention.heure_depart else '--:--'}", ln=True)
    pdf.cell(0, 6, f"Durée intervention : {intervention.duree_intervention.strftime('%H:%M') if intervention.duree_intervention else '--:--'}", ln=True)
    pdf.ln(3)

    # Informations techniques
    pdf.cell(0, 6, f"Identifiant DVR/NVR : {intervention.id_dvr_nvr or 'Non renseigné'}", ln=True)
    pdf.cell(0, 6, f"Mot de passe DVR/NVR : {intervention.mdp_dvr_nvr or 'Non renseigné'}", ln=True)
    pdf.ln(5)

    # Signatures
    pdf.cell(0, 6, "Fait le : " + (intervention.updated_at.strftime('%Y-%m-%d') if intervention.updated_at else datetime.today().strftime('%Y-%m-%d')), ln=True)
    
    # Ajout de la signature si elle existe
    if intervention.signature_data:
        try:
            # Convertir la signature base64 en image
            signature_data = intervention.signature_data.split(',')[1]  # Enlever le préfixe data:image/png;base64,
            signature_bytes = BytesIO(base64.b64decode(signature_data))
            pdf.image(signature_bytes, x=10, y=pdf.get_y(), w=60)  # Signature plus petite
            pdf.ln(20)  # Espace après la signature
        except Exception as e:
            pdf.cell(0, 6, "Signature non disponible", ln=True)
    else:
        pdf.cell(0, 6, "Signature : _____________________", ln=True)
    
    pdf.cell(0, 6, "Cachet de l'entreprise : ___________________________", ln=True)

    # Génération du fichier
    pdf_bytes = pdf.output(dest='S').encode('latin1')
    pdf_output = BytesIO(pdf_bytes)

    response = make_response(pdf_output.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=fiche_intervention_{intervention.id}.pdf'
    return response


#Le service de rapport d'absences
# from datetime import time
# from flask_mail import Message
#from app import mail, db
#from models import User, Attendance
#from jinja2 import Template
#import pandas as pd

class DailyAttendanceReport:
    def __init__(self, app):
        self.app = app
        self.report_time = time(10, 00) 
        self.director_email = "diazfaye82@gmail.com"
        self.heure_limite = time(9, 15)

    def generate_report(self):
        print("Génération du rapport de présence !")
        with self.app.app_context():
            today = date.today()
            employees = User.query.filter_by(is_active=True).all()
            attendances = {
                a.user_id: a for a in Attendance.query.filter_by(date=today).all()
            }

            attendance_data = []
            total_present = total_absent = total_late = 0

            for employee in employees:
                attendance = attendances.get(employee.id)
                
                status = "Absent"
                arrival_time = "N/A"
                departure_time = "N/A"
                justification = "Non justifié"
                total_hours = 0

                if attendance:
                    if attendance.check_in:
                        if attendance.check_in.time() > self.heure_limite:
                            status = "En retard"
                            total_late += 1
                        else:
                            status = "Présent"
                            total_present += 1

                        arrival_time = attendance.check_in.strftime("%H:%M")
                        
                        if attendance.check_out:
                            departure_time = attendance.check_out.strftime("%H:%M")
                            total_hours = attendance.total_hours

                        if attendance.notes:
                            justification = attendance.notes
                else:
                    total_absent += 1

                attendance_data.append({
                    "Nom": f"{employee.nom} {employee.prenom}",
                    "Status": status,
                    "Heure d'arrivée": arrival_time,
                    "Heure de sortie": departure_time,
                    "Durée totale": f"{total_hours:.2f}h" if total_hours else "N/A",
                    "Justificatif": justification
                })

            df = pd.DataFrame(attendance_data)
            
            html_content = self._generate_html_report(
                df, 
                today,
                {
                    'presents': total_present,
                    'absents': total_absent,
                    'retards': total_late
                }
            )

            # Appelle send_email APRÈS avoir défini html_content
            send_email(
                subject=f"Rapport de présence du {today.strftime('%d/%m/%Y')}",
                recipients=[self.director_email],
                html=html_content
            )

    def _generate_html_report(self, df, date_report, stats):
        template = Template("""
        <html>
            <head>
                <style>
                    body { font-family: Arial, sans-serif; }
                    table { 
                        border-collapse: collapse; 
                        width: 100%;
                        margin-bottom: 20px;
                    }
                    th, td { 
                        border: 1px solid #ddd; 
                        padding: 8px; 
                        text-align: left; 
                    }
                    th { background-color: #f2f2f2; }
                    .stats-container {
                        margin-bottom: 20px;
                        border: 1px solid #ddd;
                        padding: 15px;
                    }
                    .stats-row {
                        display: flex;
                        justify-content: space-between;
                    }
                    .stat-box {
                        padding: 10px;
                        text-align: center;
                        border-radius: 4px;
                        flex: 1;
                        margin: 0 10px;
                    }
                    .present { background-color: #d4edda; color: #155724; }
                    .absent { background-color: #f8d7da; color: #721c24; }
                    .late { background-color: #fff3cd; color: #856404; }
                </style>
            </head>
            <body>
                <h2>Rapport de présence du {{ date }}</h2>
                
                <div class="stats-container">
                    <div class="stats-row">
                        <div class="stat-box present">
                            <h3>Présents</h3>
                            <p>{{ stats.presents }}</p>
                        </div>
                        <div class="stat-box absent">
                            <h3>Absents</h3>
                            <p>{{ stats.absents }}</p>
                        </div>
                        <div class="stat-box late">
                            <h3>Retards</h3>
                            <p>{{ stats.retards }}</p>
                        </div>
                    </div>
                </div>

                {{ table }}

                <p style="margin-top: 20px; color: #666; font-size: 12px;">
                    Rapport généré automatiquement le {{ date }} à {{ time }}
                </p>
            </body>
        </html>
        """)
        
        styled_df = df.style.map(
            lambda x: 'color: red' if x == 'Absent' else 
                     'color: orange' if x == 'En retard' else 
                     'color: green',
            subset=['Status']
        )
        
        return template.render(
            date=date_report.strftime("%d/%m/%Y"),
            time=datetime.now().strftime("%H:%M"),
            stats=stats,
            table=styled_df.to_html(classes='table')
        )



def redistribute_clients():
    """Redistribue équitablement les clients entre les commerciaux actifs"""
    # Récupère tous les commerciaux actifs
    commercials = User.query.join(Role).filter(
        Role.name == 'Commercial',
        User.is_active == True
    ).all()
    
    if not commercials:
        return False
        
    # Récupère tous les clients non blacklistés
    clients = Client.query.filter_by(is_blacklisted=False, type_client='prospect').all()
    
    # Répartition équitable
    for idx, client in enumerate(clients):
        assigned_commercial = commercials[idx % len(commercials)]
        client.assigned_to = assigned_commercial.id
    
    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        return False
 

def redistribute_clients_of(user_id):
    """Redistribue uniquement les prospects du commercial désactivé/activé/ajouté"""
    # Récupère tous les commerciaux actifs SAUF celui désactivé
    commercials = User.query.join(Role).filter(
        Role.name == 'Commercial',
        User.is_active == True,
        User.id != user_id
    ).all()
    if not commercials:
        return False

    # Récupère les prospects du commercial désactivé
    # clients = Client.query.filter_by(is_blacklisted=False, type_client='prospect', assigned_to=user_id).all()
    clients = Client.query.filter_by(is_blacklisted=False, assigned_to=user_id).all()

    for idx, client in enumerate(clients):
        assigned_commercial = commercials[idx % len(commercials)]
        client.assigned_to = assigned_commercial.id

    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        return False

@main_bp.route('/user/<int:user_id>/deactivate', methods=['POST'])
@login_required
def deactivate_user(user_id):
    if not current_user.has_permission('all'):
        flash('Accès refusé.', 'error')
        return redirect(url_for('main.users'))
        
    user = User.query.get_or_404(user_id)
    
    # Vérifie si c'est un commercial
    is_commercial = user.role.name == 'Commercial'
    
    user.is_active = False
    db.session.commit()
    
    # Si c'était un commercial, redistribue les clients
    if is_commercial:
        if redistribute_clients_of(user.id):
            flash(f'Utilisateur désactivé et clients redistribués avec succès.', 'success')
        else:
            flash(f'Utilisateur désactivé mais erreur lors de la redistribution des clients.', 'warning')
    else:
        flash('Utilisateur désactivé avec succès.', 'success')
    
    return redirect(url_for('main.users'))


@main_bp.route('/user/<int:user_id>/activate', methods=['POST'])
@login_required
def activate_user(user_id):
    if not current_user.has_permission('all'):
        flash('Accès refusé.', 'error')
        return redirect(url_for('main.users'))
    
    user = User.query.get_or_404(user_id)
    user.is_active = True
    db.session.commit()
    
    flash('Utilisateur réactivé avec succès.', 'success')
    return redirect(url_for('main.users'))

#Intégration du module de facturation
# Configuration pour les uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(os.path.join(UPLOAD_FOLDER, 'uploads'), exist_ok=True)

def allowed_files(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@billing.route('/billing')
@login_required

def billing_dashboard():
    total_clients = BillingClient.query.count()
    total_invoices = Invoice.query.count()
    total_proformas = Proforma.query.count()
    total_products = Product.query.count()
    low_stock = Product.query.filter(Product.quantity <= Product.alert_quantity).count()
    
    recent_invoices = Invoice.query.order_by(Invoice.date.desc()).limit(5).all()
    recent_proformas = Proforma.query.order_by(Proforma.date.desc()).limit(5).all()
    
    return render_template('billing/dashboard.html',
                         total_clients=total_clients,
                         total_invoices=total_invoices,
                         total_proformas=total_proformas,
                         total_products=total_products,
                         low_stock=low_stock,
                         recent_invoices=recent_invoices,
                         recent_proformas=recent_proformas)

# Gestion des clients
@billing.route('/billing/clients')
@login_required

def manage_clients():
    clients = BillingClient.query.order_by(BillingClient.company_name).all()
    return render_template('billing/clients.html', clients=clients)

@billing.route('/billing/clients/add', methods=['GET', 'POST'])
@login_required

def add_client():
    if request.method == 'POST':
        company_name = request.form.get('company_name')
        contact_name = request.form.get('contact_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        tax_id = request.form.get('tax_id')
        
        new_client = BillingClient(
            company_name=company_name,
            contact_name=contact_name,
            email=email,
            phone=phone,
            address=address,
            tax_id=tax_id
        )
        
        db.session.add(new_client)
        db.session.commit()
        
        flash('Client ajouté avec succès', 'success')
        return redirect(url_for('billing.manage_clients'))
    
    return render_template('billing/add_client.html')

# Gestion des produits
@billing.route('/billing/products')
@login_required

def manage_products():
    products = Product.query.order_by(Product.description).all()
    return render_template('billing/products.html', products=products)

@billing.route('/billing/products/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        # Récupération des données du formulaire
        name = request.form.get('name')
        description = request.form.get('description')
        quantity = float(request.form.get('qty', 0))
        unit_price = float(request.form.get('prix', 0))
        supplier = request.form.get('fournisseur')
        alert_quantity = float(request.form.get('alert_quantity', 5))
        
        # Gestion du fichier image (comme dans add_expense)
        image_path = None
        img_file = request.files['img']
        if img_file and img_file.filename:
                # Création du répertoire s'il n'existe pas
                static_path = current_app.static_folder
                upload_folder = os.path.join(static_path, 'uploads', 'products')
                os.makedirs(upload_folder, exist_ok=True)
                
                # Sécurisation et sauvegarde du fichier
                filename = secure_filename(img_file.filename)
                file_path = os.path.join(upload_folder, filename)
                
                try:
                    img_file.save(file_path)
                    image_path = f"uploads/products/{filename}"  # Chemin relatif comme dans add_expense
                except Exception as e:
                    current_app.logger.error(f"Erreur sauvegarde image: {str(e)}")
                    flash("Erreur lors de l'enregistrement de l'image", "error")
        try:
            # Création et sauvegarde du produit
            new_product = Product(
                name=name,
                description=description,
                quantity=quantity,
                unit_price=unit_price,
                supplier=supplier,
                alert_quantity=alert_quantity,
                image_path=image_path  # Utilisation du chemin relatif
            )
            
            db.session.add(new_product)
            db.session.commit()
            
            flash('Produit ajouté avec succès', 'success')
            return redirect(url_for('billing.manage_products'))
            
        except ValueError as e:
            db.session.rollback()
            flash('Erreur de format dans les données numériques', 'error')
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Erreur création produit")
            flash('Erreur lors de l\'ajout du produit', 'error')
    
    return render_template('billing/add_product.html')

@billing.route('/billing/products/edit/<int:product_id>/modal')
@login_required
def edit_product_modal(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('billing/_edit_product_modal.html', product=product)

@billing.route('/billing/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    if request.method == 'POST':
        try:
            # Récupération des données du formulaire
            product.name = request.form.get('name')
            product.description = request.form.get('description')
            product.quantity = float(request.form.get('qty', 0))
            product.unit_price = float(request.form.get('prix', 0))
            product.supplier = request.form.get('fournisseur')
            product.alert_quantity = float(request.form.get('alert_quantity', 5))
            
            # Gestion de l'image (même méthode que pour l'ajout)
            img_file = request.files['img']
            if img_file and img_file.filename:
                    static_path = current_app.static_folder
                    upload_folder = os.path.join(static_path, 'uploads', 'products')
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    filename = secure_filename(img_file.filename)
                    file_path = os.path.join(upload_folder, filename)
                    
                    try:
                        # Suppression de l'ancienne image si elle existe
                        if product.image_path:
                            old_path = os.path.join(static_path, product.image_path)
                            if os.path.exists(old_path):
                                os.remove(old_path)
                        
                        img_file.save(file_path)
                        product.image_path = f"uploads/products/{filename}"
                    except Exception as e:
                        current_app.logger.error(f"Erreur sauvegarde image: {str(e)}")
                        flash("Erreur lors de la mise à jour de l'image", "error")
            
            db.session.commit()
            flash('Produit mis à jour avec succès', 'success')
            return redirect(url_for('billing.manage_products'))
            
        except ValueError as e:
            db.session.rollback()
            flash('Erreur de format dans les données numériques', 'error')
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Erreur modification produit")
            flash('Erreur lors de la modification du produit', 'error')
    
    # Pour GET, le template est rendu via la modale
    return jsonify({
        'html': render_template('billing/_edit_product_modal.html', product=product)
    })

@billing.route('/billing/products/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    try:
        # Suppression de l'image associée si elle existe
        if product.image_path:
            image_path = os.path.join(current_app.static_folder, product.image_path)
            if os.path.exists(image_path):
                os.remove(image_path)
        
        db.session.delete(product)
        db.session.commit()
        flash('Produit supprimé avec succès', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur suppression produit: {str(e)}")
        flash('Erreur lors de la suppression du produit', 'error')
    
    return redirect(url_for('billing.manage_products'))

# Gestion des factures
@billing.route('/billing/invoices')
@login_required

def manage_invoices():
    invoices = Invoice.query.order_by(Invoice.date.desc()).all()
    return render_template('billing/invoices.html', invoices=invoices)

@billing.route('/billing/invoices/new', methods=['GET', 'POST'])
@login_required

def new_invoice():
    if request.method == 'POST':
        try:
            # Validation des données requises
            if not request.form.get('client_id'):
                flash("Un client doit être sélectionné", 'danger')
                return redirect(url_for('billing.new_invoice'))
                
            if not request.form.get('invoice_number'):
                flash("Le numéro de facture est obligatoire", 'danger')
                return redirect(url_for('billing.new_invoice'))
            
            if not request.form.get('domaine'):
                flash("Veillez selectionnez un domaine", 'danger')
                return redirect(url_for('billing.new_invoice'))
            # Création de la facture
            new_invoice = Invoice(
                invoice_number=request.form['invoice_number'],
                billing_client_id=request.form['client_id'],
                date=datetime.strptime(request.form['date'], '%Y-%m-%d').date() if request.form.get('date') else datetime.utcnow().date(),
                due_date=datetime.strptime(request.form['due_date'], '%Y-%m-%d').date() if request.form.get('due_date') else None,
                tax_rate=float(request.form.get('tax_rate', 0.18)),
                domaine=request.form.get('domaine', ''),
                notes=request.form.get('notes', ''),
                status='draft'
            )
            
            # Gestion des remises
            discount_type = request.form.get('discount_type')
            if discount_type == 'percent':
                new_invoice.discount_percent = float(request.form.get('discount_value', 0))
            elif discount_type == 'amount':
                new_invoice.discount_amount = float(request.form.get('discount_value', 0))
            
            db.session.add(new_invoice)
            db.session.flush()  # Important pour obtenir l'ID
            
            # Traitement des articles
            descriptions = request.form.getlist('item_description[]')
            quantities = request.form.getlist('item_quantity[]')
            unit_prices = request.form.getlist('item_unit_price[]')
            discounts = request.form.getlist('item_discount[]')
            product_ids = request.form.getlist('item_product_id[]')
            
            for i, desc in enumerate(descriptions):
                if desc.strip():  # Ignorer les lignes vides
                    try:
                        item = InvoiceItem(
                            invoice_id=new_invoice.id,  # Ceci est crucial
                            description=desc,
                            quantity=float(quantities[i]) if quantities[i] else 1.0,
                            unit_price=float(unit_prices[i]) if unit_prices[i] else 0.0,
                            discount_percent=float(discounts[i]) if discounts[i] else 0.0,
                            product_id=int(product_ids[i]) if product_ids[i] else None
                        )
                        db.session.add(item)
                    except (ValueError, IndexError) as e:
                        db.session.rollback()
                        flash(f"Erreur dans l'article {i+1}: {str(e)}", 'danger')
                        return redirect(url_for('billing.new_invoice'))
            
            db.session.commit()
            flash('Facture créée avec succès', 'success')
            return redirect(url_for('billing.view_invoice', invoice_id=new_invoice.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors de la création: {str(e)}", 'danger')
            return redirect(url_for('billing.new_invoice'))
    
    # GET request
    clients = BillingClient.query.order_by(BillingClient.company_name).all()
    products = Product.query.order_by(Product.description).all()
    today = datetime.utcnow().date()
    next_number = f"FACT-{today.strftime('%Y%m%d')}-{Invoice.query.count() + 1}"
    
    return render_template('billing/new_invoice.html',
                         clients=clients,
                         products=products,
                         next_number=next_number,
                         today=today)

@billing.route('/billing/invoices/<int:invoice_id>')
@login_required

def view_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    #invoice = Invoice.query.options(db.joinedload(Invoice.items)).get_or_404(invoice_id)
    return render_template('billing/view_invoice.html', invoice=invoice)

@billing.route('/billing/invoices/<int:invoice_id>/confirm')
@login_required

def confirm_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Vérifier le stock
    for item in invoice.items:
        if item.product and item.product.quantity < item.quantity:
            flash(f"Stock insuffisant pour {item.product.description} (stock: {item.product.quantity}, demandé: {item.quantity})", 'danger')
            return redirect(url_for('billing.view_invoice', invoice_id=invoice.id))
    
    # Mettre à jour le stock
    for item in invoice.items:
        if item.product:
            item.product.quantity -= item.quantity
            db.session.add(item.product)
    
    invoice.status = 'confirmed'
    db.session.commit()
    
    flash('Facture confirmée et stock mis à jour', 'success')
    return redirect(url_for('billing.view_invoice', invoice_id=invoice.id))

# Gestion des proformas
@billing.route('/billing/proformas')
@login_required

def manage_proformas():
    proformas = Proforma.query.order_by(Proforma.date.desc()).all()
    return render_template('billing/proformas.html', proformas=proformas)

@billing.route('/billing/proformas/new', methods=['GET', 'POST'])
@login_required

def new_proforma():
    if request.method == 'POST':
        client_id = request.form.get('client_id')
        proforma_number = request.form.get('proforma_number')
        date_str = request.form.get('date')
        valid_until_str = request.form.get('valid_until')
        tax_rate = float(request.form.get('tax_rate', 0.18))
        discount_type = request.form.get('discount_type')
        discount_value = float(request.form.get('discount_value', 0))
        domaine = request.form.get('domaine')
        notes = request.form.get('notes')
        
        date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.utcnow().date()
        valid_until = datetime.strptime(valid_until_str, '%Y-%m-%d').date() if valid_until_str else None
        
        new_proforma = Proforma(
            proforma_number=proforma_number,
            billing_client_id=client_id,
            date=date,
            valid_until=valid_until,
            tax_rate=tax_rate,
            domaine=domaine,
            notes=notes,
            status='draft'
        )
        
        if discount_type == 'percent':
            new_proforma.discount_percent = discount_value
        elif discount_type == 'amount':
            new_proforma.discount_amount = discount_value
        
        db.session.add(new_proforma)
        db.session.commit()
        
        # Ajouter les articles
        product_ids = request.form.getlist('item_product_id[]')
        descriptions = request.form.getlist('item_description[]')
        quantities = request.form.getlist('item_quantity[]')
        unit_prices = request.form.getlist('item_unit_price[]')
        discounts = request.form.getlist('item_discount[]')
        
        for product_id, desc, qty, price, discount in zip(product_ids, descriptions, quantities, unit_prices, discounts):
            if desc:
                item = ProformaItem(
                    proforma_id=new_proforma.id,
                    product_id=product_id if product_id else None,
                    description=desc,
                    quantity=float(qty),
                    unit_price=float(price),
                    discount_percent=float(discount)
                )
                db.session.add(item)
        
        db.session.commit()
        
        flash('Proforma créé avec succès', 'success')
        return redirect(url_for('billing.view_proforma', proforma_id=new_proforma.id))
    
    clients = BillingClient.query.order_by(BillingClient.company_name).all()
    products = Product.query.order_by(Product.description).all()
    today = datetime.utcnow().date()
    next_number = f"PRO-{today.strftime('%Y%m%d')}-{Proforma.query.count() + 1}"
    
    return render_template('billing/new_proforma.html', 
                         clients=clients,
                         products=products,
                         next_number=next_number,
                         today=today)

@billing.route('/billing/proformas/<int:proforma_id>')
@login_required

def view_proforma(proforma_id):
    proforma = Proforma.query.get_or_404(proforma_id)
    return render_template('billing/view_proforma.html', proforma=proforma)

@billing.route('/billing/proformas/<int:proforma_id>/convert')
@login_required

def convert_proforma(proforma_id):
    proforma = Proforma.query.get_or_404(proforma_id)
    
    # Créer une facture à partir du proforma
    today = datetime.utcnow().date()
    invoice_number = f"FACT-{today.strftime('%Y%m%d')}-{Invoice.query.count() + 1}"
    
    new_invoice = Invoice(
        invoice_number=invoice_number,
        billing_client_id=proforma.billing_client_id,
        date=today,
        due_date=proforma.valid_until,
        tax_rate=proforma.tax_rate,
        discount_percent=proforma.discount_percent,
        discount_amount=proforma.discount_amount,
        notes=f"Converti à partir du proforma {proforma.proforma_number}",
        status='draft'
    )
    
    db.session.add(new_invoice)
    db.session.commit()
    
    # Copier les articles
    for item in proforma.items:
        invoice_item = InvoiceItem(
            invoice_id=new_invoice.id,
            product_id=item.product_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent
        )
        db.session.add(invoice_item)
    
    proforma.converted_to_invoice = True
    proforma.invoice_id = new_invoice.id
    proforma.status = 'converted'
    
    db.session.commit()
    
    flash('Proforma converti en facture avec succès', 'success')
    return redirect(url_for('billing.view_invoice', invoice_id=new_invoice.id))

# API
@billing.route('/api/billing/clients')
@login_required

def api_clients():
    clients = BillingClient.query.all()
    return jsonify([{
        'id': c.id,
        'text': f"{c.company_name} - {c.contact_name or ''}"
    } for c in clients])

@billing.route('/api/billing/products')
@login_required

def api_products():
    products = Product.query.all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'description': p.description,
        'price': p.unit_price,
        'quantity': p.quantity
    } for p in products])

@billing.route('/billing/invoices/<int:invoice_id>/pdf')
@login_required
def invoice_pdf(invoice_id):
    config = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\bin\wkhtmltopdf.exe')
    invoice = Invoice.query.get_or_404(invoice_id)
    # Choix du template selon le domaine
    if invoice.domaine == "SSE":
        template = "billing/invoice_sse.html"
    else:
        template = "billing/invoice_netsysteme.html"
    rendered = render_template(template, invoice=invoice)
    options = {
        'enable-local-file-access': None,
        'quiet': '',
    }
    try:
        pdf = pdfkit.from_string(rendered, False, configuration=config, options=options)
    except OSError as e:
        return f"Erreur de génération PDF : {e}", 500
    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"inline; filename=facture_{invoice.invoice_number}.pdf"
    return response     


@billing.route('/billing/proformas/<int:proforma_id>/pdf')
@login_required
def proforma_pdf(proforma_id):
    # Configuration de PDFKit (adaptez le chemin selon votre environnement)
    config = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\bin\wkhtmltopdf.exe')
    
    # Récupération du proforma
    proforma = Proforma.query.get_or_404(proforma_id)
    
    # Choix du template selon le domaine
    if proforma.domaine == "SSE": 
        template = "billing/proforma_sse.html"
    else:
        template = "billing/proforma_netsysteme.html"
    
    # Rendu du template
    rendered = render_template(template, proforma=proforma)
    
    # Options de génération PDF
    options = {
        'enable-local-file-access': None,
        'quiet': '',
    }
    
    try:
        # Génération du PDF
        pdf = pdfkit.from_string(rendered, False, configuration=config, options=options)
    except OSError as e:
        current_app.logging.error(f"Erreur de génération PDF pour le proforma {proforma_id}: {str(e)}")
        flash("Erreur lors de la génération du PDF", "danger")
        return redirect(url_for('billing.view_proforma', proforma_id=proforma_id))
    
    # Création de la réponse
    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"inline; filename=proforma_{proforma.proforma_number}.pdf"
    
    return response



@main_bp.route('/converted_clients_list')
@login_required
def converted_clients_list():
    # Affiche tous les clients convertis avec le commercial et la note
    clients = Client.query.filter_by(type_client='client', is_blacklisted=False).order_by(Client.converted_by_id.desc()).all()
    commerciaux = {u.id: f"{u.prenom} {u.nom}" for u in User.query.all()}
    return render_template('partials/converted_clients_list.html', clients=clients, commerciaux=commerciaux)    


@main_bp.route('/unconverted_clients_list')
@login_required
def unconverted_clients_list():
    clients = Client.query.filter_by(type_client='prospect', is_blacklisted=False).all()
    commerciaux = {u.id: f"{u.prenom} {u.nom}" for u in User.query.all()}
    return render_template('partials/unconverted_clients_list.html', clients=clients, commerciaux=commerciaux)    


@main_bp.route('/notifications')
@login_required
def notifications():
    # Affiche toutes les notifications de l'utilisateur courant, non lues en haut
    notifications = NotificationModel.query.filter_by(user_id=current_user.id).order_by(
        NotificationModel.is_read.asc(), NotificationModel.created_at.desc()
    ).all()
    return render_template('notifications.html', notifications=notifications)


@main_bp.route('/notification/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    notif = NotificationModel.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        flash("Accès refusé.", "danger")
        return redirect(url_for('main.notifications'))
    notif.is_read = True
    db.session.commit()
    return redirect(url_for('main.notifications')) 


@main_bp.route('/add_approvisionnement/<site>', methods=['POST'])
@login_required
def add_approvisionnement(site):
    montant = request.form.get('montant')
    date_str = request.form.get('date')

    if not montant:
        flash("Le montant est requis.", "error")
        return redirect(url_for('main.expenses_by_site', site=site))

    try:
        montant = float(montant)
        # Si date spécifiée, on parse, sinon datetime UTC avec heure
        if date_str:
            # On conserve l'heure si l'utilisateur l'a saisie, sinon 00:00
            date_appro = datetime.strptime(date_str, '%Y-%m-%d')
        else:
            date_appro = datetime.utcnow()

        appro = Approvisionnement(montant=montant, site=site, date=date_appro)
        db.session.add(appro)
        db.session.commit()

        flash("Approvisionnement ajouté avec succès !", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de l'ajout : {str(e)}", "error")

    return redirect(url_for('main.expenses_by_site', site=site))


@main_bp.route('/expense/<int:expense_id>/approve', methods=['POST'])
@login_required
def approve_expense(expense_id):
    if not current_user.role.name == 'Administrateur':
        flash("Accès refusé.", "danger")
        return redirect(url_for('main.expenses_by_site', site=current_user.site))

    expense = Expense.query.get_or_404(expense_id)
    expense.statut = 'approuve'
    db.session.commit()
    flash("Dépense approuvée.", "success")
    return redirect(url_for('main.expenses_by_site', site=expense.site))



@main_bp.route('/expense/<int:expense_id>/reject', methods=['POST'])
@login_required
def reject_expense(expense_id):
    if not current_user.role.name == 'Administrateur':
        flash("Accès refusé.", "danger")
        return redirect(url_for('main.expenses_by_site', site=current_user.site))

    expense = Expense.query.get_or_404(expense_id)
    expense.statut = 'rejete'
    db.session.commit()
    flash("Dépense rejetée.", "warning")
    return redirect(url_for('main.expenses_by_site', site=expense.site))
 

""" @main_bp.route('/expense/<int:expense_id>/reject', methods=['POST'])
@login_required
def reject_expense(expense_id):
    if not current_user.role.name == 'Administrateur':
        flash("Accès refusé.", "danger")
        return redirect(url_for('main.expenses'))
    expense = Expense.query.get_or_404(expense_id)
    expense.statut = 'refuse'
    db.session.commit()
    flash("Dépense refusée.", "warning")
    return redirect(url_for('main.expenses'))   """ 

@main_bp.route('/expense/<int:expense_id>')
@login_required
def expense_detail(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    return render_template('expense_detail.html', expense=expense, get_priority_badge_class=get_priority_badge_class,
        get_status_badge_class=get_status_badge_class)    


@main_bp.route('/inventory/update_quantity/<int:item_id>', methods=['POST'])
@login_required
def update_inventory_quantity(item_id):
    item = InventoryItem.query.get_or_404(item_id)
    data = request.get_json()
    try:
        new_quantity = int(data.get('quantity'))
        if new_quantity < 0:
            return jsonify(success=False, message="Quantité invalide"), 400

        old_quantity = item.quantity
        item.quantity = new_quantity
        db.session.commit()

        # Envoi d'email admin
        subject = f"[ALERTE STOCK] Modification du stock - {item.name}"
        body = (
            f"Bonjour,\n\n"
            f"Le stock d’un article a été modifié :\n\n"
            f"- Article : {item.name}\n"
            f"- Ancienne quantité : {old_quantity}\n"
            f"- Nouvelle quantité : {new_quantity}\n"
            f"- Effectué par : {current_user.prenom} {current_user.nom} ({current_user.email})\n\n"
            f"Cordialement,\nSystème de gestion des stocks"
        )
        send_admin_notification(subject, body)

        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500




def send_sms_twilio(to, message):
    # Remplace par tes identifiants Twilio
    account_sid = 'TON_ACCOUNT_SID'
    auth_token = 'TON_AUTH_TOKEN'
    from_number = '+221775561233'  # format international, ex: '+1415xxxxxxx'
    client = TwilioClient(account_sid, auth_token)
    try:
        client.messages.create(
            body=message,
            from_=from_number,
            to=to  # format international, ex: '+22177xxxxxxx'
        )
        return True
    except Exception as e:
        print(f"Erreur envoi SMS Twilio: {e}")
        return False        

@main_bp.route('/api/calendar/events', methods=['GET', 'POST'])
@login_required
def calendar_events():
    if request.method == 'GET':
        events = CalendarEvent.query.order_by(CalendarEvent.start).all()
        return jsonify([
            {
                "id": event.id,
                "title": event.title,
                "start": event.start,
                "allDay": event.allDay
            } for event in events
        ])
    if request.method == 'POST':
        data = request.get_json()
        title = data.get("title")
        start = data.get("start")
        allDay = False if "T" in start else True

        event = CalendarEvent(title=title, start=start, allDay=allDay)
        db.session.add(event)
        db.session.commit()
        return jsonify({
            "id": event.id,
            "title": event.title,
            "start": event.start,
            "allDay": event.allDay
        }), 201
    
@main_bp.route('/installations/add', methods=['GET', 'POST'])
@login_required
def add_installation():
    if request.method == 'POST':
        # Récupération des données du formulaire
        prenom = request.form.get('prenom')
        nom = request.form.get('nom')
        telephone = request.form.get('tel')
        montant_total = float(request.form.get('total', 0))
        montant_avance = float(request.form.get('avance', 0))
        montant_restant = montant_total - montant_avance
        date_install = request.form.get('date_install')
        methode = request.form.get('methode')
        date_echeance = request.form.get('date_echeance')
        contrat = request.files.get('contrat')
        contrat_path = None

        # Gestion du fichier contrat
        if contrat and contrat.filename:
            filename = secure_filename(contrat.filename)
            upload_folder = os.path.join(current_app.static_folder, 'uploads', 'contrats')
            os.makedirs(upload_folder, exist_ok=True)
            contrat.save(os.path.join(upload_folder, filename))
            contrat_path = f'uploads/contrats/{filename}'

        # Création de l'installation
        installation = Installation(
            prenom=prenom,
            nom=nom,
            telephone=telephone,
            montant_total=montant_total,
            montant_avance=montant_avance,
            montant_restant=montant_restant,
            date_installation=datetime.strptime(date_install, '%Y-%m-%d') if date_install else None,
            methode_paiement=methode,
            date_echeance=datetime.strptime(date_echeance, '%Y-%m-%d') if date_echeance else None,
            contrat_path=contrat_path,
            statut='en_attente'
        )
        db.session.add(installation)
        db.session.commit()
        flash("Installation ajoutée avec succès.", "success")
        return redirect(url_for('main.installations'))

    return render_template('installations/new_installation.html')


@main_bp.route('/installations')
@login_required
def installations():
    if not current_user.has_permission('all'):
        flash("Vous n'avez pas accès à cette section.", "danger")
        return redirect(url_for('main.dashboard'))
    installations = Installation.query.order_by(Installation.created_at.desc()).all()
    somme_total = db.session.query(func.sum(Installation.montant_total)).scalar() or 0
    somme_restant = db.session.query(func.sum(Installation.montant_restant)).scalar() or 0
    return render_template('installations/list.html',
                            installations=installations,
                            somme_total=somme_total,
                            somme_restant=somme_restant)

@main_bp.route('/installations/<int:id>/versement', methods=['GET', 'POST'])
@login_required
def versement_installation(id):
    installation = Installation.query.get_or_404(id)
    if request.method == 'POST':
        montant_verse = float(request.form.get('montant_verse', 0))
        installation.montant_avance += montant_verse
        installation.montant_restant = installation.montant_total - installation.montant_avance
        db.session.commit()
        flash("Versement enregistré.", "success")
        return redirect(url_for('main.installations', id=id))
    return render_template('installations/versement.html', installation=installation)          


@main_bp.route('/installations/<int:installation_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_installation(installation_id):
    installation = Installation.query.get_or_404(installation_id)
    
    if request.method == 'POST':
        try:
            # Récupération des données du formulaire
            installation.prenom = request.form.get('prenom')
            installation.nom = request.form.get('nom')
            installation.telephone = request.form.get('tel')
            installation.montant_total = float(request.form.get('total', 0))
            installation.montant_avance = float(request.form.get('avance', 0))
            installation.montant_restant = installation.montant_total - installation.montant_avance
            installation.date_installation = datetime.strptime(request.form.get('date_install'), '%Y-%m-%d') if request.form.get('date_install') else None
            installation.methode_paiement = request.form.get('methode')
            installation.date_echeance = datetime.strptime(request.form.get('date_echeance'), '%Y-%m-%d') if request.form.get('date_echeance') else None
            installation.statut = request.form.get('statut', 'en_attente')

            # Gestion du fichier contrat (si nouveau fichier uploadé)
            contrat = request.files.get('contrat')
            if contrat and contrat.filename:
                # Supprimer l'ancien fichier s'il existe
                if installation.contrat_path:
                    old_path = os.path.join(current_app.static_folder, installation.contrat_path)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                # Sauvegarder le nouveau fichier
                filename = secure_filename(contrat.filename)
                upload_folder = os.path.join(current_app.static_folder, 'uploads', 'contrats')
                os.makedirs(upload_folder, exist_ok=True)
                contrat.save(os.path.join(upload_folder, filename))
                installation.contrat_path = f'uploads/contrats/{filename}'

            db.session.commit()
            flash("Installation modifiée avec succès.", "success")
            return redirect(url_for('main.installations'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors de la modification: {str(e)}", "danger")
            return redirect(url_for('main.edit_installation', installation_id=installation.id))
    
    # GET request - Afficher le formulaire pré-rempli
    return render_template('installations/edit_installation.html', installation=installation)

@main_bp.route('/installations/<int:installation_id>/delete', methods=['POST'])
@login_required
def delete_installation(installation_id):
    installation = Installation.query.get_or_404(installation_id)
    
    try:
        # Supprimer le fichier contrat associé s'il existe
        if installation.contrat_path:
            file_path = os.path.join(current_app.static_folder, installation.contrat_path)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        db.session.delete(installation)
        db.session.commit()
        flash("Installation supprimée avec succès.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la suppression: {str(e)}", "danger")
    
    return redirect(url_for('main.installations')) 

@main_bp.route('/devis')
@login_required
def devis_list():
    devis_list = Devis.query.order_by(Devis.created_at.desc()).all()
    technicians = User.query.join(Role).filter(Role.name == 'Technicien').all()  
    return render_template('devis/devis_list.html', 
                         devis_list=devis_list,
                         technicians=technicians)

@main_bp.route('/devis/create', methods=['POST'])
@login_required
def devis_create():
    nom = request.form.get('nom')
    prenom = request.form.get('prenom')
    telephone = request.form.get('telephone')
    commentaire = request.form.get('commentaire')
    
    # Créer le devis avec l'utilisateur courant comme créateur
    devis = Devis(
        nom=nom,
        prenom=prenom,
        telephone=telephone,
        commentaire=commentaire,
        user_id=current_user.id
    )
    
    # Auto-assigner si l'utilisateur est un technicien
    if current_user.role.name.lower() in ['technicien', 'technician']:
        devis.assigned_to = current_user.id
        devis.status = 'assigned'
    
    db.session.add(devis)
    db.session.commit()
    
    # Envoyer notification si assigné
    if devis.assigned_to:
        technician = User.query.get(devis.assigned_to)
        send_devis_assignment_notification(devis, technician)
    
    flash('Devis créé avec succès.', 'success')
    return redirect(url_for('main.devis_list'))

@main_bp.route('/devis/assign/<int:devis_id>', methods=['POST'])
@login_required
def assign_devis(devis_id):
    devis = Devis.query.get_or_404(devis_id)
    technician_id = request.form.get('technician_id')
    
    if not technician_id:
        return jsonify({'success': False, 'message': 'Technicien non sélectionné'}), 400
    
    technician = User.query.get(technician_id)
    if not technician:
        return jsonify({'success': False, 'message': 'Technicien introuvable'}), 404
    
    devis.assigned_to = technician_id
    devis.status = 'assigned'
    db.session.commit()
    
    # Envoyer une notification (à implémenter)
    send_devis_assignment_notification(devis, technician)
    
    flash('Devis assigné avec succès', 'success')
    return jsonify({'success': True, 'message': 'Devis assigné'})

@main_bp.route('/devis/complete/<int:devis_id>', methods=['POST'])
@login_required
def complete_devis(devis_id):
    devis = Devis.query.get_or_404(devis_id)
    
    # Vérifier que l'utilisateur courant est le technicien assigné
    if current_user.id != devis.assigned_to:
        abort(403)
    
    commentaire = request.form.get('commentaire')
    if commentaire:
        devis.commentaire = commentaire
    devis.status = 'completed'
    db.session.commit()
    
    flash('Devis complété avec succès', 'success')
    return redirect(url_for('main.devis_list'))

def send_devis_assignment_notification(devis, technician):
    """Envoie une notification au technicien lorsqu'un devis lui est assigné"""
    if technician and technician.email:
        # Construction du message
        message = f"""Bonjour {technician.prenom},

        Un nouveau devis vous a été assigné :

        Référence : #{devis.id}
        Client : {devis.prenom} {devis.nom}
        Téléphone : {devis.telephone}
        Date de création : {devis.created_at.strftime('%d/%m/%Y %H:%M')}
        
        Commentaire initial : 
        {devis.commentaire or "Aucun commentaire"}

        Veuillez vous connecter à l'application pour compléter ce devis."""

        # Envoi de l'email
        send_email(
            subject=f"Nouveau devis assigné - #{devis.id}",
            recipients=[technician.email, "diazfaye82@gmail.com"],  # Email du technicien + copie admin
            body=message
        )

        notification = create_notification(
            user_id=technician.id,
            message=f"Vous avez un nouveau devis pour {devis.prenom} {devis.nom}",
            
        )
        db.session.add(notification)
        db.session.commit()


@main_bp.route('/api/calendar/events/<int:event_id>', methods=['PUT', 'DELETE'])
@login_required
def calendar_event_update_delete(event_id):
    event = CalendarEvent.query.get_or_404(event_id)
    if request.method == 'PUT':
        data = request.get_json()
        event.title = data.get('title', event.title)
        event.start = data.get('start', event.start)
        event.allDay = data.get('allDay', event.allDay)
        db.session.commit()
        return jsonify({
            "id": event.id,
            "title": event.title,
            "start": event.start,
            "allDay": event.allDay
        })
    if request.method == 'DELETE':
        db.session.delete(event)
        db.session.commit()
        return jsonify({"success": True})    
    
@main_bp.route('/expense/<int:expense_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)

    if not current_user.role.name == 'Administrateur':
        flash("Accès refusé.", "danger")
        return redirect(url_for('main.expenses_by_site', site=expense.site))

    if request.method == 'POST':
        try:
            expense.titre = request.form['titre']
            expense.description = request.form.get('description')
            expense.montant = float(request.form['montant'])
            expense.categorie = request.form.get('categorie')
            date_depense = request.form.get('date_depense')
            expense.date_depense = datetime.strptime(date_depense, '%Y-%m-%d').date() if date_depense else date.today()

            db.session.commit()
            flash('Dépense modifiée avec succès.', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Erreur lors de la modification de la dépense.', 'error')

        return redirect(url_for('main.expenses_by_site', site=expense.site))

    return render_template('edit_expense.html', expense=expense)


@main_bp.route('/expense/<int:expense_id>/delete', methods=['POST'])
@login_required
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)

    if not current_user.role.name == 'Administrateur':
        flash("Accès refusé.", "danger")
        return redirect(url_for('main.expenses_by_site', site=expense.site))

    # Vérifie si déjà supprimé
    if expense.deleted_at:
        flash("Cette dépense est déjà dans la corbeille.", "warning")
        return redirect(url_for('main.expenses_by_site', site=expense.site))

    expense.deleted_at = datetime.utcnow()
    db.session.commit()

    # 🔹 Envoi d'email après suppression
    subject = f"[ALERTE] Dépense supprimée sur {expense.site}"
    body = (
        f"Bonjour,\n\n"
        f"La dépense suivante a été déplacée vers la corbeille :\n\n"
        f"- Titre : {expense.titre}\n"
        f"- Montant : {expense.montant} Fcfa\n"
        f"- Catégorie : {expense.categorie or 'Non définie'}\n"
        f"- Employé : {expense.user.prenom} {expense.user.nom if expense.user else ''}\n"
        f"- Site : {expense.site}\n"
        f"- Date de suppression : {expense.deleted_at.strftime('%d/%m/%Y %H:%M')}\n\n"
        f"Cordialement,\nSystème de gestion des dépenses"
    )
    send_admin_notification(subject, body)

    flash("Dépense envoyée dans la corbeille (restaurable 24h).", "info")
    return redirect(url_for('main.expenses_by_site', site=expense.site))


@main_bp.route('/appro-history')
@login_required
def appro_history():
    site = request.args.get('site')  # récupéré depuis l’URL

    query = Approvisionnement.query.order_by(Approvisionnement.date.desc())
    if site:
        query = query.filter_by(site=site)

    approvisionnements = query.all()
    return render_template(
        'appro_history.html',
        approvisionnements=approvisionnements,
        site=site
    )


@billing.route('/edit_invoice/<int:invoice_id>', methods=['GET', 'POST'])
@login_required
def edit_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    clients = BillingClient.query.all()
    products = Product.query.all()
    
    if request.method == 'POST':
        try:
            invoice.billing_client_id = request.form['client_id']
            invoice.invoice_number = request.form['invoice_number']
            invoice.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            
            # Gestion de la due_date qui peut être vide
            due_date_str = request.form.get('due_date')
            invoice.due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None
            
            invoice.tax_rate = float(request.form['tax_rate'])
            invoice.domaine = request.form.get('domaine')
            invoice.notes = request.form.get('notes')
            
            # Remise
            discount_type = request.form.get('discount_type')
            discount_value = float(request.form.get('discount_value', 0))
            if discount_type == 'percent':
                invoice.discount_percent = discount_value
                invoice.discount_amount = 0
            elif discount_type == 'amount':
                invoice.discount_percent = 0
                invoice.discount_amount = discount_value
            else:
                invoice.discount_percent = 0
                invoice.discount_amount = 0
                
            # Supprime les anciens items
            InvoiceItem.query.filter_by(invoice_id=invoice.id).delete()
            
            # Ajoute les nouveaux items
            items = zip(
                request.form.getlist('item_product_id[]'),
                request.form.getlist('item_description[]'),
                request.form.getlist('item_quantity[]'),
                request.form.getlist('item_unit_price[]'),
                request.form.getlist('item_discount[]')
            )
            for product_id, description, quantity, unit_price, discount in items:
                if not product_id:
                    continue
                item = InvoiceItem(
                    invoice_id=invoice.id,
                    product_id=int(product_id),
                    description=description,
                    quantity=float(quantity),
                    unit_price=float(unit_price),
                    discount_percent=float(discount)
                )
                db.session.add(item)
                
            db.session.commit()
            flash("Facture modifiée avec succès.", "success")
            return redirect(url_for('billing.manage_invoices'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors de la modification: {str(e)}", "danger")
    
    # Prépare les valeurs pour le formulaire
    discount_type = 'none'
    discount_value = 0
    if invoice.discount_percent > 0:
        discount_type = 'percent'
        discount_value = invoice.discount_percent
    elif invoice.discount_amount > 0:
        discount_type = 'amount'
        discount_value = invoice.discount_amount
        
    return render_template(
        'billing/edit_invoice.html',
        invoice=invoice,
        clients=clients,
        products=products,
        discount_type=discount_type,
        discount_value=discount_value
    )

@billing.route('/edit_proforma/<int:proforma_id>', methods=['GET', 'POST'])
@login_required
def edit_proforma(proforma_id):
    proforma = Proforma.query.get_or_404(proforma_id)
    clients = BillingClient.query.all()
    products = Product.query.all()
    
    if request.method == 'POST':
        try:
            proforma.billing_client_id = request.form['client_id']
            proforma.proforma_number = request.form['proforma_number']
            proforma.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            
            # Gestion de la due_date qui peut être vide
            due_date_str = request.form.get('due_date')
            proforma.due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None
            
            proforma.tax_rate = float(request.form['tax_rate'])
            proforma.domaine = request.form.get('domaine')
            proforma.notes = request.form.get('notes')
            
            # Remise
            discount_type = request.form.get('discount_type')
            discount_value = float(request.form.get('discount_value', 0))
            if discount_type == 'percent':
                proforma.discount_percent = discount_value
                proforma.discount_amount = 0
            elif discount_type == 'amount':
                proforma.discount_percent = 0
                proforma.discount_amount = discount_value
            else:
                proforma.discount_percent = 0
                proforma.discount_amount = 0
                
            # Supprime les anciens items
            ProformaItem.query.filter_by(proforma_id=proforma.id).delete()
            
            # Ajoute les nouveaux items
            items = zip(
                request.form.getlist('item_product_id[]'),
                request.form.getlist('item_description[]'),
                request.form.getlist('item_quantity[]'),
                request.form.getlist('item_unit_price[]'),
                request.form.getlist('item_discount[]')
            )
            for product_id, description, quantity, unit_price, discount in items:
                if not product_id:
                    continue
                item = ProformaItem(
                    proforma_id=proforma.id,
                    product_id=int(product_id),
                    description=description,
                    quantity=float(quantity),
                    unit_price=float(unit_price),
                    discount_percent=float(discount)
                )
                db.session.add(item)
                
            db.session.commit()
            flash("Proforma modifiée avec succès.", "success")
            return redirect(url_for('billing.manage_proformas'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors de la modification: {str(e)}", "danger")
    
    # Prépare les valeurs pour le formulaire
    discount_type = 'none'
    discount_value = 0
    if proforma.discount_percent > 0:
        discount_type = 'percent'
        discount_value = proforma.discount_percent
    elif proforma.discount_amount > 0:
        discount_type = 'amount'
        discount_value = proforma.discount_amount
        
    return render_template(
        'billing/edit_proforma.html',
        proforma=proforma,
        clients=clients,
        products=products,
        discount_type=discount_type,
        discount_value=discount_value
    )
@main_bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash("Vous ne pouvez pas supprimer votre propre compte.", "warning")
        return redirect(url_for('main.users'))
    user = User.query.get_or_404(user_id)
    try:
        db.session.delete(user)
        db.session.commit()
        flash("Utilisateur supprimé avec succès.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la suppression : {str(e)}", "danger")
    return redirect(url_for('main.users'))    

@billing.route('/billing/invoices/<int:invoice_id>/delete', methods=['POST'])
@login_required
def delete_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    try:
        db.session.delete(invoice)
        db.session.commit()
        flash("Facture supprimée avec succès.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la suppression de la facture : {str(e)}", "danger")
    return redirect(url_for('billing.manage_invoices'))    

@billing.route('/billing/proformas/<int:proforma_id>/delete', methods=['POST'])
@login_required
def delete_proforma(proforma_id):
    proforma = Proforma.query.get_or_404(proforma_id)
    try:
        db.session.delete(proforma)
        db.session.commit()
        flash("Proforma supprimée avec succès.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la suppression de la proforma : {str(e)}", "danger")
    return redirect(url_for('billing.manage_proformas'))   


def notify_due_events(app=None):
    if app is not None:
        with app.app_context():
            now = datetime.utcnow()
            due_events = CalendarEvent.query.filter(CalendarEvent.start <= now, CalendarEvent.notified == False).all()
            for event in due_events:
                # Conversion de event.start (str) en datetime
                try:
                    event_start_dt = datetime.fromisoformat(event.start)
                except Exception:
                    event_start_dt = now  # fallback si format non valide
                admins = User.query.join(Role).filter(Role.name == 'Administrateur').all()
                for admin in admins:
                    send_email(
                        subject="Rappel événement calendrier",
                        recipients=[admin.email],
                        body=f"L'événement '{event.title}' est arrivé à échéance ({event_start_dt.strftime('%d/%m/%Y %H:%M')})."
                    )
                if hasattr(event, 'commercial_id') and event.commercial_id:
                    commercial = User.query.get(event.commercial_id)
                    if commercial and commercial.email:
                        send_email(
                            subject="Rappel événement calendrier",
                            recipients=[commercial.email],
                            body=f"L'événement '{event.title}' est arrivé à échéance ({event_start_dt.strftime('%d/%m/%Y %H:%M')})."
                        )
                event.notified = True
            db.session.commit()
@main_bp.route('/inventory/outbound', methods=['POST'])
@login_required
def inventory_outbound():
    if not current_user.has_permission('inventory'):
        return jsonify({'success': False, 'message': 'Permission refusée'}), 403
    
    data = request.get_json()
    item_id = data.get('item_id')
    quantity = data.get('quantity')
    reason = data.get('reason', 'Sortie de stock')
    
    if not item_id or not quantity:
        return jsonify({'success': False, 'message': 'Données manquantes'}), 400
    
    try:
        item = InventoryItem.query.get(item_id)
        if not item:
            return jsonify({'success': False, 'message': 'Article non trouvé'}), 404
        
        quantity = int(quantity)
        if quantity <= 0:
            return jsonify({'success': False, 'message': 'Quantité invalide'}), 400
            
        if item.quantity < quantity:
            return jsonify({'success': False, 'message': 'Stock insuffisant'}), 400
            
        # Mise à jour du stock
        item.quantity -= quantity
        db.session.commit()

        # Envoi d'email admin
        subject = f"[ALERTE STOCK] Sortie de {quantity} unités - {item.name}"
        body = (
            f"Bonjour,\n\n"
            f"Une sortie de stock a été effectuée :\n\n"
            f"- Article : {item.name}\n"
            f"- Quantité sortie : {quantity}\n"
            f"- Nouveau stock : {item.quantity}\n"
            f"- Raison : {reason}\n"
            f"- Effectué par : {current_user.prenom} {current_user.nom} ({current_user.email})\n\n"
            f"Cordialement,\nSystème de gestion des stocks"
        )
        send_admin_notification(subject, body)
        
        return jsonify({
            'success': True,
            'message': 'Sortie de stock enregistrée',
            'new_quantity': item.quantity
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur sortie de stock: {str(e)}")
        return jsonify({'success': False, 'message': 'Erreur serveur'}), 500

@main_bp.route('/inventory/get_quantity/<int:item_id>')
@login_required
def get_inventory_quantity(item_id):
    if not current_user.has_permission('inventory'):
        return jsonify({'success': False, 'message': 'Permission refusée'}), 403
    
    item = InventoryItem.query.get(item_id)
    if not item:
        return jsonify({'success': False, 'message': 'Article non trouvé'}), 404
    
    return jsonify({
        'success': True,
        'quantity': item.quantity,
        'item_name': item.name
    })    

@billing.route('/billing/invoices/<int:invoice_id>/duplicate', methods=['GET'])
@login_required
def duplicate_invoice(invoice_id):
    try:
        original_invoice = Invoice.query.get_or_404(invoice_id)
        
        # Générer un nouveau numéro de facture
        today = datetime.utcnow().date()
        invoice_count = Invoice.query.count()
        new_number = f"FACT-{today.strftime('%Y%m%d')}-{invoice_count + 1}"
        
        # Créer la nouvelle facture avec les données de l'originale
        new_invoice = Invoice(
            invoice_number=new_number,
            billing_client_id=original_invoice.billing_client_id,
            date=today,
            due_date=today + timedelta(days=30),  # 30 jours par défaut
            tax_rate=original_invoice.tax_rate,
            domaine=original_invoice.domaine,
            notes=original_invoice.notes,
            status='draft',
            discount_percent=original_invoice.discount_percent,
            discount_amount=original_invoice.discount_amount
        )
        
        db.session.add(new_invoice)
        db.session.flush()  # Pour obtenir l'ID
        
        # Dupliquer les articles
        for item in original_invoice.items:
            new_item = InvoiceItem(
                invoice_id=new_invoice.id,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                discount_percent=item.discount_percent,
                product_id=item.product_id
            )
            db.session.add(new_item)
        
        db.session.commit()
        flash('Facture dupliquée avec succès. Vous pouvez maintenant la modifier.', 'success')
        return redirect(url_for('billing.edit_invoice', invoice_id=new_invoice.id))
    
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la duplication: {str(e)}", 'danger')
        return redirect(url_for('billing.view_invoice', invoice_id=invoice_id))                
@billing.route('/billing/proformas/<int:proforma_id>/duplicate', methods=['GET'])
@login_required
def duplicate_proforma(proforma_id):
    try:
        original_proforma = Proforma.query.get_or_404(proforma_id)
        
        # Générer un nouveau numéro de proforma
        today = datetime.utcnow().date()
        proforma_count = Proforma.query.count()
        new_number = f"PRO-{today.strftime('%Y%m%d')}-{proforma_count + 1}"
        
        # Créer la nouvelle proforma avec les données de l'originale
        new_proforma = Proforma(
            proforma_number=new_number,
            billing_client_id=original_proforma.billing_client_id,
            date=today,
            valid_until=today + timedelta(days=30),  # 30 jours de validité par défaut
            tax_rate=original_proforma.tax_rate,
            domaine=original_proforma.domaine,
            notes=original_proforma.notes,
            status='draft',
            discount_percent=original_proforma.discount_percent,
            discount_amount=original_proforma.discount_amount
        )
        
        db.session.add(new_proforma)
        db.session.flush()  # Pour obtenir l'ID
        
        # Dupliquer les articles
        for item in original_proforma.items:
            new_item = ProformaItem(
                proforma_id=new_proforma.id,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                discount_percent=item.discount_percent,
                product_id=item.product_id
            )
            db.session.add(new_item)
        
        db.session.commit()
        flash('Proforma dupliquée avec succès. Vous pouvez maintenant la modifier.', 'success')
        return redirect(url_for('billing.edit_proforma', proforma_id=new_proforma.id))
    
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la duplication: {str(e)}", 'danger')
        return redirect(url_for('billing.view_proforma', proforma_id=proforma_id))    
@main_bp.route('/expenses/<site>')
@login_required
def expenses_by_site(site):
    try:
        if not current_user.has_permission('expenses'):
            flash("Vous n'avez pas accès à cette section.", "error")
            return redirect(url_for('main.dashboard'))

        if site not in ['Dakar', 'Mbour']:
            flash("Site invalide.", "error")
            return redirect(url_for('main.dashboard'))

        # ----------- Filtres -----------
        month = request.args.get('month')
        month_int = int(month) if month else None
        category = request.args.get('category')
        employee = request.args.get('employee')

        # ----------- Dépenses (toutes pour affichage) -----------
        expenses_query = Expense.query.filter_by(site=site)\
                                      .filter(Expense.deleted_at.is_(None))
        if month_int:
            expenses_query = expenses_query.filter(db.extract('month', Expense.date_depense) == month_int)
        if category:
            expenses_query = expenses_query.filter(Expense.categorie == category)
        if employee:
            expenses_query = expenses_query.filter(Expense.user_id == int(employee))
        expenses = expenses_query.order_by(Expense.created_at.desc()).all()

        # ----------- Approvisionnements (totaux) -----------
        total_appro_query = db.session.query(db.func.sum(Approvisionnement.montant))\
                                      .filter(Approvisionnement.site == site)
        if month_int:
            total_appro_query = total_appro_query.filter(db.extract('month', Approvisionnement.date) == month_int)
        total_appro = total_appro_query.scalar() or 0

        # ----------- Totaux dépenses (approuvées uniquement) -----------
        total_depenses_query = db.session.query(db.func.sum(Expense.montant))\
                                         .filter(
                                             Expense.site == site,
                                             Expense.deleted_at.is_(None),
                                             Expense.statut == 'approuve'
                                         )
        if month_int:
            total_depenses_query = total_depenses_query.filter(db.extract('month', Expense.date_depense) == month_int)
        if category:
            total_depenses_query = total_depenses_query.filter(Expense.categorie == category)
        if employee:
            total_depenses_query = total_depenses_query.filter(Expense.user_id == int(employee))
        total_depenses = total_depenses_query.scalar() or 0

        # ----------- Calculs bénéfices/pertes -----------
        montant_restant = total_appro - total_depenses
        benefice = montant_restant if montant_restant > 0 else 0
        pertes = abs(montant_restant) if montant_restant < 0 else 0

        # ----------- Données graphiques par mois (approvisionnement & dépenses approuvées) -----------
        appro_mensuel = []
        depenses_mensuel = []
        for m in range(1, 13):
            appro_m = db.session.query(db.func.sum(Approvisionnement.montant))\
                                .filter(Approvisionnement.site == site)\
                                .filter(db.extract('month', Approvisionnement.date) == m).scalar() or 0

            dep_m = db.session.query(db.func.sum(Expense.montant))\
                              .filter(
                                  Expense.site == site,
                                  Expense.deleted_at.is_(None),
                                  Expense.statut == 'approuve'
                              )\
                              .filter(db.extract('month', Expense.date_depense) == m).scalar() or 0

            appro_mensuel.append(float(appro_m))
            depenses_mensuel.append(float(dep_m))

        # ----------- Liste des catégories & employés pour filtres -----------
        categories = db.session.query(Expense.categorie)\
                               .filter_by(site=site)\
                               .filter(Expense.deleted_at.is_(None))\
                               .distinct().all()
        categories = [c[0] for c in categories]

        employees = User.query.join(Expense, Expense.user_id == User.id)\
                              .filter(Expense.site == site, Expense.deleted_at.is_(None))\
                              .distinct().all()
        for emp in employees:
            emp.display_name = f"{emp.prenom} {emp.nom}".strip()

        return render_template(
            'expenses_dashboard.html',
            site=site,
            expenses=expenses,
            total_appro=total_appro,
            total_depenses=total_depenses,
            montant_restant=montant_restant,
            benefice=benefice,
            pertes=pertes,
            appro_mensuel=appro_mensuel,
            depenses_mensuel=depenses_mensuel,
            month_selected=month,
            selected_category=category,
            selected_employee=int(employee) if employee else None,
            categories=categories,
            employees=employees,
            get_status_badge_class=get_status_badge_class
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Erreur serveur : {e}", 500


@main_bp.route('/expenses/trash')
@login_required
def expenses_trash():
    if not current_user.has_permission('expenses'):
        flash("Vous n'avez pas accès à cette section.", "error")
        return redirect(url_for('main.dashboard'))

    # Administrateur : voir toutes les dépenses supprimées
    if current_user.role.name == 'Administrateur':
        trashed_expenses = Expense.query.filter(Expense.deleted_at.isnot(None))\
                                        .order_by(Expense.deleted_at.desc()).all()
    # Administration : voir seulement celles de son site
    elif current_user.role.name == 'administration':
        trashed_expenses = Expense.query.filter(Expense.site == current_user.site,
                                                Expense.deleted_at.isnot(None))\
                                        .order_by(Expense.deleted_at.desc()).all()
    # Employé : voir seulement les siennes
    else:
        trashed_expenses = Expense.query.filter(Expense.user_id == current_user.id,
                                                Expense.deleted_at.isnot(None))\
                                        .order_by(Expense.deleted_at.desc()).all()

    return render_template(
        'expenses_trash.html',
        trashed_expenses=trashed_expenses,
        get_status_badge_class=get_status_badge_class
    )

# Restaurer une dépense
@main_bp.route('/expense/<int:expense_id>/restore', methods=['POST'])
@login_required
def restore_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)

    if not current_user.has_permission('expenses'):
        flash("Vous n'avez pas accès à cette action.", "error")
        return redirect(url_for('main.dashboard'))

    # Restauration
    expense.deleted_at = None
    db.session.commit()

    # Envoi mail aux administrateurs
    try:
        from flask_mail import Message
        from extensions import mail

        msg = Message(
                subject="Restauration d'une dépense",
                recipients=["mohamethlo01@esp.sn", "adiarra@netsys-info.com"],  # 👈 Mets ici tes admins
                #recipients=["mohamethlo01@esp.sn"],  # 👈 Mets ici tes admins
                body=f"""
            Bonjour,

            La dépense suivante vient d'être restaurée par {current_user.username} :

            - ID : {expense.id}
            - Titre : {expense.titre}        
            - Montant : {expense.montant}    
            - Site : {expense.site}

            Cordialement,
            Votre application Gesnetsys
            """
            )

        mail.send(msg)
    except Exception as e:
        print(f"[ERREUR ENVOI MAIL] {e}")  # Log en console si problème

    flash("Dépense restaurée avec succès.", "success")
    return redirect(url_for('main.expenses_trash'))


# Supprimer définitivement
@main_bp.route('/expense/<int:expense_id>/force_delete', methods=['POST'])
@login_required
def force_delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)

    if not current_user.has_permission('expenses'):
        flash("Vous n'avez pas accès à cette action.", "error")
        return redirect(url_for('main.dashboard'))

    try:
        # Sauvegarder les infos avant suppression pour le mail
        expense_info = {
            "id": expense.id,
            "titre": getattr(expense, "titre", "N/A"),   # 🔹 on récupère titre si dispo
            "montant": getattr(expense, "montant", "N/A"),
            "site": getattr(expense, "site", "N/A")
        }

        db.session.delete(expense)
        db.session.commit()

        # Préparer et envoyer le mail
        msg = Message(
            subject="Suppression définitive d'une dépense",
            recipients=["mohamethlo01@esp.sn", "adiarra@netsys-info.com"],  # 👈 Mets ici les vrais emails
            #recipients=["mohamethlo01@esp.sn"],  # 👈 Mets ici les vrais emails
            body=f"""
                    Bonjour,

                    La dépense suivante vient d'être SUPPRIMÉE DÉFINITIVEMENT par {current_user.username} :

                    - ID : {expense_info['id']}
                    - Titre : {expense_info['titre']}
                    - Montant : {expense_info['montant']}
                    - Site : {expense_info['site']}

                    ⚠️ Cette dépense n'est plus récupérable.

                    Cordialement,
                    Votre application Gesnetsys
                    """
        )
        mail.send(msg)

    except Exception as e:
        flash("La dépense a été supprimée, mais l'envoi du mail a échoué.", "warning")
        print(f"[ERREUR ENVOI MAIL] {e}")

    flash("Dépense supprimée définitivement.", "danger")
    return redirect(url_for('main.expenses_trash'))



def clean_trash():
    # MODE TEST LOCAL : supprime après 1 minute
    expiration_time = datetime.utcnow() - timedelta(hours=24)
    old_expenses = Expense.query.filter(
        Expense.deleted_at.isnot(None),
        Expense.deleted_at < expiration_time
    ).all()

    for expense in old_expenses:
        db.session.delete(expense)

    db.session.commit()
    print(f"{len(old_expenses)} dépenses supprimées définitivement (plus de 1 minute dans la corbeille).")



@main_bp.route('/api/expenses/trash')
@login_required
def api_trash():
    trashed_expenses = Expense.query.filter(Expense.deleted_at.isnot(None))\
                                    .order_by(Expense.deleted_at.desc()).all()
    return jsonify([
        {
            "id": e.id,
            "titre": e.titre,
            "montant": int(e.montant),
            "categorie": e.categorie,
            "statut": e.statut,
            "date_depense": e.date_depense.strftime("%d/%m/%Y"),
            "deleted_at": e.deleted_at.strftime("%d/%m/%Y %H:%M")
        }
        for e in trashed_expenses
    ])

# ------------------------ Envoie de mail automatique --------------------

def send_admin_notification(subject, body):
    """Envoie un mail à l’administrateur"""
    try:
        with current_app.app_context():
            msg = Message(
                subject=subject,
                recipients=["mohamethlo01@esp.sn", "adiarra@netsys-info.com"],  # <-- mets ici l'email de l’admin
                #recipients=["mohamethlo01@esp.sn"],  # <-- mets ici l'email de l’admin
                body=body
            )
            mail.send(msg)
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'email : {e}")
