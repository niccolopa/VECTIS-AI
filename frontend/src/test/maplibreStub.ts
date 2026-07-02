// Test-only stub for maplibre-gl (jsdom has no WebGL). Provides just enough of
// the API surface RiskMap uses so components render without a real GL context.
/* eslint-disable @typescript-eslint/no-explicit-any */

// The fixed viewport every FakeMap reports — tests assert tile requests are scoped
// to exactly these bounds (California-ish, nothing else on the planet).
export const STUB_BOUNDS = { west: -125, south: 32, east: -114, north: 42, zoom: 8 };

class FakeMap {
  constructor(_opts: any) {}
  addControl() {}
  on() {}
  once() {}
  remove() {}
  getBounds() {
    return {
      getWest: () => STUB_BOUNDS.west,
      getSouth: () => STUB_BOUNDS.south,
      getEast: () => STUB_BOUNDS.east,
      getNorth: () => STUB_BOUNDS.north,
    };
  }
  getZoom() {
    return STUB_BOUNDS.zoom;
  }
  flyTo(_opts: any) {}
  getSource() {
    return undefined;
  }
  addSource() {}
  addLayer() {}
  getLayer() {
    return undefined;
  }
  setFilter() {}
  setPaintProperty() {}
  isStyleLoaded() {
    return true;
  }
  getCanvas() {
    return { style: {} };
  }
}

class FakeNavigationControl {
  constructor(_opts?: any) {}
}

export const Map = FakeMap;
export const NavigationControl = FakeNavigationControl;

export default { Map: FakeMap, NavigationControl: FakeNavigationControl };
