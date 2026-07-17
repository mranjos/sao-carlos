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

// cores dos pontos de referência por categoria
const COR_REFERENCIA = [
  "match", ["get", "cat"],
  "universidade", "#6741d9",
  "transporte", "#e8590c",
  "saude", "#e03131",
  "comercio", "#0c8599",
  "cultura", "#c2255c",
  "parque", "#2f9e44",
  "#495057",
];

// ---- estilo ---------------------------------------------------------------
// glyphs precisam de URL absoluta; {fontstack}/{range} ficam literais p/ o MapLibre
const GLYPHS_URL = new URL("fonts/", location.href).href + "{fontstack}/{range}.pbf";

const estilo = {
  version: 8,
  glyphs: GLYPHS_URL,
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
    agua: {
      type: "geojson",
      data: "../data/water.geojson",
    },
    campi: {
      type: "geojson",
      data: "../data/campuses.geojson",
    },
    referencias: {
      type: "geojson",
      data: "../data/landmarks.geojson",
    },
    alagamentos: {
      type: "geojson",
      data: "../data/flood-points.geojson",
    },
    intervencoes: {
      type: "geojson",
      data: "../data/interventions.geojson",
    },
    riverwalk: {
      type: "geojson",
      data: "../data/proposal-riverwalk.geojson",
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
      id: "campi-area",
      type: "fill",
      source: "campi",
      paint: { "fill-color": "#b9dba9", "fill-opacity": 0.45 },
    },
    {
      id: "campi-contorno",
      type: "line",
      source: "campi",
      paint: { "line-color": "#74a35c", "line-width": 1.2, "line-dasharray": [3, 2] },
    },
    {
      id: "agua-area",
      type: "fill",
      source: "agua",
      filter: ["in", ["geometry-type"], ["literal", ["Polygon", "MultiPolygon"]]],
      paint: { "fill-color": "#a5c9e8", "fill-opacity": 0.8 },
    },
    {
      id: "agua-linha",
      type: "line",
      source: "agua",
      filter: ["==", ["geometry-type"], "LineString"],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": "#5c9ac9",
        "line-width": ["interpolate", ["linear"], ["zoom"],
          11, ["match", ["get", "class"], "river", 1.6, "canal", 1.2, 0.7],
          16, ["match", ["get", "class"], "river", 5, "canal", 4, 2.5]],
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
    // ---- cenário River Walk (modo proposta; oculto por padrão) ----
    {
      id: "rw-varzea", type: "fill", source: "riverwalk",
      filter: ["==", ["get", "tipo"], "varzea"],
      layout: { visibility: "none" },
      paint: { "fill-color": "#b7e4c7", "fill-opacity": 0.55 },
    },
    {
      id: "rw-lago", type: "fill", source: "riverwalk",
      filter: ["==", ["get", "tipo"], "lago"],
      layout: { visibility: "none" },
      paint: { "fill-color": "#76c7e8", "fill-opacity": 0.9 },
    },
    {
      id: "rw-canal", type: "fill", source: "riverwalk",
      filter: ["==", ["get", "tipo"], "canal"],
      layout: { visibility: "none" },
      paint: { "fill-color": "#4aa3d8", "fill-opacity": 0.92 },
    },
    {
      id: "rw-calcadao", type: "line", source: "riverwalk",
      filter: ["==", ["get", "tipo"], "calcadao"],
      layout: { visibility: "none", "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": "#d9a05b",
        "line-width": ["interpolate", ["linear"], ["zoom"], 13, 2, 17, 8],
      },
    },
    {
      id: "rw-passarela", type: "line", source: "riverwalk",
      filter: ["==", ["get", "tipo"], "passarela"],
      layout: { visibility: "none", "line-cap": "round" },
      paint: { "line-color": "#6c584c", "line-width": ["interpolate", ["linear"], ["zoom"], 13, 1.5, 17, 5] },
    },
    {
      // terraços da Praça d'água do Mercadão (nível 1 = cota d'água)
      id: "rw-praca", type: "fill", source: "riverwalk",
      filter: ["==", ["get", "tipo"], "praca-terraco"],
      layout: { visibility: "none" },
      paint: {
        "fill-color": ["match", ["get", "nivel"],
          1, "#e9d3ae", 2, "#ddba8c", 3, "#cfa269", "#ddba8c"],
        "fill-opacity": 0.95,
        "fill-outline-color": "#8c6239",
      },
    },
    {
      id: "rw-deck", type: "fill", source: "riverwalk",
      filter: ["==", ["get", "tipo"], "deck"],
      layout: { visibility: "none" },
      paint: { "fill-color": "#a3703f", "fill-opacity": 0.97 },
    },
    {
      // pontes veiculares mantendo as travessias sobre o canal
      id: "rw-ponte", type: "line", source: "riverwalk",
      filter: ["==", ["get", "tipo"], "ponte"],
      layout: { visibility: "none", "line-cap": "butt" },
      paint: {
        "line-color": "#455a64",
        "line-width": ["interpolate", ["linear"], ["zoom"], 13, 3, 17, 11],
      },
    },
    {
      id: "rw-ponte-guia", type: "line", source: "riverwalk",
      filter: ["==", ["get", "tipo"], "ponte"],
      layout: { visibility: "none", "line-cap": "butt" },
      paint: {
        "line-color": "#eceff1",
        "line-width": ["interpolate", ["linear"], ["zoom"], 13, 0.6, 17, 1.6],
        "line-dasharray": [2, 2],
      },
    },
    {
      id: "rw-arvore", type: "circle", source: "riverwalk",
      filter: ["==", ["get", "tipo"], "arvore"],
      layout: { visibility: "none" },
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 13, 1.5, 17, 5],
        "circle-color": "#2d6a4f",
        "circle-stroke-color": "#95d5b2",
        "circle-stroke-width": 1,
      },
    },
    // ---- intervenções propostas (visão geral) ----
    {
      id: "intervencoes-area", type: "fill", source: "intervencoes",
      filter: ["in", ["geometry-type"], ["literal", ["Polygon", "MultiPolygon"]]],
      layout: { visibility: "none" },
      paint: {
        "fill-color": ["match", ["get", "tipo"],
          "parque-alagavel", "#74c69d",
          "praca-dagua", "#4cc9f0",
          "ancora", "#ffd166",
          "reservatorio", "#90caf9",
          "#74c69d"],
        "fill-opacity": 0.4,
      },
    },
    {
      id: "intervencoes-contorno", type: "line", source: "intervencoes",
      filter: ["in", ["geometry-type"], ["literal", ["Polygon", "MultiPolygon"]]],
      layout: { visibility: "none" },
      paint: { "line-color": "#2d6a4f", "line-width": 1.5, "line-dasharray": [3, 2] },
    },
    {
      id: "intervencoes-linha", type: "line", source: "intervencoes",
      filter: ["==", ["geometry-type"], "LineString"],
      layout: { visibility: "none", "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": ["match", ["get", "tipo"],
          "boulevard", "#0c8599",
          "circuito", "#7b2cbf",
          "parque-linear", "#2f9e44",
          "binario", "#3a6ea5",
          "#0c8599"],
        "line-width": ["match", ["get", "tipo"], "boulevard", 5, "circuito", 2.5, "binario", 3.5, 4],
        "line-dasharray": ["match", ["get", "tipo"],
          "circuito", ["literal", [0.4, 2]],
          "binario", ["literal", [4, 2]],
          ["literal", [2.5, 1.5]]],
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
    {
      // nomes das vias principais — aparecem antes (zoom mais distante);
      // por último na lista p/ ficarem sobre os prédios
      id: "nomes-principais",
      type: "symbol",
      source: "vias",
      minzoom: 11.5,
      filter: ["all", ["has", "name"],
        ["in", ["get", "class"], ["literal", ["motorway", "trunk", "primary", "secondary"]]]],
      layout: {
        "symbol-placement": "line",
        "text-field": ["get", "name"],
        "text-font": ["Noto Sans Regular"],
        "text-size": ["interpolate", ["linear"], ["zoom"], 11.5, 11, 17, 16],
        "symbol-spacing": 400,
        "text-padding": 4,
      },
      paint: {
        "text-color": "#7a4a12",
        "text-halo-color": "rgba(255,255,255,0.92)",
        "text-halo-width": 1.8,
      },
    },
    {
      // nomes dos córregos e represas
      id: "agua-nomes",
      type: "symbol",
      source: "agua",
      minzoom: 12.5,
      filter: ["has", "name"],
      layout: {
        "symbol-placement": "line",
        "text-field": ["get", "name"],
        "text-font": ["Noto Sans Regular"],
        "text-size": ["interpolate", ["linear"], ["zoom"], 12.5, 10.5, 17, 14],
        "symbol-spacing": 450,
      },
      paint: {
        "text-color": "#33658a",
        "text-halo-color": "rgba(255,255,255,0.9)",
        "text-halo-width": 1.5,
      },
    },
    {
      // nomes das demais ruas — só em zoom próximo
      id: "nomes-ruas",
      type: "symbol",
      source: "vias",
      minzoom: 14,
      filter: ["all", ["has", "name"],
        ["!", ["in", ["get", "class"], ["literal", ["motorway", "trunk", "primary", "secondary"]]]]],
      layout: {
        "symbol-placement": "line",
        "text-field": ["get", "name"],
        "text-font": ["Noto Sans Regular"],
        "text-size": ["interpolate", ["linear"], ["zoom"], 14, 10, 17, 14],
        "symbol-spacing": 300,
        "text-padding": 3,
      },
      paint: {
        "text-color": "#4a4a4a",
        "text-halo-color": "rgba(255,255,255,0.92)",
        "text-halo-width": 1.6,
      },
    },
    {
      // zona de alerta de alagamento (halo translúcido)
      id: "alagamentos-halo",
      type: "circle",
      source: "alagamentos",
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"],
          11, ["match", ["get", "sev"], "alta", 16, 10],
          16, ["match", ["get", "sev"], "alta", 46, 28]],
        "circle-color": ["match", ["get", "sev"], "alta", "#d90429", "#f4771f"],
        "circle-opacity": 0.22,
        "circle-stroke-color": ["match", ["get", "sev"], "alta", "#d90429", "#f4771f"],
        "circle-stroke-width": 1.5,
        "circle-stroke-opacity": 0.6,
      },
    },
    {
      id: "alagamentos-nucleo",
      type: "circle",
      source: "alagamentos",
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 4.5, 16, 8],
        "circle-color": ["match", ["get", "sev"], "alta", "#d90429", "#f4771f"],
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 2,
      },
    },
    {
      id: "alagamentos-nome",
      type: "symbol",
      source: "alagamentos",
      minzoom: 12.5,
      layout: {
        "text-field": ["get", "name"],
        "text-font": ["Noto Sans Regular"],
        "text-size": 12,
        "text-offset": [0, 1.3],
        "text-anchor": "top",
      },
      paint: {
        "text-color": "#a4001f",
        "text-halo-color": "rgba(255,255,255,0.95)",
        "text-halo-width": 2,
      },
    },
    {
      id: "intervencoes-nome", type: "symbol", source: "intervencoes",
      minzoom: 12.8,
      filter: ["in", ["geometry-type"], ["literal", ["Polygon", "MultiPolygon"]]],
      layout: {
        visibility: "none",
        "text-field": ["get", "name"],
        "text-font": ["Noto Sans Regular"],
        "text-size": 12.5,
      },
      paint: {
        "text-color": "#1b4332",
        "text-halo-color": "rgba(255,255,255,0.95)",
        "text-halo-width": 2,
      },
    },
    {
      id: "intervencoes-nome-linha", type: "symbol", source: "intervencoes",
      minzoom: 12.8,
      filter: ["==", ["geometry-type"], "LineString"],
      layout: {
        visibility: "none",
        "symbol-placement": "line",
        "text-field": ["get", "name"],
        "text-font": ["Noto Sans Regular"],
        "text-size": 12,
        "symbol-spacing": 500,
      },
      paint: {
        "text-color": "#1b4332",
        "text-halo-color": "rgba(255,255,255,0.95)",
        "text-halo-width": 2,
      },
    },
    {
      id: "referencias-ponto",
      type: "circle",
      source: "referencias",
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 4, 16, 7],
        "circle-color": COR_REFERENCIA,
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 2,
      },
    },
    {
      id: "referencias-nome",
      type: "symbol",
      source: "referencias",
      layout: {
        "text-field": ["get", "name"],
        "text-font": ["Noto Sans Regular"],
        "text-size": ["interpolate", ["linear"], ["zoom"], 10, 11.5, 16, 15],
        "text-offset": [0, 1.1],
        "text-anchor": "top",
        "text-optional": false,
      },
      paint: {
        "text-color": COR_REFERENCIA,
        "text-halo-color": "rgba(255,255,255,0.95)",
        "text-halo-width": 2,
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
  hash: true, // câmera na URL — permite compartilhar uma vista exata
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
ligarCamada("cb-nomes", ["nomes-principais", "nomes-ruas"]);
ligarCamada("cb-agua", ["agua-area", "agua-linha", "agua-nomes"]);
ligarCamada("cb-referencias", ["referencias-ponto", "referencias-nome", "campi-area", "campi-contorno"]);
ligarCamada("cb-alagamentos", ["alagamentos-halo", "alagamentos-nucleo", "alagamentos-nome"]);
ligarCamada("cb-sombra", ["sombra-relevo"]);

// ---- popup dos pontos de alagamento ------------------------------------------
map.on("click", "alagamentos-nucleo", (e) => {
  const p = e.features[0].properties;
  const aprox = p.aproximado ? " <em>(posição aproximada)</em>" : "";
  new maplibregl.Popup({ maxWidth: "320px" })
    .setLngLat(e.features[0].geometry.coordinates)
    .setHTML(
      `<strong>${p.name}</strong>${aprox}<br>` +
      `<span class="pop-meta">Córrego: ${p.corrego} · severidade ${p.sev === "alta" ? "ALTA" : "média"}</span>` +
      `<p class="pop-desc">${p.desc}</p>` +
      `<span class="pop-fonte">Fontes: ${p.fonte}</span>`
    )
    .addTo(map);
});
map.on("mouseenter", "alagamentos-nucleo", () => { map.getCanvas().style.cursor = "pointer"; });
map.on("mouseleave", "alagamentos-nucleo", () => { map.getCanvas().style.cursor = ""; });

// ---- popups das intervenções propostas ---------------------------------------
const HORIZONTE = { curto: "curto prazo", medio: "médio prazo", longo: "longo prazo" };
for (const id of ["intervencoes-area", "intervencoes-linha"]) {
  map.on("click", id, (e) => {
    const p = e.features[0].properties;
    const aprox = p.aproximado ? " <em>(posição aproximada)</em>" : "";
    new maplibregl.Popup({ maxWidth: "330px" })
      .setLngLat(e.lngLat)
      .setHTML(
        `<strong>${p.name}</strong>${aprox}<br>` +
        `<span class="pop-meta pop-proposta">Proposta · ${HORIZONTE[p.horizonte] || p.horizonte}</span>` +
        `<p class="pop-desc">${p.desc}</p>`
      )
      .addTo(map);
  });
  map.on("mouseenter", id, () => { map.getCanvas().style.cursor = "pointer"; });
  map.on("mouseleave", id, () => { map.getCanvas().style.cursor = ""; });
}

// popups dos elementos detalhados da praça
for (const id of ["rw-praca", "rw-deck"]) {
  map.on("click", id, (e) => {
    const p = e.features[0].properties;
    new maplibregl.Popup({ maxWidth: "300px" })
      .setLngLat(e.lngLat)
      .setHTML(
        `<strong>${p.name}</strong><br>` +
        `<span class="pop-meta pop-proposta">Praça d'água do Mercadão</span>` +
        `<p class="pop-desc">${p.desc}</p>`
      )
      .addTo(map);
  });
  map.on("mouseenter", id, () => { map.getCanvas().style.cursor = "pointer"; });
  map.on("mouseleave", id, () => { map.getCanvas().style.cursor = ""; });
}

// ---- modo hoje ⇄ proposta ------------------------------------------------------
const CAMADAS_PROPOSTA = [
  "rw-varzea", "rw-lago", "rw-canal", "rw-praca", "rw-deck", "rw-calcadao",
  "rw-passarela", "rw-ponte", "rw-ponte-guia", "rw-arvore",
  "intervencoes-area", "intervencoes-contorno", "intervencoes-linha",
  "intervencoes-nome", "intervencoes-nome-linha",
];
let modoProposta = false;
const btnProposta = document.getElementById("modo-proposta");

function aplicarModo() {
  const vis = modoProposta ? "visible" : "none";
  for (const id of CAMADAS_PROPOSTA) map.setLayoutProperty(id, "visibility", vis);
  // no cenário proposto, os alertas de alagamento ficam esmaecidos (problema tratado)
  map.setPaintProperty("alagamentos-halo", "circle-opacity", modoProposta ? 0.05 : 0.22);
  map.setPaintProperty("alagamentos-halo", "circle-stroke-opacity", modoProposta ? 0.15 : 0.6);
  map.setPaintProperty("alagamentos-nucleo", "circle-opacity", modoProposta ? 0.35 : 1);
  document.getElementById("cb-alagamentos").disabled = modoProposta;
  btnProposta.classList.toggle("ativo", modoProposta);
  btnProposta.textContent = modoProposta ? "✕ Voltar a hoje" : "✨ Ver proposta (River Walk)";
}

btnProposta.addEventListener("click", () => {
  modoProposta = !modoProposta;
  aplicarModo();
  if (modoProposta) {
    map.flyTo({ center: [-47.8845, -22.0209], zoom: 15.1, pitch: 60, bearing: -105, duration: 2200 });
  }
});

// ---- tour "Entender a bacia" ---------------------------------------------------
const TOUR = [
  {
    c: [-47.889, -22.017], z: 12.1, p: 65, b: -20,
    t: "<b>1/4 · A cidade entre espigões.</b> São Carlos cresceu sobre um planalto cortado por vales. Com o relevo exagerado 3×, repare como o terreno desce de todos os lados para o centro.",
  },
  {
    c: [-47.882, -22.0215], z: 14.0, p: 62, b: -78,
    t: "<b>2/4 · O vale do Gregório.</b> O córrego nasce a leste e desce por este vale, canalizado e espremido pelas marginais. Toda a chuva dos bairros altos converge para esta calha.",
  },
  {
    c: [-47.8911, -22.0202], z: 15.3, p: 58, b: -30,
    t: "<b>3/4 · A baixada do Mercado.</b> O ponto mais baixo do centro: o canal estrangulado transborda aqui — 130 lojas atingidas em 2020. É também o coração histórico: Mercadão, Catedral, Estação.",
  },
  {
    c: [-47.887, -22.026], z: 13.3, p: 60, b: -10,
    t: "<b>4/4 · A estratégia.</b> Reter a montante (Parque Alagável da Chaminé, à esquerda) e na bacia do Simeão (abaixo), depois requalificar a baixada. Toque em “✨ Ver proposta” para o cenário River Walk.",
  },
];
let tourIdx = -1;
const tourBox = document.getElementById("tour");
const tourTexto = document.getElementById("tour-texto");

function irParaEtapa(i) {
  tourIdx = i;
  const e = TOUR[i];
  map.flyTo({ center: e.c, zoom: e.z, pitch: e.p, bearing: e.b, duration: 2600 });
  tourTexto.innerHTML = e.t;
  document.getElementById("tour-ant").disabled = i === 0;
  document.getElementById("tour-prox").textContent = i === TOUR.length - 1 ? "Concluir" : "Próximo ›";
}

let exageroAntesDoTour = null;

function sairDoTour() {
  tourBox.classList.add("oculto");
  tourIdx = -1;
  if (exageroAntesDoTour != null) {
    slider.value = exageroAntesDoTour;
    sliderValor.textContent = parseFloat(exageroAntesDoTour).toFixed(1) + "×";
    map.setTerrain({ source: "terreno", exaggeration: parseFloat(exageroAntesDoTour) });
    exageroAntesDoTour = null;
  }
}

document.getElementById("btn-tour").addEventListener("click", () => {
  tourBox.classList.remove("oculto");
  exageroAntesDoTour = slider.value;
  slider.value = 3.0;
  sliderValor.textContent = "3.0×";
  map.setTerrain({ source: "terreno", exaggeration: 3.0 });
  irParaEtapa(0);
});
document.getElementById("tour-ant").addEventListener("click", () => {
  if (tourIdx > 0) irParaEtapa(tourIdx - 1);
});
document.getElementById("tour-prox").addEventListener("click", () => {
  if (tourIdx < TOUR.length - 1) irParaEtapa(tourIdx + 1);
  else sairDoTour();
});
document.getElementById("tour-sair").addEventListener("click", sairDoTour);

// ---- modo apresentação (?ui=0 esconde a interface; &modo=proposta abre no cenário)
const params = new URLSearchParams(location.search);
if (params.get("ui") === "0") {
  document.getElementById("painel").style.display = "none";
  document.querySelectorAll(
    ".maplibregl-ctrl-top-right, .maplibregl-ctrl-bottom-left"
  ).forEach((el) => { el.style.display = "none"; });
}
if (params.get("modo") === "proposta") {
  map.on("load", () => {
    modoProposta = true;
    aplicarModo();
  });
}

// ---- cota (altitude) sob o cursor --------------------------------------------
const cotaEl = document.getElementById("cota");
map.on("mousemove", (e) => {
  const q = map.queryTerrainElevation(e.lngLat);
  if (q == null) { cotaEl.textContent = "—"; return; }
  // queryTerrainElevation devolve o valor já exagerado — normaliza p/ metros reais
  const ex = map.getTerrain() ? map.getTerrain().exaggeration : 1;
  cotaEl.textContent = Math.round(q / (ex || 1)) + " m";
});
