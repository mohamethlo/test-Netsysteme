// Maps module for location visualization

class MapManager {
    constructor() {
        this.map = null;
        this.userMarker = null;
        this.workLocationMarkers = [];
        this.workLocationCircles = [];
        this.isInitialized = false;
    }
    
    initializeAttendanceMap() {
        const mapElement = document.getElementById('map');
        if (!mapElement) return;
        
        // Default center (France)
        const defaultCenter = [46.603354, 1.888334];
        
        // Initialize map
        this.map = L.map('map').setView(defaultCenter, 6);
        
        // Add tile layer
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(this.map);
        
        this.isInitialized = true;
        
        // Add work locations if available
        if (typeof workLocations !== 'undefined' && workLocations.length > 0) {
            this.addWorkLocations(workLocations);
        }
        
        // Center on work locations or default
        this.centerMapOnWorkLocations();
    }
    
    addWorkLocations(locations) {
        if (!this.isInitialized) return;
        
        // Clear existing markers and circles
        this.clearWorkLocations();
        
        locations.forEach(location => {
            // Add marker for work location
            const marker = L.marker([location.latitude, location.longitude])
                .addTo(this.map)
                .bindPopup(`
                    <div>
                        <strong>${location.name}</strong><br>
                        ${location.address || 'Adresse non renseignée'}<br>
                        <small>Zone de ${location.radius}m</small>
                    </div>
                `);
            
            this.workLocationMarkers.push(marker);
            
            // Add radius circle
            const circle = L.circle([location.latitude, location.longitude], {
                color: '#007bff',
                fillColor: '#007bff',
                fillOpacity: 0.1,
                radius: location.radius
            }).addTo(this.map);
            
            this.workLocationCircles.push(circle);
        });
    }
    
    clearWorkLocations() {
        // Remove markers
        this.workLocationMarkers.forEach(marker => {
            this.map.removeLayer(marker);
        });
        this.workLocationMarkers = [];
        
        // Remove circles
        this.workLocationCircles.forEach(circle => {
            this.map.removeLayer(circle);
        });
        this.workLocationCircles = [];
    }
    
    updateUserLocation(location) {
        if (!this.isInitialized || !location) return;
        
        const { latitude, longitude, accuracy } = location;
        
        // Remove existing user marker
        if (this.userMarker) {
            this.map.removeLayer(this.userMarker);
        }
        
        // Add new user marker
        this.userMarker = L.marker([latitude, longitude], {
            icon: this.createUserIcon()
        }).addTo(this.map)
        .bindPopup(`
            <div>
                <strong>Votre position</strong><br>
                Précision: ±${Math.round(accuracy)}m<br>
                <small>${new Date().toLocaleTimeString('fr-FR')}</small>
            </div>
        `);
        
        // Add accuracy circle
        if (accuracy < 100) { // Only show if accuracy is reasonable
            L.circle([latitude, longitude], {
                color: '#28a745',
                fillColor: '#28a745',
                fillOpacity: 0.1,
                radius: accuracy
            }).addTo(this.map);
        }
        
        // Center map on user location
        this.map.setView([latitude, longitude], 16);
    }
    
    createUserIcon() {
        return L.divIcon({
            className: 'user-location-marker',
            html: '<div style="background: #28a745; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 5px rgba(0,0,0,0.3);"></div>',
            iconSize: [20, 20],
            iconAnchor: [10, 10]
        });
    }
    
    centerMapOnWorkLocations() {
        if (!this.isInitialized) return;
        
        if (this.workLocationMarkers.length === 0) {
            return;
        }
        
        if (this.workLocationMarkers.length === 1) {
            const marker = this.workLocationMarkers[0];
            this.map.setView(marker.getLatLng(), 15);
        } else {
            // Create bounds that include all work locations
            const group = new L.featureGroup(this.workLocationMarkers);
            this.map.fitBounds(group.getBounds().pad(0.1));
        }
    }
    
    showRoute(start, end) {
        if (!this.isInitialized) return;
        
        // Simple line between points (for more advanced routing, use a routing service)
        const routeLine = L.polyline([start, end], {
            color: '#007bff',
            weight: 3,
            opacity: 0.7
        }).addTo(this.map);
        
        // Fit bounds to show the route
        this.map.fitBounds(routeLine.getBounds().pad(0.1));
        
        return routeLine;
    }
    
    calculateDistanceOnMap(lat1, lon1, lat2, lon2) {
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
    
    addCustomMarker(lat, lng, options = {}) {
        if (!this.isInitialized) return null;
        
        const defaultOptions = {
            title: 'Marqueur personnalisé',
            popup: null,
            icon: null
        };
        
        const markerOptions = { ...defaultOptions, ...options };
        
        const marker = L.marker([lat, lng], {
            title: markerOptions.title,
            icon: markerOptions.icon
        }).addTo(this.map);
        
        if (markerOptions.popup) {
            marker.bindPopup(markerOptions.popup);
        }
        
        return marker;
    }
    
    removeMarker(marker) {
        if (marker && this.isInitialized) {
            this.map.removeLayer(marker);
        }
    }
    
    setMapView(lat, lng, zoom = 15) {
        if (this.isInitialized) {
            this.map.setView([lat, lng], zoom);
        }
    }
    
    getMapBounds() {
        if (this.isInitialized) {
            return this.map.getBounds();
        }
        return null;
    }
    
    onMapClick(callback) {
        if (this.isInitialized) {
            this.map.on('click', callback);
        }
    }
    
    offMapClick(callback) {
        if (this.isInitialized) {
            this.map.off('click', callback);
        }
    }
    
    destroy() {
        if (this.isInitialized && this.map) {
            this.map.remove();
            this.map = null;
            this.isInitialized = false;
        }
    }
}

// Initialize map manager
let mapManager;

// Global functions for attendance integration
function initializeAttendanceMap() {
    mapManager = new MapManager();
    mapManager.initializeAttendanceMap();
}

function updateAttendanceMap(userLocation) {
    if (mapManager && userLocation) {
        mapManager.updateUserLocation(userLocation);
    }
}

// Export for global use
window.mapManager = mapManager;
window.initializeAttendanceMap = initializeAttendanceMap;
window.updateAttendanceMap = updateAttendanceMap;

// Auto-initialize if map element exists
document.addEventListener('DOMContentLoaded', function() {
    const mapElement = document.getElementById('map');
    if (mapElement) {
        initializeAttendanceMap();
    }
});
