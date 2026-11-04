import re

code = '''
    let isLeafletMode = false;
    let leafletMap = null;
    let leafletFullPolyline = null;
    let leafletTraveledPolyline = null;
    let leafletVehicleMarker = null;
    let leafletPoiMarkers = [];
    let leafletTileLayer = null;

    function checkWebGLSupport() {
      try {
        if (!window.maplibregl || !maplibregl.supported()) return false;
        const canvas = document.createElement('canvas');
        const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
        return !!gl;
      } catch (e) {
        return false;
      }
    }

    function initMap() {
      if (!checkWebGLSupport()) {
        console.warn("WebGL not available or disabled in current environment, falling back to 2D/2.5D Leaflet map mode.");
        isLeafletMode = true;
        initLeafletMap();
        return;
      }

      try {
        initMapLibre3D();
      } catch (e) {
        console.warn("MapLibre 3D initialization failed, falling back to Leaflet:", e);
        isLeafletMode = true;
        initLeafletMap();
      }
    }

    function initLeafletMap() {
      const startPt = points[0];
      leafletMap = L.map('map', {
        center: [startPt[1], startPt[0]],
        zoom: 7,
        zoomControl: false
      });

      L.control.zoom({ position: 'top-right' }).addTo(leafletMap);

      leafletTileLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 18,
        attribution: 'Esri Satellite'
      }).addTo(leafletMap);

      const latLngs = points.map(p => [p[1], p[0]]);
      leafletFullPolyline = L.polyline(latLngs, {
        color: '#06b6d4',
        weight: 3.5,
        opacity: 0.75,
        lineJoin: 'round'
      }).addTo(leafletMap);

      leafletTraveledPolyline = L.polyline([[startPt[1], startPt[0]]], {
        color: '#f59e0b',
        weight: 5,
        opacity: 0.95,
        lineJoin: 'round'
      }).addTo(leafletMap);

      // Vehicle marker
      const carIcon = L.divIcon({
        className: 'leaflet-vehicle-wrap',
        html: `
          <div class="vehicle-marker" style="transform: translate(-50%, -50%);">
            <div class="vehicle-ripple"></div>
            <div class="vehicle-beam" id="vehicleBeam"></div>
            <div class="vehicle-body" id="vehicleBody">
              <div class="vehicle-arrow"></div>
            </div>
          </div>
        `,
        iconSize: [44, 44],
        iconAnchor: [22, 22]
      });

      leafletVehicleMarker = L.marker([startPt[1], startPt[0]], { icon: carIcon }).addTo(leafletMap);

      // POI Markers
      pois.forEach(poi => {
        const poiIcon = L.divIcon({
          className: 'leaflet-poi-wrap',
          html: `
            <div class="poi-marker" style="transform: translate(-50%, -100%);">
              <div class="poi-bubble">
                <span>🚩</span>
                <span>${poi.name}</span>
                <span style="color: var(--accent-gold); font-family: 'JetBrains Mono'; font-size: 10px;">${poi.ele}m</span>
              </div>
              <div class="poi-pin-dot"></div>
            </div>
          `,
          iconSize: [120, 36],
          iconAnchor: [60, 36]
        });

        const m = L.marker([poi.lat, poi.lon], { icon: poiIcon }).addTo(leafletMap);
        m.on('click', () => {
          leafletMap.flyTo([poi.lat, poi.lon], 11, { duration: 1.5 });
          showToast(`🚩 ${poi.name}: ${poi.desc}`);
        });
        leafletPoiMarkers.push(m);
      });

      renderElevationProfile();
      initUI();
      fitMasterRoute();
      showToast("💡 当前环境已启用高清卫星遥感巡航引擎");
    }

    function initMapLibre3D() {
'''

with open('/home/gcpvm/3DTracker/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace starting from `function initMap() {` to `const styleConfig = {`
target = 'function initMap() {\n      // Style definition with ESRI Satellite & AWS Terrarium 3D Terrain\n      const styleConfig = {'
replacement = code + '\n      const styleConfig = {'

if target in content:
    content = content.replace(target, replacement)
    print("Replaced initMap header successfully")
else:
    print("Could not find exact target for initMap header")

with open('/home/gcpvm/3DTracker/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

