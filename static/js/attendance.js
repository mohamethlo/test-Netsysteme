class AttendanceManager {
    constructor() {
        this.userLocation = null;
        this.workLocations = [];
        this.watchId = null;
        this.isTracking = false;
        this.zoneNamePrompted = false;

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.startLocationTracking();
    }

    setupEventListeners() {
        const checkInBtn = document.getElementById('checkInBtn');
        const checkOutBtn = document.getElementById('checkOutBtn');

        if (checkInBtn) {
            checkInBtn.addEventListener('click', () => this.checkIn());
        }

        if (checkOutBtn) {
            checkOutBtn.addEventListener('click', () => this.checkOut());
        }
    }

    startLocationTracking() {
        if (!navigator.geolocation) {
            this.showLocationError('La géolocalisation n\'est pas supportée par ce navigateur.');
            return;
        }

        this.isTracking = true;

        navigator.geolocation.getCurrentPosition(
            (position) => this.onLocationSuccess(position),
            (error) => this.onLocationError(error),
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 300000
            }
        );

        this.watchId = navigator.geolocation.watchPosition(
            (position) => this.onLocationSuccess(position),
            (error) => this.onLocationError(error),
            {
                enableHighAccuracy: true,
                timeout: 30000,
                maximumAge: 60000
            }
        );
    }

    stopLocationTracking() {
        if (this.watchId) {
            navigator.geolocation.clearWatch(this.watchId);
            this.watchId = null;
        }
        this.isTracking = false;
    }

    onLocationSuccess(position) {
        this.userLocation = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
            timestamp: new Date()
        };

        // Récupérer les deux boutons
        const checkInBtn = document.getElementById('checkInBtn');
        const checkOutBtn = document.getElementById('checkOutBtn');

        if (this.userLocation.accuracy > 1000) {
            Utils.showToast('La précision GPS est faible. Veuillez patienter ou activer le GPS.', 'warning');

            // Désactiver les deux boutons si la précision est faible
            if (checkInBtn) checkInBtn.setAttribute('disabled', 'disabled');
            if (checkOutBtn) checkOutBtn.setAttribute('disabled', 'disabled');
        } else {
            // Réactiver les deux boutons si la précision est bonne
            if (checkInBtn) checkInBtn.removeAttribute('disabled');
            if (checkOutBtn) checkOutBtn.removeAttribute('disabled');
        }

        this.updateLocationStatus();
        this.updateMap();
    }

    onLocationError(error) {
        let message = 'Erreur de géolocalisation: ';
        switch (error.code) {
            case error.PERMISSION_DENIED:
                message += 'Permission refusée par l\'utilisateur.';
                break;
            case error.POSITION_UNAVAILABLE:
                message += 'Position indisponible.';
                break;
            case error.TIMEOUT:
                message += 'Délai d\'attente dépassé.';
                break;
            default:
                message += 'Erreur inconnue.';
                break;
        }
        this.showLocationError(message);
    }
    /*  updateLocationStatus() {
         const statusElement = document.getElementById(`locationStatus${this.type.charAt(0).toUpperCase() + this.type.slice(1)}`);
         if (!statusElement || !this.userLocation) return;
 
         const { nearest, minDistance } = this.getNearestWorkLocationWithDistance();
         const accuracy = this.userLocation.accuracy;
         const lat = this.userLocation.latitude.toFixed(6);
         const lon = this.userLocation.longitude.toFixed(6);
         const precision = Math.round(accuracy);
         let statusHtml = '';
 
         if (accuracy > 100) {
             statusHtml = `
             <div class="alert alert-warning">
                 <i data-feather="alert-triangle"></i>
                 La précision GPS est faible (±${precision} m).
                 <br>Veuillez patienter ou améliorer votre position GPS.
             </div>
         `;
         } else if (nearest) {
             if (minDistance <= nearest.radius) {
                 statusHtml = `
                 <div class="alert alert-success">
                     <i data-feather="map-pin"></i>
                     ✅ Vous êtes dans la zone ${this.type} : <strong>${nearest.name}</strong>
                     <br><small>Distance : ${Math.round(minDistance)} m</small>
                 </div>
             `;
             } else if (minDistance > 1000) {
                 statusHtml = `
                 <div class="alert alert-info">
                     <i data-feather="info"></i>
                     📍 Position actuelle : ${lat}, ${lon}
                     <br><small>Précision : ±${precision} m</small>
                     <br><small>Zone la plus proche : ${nearest.name} à ${Math.round(minDistance)} m</small>
                 </div>
             `;
             } else {
                 statusHtml = `
                 <div class="alert alert-warning">
                     <i data-feather="alert-triangle"></i>
                     ❌ Trop éloigné de la zone ${this.type} la plus proche : <strong>${nearest.name}</strong>
                     <br><small>Distance : ${Math.round(minDistance)} m (max autorisé : ${nearest.radius} m)</small>
                 </div>
             `;
             }
         } else {
             statusHtml = `
             <div class="alert alert-info">
                 <i data-feather="info"></i>
                 📍 Position actuelle : ${lat}, ${lon}
                 <br><small>Précision : ±${precision} m</small>
                 <br><small>Aucune zone de travail connue dans cette zone.</small>
             </div>
         `;
         }
 
         statusElement.innerHTML = statusHtml;
         feather.replace();
     } */


    updateLocationStatus() {
        const statusElement = document.getElementById('locationStatus');
        if (!statusElement || !this.userLocation) return;

        const { nearest, minDistance } = this.getNearestWorkLocationWithDistance();
        let statusHtml = '';

        if (nearest) {
            if (minDistance <= nearest.radius) {
                statusHtml = `
                    <div class="alert alert-success">
                        <i data-feather="map-pin"></i>
                        Vous êtes dans la zone de travail: <strong>${nearest.name}</strong>
                        <br><small>Distance: ${Math.round(minDistance)}m</small>
                    </div>
                `;
            } else {
                statusHtml = `
                    <div class="alert alert-warning">
                        <i data-feather="alert-triangle"></i>
                        Vous êtes trop loin de la zone la plus proche : <strong>${nearest.name}</strong>
                        <br><small>Distance: ${Math.round(minDistance)}m (max: ${nearest.radius}m)</small>
                    </div>
                `;
            }
        } else {
            statusHtml = `
                <div class="alert alert-info">
                    <i data-feather="info"></i>
                    Position actuelle: ${this.userLocation.latitude.toFixed(6)}, ${this.userLocation.longitude.toFixed(6)}
                    <br><small>Précision: ±${Math.round(this.userLocation.accuracy)}m</small>
                </div>
            `;
        }

        statusElement.innerHTML = statusHtml;
        feather.replace();
    }

    getNearestWorkLocationWithDistance() {
        if (!this.userLocation || !this.workLocations.length) {
            return { nearest: null, minDistance: Infinity };
        }

        let nearest = null;
        let minDistance = Infinity;

        for (const location of this.workLocations) {
            const distance = this.calculateDistance(
                this.userLocation.latitude,
                this.userLocation.longitude,
                location.latitude,
                location.longitude
            );
            if (distance < minDistance) {
                minDistance = distance;
                nearest = location;
            }
        }
        return { nearest, minDistance };
    }

    calculateDistance(lat1, lon1, lat2, lon2) {
        const R = 6371000; // Earth's radius in meters
        const dLat = this.toRadians(lat2 - lat1);
        const dLon = this.toRadians(lon2 - lon1);

        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(this.toRadians(lat1)) * Math.cos(this.toRadians(lat2)) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2);

        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

        return R * c;
    }

    toRadians(degrees) {
        return degrees * (Math.PI / 180);
    }

    async checkIn(zoneName = null) {
        if (!this.userLocation) {
            Utils.showToast('Position non disponible. Veuillez activer la géolocalisation.', 'warning');
            return;
        }

        // Recherche la zone la plus proche
        const { nearest, minDistance } = this.getNearestWorkLocationWithDistance();

        // Rayon dynamique selon la zone la plus proche
        let location_name = null;
        if (nearest && minDistance <= nearest.radius) {
            location_name = nearest.name;
        } else if (zoneName) {
            location_name = zoneName;
        }

        try {
            const response = await fetch('/check_in', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    latitude: this.userLocation.latitude,
                    longitude: this.userLocation.longitude,
                    location_name: location_name
                })
            });

            const data = await response.json();

            if (data.need_zone_name) {
                this.promptZoneName();
                Utils.showToast(data.message, 'info');
            } else if (data.success) {
                Utils.showToast(data.message, 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                Utils.showToast(data.message, 'danger');
            }
        } catch (error) {
            console.error('Check-in error:', error);
            Utils.showToast('Erreur lors du pointage d\'entrée.', 'danger');
        }
    }

    promptZoneName() {
        if (this.zoneNamePrompted) return;
        this.zoneNamePrompted = true;

        const formDiv = document.getElementById('pointage_form');
        if (!formDiv) return;

        formDiv.innerHTML = `
            <div class="mb-3">
                <label>Nom du lieu</label>
                <input type="text" id="zone_name_input" class="form-control" required>
            </div>
            <button class="btn btn-primary" id="confirmZoneBtn">Créer et pointer</button>
        `;

        document.getElementById('confirmZoneBtn').addEventListener('click', (e) => {
            e.preventDefault();
            const zoneName = document.getElementById('zone_name_input').value;
            if (!zoneName || !zoneName.trim()) {
                Utils.showToast('Veuillez saisir un nom pour ce lieu.', 'warning');
                return;
            }
            this.checkIn(zoneName.trim());
        });
    }

    async checkOut() {
        if (!this.userLocation) {
            Utils.showToast('Position non disponible. Veuillez activer la géolocalisation.', 'warning');
            return;
        }
        // Recherche la zone la plus proche
        const { nearest, minDistance } = this.getNearestWorkLocationWithDistance();
        let location_name = null;

        if (nearest && minDistance <= nearest.radius) {
            location_name = nearest.name;
        } else {
            Utils.showToast('Vous devez être dans la même zone que votre pointage d\'entrée pour pointer la sortie.', 'danger');
            return;
        }

        try {
            const response = await fetch('/check_out', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    latitude: this.userLocation.latitude,
                    longitude: this.userLocation.longitude,
                    location: location_name
                })
            });

            const data = await response.json();

            if (data.success) {
                Utils.showToast(data.message, 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                Utils.showToast(data.message, 'danger');
            }
        } catch (error) {
            console.error('Check-out error:', error);
            Utils.showToast('Erreur lors du pointage de sortie.', 'danger');
        }
    }

    updateMap() {
        if (typeof updateAttendanceMap === 'function') {
            updateAttendanceMap(this.userLocation);
        }
    }

    showLocationError(message) {
        const statusElement = document.getElementById('locationStatus');
        if (statusElement) {
            statusElement.innerHTML = `
                <div class="alert alert-danger">
                    <i data-feather="alert-circle"></i>
                    ${message}
                    <br><button class="btn btn-sm btn-outline-danger mt-2" onclick="attendanceManager.requestLocationPermission()">
                        Réessayer
                    </button>
                </div>
            `;
            feather.replace();
        }
    }

    requestLocationPermission() {
        if (navigator.permissions) {
            navigator.permissions.query({ name: 'geolocation' }).then((result) => {
                if (result.state === 'granted') {
                    this.startLocationTracking();
                } else if (result.state === 'prompt') {
                    this.startLocationTracking();
                } else {
                    Utils.showToast('Veuillez autoriser l\'accès à votre position dans les paramètres du navigateur.', 'warning');
                }
            });
        } else {
            this.startLocationTracking();
        }
    }

    setWorkLocations(locations) {
        this.workLocations = locations;
        this.updateLocationStatus();
    }

    getCurrentLocation() {
        return this.userLocation;
    }

    getWorkLocations() {
        return this.workLocations;
    }

    isInWorkZone() {
        if (!this.userLocation || !this.workLocations.length) {
            return false;
        }
        const { nearest, minDistance } = this.getNearestWorkLocationWithDistance();
        return nearest && minDistance <= nearest.radius;
    }
}

// Initialize attendance manager when DOM is loaded
let attendanceManager;

document.addEventListener('DOMContentLoaded', function () {
    attendanceManager = new AttendanceManager();

    // Set work locations if available
    if (typeof workLocations !== 'undefined') {
        attendanceManager.setWorkLocations(workLocations);
    }
});

// Export for global use
window.attendanceManager = attendanceManager;


/* 
class AttendanceManager {
    constructor() {
        this.userLocation = null;
        this.workLocations = [];
        this.watchId = null;
        this.isTracking = false;
        this.zoneNamePrompted = false;
        this.type = 'bureau'; // Par défaut

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.startLocationTracking();
    }

    setupEventListeners() {
        // Pointage Bureau
        const checkInBtnBureau = document.getElementById('checkInBtnBureau');
        const checkOutBtnBureau = document.getElementById('checkOutBtnBureau');
        
        // Pointage Terrain
        const checkInBtnTerrain = document.getElementById('checkInBtnTerrain');
        const checkOutBtnTerrain = document.getElementById('checkOutBtnTerrain');

        if (checkInBtnBureau) {
            checkInBtnBureau.addEventListener('click', () => {
                this.type = 'bureau';
                this.checkIn();
            });
        }

        if (checkOutBtnBureau) {
            checkOutBtnBureau.addEventListener('click', () => {
                this.type = 'bureau';
                this.checkOut();
            });
        }

        if (checkInBtnTerrain) {
            checkInBtnTerrain.addEventListener('click', () => {
                this.type = 'terrain';
                this.checkIn();
            });
        }

        if (checkOutBtnTerrain) {
            checkOutBtnTerrain.addEventListener('click', () => {
                this.type = 'terrain';
                this.checkOut();
            });
        }
    }

    startLocationTracking() {
        if (!navigator.geolocation) {
            this.showLocationError('La géolocalisation n\'est pas supportée par ce navigateur.');
            return;
        }

        this.isTracking = true;

        navigator.geolocation.getCurrentPosition(
            (position) => this.onLocationSuccess(position),
            (error) => this.onLocationError(error),
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 300000
            }
        );

        this.watchId = navigator.geolocation.watchPosition(
            (position) => this.onLocationSuccess(position),
            (error) => this.onLocationError(error),
            {
                enableHighAccuracy: true,
                timeout: 30000,
                maximumAge: 60000
            }
        );
    }

    stopLocationTracking() {
        if (this.watchId) {
            navigator.geolocation.clearWatch(this.watchId);
            this.watchId = null;
        }
        this.isTracking = false;
    }

    onLocationSuccess(position) {
        this.userLocation = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
            timestamp: new Date()
        };

        const checkInBtnBureau = document.getElementById('checkInBtnBureau');
        const checkInBtnTerrain = document.getElementById('checkInBtnTerrain');

        if (this.userLocation.accuracy > 100) {
            Utils.showToast('La précision GPS est faible. Veuillez patienter.', 'warning');
            if (checkInBtnBureau) checkInBtnBureau.setAttribute('disabled', 'disabled');
            if (checkInBtnTerrain) checkInBtnTerrain.setAttribute('disabled', 'disabled');
        } else {
            if (checkInBtnBureau) checkInBtnBureau.removeAttribute('disabled');
            if (checkInBtnTerrain) checkInBtnTerrain.removeAttribute('disabled');
        }

        this.updateLocationStatus();
        this.updateMap();
    }

    onLocationError(error) {
        let message = 'Erreur de géolocalisation: ';
        switch (error.code) {
            case error.PERMISSION_DENIED:
                message += 'Permission refusée par l\'utilisateur.';
                break;
            case error.POSITION_UNAVAILABLE:
                message += 'Position indisponible.';
                break;
            case error.TIMEOUT:
                message += 'Délai d\'attente dépassé.';
                break;
            default:
                message += 'Erreur inconnue.';
                break;
        }
        this.showLocationError(message);
    }

    updateLocationStatus() {
        const statusElement = document.getElementById(`locationStatus${this.type.charAt(0).toUpperCase() + this.type.slice(1)}`);
        if (!statusElement || !this.userLocation) return;

        const { nearest, minDistance } = this.getNearestWorkLocationWithDistance();
        let statusHtml = '';

        if (nearest) {
            if (minDistance <= nearest.radius) {
                statusHtml = `
                    <div class="alert alert-success">
                        <i data-feather="map-pin"></i>
                        Vous êtes dans la zone ${this.type}: <strong>${nearest.name}</strong>
                        <br><small>Distance: ${Math.round(minDistance)}m</small>
                    </div>
                `;
            } else {
                statusHtml = `
                    <div class="alert alert-warning">
                        <i data-feather="alert-triangle"></i>
                        Vous êtes trop loin de la zone ${this.type} la plus proche: <strong>${nearest.name}</strong>
                        <br><small>Distance: ${Math.round(minDistance)}m (max: ${nearest.radius}m)</small>
                    </div>
                `;
            }
        } else {
            statusHtml = `
                <div class="alert alert-info">
                    <i data-feather="info"></i>
                    Position actuelle: ${this.userLocation.latitude.toFixed(6)}, ${this.userLocation.longitude.toFixed(6)}
                    <br><small>Précision: ±${Math.round(this.userLocation.accuracy)}m</small>
                </div>
            `;
        }

        statusElement.innerHTML = statusHtml;
        feather.replace();
    }

    getNearestWorkLocationWithDistance() {
        if (!this.userLocation || !this.workLocations.length) {
            return { nearest: null, minDistance: Infinity };
        }

        let nearest = null;
        let minDistance = Infinity;

        for (const location of this.workLocations) {
            if (this.type === 'bureau' && location.type !== 'bureau') continue;
            
            const distance = this.calculateDistance(
                this.userLocation.latitude,
                this.userLocation.longitude,
                location.latitude,
                location.longitude
            );
            if (distance < minDistance) {
                minDistance = distance;
                nearest = location;
            }
        }
        return { nearest, minDistance };
    }

    calculateDistance(lat1, lon1, lat2, lon2) {
        const R = 6371000; // Earth's radius in meters
        const dLat = this.toRadians(lat2 - lat1);
        const dLon = this.toRadians(lon2 - lon1);

        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(this.toRadians(lat1)) * Math.cos(this.toRadians(lat2)) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2);

        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

        return R * c;
    }

    toRadians(degrees) {
        return degrees * (Math.PI / 180);
    }

    async checkIn(zoneName = null) {
        if (!this.userLocation) {
            Utils.showToast('Position non disponible. Veuillez activer la géolocalisation.', 'warning');
            return;
        }

        const { nearest, minDistance } = this.getNearestWorkLocationWithDistance();
        let location_name = null;

        if (this.type === 'bureau') {
            if (!nearest || nearest.type !== 'bureau') {
                Utils.showToast('Vous devez être au bureau pour pointer.', 'warning');
                return;
            }
            location_name = nearest.name;
        } else {
            location_name = nearest && minDistance <= nearest.radius ? nearest.name : zoneName;
        }

        try {
            const response = await fetch('/check_in', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    type_pointage: this.type,
                    latitude: this.userLocation.latitude,
                    longitude: this.userLocation.longitude,
                    location_name: location_name
                })
            });

            const data = await response.json();

            if (data.need_zone_name && this.type === 'terrain') {
                this.promptZoneName();
                Utils.showToast(data.message, 'info');
            } else if (data.success) {
                Utils.showToast(data.message, 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                Utils.showToast(data.message, 'danger');
            }
        } catch (error) {
            console.error('Check-in error:', error);
            Utils.showToast('Erreur lors du pointage.', 'danger');
        }
    }

    promptZoneName() {
        if (this.zoneNamePrompted) return;
        this.zoneNamePrompted = true;

        const formDiv = document.getElementById('pointage_form_terrain');
        if (!formDiv) return;

        formDiv.innerHTML = `
            <div class="mb-3">
                <label>Nom du lieu</label>
                <input type="text" id="zone_name_input" class="form-control" required>
            </div>
            <button class="btn btn-primary" id="confirmZoneBtn">Créer et pointer</button>
        `;

        document.getElementById('confirmZoneBtn').addEventListener('click', (e) => {
            e.preventDefault();
            const zoneName = document.getElementById('zone_name_input').value;
            if (!zoneName || !zoneName.trim()) {
                Utils.showToast('Veuillez saisir un nom pour ce lieu.', 'warning');
                return;
            }
            this.checkIn(zoneName.trim());
        });
    }

    async checkOut() {
        if (!this.userLocation) {
            Utils.showToast('Position non disponible.', 'warning');
            return;
        }

        try {
            const response = await fetch('/check_out', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    type_pointage: this.type,
                    latitude: this.userLocation.latitude,
                    longitude: this.userLocation.longitude,
                    location: `Position de sortie ${this.type}`
                })
            });

            const data = await response.json();
            if (data.success) {
                Utils.showToast(data.message, 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                Utils.showToast(data.message, 'danger');
            }
        } catch (error) {
            console.error('Check-out error:', error);
            Utils.showToast('Erreur lors du pointage de sortie.', 'danger');
        }
    }

    updateMap() {
        if (typeof updateAttendanceMap === 'function') {
            updateAttendanceMap(this.userLocation);
        }
    }

    showLocationError(message) {
        const statusElement = document.getElementById(`locationStatus${this.type.charAt(0).toUpperCase() + this.type.slice(1)}`);
        if (statusElement) {
            statusElement.innerHTML = `
                <div class="alert alert-danger">
                    <i data-feather="alert-circle"></i>
                    ${message}
                    <br><button class="btn btn-sm btn-outline-danger mt-2" onclick="attendanceManager.requestLocationPermission()">
                        Réessayer
                    </button>
                </div>
            `;
            feather.replace();
        }
    }

    requestLocationPermission() {
        if (navigator.permissions) {
            navigator.permissions.query({ name: 'geolocation' }).then((result) => {
                if (result.state === 'granted' || result.state === 'prompt') {
                    this.startLocationTracking();
                } else {
                    Utils.showToast('Veuillez autoriser l\'accès à votre position.', 'warning');
                }
            });
        } else {
            this.startLocationTracking();
        }
    }

    setWorkLocations(locations) {
        this.workLocations = locations;
        this.updateLocationStatus();
    }
}

// Initialize attendance manager when DOM is loaded
let attendanceManager;

document.addEventListener('DOMContentLoaded', function() {
    attendanceManager = new AttendanceManager();
    
    if (typeof workLocations !== 'undefined') {
        attendanceManager.setWorkLocations(workLocations);
    }

    // Handle late justification form if needed
    if (typeof isLate !== 'undefined' && isLate && needJustification) {
        const modal = new bootstrap.Modal(document.getElementById('lateJustifyModal'));
        modal.show();
    }
});

// Export for global use
window.attendanceManager = attendanceManager; */