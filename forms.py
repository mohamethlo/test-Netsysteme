from flask_wtf import FlaskForm
from wtforms import SelectMultipleField, StringField, SubmitField, TextAreaField, SelectField, DateTimeField, IntegerField, FloatField, BooleanField, PasswordField, TimeField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange
from wtforms.widgets import DateTimeLocalInput

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Mot de passe', validators=[DataRequired()])
    remember = BooleanField('Se souvenir de moi')

class UserForm(FlaskForm):
    username = StringField('Nom d\'utilisateur', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    nom = StringField('Nom', validators=[DataRequired(), Length(max=100)])
    prenom = StringField('Prénom', validators=[DataRequired(), Length(max=100)])
    telephone = StringField('Téléphone', validators=[Optional(), Length(max=20)])
    role_id = SelectField('Rôle', coerce=int, validators=[DataRequired()])
    password = PasswordField('Mot de passe', validators=[DataRequired(), Length(min=6)])

class ClientForm(FlaskForm):
    nom = StringField('Nom', validators=[DataRequired(), Length(max=100)])
    prenom = StringField('Prénom', validators=[Optional(), Length(max=100)])
    entreprise = StringField('Entreprise', validators=[Optional(), Length(max=100)])
    email = StringField('Email', validators=[Optional(), Email()])
    telephone = StringField('Téléphone', validators=[Optional(), Length(max=20)])
    adresse = TextAreaField('Adresse')
    ville = StringField('Ville', validators=[Optional(), Length(max=100)])
    code_postal = StringField('Code postal', validators=[Optional(), Length(max=10)])
    type_client = SelectField('Type', choices=[('prospect', 'Prospect'), ('client', 'Client')])

""" class InterventionForm(FlaskForm): 
    titre = StringField('Titre', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description')
    client_id = SelectField('Client', coerce=int, validators=[DataRequired()])
    technicien_id = SelectField('Technicien', coerce=int, validators=[Optional()])
    date_prevue = DateTimeField('Date prévue', validators=[DataRequired()], widget=DateTimeLocalInput())
    duree_estimee = IntegerField('Durée estimée (minutes)', validators=[Optional(), NumberRange(min=1)])
    priorite = SelectField('Priorité', choices=[
        ('basse', 'Basse'),
        ('normale', 'Normale'),
        ('haute', 'Haute'),
        ('urgente', 'Urgente')
    ])
    adresse = TextAreaField('Adresse')"""
class InterventionForm(FlaskForm):
    #titre = StringField('Titre', validators=[DataRequired()])
    description = TextAreaField('Description')
    client_id = SelectField('Client', coerce=int, validators=[Optional()])
    technicien_id = SelectField('Technicien', coerce=int, validators=[Optional()])
    autres_intervenants = SelectMultipleField('Autres intervenants', coerce=int, validators=[Optional()])
    date_prevue = DateTimeField('Date prévue', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    date_realisation = DateTimeField('Date de réalisation', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    duree_estimee = IntegerField('Durée estimée (minutes)', validators=[Optional(), NumberRange(min=1)])
    duree_reelle = IntegerField('Durée réelle (minutes)', validators=[Optional(), NumberRange(min=1)])
    statut = SelectField('Statut', choices=[('planifiee', 'Planifiée'), ('en_cours', 'En cours'), ('terminee', 'Terminée'), ('annulee', 'Annulée')])
    priorite = SelectField('Priorité', choices=[('basse', 'Basse'), ('normale', 'Normale'), ('haute', 'Haute'), ('urgente', 'Urgente')])
    adresse = TextAreaField('Adresse')
    type_intervention = SelectField(
        "Type d'intervention",
        choices=[('Installation', 'Installation'), ('Maintenance', 'Maintenance')],
        validators=[DataRequired()]
    )
    societe = StringField('Société')
    representant = StringField('Représentant')
    telephone = StringField('Téléphone')
    taches_realisees = TextAreaField('Tâches réalisées')
    heure_arrivee = TimeField('Heure d\'arrivée', validators=[Optional()])
    heure_depart = TimeField('Heure de départ', validators=[Optional()])
    duree_intervention = TimeField('Durée intervention', validators=[Optional()])
    observations_technicien = TextAreaField('Observations technicien')
    id_dvr_nvr = StringField('ID DVR/NVR')
    mdp_dvr_nvr = StringField('MDP DVR/NVR')
    qr_code_path = StringField('QR Code (chemin)')
    signature_data = StringField('Signature (base64)')

class InventoryItemForm(FlaskForm):
    name = StringField('Nom', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description')
    reference = StringField('Référence', validators=[Optional(), Length(max=100)])
    category_id = SelectField('Catégorie', coerce=int, validators=[Optional()])
    quantity = IntegerField('Quantité', validators=[DataRequired(), NumberRange(min=0)])
    unit = StringField('Unité', validators=[Optional(), Length(max=20)])
    prix_achat = FloatField('Prix d\'achat', validators=[Optional(), NumberRange(min=0)])
    prix_vente = FloatField('Prix de vente', validators=[Optional(), NumberRange(min=0)])
    seuil_alerte = IntegerField('Seuil d\'alerte', validators=[DataRequired(), NumberRange(min=0)])
    fournisseur = StringField('Fournisseur', validators=[Optional(), Length(max=100)])
    emplacement = StringField('Emplacement', validators=[Optional(), Length(max=100)])

class ExpenseForm(FlaskForm):
    titre = StringField('Titre', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description')
    montant = FloatField('Montant', validators=[DataRequired(), NumberRange(min=0)])
    categorie = StringField('Catégorie', validators=[Optional(), Length(max=100)])
    date_depense = DateTimeField('Date de dépense', validators=[DataRequired()])

class WorkLocationForm(FlaskForm):
    name = StringField('Nom', validators=[DataRequired(), Length(max=100)])
    address = StringField('Adresse', validators=[Optional(), Length(max=255)])
    latitude = FloatField('Latitude', validators=[DataRequired()])
    longitude = FloatField('Longitude', validators=[DataRequired()])
    radius = IntegerField('Rayon (mètres)', validators=[DataRequired(), NumberRange(min=1)])
    type = SelectField('Type de zone', choices=[('bureau', 'Bureau'), ('chantier', 'Chantier')], default='bureau')

class SalaryAdvanceForm(FlaskForm):
    montant = FloatField('Montant demandé (€)', validators=[DataRequired(), NumberRange(min=1)])
    motif = TextAreaField('Motif', validators=[DataRequired()])
    submit = SubmitField('Demander une avance')