
from flask_login import UserMixin
from datetime import datetime, date
from extensions import db
from flask_login import UserMixin
from datetime import datetime, date
from sqlalchemy import func
from flask_sqlalchemy import SQLAlchemy

class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    permissions = db.Column(db.Text)  # Comma-separated permissions
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Role {self.name}>'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    telephone = db.Column(db.String(20))
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    permissions = db.Column(db.String(255))  # ex: "attendance,clients"
    site = db.Column(db.String(50))
    
    # Relationships
    role = db.relationship('Role', backref='users')
    attendances = db.relationship('Attendance', backref='user', lazy=True)
    interventions_assigned = db.relationship('Intervention', foreign_keys='Intervention.technicien_id', backref='technicien', lazy=True)
    interventions_created = db.relationship('Intervention', foreign_keys='Intervention.created_by_id', backref='created_by', lazy=True)
    expenses = db.relationship('Expense', foreign_keys='Expense.user_id', backref='user', lazy=True)
    """ 
    def has_permission(self, permission):
        if not self.role:
            return False
        if self.role.permissions == 'all':
            return True
        permissions = self.role.permissions.split(',') if self.role.permissions else []
        return permission in permissions """
    
    def has_permission(self, permission):
        # Si l'utilisateur a toutes les permissions
        if self.permissions == 'all':
            return True
        # Sinon, regarde dans ses permissions personnalisées
        if self.permissions:
            if permission in self.permissions.split(','):
                return True
        # Sinon, regarde dans les permissions du rôle
        if self.role:
            if self.role.permissions == 'all':
                return True
            if self.role.permissions:
                if permission in self.role.permissions.split(','):
                    return True
        return False
    
    def __repr__(self):
        return f'<User {self.username}>'

class WorkLocation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), default="bureau")  # "bureau" ou "chantier"
    address = db.Column(db.String(255))
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    radius = db.Column(db.Integer, default=100)  # meters
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<WorkLocation {self.name}>'

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, default=date.today)
    check_in = db.Column(db.DateTime)
    check_out = db.Column(db.DateTime)
    check_in_location = db.Column(db.String(255))
    check_out_location = db.Column(db.String(255))
    check_in_lat = db.Column(db.Float)
    check_in_lng = db.Column(db.Float)
    check_out_lat = db.Column(db.Float)
    check_out_lng = db.Column(db.Float)
    work_location_id = db.Column(db.Integer, db.ForeignKey('work_location.id'))
    status = db.Column(db.String(20), default='present')  # present, absent, late
    notes = db.Column(db.Text)
    #type_pointage = db.Column(db.String(20))
    
    work_location = db.relationship('WorkLocation', backref='attendances')
    
    @property
    def total_hours(self):
        if self.check_in and self.check_out:
            return (self.check_out - self.check_in).total_seconds() / 3600
        return 0
    
    def __repr__(self):
        return f'<Attendance {self.user.username} - {self.date}>'

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100))
    entreprise = db.Column(db.String(100))
    email = db.Column(db.String(120))
    telephone = db.Column(db.String(20), unique=True)
    adresse = db.Column(db.Text)
    ville = db.Column(db.String(100))
    code_postal = db.Column(db.String(10))
    type_client = db.Column(db.String(20), default='prospect')  # prospect, client
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'))  # ou commercial_id
    is_blacklisted = db.Column(db.Boolean, default=False)
    note_conversion = db.Column(db.Text)  # Note sur la conversion du prospect en client
    converted_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    converted_by = db.relationship('User', foreign_keys=[converted_by_id])
    date_blacklisted = db.Column(db.DateTime)
    reminders = db.relationship('Reminder', backref='client', lazy='dynamic')
    import_history_id = db.Column(db.Integer, db.ForeignKey('client_import_history.id'))
    @staticmethod
    def telephone_exists(telephone):
        """Check if a phone number already exists"""
        return Client.query.filter_by(telephone=telephone).first() is not None
    
    
    """ @property
    def next_reminder(self):
        if self.reminders.count() > 0:
            return self.reminders.order_by(Reminder.created_at.desc()).first()
        return None """
    @property
    def next_reminder(self):
        """Version simplifiée mais robuste"""
        return getattr(self, 'reminders', None) and \
            self.reminders.order_by(Reminder.created_at.desc()).first()
        
    # Relationships
    interventions = db.relationship('Intervention', backref='client', lazy=True)
    
    def __repr__(self):
        return f'<Client {self.nom} {self.prenom or ""}>'

autres_intervenants_assoc = db.Table(
    'autres_intervenants_assoc',
    db.Column('intervention_id', db.Integer, db.ForeignKey('intervention.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)
class Intervention(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    #titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)
    client_libre_nom = db.Column(db.String(200))
    client_libre_telephone = db.Column(db.String(20))
    technicien_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date_prevue = db.Column(db.DateTime, nullable=False)
    date_realisation = db.Column(db.DateTime)
    duree_estimee = db.Column(db.Integer)  # en minutes
    duree_reelle = db.Column(db.Integer)  # en minutes
    statut = db.Column(db.String(20), default='planifiee')  # planifiee, en_cours, terminee, annulee
    priorite = db.Column(db.String(20), default='normale')  # basse, normale, haute, urgente
    adresse = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Nouveaux champs pour l'intervention:
    type_intervention = db.Column(db.String(100))
    societe = db.Column(db.String(100))
    representant = db.Column(db.String(100))
    telephone = db.Column(db.String(30))

    autres_intervenants = db.relationship(
        'User',
        secondary=autres_intervenants_assoc,
        backref='interventions_autres',
        lazy='subquery'
    )
    
    taches_realisees = db.Column(db.Text)
    heure_arrivee = db.Column(db.Time)
    heure_depart = db.Column(db.Time)
    duree_intervention = db.Column(db.Time)
    observations_technicien = db.Column(db.Text)
    id_dvr_nvr = db.Column(db.String(100))
    mdp_dvr_nvr = db.Column(db.String(100))
    qr_code_path = db.Column(db.String(255))
    signature_data = db.Column(db.Text)
    materiels = db.relationship('InterventionMaterial', backref='intervention', lazy='joined')
    def __repr__(self):
        return f'<Intervention {self.titre}>'

class InventoryCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    items = db.relationship('InventoryItem', backref='category', lazy=True)
    
    def __repr__(self):
        return f'<InventoryCategory {self.name}>'

class InventoryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    reference = db.Column(db.String(100), unique=True)
    category_id = db.Column(db.Integer, db.ForeignKey('inventory_category.id'))
    quantity = db.Column(db.Integer, default=0)
    unit = db.Column(db.String(20), default='pièce')
    prix_achat = db.Column(db.Float)
    prix_vente = db.Column(db.Float)
    seuil_alerte = db.Column(db.Integer, default=10)
    fournisseur = db.Column(db.String(100))
    emplacement = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    image_path = db.Column(db.String(255))
    
    @property
    def is_low_stock(self):
        return self.quantity <= self.seuil_alerte
    
    def __repr__(self):
        return f'<InventoryItem {self.name}>'

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    montant = db.Column(db.Float, nullable=False)
    categorie = db.Column(db.String(100))
    date_depense = db.Column(db.Date, default=date.today)
    statut = db.Column(db.String(20), default='en_attente')  # en_attente, approuve, refuse
    justificatif = db.Column(db.String(512))  # path to uploaded file
    notes_admin = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    site = db.Column(db.String(50))
    approved_by = db.relationship('User', foreign_keys=[approved_by_id], backref='approved_expenses')

    # === nouveau champ ===
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)

    def __repr__(self):
        return f'<Expense {self.titre} - {self.montant}Fcfa>'

    def is_deleted(self):
        """Retourne True si la dépense est marquée supprimée (dans la corbeille)."""
        return self.deleted_at is not None

    def can_restore(self, hours=24):
        """Retourne True si la dépense est restaurable (supprimée depuis moins de `hours`)."""
        if not self.deleted_at:
            return False
        return (datetime.utcnow() - self.deleted_at) < timedelta(hours=hours)


class SalaryAdvance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    motif = db.Column(db.Text)
    date_demande = db.Column(db.Date, default=date.today)
    statut = db.Column(db.String(20), default='en_attente')  # en_attente, approuve, refuse
    notes_admin = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    user = db.relationship('User', foreign_keys=[user_id], backref='salary_advances')
    approved_by = db.relationship('User', foreign_keys=[approved_by_id], backref='approved_advances')
    
    def __repr__(self):
        return f'<SalaryAdvance {self.user.username} - {self.montant}€>'

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_messages')
    
    def __repr__(self):
        return f'<Message {self.subject}>'
    


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    message = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref='notifications')

    def __repr__(self):
        return f'<Notification {self.id}>'
 

class InterventionMaterial(db.Model):
    __tablename__ = 'intervention_material'
    id = db.Column(db.Integer, primary_key=True)
    intervention_id = db.Column(db.Integer, db.ForeignKey('intervention.id'))
    article_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'))
    quantite = db.Column(db.Integer, nullable=False)
    article = db.relationship('InventoryItem')

class Reminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    remind_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class QuoteRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    details = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Devis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    telephone = db.Column(db.String(20), nullable=False)
    commentaire = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'))  # Technicien assigné
    status = db.Column(db.String(20), default='pending')  # pending, assigned, completed
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Créateur du devis
    user = db.relationship('User', foreign_keys=[user_id], backref='created_devis')
    technician = db.relationship('User', foreign_keys=[assigned_to], backref='assigned_devis')            # Relation pour accéder à l'utilisateur       

#Intégration du module de facturation

class BillingClient(db.Model):
    """Client spécifique pour le module de facturation"""
    __tablename__ = 'billing_client'
    
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(120))
    contact_name = db.Column(db.String(80))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    tax_id = db.Column(db.String(50))  # Numéro d'identification fiscale
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relations
    invoices = db.relationship('Invoice', backref='billing_client', lazy=True)
    proformas = db.relationship('Proforma', backref='billing_client', lazy=True)

class Invoice(db.Model):
    """Modèle pour les factures"""
    __tablename__ = 'invoice'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=True)
    billing_client_id = db.Column(db.Integer, db.ForeignKey('billing_client.id'), nullable=True)
    date = db.Column(db.Date, default=datetime.utcnow)
    due_date = db.Column(db.Date)
    tax_rate = db.Column(db.Float, default=0.18)  # TVA 18% par défaut
    status = db.Column(db.String(20), default='draft')  # draft, sent, paid, cancelled
    notes = db.Column(db.Text)
    domaine = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    discount_percent = db.Column(db.Float, default=0.0)  # Pourcentage de remise
    discount_amount = db.Column(db.Float, default=0.0)   # Montant fixe de remise

    
    # Relation avec les lignes de facture
    items = db.relationship('InvoiceItem', backref='invoice', lazy=True, cascade="all, delete-orphan")

    def total_amount(self):
        return sum(item.subtotal() for item in self.items)

    def tax_amount(self):
        return self.total_amount() * self.tax_rate

    def total_with_tax(self):
        return self.total_amount() * (1 + self.tax_rate)
    
    def total_before_discount(self):
        return self.total_amount() * (1 + self.tax_rate)

    def discount_value(self):
        if self.discount_percent > 0:
            return self.total_before_discount() * (self.discount_percent / 100)
        return self.discount_amount

    def total_with_tax_and_discount(self):
        return self.total_before_discount() - self.discount_value()

class Proforma(db.Model):
    """Modèle pour les proformas"""
    __tablename__ = 'proforma'
    
    id = db.Column(db.Integer, primary_key=True)
    proforma_number = db.Column(db.String(50), unique=True)
    billing_client_id = db.Column(db.Integer, db.ForeignKey('billing_client.id'), nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow)
    valid_until = db.Column(db.Date)
    tax_rate = db.Column(db.Float, default=0.18)
    status = db.Column(db.String(20), default='draft')  # draft, sent, converted, cancelled
    notes = db.Column(db.Text)
    domaine = db.Column(db.String(50), nullable=True)
    converted_to_invoice = db.Column(db.Boolean, default=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'))  # Lien vers la facture si convertie
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    discount_percent = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Float, default=0.0)

    def total_before_discount(self):
        return self.total_amount() * (1 + self.tax_rate)

    def discount_value(self):
        if self.discount_percent > 0:
            return self.total_before_discount() * (self.discount_percent / 100)
        return self.discount_amount

    def total_with_tax_and_discount(self):
        return self.total_before_discount() - self.discount_value()

    # Relation avec les lignes de proforma
    items = db.relationship('ProformaItem', backref='proforma', lazy=True, cascade="all, delete-orphan")

    def total_amount(self):
        return sum(item.subtotal() for item in self.items)

    def tax_amount(self):
        return self.total_amount() * self.tax_rate

    def total_with_tax(self):
        return self.total_amount() * (1 + self.tax_rate)

class InvoiceItem(db.Model):
    """Lignes d'une facture"""
    __tablename__ = 'invoice_item'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id', ondelete='CASCADE'), nullable=False)
    #invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'))
    description = db.Column(db.String(200), nullable=True)
    quantity = db.Column(db.Float, default=1)
    unit_price = db.Column(db.Float, nullable=False)
    tax_rate = db.Column(db.Float)  # Taux spécifique pour cette ligne
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    discount_percent = db.Column(db.Float, default=0.0)

    def subtotal_after_discount(self):
        subtotal = self.subtotal()
        return subtotal * (1 - (self.discount_percent / 100))

    def subtotal(self):
        return self.quantity * self.unit_price

class ProformaItem(db.Model):
    """Lignes d'un proforma"""
    __tablename__ = 'proforma_item'
    
    id = db.Column(db.Integer, primary_key=True)
    proforma_id = db.Column(db.Integer, db.ForeignKey('proforma.id'))
    description = db.Column(db.String(200))
    quantity = db.Column(db.Float, default=1)
    unit_price = db.Column(db.Float, nullable=False)
    tax_rate = db.Column(db.Float)  # Taux spécifique pour cette ligne
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    discount_percent = db.Column(db.Float, default=0.0)

    def subtotal_after_discount(self):
        subtotal = self.subtotal()
        return subtotal * (1 - (self.discount_percent / 100))

    def subtotal(self):
        return self.quantity * self.unit_price



class Product(db.Model):
    """Modèle pour les produits en stock"""
    __tablename__ = 'product'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    description = db.Column(db.Text)
    quantity = db.Column(db.Float, default=0)
    alert_quantity = db.Column(db.Float, default=5)  # Niveau d'alerte pour réapprovisionnement
    unit_price = db.Column(db.Float, nullable=False)
    supplier = db.Column(db.String(120))
    image_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relation avec les lignes de facture/proforma
    invoice_items = db.relationship('InvoiceItem', backref='product', lazy=True)
    proforma_items = db.relationship('ProformaItem', backref='product', lazy=True)

    def __repr__(self):
        return f"<Product {self.name}>"
    

class Approvisionnement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    montant = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    site = db.Column(db.String(50))  


class Installation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prenom = db.Column(db.String(100))
    nom = db.Column(db.String(100))
    telephone = db.Column(db.String(50))
    montant_total = db.Column(db.Float, nullable=False)
    montant_avance = db.Column(db.Float, default=0)
    montant_restant = db.Column(db.Float, default=0)
    date_installation = db.Column(db.Date)
    methode_paiement = db.Column(db.String(30))
    date_echeance = db.Column(db.Date)
    contrat_path = db.Column(db.String(255))
    statut = db.Column(db.String(30), default='en_attente')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CalendarEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    start = db.Column(db.String(50), nullable=False)
    allDay = db.Column(db.Boolean, default=False) 
    notified = db.Column(db.Boolean, default=False)  # Pour éviter les doublons de notification
    commercial_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Commercial associé
    commercial = db.relationship('User', foreign_keys=[commercial_id])   

class ClientImportHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255))
    imported_at = db.Column(db.DateTime, default=datetime.utcnow)
    imported_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    imported_by = db.relationship('User')
    clients = db.relationship('Client', backref='import_history', lazy=True)