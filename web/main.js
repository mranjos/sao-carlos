/* São Carlos/SP — maquete 3D interativa
 * Relevo: AWS Terrain Tiles (Terrarium/Mapzen — SRTM/NASA)
 * Prédios e vias: Overture Maps Foundation / OpenStreetMap
 */

const CENTRO = [-47.8908, -22.0175];
const EXAGERO_INICIAL = 1.6;

const TERRAIN_TILES =
  "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";

// ---- cores das vias por classe -------------------------------------------
const COR_VIA = [
  "match", ["get", "class"],
  ["motorway", "trunk"], "#e8843c",
  "primary", "#f2a54a",
  "secondary", "#f6c26b",
  "tertiary", "#ffffff",
  ["residential", "living_street", "unclassified"], "#ffffff",
  "service", "#f1ede6",
  "rail", "#9b8ff5",
  /* pedestre/ciclo/trilha */ "#d8cfc0",
];

const LARGURA_VIA = [
  "interpolate", ["linear"], ["zoom"],
  11, ["match", ["get", "class"],
    ["motorway", "trunk"], 2.4,
    "primary", 2.0,
    "secondary", 1.5,
    "tertiary", 1.0,
    ["residential", "living_street", "unclassified"], 0.6,
    "rail", 0.8,
    0.3],
  16, ["match", ["get", "class"],
    ["motorway", "trunk"], 10,
    "primary", 8,
    "secondary", 7,
    "tertiary", 6,
    ["residential", "living_street", "unclassified"], 5,
    "rail", 2.5,
    1.5],
];

// ---- estilo ---------------------------------------------------------------
const estilo = {
  version: 8,
  sky: {
    "sky-color": "#a6c8e8",
    "horizon-color": "#e8ded0",
    "fog-color": "#e8e2d8",
    "sky-horizon-blend": 0.6,
    "horizon-fog-blend": 0.7,
    "fog-ground-blend": 0.85,
    "atmosphere-blend": ["interpolate", ["linear"], ["zoom"], 10, 1, 14, 0.4],
  },
  sources: {
    // duas fontes raster-dem iguais: uma para o terreno 3D, outra p/ hillshade
    terreno: {
      type: "raster-dem",
      tiles: [TERRAIN_TILES],
      encoding: "terrarium",
      tileSize: 256,
      maxzoom: 13,
      attribution:
        'Relevo: <a href="https://registry.opendata.aws/terrain-tiles/">Terrain Tiles (Mapzen/AWS, SRTM–NASA)</a>',
    },
    sombra: {
      type: "raster-dem",
      tiles: [TERRAIN_TILES],
      encoding: "terrarium",
      tileSize: 256,
      maxzoom: 13,
    },
    predios: {
      type: "geojson",
      data: "../data/buildings.geojson",
      attribution:
        '© <a href="https://overturemaps.org/">Overture Maps</a> · © colaboradores do <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    },
    vias: {
      type: "geojson",
      data: "../data/roads.geojson",
    },
  },
  layers: [
    { id: "fundo", type: "background", paint: { "background-color": "#dcd8cf" } },
    {
      id: "sombra-relevo",
      type: "hillshade",
      source: "sombra",
      paint: {
        "hillshade-exaggeration": 0.45,
        "hillshade-shadow-color": "#5a5245",
        "hillshade-highlight-color": "#ffffff",
        "hillshade-accent-color": "#8a8172",
      },
    },
    {
      id: "vias-linha",
      type: "line",
      source: "vias",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": COR_VIA,
        "line-width": LARGURA_VIA,
        "line-opacity": 0.95,
      },
    },
    {
      id: "predios-3d",
      type: "fill-extrusion",
      source: "predios",
      minzoom: 12,
      paint: {
        "fill-extrusion-height": ["get", "h"],
        "fill-extrusion-base": 0,
        "fill-extrusion-color": [
          "interpolate", ["linear"], ["get", "h"],
          3, "#e3ddd3",
          8, "#d4d2cb",
          20, "#aebfce",
          45, "#7d9cbd",
          90, "#54779e",
        ],
        "fill-extrusion-opacity": 0.95,
        "fill-extrusion-vertical-gradient": true,
      },
    },
  ],
};

// ---- mapa -------------------------------------------------------------------
const map = new maplibregl.Map({
  container: "map",
  style: estilo,
  center: CENTRO,
  zoom: 13.4,
  pitch: 58,
  bearing: -15,
  maxPitch: 78,
  minZoom: 9.5,
  maxBounds: [[-48.45, -22.42], [-47.40, -21.58]],
  attributionControl: { compact: false },
});

map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
map.addControl(new maplibregl.FullscreenControl(), "top-right");

map.on("load", () => {
  map.setTerrain({ source: "terreno", exaggeration: EXAGERO_INICIAL });
});

map.once("idle", () => {
  document.getElementById("carregando").classList.add("oculto");
});

// ---- controles ---------------------------------------------------------------
const slider = document.getElementById("exagero");
const sliderValor = document.getElementById("exagero-valor");
slider.addEventListener("input", () => {
  const v = parseFloat(slider.value);
  sliderValor.textContent = v.toFixed(1) + "×";
  map.setTerrain({ source: "terreno", exaggeration: v });
});

const btn3d = document.getElementById("modo-3d");
const btn2d = document.getElementById("modo-2d");
btn3d.addEventListener("click", () => {
  btn3d.classList.add("ativo");
  btn2d.classList.remove("ativo");
  map.easeTo({ pitch: 58, duration: 800 });
});
btn2d.addEventListener("click", () => {
  btn2d.classList.add("ativo");
  btn3d.classList.remove("ativo");
  map.easeTo({ pitch: 0, bearing: 0, duration: 800 });
});

function ligarCamada(idCheckbox, idsCamadas) {
  document.getElementById(idCheckbox).addEventListener("change", (e) => {
    const vis = e.target.checked ? "visible" : "none";
    for (const id of idsCamadas) map.setLayoutProperty(id, "visibility", vis);
  });
}
ligarCamada("cb-predios", ["predios-3d"]);
ligarCamada("cb-vias", ["vias-linha"]);
ligarCamada("cb-sombra", ["sombra-relevo"]);

// ---- cota (altitude) sob o cursor --------------------------------------------
const cotaEl = document.getElementById("cota");
map.on("mousemove", (e) => {
  const q = map.queryTerrainElevation(e.lngLat);
  if (q == null) { cotaEl.textContent = "—"; return; }
  // queryTerrainElevation devolve o valor já exagerado — normaliza p/ metros reais
  const ex = map.getTerrain() ? map.getTerrain().exaggeration : 1;
  cotaEl.textContent = Math.round(q / (ex || 1)) + " m";
});
