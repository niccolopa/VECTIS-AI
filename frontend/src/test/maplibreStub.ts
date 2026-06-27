// Test-only stub for maplibre-gl (jsdom has no WebGL). Provides just enough of
// the API surface RiskMap uses so components render without a real GL context.
/* eslint-disable @typescript-eslint/no-explicit-any */

class FakeMap {
  constructor(_opts: any) {}
  addControl() {}
  on() {}
  once() {}
  remove() {}
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
