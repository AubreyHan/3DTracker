with open('/home/gcpvm/3DTracker/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

target_update = '''    function updatePosition(idx) {
      if (!map || idx < 0 || idx >= totalPoints) return;'''

repl_update = '''    function updatePosition(idx) {
      if (idx < 0 || idx >= totalPoints) return;

      const pt = points[idx];
      const [lon, lat, ele, timeSec, cumKm, speed, legIdx] = pt;

      // Calculate heading
      const nextPt = points[Math.min(idx + 1, totalPoints - 1)];
      let heading = 0;
      if (nextPt) {
        const dLon = (nextPt[0] - lon) * Math.PI / 180;
        const lat1 = lat * Math.PI / 180;
        const lat2 = nextPt[1] * Math.PI / 180;
        const y = Math.sin(dLon) * Math.cos(lat2);
        const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);
        heading = (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
      }

      if (isLeafletMode) {
        if (leafletVehicleMarker) {
          leafletVehicleMarker.setLatLng([lat, lon]);
          const bodyEl = document.getElementById('vehicleBody');
          if (bodyEl) bodyEl.style.transform = `rotate(${heading}deg)`;
          const beamEl = document.getElementById('vehicleBeam');
          if (beamEl) beamEl.style.transform = `rotate(${heading}deg)`;
        }
        if (leafletTraveledPolyline) {
          const traveledLatLngs = points.slice(0, idx + 1).map(p => [p[1], p[0]]);
          leafletTraveledPolyline.setLatLngs(traveledLatLngs);
        }
        if (cameraMode === 'chase' || cameraMode === 'drone') {
          leafletMap.panTo([lat, lon], { animate: false });
        }
      } else if (map) {
        if (vehicleMarker) {
          vehicleMarker.setLngLat([lon, lat]);
          const bodyEl = document.getElementById('vehicleBody');
          if (bodyEl) bodyEl.style.transform = `rotate(${heading}deg)`;
          const beamEl = document.getElementById('vehicleBeam');
          if (beamEl) beamEl.style.transform = `rotate(${heading}deg)`;
        }
        const traveledCoords = points.slice(0, idx + 1).map(p => [p[0], p[1], p[2]]);
        if (map.getSource('traveled-source')) {
          map.getSource('traveled-source').setData({
            type: 'Feature',
            geometry: {
              type: 'LineString',
              coordinates: traveledCoords.length > 1 ? traveledCoords : [[lon, lat], [lon, lat]]
            }
          });
        }
        updateCamera(lon, lat, ele, heading);
      }

      updateHUD();
      updateScrubber(idx);
      return;
    }

    function _disabled_old_updatePosition(idx) {'''

content = content.replace(target_update, repl_update)

# Also update fitMasterRoute
target_fit = '''    function fitMasterRoute() {
      if (!map) return;'''

repl_fit = '''    function fitMasterRoute() {
      if (isLeafletMode && leafletMap) {
        leafletMap.fitBounds([[36.0, 87.0], [44.5, 117.5]], { padding: [60, 60] });
        showToast("🗺️ 展开8,015公里西北大环线全景视图");
        return;
      }
      if (!map) return;'''

content = content.replace(target_fit, repl_fit)

# Also update selectLeg
target_select = '''    function selectLeg(legIdx) {
      const leg = legs[legIdx];
      currentIndex = leg.start_idx;
      updatePosition(currentIndex);

      // Fly camera to day start with smooth transition
      map.flyTo({'''

repl_select = '''    function selectLeg(legIdx) {
      const leg = legs[legIdx];
      currentIndex = leg.start_idx;
      updatePosition(currentIndex);

      if (isLeafletMode && leafletMap) {
        leafletMap.flyTo([leg.start_coord[1], leg.start_coord[0]], 9, { duration: 1.5 });
        showToast(`🚗 切换至 Day ${leg.day}: ${leg.title}`);
        return;
      }

      // Fly camera to day start with smooth transition
      if (map) map.flyTo({'''

content = content.replace(target_select, repl_select)

# Also update switchMapStyle for Leaflet
target_style = '''    function switchMapStyle(styleType) {
      currentMapStyle = styleType;
      document.getElementById('btn-style-sat').classList.toggle('active', styleType === 'satellite');
      document.getElementById('btn-style-topo').classList.toggle('active', styleType === 'topo');
      document.getElementById('btn-style-dark').classList.toggle('active', styleType === 'dark');

      if (!map) return;'''

repl_style = '''    function switchMapStyle(styleType) {
      currentMapStyle = styleType;
      document.getElementById('btn-style-sat').classList.toggle('active', styleType === 'satellite');
      document.getElementById('btn-style-topo').classList.toggle('active', styleType === 'topo');
      document.getElementById('btn-style-dark').classList.toggle('active', styleType === 'dark');

      if (isLeafletMode && leafletMap) {
        if (leafletTileLayer) leafletMap.removeLayer(leafletTileLayer);
        let tileUrl = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
        if (styleType === 'topo') {
          tileUrl = 'https://tile.opentopomap.org/{z}/{x}/{y}.png';
        } else if (styleType === 'dark') {
          tileUrl = 'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png';
        }
        leafletTileLayer = L.tileLayer(tileUrl, { maxZoom: 18 }).addTo(leafletMap);
        showToast(`🗺️ 底图已切换为：${styleType === 'satellite' ? '高清卫星实景' : styleType === 'topo' ? '等高地形图' : '暗夜赛博'}`);
        return;
      }

      if (!map) return;'''

content = content.replace(target_style, repl_style)

with open('/home/gcpvm/3DTracker/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated handlers successfully!")
