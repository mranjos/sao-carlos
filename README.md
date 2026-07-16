# São Carlos/SP — Maquete 3D interativa

Maquete digital 3D da área urbana de **São Carlos/SP** para o navegador, com:

- **Relevo real** (subidas, descidas, vales) com exagero vertical ajustável;
- **Prédios em 3D** (footprints com altura real ou estimada);
- **Malha viária** colorida por hierarquia (rodovias → ruas locais → ferrovia);
- Navegação livre: girar, inclinar, zoom, modo 2D (planta) e 3D.

O objetivo é servir de **base territorial para estudos de projeto arquitetônico
e urbano** — leitura da topografia, do traçado viário e da massa construída.

## Fontes de dados (todas abertas)

| Camada | Fonte | Licença |
|---|---|---|
| Relevo | [Terrain Tiles (Mapzen/AWS)](https://registry.opendata.aws/terrain-tiles/) — SRTM/NASA ~30 m | domínio público / atribuição |
| Prédios | [Overture Maps Foundation](https://overturemaps.org/) (OSM + footprints ML Microsoft/Google/Esri) | ODbL / CDLA |
| Vias | Overture Maps `transportation` (derivado do OpenStreetMap) | ODbL |

> **Por que não Google Maps?** Os Termos de Serviço do Google proíbem extrair
> ou derivar modelos dos dados/imagens do Maps. As fontes acima são abertas,
> gratuitas e feitas exatamente para esse tipo de uso — basta manter a atribuição.

## Como rodar

### 1. Gerar os dados (uma vez)

```bash
pip install -r pipeline/requirements.txt
python pipeline/fetch_overture.py          # gera data/buildings.geojson e data/roads.geojson
```

O script consulta o GeoParquet planetário do Overture direto no S3 público,
baixando **apenas os blocos que intersectam o bbox** de São Carlos
(definido em `config.json`). Leva alguns minutos.

Alternativa via Overpass/OSM (menos prédios, exige `overpass-api.de` acessível):

```bash
python pipeline/fetch_osm.py
```

### 2. Abrir o viewer

```bash
python -m http.server 8000        # na raiz do repositório
# abra http://localhost:8000/web/
```

Os tiles de relevo são carregados em tempo real da AWS (sem chave de API);
prédios e vias são servidos localmente dos GeoJSON em `data/`.

## Estrutura

```
config.json              # bbox da área urbana + parâmetros (alturas, etc.)
pipeline/
  fetch_overture.py      # pipeline principal (Overture/S3 via DuckDB)
  fetch_osm.py           # alternativa via Overpass API (OSM)
  requirements.txt
data/                    # GeoJSON gerados (prédios com propriedade `h` em metros)
web/
  index.html  main.js  style.css
  vendor/                # MapLibre GL JS vendorizado (sem CDN)
```

## Ajustes úteis

- **Área coberta:** edite `bbox` em `config.json` e rode o pipeline de novo.
- **Exagero do relevo:** slider no painel (1×–4×). Padrão 1,6×.
- **Alturas:** prédios sem altura conhecida recebem `building:levels × 3,2 m`
  ou o padrão de 7 m (`config.json → predios`).

## Limitações conhecidas

- Relevo com resolução ~30 m (SRTM): ótimo para leitura urbana de morros e
  fundos de vale, insuficiente para microtopografia de lote.
- Parte das alturas de prédios é estimada (ML/pavimentos), não cadastral.
- Próximo passo natural: exportar recortes para **Blender/CAD (GLB)** ou
  **impressão 3D (STL)** a partir dos mesmos dados.

## Atribuição

Dados © Overture Maps Foundation · © colaboradores do OpenStreetMap (ODbL) ·
Relevo: Terrain Tiles / Mapzen / AWS Open Data (SRTM–NASA).
